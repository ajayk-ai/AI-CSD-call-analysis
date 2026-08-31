from pydantic import BaseModel


class PipelineStatusOut(BaseModel):
    """Ingest progress, counted from the `calls` table alone."""

    total_calls: int
    analyzed: int
    failed: int
    # PENDING + ANALYZING + FAILED — i.e. what the next run would retry, out of
    # the recordings already discovered. Excludes bucket objects never listed.
    not_yet_analyzed: int
    # PIPELINE_RUN_LIMIT, so the UI can label the button with the batch size
    # it will actually trigger. 0 = no cap.
    default_run_limit: int
