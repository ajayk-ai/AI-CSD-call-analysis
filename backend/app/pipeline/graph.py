"""Per-call analysis workflow, as a LangGraph state machine.

    prescreen ──(too small / unusable)──▶ END          [costs nothing]
        │
        └──(looks like real audio)──▶ fetch_audio ──▶ analyze ──▶ END

Deliberately **no database access inside these nodes**. The pipeline loads
what the graph needs beforehand and persists what it returns afterwards,
which keeps the nodes pure enough to run several calls concurrently on
threads without sharing a SQLAlchemy Session across them.

Also deliberately **no LangGraph checkpointer**. The `calls` table is already
the durable resume point (a call that didn't reach ANALYZED is retried on the
next run), so a checkpointer would be a second, redundant source of truth —
and it would have to serialize megabytes of audio bytes per call to do it.
"""

import logging
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.config import get_settings
from app.db.models import MentionType
from app.schemas.analysis import CallAnalysisResult
from app.services import call_analysis_service, gcs_service

logger = logging.getLogger(__name__)


class CallAnalysisState(TypedDict, total=False):
    # --- inputs ---
    bucket_name: str
    object_name: str
    size_bytes: int | None
    known_categories: dict[MentionType, list[str]]
    # --- working ---
    audio_bytes: bytes | None
    mime_type: str | None
    # --- outputs (exactly one of these is set) ---
    result: CallAnalysisResult | None
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


def _should_analyze(state: CallAnalysisState) -> str:
    return "fetch_audio" if state.get("skipped_reason") is None else END


def _fetch_audio(state: CallAnalysisState) -> CallAnalysisState:
    return {
        "audio_bytes": gcs_service.download_blob_bytes(state["bucket_name"], state["object_name"]),
        "mime_type": gcs_service.mime_type_for(state["object_name"]),
    }


def _analyze(state: CallAnalysisState) -> CallAnalysisState:
    audio_bytes = state.get("audio_bytes")
    if not audio_bytes:
        # Object exists but is empty — same conclusion as the prescreen, still
        # without spending a model call.
        return {"skipped_reason": "Downloaded object was empty."}

    result = call_analysis_service.analyze_call_audio(
        audio_bytes,
        state["mime_type"] or "audio/mp3",
        state.get("known_categories") or {},
    )
    # Drop the audio from state once it's been used — with several calls in
    # flight there's no reason to hold every recording in memory until the
    # graph finishes.
    return {"result": result, "audio_bytes": None}


def build_call_analysis_graph():
    graph = StateGraph(CallAnalysisState)
    graph.add_node("prescreen", _prescreen)
    graph.add_node("fetch_audio", _fetch_audio)
    graph.add_node("analyze", _analyze)

    graph.add_edge(START, "prescreen")
    graph.add_conditional_edges("prescreen", _should_analyze, {"fetch_audio": "fetch_audio", END: END})
    graph.add_edge("fetch_audio", "analyze")
    graph.add_edge("analyze", END)

    return graph.compile()


# Compiling is not free and the graph is stateless, so build it once.
call_analysis_graph = build_call_analysis_graph()
