# AI CSD Call Analysis

Analysis tooling and reporting for customer service call transcripts, built
around the "Customer Trust Improvement Mission" service feedback report.

## Structure

- [`frontend/`](frontend/) — React + TypeScript + Vite dashboard that visualizes
  call quality, sentiment, satisfaction, issue trends, and KPI targets. Currently
  runs on synthetic/mock data (see [`frontend/src/data/mockData.ts`](frontend/src/data/mockData.ts)),
  with a "Run Analysis" button wired to the backend below;
  see [`frontend/README.md`](frontend/README.md) for setup and structure.
- [`backend/`](backend/) — Python/FastAPI service that downloads call
  recordings from a GCS bucket (the only piece that touches GCP) and sends
  each one to Gemini Flash-Lite (API key), which transcribes and runs
  KPI/sentiment analysis in a single call, then stores results in a local
  Postgres. Triggered manually (button or `POST /api/pipeline/run`); see
  [`backend/README.md`](backend/README.md) for setup.
