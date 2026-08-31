from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.db.models import Call, CallAnalysis, CallQuality, IssueMention, MentionType
from app.db.session import get_db
from app.schemas.dashboard import (
    DailyRatingOut,
    DashboardPlantsOut,
    DashboardSummaryOut,
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

_SENTIMENT_LABELS = {"positive": "POSITIVE", "neutral": "NEUTRAL", "negative": "NEGATIVE"}
_SENTIMENT_ORDER = ["positive", "neutral", "negative"]

_SATISFIED_BAND = "8 - 10"
_UNSATISFIED_BAND = "1 - 7"
_BAND_ORDER = [_SATISFIED_BAND, _UNSATISFIED_BAND]

_MONTH_ABBR = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

# When a call actually happened, which is what the dashboard's time filter
# means — NOT when we happened to ingest it. `recording_date` is parsed out of
# the object path ("recordings/2026-08-24/<team>/..."); it falls back to the
# ingest timestamp for objects whose path doesn't carry a date.
_EFFECTIVE_DATE = func.coalesce(cast(Call.recording_date, Date), cast(Call.created_at, Date))

# The bucket's `team_code` ("BMCSTTA", "BMCSTCE", parsed from
# recordings/<date>/<team_code>/<file>) encodes the plant as its last two
# letters — TA / CE. There's no separate "plant" column: deriving it from the
# same SQL expression on both the read side (here) and the filter side keeps
# the two from ever disagreeing.
_PLANT_SUFFIX_LEN = 2
_PLANT = func.upper(func.right(Call.team_code, _PLANT_SUFFIX_LEN))


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
        )
        for key in keys
    ]


def _satisfaction_band(rating: int) -> str:
    """8-10 = Satisfied, 1-7 = Not Satisfied. Matches the banding the model is
    told to aim for in the analysis prompt."""
    return _SATISFIED_BAND if rating >= 8 else _UNSATISFIED_BAND


def _month_label(year: int, month: int) -> str:
    return f"{_MONTH_ABBR[month - 1]} AVG"


def _shift_month(year: int, month: int, back: int) -> tuple[int, int]:
    index = (year * 12 + (month - 1)) - back
    return index // 12, index % 12 + 1


def _trend(
    db: Session, plant: str | None
) -> tuple[str | None, list[MonthlyAverageOut], list[DailyRatingOut]]:
    """Daily ratings for the most recent month present in the data, plus the
    three months before it.

    Anchored on the latest call in the database rather than on today's clock:
    a dataset that stops in August should still render its August trend in
    September, instead of showing an empty "current month".

    Deliberately NOT filtered by the time-range picker (see DashboardSummaryOut
    docstring) but IS filtered by `plant` — picking "CE" should show CE's own
    trend, not one still averaged in with TA.
    """
    stmt = (
        select(_EFFECTIVE_DATE.label("day"), CallAnalysis.satisfaction_rating)
        .join(CallAnalysis, CallAnalysis.call_id == Call.id)
        .where(CallAnalysis.call_quality != CallQuality.REJECTED_CORRUPTED)
    )
    if plant is not None:
        stmt = stmt.where(_PLANT == plant)
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
def get_dashboard_plants(db: Session = Depends(get_db)) -> DashboardPlantsOut:
    """Every plant code seen in the data, for the filter's own option list.

    Unfiltered by range or plant on purpose — the list of *available* filters
    shouldn't shrink just because the currently selected time range happens to
    have no calls from one plant.
    """
    plants = db.execute(
        select(_PLANT).where(Call.team_code.isnot(None)).distinct().order_by(_PLANT)
    ).scalars().all()
    return DashboardPlantsOut(plants=list(plants))


@router.get("/summary", response_model=DashboardSummaryOut)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    time_range: str = Query("all", alias="range", pattern="^(1d|7d|1m|3m|all)$"),
    plant: str | None = Query(
        None,
        pattern="^[A-Za-z]{2}$",
        description="Filter to one plant (last 2 letters of the team code, e.g. 'CE' or 'TA'). Omit for all plants.",
    ),
) -> DashboardSummaryOut:
    cutoff = _cutoff(time_range)
    plant = plant.upper() if plant else None

    call_stmt = select(Call.id)
    if cutoff is not None:
        call_stmt = call_stmt.where(_EFFECTIVE_DATE >= cutoff)
    if plant is not None:
        call_stmt = call_stmt.where(_PLANT == plant)
    call_ids = list(db.execute(call_stmt).scalars().all())
    total_calls = len(call_ids)

    quality_counter: "Counter[str]" = Counter()
    sentiment_counter: "Counter[str]" = Counter()
    band_counter: "Counter[str]" = Counter()
    mention_counters: dict[MentionType, "Counter[str]"] = {mt: Counter() for mt in MentionType}
    mention_examples: dict[MentionType, dict[str, str]] = {mt: {} for mt in MentionType}
    ratings: list[int] = []
    analyzed_calls = 0
    usable_calls = 0

    if call_ids:
        analyses = list(
            db.execute(select(CallAnalysis).where(CallAnalysis.call_id.in_(call_ids))).scalars().all()
        )
        analyzed_calls = len(analyses)
        for analysis in analyses:
            quality_counter[analysis.call_quality.value] += 1
            # Rejected calls are counted in the quality breakdown (that IS the
            # finding) but excluded everywhere else: the model's sentiment and
            # rating for audio it couldn't hear are not evidence of anything.
            if analysis.call_quality is CallQuality.REJECTED_CORRUPTED:
                continue
            usable_calls += 1
            sentiment_counter[analysis.sentiment.value] += 1
            band_counter[_satisfaction_band(analysis.satisfaction_rating)] += 1
            ratings.append(analysis.satisfaction_rating)

        mention_rows = db.execute(
            select(
                IssueMention.mention_type,
                IssueMention.category,
                func.count().label("n"),
                # One representative quote per category for the "Example from
                # Transcripts" column. min() is arbitrary but stable, so the
                # table doesn't reshuffle its examples between refreshes.
                func.min(IssueMention.quote).label("example"),
            )
            .where(IssueMention.call_id.in_(call_ids))
            .group_by(IssueMention.mention_type, IssueMention.category)
        ).all()
        for mention_type, category, n, example in mention_rows:
            mention_counters[mention_type][category] += n
            if example:
                mention_examples[mention_type][category] = example

    def _mentions(mention_type: MentionType) -> list[SliceOut]:
        counter = mention_counters[mention_type]
        return _to_slices(counter, sum(counter.values()), examples=mention_examples[mention_type])

    current_month, monthly_averages, daily_ratings = _trend(db, plant)

    return DashboardSummaryOut(
        range=time_range,
        plant=plant,
        total_calls=total_calls,
        analyzed_calls=analyzed_calls,
        usable_calls=usable_calls,
        average_rating=round(sum(ratings) / len(ratings), 2) if ratings else None,
        call_quality=_to_slices(quality_counter, analyzed_calls, _QUALITY_LABELS, _QUALITY_ORDER),
        sentiment=_to_slices(sentiment_counter, usable_calls, _SENTIMENT_LABELS, _SENTIMENT_ORDER),
        satisfaction_bands=_to_slices(band_counter, usable_calls, order=_BAND_ORDER),
        top_negative_drivers=_mentions(MentionType.NEGATIVE_DRIVER),
        top_service_issues=_mentions(MentionType.SERVICE_ISSUE),
        top_positive_themes=_mentions(MentionType.POSITIVE_THEME),
        current_month_label=current_month,
        monthly_averages=monthly_averages,
        daily_ratings=daily_ratings,
    )
