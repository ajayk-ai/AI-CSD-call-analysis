# AI CSD Call Analysis

Analysis tooling and reporting for customer service call transcripts, built
around the "Customer Trust Improvement Mission" service feedback report.

## Structure

- [`frontend/`](frontend/) — React + TypeScript + Vite dashboard that visualizes
  call quality, sentiment, satisfaction, issue trends, and KPI targets. Currently
  runs on synthetic/mock data (see [`frontend/src/data/mockData.ts`](frontend/src/data/mockData.ts));
  see [`frontend/README.md`](frontend/README.md) for setup and structure.
- [`main.py`](main.py) / [`pyproject.toml`](pyproject.toml) — Python project stub
  reserved for the call analysis / data pipeline.
