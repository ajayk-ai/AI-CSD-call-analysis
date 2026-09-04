# CSD Call Analysis Dashboard

React + TypeScript + Vite dashboard for the backend in [`../backend/`](../backend/).
Every card reads live data from `GET /api/dashboard/summary` and related
endpoints — there is no mock dataset anymore; use the Admin tab's Synthetic
Data panel to generate cost-free dummy data for previewing changes instead
(see [`../docs/dashboard.md`](../docs/dashboard.md#data-mode)).

For how the dashboard is actually put together — the shared summary cache,
the cross-filter design, click-to-review navigation — see
**[`../docs/dashboard.md`](../docs/dashboard.md)**. For the full API surface
this talks to, see **[`../docs/api-reference.md`](../docs/api-reference.md)**.

## Getting started

```bash
npm install
npm run dev
```

Opens on `http://localhost:5173`, proxying `/api` to the backend on `:8001`
(see [`vite.config.ts`](vite.config.ts) — note this differs from the
backend's own default dev port of `:8000`; check `vite.config.ts` if the
dashboard shows stale data despite a backend restart).

Other scripts:

```bash
npm run build    # type-check (tsc -b) and produce a production build in dist/
npm run preview  # preview the production build locally
npm run lint     # oxlint
```

In production (`../start-prod.bat`), FastAPI serves this build directly from
`frontend/dist` — no separate Vite process, no proxy, same-origin requests.

## Project structure

```
src/
  App.tsx                    tab shell + the dashboard's card grid layout
  main.tsx                   entry point

  state/
    dashboardContext.ts        shared summary cache: hooks, cache-key logic
    dashboardData.tsx           the cache provider (fetch/invalidate/refresh)
    navigation.tsx               cross-tab "review these calls" plumbing
    filterMapping.ts             DashboardFilters -> CallFilters translation

  components/
    dashboard/                  one component per KPI card
    admin/                       Admin tab panels (schedule, KPI flow, synthetic data, health)
    common/                      shared primitives — Card, DonutChart, RankedTable,
                                  ClickableSlice, FilterChips, OpenCallsButton
    layout/                      TabNav, DashboardHeader

  pages/
    CallsPage.tsx                filterable/sortable call list + transcript/audio viewer
    AdminPage.tsx                 composes the Admin panels

  services/
    api.ts                      every fetch() call and its response types — the
                                  only file that talks to the backend directly

  data/presentation.ts         icon/color lookups for slice keys (sentiment, quality, ...)
  types/dashboard.types.ts     shared frontend-only types (e.g. TimeRangeKey)
  styles/theme.css             CSS custom properties for the dark theme
```

### Data flow

`state/dashboardData.tsx` owns one cache of dashboard-summary responses,
keyed by every active filter plus a `version` that only changes on an
explicit refresh. Most cards call `useDashboardSummary()` and read straight
off the cached payload — no component fetches on its own except `KeyInsights`
(its own endpoint) and `CallsPage` (its own paginated list). See
[`../docs/dashboard.md`](../docs/dashboard.md) for the full design, including
why a filtered card still shows its own full breakdown.
