from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Date, Select, cast, func, select
from sqlalchemy.orm import Session, aliased

from app.db.models import (
    Call,
    CallAnalysis,
    CallQuality,
    ConnectionStatus,
    IssueMention,
    MentionType,
    ScriptAdherence,
    Sentiment,
    plant_expr,
)
from app.db.session import get_db
from app.schemas.dashboard import (
    ActiveFiltersOut,
    AgentStatsOut,
    DailyRatingOut,
    DashboardAgentsOut,
    DashboardInsightsOut,
    DashboardPlantsOut,
    DashboardSummaryOut,
    InsightPairOut,
    MonthlyAverageOut,
    SliceOut,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

_RANGE_TO_DAYS = {"1d": 1, "7d": 7, "1m": 30, "3m": 90}

_QUALITY_LABELS = {
    "good_clear": "Good Clear Calls",
    "partial_usable": "Partial but Usable Calls",
    "rejected_corrupted": "Rejected / Corrupted Calls",
}
# Fixed display order, so the donut's colors don't reshuffle as counts change.
_QUALITY_ORDER = ["good_clear", "partial_usable", "rejected_corrupted"]

# "Good Connection" / "Poor Connection (...)" — deliberately phrased as two
# plain business categories (good vs. poor) rather than raw enum names, since
# that's the actual question this KPI answers. Scoped to usable_calls (see
# get_dashboard_summary), so in practice only "connected" and
# "dropped_during_call" normally appear — the others stay defined for the
# rare case a call is marked usable with one of them anyway.
_CONNECTION_LABELS = {
    "connected": "Good Connection",
    "dropped_during_call": "Poor Connection (Dropped Mid-Call)",
    "dropped_at_greeting": "Poor Connection (Dropped at Greeting)",
    "no_answer_busy": "Poor Connection (No Answer / Busy)",
    "voicemail_ivr_only": "Poor Connection (Voicemail / IVR)",
    "silent_dead_air": "Poor Connection (Dead Air)",
}
_CONNECTION_ORDER = [
    "connected",
    "dropped_during_call",
    "dropped_at_greeting",
    "no_answer_busy",
    "voicemail_ivr_only",
    "silent_dead_air",
]

_SCRIPT_LABELS = {
    "followed": "Followed Script",
    "partial": "Partially Followed",
    "not_followed": "Did Not Follow Script",
}
_SCRIPT_ORDER = ["followed", "partial", "not_followed"]

_SENTIMENT_LABELS = {"positive": "POSITIVE", "neutral": "NEUTRAL", "negative": "NEGATIVE"}
_SENTIMENT_ORDER = ["positive", "neutral", "negative"]

_SATISFIED_BAND = "9 - 10"
_BORDERLINE_BAND = "8"
_UNSATISFIED_BAND = "1 - 7"
_NOT_GIVEN_BAND = "Not Given"
_BAND_ORDER = [_SATISFIED_BAND, _BORDERLINE_BAND, _UNSATISFIED_BAND]
_BAND_ORDER_STATED = [_SATISFIED_BAND, _BORDERLINE_BAND, _UNSATISFIED_BAND, _NOT_GIVEN_BAND]

_UNASSIGNED_AGENT = "Unassigned"

_MONTH_ABBR = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

# When a call actually happened, which is what the dashboard's time filter
# means — NOT when we happened to ingest it. `recording_date` is parsed out of
# the object path ("recordings/2026-08-24/<team>/..."); it falls back to the
# ingest timestamp for objects whose path doesn't carry a date.
_EFFECTIVE_DATE = func.coalesce(cast(Call.recording_date, Date), cast(Call.created_at, Date))

_DATA_MODE_DESCRIPTION = (
    "'live' (default): real calls only. 'synthetic': only Admin-generated dummy calls, for QA without "
    "touching real data. 'all': both."
)
_AGENT_DESCRIPTION = (
    "Scope every KPI on this response to one agent's calls (exact agent_name match). This is what powers "
    "the dashboard's interactive agent drill-down — every card driven by this endpoint recontextualizes "
    "around the selected agent. by_agent is the one exception: it always reflects the full roster "
    "(ignoring this filter), so it stays usable as a picker regardless of the current selection."
)
_FILTER_DESCRIPTION = (
    "Interactive KPI cross-filter, set by clicking the corresponding slice/row on the dashboard. Scopes "
    "every card to matching calls — except the card that owns this dimension, which keeps its full "
    "breakdown so the selection can be changed or cleared from the same place it was made."
)


def _cutoff(time_range: str) -> date | None:
    days = _RANGE_TO_DAYS.get(time_range)
    if days is None:
        return None
    return (datetime.now(timezone.utc) - timedelta(days=days)).date()


def _to_slices(
    counter: "Counter[str]",
    total: int,
    labels: dict[str, str] | None = None,
    order: list[str] | None = None,
    examples: dict[str, str] | None = None,
    tags: dict[str, list[str]] | None = None,
) -> list[SliceOut]:
    """Ranked breakdown. `order` pins a fixed sequence (for the fixed-palette
    donuts); without it, rows come back largest-first, which is what the
    ranked issue tables want."""
    if order is not None:
        keys = [k for k in order if counter.get(k)]
    else:
        keys = [k for k, _ in counter.most_common()]

    return [
        SliceOut(
            key=key,
            label=(labels or {}).get(key, key),
            count=counter[key],
            percentage=round(counter[key] / total * 100, 2) if total else 0.0,
            example=(examples or {}).get(key),
            tags=(tags or {}).get(key, []),
        )
        for key in keys
    ]


def _satisfaction_band(rating: int) -> str:
    """9-10 = Satisfied, 8 = Borderline ("on the fence" — not a complaint, but
    not a delighted customer either), 1-7 = Not Satisfied."""
    if rating >= 9:
        return _SATISFIED_BAND
    if rating == 8:
        return _BORDERLINE_BAND
    return _UNSATISFIED_BAND


def _month_label(year: int, month: int) -> str:
    return f"{_MONTH_ABBR[month - 1]} AVG"


def _shift_month(year: int, month: int, back: int) -> tuple[int, int]:
    index = (year * 12 + (month - 1)) - back
    return index // 12, index % 12 + 1


def _data_mode_filter(data_mode: str):
    """None when `data_mode='all'` (no filter); otherwise a Call.is_synthetic
    predicate. A shared helper so every dashboard endpoint applies it
    consistently."""
    if data_mode == "all":
        return None
    return Call.is_synthetic.is_(data_mode == "synthetic")


def _base_call_stmt(cutoff: date | None, plant: str | None, data_mode: str) -> Select:
    """The (range, plant, data_mode)-filtered call set — everything EXCEPT the
    agent filter, which callers add on top only for the "scoped" query. Kept
    separate so `by_agent` can always be computed from the un-agent-filtered
    roster (see module docstring on `agent` query params)."""
    stmt = select(Call.id)
    if cutoff is not None:
        stmt = stmt.where(_EFFECTIVE_DATE >= cutoff)
    if plant is not None:
        stmt = stmt.where(plant_expr == plant)
    mode_filter = _data_mode_filter(data_mode)
    if mode_filter is not None:
        stmt = stmt.where(mode_filter)
    return stmt


@dataclass(frozen=True)
class KpiFilters:
    """The cross-filter selection: one optional value per clickable dimension.

    Every one of these is set by clicking something on the dashboard — a donut
    slice, a satisfaction band, an agent name, a category row — and clearing it
    is clicking the same thing again, or its chip. Keeping them in one object
    (rather than six parameters threaded everywhere) is what makes
    `without()` below possible, and `without()` is what keeps the dashboard
    navigable.
    """

    agent: str | None = None
    sentiment: str | None = None
    connection: str | None = None
    band: str | None = None
    quality: str | None = None
    adherence: str | None = None
    category: str | None = None

    def without(self, dimension: str) -> "KpiFilters":
        """The same selection with one dimension released.

        This is the rule that makes a KPI card clickable *both ways*: a card is
        rendered from the aggregate computed without its own filter, so it
        keeps showing the full breakdown (with the chosen slice highlighted)
        instead of collapsing to 100% of whatever was clicked. Every other card
        sees the full selection.
        """
        return replace(self, **{dimension: None})

    def as_out(self) -> ActiveFiltersOut:
        return ActiveFiltersOut(**asdict(self))


def _analysis_conditions(filters: KpiFilters, rating_source: str) -> list:
    """Predicates on `CallAnalysis` for whichever filters are active."""
    conditions = []
    if filters.agent is not None:
        conditions.append(CallAnalysis.agent_name == filters.agent)
    if filters.sentiment is not None:
        conditions.append(CallAnalysis.sentiment == Sentiment(filters.sentiment))
    if filters.connection is not None:
        conditions.append(CallAnalysis.connection_status == ConnectionStatus(filters.connection))
    if filters.quality is not None:
        conditions.append(CallAnalysis.call_quality == CallQuality(filters.quality))
    if filters.adherence is not None:
        conditions.append(CallAnalysis.script_adherence == ScriptAdherence(filters.adherence))
    if filters.band is not None:
        # Band is a derived bucket, not a column, so it has to be turned back
        # into a range — against whichever rating the card is currently showing.
        column = (
            CallAnalysis.customer_stated_rating
            if rating_source == "stated"
            else CallAnalysis.satisfaction_rating
        )
        if filters.band == _NOT_GIVEN_BAND:
            conditions.append(column.is_(None))
        elif filters.band == _SATISFIED_BAND:
            conditions.append(column >= 9)
        elif filters.band == _BORDERLINE_BAND:
            conditions.append(column == 8)
        else:
            conditions.append(column <= 7)
    return conditions


def _category_exists(category: str):
    """Calls carrying at least one mention of this category, across any mention
    type — clicking "Spare Parts Pricing" in one table should pull up
    everything true about those calls, not just that table's slice of them."""
    return (
        select(1)
        .where(IssueMention.call_id == Call.id, IssueMention.category == category)
        .exists()
    )


def _with_kpi_filters(stmt: Select, filters: KpiFilters, rating_source: str = "ai") -> Select:
    conditions = _analysis_conditions(filters, rating_source)
    if conditions:
        stmt = stmt.join(CallAnalysis, CallAnalysis.call_id == Call.id).where(*conditions)
    if filters.category is not None:
        stmt = stmt.where(_category_exists(filters.category))
    return stmt


@dataclass
class _Aggregate:
    """Everything derivable from one set of call ids — computed once per
    (scoped, roster) query rather than duplicated inline, so get_dashboard_summary
    can ask for it twice (agent-scoped for the top-line KPIs; roster-wide,
    ignoring the agent filter, for the by_agent picker) without repeating the
    aggregation logic itself."""

    analyzed_calls: int = 0
    usable_calls: int = 0
    quality_counter: "Counter[str]" = field(default_factory=Counter)
    connection_counter: "Counter[str]" = field(default_factory=Counter)
    sentiment_counter: "Counter[str]" = field(default_factory=Counter)
    script_counter: "Counter[str]" = field(default_factory=Counter)
    ai_ratings: list[int] = field(default_factory=list)
    stated_ratings: list[int] = field(default_factory=list)
    not_given_count: int = 0
    mention_counters: dict[MentionType, "Counter[str]"] = field(
        default_factory=lambda: {mt: Counter() for mt in MentionType}
    )
    mention_examples: dict[MentionType, dict[str, str]] = field(
        default_factory=lambda: {mt: {} for mt in MentionType}
    )
    mention_tags: dict[MentionType, dict[str, "Counter[str]"]] = field(
        default_factory=lambda: {mt: defaultdict(Counter) for mt in MentionType}
    )
    agent_usable_analyses: dict[str, list[CallAnalysis]] = field(default_factory=lambda: defaultdict(list))
    agent_compliance_counts: "Counter[str]" = field(default_factory=Counter)

    def mentions(self, mention_type: MentionType) -> list[SliceOut]:
        counter = self.mention_counters[mention_type]
        return _to_slices(
            counter,
            sum(counter.values()),
            examples=self.mention_examples[mention_type],
            tags={k: [t for t, _ in c.most_common(3)] for k, c in self.mention_tags[mention_type].items()},
        )


def _aggregate(db: Session, call_ids: list[UUID]) -> _Aggregate:
    agg = _Aggregate()
    if not call_ids:
        return agg

    analyses = list(db.execute(select(CallAnalysis).where(CallAnalysis.call_id.in_(call_ids))).scalars().all())
    agg.analyzed_calls = len(analyses)

    call_id_to_agent: dict[UUID, str] = {}
    for analysis in analyses:
        call_id_to_agent[analysis.call_id] = analysis.agent_name or _UNASSIGNED_AGENT
        agg.quality_counter[analysis.call_quality.value] += 1

        # Rejected calls are counted in the quality breakdown (that IS the
        # finding) but excluded everywhere else: the model's sentiment and
        # rating for audio it couldn't hear are not evidence of anything.
        # Connection status is scoped to usable calls too — "no real
        # conversation happened" is already what call_quality=rejected means,
        # so re-showing that here would be redundant. What this breakdown
        # answers is narrower and more useful: of the calls we COULD actually
        # use, how many still hit a network/technical problem?
        if analysis.call_quality is CallQuality.REJECTED_CORRUPTED:
            continue
        agg.usable_calls += 1
        agg.connection_counter[analysis.connection_status.value] += 1
        agg.sentiment_counter[analysis.sentiment.value] += 1
        agg.script_counter[analysis.script_adherence.value] += 1
        agg.ai_ratings.append(analysis.satisfaction_rating)
        if analysis.customer_stated_rating is not None:
            agg.stated_ratings.append(analysis.customer_stated_rating)
        else:
            agg.not_given_count += 1
        agg.agent_usable_analyses[analysis.agent_name or _UNASSIGNED_AGENT].append(analysis)

    mention_rows = db.execute(
        select(
            IssueMention.call_id,
            IssueMention.mention_type,
            IssueMention.category,
            IssueMention.quote,
            IssueMention.tags,
        ).where(IssueMention.call_id.in_(call_ids))
    ).all()
    for call_id, mention_type, category, quote, tags in mention_rows:
        agg.mention_counters[mention_type][category] += 1
        if quote and (
            category not in agg.mention_examples[mention_type]
            or quote < agg.mention_examples[mention_type][category]
        ):
            agg.mention_examples[mention_type][category] = quote
        for tag in tags or []:
            agg.mention_tags[mention_type][category][tag] += 1
        if mention_type is MentionType.AGENT_COMPLIANCE:
            agg.agent_compliance_counts[call_id_to_agent.get(call_id, _UNASSIGNED_AGENT)] += 1

    return agg


def _trend(
    db: Session, plant: str | None, data_mode: str, filters: KpiFilters, rating_source: str
) -> tuple[str | None, list[MonthlyAverageOut], list[DailyRatingOut]]:
    """Daily ratings for the most recent month present in the data, plus the
    three months before it.

    Anchored on the latest call in the database rather than on today's clock:
    a dataset that stops in August should still render its August trend in
    September, instead of showing an empty "current month".

    Deliberately NOT filtered by the time-range picker (see DashboardSummaryOut
    docstring) but IS filtered by `plant` and by every active KPI cross-filter —
    picking "CE", one agent, or "Negative sentiment" should show that group's
    own trend, not one still averaged in with everyone else.
    """
    stmt = (
        select(_EFFECTIVE_DATE.label("day"), CallAnalysis.satisfaction_rating)
        .join(CallAnalysis, CallAnalysis.call_id == Call.id)
        .where(CallAnalysis.call_quality != CallQuality.REJECTED_CORRUPTED)
    )
    if plant is not None:
        stmt = stmt.where(plant_expr == plant)
    # CallAnalysis is already joined here, so the conditions apply directly
    # rather than through _with_kpi_filters (which would join it a second time).
    conditions = _analysis_conditions(filters, rating_source)
    if conditions:
        stmt = stmt.where(*conditions)
    if filters.category is not None:
        stmt = stmt.where(_category_exists(filters.category))
    mode_filter = _data_mode_filter(data_mode)
    if mode_filter is not None:
        stmt = stmt.where(mode_filter)
    rows = db.execute(stmt).all()
    if not rows:
        return None, [], []

    latest = max(day for day, _ in rows)

    per_day: dict[int, list[int]] = defaultdict(list)
    per_month: dict[tuple[int, int], list[int]] = defaultdict(list)
    for day, rating in rows:
        per_month[(day.year, day.month)].append(rating)
        if (day.year, day.month) == (latest.year, latest.month):
            per_day[day.day].append(rating)

    def _avg(values: list[int]) -> float:
        return round(sum(values) / len(values), 2)

    daily = [
        DailyRatingOut(day=day, rating=_avg(values), call_count=len(values))
        for day, values in sorted(per_day.items())
    ]

    # Oldest first, so the bars read left-to-right chronologically. Months with
    # no calls are omitted rather than drawn as zero — a zero bar would read as
    # "everyone was furious" instead of "no data".
    monthly = []
    for back in (3, 2, 1):
        key = _shift_month(latest.year, latest.month, back)
        values = per_month.get(key)
        if values:
            monthly.append(
                MonthlyAverageOut(
                    month=_month_label(*key), avg_rating=_avg(values), call_count=len(values)
                )
            )

    return f"{_MONTH_ABBR[latest.month - 1]} {latest.year}", monthly, daily


@router.get("/plants", response_model=DashboardPlantsOut)
def get_dashboard_plants(
    db: Session = Depends(get_db),
    data_mode: str = Query("live", pattern="^(live|synthetic|all)$", description=_DATA_MODE_DESCRIPTION),
) -> DashboardPlantsOut:
    """Every plant code seen in the data, for the filter's own option list.

    Unfiltered by range or plant on purpose — the list of *available* filters
    shouldn't shrink just because the currently selected time range happens to
    have no calls from one plant.
    """
    stmt = select(plant_expr).where(Call.team_code.isnot(None))
    mode_filter = _data_mode_filter(data_mode)
    if mode_filter is not None:
        stmt = stmt.where(mode_filter)
    plants = db.execute(stmt.distinct().order_by(plant_expr)).scalars().all()
    return DashboardPlantsOut(plants=list(plants))


@router.get("/agents", response_model=DashboardAgentsOut)
def get_dashboard_agents(
    db: Session = Depends(get_db),
    data_mode: str = Query("live", pattern="^(live|synthetic|all)$", description=_DATA_MODE_DESCRIPTION),
) -> DashboardAgentsOut:
    """Every distinct agent name seen in the data, for the Calls page's and
    the dashboard's agent filter/breakdown option lists. Unfiltered by range
    or plant for the same reason as get_dashboard_plants."""
    stmt = (
        select(CallAnalysis.agent_name)
        .join(Call, Call.id == CallAnalysis.call_id)
        .where(CallAnalysis.agent_name.isnot(None))
    )
    mode_filter = _data_mode_filter(data_mode)
    if mode_filter is not None:
        stmt = stmt.where(mode_filter)
    agents = db.execute(stmt.distinct().order_by(CallAnalysis.agent_name)).scalars().all()
    return DashboardAgentsOut(agents=list(agents))


@router.get("/summary", response_model=DashboardSummaryOut)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    time_range: str = Query("all", alias="range", pattern="^(1d|7d|1m|3m|all)$"),
    plant: str | None = Query(
        None,
        pattern="^[A-Za-z]{2}$",
        description="Filter to one plant (last 2 letters of the team code, e.g. 'CE' or 'TA'). Omit for all plants.",
    ),
    agent: str | None = Query(None, description=_AGENT_DESCRIPTION),
    rating_source: str = Query(
        "ai",
        pattern="^(ai|stated)$",
        description=(
            "'ai' (default): satisfaction_bands/average_rating from the model's own estimate. "
            "'stated': from the customer's explicitly-stated number only — calls where none was "
            "given show up as a 'Not Given' band and are excluded from the average."
        ),
    ),
    data_mode: str = Query("live", pattern="^(live|synthetic|all)$", description=_DATA_MODE_DESCRIPTION),
    sentiment: str | None = Query(None, pattern="^(positive|neutral|negative)$", description=_FILTER_DESCRIPTION),
    connection: str | None = Query(
        None,
        pattern="^(connected|dropped_during_call|dropped_at_greeting|no_answer_busy|voicemail_ivr_only|silent_dead_air)$",
        description=_FILTER_DESCRIPTION,
    ),
    band: str | None = Query(
        None,
        description=f"Satisfaction band: '{_SATISFIED_BAND}', '{_BORDERLINE_BAND}', "
        f"'{_UNSATISFIED_BAND}' or '{_NOT_GIVEN_BAND}'. {_FILTER_DESCRIPTION}",
    ),
    quality: str | None = Query(
        None, pattern="^(good_clear|partial_usable|rejected_corrupted)$", description=_FILTER_DESCRIPTION
    ),
    adherence: str | None = Query(
        None, pattern="^(followed|partial|not_followed)$", description=_FILTER_DESCRIPTION
    ),
    category: str | None = Query(
        None,
        description="Only calls carrying a mention of this exact category, in any mention type. "
        + _FILTER_DESCRIPTION,
    ),
) -> DashboardSummaryOut:
    cutoff = _cutoff(time_range)
    plant = plant.upper() if plant else None

    if band is not None and band not in _BAND_ORDER_STATED:
        raise HTTPException(status_code=422, detail=f"Unknown satisfaction band: {band}")

    filters = KpiFilters(
        agent=agent,
        sentiment=sentiment,
        connection=connection,
        band=band,
        quality=quality,
        adherence=adherence,
        category=category,
    )

    base_stmt = _base_call_stmt(cutoff, plant, data_mode)

    def _ids(selection: KpiFilters) -> list[UUID]:
        return list(db.execute(_with_kpi_filters(base_stmt, selection, rating_source)).scalars().all())

    call_ids = _ids(filters)
    total_calls = len(call_ids)
    scoped = _aggregate(db, call_ids)

    # A card that owns an active filter is rendered from the aggregate computed
    # WITHOUT that filter, so it keeps its full breakdown (with the selected
    # slice highlighted) and stays clickable in both directions. Cached because
    # by_agent and the band counter both ask for their dimension more than once,
    # and because `scoped` is the correct answer whenever the dimension is
    # inactive — costing no extra query in the common case.
    cache: dict[str, _Aggregate] = {}

    def _excluding(dimension: str) -> _Aggregate:
        if getattr(filters, dimension) is None:
            return scoped
        if dimension not in cache:
            cache[dimension] = _aggregate(db, _ids(filters.without(dimension)))
        return cache[dimension]

    # by_agent must stay a full roster regardless of the current agent
    # selection — it's the picker that lets you GET to a per-agent view in the
    # first place, so it can't itself collapse to one row once you're in one.
    roster = _excluding("agent")
    band_source = _excluding("band")
    category_source = _excluding("category")

    if rating_source == "stated":
        band_counter: "Counter[str]" = Counter()
        for rating in band_source.stated_ratings:
            band_counter[_satisfaction_band(rating)] += 1
        band_counter[_NOT_GIVEN_BAND] = band_source.not_given_count
        ratings_for_avg = scoped.stated_ratings
    else:
        band_counter = Counter()
        for rating in band_source.ai_ratings:
            band_counter[_satisfaction_band(rating)] += 1
        ratings_for_avg = scoped.ai_ratings

    def _agent_stats() -> list[AgentStatsOut]:
        stats: list[AgentStatsOut] = []
        for name, items in roster.agent_usable_analyses.items():
            ai_vals = [a.satisfaction_rating for a in items]
            stated_vals = [a.customer_stated_rating for a in items if a.customer_stated_rating is not None]
            sentiment_c: "Counter[str]" = Counter(a.sentiment.value for a in items)
            band_c: "Counter[str]" = Counter(_satisfaction_band(a.satisfaction_rating) for a in items)
            script_c: "Counter[str]" = Counter(a.script_adherence.value for a in items)
            not_connected = sum(1 for a in items if a.connection_status is not ConnectionStatus.CONNECTED)
            stats.append(
                AgentStatsOut(
                    agent_name=name,
                    calls_handled=len(items),
                    average_rating=round(sum(ai_vals) / len(ai_vals), 2) if ai_vals else None,
                    average_stated_rating=round(sum(stated_vals) / len(stated_vals), 2)
                    if stated_vals
                    else None,
                    sentiment=_to_slices(sentiment_c, len(items), _SENTIMENT_LABELS, _SENTIMENT_ORDER),
                    satisfaction_bands=_to_slices(band_c, len(items), order=_BAND_ORDER),
                    script_adherence=_to_slices(script_c, len(items), _SCRIPT_LABELS, _SCRIPT_ORDER),
                    compliance_issue_count=roster.agent_compliance_counts.get(name, 0),
                    connection_issue_rate=round(not_connected / len(items) * 100, 2) if items else 0.0,
                )
            )
        # Worst average rating first — that's where attention is needed.
        stats.sort(key=lambda s: s.average_rating if s.average_rating is not None else 0)
        return stats

    current_month, monthly_averages, daily_ratings = _trend(db, plant, data_mode, filters, rating_source)

    quality_source = _excluding("quality")
    connection_source = _excluding("connection")
    sentiment_source = _excluding("sentiment")
    adherence_source = _excluding("adherence")

    return DashboardSummaryOut(
        range=time_range,
        plant=plant,
        agent=agent,
        rating_source=rating_source,
        data_mode=data_mode,
        filters=filters.as_out(),
        total_calls=total_calls,
        analyzed_calls=scoped.analyzed_calls,
        usable_calls=scoped.usable_calls,
        average_rating=round(sum(ratings_for_avg) / len(ratings_for_avg), 2) if ratings_for_avg else None,
        call_quality=_to_slices(
            quality_source.quality_counter, quality_source.analyzed_calls, _QUALITY_LABELS, _QUALITY_ORDER
        ),
        connection_status=_to_slices(
            connection_source.connection_counter,
            connection_source.usable_calls,
            _CONNECTION_LABELS,
            _CONNECTION_ORDER,
        ),
        sentiment=_to_slices(
            sentiment_source.sentiment_counter,
            sentiment_source.usable_calls,
            _SENTIMENT_LABELS,
            _SENTIMENT_ORDER,
        ),
        satisfaction_bands=_to_slices(
            band_counter,
            band_source.usable_calls,
            order=_BAND_ORDER_STATED if rating_source == "stated" else _BAND_ORDER,
        ),
        script_adherence=_to_slices(
            adherence_source.script_counter, adherence_source.usable_calls, _SCRIPT_LABELS, _SCRIPT_ORDER
        ),
        top_negative_drivers=category_source.mentions(MentionType.NEGATIVE_DRIVER),
        top_service_issues=category_source.mentions(MentionType.SERVICE_ISSUE),
        top_positive_themes=category_source.mentions(MentionType.POSITIVE_THEME),
        top_compliance_issues=category_source.mentions(MentionType.AGENT_COMPLIANCE),
        by_agent=_agent_stats(),
        current_month_label=current_month,
        monthly_averages=monthly_averages,
        daily_ratings=daily_ratings,
    )


@router.get("/insights", response_model=DashboardInsightsOut)
def get_dashboard_insights(
    db: Session = Depends(get_db),
    time_range: str = Query("all", alias="range", pattern="^(1d|7d|1m|3m|all)$"),
    plant: str | None = Query(
        None,
        pattern="^[A-Za-z]{2}$",
        description="Filter to one plant (last 2 letters of the team code, e.g. 'CE' or 'TA'). Omit for all plants.",
    ),
    agent: str | None = Query(None, description=_AGENT_DESCRIPTION),
    data_mode: str = Query("live", pattern="^(live|synthetic|all)$", description=_DATA_MODE_DESCRIPTION),
    sentiment: str | None = Query(None, pattern="^(positive|neutral|negative)$", description=_FILTER_DESCRIPTION),
    connection: str | None = Query(
        None,
        pattern="^(connected|dropped_during_call|dropped_at_greeting|no_answer_busy|voicemail_ivr_only|silent_dead_air)$",
        description=_FILTER_DESCRIPTION,
    ),
    band: str | None = Query(None, description=_FILTER_DESCRIPTION),
    quality: str | None = Query(
        None, pattern="^(good_clear|partial_usable|rejected_corrupted)$", description=_FILTER_DESCRIPTION
    ),
    adherence: str | None = Query(
        None, pattern="^(followed|partial|not_followed)$", description=_FILTER_DESCRIPTION
    ),
    category: str | None = Query(None, description=_FILTER_DESCRIPTION),
) -> DashboardInsightsOut:
    """Cross-signal correlation: positive themes that co-occur, on the same
    calls, with a negative driver or service issue — e.g. "service praised
    alongside spare-part pricing complaints in 23 calls". Surfaces the kind of
    actionable insight a single ranked-by-category table can't show, since it
    requires looking at pairs of mentions rather than one at a time.
    """
    cutoff = _cutoff(time_range)
    plant_upper = plant.upper() if plant else None

    if band is not None and band not in _BAND_ORDER_STATED:
        raise HTTPException(status_code=422, detail=f"Unknown satisfaction band: {band}")

    filters = KpiFilters(
        agent=agent,
        sentiment=sentiment,
        connection=connection,
        band=band,
        quality=quality,
        adherence=adherence,
        category=category,
    )
    call_ids = list(
        db.execute(_with_kpi_filters(_base_call_stmt(cutoff, plant_upper, data_mode), filters))
        .scalars()
        .all()
    )

    usable_calls = 0
    insights: list[InsightPairOut] = []

    if call_ids:
        usable_calls = db.execute(
            select(func.count())
            .select_from(CallAnalysis)
            .where(CallAnalysis.call_id.in_(call_ids), CallAnalysis.call_quality != CallQuality.REJECTED_CORRUPTED)
        ).scalar_one()

        positive = aliased(IssueMention)
        other = aliased(IssueMention)
        rows = db.execute(
            select(
                positive.category,
                other.category,
                other.mention_type,
                func.count(func.distinct(positive.call_id)).label("n"),
                func.min(positive.quote).label("positive_example"),
                func.min(other.quote).label("other_example"),
            )
            .join(other, other.call_id == positive.call_id)
            .where(
                positive.call_id.in_(call_ids),
                positive.mention_type == MentionType.POSITIVE_THEME,
                other.mention_type.in_([MentionType.NEGATIVE_DRIVER, MentionType.SERVICE_ISSUE]),
            )
            .group_by(positive.category, other.category, other.mention_type)
            .order_by(func.count(func.distinct(positive.call_id)).desc())
            .limit(8)
        ).all()

        for positive_category, other_category, other_mention_type, n, positive_example, other_example in rows:
            insights.append(
                InsightPairOut(
                    positive_category=positive_category,
                    other_category=other_category,
                    other_mention_type=other_mention_type.value,
                    count=n,
                    percentage=round(n / usable_calls * 100, 2) if usable_calls else 0.0,
                    positive_example=positive_example,
                    other_example=other_example,
                )
            )

    return DashboardInsightsOut(
        range=time_range,
        plant=plant_upper,
        agent=agent,
        data_mode=data_mode,
        filters=filters.as_out(),
        usable_calls=usable_calls,
        insights=insights,
    )
