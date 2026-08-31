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
  each one to Gemini (API key, via LangChain), which transcribes
  and runs KPI/sentiment analysis in a single call, then stores results in a
  local Postgres. Per-call work is a LangGraph state machine that gates out
  unusable audio before it costs anything. Triggered manually (button or
  `POST /api/pipeline/run`); see [`backend/README.md`](backend/README.md) for
  setup and the full list of cost optimizations.

## Running it

On a new Windows machine:

1. `setup.bat` — one-time: installs both sides' dependencies, creates
   `backend\.env` from the template (edit it — at minimum `GEMINI_API_KEY`
   and `DB_PASSWORD`), applies database migrations.
2. `verify-setup.bat` — confirms Postgres, GCS and Gemini are all reachable
   before you spend anything on a real run.
3. Start the app — two ways, same dashboard:
   - `start-prod.bat` — **recommended.** Builds the dashboard and serves it
     from the FastAPI backend itself: one process, one port
     (`http://localhost:8000`), no separate dev server.
   - `start.bat` — dev mode: backend on :8000, Vite dev server on :5173 with
     hot-reload. Use this only while actively editing frontend code; run
     `build-frontend.bat` afterward so `start-prod.bat` picks up the change.
4. `stop.bat` — stops whatever this project left listening on its ports.
5. `run-analysis.bat` — trigger an analysis run from the command line
   instead of the dashboard's button (same endpoint either way).
