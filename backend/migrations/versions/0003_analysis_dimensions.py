"""analysis dimensions: agent identification, stated rating, connection
status, script adherence, agent_compliance mentions, mention tags

Revision ID: 0003_analysis_dimensions
Revises: 0002_scheduler_config
Create Date: 2026-09-02

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_analysis_dimensions"
down_revision: str | None = "0002_scheduler_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection_status = postgresql.ENUM(
        "connected",
        "dropped_during_call",
        "dropped_at_greeting",
        "no_answer_busy",
        "voicemail_ivr_only",
        "silent_dead_air",
        name="connection_status",
    )
    connection_status.create(op.get_bind())

    script_adherence = postgresql.ENUM(
        "followed", "partial", "not_followed", name="script_adherence"
    )
    script_adherence.create(op.get_bind())

    op.add_column("call_analysis", sa.Column("customer_stated_rating", sa.Integer(), nullable=True))
    op.add_column("call_analysis", sa.Column("agent_name", sa.String(length=255), nullable=True))
    op.create_index("ix_call_analysis_agent_name", "call_analysis", ["agent_name"])
    op.add_column(
        "call_analysis",
        sa.Column(
            "connection_status",
            connection_status,
            nullable=False,
            server_default="connected",
        ),
    )
    op.add_column(
        "call_analysis",
        sa.Column(
            "script_adherence",
            script_adherence,
            nullable=False,
            server_default="followed",
        ),
    )

    op.add_column(
        "issue_mentions",
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String(length=64)),
            nullable=False,
            server_default="{}",
        ),
    )

    # New mention_type value. Postgres requires ALTER TYPE ... ADD VALUE to run
    # outside a transaction block (mirrors the enum-creation approach used in
    # 0001_initial_schema.py for the same enum).
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE mention_type ADD VALUE IF NOT EXISTS 'agent_compliance'")


def downgrade() -> None:
    op.drop_column("issue_mentions", "tags")
    op.drop_column("call_analysis", "script_adherence")
    op.drop_column("call_analysis", "connection_status")
    op.drop_index("ix_call_analysis_agent_name", table_name="call_analysis")
    op.drop_column("call_analysis", "agent_name")
    op.drop_column("call_analysis", "customer_stated_rating")
    sa.Enum(name="script_adherence").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="connection_status").drop(op.get_bind(), checkfirst=True)
    # Postgres cannot remove a value from an enum type, so 'agent_compliance'
    # remains in mention_type after downgrade — harmless (unused), matches how
    # the rest of this codebase treats enum values as append-only.
