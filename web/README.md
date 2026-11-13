# Web (Person 3)

Pages, served by FastAPI as static files or a small separate app:

- **Check page:** paste a message → verdict, score, reasons with each contribution as a bar (visible without scrolling), narrative, technique quotes, evidence messages.
- **Cluster view:** graph of channels and messages (Sigma.js or Cytoscape.js) coloured by known-actor / control, plus a timeline.
- **Reviewer console:** queue of unreviewed clusters, confirm / reject / benign + note, shared password.
- **Metrics page:** precision, false-positive rate, number of labels, last evaluation date. Linked from the front page.

Build against `api/fixtures/score_example.json` until the real endpoints are wired.
