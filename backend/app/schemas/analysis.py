from enum import Enum

from pydantic import BaseModel, Field

# Category taxonomy (negative drivers, service/machine issues, positive
# themes) is NOT hardcoded here — it lives in the `mention_categories` table
# and grows over time via app/services/category_service.py. The initial seed
# list (mirroring frontend/src/data/mockData.ts) is in the first Alembic
# migration; from there, any new category Gemini has to invent for a call
# gets persisted so it's offered as a reusable option on the next call. See
# category_service.get_known_categories / register_new_categories.


class CallQualityLabel(str, Enum):
    GOOD_CLEAR = "good_clear"
    PARTIAL_USABLE = "partial_usable"
    REJECTED_CORRUPTED = "rejected_corrupted"


class SentimentLabel(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class IssueMentionResult(BaseModel):
    category: str = Field(
        description=(
            "Reuse one of the existing category labels given in the prompt if it reasonably fits. "
            "Only write a new, short, specific label if this is a genuinely new kind of case that "
            "none of the existing ones cover."
        )
    )
    quote: str | None = Field(default=None, description="Short verbatim quote from the transcript, if available.")


class CallAnalysisResult(BaseModel):
    transcript: str = Field(description="Full verbatim transcript of the call audio.")
    language_code: str | None = Field(
        default=None, description="Best-guess BCP-47 language code of the call, e.g. 'en-IN' or 'hi-IN'."
    )
    call_quality: CallQualityLabel = Field(
        description="Whether the audio is clear/usable, partially usable, or too corrupted/inaudible to analyze."
    )
    sentiment: SentimentLabel
    sentiment_summary: str = Field(description="One sentence explaining the sentiment, e.g. what drove it.")
    satisfaction_rating: int = Field(ge=1, le=10, description="Overall customer satisfaction, 1 (worst) to 10 (best).")
    summary: str = Field(description="Two to three sentence summary of what happened on the call.")
    negative_drivers: list[IssueMentionResult] = Field(default_factory=list)
    service_issues: list[IssueMentionResult] = Field(default_factory=list)
    positive_themes: list[IssueMentionResult] = Field(default_factory=list)
