"""Tests for the per-call analysis graph.

These deliberately avoid the network and the database: the point is to prove
the prescreen gate actually prevents the expensive work (GCS download + Gemini
call) from happening, which is the cost claim the graph is built around.
"""

import pytest

from app.config import get_settings
from app.db.models import MentionType
from app.pipeline import graph as graph_module
from app.schemas.analysis import CallAnalysisResult, CallQualityLabel, SentimentLabel


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def spies(monkeypatch):
    """Replaces the two expensive operations with counters."""
    calls = {"downloads": 0, "analyses": 0}

    def fake_download(bucket_name: str, object_name: str) -> bytes:
        calls["downloads"] += 1
        return b"\x00" * 50_000

    def fake_analyze(audio_bytes, mime_type, known_categories) -> CallAnalysisResult:
        calls["analyses"] += 1
        return CallAnalysisResult(
            transcript="hello",
            language_code="en-IN",
            call_quality=CallQualityLabel.GOOD_CLEAR,
            sentiment=SentimentLabel.POSITIVE,
            sentiment_summary="fine",
            satisfaction_rating=9,
            summary="ok",
        )

    monkeypatch.setattr(graph_module.gcs_service, "download_blob_bytes", fake_download)
    monkeypatch.setattr(graph_module.call_analysis_service, "analyze_call_audio", fake_analyze)
    return calls


def _invoke(size_bytes: int | None):
    return graph_module.build_call_analysis_graph().invoke(
        {
            "bucket_name": "csdcallaudio",
            "object_name": "recordings/2026-08-24/BMCSTTA/x.mp3",
            "size_bytes": size_bytes,
            "known_categories": {mt: [] for mt in MentionType},
        }
    )


def test_tiny_object_is_skipped_without_download_or_model_call(spies, monkeypatch):
    """A 288-byte object (the bucket has several) must cost nothing at all."""
    monkeypatch.setenv("MIN_AUDIO_BYTES", "2048")

    state = _invoke(288)

    assert state["skipped_reason"] is not None
    assert "288 bytes" in state["skipped_reason"]
    assert state.get("result") is None
    assert spies == {"downloads": 0, "analyses": 0}


def test_real_sized_object_is_downloaded_and_analyzed(spies, monkeypatch):
    monkeypatch.setenv("MIN_AUDIO_BYTES", "2048")

    state = _invoke(180_000)

    assert state.get("skipped_reason") is None
    assert state["result"].satisfaction_rating == 9
    assert spies == {"downloads": 1, "analyses": 1}


def test_audio_is_dropped_from_state_after_analysis(spies, monkeypatch):
    """Recordings shouldn't linger in memory once they've been sent."""
    monkeypatch.setenv("MIN_AUDIO_BYTES", "2048")

    state = _invoke(180_000)

    assert not state.get("audio_bytes")


def test_gate_can_be_disabled(spies, monkeypatch):
    monkeypatch.setenv("MIN_AUDIO_BYTES", "0")

    state = _invoke(288)

    assert state.get("skipped_reason") is None
    assert spies == {"downloads": 1, "analyses": 1}


def test_unknown_size_is_not_skipped(spies, monkeypatch):
    """Missing metadata must not silently drop a real recording."""
    monkeypatch.setenv("MIN_AUDIO_BYTES", "2048")

    state = _invoke(None)

    assert state.get("skipped_reason") is None
    assert spies == {"downloads": 1, "analyses": 1}


def test_empty_download_skips_the_model_call(spies, monkeypatch):
    """Object passed the size gate but came back empty — still no model spend."""
    monkeypatch.setenv("MIN_AUDIO_BYTES", "2048")
    monkeypatch.setattr(graph_module.gcs_service, "download_blob_bytes", lambda b, o: b"")

    state = _invoke(180_000)

    assert state["skipped_reason"] == "Downloaded object was empty."
    assert spies["analyses"] == 0
