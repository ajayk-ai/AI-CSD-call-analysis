"""Per-call analysis workflow, as a LangGraph state machine built from the KPI
registry.

    prescreen ──(too small / unusable)──▶ END          [costs nothing]
        │
        ▼
    transcribe   [STRONG model — the only node that touches audio]
        │
        ├────────────┬────────────┐
        ▼            ▼            ▼                     [CHEAP model, text only,
    sentiment     issues     compliance  ...             one node per KpiSpec,
        │            │            │                      run in parallel]
        └────────────┴─────┬──────┘
                           ▼
                        assemble ──▶ END

The node list is not written here — it comes from `kpi_registry.KPI_SPECS`, so
adding a KPI is adding a spec, and disabling one (Admin → KPI Flow) drops its
node from the compiled graph.

**Every node begins by asking whether its output is already checkpointed at the
current version, and returns immediately if so.** That is the point of the
whole structure: transcription is the only expensive step, its output is what
survives in the checkpoint, and a KPI change never invalidates it. Re-analyzing
a call after adding a KPI therefore costs one cheap text call and zero audio
tokens.

Deliberately **no database access inside these nodes**. The pipeline loads what
the graph needs beforehand and persists what it returns afterwards, which keeps
the nodes pure enough to run several calls concurrently on threads without
sharing a SQLAlchemy Session across them.

Deliberately **no audio in the state**, either. `transcribe` downloads and
sends within one function, so the recording never becomes a state value and
therefore never reaches a checkpoint — which is what makes checkpointing cheap
enough to be worth doing at all. (An earlier version of this file argued
against a checkpointer on exactly that ground; the objection is designed out
here rather than accepted.)
"""

import logging
from typing import Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from app.config import get_settings
from app.db.models import MentionType
from app.pipeline.kpi_registry import (
    EXTRACTION_SPECS,
    KPI_SPECS,
    TRANSCRIPTION,
    KpiSpec,
    default_enabled_keys,
)
from app.schemas.analysis import CallAnalysisResult, TranscriptionResult
from app.services import call_analysis_service, gcs_service

logger = logging.getLogger(__name__)

ASSEMBLE_NODE = "assemble"


def _merge(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    """Reducer for the two per-KPI dicts. Nodes fan out in parallel and each
    writes only its own key, so a plain overwrite would let whichever finished
    last discard its siblings."""
    return {**(left or {}), **(right or {})}


class CallAnalysisState(TypedDict, total=False):
    # --- inputs ---
    bucket_name: str
    object_name: str
    size_bytes: int | None
    # --- working ---
    # Each KPI's structured output, dumped with `mode="json"` — i.e. plain
    # JSON-compatible values, no model instances and no enum members.
    #
    # This matters because state is what gets checkpointed, and a checkpoint
    # outlives the code that wrote it. A serialized class has to be resolvable
    # and still compatible at read time (LangGraph warns about exactly this and
    # intends to refuse it); a dict is just data, and `_is_fresh` can
    # re-validate it and quietly recompute if the schema has moved on.
    kpi_results: Annotated[dict[str, dict], _merge]
    # {kpi_key: version that produced it} — the freshness check every node runs.
    kpi_versions: Annotated[dict[str, str], _merge]
    # --- outputs (exactly one of these is set) ---
    # Also a plain dict, for the same reason; the pipeline validates it back
    # into a CallAnalysisResult on the way to the database.
    result: dict | None
    skipped_reason: str | None


def prescreen_reason(size_bytes: int | None) -> str | None:
    """Would this object be gated out before costing anything? Returns the
    reason, or None if it should go to the model.

    Lives here (rather than inline in `_prescreen`) so the batch driver can ask
    the same question from the bucket listing — it needs to know which pending
    calls are free in order to apply its spend limit only to the ones that
    aren't. One predicate, so the two can't drift apart.
    """
    threshold = get_settings().min_audio_bytes
    if threshold and size_bytes is not None and size_bytes < threshold:
        return (
            f"Audio is {size_bytes} bytes (below the {threshold}-byte minimum) "
            "— too small to contain speech."
        )
    return None


def _prescreen(state: CallAnalysisState) -> CallAnalysisState:
    """Cheapest possible filter, and the main cost win in this graph.

    Runs on the object metadata from the bucket listing, before anything is
    downloaded or sent to the model. An object of a few hundred bytes cannot
    contain intelligible speech, so paying audio-input tokens to have Gemini
    tell us it's corrupted is pure waste — we can conclude that for free.
    """
    reason = prescreen_reason(state.get("size_bytes"))
    if reason is not None:
        logger.info("Prescreen skipped %s: %s", state["object_name"], reason)
    return {"skipped_reason": reason}


def _is_fresh(state: CallAnalysisState, spec: KpiSpec) -> bool:
    """True when the checkpoint already holds this node's output at the current
    version — the guard that turns a re-run into a no-op for unchanged KPIs."""
    if (state.get("kpi_versions") or {}).get(spec.key) != spec.version:
        return False
    payload = (state.get("kpi_results") or {}).get(spec.key)
    if payload is None:
        return False
    try:
        spec.schema.model_validate(payload)
    except ValidationError:
        # Checkpointed under this version, but the schema has since changed
        # incompatibly. Treat as stale and recompute rather than crash later.
        logger.info("Checkpointed %s no longer matches its schema — recomputing.", spec.key)
        return False
    return True


def _known_categories(config: RunnableConfig) -> dict[MentionType, list[str]]:
    """Run-scoped context, passed via config rather than state so the taxonomy
    (which changes between runs and is reloaded per chunk anyway) is never
    frozen into a checkpoint."""
    return (config.get("configurable") or {}).get("known_categories") or {}


def _transcript_for_extraction(state: CallAnalysisState) -> str | None:
    """The English transcript the KPI nodes read.

    Falls back to the verbatim text if translation came back empty, so a KPI
    node degrades to reasoning over the original rather than over nothing.
    """
    payload = (state.get("kpi_results") or {}).get(TRANSCRIPTION.key)
    if not payload:
        return None
    return payload.get("transcript_english") or payload.get("transcript") or None


def _transcribe(state: CallAnalysisState) -> CallAnalysisState:
    if _is_fresh(state, TRANSCRIPTION):
        logger.info(
            "Reusing checkpointed transcript for %s — no download, no audio tokens.",
            state["object_name"],
        )
        return {}

    audio_bytes = gcs_service.download_blob_bytes(state["bucket_name"], state["object_name"])
    if not audio_bytes:
        # Object exists but is empty — same conclusion as the prescreen, still
        # without spending a model call.
        return {"skipped_reason": "Downloaded object was empty."}

    mime_type = gcs_service.mime_type_for(state["object_name"])
    result = call_analysis_service.transcribe(TRANSCRIPTION, audio_bytes, mime_type)
    # `audio_bytes` is a local, not a state field: it goes out of scope here
    # rather than lingering in memory across a batch or landing in a checkpoint.
    return {
        "kpi_results": {TRANSCRIPTION.key: result.model_dump(mode="json")},
        "kpi_versions": {TRANSCRIPTION.key: TRANSCRIPTION.version},
    }


def _make_extraction_node(spec: KpiSpec):
    def node(state: CallAnalysisState, config: RunnableConfig) -> CallAnalysisState:
        if _is_fresh(state, spec):
            return {}
        transcript = _transcript_for_extraction(state)
        if not transcript:
            # No transcript to reason over (transcription was skipped or came
            # back empty). Nothing to do — and nothing to charge for.
            return {}
        result = call_analysis_service.extract(spec, transcript, _known_categories(config))
        return {
            "kpi_results": {spec.key: result.model_dump(mode="json")},
            "kpi_versions": {spec.key: spec.version},
        }

    node.__name__ = f"kpi_{spec.key}"
    return node


def _assemble(state: CallAnalysisState) -> CallAnalysisState:
    """Folds every node's output into the single result the pipeline persists.

    A KPI that is disabled, or that produced nothing, simply contributes no
    fields — `CallAnalysisResult` defaults cover it — so turning a KPI off
    degrades that part of the dashboard rather than breaking the row.
    """
    payloads = state.get("kpi_results") or {}
    versions = state.get("kpi_versions") or {}

    merged: dict[str, Any] = {}
    for spec in KPI_SPECS:
        payload = payloads.get(spec.key)
        if payload is None:
            continue
        try:
            merged.update(spec.schema.model_validate(payload).model_dump(mode="json"))
        except ValidationError:
            logger.warning("Discarding unusable checkpointed output for %s", spec.key, exc_info=True)

    if not merged.get("transcript"):
        # Transcription is required; without it there is nothing to store.
        return {"skipped_reason": state.get("skipped_reason") or "No transcript was produced."}

    merged["kpi_versions"] = dict(versions)
    # Validated here so a malformed assembly fails inside the graph rather than
    # halfway through a database write, then dumped back to plain JSON so the
    # checkpoint holds no class references. The pipeline re-validates on read.
    return {"result": CallAnalysisResult.model_validate(merged).model_dump(mode="json")}


def _after_prescreen(state: CallAnalysisState) -> str:
    return TRANSCRIPTION.key if state.get("skipped_reason") is None else END


def _make_after_transcribe(next_nodes: list[str]):
    """Router out of the transcription node.

    Returns the whole list of KPI nodes at once, which is how LangGraph fans
    out: they all run in the same superstep, i.e. concurrently, rather than
    one after another.

    A recording that turned out to be empty stops here instead — running the
    KPI nodes on a non-existent transcript would spend tokens to produce
    nothing.
    """

    def route(state: CallAnalysisState) -> list[str] | str:
        return next_nodes if state.get("skipped_reason") is None else END

    return route


def build_call_analysis_graph(
    checkpointer: BaseCheckpointSaver | None = None,
    enabled_keys: frozenset[str] | None = None,
):
    """Compiles the flow for one set of enabled KPIs.

    `enabled_keys` filters which extraction nodes exist at all; transcription
    is always present (`KpiSpec.required`). `checkpointer=None` compiles a
    stateless graph — used by the tests, which have no database.
    """
    keys = default_enabled_keys() if enabled_keys is None else enabled_keys
    specs = [spec for spec in EXTRACTION_SPECS if spec.key in keys]

    graph = StateGraph(CallAnalysisState)
    graph.add_node("prescreen", _prescreen)
    graph.add_node(TRANSCRIPTION.key, _transcribe)
    graph.add_node(ASSEMBLE_NODE, _assemble)

    graph.add_edge(START, "prescreen")
    graph.add_conditional_edges(
        "prescreen", _after_prescreen, {TRANSCRIPTION.key: TRANSCRIPTION.key, END: END}
    )

    for spec in specs:
        graph.add_node(spec.key, _make_extraction_node(spec))
        # Fan-in: every KPI node feeds assemble, which LangGraph runs once all
        # of them have finished.
        graph.add_edge(spec.key, ASSEMBLE_NODE)

    # With every KPI disabled the flow still runs — transcription alone
    # produces the transcript, agent name, quality and connection status.
    next_nodes = [spec.key for spec in specs] or [ASSEMBLE_NODE]
    graph.add_conditional_edges(
        TRANSCRIPTION.key, _make_after_transcribe(next_nodes), [*next_nodes, END]
    )

    graph.add_edge(ASSEMBLE_NODE, END)

    return graph.compile(checkpointer=checkpointer)


_compiled: dict[frozenset[str], Any] = {}


def get_call_analysis_graph(enabled_keys: frozenset[str]):
    """Compiled graphs, cached per enabled-KPI set.

    Compiling is not free and a batch run reuses the same configuration for
    every call, but the set can change between runs (someone toggles a KPI in
    Admin), so this is a small cache rather than a module-level singleton.
    """
    from app.pipeline import checkpointer as checkpointer_module

    if enabled_keys not in _compiled:
        _compiled[enabled_keys] = build_call_analysis_graph(
            checkpointer=checkpointer_module.get_checkpointer(), enabled_keys=enabled_keys
        )
    return _compiled[enabled_keys]


__all__ = [
    "ASSEMBLE_NODE",
    "CallAnalysisState",
    "TranscriptionResult",
    "build_call_analysis_graph",
    "get_call_analysis_graph",
    "prescreen_reason",
]
