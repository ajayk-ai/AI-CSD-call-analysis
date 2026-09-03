import enum
import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _pg_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    """Persist the member's `.value`, not its `.name`.

    SQLAlchemy's Enum defaults to storing the member NAME ("GOOD_CLEAR"), but
    every Postgres enum type in 0001_initial_schema was created with lowercase
    labels ("good_clear") — i.e. the `.value`. Without values_callable the two
    disagree and every insert dies with
    `invalid input value for enum call_quality: "GOOD_CLEAR"`.
    """
    return Enum(enum_cls, name=name, values_callable=lambda cls: [m.value for m in cls])


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
    AGENT_COMPLIANCE = "agent_compliance"


class ConnectionStatus(str, enum.Enum):
    """How the call itself went, technically — distinct from `CallQuality`,
    which is about the *recording's* clarity. A call can be perfectly clear
    audio (call_quality=good_clear) and still never become a real
    conversation (connection_status=no_answer_busy)."""

    CONNECTED = "connected"
    DROPPED_DURING_CALL = "dropped_during_call"
    DROPPED_AT_GREETING = "dropped_at_greeting"
    NO_ANSWER_BUSY = "no_answer_busy"
    VOICEMAIL_IVR_ONLY = "voicemail_ivr_only"
    SILENT_DEAD_AIR = "silent_dead_air"


class ScriptAdherence(str, enum.Enum):
    FOLLOWED = "followed"
    PARTIAL = "partial"
    NOT_FOLLOWED = "not_followed"


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
        _pg_enum(CallStatus, "call_status"), nullable=False, default=CallStatus.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # True for rows created by synthetic_data_service, never by the real
    # ingest pipeline. Lets the Admin tab seed cost-free dummy data (no GCS,
    # no Gemini calls) to QA dashboard/KPI changes, and cleanly filter it out
    # of — or into — any view via the data_mode query param.
    is_synthetic: Mapped[bool] = mapped_column(nullable=False, default=False, index=True)

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


# The bucket's `team_code` ("BMCSTTA", "BMCSTCE", parsed from
# recordings/<date>/<team_code>/<file>) encodes the plant as its last two
# letters — TA / CE. There's no separate "plant" column: every place that
# needs to read or filter by plant must derive it from this SAME expression,
# or the two could disagree.
PLANT_SUFFIX_LEN = 2
plant_expr = func.upper(func.right(Call.team_code, PLANT_SUFFIX_LEN))


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # Verbatim, as spoken — a code-mixed Hindi/English call is stored the way
    # it was said, because this is the record of what happened and quotes have
    # to be quotable.
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # The same conversation in English. This is what every KPI node reads (see
    # app/pipeline/kpi_registry.py), so the analysis never has to reason across
    # a code-mixed text, and what an English-speaking reviewer reads on the
    # Calls page. Nullable: rows analyzed before the translation step existed
    # have only `text`.
    english_text: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    call_quality: Mapped[CallQuality] = mapped_column(_pg_enum(CallQuality, "call_quality"), nullable=False)
    sentiment: Mapped[Sentiment] = mapped_column(_pg_enum(Sentiment, "sentiment"), nullable=False)
    sentiment_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 1-10, AI-estimated — matches the "Customer Satisfaction Rating" bands in
    # the dashboard. See customer_stated_rating for the customer's own number.
    satisfaction_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    # 1-10, ONLY set when the customer explicitly said a number out loud on the
    # call (e.g. answering a spoken CSAT question). Null = never stated — the
    # dashboard's "Actual" rating view buckets those as "Not Given" rather than
    # falling back to the AI estimate.
    customer_stated_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Extracted from the transcript's self-identification (e.g. "This is Rahul
    # from..."); null when the agent never states a name. Indexed — the Calls
    # page and the per-agent dashboard breakdown both filter/group on this.
    agent_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    connection_status: Mapped[ConnectionStatus] = mapped_column(
        _pg_enum(ConnectionStatus, "connection_status"), nullable=False, default=ConnectionStatus.CONNECTED
    )
    script_adherence: Mapped[ScriptAdherence] = mapped_column(
        _pg_enum(ScriptAdherence, "script_adherence"), nullable=False, default=ScriptAdherence.FOLLOWED
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Full raw model response, kept for audit / re-parsing without another API call
    raw_model_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    call: Mapped["Call"] = relationship(back_populates="analysis")


class MentionCategory(Base):
    """The known category taxonomy per mention type — seeded with an initial
    set, but not fixed: `category_service.register_new_categories` adds a row
    here whenever Gemini classifies a call into a category that doesn't
    already exist, so the list grows to fit new kinds of cases as they show
    up instead of forcing everything into a stale fixed list."""

    __tablename__ = "mention_categories"
    __table_args__ = (UniqueConstraint("mention_type", "name", name="uq_mention_categories_type_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mention_type: Mapped[MentionType] = mapped_column(_pg_enum(MentionType, "mention_type"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_seed: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SchedulerConfig(Base):
    """Single-row table holding the daily auto-analysis schedule. Read/written
    by app/services/scheduler_service.py; there is exactly one row, fetched
    with `.limit(1)` rather than a fixed id."""

    __tablename__ = "scheduler_config"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    run_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    run_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # None = fall back to settings.pipeline_run_limit at run time; 0 = no cap.
    run_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_run_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class KpiConfig(Base):
    """Which analysis KPI nodes are switched on, as overrides.

    Sparse on purpose: a row exists only for a KPI whose enabled state differs
    from its `KpiSpec.default_enabled` in app/pipeline/kpi_registry.py. That
    way adding a new KPI spec needs no data migration, and the registry stays
    the single source of truth for what KPIs exist at all — this table only
    records what the user has since decided about them.
    """

    __tablename__ = "kpi_config"
    __table_args__ = (UniqueConstraint("key", name="uq_kpi_config_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IssueMention(Base):
    """One row per (call, category) hit — negative driver, service/machine issue,
    or positive theme. Aggregating COUNT(*) GROUP BY category reproduces the
    dashboard's ranked tables directly from real data."""

    __tablename__ = "issue_mentions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False
    )
    mention_type: Mapped[MentionType] = mapped_column(_pg_enum(MentionType, "mention_type"), nullable=False)
    category: Mapped[str] = mapped_column(String(255), nullable=False)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Short, specific descriptors beyond `category` (e.g. ["pricing",
    # "spare-parts"]) — freeform, not a converging taxonomy like `category`.
    # Lets the same mention be sliced along multiple concrete dimensions, and
    # is what the cross-signal insight mining correlates on.
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(64)), nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    call: Mapped["Call"] = relationship(back_populates="mentions")
