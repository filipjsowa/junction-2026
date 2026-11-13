# Swarm Detector

Detects coordinated propaganda swarms in Telegram messages and explains every score.
Project context, rules and commands for humans and Claude Code: [`CLAUDE.md`](CLAUDE.md).

## Quick start

```bash
cp .env.example .env            # fill in DB passwords, embeddings API, AI Router
# set VECTOR(1024) in db/schema.sql to your embedding dimension
docker compose up -d db
pip install -r requirements.txt
python -m ingest.load_jsonl data/dev/sample.jsonl
uvicorn api.main:app --reload   # http://localhost:8000/docs
```

## Kickoff prompts for Claude Code (one per person)

**Person 1 – data**
> Read CLAUDE.md and data/dev/README.md. Write `ingest/make_synthetic.py` that uses the AI Router to generate
> `planted_swarms.jsonl` and `benign_trap.jsonl` as described there, then `ingest/convert_ira.py` that turns a
> FiveThirtyEight russian-troll-tweets CSV into a 50k-row JSONL sample. Keep it simple.

**Person 2 – detection**
> Read CLAUDE.md and detect/scoring.py. Write `detect/cluster.py`: read messages and embeddings from MariaDB, run
> BERTopic with precomputed embeddings, write cluster_id and clusters rows. Then `detect/features.py` computing the six
> features per cluster, and `detect/evaluate.py` computing precision and false-positive rate on synthetic labels.

**Person 3 – API and web**
> Read CLAUDE.md and api/main.py. Implement `/score` for real: embed the text, nearest-neighbour query in MariaDB,
> "unknown" below MATCH_THRESHOLD, else return detect.scoring.explain() for the matched cluster. Then build the check
> page in web/ against api/fixtures/score_example.json.

## Hostinger MCP

`.mcp.json` adds Hostinger's hosted MCP server (`https://mcp.hostinger.com`, browser sign-in on first use).
Enable the VPS product group in the Hostinger Connector to manage the server from Claude Code.
