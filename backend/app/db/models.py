import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CallStatus(str, enum.Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    FAILED = "failed"


class CallQuality(str, enum.Enum):
    GOOD_CLEAR = "good_clear"
    PARTIAL_USABLE = "partial_usable"
    REJECTED_CORRUPTED = "rejected_corrupted"


class Sentiment(str, enum.Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class MentionType(str, enum.Enum):
    NEGATIVE_DRIVER = "negative_driver"
    SERVICE_ISSUE = "service_issue"
    POSITIVE_THEME = "positive_theme"


class Call(Base):
    __tablename__ = "calls"
    __table_args__ = (UniqueConstraint("gcs_uri", name="uq_calls_gcs_uri"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gcs_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    bucket_name: Mapped[str] = mapped_column(String(255), nullable=False)
    object_name: Mapped[str] = mapped_column(String(1024), nullable=False)
    # e.g. "BMCSTTA" parsed from the recordings/<date>/<team>/ path
    team_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recording_date: Mapped[str | None] = mapped_column(String(16), nullable=True)  # "2026-08-24"
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[CallStatus] = mapped_column(
        Enum(CallStatus, name="call_status"), nullable=False, default=CallStatus.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    transcript: Mapped["Transcript | None"] = relationship(
        back_populates="call", uselist=False, cascade="all, delete-orphan"
    )
    analysis: Mapped["CallAnalysis | None"] = relationship(
        back_populates="call", uselist=False, cascade="all, delete-orphan"
    )
    mentions: Mapped[list["IssueMention"]] = relationship(
        back_populates="call", cascade="all, delete-orphan"
    )


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    language_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    call: Mapped["Call"] = relationship(back_populates="transcript")


class CallAnalysis(Base):
    __tablename__ = "call_analysis"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    call_quality: Mapped[CallQuality] = mapped_column(Enum(CallQuality, name="call_quality"), nullable=False)
    sentiment: Mapped[Sentiment] = mapped_column(Enum(Sentiment, name="sentiment"), nullable=False)
    sentiment_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 1-10, matches the "Customer Satisfaction Rating" bands in the dashboard
    satisfaction_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Full raw model response, kept for audit / re-parsing without another API call
    raw_model_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    call: Mapped["Call"] = relationship(back_populates="analysis")


class IssueMention(Base):
    """One row per (call, category) hit — negative driver, service/machine issue,
    or positive theme. Aggregating COUNT(*) GROUP BY category reproduces the
    dashboard's ranked tables directly from real data."""

    __tablename__ = "issue_mentions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False
    )
    mention_type: Mapped[MentionType] = mapped_column(Enum(MentionType, name="mention_type"), nullable=False)
    category: Mapped[str] = mapped_column(String(255), nullable=False)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    call: Mapped["Call"] = relationship(back_populates="mentions")
