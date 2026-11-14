"""
Basic clustering module.
Pulls unclustered messages from MariaDB, clusters them using their embeddings,
and writes the cluster_id back to the messages table.
Structured for HDBSCAN/BERTopic but uses a placeholder/simple distance-based algorithm for now.

Modal GPU Offloading:
You can run this script remotely on Modal to leverage GPU acceleration.
Run the following command:
    modal run detect/cluster.py
"""

import json
import logging
import math
import os
from datetime import datetime
import modal

from ingest.db import connect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = modal.App("swarm-detector-clustering")
image = modal.Image.debian_slim().pip_install("pymysql", "python-dotenv")

def cosine_distance(vec1: list[float], vec2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 1.0
    return 1.0 - (dot / (norm1 * norm2))


def simple_cluster(embeddings: list[list[float]], threshold: float = 0.15) -> list[int]:
    """
    Placeholder clustering algorithm (simple greedy clustering).
    Can be replaced with BERTopic/HDBSCAN later.
    Returns a list of local cluster group IDs. -1 means unclustered/noise.
    """
    cluster_ids = [-1] * len(embeddings)
    current_cluster = 0
    
    for i, vec in enumerate(embeddings):
        if cluster_ids[i] != -1:
            continue
            
        cluster_ids[i] = current_cluster
        cluster_size = 1
        
        for j in range(i + 1, len(embeddings)):
            if cluster_ids[j] == -1:
                dist = cosine_distance(vec, embeddings[j])
                if dist <= threshold:
                    cluster_ids[j] = current_cluster
                    cluster_size += 1
        
        # We only form a cluster if size > 1, otherwise it's noise
        if cluster_size > 1:
            current_cluster += 1
        else:
            cluster_ids[i] = -1
            
    return cluster_ids


def compute_centroid(embeddings: list[list[float]]) -> list[float]:
    """Computes the mean vector (centroid) of a list of embeddings."""
    n = len(embeddings)
    dim = len(embeddings[0])
    centroid = [0.0] * dim
    for vec in embeddings:
        for i in range(dim):
            centroid[i] += vec[i]
    return [x / n for x in centroid]


@app.function(gpu="any", image=image, secrets=[modal.Secret.from_dotenv()])
def run_clustering():
    logger.info("Starting clustering process...")
    
    # Ensure connection to Hostinger MariaDB using external IP/domain if on Modal,
    # falling back to localhost for local dev.
    if not modal.is_local():
        # Read the domain/IP from .env or fallback to a default
        domain = os.environ.get("DOMAIN", "")
        ext_host = domain.split(":")[0] if domain else ""
        if ext_host:
            os.environ["DB_HOST"] = ext_host
    else:
        # Default local dev fallback
        if not os.environ.get("DB_HOST"):
            os.environ["DB_HOST"] = "127.0.0.1"

    conn = connect()
    try:
        with conn.cursor() as cursor:
            # Pull unclustered messages. 
            # Note: MariaDB VECTOR can be read with VEC_AsText()
            # Messages that don't form a cluster remain with cluster_id IS NULL
            # so they can potentially cluster with new messages arriving later.
            cursor.execute(
                "SELECT id, VEC_AsText(embedding) as embedding_text, ts FROM messages WHERE cluster_id IS NULL"
            )
            rows = cursor.fetchall()
            
            if not rows:
                logger.info("No unclustered messages found.")
                return

            logger.info(f"Found {len(rows)} unclustered messages.")
            
            ids = []
            embeddings = []
            timestamps = []
            for row in rows:
                ids.append(row["id"])
                embeddings.append(json.loads(row["embedding_text"]))
                timestamps.append(row["ts"])
                
            # Run clustering (local IDs)
            local_cluster_labels = simple_cluster(embeddings, threshold=0.15)
            
            # Group by local cluster ID
            clusters_map = {}
            for i, label in enumerate(local_cluster_labels):
                if label == -1:
                    continue
                if label not in clusters_map:
                    clusters_map[label] = {
                        "ids": [],
                        "embeddings": [],
                        "timestamps": []
                    }
                clusters_map[label]["ids"].append(ids[i])
                clusters_map[label]["embeddings"].append(embeddings[i])
                clusters_map[label]["timestamps"].append(timestamps[i])

            if not clusters_map:
                logger.info("No clusters formed from the current unclustered messages.")
                return

            logger.info(f"Formed {len(clusters_map)} new clusters.")

            total_messages_updated = 0
            
            # Insert new clusters into the DB and update messages
            for local_id, data in clusters_map.items():
                size = len(data["ids"])
                first_seen = min(data["timestamps"])
                last_seen = max(data["timestamps"])
                centroid = compute_centroid(data["embeddings"])
                
                # Create cluster entry
                cursor.execute(
                    """
                    INSERT INTO clusters (size, first_seen, last_seen, centroid)
                    VALUES (%s, %s, %s, VEC_FromText(%s))
                    """,
                    (size, first_seen, last_seen, json.dumps(centroid))
                )
                new_cluster_id = cursor.lastrowid
                
                # Update messages with the real cluster ID
                update_data = [(new_cluster_id, msg_id) for msg_id in data["ids"]]
                cursor.executemany(
                    "UPDATE messages SET cluster_id = %s WHERE id = %s",
                    update_data
                )
                total_messages_updated += len(update_data)
                
            logger.info(f"Successfully processed {len(clusters_map)} clusters and updated {total_messages_updated} messages.")
            
    except Exception as e:
        logger.error(f"Error during clustering: {e}")
    finally:
        conn.close()

@app.local_entrypoint()
def main():
    run_clustering.remote()

if __name__ == "__main__":
    # If run natively (e.g. `python -m detect.cluster`), run locally
    run_clustering.local()
