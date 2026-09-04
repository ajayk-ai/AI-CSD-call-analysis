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
    # A handful of representative tags seen on mentions in this slice (see
    # IssueMention.tags) — lets the ranked issue tables surface the concrete
    # dimension of an issue (e.g. "pricing") without changing its category.
    tags: list[str] = []

    # --- Issue-category rows only (null on enum breakdowns like sentiment) ---
    # How many calls raised this category as praise vs. as a problem. The same
    # category legitimately lands on both sides — "Installation / Delivery" is
    # praised on some calls and complained about on others — and an issue table
    # that hides that is telling half the story.
    positive_calls: int | None = None
    negative_calls: int | None = None
    # Of the calls that raised this category at all, the share that raised it
    # as a problem (0-100). None when nothing raised it.
    negative_share: float | None = None


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


class DashboardAgentsOut(BaseModel):
    # Every distinct agent_name seen across ALL calls, unfiltered by range or
    # plant — same "don't shrink the filter's own option list" rationale as
    # DashboardPlantsOut.
    agents: list[str]


class AgentStatsOut(BaseModel):
    """Per-agent rollup, grouped by CallAnalysis.agent_name. Calls where the
    model never caught an agent name roll into agent_name="Unassigned" rather
    than being dropped, so calls_handled across every row still reconciles
    with usable_calls."""

    agent_name: str
    calls_handled: int
    average_rating: float | None
    # Only over calls where the customer actually stated a number; null when
    # none of this agent's calls had one.
    average_stated_rating: float | None
    sentiment: list[SliceOut]
    satisfaction_bands: list[SliceOut]
    script_adherence: list[SliceOut]
    compliance_issue_count: int
    # Share (0-100) of this agent's calls whose connection_status wasn't
    # "connected" — network drops, no-answers, etc.
    connection_issue_rate: float


class InsightPairOut(BaseModel):
    """One cross-signal correlation: a positive theme and a negative/service
    issue that co-occur often on the same calls — e.g. service praised
    alongside spare-part pricing complaints."""

    positive_category: str
    other_category: str
    other_mention_type: str  # "negative_driver" | "service_issue"
    count: int
    percentage: float
    positive_example: str | None
    other_example: str | None


class ActiveFiltersOut(BaseModel):
    """The KPI cross-filters this response was computed under, echoed back.

    The dashboard renders these as removable chips, so what's currently
    filtered is always visible and always one click to undo — a KPI card you
    can click into but not out of is worse than one you can't click at all.
    """

    agent: str | None = None
    sentiment: str | None = None
    connection: str | None = None
    band: str | None = None
    quality: str | None = None
    adherence: str | None = None
    category: str | None = None


class DashboardInsightsOut(BaseModel):
    range: str
    plant: str | None
    # Echoes the request's `agent` filter (None = every agent combined).
    agent: str | None
    # Echoes the request's `data_mode` ("live" | "synthetic" | "all").
    data_mode: str
    filters: ActiveFiltersOut = ActiveFiltersOut()
    usable_calls: int
    insights: list[InsightPairOut]


class DashboardSummaryOut(BaseModel):
    range: str
    # Echoes the request's `plant` filter (None = all plants combined).
    plant: str | None
    # Echoes the request's `agent` filter (None = every agent combined). When
    # set, every KPI below is scoped to that one agent's calls — see
    # get_dashboard_summary's `agent` param for the by_agent exception.
    agent: str | None
    # Echoes the request's `rating_source` ("ai" | "stated").
    rating_source: str
    # Echoes the request's `data_mode` ("live" | "synthetic" | "all").
    data_mode: str
    # Every active KPI cross-filter, including `agent` — the frontend renders
    # these as chips. See ActiveFiltersOut.
    filters: ActiveFiltersOut = ActiveFiltersOut()
    # Every call in range, including ones too corrupt to analyze.
    total_calls: int
    # Calls with an analysis row of any kind.
    analyzed_calls: int
    # Analyzed and intelligible — i.e. we could hear what happened. INCLUDES
    # busy tones and voicemails, which are clear recordings of nothing. Only
    # the Call Connection Quality card uses this, because its whole question is
    # "of the calls we could hear, how many actually connected?"
    reachable_calls: int
    # Reachable AND a customer actually spoke (see models.CONVERSATION_STATUSES).
    # The denominator behind every "Based on N Usable Calls" subtitle, and the
    # basis of every rating, sentiment, compliance and issue figure — a busy
    # tone carries no customer opinion, so counting it would dilute the calls
    # that do.
    usable_calls: int
    average_rating: float | None

    # NOTE on the breakdowns below: each one is computed with every active
    # filter applied EXCEPT its own dimension. So filtering to Negative
    # sentiment rescopes every other card, while the sentiment breakdown itself
    # still shows positive/neutral/negative — with the selected slice
    # highlighted. Without that, one click would collapse the card to 100% of
    # the thing you clicked and leave no way back to the others.
    call_quality: list[SliceOut]
    # How the call itself went technically (connected / dropped mid-call /
    # etc.), independent of recording clarity — see call_quality for that.
    # Scoped to usable_calls (call_quality != rejected_corrupted): a call with
    # no real conversation is already captured by call_quality, so this
    # answers the narrower, more useful question — of the calls we could
    # actually use, how many still hit a network/technical problem?
    connection_status: list[SliceOut]
    sentiment: list[SliceOut]
    satisfaction_bands: list[SliceOut]
    script_adherence: list[SliceOut]

    top_negative_drivers: list[SliceOut]
    top_service_issues: list[SliceOut]
    top_positive_themes: list[SliceOut]
    top_compliance_issues: list[SliceOut]

    by_agent: list[AgentStatsOut]

    # The trend card spans its own fixed windows (the latest month present in
    # the data, and the three months before it), so these are deliberately NOT
    # filtered by `range` — otherwise picking "1D" would empty the chart.
    current_month_label: str | None
    monthly_averages: list[MonthlyAverageOut]
    daily_ratings: list[DailyRatingOut]
