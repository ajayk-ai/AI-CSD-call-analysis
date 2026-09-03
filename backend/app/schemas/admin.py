from datetime import datetime

from pydantic import BaseModel, Field


class SchedulerConfigOut(BaseModel):
    enabled: bool
    run_hour: int
    run_minute: int
    # None = uses PIPELINE_RUN_LIMIT; 0 = no cap.
    run_limit: int | None
    last_run_at: datetime | None
    last_run_status: str | None
    last_run_summary: str | None

    model_config = {"from_attributes": True}


class SchedulerConfigUpdate(BaseModel):
    enabled: bool
    run_hour: int = Field(ge=0, le=23)
    run_minute: int = Field(ge=0, le=59)
    run_limit: int | None = Field(default=None, ge=0)


class SyntheticDataStatusOut(BaseModel):
    live_calls: int
    synthetic_calls: int


class KpiNodeOut(BaseModel):
    """One node of the analysis flow, as the Admin page shows it."""

    key: str
    label: str
    description: str
    version: str
    # "transcription" (strong model, reads audio) or "extraction" (cheap model,
    # reads the transcript text).
    tier: str
    # The model this tier actually resolves to right now, so the page shows
    # what will run rather than an abstract tier name.
    model: str
    enabled: bool
    # Required nodes can't be switched off — everything else reads their output.
    required: bool


class KpiNodeUpdate(BaseModel):
    enabled: bool
