"""On-demand, LLM-written insight for the Key Insights card.

The card's default view is a rule-based correlation table (see
routes_dashboard.get_dashboard_insights): positive themes that co-occur, on
the same calls, with a negative driver or service issue. That's precise but
narrow — it only ever surfaces category/tag PAIRS, so a real pattern that
spans compliance, connection quality, or a trend never shows up there.

This module reads the same correlation pairs PLUS the full dashboard digest
(sentiment mix, top issues, agent performance, trend — everything
get_dashboard_summary already computes) and asks the cheap text tier to write
a short, broad set of findings over all of it. Broad is the point: the model
isn't limited to repeating whichever single top category pair ranks first.

The card loads this automatically, so results are cached per (filters, data
snapshot): viewing the same selection again is free, and a new Gemini call
only happens once newly analyzed calls change the underlying data.
"""

import threading
from collections import OrderedDict
from collections.abc import Callable, Hashable
from typing import TypeVar

from pydantic import BaseModel, Field

from app.schemas.dashboard import AgentStatsOut, DashboardSummaryOut, InsightPairOut, SliceOut
from app.services.llm_service import run_on_text

_MENTION_TYPE_LABEL = {"negative_driver": "complaint", "service_issue": "service issue"}


class AiInsightResult(BaseModel):
    """What the model produces. `usable_calls` isn't part of this — the route
    fills that in from the summary object itself, since it's already known
    and shouldn't be left for the model to restate (or get slightly wrong)."""

    headline: str = Field(
        description=(
            "One or two sentences giving the overall verdict on customer trust and satisfaction this "
            "period, citing the actual average rating and/or sentiment split from the data."
        )
    )
    key_points: list[str] = Field(
        description=(
            "4 to 7 short, distinct findings. Cover a BROAD MIX of the data provided — do not just "
            "restate the single strongest category/tag pair. Between them, touch on: a notable "
            "positive-theme/complaint correlation (if any are listed), the biggest complaint driver, "
            "the most reported machine/service issue, any agent script compliance or connection-quality "
            "problem, any notable trend (better/worse than the prior months), and any standout agent "
            "(best or worst). Skip a topic only if the data below has nothing in it. Every number quoted "
            "must come from the data below — never invent one."
        )
    )
    recommendation: str = Field(
        description=(
            "One or two sentences naming the single highest-priority action to take next, and the "
            "concrete reason (grounded in the data) it should come before the others."
        )
    )


_PROMPT = """You are writing "Key Insights" for a customer-service call-quality dashboard — a manager \
reads this to spot patterns a plain ranked table of categories can't show.

Ground every sentence in the data below. Never invent a category, agent name, or statistic that isn't \
listed. Go broad, not narrow: the data spans category/tag correlations, sentiment, satisfaction, several \
kinds of issues, script compliance, connection quality, trend, and per-agent performance — your findings \
should reflect that spread instead of repeating the single strongest correlation in different words.

DASHBOARD DATA
{digest}
"""


def _format_slices(slices: list[SliceOut], limit: int = 5) -> str:
    top = [s for s in slices if s.count > 0][:limit]
    if not top:
        return "  (none)"
    return "\n".join(f"  - {s.label}: {s.count} calls ({s.percentage:.1f}% of usable calls)" for s in top)


# An agent's average over one or two calls says nothing about the agent.
_MIN_AGENT_CALLS = 5


def _format_agents(agents: list[AgentStatsOut], *, worst: bool, limit: int = 3) -> str:
    ranked = [
        a
        for a in agents
        if a.average_rating is not None and a.agent_name != "Unassigned" and a.calls_handled >= _MIN_AGENT_CALLS
    ]
    ranked.sort(key=lambda a: a.average_rating, reverse=not worst)
    top = ranked[:limit]
    if not top:
        return "  (not enough data)"
    return "\n".join(
        f"  - {a.agent_name}: {a.calls_handled} calls, avg rating {a.average_rating:.2f}/10, "
        f"{a.compliance_issue_count} compliance issue(s), {a.connection_issue_rate:.1f}% connection-issue rate"
        for a in top
    )


def _format_pairs(pairs: list[InsightPairOut], limit: int = 8) -> str:
    top = pairs[:limit]
    if not top:
        return "  (none found — no positive theme and issue co-occur often enough on the same calls)"
    return "\n".join(
        f'  - "{p.positive_category}" praised alongside "{p.other_category}" '
        f"({_MENTION_TYPE_LABEL.get(p.other_mention_type, 'issue')}) in {p.count} calls ({p.percentage:.1f}%)"
        for p in top
    )


def build_digest(summary: DashboardSummaryOut, pairs: list[InsightPairOut]) -> str:
    """A compact, curated text digest of the dashboard's aggregate numbers —
    everything the insight should be able to draw on, without the noise of
    per-category example quotes/tags or the full agent roster."""
    lines: list[str] = []

    scope_bits = [f"range={summary.range}"]
    if summary.plant:
        scope_bits.append(f"plant={summary.plant}")
    if summary.agent:
        scope_bits.append(f"agent={summary.agent}")
    for name, value in (
        ("sentiment", summary.filters.sentiment),
        ("connection", summary.filters.connection),
        ("band", summary.filters.band),
        ("quality", summary.filters.quality),
        ("adherence", summary.filters.adherence),
        ("category", summary.filters.category),
    ):
        if value:
            scope_bits.append(f"{name}={value}")
    lines.append(f"Scope: {', '.join(scope_bits)}")
    lines.append(f"Usable calls: {summary.usable_calls} (of {summary.total_calls} discovered)")
    lines.append(
        f"Average rating: {summary.average_rating:.2f}/10" if summary.average_rating is not None else "Average rating: n/a"
    )

    lines.append("\nPositive themes co-occurring with a complaint/issue (same calls):")
    lines.append(_format_pairs(pairs))

    lines.append("\nSentiment split:")
    lines.append(_format_slices(summary.sentiment, limit=3))

    lines.append("\nSatisfaction bands:")
    lines.append(_format_slices(summary.satisfaction_bands, limit=4))

    lines.append("\nCall quality (of all analyzed calls):")
    lines.append(_format_slices(summary.call_quality, limit=3))

    lines.append("\nConnection status (of reachable calls):")
    lines.append(_format_slices(summary.connection_status, limit=6))

    lines.append("\nScript adherence:")
    lines.append(_format_slices(summary.script_adherence, limit=3))

    lines.append("\nTop negative drivers:")
    lines.append(_format_slices(summary.top_negative_drivers))

    lines.append("\nTop service/machine issues:")
    lines.append(_format_slices(summary.top_service_issues))

    lines.append("\nTop things customers praised:")
    lines.append(_format_slices(summary.top_positive_themes))

    lines.append("\nTop agent compliance issues:")
    lines.append(_format_slices(summary.top_compliance_issues))

    if summary.monthly_averages or summary.daily_ratings:
        lines.append("\nRating trend:")
        for m in summary.monthly_averages:
            lines.append(f"  - {m.month}: {m.avg_rating:.2f}/10 ({m.call_count} calls)")
        if summary.daily_ratings:
            days = summary.daily_ratings
            running_avg = sum(d.rating * d.call_count for d in days) / sum(d.call_count for d in days)
            label = summary.current_month_label or "current month"
            lines.append(f"  - {label} so far: {running_avg:.2f}/10 across {len(days)} day(s)")

    # by_agent is always the full roster (it ignores the agent filter), so with
    # one agent selected it would drag other agents into that agent's insights.
    if not summary.agent:
        lines.append("\nBest-performing agents:")
        lines.append(_format_agents(summary.by_agent, worst=False))
        lines.append("\nAgents most needing attention:")
        lines.append(_format_agents(summary.by_agent, worst=True))

    return "\n".join(lines)


def generate_ai_insight(summary: DashboardSummaryOut, pairs: list[InsightPairOut]) -> AiInsightResult:
    digest = build_digest(summary, pairs)
    result = run_on_text(AiInsightResult, _PROMPT.format(digest=digest))
    assert isinstance(result, AiInsightResult)
    return result


T = TypeVar("T")

_CACHE_LIMIT = 64
_cache: "OrderedDict[Hashable, object]" = OrderedDict()
_cache_lock = threading.Lock()
_key_locks: dict[Hashable, threading.Lock] = {}


def get_or_create(key: Hashable, produce: Callable[[], T]) -> T:
    """Returns the cached value for `key`, or runs `produce` once and caches it.

    A per-key lock stops two tabs opening the same view at once from paying
    for two identical Gemini calls. Failures aren't cached, so the next load
    retries.
    """
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]  # type: ignore[return-value]
        key_lock = _key_locks.setdefault(key, threading.Lock())

    with key_lock:
        with _cache_lock:
            if key in _cache:
                return _cache[key]  # type: ignore[return-value]
        try:
            value = produce()
        finally:
            with _cache_lock:
                _key_locks.pop(key, None)
        with _cache_lock:
            _cache[key] = value
            while len(_cache) > _CACHE_LIMIT:
                _cache.popitem(last=False)
        return value
