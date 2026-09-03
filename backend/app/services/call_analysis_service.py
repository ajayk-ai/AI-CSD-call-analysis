"""Runs one KPI spec against one call.

This used to hold a single 80-line prompt that did transcription and every
classification in one Gemini call. That prompt now lives split across
`app/pipeline/kpi_registry.py`, one section per node, and this module is just
the two-line bridge between a `KpiSpec` and the model: pick the right tier,
format the prompt, invoke.

Keeping it separate from `llm_service` (which knows about models) and from
`graph.py` (which knows about flow) is what lets a node be executed from a
test, or one-off from a script, without building a graph.
"""

from app.db.models import MentionType
from app.pipeline.kpi_registry import KpiSpec
from app.schemas.analysis import TranscriptionResult
from app.services import llm_service


def transcribe(spec: KpiSpec, audio_bytes: bytes, mime_type: str) -> TranscriptionResult:
    """The audio pass. Runs once per recording, ever — its output is
    checkpointed, so re-analysis reuses it rather than paying again."""
    result = llm_service.run_on_audio(spec.schema, spec.prompt, audio_bytes, mime_type)
    assert isinstance(result, TranscriptionResult)  # noqa: S101 - spec.schema guarantees this
    return result


def extract(spec: KpiSpec, transcript: str, known_categories: dict[MentionType, list[str]]):
    """A KPI pass over the transcript text — no audio, cheap tier.

    `known_categories` is the current taxonomy per mention type (from
    category_service.get_known_categories). Feeding it in each time is what
    makes the category list converge instead of drifting: Gemini reuses what
    already exists whenever it fits, and only proposes something new for a
    genuinely new kind of case. The caller persists anything new via
    category_service.register_new_categories.
    """
    return llm_service.run_on_text(spec.schema, spec.format_prompt(transcript, known_categories))
