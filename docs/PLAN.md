# Swarm Detector – Hackathon Team Plan

> Exported on 2026-11-14 from the team doc (https://claude.ai/artifact/1H12o9ApDBXEY6gYfhtYGJ), which stays the live
> version: re-export it (doc menu → Export → Markdown) to refresh this file. The architecture diagram does not export;
> see the ASCII version in `CLAUDE.md`. The schema in the doc's "Shared contract" is an older draft, so this file
> points to `db/schema.sql` instead, which is the real contract.

Nov 13, 2026 · @Filip

## Architecture

Three lanes, one per person, meeting in one MariaDB database. Messages are collected and embedded, then clustered and scored, then served with their reasons.

_(Architecture diagram: see the team doc, or the ASCII version in `CLAUDE.md`.)_

`POST /score` embeds the incoming message with the same API, finds its nearest messages with MariaDB's vector index, and returns that cluster's score and reasons. Reviewer labels go back into the database and refit the score weights.

**Fixes applied to the first sketch:**

- **Similar text is a topic, not a swarm.** A cluster only scores high with coordination evidence: many distinct channels, a tight time burst, near-copies, known actors, and a result well above chance.
- **The database doesn't cluster by itself.** A clustering job runs every few minutes and writes cluster ids back.
- **MariaDB 11.8 with its native VECTOR type** keeps vectors and metadata in one place instead of a separate vector DB.
- **No sender location.** Social media platforms often don't expose it and collecting it raises GDPR issues. The site shows channel, language, first-seen time and forwarding source instead.
- **No match means `unknown`, not 0.** A score is only given when a message matches a known cluster.
- **Embeddings come from the external API,** so the VPS only runs MariaDB, the jobs and the web app.

## Explainable scoring

The score is computed from a few named, measurable features, so the explanation *is* the calculation. The LLM only describes the cluster in words; it never sets the number. This answers the judge's request directly: every point of the score traces back to a feature, and every feature traces back to real messages.

**How a score is produced**

1. Embed the incoming message with the same embedding API used for ingestion.
2. Find the nearest messages and clusters in the DB (top-k by cosine similarity).
3. If nothing is closer than the match threshold, return `verdict: "unknown"` and no score. No match is not the same as clean.
4. Otherwise take the matched cluster's features, compute the score, and return each feature's contribution next to it.

Score model: a logistic regression over the features below. Hand-set weights until there are about 50 reviewer labels, then fit the weights on those labels. Each feature's contribution is its weight times its value, so the breakdown adds up.

```latex
\text{score} = \sigma\Big(w_0 + \sum_i w_i x_i\Big), \qquad \text{contribution}_i = w_i x_i
```

| Feature | What it measures | Reason shown to the user |
| --- | --- | --- |
| `match_similarity` | Cosine similarity to the matched cluster | "93% similar to 41 messages in cluster 12" |
| `near_dup_share` | Share of the cluster that is near-identical text (cosine above 0.95) | "68% of those messages are near-copies" |
| `account_spread` | Distinct channels or accounts posting it | "Posted by 27 different channels" |
| `burstiness` | Share posted within a short window of first appearance | "80% appeared within 90 minutes" |
| `known_actor_share` | Share from channels on the seed list of known bad actors | "9 of 27 channels are on the known-actor list" |
| `null_model_z` | How far the coordination is above chance when timestamps are shuffled | "Coordination is 4.1 standard deviations above chance" |

The example numbers are illustrative, not results.

**Shown alongside the score, but not inside it:**

- **Narrative:** the LLM's one-line "order" behind the cluster, for example "Blame Ukraine, citing the vest patch and the flag photo".
- **Techniques:** loaded language, fear appeal, whataboutism, fabricated authority, each with the quoted words that triggered it. Kept out of the score because judging content alone is where most false positives come from.
- **Reviewer status:** confirmed, rejected or not yet reviewed, with who and when.
- **Evidence:** the closest messages with channel, timestamp and similarity, each clickable.
- **Model quality:** precision and false-positive rate at the current threshold, and which evaluation set they come from.

**Verdicts:** `matches_flagged_campaign`, `coordinated_unreviewed`, `matches_benign_cluster` (for example newsrooms syndicating one wire story), `unknown`.

Example `POST /score` response (illustrative values):

```json
{
  "verdict": "matches_flagged_campaign",
  "score": 0.87,
  "matched_cluster": {
    "id": 12,
    "narrative": "Gunman was a Ukrainian soldier (vest patch)",
    "similarity": 0.93,
    "review": {"status": "confirmed", "by": "reviewer-1", "at": "2026-11-14T10:20Z"}
  },
  "reasons": [
    {"feature": "near_dup_share", "value": 0.68, "contribution": 0.21, "text": "68% of the 41 messages are near-copies"},
    {"feature": "burstiness", "value": 0.80, "contribution": 0.18, "text": "80% appeared within 90 minutes"}
  ],
  "techniques": [{"name": "fabricated authority", "quote": "..."}],
  "evidence": [{"message_id": 4812, "channel": "...", "ts": "2026-11-07T16:42Z", "similarity": 0.95}],
  "model_quality": {"precision": null, "false_positive_rate": null, "eval_set": "reviewer labels + control channels"}
}
```

## Dev dataset and existing tools

Development starts from a prepared file, not a live collector, so all three people can start in hour 1 and precision can be measured from day 1.

**Dev dataset:** one JSONL file, one message per line, with the same fields as `messages` (without `embedding` and `cluster_id`). Synthetic rows also carry `"synthetic": true` and a `label`, and never count in the reported numbers.

| Part | Content | Why |
| --- | --- | --- |
| Planted swarms (synthetic) | About 5 narratives, each 30–80 LLM-reworded messages from 15–40 fake channels in tight bursts, plus normal messages spread over days | Known answers, so precision and false-positive rate work from day 1 |
| Benign trap (synthetic) | 10 news channels posting the same news-agency story | Real coordination that is not propaganda: the false-positive test |
| [IRA troll tweets](https://fivethirtyeight.com/features/why-were-sharing-3-million-russian-troll-tweets) (real) | About 50k sampled from FiveThirtyEight's ~3M Russian troll tweets, 2012–2018 | Real coordinated text to cluster; contains no normal accounts |
| Real-world export (real) | Export from the seed channels, pulled once | Demo data and the final evaluation |

**Existing tools to reuse:**

| Tool | Replaces | Owner | Note |
| --- | --- | --- | --- |
| [telegram-tracker](https://github.com/estebanpdl/telegram-tracker) | Writing a Telethon collector | Person 1 | Paid Apify Telegram scrapers are the fallback if the API ID is a problem |
| [BERTopic](https://github.com/MaartenGr/BERTopic) | Clustering job and narrative naming | Person 2 | Pass the precomputed embeddings; LLM topic labels through the AI Router (OpenAI-compatible). Cluster ids change on refit |
| [datasketch](https://github.com/ekzhu/datasketch) (MinHash LSH) | Near-duplicate code | Person 2 | Optional: cosine distance under 0.05 in MariaDB is enough for small data |
| [QUT coordination-network-toolkit](https://github.com/QUT-Digital-Observatory/coordination-network-toolkit) | Coordination-graph code | Person 2 | CSV in, channels treated as users, 60 s window; a published method to cite |
| Argilla or Label Studio | Reviewer console | Person 3 | Only if short on time; a simple confirm/reject page may be quicker |
| Sigma.js or Cytoscape.js | Graph rendering | Person 3 | |
| lingua | Language detection | Person 1 | |

## Person 1 – Data pipeline and infrastructure

Owns getting real messages into the DB with embeddings and metadata, and owns the VPS. With embeddings on an external API this role is lighter, so it also takes the second data source and the known-actor list.

- [ ] Register a Telegram API ID (my.telegram.org, needs a phone number) and test Telethon on 3 public channels. **Do this first.**
- [ ] Seed channel list in a config file: suspect channels named in the information operation reports, local channels that repost them, and a **control set** of normal news channels (`is_control = true`).
- [ ] Build dev dataset v1 (planted swarms, benign trap, IRA sample) in the first 2 hours. Then export once with scrapers/trackers into the same format. A live collector comes later, if at all.
- [ ] Normalise each message: text, language, timestamp, channel, forwarded-from, URLs.
- [ ] Embedding client for the embeddings API: batch requests, retry on errors, cache by text hash so identical texts are embedded once. Note the model name and vector dimension in the schema.
- [ ] MariaDB 11.8 (mariadb:11.8 image) + docker-compose on the VPS, with a cosine VECTOR INDEX on the embedding column.
- [ ] Known-actor list with a source for each entry (Detector Media/StopFake reports, EU vs Disinfo), used by Person 2 as a feature.
- [ ] If time allows: Bluesky Jetstream as a second source, same normalised format.

**Hands over:** a filled `messages` table and a `seed_channels` table, about 4 hours in.

## Person 2 – Detection, classification and evaluation

Owns the part the judges score: turning clusters of similar text into an explainable, measured verdict. Similar text alone is only a topic; the coordination features are what make it a swarm.

- [ ] **Clustering job** (runs every 5–10 min): BERTopic (HDBSCAN inside) over embeddings from the last N days, writes `cluster_id` back to `messages`. Keep cluster ids stable between runs by matching new clusters to old centroids.
- [ ] **Near-duplicate check:** pairs with cosine above 0.95 inside a cluster, giving `near_dup_share`.
- [ ] **Coordination features per cluster:** `account_spread`, `burstiness`, `known_actor_share`, and `null_model_z` (shuffle timestamps 100 times, compare how often the same burst appears by chance).
- [ ] **Score model:** the logistic regression from the Explainable scoring section, with a function that returns score, contributions and reason sentences. Person 3's API calls this function directly.
- [ ] **LLM description** via AI Router, once per cluster (cached, rerun only when the cluster grows a lot): the narrative "order" in one line, techniques with quoted spans, and a flag if it looks like normal news syndication. Prompt must cite message ids as evidence.
- [ ] **Automated classifier** = score model + LLM flags → `auto_score` and a suggested verdict. The human reviewer confirms or rejects, and those labels refit the weights.
- [ ] **Evaluation script:** precision and false-positive rate at the chosen threshold, measured on (a) reviewer labels, (b) control channels, which should almost never be flagged, and (c) if time allows, a labelled information-operations dataset ([arXiv 2411.10609](https://arxiv.org/html/2411.10609v2)). Writes results to an `eval_runs` table for the metrics page.

**Hands over:** filled `clusters` table and a `score_message(text)` function, about 10 hours in; evaluation numbers on day 2.

## Person 3 – API, website and reviewer console

Owns everything a judge touches. Builds against fake JSON from hour 1, so no waiting on Persons 1 and 2.

- [ ] **FastAPI endpoints:**
  - `POST /score` → the response in the Explainable scoring section
  - `GET /clusters` (sorted by score) and `GET /clusters/{id}` (features, narrative, techniques, sample messages, timeline)
  - `GET /review/queue` and `POST /clusters/{id}/label` for the reviewer
  - `GET /metrics` → latest evaluation run
- [ ] **Check page:** paste a message, see the verdict and score, the **reasons list with each contribution as a bar**, the narrative, highlighted technique quotes, and the evidence messages. The reasons must be visible without scrolling: this is what the judge asked for.
- [ ] **Cluster view:** graph of channels and messages (Cytoscape.js or sigma.js), coloured by known-actor or control, plus a timeline of when the messages appeared.
- [ ] **Reviewer console** (the "Control" box): queue of unreviewed clusters, with confirm / reject / benign buttons and a note field. Simple shared password is enough for the demo.
- [ ] **Metrics page:** precision, false-positive rate, number of labels, date of the last evaluation. Link to it from the front page.
- [ ] Domain + HTTPS on the VPS (Caddy is the quickest), and a public URL for the judges.

**Hands over:** a live URL with fake data by about 6 hours in, switched to real data once Person 2's tables exist.

## Shared contract

Agree on this schema in the first hour; then nobody blocks anybody. It needs MariaDB 11.8 or newer (`mariadb:11.8` Docker image) for the native `VECTOR` type ([docs](https://mariadb.com/docs/server/reference/sql-structure/vectors/vector-overview)). Use the same embedding model for ingestion and for `/score`.

**Schema:** see [`db/schema.sql`](../db/schema.sql), the real contract. (The doc holds an earlier draft without the
`synthetic`/`label` columns and with `VECTOR(D)` placeholders.)

Nearest neighbours for `/score` (cosine distance = 1 − similarity):

```sql
SELECT id, cluster_id, VEC_DISTANCE_COSINE(embedding, VEC_FromText(?)) AS dist
FROM messages
ORDER BY VEC_DISTANCE_COSINE(embedding, VEC_FromText(?))
LIMIT 20;
```

MariaDB rules that affect the code:

- The indexed `embedding` column must be NOT NULL, so embed a message before inserting it.
- One vector index per table, which is fine here: only `messages` needs one.
- The index is only used with a bare `ORDER BY VEC_DISTANCE_COSINE(col, vec) LIMIT k`. To filter by a similarity threshold, wrap that query in a subquery and filter outside it.
- Vectors are sent as text with `VEC_FromText('[0.1, 0.2, ...]')`. When reading them for clustering, select `VEC_ToText(embedding)` or decode the raw bytes as float32.

## Stretch ideas

Start these only once the core loop works (real message → explained verdict). Listed strongest first; effort is a rough guess.

| Idea | What it adds | Owner | Effort |
| --- | --- | --- | --- |
| Telegram forward chains | Rebuild the spread tree from `forwarded_from` and name the first channel that posted the narrative | Person 2 (data), Person 3 (tree view) | 2–3 h |
| Same narrative across languages | Link the Polish, Russian, English and Ukrainian versions of one narrative: "one story in 4 languages within 2 hours" | Person 2 | 1–2 h |
| Feature ablation table | Precision with each feature removed, proving every reason in the score matters | Person 2 | 1 h |
| Paraphrase stress test | LLM rewords flagged messages and runs them through `/score`, showing detection survives rewording | Person 2 | 1 h |
| Telegram bot | Forward any message to the bot and get the verdict and reasons back; reuses `/score` | Person 1 | 1 h |
| "Report false positive" button | On the check page; feeds the reviewer queue, so false-positive handling is visible in the product | Person 3 | 30 min |

## Milestones and demo

The goal for day 1 is an ugly but complete loop from real message to explained verdict; day 2 is about measured quality. Hours are counted from when you start.

1. **H+1:** schema agreed, repo and docker-compose skeleton on the VPS, dev dataset v1 shared.
2. **H+4:** dev dataset loaded with embeddings; Real-world export follows (Person 1).
3. **H+6:** public URL live with fake data (Person 3).
4. **H+10:** first clusters and scores; a real message goes through `/score` to the page (Person 2 + 3).
5. **End of day 1:** everyone spends 20 minutes in the reviewer console labelling 30–50 clusters, giving the first precision and false-positive numbers.
6. **Day 2 morning:** refit weights on the labels, null model, false-positive rate on control channels, better reason sentences.
7. **3 hours before the deadline:** feature freeze, rehearse the demo twice.

**Demo script (about 3 minutes):**

- [ ] Open with the selected information operation, detailing the timeline and the fake narratives on social media within hours.
- [ ] Paste a real message from that narrative: verdict, score, and the reasons with their contributions.
- [ ] Paste a normal news message about the attack: `unknown` or `matches_benign_cluster`. This shows false-positive handling.
- [ ] Open the cluster graph and timeline for the flagged narrative.
- [ ] Show the metrics page: precision, false-positive rate, number of labels.
- [ ] One honest limitations line: coordination is not proof of inauthenticity, the known-actor list carries its sources' bias, the label set is small, and the data is across specific platforms.

## Stretch goals (after H+10)

Six extras, in the order to try them, once a real message goes through `/score` to the page. All stop at the feature freeze. None changes the score unless it becomes a named feature in `detect/scoring.py`.

| # | Idea | Owner | Effort (est.) | What to build | Demo moment | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | "Report false positive" button | Person 3 | 1 h | Button on the check page → `POST /score/report` with the matched cluster id and an optional note. The cluster moves to the top of the reviewer queue. Needs a small `fp_reports` table: schema change, tell the team. | False-positive handling is visible in the product, not only on the metrics page. | Not started |
| 2 | Telegram forward chains | Person 1 + 3 | 2 h | Keep `forwarded_from` in the Telegram export (the column is already in `messages`). Per cluster, build the tree from forward edges and timestamps, name the earliest channel, draw it on the cluster graph. | "Channel X posted it first; 14 channels forwarded it within 40 minutes." | Not started |
| 3 | Telegram bot | Person 3 | 1 h | Separate compose service. A user forwards a message; the bot calls `/score` and replies with verdict, score and top 3 reasons. Token in `TELEGRAM_BOT_TOKEN` (add to `.env.example`). | Forward a message live from a phone. | Not started |
| 4 | Same narrative across languages | Person 2 | 1–2 h | First check the embedding model is multilingual: a Polish/Russian translation pair should score above `MATCH_THRESHOLD`. Then per cluster: languages from `messages.lang` and time from first to last language. Shown as evidence; scored only if added to `scoring.py` as `lang_spread` and refit. | "One story pushed in 4 languages within 2 hours." | Not started |
| 5 | Feature ablation table | Person 2 | 1 h | In the eval script, zero out (or refit without) each feature and record precision and false-positive rate. Store rows in `eval_runs` with `eval_set = 'ablation:-burstiness'` etc., so no schema change. Show on the metrics page. Needs the day-1 labels. | Every reason in the score is shown to matter. | Not started |
| 6 | Paraphrase stress test | Person 2 | 1–2 h | AI Router rewords ~30 flagged messages; each goes through `/score` without being inserted. Report the share still matched to the same cluster and the median score change. Reported separately; never counts in precision or false-positive rate. | Detection survives rewording, not just copy-paste. | Not started |
