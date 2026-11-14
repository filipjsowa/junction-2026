"""Load a JSONL file of messages, embed them, and insert them into `messages`.

Usage: python -m ingest.load_jsonl data/dev/sample.jsonl
Format of each line: see data/dev/README.md.
"""
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

import requests

from ingest.db import connect  # loads .env first
from ingest.embed import embed

INSERT = """
INSERT IGNORE INTO messages
  (platform, channel_id, author_id, text, text_hash, lang, ts, url,
   forwarded_from, is_control, synthetic, label, embedding)
VALUES
  (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, VEC_FromText(%s))
"""


def to_utc(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def fetch_oxylabs_summary(text: str) -> str:
    url_match = re.search(r'https?://[^\s]+', text)
    if not url_match:
        return text
    url = url_match.group(0)
    api_key = os.environ.get("OXYLABS_API_KEY")
    if not api_key:
        return text
    try:
        res = requests.post(
            "https://realtime.oxylabs.io/v1/queries",
            auth=("user", api_key),
            json={"source": "universal", "url": url},
            timeout=5
        )
        res.raise_for_status()
        # Simulate extraction and summary
        return text + f"\n[Link Summary: {url} HTML content]"
    except Exception:
        return text


def main(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    
    for r in rows:
        r["text"] = fetch_oxylabs_summary(r["text"])

    vectors = embed([r["text"] for r in rows])

    with connect() as conn, conn.cursor() as cur:
        for r, v in zip(rows, vectors):
            cur.execute(
                INSERT,
                (
                    r["platform"],
                    r["channel_id"],
                    r.get("author_id"),
                    r["text"],
                    hashlib.sha256(r["text"].encode()).hexdigest(),
                    r.get("lang"),
                    to_utc(r["ts"]),
                    r.get("url"),
                    r.get("forwarded_from"),
                    r.get("is_control", False),
                    r.get("synthetic", False),
                    r.get("label"),
                    json.dumps(v),
                ),
            )
    print(f"Loaded {len(rows)} messages from {path}")


if __name__ == "__main__":
    main(sys.argv[1])
