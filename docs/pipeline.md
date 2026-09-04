# The analysis pipeline

## The problem this design solves

The first version of this pipeline sent one Gemini call per recording that
did everything at once — transcription, agent identification, call quality,
connection status, sentiment, satisfaction, issue extraction, script
compliance — on the cheapest model tier available.

That works until you want to change *one* of those things. Every dashboard
iteration on this project has ended the same way: a wording fix to how
"satisfaction" is judged, or a new field like `customer_stated_rating`, meant
re-sending every recording's audio to get the new field populated on
historical data. Audio-input tokens are by far the most expensive part of a
Gemini call, so "tweak one KPI" and "re-transcribe the entire bucket" had
become the same operation.

The current pipeline exists to break that coupling: **the expensive step
(listening to the audio) happens once and is durably checkpointed; everything
downstream is cheap, independent, and individually re-runnable.**

## Shape of the graph

```
prescreen ──(too small / empty)──▶ END                    [free — no download, no model call]
    │
    ▼
transcribe                          [STRONG model, gemini-3.5-flash — the ONLY node
    │                                 that touches audio]
    │  produces: transcript (verbatim), transcript_english,
    │            language_code, agent_name, call_quality, connection_status
    │
    ├──────────────┬──────────────┐
    ▼              ▼              ▼          [CHEAP model, gemini-3.5-flash-lite,
 sentiment      issues       compliance        text-only, run concurrently]
    │              │              │
    └──────────────┴──────┬───────┘
                          ▼
                      assemble ──▶ END        [folds every node's output into one
                                                 CallAnalysisResult; persisted as-is]
```

Implemented in [`app/pipeline/graph.py`](../backend/app/pipeline/graph.py),
built from the declarative list in
[`app/pipeline/kpi_registry.py`](../backend/app/pipeline/kpi_registry.py).

### Why `call_quality` / `connection_status` / `agent_name` live in `transcribe`

These are judgments that genuinely require *hearing* the recording: was it
clear, was there dead air, did the agent say their name. Inferring them from
a transcript would be guesswork. Everything past `transcribe` is text
reasoning over a transcript that's already been written down, and belongs on
the cheap tier.

### Why `transcribe` produces two transcripts

`transcript` is verbatim, as spoken — a Hindi/English code-mixed call stays
code-mixed, because this is the record of what was actually said and quotes
have to be quotable. `transcript_english` is a full English rendering,
produced in the same model call. Every downstream KPI node reads
`transcript_english`, so no text-reasoning step pays to work across a
code-mixed transcript. The Calls page shows both, with an English/Original
toggle that only appears when they actually differ.

## The KPI registry — how a KPI gets added

[`kpi_registry.py`](../backend/app/pipeline/kpi_registry.py) is the single
source of truth for what gets analyzed. The graph, the Admin toggles, and the
checkpoint versioning are all *built from* this list — adding a KPI means
adding one `KpiSpec` entry, not touching the graph. It only wires
`prompt -> schema -> tier -> version`; it holds no prompt wording itself.

**Prompt text lives in one place:**
[`app/pipeline/prompts.py`](../backend/app/pipeline/prompts.py) — one
`*_PROMPT` constant per node (`TRANSCRIPTION_PROMPT`, `SENTIMENT_PROMPT`,
`ISSUES_PROMPT`, `COMPLIANCE_PROMPT`), plus the fragments they share
(`TRANSCRIPT_PREAMBLE`, `TAXONOMY_RULE`, `ANALYST_ROLE`). This is the file to
open to read or tune what the model is actually asked, without wading through
registry/dataclass code. A new KPI's prompt goes here too, as a new constant
that `kpi_registry.py` then points a `KpiSpec.prompt` at.

```python
@dataclass(frozen=True)
class KpiSpec:
    key: str                    # graph node name, state slot, Admin toggle id,
                                 # and the key under which its version is recorded
    label: str                  # Admin UI label
    description: str            # Admin UI helper text
    version: str                # bump -> ONLY this node recomputes on the next run
    schema: type[BaseModel]     # this node's ENTIRE structured-output contract
    prompt: str
    needs_categories: tuple[MentionType, ...] = ()
    tier: ModelTier = ModelTier.EXTRACTION   # or ModelTier.TRANSCRIPTION
    default_enabled: bool = True
    required: bool = False      # transcription only — can't be switched off
```

Registered today: `transcription` (required), `sentiment`, `issues`,
`compliance`. Each has its own Pydantic schema in
[`app/schemas/analysis.py`](../backend/app/schemas/analysis.py)
(`TranscriptionResult`, `SentimentResult`, `IssuesResult`,
`ComplianceResult`) — a node's schema is its whole contract, so nodes neither
see nor depend on each other's fields. `assemble` unions every enabled node's
output into `CallAnalysisResult`, which is what gets persisted; a disabled or
not-yet-run KPI simply leaves its fields at their schema defaults.

**To add a KPI:** write its Pydantic result schema, write a `KpiSpec` with a
fresh `key` and `version="v1"`, add it to `KPI_SPECS`. It appears in Admin's
KPI Flow panel automatically, defaults to enabled, and starts producing data
on the next analysis run — for calls that have already been transcribed, that
run costs one cheap text call and zero audio.

**To change a KPI's prompt or its schema's meaning:** edit its spec's prompt
and bump `version` (`"v1"` → `"v2"`). Every other spec's version is untouched,
so only this node recomputes.

## The checkpointer — why re-analysis is cheap

[`app/pipeline/checkpointer.py`](../backend/app/pipeline/checkpointer.py)
wires a `PostgresSaver` (from `langgraph-checkpoint-postgres`) as the graph's
checkpointer, keyed by `thread_id = str(call.id)` — stable across runs, so
the same call always resumes its own state.

Every node opens with the same guard:

```python
def _is_fresh(state, spec) -> bool:
    if state["kpi_versions"].get(spec.key) != spec.version:
        return False
    # ...validate the checkpointed payload still matches the current schema...
    return True
```

If a node's output is already checkpointed at its current version, the node
returns immediately — no model call, and for `transcribe`, no download
either. This is the entire mechanism behind three claims, all verified
against the real Postgres checkpointer in this project's test suite:

| Scenario | Audio cost | Text-model cost |
|---|---|---|
| First analysis of a call | 1 download + 1 transcription | 1 call per enabled KPI |
| Forced re-run, nothing changed | **0** | **0** (every node still fresh) |
| One KPI toggled on in Admin, then re-run | **0** | 1 call — only the new node |
| One KPI's prompt version bumped, then re-run | **0** | 1 call — only that node |

**No audio ever enters graph state**, deliberately: `transcribe` downloads
and sends within one function, and the bytes go out of scope when it
returns. This is what makes checkpointing affordable at all — a checkpoint
holds JSON-serializable node outputs (each `.model_dump(mode="json")`'d
before being written to state), never a recording. An earlier version of
this pipeline argued *against* a checkpointer on exactly the "it would have
to serialize megabytes of audio" ground; that objection is designed out here
rather than accepted.

If Postgres is unreachable when the checkpointer is first requested, it
degrades to an in-memory saver with a logged warning rather than failing the
whole pipeline — losing cross-run resume is a cost problem, but a run that
refuses to start at all is worse.

## Two model tiers

[`app/services/llm_service.py`](../backend/app/services/llm_service.py) is
the only module that turns a `ModelTier` into an actual Gemini client,
cached per `(tier, schema)`:

- `ModelTier.TRANSCRIPTION` → `settings.gemini_transcription_model`
  (`gemini-3.5-flash` by default) — the one node that reads audio, where
  transcription accuracy on noisy, code-mixed call-center recordings actually
  benefits from a stronger model.
- `ModelTier.EXTRACTION` → `settings.extraction_model`
  (`gemini-3.5-flash-lite` by default) — every KPI node, reasoning over text
  that's already been written down.

`settings.gemini_model` still exists as a **deprecated alias**: if set (e.g.
in an old `.env`), it overrides the extraction tier, so an existing
deployment's config keeps working without edits.

Net effect on cost: analyzing a *new* call costs one strong-model audio pass
plus one cheap text pass per enabled KPI — modestly more than the old
single-call design, in exchange for better transcription and per-KPI
re-runnability. Re-analyzing an *already-transcribed* call costs only the
cheap text passes for whichever KPIs are stale, and often costs nothing at
all.

## Batch driver: `run_pipeline`

[`app/pipeline/ingest_pipeline.py`](../backend/app/pipeline/ingest_pipeline.py)
is the part that owns the database — the graph itself never touches a
Session, so it's safe to run several calls concurrently on worker threads
(`ThreadPoolExecutor`, bounded by `settings.analysis_concurrency`, default
4).

Per run:

1. List the bucket (`gcs_service.list_audio_blobs()`), upsert a `calls` row
   per object (idempotent on `gcs_uri`).
2. Skip anything already `ANALYZED`, unless `force=True`.
3. Apply the spend cap (`limit`, defaults to `settings.pipeline_run_limit`) —
   prescreened-out objects (too small to contain speech) are free and never
   count against it.
4. Read the enabled-KPI set once per run
   (`kpi_config_service.enabled_keys`), so every call in one run sees the
   same graph shape.
5. Process in chunks of `analysis_concurrency`; reload the category taxonomy
   and tag vocabulary once per chunk (not per call — see
   [data-model.md](data-model.md) for why that's the deliberate
   convergence trade-off).
6. Persist serially on the main thread: `Transcript`, `CallAnalysis`, and
   `IssueMention` rows, plus any newly-seen category
   (`category_service.register_new_categories`).

One call's failure (`FAILED` status, error message recorded) never aborts the
batch — the next call in the chunk still runs, and the failed one retries on
the next click.

## What "force" means now

`force=True` (the "Re-analyze already-processed calls" checkbox in Admin's
Manual Run panel) used to mean "pay full price again." It no longer does —
the checkpointer decides what actually recomputes. In practice, forcing a
re-run after a KPI prompt change or a new KPI toggle is the normal workflow
for backfilling historical data, and it's cheap by construction.

## Admin: KPI Flow panel

`GET /api/admin/kpis` lists every registered `KpiSpec` — label, tier badge,
resolved model name, version, enabled state. `PUT /api/admin/kpis/{key}`
toggles one (rejected with 400 for the required `transcription` node, 404 for
an unknown key). The panel's own copy states the mechanic plainly: turning a
KPI on and then forcing a re-run recomputes only that node, from the
checkpointed transcript — no audio is re-sent. See
[api-reference.md](api-reference.md#admin) for the exact contract.
