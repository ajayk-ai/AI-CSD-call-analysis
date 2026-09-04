# Architecture

## What this is

A single-tenant tool that turns call-center recordings into a KPI dashboard.
One person (or a small team) points it at a GCS bucket of `.mp3`/`.wav`
recordings, clicks "Run Analysis," and gets a dashboard of call quality,
sentiment, satisfaction, connection health, script compliance, and ranked
issue categories — all derived from Gemini reading the actual audio, not from
a fixed rubric.

It runs as two local processes talking to a local Postgres instance:

```
┌─────────────────────┐        ┌──────────────────────────┐        ┌────────────┐
│   React dashboard    │◄──────►│      FastAPI backend       │◄──────►│  Postgres   │
│  (frontend/, Vite)   │  HTTP  │       (backend/, uv)       │  SQL   │  (local)    │
└─────────────────────┘        └──────────────┬─────────────┘        └────────────┘
                                               │
                                   ┌───────────┴───────────┐
                                   │                        │
                              GCS bucket              Gemini API
                          (recordings only)      (transcription + KPI extraction)
```

Nothing runs automatically in the background by default — analysis is
triggered by a button (`POST /api/pipeline/run`) or an optional daily
schedule you turn on from the Admin tab. Every recording costs money to
analyze, so nothing touches Gemini without a human (or the schedule) asking
it to.

## Why it's shaped this way

**Two processes, not a monolith**, because the frontend is a pure consumer of
JSON — it never touches GCS, Gemini, or Postgres directly. In production
(`start-prod.bat`) FastAPI serves the built frontend itself from the same
port, so "two processes" collapses to one for a real deployment; the split
still matters during development, where the Vite dev server proxies `/api` to
the backend for hot-reload.

**One Postgres instance, no message queue.** The dataset is a few hundred
recordings, analysis runs are triggered by a human clicking a button, and the
concurrency need is "process a handful of recordings in parallel," not
"handle bursty production traffic." A queue would be solving a problem this
system doesn't have.

**The pipeline is a LangGraph state machine, not a linear script**, because
the shape of "what to extract from a call" changes over time — see
[pipeline.md](pipeline.md) for the full design. The short version: a graph
lets audio-derived facts (transcription, agent name, connection status) and
text-derived facts (sentiment, issues, compliance) live in separate nodes with
separate cost profiles, and a checkpointer lets re-analysis skip the
expensive part.

**The dashboard aggregates in SQL, not in a data warehouse.** `GET
/api/dashboard/summary` runs a handful of `SELECT`s against `call_analysis`
and `issue_mentions`, groups in Python, and returns pre-computed slices. At
this data volume (hundreds, not millions, of rows) a real OLAP layer would be
solving a problem this system doesn't have either — the query cost is
negligible and the code stays readable.

## Request flow: from a recording to a dashboard number

```
1. GCS bucket                    recordings/<date>/<team_code>/<file>.mp3
        │  gcs_service.list_audio_blobs()
        ▼
2. ingest_pipeline.run_pipeline()          one `calls` row per object (idempotent upsert)
        │
        ▼
3. LangGraph (pipeline/graph.py)           see pipeline.md
        │  prescreen → transcribe → {sentiment, issues, compliance} → assemble
        ▼
4. Postgres                                 calls / transcripts / call_analysis /
        │                                    issue_mentions / mention_categories
        │
        ▼
5. GET /api/dashboard/summary               SQL aggregation + Python grouping,
        │  ?range=&plant=&agent=&sentiment=&...   see dashboard.md for the filter design
        ▼
6. React dashboard                          cards render slices; clicking one
                                              either narrows the whole page or
                                              jumps to Calls with an exact filter
```

Step 3 is the expensive step (the only one that costs a Gemini call) and the
one most worth understanding — see [pipeline.md](pipeline.md). Steps 4–6 are
documented in [data-model.md](data-model.md) and [dashboard.md](dashboard.md).
The full endpoint surface is in [api-reference.md](api-reference.md).

## Directory map

```
backend/
  app/
    config.py                 Settings — env-driven, see backend/.env.example
    db/
      models.py                SQLAlchemy models + CONVERSATION_STATUSES (data-model.md)
      session.py                 engine / Session / get_db dependency
    services/
      gcs_service.py               lists + downloads audio objects
      llm_service.py               tiered model access (pipeline.md)
      call_analysis_service.py      bridges a KpiSpec to llm_service
      category_service.py           issue-category taxonomy + tag vocabulary
      kpi_config_service.py         which KPI nodes are enabled
      synthetic_data_service.py     cost-free dummy data for QA
      scheduler_service.py          optional daily auto-run
    pipeline/
      kpi_registry.py              the KPI node registry (pipeline.md)
      graph.py                      the LangGraph state machine
      checkpointer.py                Postgres-backed LangGraph checkpointer
      ingest_pipeline.py             batch driver: DB, concurrency, persistence
    schemas/                    Pydantic contracts (model output + API responses)
    api/
      routes_pipeline.py          POST /api/pipeline/run, GET /api/pipeline/status
      routes_calls.py               GET /api/calls, GET /api/calls/{id}
      routes_dashboard.py            GET /api/dashboard/summary, /insights, /plants, /agents
      routes_admin.py                 schedule, synthetic data, KPI toggles
      routes_health.py                 shallow + deep health probes
    main.py                    FastAPI app, middleware order, static frontend mount
  migrations/                 Alembic, hand-written revisions in versions/
  tests/                      pytest — no network or live DB required for test_graph.py

frontend/
  src/
    App.tsx                    tab shell, dashboard layout
    state/
      dashboardContext.ts        shared summary cache + filter hooks
      dashboardData.tsx            the cache provider
      navigation.tsx               cross-tab "review these calls" plumbing
      filterMapping.ts             DashboardFilters -> CallFilters translation
    components/
      dashboard/                  one file per KPI card
      admin/                       Admin tab panels
      common/                      shared primitives (Card, DonutChart, RankedTable, ...)
      layout/                      TabNav, DashboardHeader
    pages/
      CallsPage.tsx                filterable/sortable call list + transcript viewer
      AdminPage.tsx                 schedule, KPI flow, synthetic data, endpoint health
    services/api.ts             typed fetch wrappers — the only file that knows fetch()

docs/                          this folder
```

## Where to read next

- **[pipeline.md](pipeline.md)** — the KPI-node graph, the checkpointer, why
  re-analysis is cheap, how to add a KPI.
- **[data-model.md](data-model.md)** — the schema, the conversation-status
  gate (why busy tones don't count as conversations), the category taxonomy.
- **[dashboard.md](dashboard.md)** — the cross-filter design (why a filtered
  card still shows its full breakdown) and the click-to-review mechanism.
- **[api-reference.md](api-reference.md)** — every endpoint, every query
  param, response shapes.
