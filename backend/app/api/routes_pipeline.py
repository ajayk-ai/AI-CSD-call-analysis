from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.pipeline.ingest_pipeline import PipelineRunSummary, run_pipeline

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post("/run", response_model=PipelineRunSummary)
def trigger_pipeline_run(db: Session = Depends(get_db)) -> PipelineRunSummary:
    """Manually triggered from the dashboard's "Run Analysis" button.

    Scans the configured GCS bucket, transcribes and analyzes any call that
    isn't already ANALYZED, and returns a summary. Runs synchronously — for
    a large backlog this can take a while (each call is one Speech-to-Text
    long-running op plus one Gemini call), which is fine for the current
    "click a button on my local machine" deployment model.
    """
    return run_pipeline(db)
