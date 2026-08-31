from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Call, CallStatus
from app.db.session import get_db
from app.pipeline.ingest_pipeline import PipelineRunSummary, run_pipeline
from app.schemas.pipeline import PipelineStatusOut

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post("/run", response_model=PipelineRunSummary)
def trigger_pipeline_run(
    db: Session = Depends(get_db),
    limit: int | None = Query(
        None,
        ge=0,
        description=(
            "Maximum recordings to send to Gemini in this run. Omit to use "
            "PIPELINE_RUN_LIMIT from the environment; 0 means no cap. "
            "Prescreened-out objects are free and do not count against it."
        ),
    ),
) -> PipelineRunSummary:
    """Manually triggered from the dashboard's "Run Analysis" button.

    Scans the configured GCS bucket, transcribes and analyzes any call that
    isn't already ANALYZED, and returns a summary. Runs synchronously — one
    Gemini call per recording, which at the default limit is a few seconds
    per click and fine for this "run it on my own machine" deployment.

    Safe to call repeatedly: analyzed calls are skipped, so each click picks
    up where the last one stopped.
    """
    return run_pipeline(db, limit=limit)


@router.get("/status", response_model=PipelineStatusOut)
def get_pipeline_status(db: Session = Depends(get_db)) -> PipelineStatusOut:
    """Ingest state straight from the database — no GCS listing, so the
    dashboard can poll it freely without touching the network.

    `not_yet_analyzed` only counts recordings already discovered by a previous
    run; recordings sitting in the bucket that have never been listed are not
    known here and show up the next time the pipeline runs.
    """
    rows = db.execute(select(Call.status, func.count()).group_by(Call.status)).all()
    counts = {status: n for status, n in rows}

    return PipelineStatusOut(
        total_calls=sum(counts.values()),
        analyzed=counts.get(CallStatus.ANALYZED, 0),
        failed=counts.get(CallStatus.FAILED, 0),
        not_yet_analyzed=sum(
            n for status, n in counts.items() if status is not CallStatus.ANALYZED
        ),
        default_run_limit=get_settings().pipeline_run_limit,
    )
