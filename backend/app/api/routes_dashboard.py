from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Call, CallAnalysis, IssueMention, MentionType
from app.db.session import get_db
from app.schemas.dashboard import DashboardSummaryOut, SliceOut

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

_RANGE_TO_DAYS = {"1d": 1, "7d": 7, "1m": 30, "3m": 90}

_QUALITY_LABELS = {
    "good_clear": "Good Clear Calls",
    "partial_usable": "Partial but Usable Calls",
    "rejected_corrupted": "Rejected / Corrupted Calls",
}
_SENTIMENT_LABELS = {"positive": "POSITIVE", "neutral": "NEUTRAL", "negative": "NEGATIVE"}


def _cutoff(time_range: str) -> datetime | None:
    days = _RANGE_TO_DAYS.get(time_range)
    if days is None:
        return None
    return datetime.now(timezone.utc) - timedelta(days=days)


def _to_slices(counter: "Counter[str]", total: int) -> list[SliceOut]:
    return [
        SliceOut(label=label, count=count, percentage=round(count / total * 100, 2) if total else 0.0)
        for label, count in sorted(counter.items(), key=lambda kv: kv[1], reverse=True)
    ]


def _satisfaction_band(rating: int) -> str:
    if rating >= 9:
        return "9 - 10"
    if rating >= 7:
        return "7 - 8"
    if rating >= 5:
        return "5 - 6"
    return "1 - 4"


@router.get("/summary", response_model=DashboardSummaryOut)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    time_range: str = Query("all", alias="range", pattern="^(1d|7d|1m|3m|all)$"),
) -> DashboardSummaryOut:
    cutoff = _cutoff(time_range)

    call_stmt = select(Call.id)
    if cutoff is not None:
        call_stmt = call_stmt.where(Call.created_at >= cutoff)
    call_ids = list(db.execute(call_stmt).scalars().all())
    total_calls = len(call_ids)

    quality_counter: "Counter[str]" = Counter()
    sentiment_counter: "Counter[str]" = Counter()
    band_counter: "Counter[str]" = Counter()
    negative_counter: "Counter[str]" = Counter()
    service_counter: "Counter[str]" = Counter()
    positive_counter: "Counter[str]" = Counter()
    ratings: list[int] = []
    usable_calls = 0

    if call_ids:
        analyses = list(
            db.execute(select(CallAnalysis).where(CallAnalysis.call_id.in_(call_ids))).scalars().all()
        )
        usable_calls = len(analyses)
        for analysis in analyses:
            quality_counter[_QUALITY_LABELS.get(analysis.call_quality, analysis.call_quality)] += 1
            sentiment_counter[_SENTIMENT_LABELS.get(analysis.sentiment, analysis.sentiment)] += 1
            band_counter[_satisfaction_band(analysis.satisfaction_rating)] += 1
            ratings.append(analysis.satisfaction_rating)

        mention_rows = db.execute(
            select(IssueMention.mention_type, IssueMention.category, func.count().label("n"))
            .where(IssueMention.call_id.in_(call_ids))
            .group_by(IssueMention.mention_type, IssueMention.category)
        ).all()
        for mention_type, category, n in mention_rows:
            if mention_type == MentionType.NEGATIVE_DRIVER:
                negative_counter[category] += n
            elif mention_type == MentionType.SERVICE_ISSUE:
                service_counter[category] += n
            elif mention_type == MentionType.POSITIVE_THEME:
                positive_counter[category] += n

    return DashboardSummaryOut(
        range=time_range,
        total_calls=total_calls,
        usable_calls=usable_calls,
        call_quality=_to_slices(quality_counter, total_calls),
        sentiment=_to_slices(sentiment_counter, usable_calls),
        satisfaction_bands=_to_slices(band_counter, usable_calls),
        average_rating=round(sum(ratings) / len(ratings), 2) if ratings else None,
        top_negative_drivers=_to_slices(negative_counter, sum(negative_counter.values())),
        top_service_issues=_to_slices(service_counter, sum(service_counter.values())),
        top_positive_themes=_to_slices(positive_counter, sum(positive_counter.values())),
    )
