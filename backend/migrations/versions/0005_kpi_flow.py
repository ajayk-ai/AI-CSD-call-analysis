"""KPI-node flow: English transcript + per-KPI enable/disable config

The analysis is now produced by several independent LangGraph nodes (see
app/pipeline/kpi_registry.py) instead of one combined model call:

* `transcripts.english_text` holds the English rendering the KPI nodes read,
  while `transcripts.text` keeps the verbatim as-spoken record.
* `kpi_config` is a sparse override table — a row exists only where someone has
  toggled a KPI away from its registry default, so adding a new KPI spec
  doesn't require a data migration.

Note LangGraph's own `checkpoints*` tables are NOT created here: the library
manages and versions them itself via `PostgresSaver.setup()`, and owning them
in Alembic would fight that.

Revision ID: 0005_kpi_flow
Revises: 0004_synthetic_data_flag
Create Date: 2026-09-03

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_kpi_flow"
down_revision: str | None = "0004_synthetic_data_flag"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("transcripts", sa.Column("english_text", sa.Text(), nullable=True))

    op.create_table(
        "kpi_config",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("key", name="uq_kpi_config_key"),
    )


def downgrade() -> None:
    op.drop_table("kpi_config")
    op.drop_column("transcripts", "english_text")
