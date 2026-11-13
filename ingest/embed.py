"""Client for the external embeddings API (assumed OpenAI-compatible).

If your API has a different request/response shape, change only this file.
"""
import os

import httpx

BASE_URL = os.environ["EMBEDDINGS_BASE_URL"].rstrip("/")
API_KEY = os.environ.get("EMBEDDINGS_API_KEY", "")
MODEL = os.environ.get("EMBEDDINGS_MODEL", "")
DIM = int(os.environ["EMBEDDING_DIM"])
BATCH_SIZE = 64


def embed(texts: list[str]) -> list[list[float]]:
    """Return one vector per text, in the same order."""
    vectors: list[list[float]] = []
    headers = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
    with httpx.Client(timeout=60) as client:
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start : start + BATCH_SIZE]
            for attempt in range(3):
                try:
                    resp = client.post(
                        f"{BASE_URL}/embeddings",
                        headers=headers,
                        json={"model": MODEL, "input": batch},
                    )
                    resp.raise_for_status()
                    break
                except httpx.HTTPError:
                    if attempt == 2:
                        raise
            data = sorted(resp.json()["data"], key=lambda d: d["index"])
            vectors.extend(d["embedding"] for d in data)
    for v in vectors:
        if len(v) != DIM:
            raise ValueError(f"Embedding has {len(v)} dims, EMBEDDING_DIM is {DIM}")
    return vectors
