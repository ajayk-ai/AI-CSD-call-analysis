# CSD Call Analysis Dashboard

React + TypeScript + Vite dashboard visualizing the "Customer Trust Improvement Mission"
service feedback analysis report. All data currently comes from a synthetic
mock dataset — swap [`src/data/mockData.ts`](src/data/mockData.ts) for a real
API/data source when the backend pipeline is ready.

## Getting started

```bash
npm install
npm run dev
```

Then open the printed local URL (defaults to http://localhost:5173).

Other scripts:

```bash
npm run build    # type-check and produce a production build in dist/
npm run preview  # preview the production build locally
npm run lint     # run oxlint
```

## Project structure

```
src/
  components/
    common/        # generic, reusable UI primitives (Card, DonutChart, RankedTable)
    layout/         # page chrome (DashboardHeader)
    dashboard/      # one component per report section (charts, tables, panels)
  data/
    mockData.ts     # synthetic dataset typed against DashboardData
  types/
    dashboard.types.ts  # shared TypeScript contracts for the dashboard data
  styles/
    theme.css       # CSS custom properties (colors, spacing, radii) for the dark theme
  App.tsx           # composes the dashboard sections into the report grid layout
  index.css         # global resets + background
```

### Data flow

Every section component receives typed props (e.g. `CallQualitySummary`
receives a `CallQualitySlice[]`), so swapping `mockData.ts` for a fetched
payload only requires matching the shapes in `dashboard.types.ts` — no
component changes needed.
