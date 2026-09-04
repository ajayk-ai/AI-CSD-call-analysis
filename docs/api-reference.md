# API reference

Base URL: same origin as the frontend in production
(`start-prod.bat`, FastAPI serves the built dashboard); `http://localhost:8000`
in dev (`start.bat`, Vite proxies `/api` to it). Every response not otherwise
noted is JSON. Errors are `{"detail": "..."}` with a 4xx/5xx status —
`app/main.py`'s `catch_unhandled_errors` middleware guarantees even an
uncaught exception comes back this shape, with CORS headers intact (see
"Middleware order" in [architecture.md](architecture.md) if editing this).

## Dashboard

### `GET /api/dashboard/summary`

The dashboard's main payload — one call powers nearly every card via the
shared frontend cache (see [dashboard.md](dashboard.md)).

| Param | Type | Notes |
|---|---|---|
| `range` | `1d\|7d\|1m\|3m\|all` | Default `all`. Filters by `recording_date`, falling back to `created_at` |
| `plant` | `^[A-Za-z]{2}$` | Last two letters of `team_code`, e.g. `CE`/`TA` |
| `agent` | string | Exact `agent_name` match |
| `rating_source` | `ai\|stated` | Default `ai`. `stated` computes bands/average only from `customer_stated_rating`, with a `"Not Given"` slice for calls where the customer never gave one |
| `data_mode` | `live\|synthetic\|all` | Default `live` |
| `sentiment` | `positive\|neutral\|negative` | KPI cross-filter |
| `connection` | one of the six `ConnectionStatus` values | KPI cross-filter |
| `band` | `"9 - 10"\|"8"\|"1 - 7"\|"Not Given"` | KPI cross-filter |
| `quality` | `good_clear\|partial_usable\|rejected_corrupted` | KPI cross-filter |
| `adherence` | `followed\|partial\|not_followed` | KPI cross-filter |
| `category` | string | Exact `IssueMention.category`, matched across every mention type |

Every cross-filter param (`sentiment` through `category`) narrows every card
**except** the one that owns that dimension — see
[dashboard.md](dashboard.md#the-rule-that-keeps-a-filtered-dashboard-navigable).
`agent` behaves the same way: `by_agent` always shows the full roster
regardless of the current agent selection.

Response shape (`DashboardSummaryOut`, abbreviated):

```jsonc
{
  "range": "all", "plant": null, "agent": null,
  "rating_source": "ai", "data_mode": "live",
  "filters": { "agent": null, "sentiment": null, "..." },  // echoes every active filter

  "total_calls": 191, "analyzed_calls": 181,
  "reachable_calls": 90,   // audible, INCLUDING non-conversations — Connection card only
  "usable_calls": 71,      // reachable AND a real conversation — everything else's denominator
  "average_rating": 6.87,

  "call_quality": [ /* SliceOut[] */ ],
  "connection_status": [ /* SliceOut[], over reachable_calls */ ],
  "sentiment": [ /* SliceOut[] */ ],
  "satisfaction_bands": [ /* SliceOut[] */ ],
  "script_adherence": [ /* SliceOut[] */ ],

  "top_negative_drivers": [ /* SliceOut[], % of usable_calls, not of the table */ ],
  "top_service_issues": [ /* ... */ ],
  "top_positive_themes": [ /* ... */ ],
  "top_compliance_issues": [ /* ... */ ],

  "by_agent": [ /* AgentStatsOut[], always the full roster */ ],
  "current_month_label": "SEP 2026",
  "monthly_averages": [ /* MonthlyAverageOut[], last 3 months before the latest */ ],
  "daily_ratings": [ /* DailyRatingOut[], the latest month's daily average */ ]
}
```

`SliceOut`:

```jsonc
{
  "key": "negative",              // stable machine value — UI colors/icons key off this
  "label": "NEGATIVE",            // display text
  "count": 8, "percentage": 11.27,
  "example": "...verbatim quote...", "tags": ["response-time", "delay"],
  // Issue-category rows only — see data-model.md#praise-vs-problem-split.
  // Both null unless the category genuinely appears as both praise and problem.
  "positive_calls": null, "negative_calls": null, "negative_share": null
}
```

`monthly_averages`/`daily_ratings` are **not** filtered by `range` — they
always span the latest month present in the data plus the three before it,
anchored on the data's own latest call rather than today's clock (so a
dataset that stops in August still renders correctly in September).

### `GET /api/dashboard/insights`

Cross-signal correlation: positive themes that co-occur, on the *same
calls*, with a negative driver or service issue — e.g. "service praised
alongside spare-part pricing complaints in 23 calls." Same `range`, `plant`,
`agent`, `data_mode`, and cross-filter params as `/summary`.

```jsonc
{
  "range": "all", "plant": null, "agent": null, "data_mode": "live",
  "filters": { /* echoed, same shape as /summary */ },
  "usable_calls": 71,
  "insights": [
    {
      "positive_category": "Dealer Support",
      "other_category": "Spare Parts Delay",
      "other_mention_type": "negative_driver",
      "count": 4, "percentage": 5.63,
      "positive_example": "...", "other_example": "..."
    }
  ]
}
```

### `GET /api/dashboard/plants`

`{"plants": ["CE", "TA"]}` — every plant code seen, unfiltered by range or
the current plant selection (so the dropdown's own option list doesn't
shrink because the selected time range happens to have none from a plant).
Takes `data_mode`.

### `GET /api/dashboard/agents`

`{"agents": ["Rahul", "Divya Nair", ...]}` — same "don't shrink the picker"
rule as `/plants`. Takes `data_mode`.

## Calls

### `GET /api/calls`

The Calls page's list — filterable, sortable, paginated.

| Param | Notes |
|---|---|
| `limit`, `offset` | Default `limit=100` |
| `sort_by` | One of `created_at`, `recording_date`, `team_code`, `agent_name`, `status`, `call_quality`, `sentiment`, `satisfaction_rating` |
| `sort_dir` | `asc\|desc`, default `desc`. NULLs always sort last regardless of direction |
| `plant`, `status`, `call_quality`, `sentiment`, `agent_name` | Exact-match filters |
| `rating_min`, `rating_max` | 1–10, filters `satisfaction_rating` (the AI estimate — not `customer_stated_rating`) |
| `date_from`, `date_to` | Inclusive, same effective-date rule as the dashboard's `range` |
| `search` | `ILIKE` across `object_name`, `team_code`, `analysis.summary` |
| `category` | Exact `IssueMention.category`, any mention type — what the dashboard's issue tables link to |
| `tag` | Exact tag match |
| `connection_status` | One of the six `ConnectionStatus` values |
| `script_adherence` | `followed\|partial\|not_followed` |
| `conversations_only` | bool, default `false`. Restricts to the dashboard's exact `usable_calls` set — see [data-model.md](data-model.md#the-conversation-gate). Needed for `rating_min`/`rating_max` to line up exactly with a satisfaction-band review link |
| `data_mode` | `live\|synthetic\|all`, default `live` |

Returns `CallListItemOut[]` — no wrapper object, no total count (the frontend
pages by requesting `limit + 1` and checking whether it got that many back).

### `GET /api/calls/{id}`

`CallDetailOut` — everything from the list item plus:

```jsonc
{
  "transcript": {
    "text": "...verbatim, as spoken...",
    "english_text": "...full English rendering, or null on pre-migration rows...",
    "language_code": "hi-IN", "confidence": null
  },
  "mentions": [
    { "mention_type": "service_issue", "category": "Hydraulic Issues",
      "quote": "...", "tags": ["hydraulic", "leak"] }
  ]
}
```

### `GET /api/calls/{id}/audio`

Streams the raw recording (proxied through the backend, not a GCS signed
URL) for the inline player. `404` for a synthetic call — there is no real
recording behind it.

## Pipeline

### `POST /api/pipeline/run`

Triggers a batch analysis run. Synchronous — the response is the finished
summary, which at the default limit is a few seconds.

| Param | Notes |
|---|---|
| `limit` | Max recordings sent to Gemini this run. Omit → `settings.pipeline_run_limit` (default 5). `0` = no cap. Prescreened-out (too-small) objects are free and don't count |
| `force` | Re-analyze already-`ANALYZED` calls too. See [pipeline.md](pipeline.md#what-force-means-now) — cheap by construction, not a full re-cost |

```jsonc
{
  "found_in_bucket": 191, "already_processed": 140, "newly_processed": 12,
  "skipped_by_prescreen": 2, "failed": 1,
  "limit_applied": 5, "remaining_pending": 38,
  "errors": ["recordings/.../x.mp3: RESOURCE_EXHAUSTED..."]
}
```

### `GET /api/pipeline/status`

Cheap, DB-only (no GCS listing) — safe to poll.

```jsonc
{ "total_calls": 191, "analyzed": 181, "failed": 10, "not_yet_analyzed": 0, "default_run_limit": 5 }
```

## Admin

### `GET` / `PUT /api/admin/schedule`

The single-row daily auto-run config.

```jsonc
{ "enabled": false, "run_hour": 7, "run_minute": 0, "run_limit": null,
  "last_run_at": null, "last_run_status": null, "last_run_summary": null }
```

`PUT` body: `{ "enabled": bool, "run_hour": 0-23, "run_minute": 0-59,
"run_limit": int|null }`.

### `GET /api/admin/kpis`

The analysis graph, one entry per registered `KpiSpec`, in graph order. See
[pipeline.md](pipeline.md#the-kpi-registry).

```jsonc
[
  { "key": "transcription", "label": "Transcription & Audio Facts", "description": "...",
    "version": "v1", "tier": "transcription", "model": "gemini-3.5-flash",
    "enabled": true, "required": true },
  { "key": "sentiment", "...": "...", "tier": "extraction", "model": "gemini-3.5-flash-lite",
    "enabled": true, "required": false },
  { "key": "issues", "version": "v2", "...": "..." },
  { "key": "compliance", "version": "v2", "...": "..." }
]
```

### `PUT /api/admin/kpis/{key}`

`{ "enabled": bool }`. `400` if `key` is `required` (currently only
`transcription`); `404` for an unknown key. Takes effect on the next
pipeline run — cheaply, per the checkpointer (see
[pipeline.md](pipeline.md#the-checkpointer--why-re-analysis-is-cheap)).

### `GET /api/admin/synthetic-data`

`{"live_calls": 181, "synthetic_calls": 0}`.

### `POST /api/admin/synthetic-data?count=N`

Generates `N` (5–1000) realistic dummy calls entirely in-process — no GCS
listing, no Gemini call, costs nothing. Returns the same status shape.

### `DELETE /api/admin/synthetic-data`

Removes every `is_synthetic=True` row (cascades to its transcript, analysis,
and mentions).

## Health

### `GET /api/health`

Shallow — DB connectivity plus config presence, safe to poll freely.

```jsonc
{ "status": "ok", "database": "ok", "gemini_api_key": "set",
  "gcs_bucket": "csdcallaudio",
  "model": "gemini-3.5-flash (audio) + gemini-3.5-flash-lite (kpi)" }
```

### `GET /api/health/{database|gcs|gemini}`

Deep probes — actually exercise the named dependency. `gemini` costs a real
(tiny) model call, so this is manual-trigger-only from the Admin tab, never
auto-polled. Returns one probe object: `{"name": "gemini", "status": "ok",
"detail": "model '...' responded"}`.

### `GET /api/health/all`

All three probes at once — what `verify-setup.bat` calls to confirm a fresh
machine is fully wired before anyone clicks "Run Analysis."

```jsonc
{
  "status": "ok",
  "probes": [
    { "name": "database", "status": "ok", "detail": "..." },
    { "name": "gcs", "status": "ok", "detail": "..." },
    { "name": "gemini", "status": "ok", "detail": "model '...' responded" }
  ]
}
```
