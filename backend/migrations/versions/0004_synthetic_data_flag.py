"""synthetic data flag: lets the Admin tab seed/clear cost-free dummy calls
for QA without touching real data or spending on Gemini calls

Revision ID: 0004_synthetic_data_flag
Revises: 0003_analysis_dimensions
Create Date: 2026-09-03

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_synthetic_data_flag"
down_revision: str | None = "0003_analysis_dimensions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "calls",
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_calls_is_synthetic", "calls", ["is_synthetic"])


def downgrade() -> None:
    op.drop_index("ix_calls_is_synthetic", table_name="calls")
    op.drop_column("calls", "is_synthetic")
