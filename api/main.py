import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import pymysql

from ingest.db import connect
from ingest.embed import embed
from detect.scoring import explain

app = FastAPI(title="Swarm Detector")


class ScoreRequest(BaseModel):
    text: str
    platform: str | None = None


class Label(BaseModel):
    label: str  # 'confirmed' | 'rejected' | 'benign'
    by: str
    note: str | None = None
    password: str | None = None


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/score")
def score(req: ScoreRequest) -> dict:
    """
    Score a message from any platform (Telegram, Twitter, BlueSky, etc.) 
    to detect coordinated disinformation swarms.
    """
    threshold = float(os.environ.get("MATCH_THRESHOLD", "0.80"))
    
    # Embed the incoming message
    try:
        vectors = embed([req.text])
        if not vectors:
            raise HTTPException(status_code=500, detail="Failed to get embedding")
        query_vec = vectors[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    conn = connect()
    try:
        with conn.cursor() as cur:
            # Find nearest messages with MariaDB vector index
            query = """
            SELECT id AS message_id, cluster_id, platform, channel_id AS channel, ts,
                   VEC_DISTANCE_COSINE(embedding, VEC_FromText(%s)) AS dist
            FROM messages
            WHERE cluster_id IS NOT NULL
            ORDER BY VEC_DISTANCE_COSINE(embedding, VEC_FromText(%s))
            LIMIT 20
            """
            vec_json = json.dumps(query_vec)
            cur.execute(query, (vec_json, vec_json))
            matches = cur.fetchall()

            if not matches:
                return {"verdict": "unknown", "score": None}

            best_match = matches[0]
            similarity = 1.0 - best_match["dist"]

            if similarity < threshold:
                return {"verdict": "unknown", "score": None}

            cluster_id = best_match["cluster_id"]
            
            # Fetch cluster
            cur.execute("SELECT * FROM clusters WHERE id = %s", (cluster_id,))
            cluster = cur.fetchone()
            if not cluster:
                return {"verdict": "unknown", "score": None}

            db_features = cluster.get("features")
            if isinstance(db_features, str):
                db_features = json.loads(db_features)
            elif db_features is None:
                db_features = {}

            features = {k: float(v) for k, v in db_features.items() if isinstance(v, (int, float))}
            features["match_similarity"] = similarity

            details = db_features.get("details", {})
            details["match_similarity"] = {
                "pct": similarity * 100,
                "size": cluster.get("size", 0),
                "cluster_id": cluster_id
            }

            explanation = explain(features, details)

            techniques = cluster.get("techniques")
            if isinstance(techniques, str):
                techniques = json.loads(techniques)
            elif techniques is None:
                techniques = []

            cur.execute("SELECT precision_score, fpr, eval_set FROM eval_runs ORDER BY id DESC LIMIT 1")
            eval_metrics = cur.fetchone()
            if eval_metrics:
                eval_metrics["precision"] = eval_metrics.pop("precision_score")
            else:
                eval_metrics = {"precision": None, "fpr": None, "eval_set": None}

            evidence = []
            for m in matches:
                if m["cluster_id"] == cluster_id:
                    m["similarity"] = 1.0 - m["dist"]
                    m["ts"] = m["ts"].isoformat() + "Z" if m["ts"] else None
                    if "dist" in m: del m["dist"]
                    if "cluster_id" in m: del m["cluster_id"]
                    evidence.append(m)

            return {
                "verdict": cluster.get("suggested", "coordinated_unreviewed"),
                "score": explanation["score"],
                "matched_cluster": {
                    "id": cluster_id,
                    "narrative": cluster.get("narrative"),
                    "similarity": similarity,
                    "review": {
                        "status": cluster.get("human_label"),
                        "by": cluster.get("labeled_by"),
                        "at": cluster["labeled_at"].isoformat() + "Z" if cluster.get("labeled_at") else None
                    }
                },
                "reasons": explanation["reasons"],
                "technique": techniques,
                "evidence": evidence[:5],
                "model_quality": eval_metrics
            }

    finally:
        conn.close()


@app.get("/clusters")
def clusters() -> list[dict]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM clusters ORDER BY auto_score DESC")
            rows = cur.fetchall()
            for r in rows:
                for col in ["features", "contributions", "techniques"]:
                    if isinstance(r.get(col), str):
                        r[col] = json.loads(r[col])
                for col in ["first_seen", "last_seen", "labeled_at"]:
                    if r.get(col):
                        r[col] = r[col].isoformat() + "Z"
            return rows
    finally:
        conn.close()


@app.get("/clusters/{cluster_id}")
def cluster(cluster_id: int) -> dict:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM clusters WHERE id = %s", (cluster_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Cluster not found")
                
            for col in ["features", "contributions", "techniques"]:
                if isinstance(row.get(col), str):
                    row[col] = json.loads(row[col])
            for col in ["first_seen", "last_seen", "labeled_at"]:
                if row.get(col):
                    row[col] = row[col].isoformat() + "Z"
            
            cur.execute("SELECT id, platform, channel_id, author_id, text, lang, ts FROM messages WHERE cluster_id = %s LIMIT 10", (cluster_id,))
            msgs = cur.fetchall()
            for m in msgs:
                if m.get("ts"):
                    m["ts"] = m["ts"].isoformat() + "Z"
            
            row["sample_messages"] = msgs
            return row
    finally:
        conn.close()


@app.get("/review/queue")
def review_queue() -> list[dict]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM clusters WHERE human_label IS NULL ORDER BY auto_score DESC")
            rows = cur.fetchall()
            for r in rows:
                for col in ["features", "contributions", "techniques"]:
                    if isinstance(r.get(col), str):
                        r[col] = json.loads(r[col])
                for col in ["first_seen", "last_seen", "labeled_at"]:
                    if r.get(col):
                        r[col] = r[col].isoformat() + "Z"
            return rows
    finally:
        conn.close()


@app.post("/clusters/{cluster_id}/label")
def label_cluster(cluster_id: int, body: Label) -> dict:
    reviewer_password = os.environ.get("REVIEWER_PASSWORD")
    if body.password and body.password != reviewer_password:
        raise HTTPException(status_code=401, detail="Invalid password")
    
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE clusters SET human_label = %s, labeled_by = %s, labeled_at = UTC_TIMESTAMP(3), label_note = %s WHERE id = %s",
                (body.label, body.by, body.note, cluster_id)
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Cluster not found")
            
            cur.execute("SELECT id, human_label, labeled_by, labeled_at FROM clusters WHERE id = %s", (cluster_id,))
            row = cur.fetchone()
            if row and row.get("labeled_at"):
                row["labeled_at"] = row["labeled_at"].isoformat() + "Z"
            return row
    finally:
        conn.close()


@app.get("/metrics")
def metrics() -> dict:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT precision_score, fpr, n_labels, eval_set FROM eval_runs ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            if row:
                row["precision"] = row.pop("precision_score")
                return row
            return {"precision": None, "fpr": None, "n_labels": 0, "eval_set": None}
    finally:
        conn.close()
