from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class IssueMentionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mention_type: str
    category: str
    quote: str | None


class CallAnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    call_quality: str
    sentiment: str
    sentiment_summary: str | None
    satisfaction_rating: int
    summary: str | None


class TranscriptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    text: str
    language_code: str | None
    confidence: float | None


class CallListItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    object_name: str
    team_code: str | None
    recording_date: str | None
    status: str
    created_at: datetime
    analysis: CallAnalysisOut | None = None


class CallDetailOut(CallListItemOut):
    transcript: TranscriptOut | None = None
    mentions: list[IssueMentionOut] = []
