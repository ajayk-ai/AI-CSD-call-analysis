"""initial schema: calls, transcripts, call_analysis, issue_mentions

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-28

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("gcs_uri", sa.String(length=1024), nullable=False),
        sa.Column("bucket_name", sa.String(length=255), nullable=False),
        sa.Column("object_name", sa.String(length=1024), nullable=False),
        sa.Column("team_code", sa.String(length=64), nullable=True),
        sa.Column("recording_date", sa.String(length=16), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "analyzing", "analyzed", "failed", name="call_status"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("gcs_uri", name="uq_calls_gcs_uri"),
    )
    op.create_index("ix_calls_created_at", "calls", ["created_at"])
    op.create_index("ix_calls_status", "calls", ["status"])

    op.create_table(
        "transcripts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "call_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calls.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("language_code", sa.String(length=16), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "call_analysis",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "call_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calls.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "call_quality",
            sa.Enum("good_clear", "partial_usable", "rejected_corrupted", name="call_quality"),
            nullable=False,
        ),
        sa.Column("sentiment", sa.Enum("positive", "neutral", "negative", name="sentiment"), nullable=False),
        sa.Column("sentiment_summary", sa.Text(), nullable=True),
        sa.Column("satisfaction_rating", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("raw_model_output", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "issue_mentions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "call_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mention_type",
            sa.Enum("negative_driver", "service_issue", "positive_theme", name="mention_type"),
            nullable=False,
        ),
        sa.Column("category", sa.String(length=255), nullable=False),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_issue_mentions_call_id", "issue_mentions", ["call_id"])
    op.create_index("ix_issue_mentions_type_category", "issue_mentions", ["mention_type", "category"])


def downgrade() -> None:
    op.drop_table("issue_mentions")
    op.drop_table("call_analysis")
    op.drop_table("transcripts")
    op.drop_table("calls")
    for enum_name in ("call_status", "call_quality", "sentiment", "mention_type"):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
