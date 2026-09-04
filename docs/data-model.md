# Data model

All tables in [`app/db/models.py`](../backend/app/db/models.py); schema
history in [`backend/migrations/versions/`](../backend/migrations/versions/)
(Alembic, hand-written revisions, applied with `uv run alembic upgrade head`).

## Entity overview

```
Call ──1:1── Transcript
  │
  ├──1:1── CallAnalysis
  │
  └──1:N── IssueMention ──N:1── (category name, free text, drawn from
                                  the converging taxonomy in MentionCategory)

MentionCategory      the known category names per mention type — grows over time
SchedulerConfig       single-row: the optional daily auto-run schedule
KpiConfig              sparse overrides of KpiSpec.default_enabled (see pipeline.md)
```

`Call` is the identity anchor: one row per GCS object, created the first time
the bucket listing sees it (`gcs_uri` is unique). `Transcript` and
`CallAnalysis` are 1:1 with `Call`, created once analysis completes, and
**replaced wholesale** on re-analysis (`ingest_pipeline._clear_previous_attempt`
deletes the old `Transcript`/`CallAnalysis`/`IssueMention` rows before writing
new ones) — there is no history of prior analysis attempts, only the latest.

## `Call`

| Column | Notes |
|---|---|
| `gcs_uri`, `bucket_name`, `object_name` | Identity — `gcs_uri` is unique |
| `team_code` | Parsed from the path (`recordings/<date>/<team_code>/<file>`); its last two letters are the "plant" (`plant_expr` — no separate plant column, every plant-filtering query derives it from this same expression) |
| `recording_date` | Parsed from the path, `"2026-08-24"` string form |
| `status` | `CallStatus`: `pending → analyzing → analyzed`, or `failed` |
| `is_synthetic` | True only for rows from `synthetic_data_service` — never the real pipeline. See [dashboard.md](dashboard.md#data-mode) |

## `Transcript`

| Column | Notes |
|---|---|
| `text` | Verbatim, as spoken — code-mixed stays code-mixed |
| `english_text` | Full English rendering, produced in the same transcription call. Null on rows analyzed before this field existed |
| `language_code` | Best-guess BCP-47, e.g. `hi-IN` |

## `CallAnalysis` — the KPI row

| Column | Notes |
|---|---|
| `call_quality` | `good_clear` / `partial_usable` / `rejected_corrupted` — about the **recording's clarity only** |
| `connection_status` | `connected` / `dropped_during_call` / `dropped_at_greeting` / `no_answer_busy` / `voicemail_ivr_only` / `silent_dead_air` — whether a real conversation happened. See **the conversation gate**, below — this is the field that matters most for correct reporting |
| `sentiment` | `positive` / `neutral` / `negative` |
| `satisfaction_rating` | 1–10, AI estimate. `5` is a **placeholder**, not a real score, on any call where `connection_status` isn't a conversation state — see below |
| `customer_stated_rating` | 1–10, only set if the customer said an actual number out loud; null otherwise |
| `agent_name` | Extracted from self-identification in the transcript; null if never stated |
| `script_adherence` | `followed` / `partial` / `not_followed` |
| `model_name` | Both tiers, recorded as text: `"gemini-3.5-flash (audio) + gemini-3.5-flash-lite (kpi)"` |
| `raw_model_output` | Full `CallAnalysisResult` JSON, including `kpi_versions` — an audit trail of which spec version produced each part of the row |

## `IssueMention`

One row per (call, category) hit — negative drivers, service/machine issues,
positive themes, and agent-compliance issues all share this table,
distinguished by `mention_type`.

| Column | Notes |
|---|---|
| `mention_type` | `negative_driver` / `service_issue` / `positive_theme` / `agent_compliance` |
| `category` | Free text, but drawn from a converging taxonomy — see below |
| `quote` | Short verbatim excerpt, when the model found one |
| `tags` | `ARRAY(String)` — 1–3 short, hyphenated descriptors (`"pricing"`, `"response-time"`), freeform and *not* part of the converging taxonomy; this is what lets the same underlying problem be found across calls filed under different categories |

## `MentionCategory` — the converging taxonomy

Not a fixed enum. Seeded once
([`0001_initial_schema.py`](../backend/migrations/versions/0001_initial_schema.py))
and grown by [`category_service.py`](../backend/app/services/category_service.py):

1. `get_known_categories(db)` reads the current names per mention type and
   feeds them into the prompt — the model is told to reuse an existing
   category whenever one reasonably fits.
2. `register_new_categories(db, result)` persists whatever the model had to
   invent, so it's an option on the *next* call. This is what makes the
   ranked issue tables converge onto a stable, meaningful vocabulary instead
   of fragmenting into near-duplicate one-off labels.

**The generic-bucket problem, and the fix.** The original seed list included
`"Other Issues (AC, Electrical, GPS, etc.)"` and `"Other Mechanical Issues"`
alongside the specific categories they claim to summarize. In practice the
generic bucket's own name lists the specific cases sitting next to it, so it
reads as the better match — and it won.  Measured on the live dataset before
the fix: `AC / Cooling Problems`, `Electrical / Wiring / GPS Issues`, `Engine
Performance Issues`, and `Transmission Issues` had **zero uses, ever**, while
the two generic buckets had absorbed 18 calls between them.

Fixed in [`0006_retire_generic_categories.py`](../backend/migrations/versions/0006_retire_generic_categories.py)
(deletes both rows from `mention_categories`, so they're no longer offered)
plus `category_service.is_generic_category()` — a regex guard
(`^(other|misc|miscellaneous|general|unknown|uncategori[sz]ed|various)\b`)
that `register_new_categories` checks before persisting anything, so an
equivalent bucket can't be re-minted. The `issues` and `compliance` KPI specs
were bumped to `v2` with a prompt that states the rule outright: *"NEVER
invent a generic bucket... When nothing in the list fits, write a NEW short
specific label for what the call is actually about."*

**Tag convergence** works the same way, one level down:
`category_service.get_known_tags(db)` returns the most-used tags
(`SELECT unnest(tags), count(*) ... ORDER BY count DESC LIMIT 60`), fed back
into the prompt so `"response-time"` gets reused instead of respelled as
`"slow-response"` on the next call.

## The conversation gate — the single most important business rule in this schema

```python
# app/db/models.py
CONVERSATION_STATUSES: tuple[ConnectionStatus, ...] = (
    ConnectionStatus.CONNECTED,
    ConnectionStatus.DROPPED_DURING_CALL,
)
```

A busy tone, a voicemail greeting, or a call cut off during the agent's
opening produces a **perfectly clear recording** — so `call_quality !=
rejected_corrupted` says yes to all of them. But there is no customer opinion
on any of those to measure: the model has nothing to judge, returns its
neutral defaults (`sentiment=neutral`, `satisfaction_rating=5`), and those
defaults are not evidence of a "mediocre" call — they're an absence of data
mislabeled as a data point.

Measured on the live dataset: 19 of 90 calls previously counted as "usable"
(21%) were non-conversations. Counting them pulled the average satisfaction
from **6.87 down to 6.48** and diluted every sentiment/compliance/issue
figure with the same phantom mass.

Every aggregation in `routes_dashboard.py` now uses **two distinct
denominators**, computed in one pass by `_aggregate()`:

| Denominator | Gate | Used by |
|---|---|---|
| `reachable_calls` | `call_quality != rejected_corrupted` | Call Connection Quality card *only* — its entire purpose is showing how many audible calls never became conversations |
| `usable_calls` | `reachable_calls` **and** `connection_status in CONVERSATION_STATUSES` | Every other KPI: sentiment, satisfaction, script compliance, issue tables, agent performance, the trend chart |

The same gate is enforced on `/api/calls` via the `conversations_only` query
param, so a "review these calls" link from a satisfaction-band row can't
accidentally sweep in a busy tone whose placeholder rating of 5 happened to
fall in the clicked band. (One subtlety this fixed: a number of historical
`call_quality=rejected_corrupted` rows still carry a stale
`connection_status=connected` default from before this column was populated —
`conversations_only` therefore checks *both* `call_quality` and
`connection_status`, not connection status alone.)

## Percentages: share of usable calls, not share of the table

Ranked issue tables (`top_negative_drivers`, `top_service_issues`, etc.) used
to report each row's percentage as a share of *mentions within that table* —
so every table summed to 100%, which overstated everything, since one call
can raise several issues and most calls raise none. `SliceOut.percentage` is
now `count / usable_calls * 100` for issue rows: a category on 9 of 71 usable
calls reads as 12.7%, and the column does not (and should not) sum to 100.

## Praise vs. problem split

The same category name can legitimately appear on both sides — e.g.
`"Installation / Delivery Issues"` praised on 4 calls and complained about on
1. `_Aggregate.mentions()` tracks `category_positive_calls` and
`category_negative_calls` per name across *every* mention type, and
`SliceOut` carries `positive_calls` / `negative_calls` / `negative_share`
(0–100) — populated only when a category genuinely has both, so a purely
negative category on a negative-drivers table doesn't clutter every row with
a tautological "100% problem."

## Migration history

| Revision | What it added |
|---|---|
| `0001_initial_schema` | Core tables, seeded `MentionCategory` (including the two generic buckets, later retired) |
| `0002_scheduler_config` | `scheduler_config` single-row table |
| `0003_analysis_dimensions` | `connection_status`, `script_adherence`, `agent_name`, `customer_stated_rating` on `CallAnalysis`; `tags` on `IssueMention`; `agent_compliance` mention type |
| `0004_synthetic_data_flag` | `calls.is_synthetic` |
| `0005_kpi_flow` | `transcripts.english_text`; `kpi_config` table |
| `0006_retire_generic_categories` | Deletes the two generic seed categories from `mention_categories` |

Note `langgraph-checkpoint-postgres`'s own `checkpoints*` tables are **not**
managed by Alembic — the library creates and versions them itself via
`PostgresSaver.setup()` (called once, lazily, in
[`checkpointer.py`](../backend/app/pipeline/checkpointer.py)). Owning them in
an Alembic revision would fight the library's own schema versioning.
