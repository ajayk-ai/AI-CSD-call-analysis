# CSD Call Analysis Backend

Ingests call recordings from the `csdcallaudio` GCS bucket and sends each one
straight to Gemini (Flash-Lite, Developer API) — one call does transcription
*and* KPI/sentiment analysis together, and results land in Postgres. GCS is
the only thing this touches in GCP; the API, Postgres, and the frontend all
run locally. Triggered manually — from the dashboard's "Run Analysis" button,
or `curl` — rather than a live GCS event subscription.

## How it fits together

`run_pipeline` is the batch driver (DB reads/writes, concurrency); the
per-call work is a small **LangGraph** state machine in `pipeline/graph.py`:

```
GCS bucket (csdcallaudio/recordings/<date>/<team>/*.mp3)
        │  gcs_service.list_audio_blobs()
        ▼
ingest_pipeline.run_pipeline()          [batch driver — owns the DB Session]
        │  upsert a `calls` row per object, skip ones already ANALYZED
        │  then, per concurrent chunk, reload the category taxonomy and run:
        │
        │   ┌─ LangGraph: pipeline/graph.py ───────────────────────────┐
        │   │  prescreen ──(too small)──▶ END        [zero cost]       │
        │   │      │                                                   │
        │   │      └──(real audio)──▶ fetch_audio ──▶ analyze ──▶ END  │
        │   └───────────────────────────────────────────────────────────┘
        │
        │  finally, serially on the main thread:
        │    category_service persists any category Gemini invented
        │    persist Transcript + CallAnalysis + IssueMention rows
        ▼
Postgres (calls / transcripts / call_analysis / issue_mentions / mention_categories)
        ▲
        │  GET /api/dashboard/summary?range=1d|7d|1m|3m|all
        │  (same range keys the frontend's TimeRangeFilter already uses)
React dashboard (frontend/)
```

### Why the graph is shaped this way

- **Graph nodes never touch the database.** The Session is configured with
  `expire_on_commit=True`, so reading an ORM attribute after a commit
  triggers a lazy refresh — doing that from several worker threads against
  one shared Session is a data race. The driver snapshots the primitives it
  needs into a `_CallJob` before dispatching, and does all persistence back
  on the main thread.
- **No LangGraph checkpointer.** The `calls` table already *is* the durable
  resume point (anything short of `ANALYZED` is retried next run), so a
  checkpointer would be a second, competing source of truth — and it would
  have to serialize megabytes of audio per call to provide it.

## Cost optimizations

Roughly in order of how much they save:

1. **Prescreen gate (`min_audio_bytes`, default 2048).** Objects too small to
   contain speech are marked rejected/corrupted from the bucket listing
   metadata alone — never downloaded, never sent to the model. Your bucket
   has a number of 288-byte objects; each one of those now costs *nothing*
   instead of a full audio-input request. `tests/test_graph.py` asserts this
   (0 downloads, 0 model calls).
2. **One call per recording.** Transcription and classification happen in a
   single request, rather than a Speech-to-Text pass plus an analysis pass.
3. **Flash-Lite**, the cheapest generally-available tier.
4. **In-place retries** (`analysis_max_retries`). A transient 429/503 is
   retried by LangChain's `.with_retry()` rather than failing the call — a
   failure would mean re-downloading and re-sending the same expensive audio
   on the next run.
5. **Cache-friendly prompt ordering.** The shared instruction + category
   block is sent *before* the audio. Gemini's implicit caching only rewards a
   common *prefix*; with audio first (as this was originally written) every
   request had a unique prefix and could never hit cache. Costs nothing to
   order correctly and pays off as the category list grows.
6. **Already-analyzed calls are skipped**, so re-running is cheap.
7. **Bounded concurrency** (`analysis_concurrency`, default 4) — saves
   wall-clock time rather than money, and keeps memory/quota bounded.

## Project structure

```
app/
  config.py            Settings (env-driven, see .env.example)
  db/
    models.py           SQLAlchemy models: Call, Transcript, CallAnalysis, IssueMention, MentionCategory
    session.py           engine / session / get_db dependency
  services/
    gcs_service.py         lists + downloads audio objects from the bucket
    call_analysis_service.py   LangChain ChatGoogleGenerativeAI wrapper — audio + known
                               categories in, transcript + structured JSON out
    category_service.py      reads/grows the mention_categories taxonomy (see below)
  schemas/
    analysis.py           Gemini's structured-output contract
    calls.py / dashboard.py    API response models
  pipeline/
    graph.py               LangGraph state machine for ONE call (prescreen → fetch → analyze)
    ingest_pipeline.py     batch driver: DB, concurrency, persistence, error isolation
  api/
    routes_pipeline.py     POST /api/pipeline/run  (the "Run Analysis" button target)
    routes_calls.py         GET /api/calls, GET /api/calls/{id}
    routes_dashboard.py      GET /api/dashboard/summary
  main.py                 FastAPI app + CORS
migrations/               Alembic (hand-written initial revision in versions/)
tests/                    pytest — graph behaviour, no network or DB needed (`uv run pytest`)
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

Returns a summary (`found_in_bucket`, `newly_processed`,
`skipped_by_prescreen`, `already_processed`, `failed`, `errors`). Safe to call
repeatedly — already-`ANALYZED` calls are skipped, and a call that failed
partway through gets retried on the next run. `skipped_by_prescreen` is the
subset of `newly_processed` that never reached the model.

This is exactly what the frontend's "Run Analysis" button calls.

## Dynamic KPI categories

"Top Issue Analysis" and "Top Service / Machine Issues" (and positive themes,
tracked but not currently shown on the dashboard) are **not** a fixed list —
the taxonomy lives in the `mention_categories` table and grows as new kinds
of cases show up, instead of forcing every call into a stale set of buckets:

1. `category_service.get_known_categories(db)` reads the current names per
   mention type and feeds them into the Gemini prompt.
2. Gemini is instructed to **reuse** an existing category whenever it's a
   reasonable fit (this is what keeps the ranked tables meaningful over
   time instead of fragmenting into near-duplicate labels), and to invent a
   short, specific new one only for a genuinely new kind of case.
3. `category_service.register_new_categories(db, result)` persists any
   category that wasn't already known, so it's available as a reusable
   option starting with the *next* call.

The first migration (`0001_initial_schema.py`) seeds the table with the
categories that were previously hardcoded (matching
`frontend/src/data/mockData.ts`), marked `is_seed=True` so they're
distinguishable from ones the model has discovered since. There's no
approval/moderation step before a new category goes live — if you start
seeing near-duplicates in practice (e.g. "AC Not Cooling" next to the seeded
"AC / Cooling Problems"), that's the signal to add a review step or a
periodic merge pass; the prompt's "reuse first" instruction is doing the
consolidation work for now.

## Customer satisfaction banding

`satisfaction_rating` is still a raw 1–10 estimate from Gemini per call.
Where it gets bucketed for reporting (`routes_dashboard.py`
`_satisfaction_band`, and the frontend's `satisfaction` mock rows), the
cutoff is: **8–10 = Satisfied, 1–7 = Not Satisfied.**

## TLS / corporate proxy

`app/__init__.py` calls `truststore.inject_into_ssl()` before anything else in
the package runs.

Python normally trusts only the CA bundle shipped by `certifi`. On a network
that performs TLS inspection — a proxy re-signing traffic with its own root CA
— that bundle knows nothing about the proxy's certificate, so every outbound
HTTPS call (Gemini, Google Cloud Storage) fails with *"self-signed certificate
in certificate chain"* or *"unable to get local issuer certificate"*. The
proxy's root CA is already installed in the **OS** certificate store, since
that's how the browser trusts it. `truststore` points Python at that store.

This is not hypothetical here: before it was added, GCS listing failed and the
pipeline errored out. After, the same call returns 108 objects.

If the injection fails it logs a warning and falls back to `certifi`, which is
correct on a network without inspection.

## Error responses and CORS

Middleware order in `main.py` is load-bearing:

```
CORSMiddleware  ->  catch_unhandled_errors  ->  routes
```

`add_middleware` inserts at the front of the stack, so the **last** registered
is outermost — the error catcher is registered first, CORS second.

Do **not** replace the catcher with `@app.exception_handler(Exception)`.
Starlette routes the catch-all handler to `ServerErrorMiddleware`, which sits
*outside* `CORSMiddleware`; its 500 then carries no `Access-Control-Allow-Origin`,
the browser reports a misleading *"blocked by CORS policy"*, and the actual
error is hidden. That is exactly how the TLS failure above first presented.
`tests/test_error_cors.py` guards this.

## Notes / things to double-check before a real run

- **Cost**: each new call costs exactly one Gemini Flash-Lite call. Nothing
  runs automatically in the background — it only processes when you hit
  "Run Analysis" (or `POST /api/pipeline/run`).
- The frontend still renders the synthetic `mockData.ts` dataset — wiring it
  to `GET /api/dashboard/summary` is a follow-up, not done here.
