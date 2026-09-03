from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.admin import (
    KpiNodeOut,
    KpiNodeUpdate,
    SchedulerConfigOut,
    SchedulerConfigUpdate,
    SyntheticDataStatusOut,
)
from app.services import kpi_config_service, scheduler_service, synthetic_data_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/schedule", response_model=SchedulerConfigOut)
def get_schedule(db: Session = Depends(get_db)) -> SchedulerConfigOut:
    return SchedulerConfigOut.model_validate(scheduler_service.get_config(db))


@router.put("/schedule", response_model=SchedulerConfigOut)
def update_schedule(
    update: SchedulerConfigUpdate, db: Session = Depends(get_db)
) -> SchedulerConfigOut:
    config = scheduler_service.update_config(
        db,
        enabled=update.enabled,
        run_hour=update.run_hour,
        run_minute=update.run_minute,
        run_limit=update.run_limit,
    )
    return SchedulerConfigOut.model_validate(config)


@router.get("/synthetic-data", response_model=SyntheticDataStatusOut)
def get_synthetic_data_status(db: Session = Depends(get_db)) -> SyntheticDataStatusOut:
    live, synthetic = synthetic_data_service.counts(db)
    return SyntheticDataStatusOut(live_calls=live, synthetic_calls=synthetic)


@router.post("/synthetic-data", response_model=SyntheticDataStatusOut)
def generate_synthetic_data(
    db: Session = Depends(get_db),
    count: int = Query(50, ge=1, le=1000, description="How many dummy calls to generate."),
) -> SyntheticDataStatusOut:
    """Seeds `count` fake calls with realistic, varied values across every
    analysis dimension — entirely in-process, no GCS/Gemini calls, so this
    costs nothing. For previewing dashboard/KPI changes with `data_mode=
    synthetic` or `all` without touching real data or spending on the real
    pipeline."""
    synthetic_data_service.generate(db, count)
    live, synthetic = synthetic_data_service.counts(db)
    return SyntheticDataStatusOut(live_calls=live, synthetic_calls=synthetic)


@router.delete("/synthetic-data", response_model=SyntheticDataStatusOut)
def clear_synthetic_data(db: Session = Depends(get_db)) -> SyntheticDataStatusOut:
    synthetic_data_service.clear(db)
    live, synthetic = synthetic_data_service.counts(db)
    return SyntheticDataStatusOut(live_calls=live, synthetic_calls=synthetic)


def _to_out(status: kpi_config_service.KpiStatus) -> KpiNodeOut:
    spec = status.spec
    return KpiNodeOut(
        key=spec.key,
        label=spec.label,
        description=spec.description,
        version=spec.version,
        tier=spec.tier.value,
        model=kpi_config_service.model_for(spec),
        enabled=status.enabled,
        required=spec.required,
    )


@router.get("/kpis", response_model=list[KpiNodeOut])
def list_kpis(db: Session = Depends(get_db)) -> list[KpiNodeOut]:
    """The analysis flow as it will next run — one entry per node in
    app/pipeline/kpi_registry.py, in graph order."""
    return [_to_out(status) for status in kpi_config_service.list_status(db)]


@router.put("/kpis/{key}", response_model=KpiNodeOut)
def update_kpi(key: str, update: KpiNodeUpdate, db: Session = Depends(get_db)) -> KpiNodeOut:
    """Switches one node on or off for the next run.

    Enabling a node does not itself analyze anything: it takes effect on the
    next pipeline run, and on already-analyzed calls only when that run is
    forced. That run is cheap — the transcript comes from the checkpoint, so
    only the newly-enabled node actually calls a model.
    """
    try:
        return _to_out(kpi_config_service.set_enabled(db, key, update.enabled))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No such KPI: {key}") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
