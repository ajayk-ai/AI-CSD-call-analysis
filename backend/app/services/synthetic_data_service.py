"""Cost-free dummy data for QA. Generates Call/Transcript/CallAnalysis/
IssueMention rows entirely in Python — no GCS listing, no Gemini calls — so
the dashboard's KPIs and cards can be exercised with realistic, varied data
without spending anything on the real pipeline.

Every row this writes has `is_synthetic=True` and every piece of generated
text is prefixed "[SYNTHETIC]" so it can never be mistaken for a real
customer's words. `data_mode` (see routes_calls.py / routes_dashboard.py)
is what lets the Admin tab preview this data without it ever mixing into the
default "live" view.
"""

import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Call,
    CallAnalysis,
    CallQuality,
    CallStatus,
    ConnectionStatus,
    IssueMention,
    MentionType,
    ScriptAdherence,
    Sentiment,
    Transcript,
)
from app.services import category_service

_MODEL_NAME = "synthetic"
_PREFIX = "[SYNTHETIC]"

_TEAM_CODES = ["BMCSTTA", "BMCSTCE"]
_AGENTS = ["Rahul Sharma", "Priya Verma", "Amit Singh", "Sneha Patel", "Karan Mehta", "Divya Nair"]
_TAGS = [
    "pricing", "response-time", "spare-parts", "communication", "technician-behavior",
    "warranty", "installation", "follow-up", "documentation", "escalation",
]

# Used only if the real taxonomy (mention_categories) hasn't been seeded yet —
# normally category_service.get_known_categories already has plenty to draw
# from, since the seed migration + every real analysis run add to it.
_FALLBACK_CATEGORIES: dict[MentionType, list[str]] = {
    MentionType.NEGATIVE_DRIVER: [
        "Delay in Service Response", "Repeat Issue After Service", "Spare Parts Delay", "Poor Follow-up / No Updates",
    ],
    MentionType.SERVICE_ISSUE: [
        "Hydraulic Issues", "Oil Leakage", "Transmission Issues", "Electrical / Wiring / GPS Issues",
    ],
    MentionType.POSITIVE_THEME: [
        "Technician Behavior", "Dealer Support", "Problem Resolved", "Communication", "Overall Satisfaction / Trust",
    ],
    MentionType.AGENT_COMPLIANCE: [
        "Skipped Greeting Script", "Topic Deviation", "Irrelevant Personal Talk", "Rushed Closing",
    ],
}


def _pool(known: dict[MentionType, list[str]], mention_type: MentionType) -> list[str]:
    return known.get(mention_type) or _FALLBACK_CATEGORIES[mention_type]


def _mention(category: str) -> tuple[str, str, list[str]]:
    quote = f"{_PREFIX} Sample note about {category.lower()}."
    tags = random.sample(_TAGS, k=random.randint(1, 2))
    return category, quote, tags


def _weighted(options: list[tuple[str, float]]) -> str:
    keys = [k for k, _ in options]
    weights = [w for _, w in options]
    return random.choices(keys, weights=weights, k=1)[0]


def generate(db: Session, count: int) -> int:
    """Inserts `count` synthetic calls with realistic, varied data across
    every analysis dimension. Commits once at the end. Returns `count`."""
    known = category_service.get_known_categories(db)
    now = datetime.now(timezone.utc)

    for _ in range(count):
        team_code = random.choice(_TEAM_CODES)
        recording_date = (now - timedelta(days=random.randint(0, 150))).strftime("%Y-%m-%d")
        object_id = uuid.uuid4().hex[:10]

        call = Call(
            gcs_uri=f"synthetic://{team_code}/{object_id}",
            bucket_name="synthetic-data",
            object_name=f"synthetic/{recording_date}/{team_code}/{object_id}.mp3",
            team_code=team_code,
            recording_date=recording_date,
            size_bytes=random.randint(400_000, 3_000_000),
            status=CallStatus.ANALYZED,
            is_synthetic=True,
        )
        db.add(call)
        db.flush()

        outcome = _weighted([("rejected", 0.12), ("usable", 0.88)])

        if outcome == "rejected":
            connection_status = ConnectionStatus[
                _weighted(
                    [
                        ("NO_ANSWER_BUSY", 0.4),
                        ("VOICEMAIL_IVR_ONLY", 0.3),
                        ("SILENT_DEAD_AIR", 0.2),
                        ("DROPPED_AT_GREETING", 0.1),
                    ]
                )
            ]
            db.add(
                Transcript(
                    call_id=call.id,
                    text=f"{_PREFIX} No usable conversation ({connection_status.value.replace('_', ' ')}).",
                    english_text=f"{_PREFIX} No usable conversation ({connection_status.value.replace('_', ' ')}).",
                    language_code="en-IN",
                )
            )
            db.add(
                CallAnalysis(
                    call_id=call.id,
                    call_quality=CallQuality.REJECTED_CORRUPTED,
                    connection_status=connection_status,
                    sentiment=Sentiment.NEUTRAL,
                    sentiment_summary=f"{_PREFIX} No conversation to evaluate.",
                    satisfaction_rating=5,
                    summary=f"{_PREFIX} Call did not result in a real conversation.",
                    model_name=_MODEL_NAME,
                )
            )
            continue

        mood = _weighted([("positive", 0.45), ("neutral", 0.35), ("negative", 0.20)])
        rating = {
            "positive": random.choices([8, 9, 10], weights=[0.2, 0.4, 0.4])[0],
            "neutral": random.choices([6, 7, 8], weights=[0.3, 0.4, 0.3])[0],
            "negative": random.randint(1, 5),
        }[mood]
        sentiment = {"positive": Sentiment.POSITIVE, "neutral": Sentiment.NEUTRAL, "negative": Sentiment.NEGATIVE}[mood]

        call_quality = CallQuality[_weighted([("GOOD_CLEAR", 0.7), ("PARTIAL_USABLE", 0.3)])]
        connection_status = ConnectionStatus[_weighted([("CONNECTED", 0.85), ("DROPPED_DURING_CALL", 0.15)])]
        script_adherence = ScriptAdherence[
            _weighted([("FOLLOWED", 0.7), ("PARTIAL", 0.22), ("NOT_FOLLOWED", 0.08)])
        ]
        agent_name = random.choices([*_AGENTS, None], weights=[*([1] * len(_AGENTS)), 0.3])[0]

        stated_rating = None
        if random.random() < 0.35:
            stated_rating = min(10, max(1, rating + random.choice([-1, 0, 0, 1])))

        db.add(
            Transcript(
                call_id=call.id,
                text=f"{_PREFIX} Placeholder transcript ({mood} call, handled by {agent_name or 'an unidentified agent'}) — asli baat-cheet yahaan hoti.",
                # Deliberately different from `text` so the Calls page's
                # EN / Original toggle is actually exercised by dummy data.
                english_text=f"{_PREFIX} Placeholder transcript for a {mood} call handled by {agent_name or 'an unidentified agent'}.",
                language_code="hi-IN",
            )
        )
        db.add(
            CallAnalysis(
                call_id=call.id,
                call_quality=call_quality,
                connection_status=connection_status,
                sentiment=sentiment,
                sentiment_summary=f"{_PREFIX} Overall {mood} tone.",
                satisfaction_rating=rating,
                customer_stated_rating=stated_rating,
                agent_name=agent_name,
                script_adherence=script_adherence,
                summary=f"{_PREFIX} A {mood} synthetic call for dashboard QA.",
                model_name=_MODEL_NAME,
            )
        )

        def _add_mentions(mention_type: MentionType, min_n: int, max_n: int) -> None:
            pool = _pool(known, mention_type)
            for category in random.sample(pool, k=min(random.randint(min_n, max_n), len(pool))):
                category, quote, tags = _mention(category)
                db.add(IssueMention(call_id=call.id, mention_type=mention_type, category=category, quote=quote, tags=tags))

        if mood in ("neutral", "negative"):
            _add_mentions(MentionType.NEGATIVE_DRIVER, 1, 2)
        if mood == "negative" or random.random() < 0.25:
            _add_mentions(MentionType.SERVICE_ISSUE, 0, 2)
        if mood in ("positive", "neutral"):
            _add_mentions(MentionType.POSITIVE_THEME, 1, 2)
        if script_adherence is not ScriptAdherence.FOLLOWED:
            _add_mentions(MentionType.AGENT_COMPLIANCE, 1, 1)

    db.commit()
    return count


def clear(db: Session) -> int:
    """Deletes every synthetic call (and, via ondelete=CASCADE, its
    transcript/analysis/mentions). Returns how many were removed."""
    ids = list(db.execute(select(Call.id).where(Call.is_synthetic.is_(True))).scalars().all())
    if not ids:
        return 0
    db.query(Call).filter(Call.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    return len(ids)


def counts(db: Session) -> tuple[int, int]:
    """(live_calls, synthetic_calls)."""
    rows = db.execute(select(Call.is_synthetic, func.count()).group_by(Call.is_synthetic)).all()
    by_flag = {is_synthetic: n for is_synthetic, n in rows}
    return by_flag.get(False, 0), by_flag.get(True, 0)
