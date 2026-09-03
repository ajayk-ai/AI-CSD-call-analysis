"""Model access, split by tier.

There used to be exactly one Gemini client here, because there was exactly one
model call per recording. Now there is one call per graph node, and the nodes
are not equally hard: transcribing noisy code-mixed call-center audio is the
job worth paying a stronger model for, while classifying a transcript that has
already been written down is not. `ModelTier` is that distinction, and this
module is the only place that turns a tier into an actual client.

Clients are cached per (tier, schema) rather than built per call — constructing
one re-does auth and transport setup for no benefit, and a batch run builds the
same handful over and over.
"""

import base64
from functools import lru_cache

from langchain_core.messages import HumanMessage
from langchain_core.runnables import Runnable
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from app.config import get_settings
from app.pipeline.kpi_registry import ModelTier


def model_name_for(tier: ModelTier) -> str:
    settings = get_settings()
    if tier is ModelTier.TRANSCRIPTION:
        return settings.gemini_transcription_model
    return settings.extraction_model


@lru_cache(maxsize=None)
def _structured_llm(tier: ModelTier, schema: type[BaseModel]) -> Runnable:
    """`.with_retry` handles transient model errors (429 rate limits, 503s) in
    place. That matters most for the transcription tier: without it a blip
    fails the node, and the next run re-downloads and re-sends the same audio,
    paying the expensive audio-input tokens a second time."""
    settings = get_settings()
    llm = ChatGoogleGenerativeAI(
        model=model_name_for(tier),
        google_api_key=settings.gemini_api_key,
        # Low temperature: this is transcription + classification, not a
        # creative task — keeping it deterministic also keeps repeat runs
        # comparable.
        temperature=0.2,
    )
    return llm.with_structured_output(schema).with_retry(stop_after_attempt=settings.analysis_max_retries)


def _invoke(tier: ModelTier, schema: type[BaseModel], content: list[dict]) -> BaseModel:
    result = _structured_llm(tier, schema).invoke([HumanMessage(content=content)])
    if result is None:
        raise ValueError(f"Gemini did not return a parseable {schema.__name__}")
    return result


def run_on_audio(
    schema: type[BaseModel], prompt: str, audio_bytes: bytes, mime_type: str
) -> BaseModel:
    """The expensive path — the only one that spends audio-input tokens.

    The instruction block is sent BEFORE the audio. Gemini's implicit context
    caching only rewards a shared *prefix*; with the audio first (as this
    originally was) every request had a unique prefix and could never hit
    cache. Ordering it this way costs nothing.
    """
    return _invoke(
        ModelTier.TRANSCRIPTION,
        schema,
        [
            {"type": "text", "text": prompt},
            {
                "type": "media",
                "mime_type": mime_type,
                "data": base64.b64encode(audio_bytes).decode("utf-8"),
            },
        ],
    )


def run_on_text(schema: type[BaseModel], prompt: str) -> BaseModel:
    """The cheap path — a KPI node reasoning over an already-written transcript."""
    return _invoke(ModelTier.EXTRACTION, schema, [{"type": "text", "text": prompt}])
