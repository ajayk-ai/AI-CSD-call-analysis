"""Retire the two generic "Other ..." seed categories.

These were seeded in 0001 and turned out to be actively harmful, for a reason
visible in the data:

    Other Issues (AC, Electrical, GPS, etc.)   7 calls
    Other Mechanical Issues                    4 calls
    AC / Cooling Problems                      0 calls   <- never once chosen
    Electrical / Wiring / GPS Issues           0 calls   <- never once chosen
    Engine Performance Issues                  0 calls   <- never once chosen
    Transmission Issues                        0 calls   <- never once chosen

The generic bucket's own NAME enumerates the specific categories sitting next
to it in the list, so when the model met an AC fault, "Other Issues (AC,
Electrical, GPS, etc.)" looked like the better match — and the specific
categories were never selected at all. No amount of prompt wording beats a
label that advertises itself as the right answer for the exact case in hand;
the fix is to stop offering it.

Removing these rows takes them out of the list fed into the analysis prompt
(category_service.get_known_categories), so future runs must pick a specific
category or mint a new specific one.

EXISTING mentions still referencing these labels are deliberately left alone —
`issue_mentions.category` is free text, so nothing breaks, and guessing a
replacement from a keyword match here would be inventing data. They are
re-classified properly by re-running with the `issues` KPI at its new version,
which reads the transcript again for one cheap text call per call and no audio.

Revision ID: 0006_retire_generic_categories
Revises: 0005_kpi_flow
Create Date: 2026-09-03

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_retire_generic_categories"
down_revision: str | None = "0005_kpi_flow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GENERIC = [
    ("negative_driver", "Other Issues (AC, Electrical, GPS, etc.)"),
    ("service_issue", "Other Issues (AC, Electrical, GPS, etc.)"),
    ("service_issue", "Other Mechanical Issues"),
]


def upgrade() -> None:
    connection = op.get_bind()
    for mention_type, name in _GENERIC:
        connection.execute(
            sa.text(
                "DELETE FROM mention_categories "
                "WHERE mention_type = CAST(:t AS mention_type) AND name = :n"
            ),
            {"t": mention_type, "n": name},
        )


def downgrade() -> None:
    connection = op.get_bind()
    for mention_type, name in _GENERIC:
        connection.execute(
            sa.text(
                "INSERT INTO mention_categories (id, mention_type, name, is_seed, created_at) "
                "VALUES (gen_random_uuid(), CAST(:t AS mention_type), :n, true, now()) "
                "ON CONFLICT DO NOTHING"
            ),
            {"t": mention_type, "n": name},
        )
