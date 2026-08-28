from google import genai
from google.genai import types

from app.config import get_settings
from app.schemas.analysis import (
    NEGATIVE_DRIVER_CATEGORIES,
    POSITIVE_THEME_CATEGORIES,
    SERVICE_ISSUE_CATEGORIES,
    CallAnalysisResult,
)

_PROMPT = """You are a QA analyst for a heavy-equipment dealership's customer service desk. \
Listen to the attached call recording and do two things in one pass: transcribe it, then classify it.

TRANSCRIPT: produce a full verbatim transcript. If the call is code-mixed (e.g. Hindi/English), \
transcribe it as spoken rather than translating.

CALL QUALITY: "good_clear" if the audio is coherent and clearly usable, "partial_usable" if parts are \
noisy/inaudible but the gist is still analyzable, "rejected_corrupted" if the audio is too broken, \
silent, or short to say anything meaningful about the call.

SENTIMENT: the customer's overall sentiment — "positive", "neutral", or "negative".

SATISFACTION RATING: your best estimate of the customer's satisfaction, 1 (furious/unresolved) to 10 (delighted).

NEGATIVE DRIVERS (only if call_quality is not rejected_corrupted): for each distinct complaint driver \
you can identify, pick the closest matching category from this exact list (do not invent new labels): \
{negative_categories}

SERVICE / MACHINE ISSUES: for each distinct mechanical/technical issue mentioned, pick the closest \
matching category from this exact list: {service_categories}

POSITIVE THEMES: for each distinct thing the customer praised or appreciated, pick the closest \
matching category from this exact list: {positive_categories}

Only include a category if the call actually supports it — an empty list is fine and expected for \
calls that don't mention that kind of thing. Where possible, attach a short verbatim quote.
"""


def analyze_call_audio(audio_bytes: bytes, mime_type: str) -> CallAnalysisResult:
    """Sends call audio straight to Gemini (Developer API, API-key auth) — one
    call does both the transcription and the KPI/sentiment classification,
    instead of a separate Speech-to-Text pass. The bytes are passed inline
    (fine for typical call-recording sizes); the caller is responsible for
    fetching them from wherever they're stored (GCS, in this pipeline).
    """
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)

    prompt = _PROMPT.format(
        negative_categories=", ".join(NEGATIVE_DRIVER_CATEGORIES),
        service_categories=", ".join(SERVICE_ISSUE_CATEGORIES),
        positive_categories=", ".join(POSITIVE_THEME_CATEGORIES),
    )

    audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=[audio_part, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CallAnalysisResult,
            # Low temperature: this is transcription + classification, not a
            # creative task — keeping it deterministic also keeps repeat
            # runs comparable.
            temperature=0.2,
        ),
    )

    result = response.parsed
    if result is None:
        raise ValueError(f"Gemini did not return a parseable analysis result: {response.text!r}")
    return result
