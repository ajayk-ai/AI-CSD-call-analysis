# CSD Call Analysis Backend

Ingests call recordings from the `csdcallaudio` GCS bucket and sends each one
straight to Gemini (Flash-Lite, Developer API) — one call does transcription
*and* KPI/sentiment analysis together, and results land in Postgres. GCS is
the only thing this touches in GCP; the API, Postgres, and the frontend all
run locally. Triggered manually — from the dashboard's "Run Analysis" button,
or `curl` — rather than a live GCS event subscription.

## How it fits together

```
GCS bucket (csdcallaudio/recordings/<date>/<team>/*.mp3)
        │  gcs_service.list_audio_blobs() / download_blob_bytes()
        ▼
ingest_pipeline.run_pipeline()
        │  1. upsert a `calls` row per new object
        │  2. download that object's bytes from GCS
        │  3. call_analysis_service (Gemini Flash-Lite, audio sent inline,
        │     returns transcript + KPI classification in one shot)
        │  4. persist Transcript + CallAnalysis + IssueMention rows
        ▼
Postgres (calls / transcripts / call_analysis / issue_mentions)
        ▲
        │  GET /api/dashboard/summary?range=1d|7d|1m|3m|all
        │  (same range keys the frontend's TimeRangeFilter already uses)
React dashboard (frontend/)
```

One Gemini call per recording instead of a separate Speech-to-Text pass —
cheaper and faster, and Flash-Lite is the lowest-cost generally-available
tier.

## Project structure

```
app/
  config.py            Settings (env-driven, see .env.example)
  db/
    models.py           SQLAlchemy models: Call, Transcript, CallAnalysis, IssueMention
    session.py           engine / session / get_db dependency
  services/
    gcs_service.py         lists + downloads audio objects from the bucket
    call_analysis_service.py   Gemini wrapper — audio bytes in, transcript + structured JSON out
  schemas/
    analysis.py           Gemini's structured-output contract + the KPI category taxonomy
    calls.py / dashboard.py    API response models
  pipeline/
    ingest_pipeline.py     orchestrates the steps above per call, per-call error isolation
  api/
    routes_pipeline.py     POST /api/pipeline/run  (the "Run Analysis" button target)
    routes_calls.py         GET /api/calls, GET /api/calls/{id}
    routes_dashboard.py      GET /api/dashboard/summary
  main.py                 FastAPI app + CORS
migrations/               Alembic (hand-written initial revision in versions/)
```

## Setup

1. **Python**: this project pins `>=3.13,<3.14` (a few of the Google client
   libraries don't have wheels for 3.14 yet). `uv` will fetch 3.13
   automatically if you don't have it.

   ```bash
   cd backend
   uv sync
   ```

2. **Google Cloud credentials** — needed only to read from GCS (Gemini itself
   uses a plain API key, not GCP auth). Either:
   - Run `gcloud auth application-default login` on this machine (simplest
     for local dev — this is what your currently-installed `gcloud` needs
     anyway, since its token had expired when this was built), or
   - Point `GOOGLE_APPLICATION_CREDENTIALS` at a service-account JSON key
     with the `Storage Object Viewer` role.

3. **Gemini API key.** Get one from Google AI Studio and set `GEMINI_API_KEY`.
   `GEMINI_MODEL` defaults to `gemini-2.5-flash-lite` (cheapest/fastest tier —
   bump only if accuracy on noisy call-center audio isn't good enough).

4. **Postgres.** Point `DATABASE_URL` at your local instance (a port scan
   found something already listening on `localhost:5432` on this machine —
   confirm the database/user/password and create the database if it
   doesn't exist yet: `createdb csd_call_analysis`).

5. Copy `.env.example` to `.env` and fill in the above.

6. Run migrations:

   ```bash
   uv run alembic upgrade head
   ```

7. Start the API:

   ```bash
   uv run uvicorn app.main:app --reload --port 8000
   ```

   The frontend dev server (`frontend/`, `http://localhost:5173`) is already
   allow-listed in CORS.

## Triggering an analysis run

```bash
curl -X POST http://localhost:8000/api/pipeline/run
```

Returns a summary (`found_in_bucket`, `newly_processed`, `already_processed`,
`failed`, `errors`). Safe to call repeatedly — already-`ANALYZED` calls are
skipped, and a call that failed partway through gets retried on the next run.

This is exactly what the frontend's "Run Analysis" button calls.

## Notes / things to double-check before a real run

- **KPI categories**: `schemas/analysis.py` hardcodes the same category
  labels already used in `frontend/src/data/mockData.ts` (negative drivers,
  service/machine issues, positive themes) so real aggregated data lines up
  with the dashboard's existing ranked tables without relabeling.
- **Cost**: each new call costs exactly one Gemini Flash-Lite call. Nothing
  runs automatically in the background — it only processes when you hit
  "Run Analysis" (or `POST /api/pipeline/run`).
- The frontend still renders the synthetic `mockData.ts` dataset — wiring it
  to `GET /api/dashboard/summary` is a follow-up, not done here.
