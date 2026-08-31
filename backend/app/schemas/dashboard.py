from pydantic import BaseModel


class SliceOut(BaseModel):
    """One row/segment of a breakdown.

    `key` is the stable machine value (an enum value like "good_clear", or a
    category name); `label` is what the dashboard prints. The frontend keys its
    colors and icons off `key` so a wording change here can't silently break
    the palette.
    """

    key: str
    label: str
    count: int
    percentage: float
    # A representative verbatim quote, for the "Example from Transcripts"
    # column. None when the model attached no quote to any mention.
    example: str | None = None


class MonthlyAverageOut(BaseModel):
    # e.g. "MAY AVG" — pre-formatted for the chart's x-axis.
    month: str
    avg_rating: float
    call_count: int


class DailyRatingOut(BaseModel):
    day: int  # day of month, 1-31
    rating: float
    call_count: int


class DashboardPlantsOut(BaseModel):
    # Every plant code seen across ALL calls, regardless of the currently
    # selected time range or plant filter — so the filter's own option list
    # doesn't shrink just because "1D" happens to have no calls from one plant.
    plants: list[str]


class DashboardSummaryOut(BaseModel):
    range: str
    # Echoes the request's `plant` filter (None = all plants combined).
    plant: str | None
    # Every call in range, including ones too corrupt to analyze.
    total_calls: int
    # Calls with an analysis row of any kind.
    analyzed_calls: int
    # Analyzed calls that were actually intelligible (quality != rejected).
    # This is the denominator the dashboard's "Based on N Usable Calls"
    # subtitles refer to.
    usable_calls: int
    average_rating: float | None

    call_quality: list[SliceOut]
    sentiment: list[SliceOut]
    satisfaction_bands: list[SliceOut]

    top_negative_drivers: list[SliceOut]
    top_service_issues: list[SliceOut]
    top_positive_themes: list[SliceOut]

    # The trend card spans its own fixed windows (the latest month present in
    # the data, and the three months before it), so these are deliberately NOT
    # filtered by `range` — otherwise picking "1D" would empty the chart.
    current_month_label: str | None
    monthly_averages: list[MonthlyAverageOut]
    daily_ratings: list[DailyRatingOut]
