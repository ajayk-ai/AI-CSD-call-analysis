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

## Running it on a new Windows machine

### 0. Prerequisites — install these first

| Tool | Why | Install |
| --- | --- | --- |
| **uv** | Manages the backend's Python version (`3.13`) and virtualenv — no separate Python install needed | `powershell -c "irm https://astral.sh/uv/install.ps1 \| iex"`, then close/reopen the terminal |
| **Node.js LTS** | Builds/runs the frontend | https://nodejs.org/ |
| **PostgreSQL** | Local database for call results + pipeline checkpoints | Install locally, note the `postgres` user's password, and create the database: `createdb csd_call_analysis` (or `CREATE DATABASE csd_call_analysis;` in `psql`) |
| **Google Cloud credentials** | Read-only access to the `csdcallaudio` GCS bucket | Either run `gcloud auth application-default login` (needs the [gcloud CLI](https://cloud.google.com/sdk/docs/install)), or get a service-account JSON key with the `Storage Object Viewer` role from whoever administers the GCP project |
| **Gemini API key** | Powers the transcription + KPI extraction pipeline | Create one at [Google AI Studio](https://aistudio.google.com/apikey) — this is the plain Developer API key, not GCP/Vertex auth |

You don't need a separate Python install — `uv` fetches the pinned version
automatically on first `uv sync`.

### 1. Get the code

Clone or copy this repo onto the machine, then open a terminal in its root
folder for every step below.

### 2. One-time setup

Run `setup.bat`. It's idempotent (safe to re-run) and does all of this:

1. Checks `uv` and `npm` are on `PATH`.
2. `uv sync` in `backend/` — installs Python deps into `backend\.venv`.
3. Creates `backend\.env` from `backend\.env.example` if it doesn't already
   exist, and opens it in Notepad. **Fill in at minimum:**
   - `GEMINI_API_KEY` (from the prerequisites step above)
   - `DB_PASSWORD` (your local Postgres password)
   - `GOOGLE_APPLICATION_CREDENTIALS` — only if you're using a
     service-account key instead of `gcloud auth application-default login`
   Save and close Notepad to let the script continue.
4. `uv run alembic upgrade head` — applies database migrations. Fails here if
   Postgres isn't running yet, or `DB_USER`/`DB_PASSWORD` are wrong — fix
   `backend\.env` and re-run `setup.bat`.
5. `npm install` in `frontend/`.

### 3. Verify before spending anything

`verify-setup.bat` — confirms Postgres, GCS and Gemini are all reachable with
the credentials you just entered, before triggering a real (paid) analysis
run.

### 4. Start the app

Two ways, same dashboard:

- `start-prod.bat` — **recommended.** Builds the dashboard and serves it from
  the FastAPI backend itself: one process, one port
  (`http://localhost:8000`), no separate dev server.
- `start.bat` — dev mode: backend on :8000, Vite dev server on :5173 with
  hot-reload. Use this only while actively editing frontend code; run
  `build-frontend.bat` afterward so `start-prod.bat` picks up the change.

`stop.bat` stops whatever this project left listening on its ports.

### 5. Run an analysis

Either click "Run Analysis" on the dashboard, or from the command line:
`run-analysis.bat` (same endpoint either way — see
[`backend/README.md`](backend/README.md#cost-optimizations) for what each
run costs and how to control it).

### If something goes wrong

- `setup.bat` / `verify-setup.bat` print which check failed and why —
  they're meant to be re-run after fixing the problem.
- For anything backend-specific (env vars, cost controls, project layout),
  see [`backend/README.md`](backend/README.md).
- For frontend-specific setup, see [`frontend/README.md`](frontend/README.md).
