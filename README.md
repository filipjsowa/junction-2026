# Swarm Detector

Detects coordinated propaganda swarms in social media posts (Telegram, Twitter/X, Bluesky) and explains every score.
Project context, rules and commands for humans and Claude Code: [`CLAUDE.md`](CLAUDE.md).

## Quick start (only Docker and make needed on your machine)

```bash
cp .env.example .env            # fill in DB passwords, embeddings API, AI Router
# set VECTOR(1024) in db/schema.sql to your embedding dimension
make up                         # http://localhost:8000/docs, code reloads on save
make load FILE=data/dev/sample.jsonl
make help                       # all commands
```

No `make` (e.g. Windows without WSL)? The same commands: `docker compose up -d --build`,
`docker compose run --rm api python -m ingest.load_jsonl data/dev/sample.jsonl`.

Optional: `make venv` creates `.venv/` inside the project, only so your editor gets autocompletion.

## Deploy to the Hostinger VPS

1. In hPanel, open the VPS (Ubuntu, Docker template is fine) and note its IP. In the VPS firewall, allow ports 22, 80 and 443.
2. SSH in as root and run the one-time setup (installs Docker, make and git if missing, clones to `/opt/swarm-detector`):
   ```bash
   git clone <repo URL> /opt/swarm-detector && bash /opt/swarm-detector/deploy/setup-vps.sh <repo URL>
   ```
   For a private repo, add a deploy key or use an HTTPS token URL.
3. `nano /opt/swarm-detector/.env`: same keys as locally, strong DB passwords, `DOMAIN=:80` for a first test.
   The script already added `COMPOSE_FILE=...prod...`, so every `make` command on the VPS uses the prod setup.
4. `cd /opt/swarm-detector && make prod`, then open `http://<VPS IP>/docs`.
5. HTTPS: point your free domain's A record to the VPS IP, set `DOMAIN=yourdomain.com` in `.env`, run `make prod` again.
   Caddy gets the certificate by itself.
6. Later updates: `git push` locally, then `make deploy` on the VPS.

Data files are not in the image: copy them with `scp data/dev/*.jsonl root@<VPS IP>:/opt/swarm-detector/data/dev/`
and run `make load FILE=...` on the VPS.

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

## Hackathon Tech Challenges

- **Modal**: The project uses Modal to offload the heavy clustering and evaluation script to serverless GPUs.
- **Oxylabs Web API**: Used in the ingestion pipeline to scrape and verify URLs found in social media posts to improve detection accuracy.
