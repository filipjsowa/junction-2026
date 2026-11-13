"""The explainable score. The ONLY place the 0-1 number comes from.

score = sigmoid(BIAS + sum(WEIGHTS[f] * x_f)),  contribution_f = WEIGHTS[f] * x_f
All feature values are normalised to 0-1 before scoring (null_model_z is clipped z / 5).
Weights are hand-set until ~50 reviewer labels exist; then refit them (logistic regression) and paste them here.
"""
import math

# Hand-set starting weights. TODO(Person 2): refit on reviewer labels.
BIAS = -4.0
WEIGHTS = {
    "match_similarity": 1.0,
    "near_dup_share": 2.0,
    "account_spread": 1.5,
    "burstiness": 1.5,
    "known_actor_share": 1.0,
    "null_model_z": 2.0,
}

# One sentence per feature, filled from the raw (un-normalised) values in `details`.
REASON_TEMPLATES = {
    "match_similarity": "{pct:.0f}% similar to {size} messages in cluster {cluster_id}",
    "near_dup_share": "{pct:.0f}% of those messages are near-copies",
    "account_spread": "Posted by {n_channels} different channels",
    "burstiness": "{pct:.0f}% appeared within {window_min} minutes of the first one",
    "known_actor_share": "{n_known} of {n_channels} channels are on the known-actor list",
    "null_model_z": "Coordination is {z:.1f} standard deviations above chance",
}


def explain(features: dict[str, float], details: dict) -> dict:
    """Return the score plus each feature's contribution and reason sentence, largest contribution first."""
    reasons = []
    for name, weight in WEIGHTS.items():
        value = features[name]
        reasons.append(
            {
                "feature": name,
                "value": round(value, 3),
                "contribution": round(weight * value, 3),
                "text": REASON_TEMPLATES[name].format(**details.get(name, {})),
            }
        )
    logit = BIAS + sum(r["contribution"] for r in reasons)
    reasons.sort(key=lambda r: r["contribution"], reverse=True)
    return {"score": round(1 / (1 + math.exp(-logit)), 3), "reasons": reasons}
