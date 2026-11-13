# Dev data

One JSONL file per source, one message per line. Loaded with `python -m ingest.load_jsonl <file>`.

| Field            | Required | Notes                                                                 |
| ---------------- | -------- | --------------------------------------------------------------------- |
| `platform`       | yes      | `telegram`, `bluesky`, `twitter`, `synthetic`                          |
| `channel_id`     | yes      | Channel or account id                                                  |
| `text`           | yes      |                                                                       |
| `ts`             | yes      | ISO 8601 with timezone, e.g. `2026-11-07T16:05:00Z`                    |
| `author_id`      | no       |                                                                       |
| `lang`           | no       | ISO 639-1                                                              |
| `url`            | no       |                                                                       |
| `forwarded_from` | no       | Channel the message was forwarded from                                 |
| `is_control`     | no       | `true` for control channels (normal news)                              |
| `synthetic`      | no       | `true` for generated data; never counts in reported metrics           |
| `label`          | no       | Ground truth for synthetic rows: `swarm:<narrative>`, `benign:<kind>`, `organic` |

Planned files (Person 1):

- `planted_swarms.jsonl`: ~5 narratives × 30–80 LLM-reworded messages from 15–40 fake channels in tight bursts, plus organic messages over several days.
- `benign_trap.jsonl`: ~10 news channels posting the same wire story (the false-positive test).
- `ira_sample.jsonl`: ~50k sample of FiveThirtyEight's Russian troll tweets (`github.com/fivethirtyeight/russian-troll-tweets`), converted to this format.
- `krakow_telegram.jsonl`: 7–10 Nov 2026 export from the seed channels (telegram-tracker).

`sample.jsonl` is a 6-line smoke test.
