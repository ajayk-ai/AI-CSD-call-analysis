"""Tests for the per-call analysis graph.

These deliberately avoid the network and the database: the point is to prove
the two cost claims the graph is built around —

1. the prescreen gate prevents the expensive work (GCS download + Gemini call)
   from happening at all, and
2. the checkpointer prevents it from happening *twice* — re-running a call, or
   adding a KPI to it, must not re-download or re-transcribe the recording.
"""

from dataclasses import replace

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.config import get_settings
from app.db.models import MentionType
from app.pipeline import graph as graph_module
from app.pipeline import kpi_registry
from app.schemas.analysis import (
    CallAnalysisResult,
    CallQualityLabel,
    ComplianceResult,
    ConnectionStatusLabel,
    IssuesResult,
    ScriptAdherenceLabel,
    SentimentLabel,
    SentimentResult,
    TranscriptionResult,
)


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def spies(monkeypatch):
    """Replaces the expensive operations with counters.

    `extractions` is per-KPI-key, because the whole point of the split is that
    the nodes run independently — a single total would hide which one ran.
    """
    calls = {"downloads": 0, "transcriptions": 0, "extractions": {}}

    def fake_download(bucket_name: str, object_name: str) -> bytes:
        calls["downloads"] += 1
        return b"\x00" * 50_000

    def fake_transcribe(spec, audio_bytes, mime_type) -> TranscriptionResult:
        calls["transcriptions"] += 1
        return TranscriptionResult(
            transcript="namaste, machine kharab hai",
            transcript_english="Hello, the machine is broken",
            language_code="hi-IN",
            agent_name="Rahul",
            call_quality=CallQualityLabel.GOOD_CLEAR,
            connection_status=ConnectionStatusLabel.CONNECTED,
        )

    _RESULTS = {
        "sentiment": SentimentResult(
            sentiment=SentimentLabel.POSITIVE,
            sentiment_summary="fine",
            satisfaction_rating=9,
            summary="ok",
        ),
        "issues": IssuesResult(),
        "compliance": ComplianceResult(script_adherence=ScriptAdherenceLabel.FOLLOWED),
    }

    def fake_extract(spec, transcript, known_categories):
        calls["extractions"][spec.key] = calls["extractions"].get(spec.key, 0) + 1
        # The KPI nodes must be reading the ENGLISH transcript, not the verbatim
        # one — that's the whole reason the transcription node produces both.
        assert transcript == "Hello, the machine is broken"
        return _RESULTS[spec.key]

    monkeypatch.setattr(graph_module.gcs_service, "download_blob_bytes", fake_download)
    monkeypatch.setattr(graph_module.call_analysis_service, "transcribe", fake_transcribe)
    monkeypatch.setattr(graph_module.call_analysis_service, "extract", fake_extract)
    return calls


def _inputs(size_bytes: int | None) -> dict:
    return {
        "bucket_name": "csdcallaudio",
        "object_name": "recordings/2026-08-24/BMCSTTA/x.mp3",
        "size_bytes": size_bytes,
    }


def _config(thread_id: str = "call-1") -> dict:
    return {
        "configurable": {
            "thread_id": thread_id,
            "known_categories": {mt: [] for mt in MentionType},
        }
    }


def _invoke(size_bytes: int | None):
    """One-shot, no checkpointer — the shape the original tests exercised."""
    return graph_module.build_call_analysis_graph().invoke(_inputs(size_bytes), config=_config())


def _result(state) -> CallAnalysisResult:
    """The graph returns plain JSON so nothing class-shaped lands in a
    checkpoint (see CallAnalysisState.result); this is the same validation the
    pipeline does on the way to the database."""
    return CallAnalysisResult.model_validate(state["result"])


def test_tiny_object_is_skipped_without_download_or_model_call(spies, monkeypatch):
    """A 288-byte object (the bucket has several) must cost nothing at all."""
    monkeypatch.setenv("MIN_AUDIO_BYTES", "2048")

    state = _invoke(288)

    assert state["skipped_reason"] is not None
    assert "288 bytes" in state["skipped_reason"]
    assert state.get("result") is None
    assert spies["downloads"] == 0
    assert spies["transcriptions"] == 0
    assert spies["extractions"] == {}


def test_real_sized_object_is_transcribed_then_analyzed_per_kpi(spies, monkeypatch):
    monkeypatch.setenv("MIN_AUDIO_BYTES", "2048")

    state = _invoke(180_000)

    assert state.get("skipped_reason") is None
    result = _result(state)
    # Fields from the audio node and from a KPI node both land on one result.
    assert result.agent_name == "Rahul"
    assert result.transcript_english == "Hello, the machine is broken"
    assert result.satisfaction_rating == 9
    assert spies["downloads"] == 1
    assert spies["transcriptions"] == 1
    assert spies["extractions"] == {"sentiment": 1, "issues": 1, "compliance": 1}


def test_gate_can_be_disabled(spies, monkeypatch):
    monkeypatch.setenv("MIN_AUDIO_BYTES", "0")

    state = _invoke(288)

    assert state.get("skipped_reason") is None
    assert spies["downloads"] == 1


def test_unknown_size_is_not_skipped(spies, monkeypatch):
    """Missing metadata must not silently drop a real recording."""
    monkeypatch.setenv("MIN_AUDIO_BYTES", "2048")

    state = _invoke(None)

    assert state.get("skipped_reason") is None
    assert spies["downloads"] == 1


def test_empty_download_skips_the_model_call(spies, monkeypatch):
    """Object passed the size gate but came back empty — still no model spend."""
    monkeypatch.setenv("MIN_AUDIO_BYTES", "2048")
    monkeypatch.setattr(graph_module.gcs_service, "download_blob_bytes", lambda b, o: b"")

    state = _invoke(180_000)

    assert state["skipped_reason"] == "Downloaded object was empty."
    assert spies["transcriptions"] == 0
    assert spies["extractions"] == {}


def test_rerunning_a_call_reuses_the_checkpointed_transcript(spies, monkeypatch):
    """The core cost claim: re-analysis must not re-download or re-transcribe.

    This is what makes a forced re-run affordable — audio-input tokens are by
    far the most expensive part of a run, and nothing about re-running a KPI
    invalidates the transcript.
    """
    monkeypatch.setenv("MIN_AUDIO_BYTES", "2048")
    graph = graph_module.build_call_analysis_graph(checkpointer=InMemorySaver())

    first = graph.invoke(_inputs(180_000), config=_config())
    second = graph.invoke(_inputs(180_000), config=_config())

    assert spies["downloads"] == 1
    assert spies["transcriptions"] == 1
    # Every KPI was already fresh too, so the second run called no model at all.
    assert spies["extractions"] == {"sentiment": 1, "issues": 1, "compliance": 1}
    # ...and still produced a complete result, from the checkpoint alone.
    assert _result(second).agent_name == _result(first).agent_name
    assert _result(second).satisfaction_rating == 9


def test_enabling_a_new_kpi_runs_only_that_node(spies, monkeypatch):
    """Adding a KPI later must cost one cheap text call, not a re-transcription.

    This is the scenario the whole registry/checkpointer design exists for:
    analyze with a subset of KPIs, then turn another one on and re-run.
    """
    monkeypatch.setenv("MIN_AUDIO_BYTES", "2048")
    checkpointer = InMemorySaver()

    without_compliance = graph_module.build_call_analysis_graph(
        checkpointer=checkpointer, enabled_keys=frozenset({"transcription", "sentiment", "issues"})
    )
    without_compliance.invoke(_inputs(180_000), config=_config())

    assert spies["extractions"] == {"sentiment": 1, "issues": 1}
    assert spies["downloads"] == 1

    # Someone switches "compliance" on in Admin and re-runs.
    with_compliance = graph_module.build_call_analysis_graph(
        checkpointer=checkpointer, enabled_keys=frozenset({"transcription", "sentiment", "issues", "compliance"})
    )
    state = with_compliance.invoke(_inputs(180_000), config=_config())

    # Only the new node ran. No second download, no second transcription, and
    # the two already-fresh KPI nodes stayed at one call each.
    assert spies["downloads"] == 1
    assert spies["transcriptions"] == 1
    assert spies["extractions"] == {"sentiment": 1, "issues": 1, "compliance": 1}
    assert _result(state).script_adherence is ScriptAdherenceLabel.FOLLOWED


def test_bumping_a_kpi_version_recomputes_only_that_kpi(spies, monkeypatch):
    """A prompt fix to one KPI must not invalidate the transcript or its peers."""
    monkeypatch.setenv("MIN_AUDIO_BYTES", "2048")
    checkpointer = InMemorySaver()

    graph_module.build_call_analysis_graph(checkpointer=checkpointer).invoke(
        _inputs(180_000), config=_config()
    )
    assert spies["extractions"] == {"sentiment": 1, "issues": 1, "compliance": 1}

    # Simulate editing the sentiment spec's prompt and bumping its version.
    # graph.py binds these names at import, so patch them there.
    bumped = replace(kpi_registry.SENTIMENT, version="v2")
    swap = lambda specs: tuple(bumped if s.key == "sentiment" else s for s in specs)  # noqa: E731
    monkeypatch.setattr(graph_module, "EXTRACTION_SPECS", swap(graph_module.EXTRACTION_SPECS))
    monkeypatch.setattr(graph_module, "KPI_SPECS", swap(graph_module.KPI_SPECS))

    graph_module.build_call_analysis_graph(checkpointer=checkpointer).invoke(
        _inputs(180_000), config=_config()
    )

    assert spies["downloads"] == 1
    assert spies["transcriptions"] == 1
    assert spies["extractions"] == {"sentiment": 2, "issues": 1, "compliance": 1}
