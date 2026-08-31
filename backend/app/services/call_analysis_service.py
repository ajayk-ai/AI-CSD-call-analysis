import base64
from functools import lru_cache

from langchain_core.messages import HumanMessage
from langchain_core.runnables import Runnable
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import get_settings
from app.db.models import MentionType
from app.schemas.analysis import CallAnalysisResult

# The instruction block is identical for every call in a batch, so it is sent
# BEFORE the audio. Gemini's implicit context caching only rewards a shared
# *prefix* — with the audio first (as this originally was) every request had a
# unique prefix and could never hit cache. Ordering it this way costs nothing
# and lets the shared prefix be cached as the category list grows.
_PROMPT = """You are a QA analyst for a heavy-equipment dealership's customer service desk. \
Listen to the attached call recording and do two things in one pass: transcribe it, then classify it.

TRANSCRIPT: produce a full verbatim transcript. If the call is code-mixed (e.g. Hindi/English), \
transcribe it as spoken rather than translating.

CALL QUALITY: "good_clear" if the audio is coherent and clearly usable, "partial_usable" if parts are \
noisy/inaudible but the gist is still analyzable, "rejected_corrupted" if there is nothing analyzable \
in the recording.

"rejected_corrupted" covers two different cases, and BOTH must use it:
  (a) the audio is broken, silent, or too short to make out; and
  (b) the audio is perfectly clear but NO CONVERSATION HAPPENED — a busy tone, a ringing tone, an \
automated network message ("the number you have dialed is currently busy", "the person you are calling \
is not answering"), a voicemail greeting, an IVR menu with no human, or a call that connects and ends \
before the customer says anything of substance.
Case (b) is common in this bucket and easy to get wrong: the recording sounds clean, so it is tempting \
to call it "good_clear". Don't. A dialer artifact is not a customer service call, and scoring one as a \
usable neutral call silently drags down every average on the report. If nobody had a conversation, it \
is rejected_corrupted.

SENTIMENT: the customer's overall sentiment — "positive", "neutral", or "negative".

SATISFACTION RATING: your best estimate of the customer's satisfaction, 1 (furious/unresolved) to 10 \
(delighted). Treat 8 and above as a satisfied customer and 7 or below as not satisfied, and pick the \
number that puts the call on the correct side of that line. If call_quality is "rejected_corrupted" \
there is no customer opinion to measure — the reporting layer discards the rating for those calls, so \
just return 5 and don't try to infer a mood from silence.

For each of the three category lists below, the same rule applies: reuse an existing category whenever \
it's a reasonable fit — this keeps reporting consistent over time — and only write a new, short, \
specific label when the call genuinely doesn't match anything already listed. Never force a mismatch \
just to avoid creating a new one.

NEGATIVE DRIVERS (only if call_quality is not rejected_corrupted): for each distinct complaint driver \
you can identify, existing categories seen so far: {negative_categories}

SERVICE / MACHINE ISSUES: for each distinct mechanical/technical issue mentioned, existing categories \
seen so far: {service_categories}

POSITIVE THEMES: for each distinct thing the customer praised or appreciated, existing categories seen \
so far: {positive_categories}

Only include a category if the call actually supports it — an empty list is fine and expected for \
calls that don't mention that kind of thing. Where possible, attach a short verbatim quote.
"""


def _format_categories(names: list[str]) -> str:
    return ", ".join(names) if names else "(none recorded yet — propose the first one)"


@lru_cache(maxsize=1)
def _get_structured_llm() -> Runnable:
    """Built once and reused — constructing the client per call would re-do
    auth/transport setup on every recording for no benefit.

    `.with_retry` handles transient model errors (429 rate limits, 503s) in
    place. That matters for cost: without it a blip fails the call, and the
    next pipeline run re-downloads and re-sends the same audio, paying the
    expensive audio-input tokens a second time.
    """
    settings = get_settings()
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        # Low temperature: this is transcription + classification, not a
        # creative task — keeping it deterministic also keeps repeat runs
        # comparable.
        temperature=0.2,
    )
    return llm.with_structured_output(CallAnalysisResult).with_retry(
        stop_after_attempt=settings.analysis_max_retries
    )


def analyze_call_audio(
    audio_bytes: bytes,
    mime_type: str,
    known_categories: dict[MentionType, list[str]],
) -> CallAnalysisResult:
    """One Gemini call does both transcription and KPI/sentiment
    classification — no separate Speech-to-Text pass. Audio is sent inline
    (fine for typical call-recording sizes); the caller fetches the bytes
    from wherever they live (GCS, in this pipeline).

    `known_categories` is the current taxonomy per mention type (from
    category_service.get_known_categories) — feeding it in each time is what
    makes the category list converge instead of drifting: Gemini reuses what
    already exists whenever it fits, and only proposes something new for a
    genuinely new kind of case. The caller persists anything new via
    category_service.register_new_categories.
    """
    prompt = _PROMPT.format(
        negative_categories=_format_categories(known_categories.get(MentionType.NEGATIVE_DRIVER, [])),
        service_categories=_format_categories(known_categories.get(MentionType.SERVICE_ISSUE, [])),
        positive_categories=_format_categories(known_categories.get(MentionType.POSITIVE_THEME, [])),
    )

    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {
                "type": "media",
                "mime_type": mime_type,
                "data": base64.b64encode(audio_bytes).decode("utf-8"),
            },
        ]
    )

    result = _get_structured_llm().invoke([message])
    if result is None:
        raise ValueError("Gemini did not return a parseable analysis result")
    return result
