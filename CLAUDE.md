# Swarm Detector

Hackathon project (Junction, Hostinger challenge). Detects coordinated propaganda swarms in Telegram messages
(first case: disinformation after the Kraków attack on 7 Nov 2026) and returns an **explainable** 0–1 score.
Must run live on a Hostinger VPS (KVM 2: 2 vCPU, 8 GB RAM, Docker) with a public URL for the judges.

Full team plan: `docs/PLAN.md`.

## Architecture

```
dev JSONL / Telegram export ──> ingest (embed via external API) ──> MariaDB 11.8 (messages, VECTOR index)
                                                                        │
                       detect: BERTopic clustering → coordination features → score + LLM narrative ──> clusters
                                                                        │
                       api (FastAPI): /score /clusters /review /metrics ──> web (check page, graph, reviewer console)
                                                                        │
                       reviewer labels ──> clusters.human_label ──> refit weights, precision / false-positive rate
```

## Owners

| Folder    | Owner    | What                                                              |
| --------- | -------- | ----------------------------------------------------------------- |
| `ingest/` | Person 1 | Load JSONL, embed, insert into `messages`; Telegram export        |
| `detect/` | Person 2 | Clustering, coordination features, scoring, LLM narrative, eval   |
| `api/`    | Person 3 | FastAPI endpoints                                                 |
| `web/`    | Person 3 | Check page, cluster graph, reviewer console, metrics page         |
| `db/`     | shared   | `schema.sql` is the contract; change it only after telling the team |

## Rules (these are what the judges score)

- The score is computed **only** from the named features in `detect/scoring.py`. The LLM writes the narrative and
  technique labels; it never sets or changes the number.
- Every `/score` response carries `reasons` (feature, value, contribution, sentence) and `evidence` (message ids).
- No cluster closer than the match threshold → `verdict: "unknown"`, `score: null`. Never return 0 for "no match".
- Similar text is a topic, not a swarm: a high score needs coordination evidence (spread, burst, near-copies, vs chance).
- Synthetic dev rows (`synthetic: true`) never count in reported precision / false-positive numbers.
- No sender location is collected or shown.

## Code conventions

- Python 3.11+, plain SQL with PyMySQL (no ORM), FastAPI. Keep it simple: no extra layers, classes or features
  nobody asked for.
- All config from environment variables (`.env`, see `.env.example`). One source of truth; no hard-coded keys or URLs.
- The embeddings API is assumed OpenAI-compatible (`POST {base}/embeddings`). If it differs, change only `ingest/embed.py`.
- LLM calls go through the Hostinger AI Router (OpenAI-compatible) using `AI_ROUTER_*` env vars.

## MariaDB vector rules

- Needs MariaDB 11.8+. `messages.embedding` is `VECTOR(1024)`: set this to the real embedding dimension
  (`EMBEDDING_DIM`) in `db/schema.sql` before the first start.
- The indexed vector column is NOT NULL: embed before inserting.
- One vector index per table.
- Insert vectors with `VEC_FromText('[...]')` (send `json.dumps(list_of_floats)`).
- The index is used only with a bare `ORDER BY VEC_DISTANCE_COSINE(embedding, VEC_FromText(%s)) LIMIT k`.
  Filter by threshold in an outer query. Cosine distance = 1 − similarity.
- `PRECISION` is reserved; the column is `precision_score`.

## Commands

```bash
cp .env.example .env                      # fill in keys
docker compose up -d db                   # MariaDB, runs db/schema.sql on first start
pip install -r requirements.txt
python -m ingest.load_jsonl data/dev/sample.jsonl
uvicorn api.main:app --reload             # http://localhost:8000/docs
docker compose up -d --build              # full stack (db + api)
```

Reset the database: `docker compose down -v && docker compose up -d db`.
