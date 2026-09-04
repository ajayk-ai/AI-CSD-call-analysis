# Dashboard design

## The cards

| Card | Component | Reads |
|---|---|---|
| Call Quality Summary | `CallQualitySummary` → `DonutBreakdownCard` | `call_quality` (over `analyzed_calls`) |
| Call Connection Quality | `CallConnectionSummary` → `DonutBreakdownCard` | `connection_status` (over `reachable_calls` — see [data-model.md](data-model.md#the-conversation-gate)) |
| Overall Customer Sentiment | `SentimentOverview` | `sentiment` (over `usable_calls`) |
| Customer Satisfaction Rating | `SatisfactionRating` | `satisfaction_bands`, with an AI-estimate / customer-stated toggle |
| Agent Script Compliance | `AgentComplianceSummary` → `DonutBreakdownCard` | `script_adherence` |
| Top Issue Analysis | `IssueAnalysisTable` → `RankedIssuesCard` | `top_negative_drivers` |
| Top Service / Machine Issues | `ServiceIssuesTable` → `RankedIssuesCard` | `top_service_issues` |
| Compliance Issues | `ComplianceIssuesTable` → `RankedIssuesCard` | `top_compliance_issues` |
| Key Insights | `KeyInsights` | its own endpoint, `GET /api/dashboard/insights` |
| Agent Performance | `AgentPerformanceTable` | `by_agent` |
| Last 3 Months vs Current Month | `TrendComparison` | `monthly_averages`, `daily_ratings` |

All but `KeyInsights` and `TrendComparison` (which take `data`/`error` as
props from `App.tsx`'s single top-level fetch) call `useDashboardSummary`
directly and manage their own `TimeRangeFilter`.

## The shared cache

[`state/dashboardData.tsx`](../frontend/src/state/dashboardData.tsx) holds
one cache of `GET /api/dashboard/summary` responses, keyed by
`` `${version}:${range}:${ratingSource}:${dataMode}:${JSON.stringify(filters)}` ``
([`dashboardContext.ts`](../frontend/src/state/dashboardContext.ts)`.cacheKey`).
Every card that reads through `useDashboardSummary` shares this cache, so
selecting a filter fires one request that every card picks up, rather than
each card independently re-fetching.

`version` only changes on an explicit refresh (clicking "Run Analysis," or
generating/clearing synthetic data) — it invalidates every entry at once,
because a pipeline run moves every number on the page and refreshing panels
piecemeal would leave the dashboard internally inconsistent. Changing a
*filter* does not bump the version; it's just a different cache key, so
toggling a filter on and back off serves the second state from cache.

## The filter model

```typescript
// services/api.ts
interface DashboardFilters {
  plant: string | null;
  agent: string | null;
  sentiment: string | null;
  connection: string | null;
  band: string | null;
  quality: string | null;
  adherence: string | null;
  category: string | null;
}
```

`plant` and `agent` have dedicated dropdowns
(`PlantFilter`/`AgentFilter` in `App.tsx`); the rest are set by clicking a
slice, row, or band directly on a KPI card via `useKpiFilter(key)`:

```typescript
const { value, toggle, isActive } = useKpiFilter('sentiment');
// toggle('negative') sets it; calling toggle('negative') again clears it
```

Every active filter renders as a removable chip in `<FilterChips />`
(replacing what used to be a one-off "agent scoped" banner) — this is the
part that makes multi-dimension filtering safe to use: what's currently
narrowed is always visible, and always one click from gone.

## The rule that keeps a filtered dashboard navigable

Naively, clicking "Negative" on the sentiment card would filter every card —
*including the sentiment card itself* — down to 100% negative, with no
slices left to click to get back out. `routes_dashboard.py` avoids this with
one rule, applied per response:

> A card that **owns** an active filter dimension is rendered from the
> aggregate computed **without** that one dimension. Every other card sees
> every active filter.

Implemented via `KpiFilters.without(dimension)` and a small per-request
cache so each "excluding" aggregate is computed at most once:

```python
def _excluding(dimension: str) -> _Aggregate:
    if getattr(filters, dimension) is None:
        return scoped                      # no query needed — same as the full selection
    if dimension not in cache:
        cache[dimension] = _aggregate(db, _ids(filters.without(dimension)))
    return cache[dimension]

roster = _excluding("agent")               # by_agent — always the full roster
band_source = _excluding("band")           # satisfaction_bands
category_source = _excluding("category")   # the three issue tables
quality_source = _excluding("quality")     # call_quality
connection_source = _excluding("connection")
sentiment_source = _excluding("sentiment")
adherence_source = _excluding("adherence")
```

This is the same idea that already governed `by_agent` before the general
filter system existed (`AgentPerformanceTable` must always show the full
roster, or it stops being a usable picker once you're already looking at one
agent) — generalized from one dimension to seven. Concretely: filtering by
`sentiment=negative` narrows every other card's numbers, but the Sentiment
card itself still shows all three moods, with "Negative" visually marked as
the active selection.

## Click-to-review: from a number to the transcripts behind it

A count on a dashboard card can't be checked on its own. Every clickable
element that represents a group of calls carries an `OpenCallsButton` (or, on
donut-card slices, a `toReviewFilters` mapping) that jumps to the Calls tab
pre-filtered to exactly that group:

```
Category row in an issue table  →  category=<name>
Tag chip                        →  tag=<name>
Sentiment slice                 →  sentiment=<key>
Connection slice                →  connection_status=<key>   (no conversations_only —
                                                                this card's whole point
                                                                is showing non-conversations)
Script-adherence slice          →  script_adherence=<key> + conversations_only
Satisfaction band row           →  rating_min/rating_max + conversations_only
                                    (AI source only — see below)
Key Insights tile               →  category=<issue-side category> + conversations_only
```

Mechanics ([`state/navigation.tsx`](../frontend/src/state/navigation.tsx)):
`useNavigation().openCalls(filters)` stores the filters and switches the tab;
`CallsPage` picks them up in a mount effect (`App.tsx` unmounts the page
whenever the tab isn't active, so it remounts fresh on every visit) and shows
a small banner explaining the seeded filter for the three dimensions
(`category`, `tag`, `connection_status`) that have no dropdown of their own.

`state/filterMapping.ts`'s `toCallFilters()` translates the dashboard's
`DashboardFilters` into the Calls page's `CallFilters` shape, so a review
link carries forward every *other* active dashboard filter too — clicking
"Review" on a category row while the dashboard is already scoped to one
agent opens exactly that agent's calls for that category, not the whole
dataset's.

**`conversations_only`** exists specifically to keep these links exact. A
non-conversation call's `satisfaction_rating` is a placeholder `5`, not a
real judgment — without this flag, a "Review" link for the "1–7" band would
silently include busy tones that happen to carry that placeholder. Verified
end-to-end: `19 + 15 + 37 = 71` calls returned across the three band review
links, matching `usable_calls` exactly. See
[data-model.md](data-model.md#the-conversation-gate) and
[api-reference.md](api-reference.md#get-apicalls) for the query param.

**Why `band` doesn't survive the trip generically:** it's a derived bucket
over whichever rating source (`ai` vs `stated`) the Satisfaction card
currently shows, and `/api/calls`'s plain `rating_min`/`rating_max` filters
only the AI estimate column. `SatisfactionRating`'s review button is
therefore only rendered when `source === 'ai'` — showing it under "Customer
Stated" would silently filter on the wrong number.

## Data mode

`useDataMode()` — `'live'` (default) / `'synthetic'` / `'all'` — is global,
set from the Admin tab's Synthetic Data panel, and threaded through every
dashboard/Calls-page endpoint (`data_mode` query param). It exists so KPI
changes can be QA'd against realistic-shaped dummy data without spending on
real Gemini calls: `synthetic_data_service.generate(db, count)` writes
plausible `Call`/`CallAnalysis`/`Transcript`/`IssueMention` rows entirely
in-process, flagged `is_synthetic=True`, cleanly separable via `data_mode`.
`DataModeBanner` warns on-screen whenever the mode isn't `'live'`, so a
synthetic-data session can't be mistaken for real numbers.

## Admin tab

- **Endpoint Health** — polls `/api/health` and offers the deep probe
  (`/api/health/all`, which actually costs a Gemini call — manual trigger
  only).
- **Schedule** — the optional daily auto-run (`scheduler_service.py`).
- **KPI Flow** — lists the analysis graph from `GET /api/admin/kpis`, one
  toggle per node. See [pipeline.md](pipeline.md#the-kpi-registry).
- **Manual Run** — `POST /api/pipeline/run`, with the "Re-analyze
  already-processed calls" (`force`) checkbox.
- **Synthetic Data** — generate/clear dummy calls, switch data mode.
