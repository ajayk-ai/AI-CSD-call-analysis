"""Which KPI nodes are switched on.

The registry (app/pipeline/kpi_registry.py) says what KPIs exist and what each
one defaults to; the `kpi_config` table records only where the user has
overridden that. Reading is therefore "defaults, overlaid with overrides",
which means adding a new spec needs no migration and no backfill — it simply
appears, at its own default.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import KpiConfig
from app.pipeline.kpi_registry import KPI_SPECS, SPECS_BY_KEY, KpiSpec
from app.services import llm_service


def _overrides(db: Session) -> dict[str, bool]:
    return dict(db.execute(select(KpiConfig.key, KpiConfig.enabled)).all())


def enabled_keys(db: Session) -> frozenset[str]:
    """The set the graph is built from. `required` specs are always included —
    every other node reads the transcription node's output, so switching it off
    would leave nothing to analyze."""
    overrides = _overrides(db)
    return frozenset(
        spec.key
        for spec in KPI_SPECS
        if spec.required or overrides.get(spec.key, spec.default_enabled)
    )


@dataclass(frozen=True)
class KpiStatus:
    spec: KpiSpec
    enabled: bool


def list_status(db: Session) -> list[KpiStatus]:
    overrides = _overrides(db)
    return [
        KpiStatus(spec=spec, enabled=spec.required or overrides.get(spec.key, spec.default_enabled))
        for spec in KPI_SPECS
    ]


def set_enabled(db: Session, key: str, enabled: bool) -> KpiStatus:
    spec = SPECS_BY_KEY.get(key)
    if spec is None:
        raise KeyError(key)
    if spec.required and not enabled:
        raise ValueError(f"{spec.label} is required and cannot be disabled.")

    row = db.execute(select(KpiConfig).where(KpiConfig.key == key)).scalar_one_or_none()
    if row is None:
        db.add(KpiConfig(key=key, enabled=enabled))
    else:
        row.enabled = enabled
    db.commit()
    return KpiStatus(spec=spec, enabled=enabled)


def model_for(spec: KpiSpec) -> str:
    """The model this spec will actually call, resolved from settings — shown
    in Admin so the tier isn't just an abstract label."""
    return llm_service.model_name_for(spec.tier)
