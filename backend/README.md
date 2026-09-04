# CSD Call Analysis Backend

Ingests call recordings from the `csdcallaudio` GCS bucket, runs each one
through a KPI-shaped LangGraph pipeline (audio transcription once, several
independent text-based KPI extractions after), and stores the results in
Postgres. GCS is the only thing this touches in GCP; Gemini is called via a
plain API key (Developer API, not Vertex/GCP auth). Triggered manually — the
dashboard's "Run Analysis" button, `curl`, or an optional daily schedule set
from the Admin tab — never a live GCS event subscription.

**This file covers setup and day-to-day operation.** For how the system is
actually built, see the docs in [`../docs/`](../docs/):

- **[`../docs/architecture.md`](../docs/architecture.md)** — system overview, request flow, directory map
- **[`../docs/pipeline.md`](../docs/pipeline.md)** — the KPI-node graph, the checkpointer, adding a KPI, why re-analysis is cheap
- **[`../docs/data-model.md`](../docs/data-model.md)** — schema, the conversation-status gate, the category taxonomy
- **[`../docs/dashboard.md`](../docs/dashboard.md)** — the cross-filter design (frontend, but backend-driven)
- **[`../docs/api-reference.md`](../docs/api-reference.md)** — every endpoint

## Setup

1. **Python**: this project pins `>=3.13,<3.14`. `uv` fetches it
   automatically if you don't have it.

   ```bash
   cd backend
   uv sync
   ```

2. **Google Cloud credentials** — needed only to read from GCS (Gemini uses a
   plain API key, not GCP auth). Either:
   - `gcloud auth application-default login`, or
   - Point `GOOGLE_APPLICATION_CREDENTIALS` at a service-account JSON key
     with the `Storage Object Viewer` role.

3. **Gemini API key** from Google AI Studio → `GEMINI_API_KEY`. Two model
   settings, not one (see [`../docs/pipeline.md`](../docs/pipeline.md#two-model-tiers)):
   `GEMINI_TRANSCRIPTION_MODEL` (default `gemini-3.5-flash`, the only tier
   that reads audio) and `GEMINI_EXTRACTION_MODEL` (default
   `gemini-3.5-flash-lite`, every KPI node). A legacy `GEMINI_MODEL` env var
   still works if set — it overrides the extraction tier only.

4. **Postgres.** Point `DATABASE_URL` (or the discrete `DB_*` fields) at your
   local instance; create the database if it doesn't exist
   (`createdb csd_call_analysis`). The LangGraph checkpointer (see
   [`../docs/pipeline.md`](../docs/pipeline.md#the-checkpointer--why-re-analysis-is-cheap))
   uses this same database — no separate service to run.

5. Copy `.env.example` to `.env` and fill in the above.

6. Run migrations:

   ```bash
   uv run alembic upgrade head
   ```

7. Start the API:

   ```bash
   uv run uvicorn app.main:app --reload --port 8000
   ```

   The frontend dev server (`http://localhost:5173`) is already allow-listed
   in CORS. Note `frontend/vite.config.ts` proxies `/api` to `:8001` by
   default, not `:8000` — check that if the dashboard shows stale data
   despite this process restarting cleanly.

## Triggering an analysis run

```bash
curl -X POST http://localhost:8000/api/pipeline/run
```

Returns a summary (`found_in_bucket`, `newly_processed`,
`skipped_by_prescreen`, `already_processed`, `failed`, `errors`). Safe to
call repeatedly — already-`ANALYZED` calls are skipped by default. Pass
`force=true` to re-analyze everything; per the checkpointer, this is *not*
"pay full price again" — only KPI nodes whose spec version changed, or that
are newly enabled, actually call a model. See
[`../docs/pipeline.md`](../docs/pipeline.md#what-force-means-now).

This is exactly what the dashboard's "Run Analysis" button calls, and what
[`../run-analysis.bat`](../run-analysis.bat) wraps for the command line.

## Cost optimizations

Roughly in order of how much they save:

1. **Prescreen gate** (`MIN_AUDIO_BYTES`, default 2048 bytes). Objects too
   small to contain speech are marked rejected/corrupted from the bucket
   listing metadata alone — never downloaded, never sent to a model.
   `tests/test_graph.py` asserts this (0 downloads, 0 model calls).
2. **The checkpointer.** Audio is transcribed once per recording, ever. A
   re-analysis — after a prompt tweak, a new KPI, or just clicking "force" —
   resumes from the checkpointed transcript and pays for text-only KPI calls,
   not audio. See [`../docs/pipeline.md`](../docs/pipeline.md) for the full
   design and the measured cost table.
3. **Two model tiers.** Only the transcription node (one per recording) uses
   the stronger, more expensive model; every KPI node runs on the cheapest
   available tier.
4. **In-place retries** (`ANALYSIS_MAX_RETRIES`). A transient 429/503 is
   retried by LangChain's `.with_retry()` rather than failing the call — for
   the transcription node especially, a failure would mean re-downloading and
   re-sending the same expensive audio next run.
5. **Cache-friendly prompt ordering.** Each node's instruction block is sent
   *before* the variable content (audio or transcript). Gemini's implicit
   caching only rewards a shared *prefix*.
6. **Already-analyzed calls are skipped** by default, so a normal click is
   nearly free once the bucket is caught up.
7. **A spend cap per run** (`PIPELINE_RUN_LIMIT`, default 5; override with
   `?limit=`). Prescreened-out objects don't count against it. `limit=0`
   means uncapped.
8. **Bounded concurrency** (`ANALYSIS_CONCURRENCY`, default 4) — saves
   wall-clock time, keeps memory/quota bounded, doesn't affect spend.

## Project structure

```
app/
  config.py                 Settings (env-driven, see .env.example)
  db/
    models.py                 SQLAlchemy models; CONVERSATION_STATUSES (see docs/data-model.md)
    session.py                  engine / Session / get_db dependency
  services/
    gcs_service.py                lists + downloads audio objects from the bucket
    llm_service.py                tiered Gemini access (transcription vs. extraction)
    call_analysis_service.py      bridges a KpiSpec to llm_service
    category_service.py           issue-category taxonomy + tag vocabulary (converging, not fixed)
    kpi_config_service.py         which KPI nodes are enabled (Admin toggles)
    synthetic_data_service.py     cost-free dummy data for QA — no GCS/Gemini calls
    scheduler_service.py          optional daily auto-run
  pipeline/
    prompts.py                    every LLM prompt, one constant per node — edit wording here
    kpi_registry.py               wires prompts.py to schema/tier/version — see docs/pipeline.md
    graph.py                       the LangGraph state machine, built from the registry
    checkpointer.py                 Postgres-backed LangGraph checkpointer, with in-memory fallback
    ingest_pipeline.py              batch driver: DB, concurrency, persistence, error isolation
  schemas/
    analysis.py                  per-KPI-node structured-output contracts
    calls.py / dashboard.py / admin.py / pipeline.py   API response models
  api/
    routes_pipeline.py           POST /api/pipeline/run, GET /api/pipeline/status
    routes_calls.py                GET /api/calls, GET /api/calls/{id}, GET .../audio
    routes_dashboard.py             GET /api/dashboard/summary|insights|plants|agents
    routes_admin.py                  schedule, synthetic data, KPI toggles
    routes_health.py                  shallow + deep health probes
  main.py                     FastAPI app, middleware order, static frontend mount
migrations/                 Alembic — hand-written revisions in versions/
tests/                       pytest — graph/checkpointer behaviour, no live DB needed (`uv run pytest`)
```

## Dynamic KPI categories

The issue taxonomy (`mention_categories`) is not a fixed list — it grows as
new kinds of cases show up, and generic catch-all categories ("Other...") are
explicitly rejected rather than allowed to absorb everything. See
[`../docs/data-model.md`](../docs/data-model.md#the-converging-taxonomy) for
the full mechanism and the measurement that led to banning generic buckets.

## Customer satisfaction banding

`satisfaction_rating` is a raw 1–10 AI estimate per call. Bucketed for
reporting as **9–10 = Satisfied, 8 = Borderline, 1–7 = Not Satisfied** — but
only over calls where a customer actually spoke. A busy tone's placeholder
rating is not a real 5; see
[`../docs/data-model.md`](../docs/data-model.md#the-conversation-gate) for
why this distinction is load-bearing and what it corrected on this dataset.

## TLS / corporate proxy

`app/__init__.py` calls `truststore.inject_into_ssl()` before anything else
in the package runs.

Python normally trusts only the CA bundle shipped by `certifi`. On a network
that performs TLS inspection — a proxy re-signing traffic with its own root
CA — that bundle knows nothing about the proxy's certificate, so every
outbound HTTPS call (Gemini, GCS) fails with *"self-signed certificate in
certificate chain"* or *"unable to get local issuer certificate."* The
proxy's root CA is already installed in the **OS** certificate store (that's
how the browser trusts it); `truststore` points Python at that store instead.
Not hypothetical here — before this was added, GCS listing failed outright.
Falls back to `certifi` with a logged warning if the injection fails, which
is correct on a network without inspection.

## Error responses and CORS

Middleware order in `main.py` is load-bearing:

```
CORSMiddleware  ->  catch_unhandled_errors  ->  routes
```

`add_middleware` inserts at the front of the stack, so the **last**
registered is outermost — the error catcher is registered first, CORS
second. Do **not** replace the catcher with `@app.exception_handler(Exception)`:
Starlette routes the catch-all handler to `ServerErrorMiddleware`, which sits
*outside* `CORSMiddleware`, so its 500 carries no
`Access-Control-Allow-Origin` and the browser reports a misleading "blocked
by CORS policy" instead of the real error. `tests/test_error_cors.py` guards
this.

## Notes before a real run

- Every *new* call costs one transcription-tier call plus one
  extraction-tier call per enabled KPI. Nothing runs automatically unless the
  Admin schedule is turned on — analysis only happens when triggered.
- Use the Admin tab's **Synthetic Data** panel (`data_mode=synthetic`) to
  exercise dashboard/KPI changes without spending anything on real data —
  see [`../docs/dashboard.md`](../docs/dashboard.md#data-mode).
