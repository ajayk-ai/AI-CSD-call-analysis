from enum import Enum

from pydantic import BaseModel, Field

# These category lists mirror the taxonomy already shown in the frontend
# dashboard (frontend/src/data/mockData.ts) so real aggregated data slots
# straight into the same ranked tables without a relabeling step.

NEGATIVE_DRIVER_CATEGORIES = [
    "Delay in Service Response",
    "Repeat Issue After Service",
    "Spare Parts Delay",
    "Poor Follow-up / No Updates",
    "Installation / Delivery Issues",
    "Other Issues (AC, Electrical, GPS, etc.)",
]

SERVICE_ISSUE_CATEGORIES = [
    "Hydraulic Issues",
    "Oil Leakage",
    "Transmission Issues",
    "AC / Cooling Problems",
    "Electrical / Wiring / GPS Issues",
    "Pipe / Hose Leakage / Burst",
    "Engine Performance Issues",
    "Other Mechanical Issues",
]

POSITIVE_THEME_CATEGORIES = [
    "Technician Behavior",
    "Dealer Support",
    "Problem Resolved",
    "Communication",
    "Overall Satisfaction / Trust",
]


class CallQualityLabel(str, Enum):
    GOOD_CLEAR = "good_clear"
    PARTIAL_USABLE = "partial_usable"
    REJECTED_CORRUPTED = "rejected_corrupted"


class SentimentLabel(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class IssueMentionResult(BaseModel):
    category: str = Field(description="Must be one of the provided category labels for this mention type.")
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
