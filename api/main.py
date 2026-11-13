"""FastAPI app. Endpoints return fixture data until detect/ is wired in (see TODOs)."""
import json
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Swarm Detector")
FIXTURES = Path(__file__).parent / "fixtures"


class ScoreRequest(BaseModel):
    text: str


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/score")
def score(req: ScoreRequest) -> dict:
    # TODO(Person 3): embed req.text, find nearest messages with the MariaDB vector index,
    # return "unknown" below MATCH_THRESHOLD, otherwise detect.scoring.explain() for the matched cluster.
    return json.loads((FIXTURES / "score_example.json").read_text())


@app.get("/clusters")
def clusters() -> list[dict]:
    # TODO(Person 3): SELECT from clusters ORDER BY auto_score DESC
    return []


@app.get("/clusters/{cluster_id}")
def cluster(cluster_id: int) -> dict:
    # TODO(Person 3): features, contributions, narrative, techniques, sample messages, timeline
    return {"id": cluster_id}


@app.get("/review/queue")
def review_queue() -> list[dict]:
    # TODO(Person 3): clusters WHERE human_label IS NULL ORDER BY auto_score DESC
    return []


class Label(BaseModel):
    label: str  # 'confirmed' | 'rejected' | 'benign'
    by: str
    note: str | None = None


@app.post("/clusters/{cluster_id}/label")
def label_cluster(cluster_id: int, body: Label) -> dict:
    # TODO(Person 3): check REVIEWER_PASSWORD, UPDATE clusters SET human_label, labeled_by, labeled_at, label_note
    return {"id": cluster_id, "label": body.label}


@app.get("/metrics")
def metrics() -> dict:
    # TODO(Person 3): latest row from eval_runs
    return {"precision": None, "false_positive_rate": None, "n_labels": 0}
