# ZGrader
Grading Prototype from Scanned Images

Runs the **Card Care Center** portal: clients submit a card, the pipeline
analyses scans for centering, corners, edges and surface faults, and an
operator publishes a PDF pre-grading report.

- `docs/deployment.md` — running it on your own hardware, and the security
  controls that depend on the deployment being set up correctly. **Read this
  before redeploying:** the backend now refuses to start on default secrets.
- `docs/qa_checklist.md` — manual end-to-end test walkthrough.
- `.env.example` — every environment variable, with notes on which ones are
  required.
