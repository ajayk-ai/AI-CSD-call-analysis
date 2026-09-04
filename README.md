# AI CSD Call Analysis

Turns call-center recordings into a KPI dashboard: call quality, sentiment,
satisfaction, connection health, agent script compliance, and ranked issue
categories, all derived from Gemini reading the actual audio — not a fixed
rubric.

**Technical documentation lives in [`docs/`](docs/):**

- [`docs/architecture.md`](docs/architecture.md) — system overview, request flow, directory map
- [`docs/pipeline.md`](docs/pipeline.md) — the analysis pipeline: the KPI-node graph, checkpointing, adding a KPI
- [`docs/data-model.md`](docs/data-model.md) — schema, the conversation-status gate, the category taxonomy
- [`docs/dashboard.md`](docs/dashboard.md) — the dashboard's cross-filter design and click-to-review navigation
- [`docs/api-reference.md`](docs/api-reference.md) — every endpoint

## Structure

- [`frontend/`](frontend/) — React + TypeScript + Vite dashboard. Reads live
  data from the backend below via `GET /api/dashboard/summary` and related
  endpoints; see [`frontend/README.md`](frontend/README.md) for setup and
  structure.
- [`backend/`](backend/) — Python/FastAPI service that downloads call
  recordings from a GCS bucket (the only piece that touches GCP), runs each
  one through a LangGraph pipeline — one audio-transcription pass, several
  independent cheap text-based KPI extractions — and stores results in a
  local Postgres. Durably checkpointed per call, so re-analyzing after a KPI
  change costs cents, not a full re-transcription. Triggered manually (button
  or `POST /api/pipeline/run`), or on an optional daily schedule; see
  [`backend/README.md`](backend/README.md) for setup and cost optimizations.

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
