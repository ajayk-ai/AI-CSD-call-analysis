from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class IssueMentionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mention_type: str
    category: str
    quote: str | None
    tags: list[str] = []


class CallAnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    call_quality: str
    connection_status: str
    sentiment: str
    sentiment_summary: str | None
    satisfaction_rating: int
    customer_stated_rating: int | None
    agent_name: str | None
    script_adherence: str
    summary: str | None


class TranscriptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    text: str
    # The English rendering. Null on rows analyzed before the translation step
    # existed — the UI only offers the EN/Original toggle when it's present and
    # actually differs from `text`.
    english_text: str | None = None
    language_code: str | None
    confidence: float | None


class CallListItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    object_name: str
    team_code: str | None
    recording_date: str | None
    status: str
    is_synthetic: bool
    created_at: datetime
    analysis: CallAnalysisOut | None = None


class CallDetailOut(CallListItemOut):
    transcript: TranscriptOut | None = None
    mentions: list[IssueMentionOut] = []
