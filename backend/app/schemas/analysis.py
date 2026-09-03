from enum import Enum

from pydantic import BaseModel, Field

# Category taxonomy (negative drivers, service/machine issues, positive
# themes) is NOT hardcoded here — it lives in the `mention_categories` table
# and grows over time via app/services/category_service.py. The initial seed
# list (mirroring frontend/src/data/mockData.ts) is in the first Alembic
# migration; from there, any new category Gemini has to invent for a call
# gets persisted so it's offered as a reusable option on the next call. See
# category_service.get_known_categories / register_new_categories.
#
# STRUCTURE OF THIS MODULE
# ------------------------
# The analysis is produced by several independent graph nodes rather than one
# model call (see app/pipeline/kpi_registry.py), so there is one small
# structured-output model per node — TranscriptionResult, SentimentResult,
# IssuesResult, ComplianceResult. Each is the *entire* contract for its node,
# which is what lets a node be added, removed, or re-run on its own.
#
# CallAnalysisResult at the bottom is NOT sent to any model any more: it is the
# assembled union of those node outputs, and it exists so the persistence layer
# (ingest_pipeline._store_result), the dashboard and the frontend keep seeing
# the same shape they always have. Every field on it therefore has a default —
# a disabled KPI node simply contributes nothing.


class CallQualityLabel(str, Enum):
    GOOD_CLEAR = "good_clear"
    PARTIAL_USABLE = "partial_usable"
    REJECTED_CORRUPTED = "rejected_corrupted"


class SentimentLabel(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class ConnectionStatusLabel(str, Enum):
    """How the call itself went, technically — distinct from CallQualityLabel,
    which is about the recording's clarity, not whether a real conversation
    happened."""

    CONNECTED = "connected"
    DROPPED_DURING_CALL = "dropped_during_call"
    DROPPED_AT_GREETING = "dropped_at_greeting"
    NO_ANSWER_BUSY = "no_answer_busy"
    VOICEMAIL_IVR_ONLY = "voicemail_ivr_only"
    SILENT_DEAD_AIR = "silent_dead_air"


class ScriptAdherenceLabel(str, Enum):
    FOLLOWED = "followed"
    PARTIAL = "partial"
    NOT_FOLLOWED = "not_followed"


class IssueMentionResult(BaseModel):
    category: str = Field(
        description=(
            "Reuse one of the existing category labels given in the prompt if it reasonably fits. "
            "Only write a new, short, specific label if this is a genuinely new kind of case that "
            "none of the existing ones cover. Never force-fit into a generic/'Other'-named category "
            "when a more specific one (existing or new) describes the case better."
        )
    )
    quote: str | None = Field(default=None, description="Short verbatim quote from the transcript, if available.")
    tags: list[str] = Field(
        default_factory=list,
        description=(
            "1-3 short, specific tags describing the concrete dimension of this issue (e.g. 'pricing', "
            "'response-time', 'spare-parts'), so it can be cross-referenced against other calls."
        ),
    )


# --- Per-node structured outputs ---------------------------------------------


class TranscriptionResult(BaseModel):
    """Output of the one node that receives the audio.

    Everything here is a judgement that genuinely needs to *hear* the
    recording — whether it was clear, whether anyone actually spoke, whether
    the agent said their name. Inferring these from a written transcript would
    be guesswork, which is why they live here and not in a cheap text node.
    """

    transcript: str = Field(description="Full verbatim transcript of the call audio, in the language(s) spoken.")
    transcript_english: str = Field(
        description=(
            "The same conversation rendered fully in English. For an all-English call this is the same "
            "text as `transcript`; for a Hindi/English code-mixed call it is a faithful English translation."
        )
    )
    language_code: str | None = Field(
        default=None, description="Best-guess BCP-47 language code of the call, e.g. 'en-IN' or 'hi-IN'."
    )
    agent_name: str | None = Field(
        default=None,
        description=(
            "The agent's name, ONLY if they explicitly state it during the call (typically the opening, "
            "e.g. 'This is Rahul from...'). Normalize to a clean proper-case name. Null if never stated — "
            "do not guess."
        ),
    )
    call_quality: CallQualityLabel = Field(
        description="Whether the audio is clear/usable, partially usable, or too corrupted/inaudible to analyze."
    )
    connection_status: ConnectionStatusLabel = Field(
        description=(
            "Whether the call itself connected and proceeded as a normal conversation, distinct from audio "
            "recording clarity (call_quality). Use 'connected' whenever a real conversation happened, even if "
            "it was later cut short by a network issue mid-call (use dropped_during_call for that case)."
        )
    )


class SentimentResult(BaseModel):
    """How the customer felt, and how satisfied they were."""

    sentiment: SentimentLabel
    sentiment_summary: str = Field(description="One sentence explaining the sentiment, e.g. what drove it.")
    satisfaction_rating: int = Field(
        ge=1, le=10, description="Your best ESTIMATE of overall customer satisfaction, 1 (worst) to 10 (best)."
    )
    customer_stated_rating: int | None = Field(
        default=None,
        ge=1,
        le=10,
        description=(
            "ONLY set this if the customer explicitly says an actual numeric rating out loud on the call "
            "(e.g. answering a spoken CSAT question with a number). Null if they never state one — do not infer "
            "or estimate a value here."
        ),
    )
    summary: str = Field(description="Two to three sentence summary of what happened on the call.")


class IssuesResult(BaseModel):
    """What the call was about — the ranked-table content on the dashboard."""

    negative_drivers: list[IssueMentionResult] = Field(default_factory=list)
    service_issues: list[IssueMentionResult] = Field(default_factory=list)
    positive_themes: list[IssueMentionResult] = Field(default_factory=list)


class ComplianceResult(BaseModel):
    """How the AGENT conducted the call, as opposed to what the customer said."""

    script_adherence: ScriptAdherenceLabel = Field(
        description="Whether the agent followed the standard call script (greeting, closing, standard flow)."
    )
    agent_compliance_issues: list[IssueMentionResult] = Field(
        default_factory=list,
        description="Specific agent-behavior issues: topic deviation, irrelevant talk, skipped script steps, etc.",
    )


# --- Assembled result --------------------------------------------------------


class CallAnalysisResult(BaseModel):
    """The union of every node's output — what gets persisted.

    Not a model prompt schema (each node has its own, above). Defaults exist on
    every field so that a KPI node which is disabled, or which hasn't been run
    yet, degrades to a neutral value instead of failing assembly.
    """

    transcript: str = ""
    transcript_english: str = ""
    language_code: str | None = None
    agent_name: str | None = None
    call_quality: CallQualityLabel = CallQualityLabel.GOOD_CLEAR
    connection_status: ConnectionStatusLabel = ConnectionStatusLabel.CONNECTED

    sentiment: SentimentLabel = SentimentLabel.NEUTRAL
    sentiment_summary: str | None = None
    satisfaction_rating: int = Field(default=5, ge=1, le=10)
    customer_stated_rating: int | None = None
    summary: str | None = None

    script_adherence: ScriptAdherenceLabel = ScriptAdherenceLabel.FOLLOWED

    negative_drivers: list[IssueMentionResult] = Field(default_factory=list)
    service_issues: list[IssueMentionResult] = Field(default_factory=list)
    positive_themes: list[IssueMentionResult] = Field(default_factory=list)
    agent_compliance_issues: list[IssueMentionResult] = Field(default_factory=list)

    # Which KPI node version produced each part of this row, e.g.
    # {"transcription": "v1", "sentiment": "v1"}. Persisted with the raw output
    # so a row can always be traced back to the prompt version behind it — and
    # so a missing key is visibly "this KPI didn't run" rather than silently
    # indistinguishable from "this KPI found nothing".
    kpi_versions: dict[str, str] = Field(default_factory=dict)
