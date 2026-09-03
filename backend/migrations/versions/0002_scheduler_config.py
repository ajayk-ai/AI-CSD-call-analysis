"""scheduler_config: persisted settings for the daily auto-analysis job

Revision ID: 0002_scheduler_config
Revises: 0001_initial_schema
Create Date: 2026-08-31

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_scheduler_config"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scheduler_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("run_hour", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("run_minute", sa.Integer(), nullable=False, server_default="0"),
        # null = fall back to PIPELINE_RUN_LIMIT at run time; 0 = no cap.
        sa.Column("run_limit", sa.Integer(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_status", sa.String(length=32), nullable=True),
        sa.Column("last_run_summary", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("scheduler_config")
