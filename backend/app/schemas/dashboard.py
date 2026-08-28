from pydantic import BaseModel


class SliceOut(BaseModel):
    label: str
    count: int
    percentage: float


class DashboardSummaryOut(BaseModel):
    range: str
    total_calls: int
    usable_calls: int
    call_quality: list[SliceOut]
    sentiment: list[SliceOut]
    satisfaction_bands: list[SliceOut]
    average_rating: float | None
    top_negative_drivers: list[SliceOut]
    top_service_issues: list[SliceOut]
    top_positive_themes: list[SliceOut]
