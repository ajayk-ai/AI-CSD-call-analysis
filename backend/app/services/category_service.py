import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import IssueMention, MentionCategory, MentionType
from app.schemas.analysis import CallAnalysisResult, IssueMentionResult

KnownCategories = dict[MentionType, list[str]]

# How many distinct tags to offer the model. Enough to converge on, short
# enough not to crowd out the category list in the prompt.
TAG_SUGGESTION_LIMIT = 60

# Category names that are buckets rather than findings. Migration 0006 removed
# the two seeded ones after they measurably crowded out every specific category
# they claimed to summarize; this stops an equivalent being minted back in.
#
# Matched on the whole name, not as a substring, so a genuinely specific
# category is never caught: "Other Mechanical Issues" is rejected while
# "Brother Machine Parts" is not.
_GENERIC_NAME = re.compile(
    r"^(other|misc|miscellaneous|general|unknown|uncategori[sz]ed|various)\b"
    r"|\b(other|misc|miscellaneous)\s*(issues?|problems?|items?|categor(y|ies))\s*$",
    re.IGNORECASE,
)


def is_generic_category(name: str) -> bool:
    """True for catch-all labels like "Other Issues (AC, Electrical, ...)".

    A catch-all full of unrelated cases is useless for reporting — worse than
    useless, since it hides the specific issue that was actually reported. See
    migration 0006 for the measurement that prompted this.
    """
    return bool(_GENERIC_NAME.search(name.strip()))


def get_known_categories(db: Session) -> KnownCategories:
    """Current taxonomy per mention type, fed into the analysis prompt so
    Gemini reuses an existing category whenever one reasonably fits."""
    rows = db.execute(select(MentionCategory.mention_type, MentionCategory.name)).all()

    known: KnownCategories = {mt: [] for mt in MentionType}
    for mention_type, name in rows:
        known[mention_type].append(name)
    for names in known.values():
        names.sort()
    return known


def get_known_tags(db: Session) -> list[str]:
    """The tag vocabulary in use, most-used first.

    Tags need the same convergence treatment categories get, and for the same
    reason. Left unguided the model invents a fresh phrasing every time: the
    current data carries 53 distinct tags across 74 applications, i.e. almost
    every tag is unique, which makes them useless for the cross-referencing
    they exist for. Showing what already exists lets "response-time" be reused
    instead of respelled as "slow-response" on the next call.
    """
    rows = db.execute(
        select(func.unnest(IssueMention.tags).label("tag"), func.count().label("n"))
        .group_by("tag")
        .order_by(func.count().desc())
        .limit(TAG_SUGGESTION_LIMIT)
    ).all()
    return [tag for tag, _ in rows]


def register_new_categories(db: Session, result: CallAnalysisResult) -> None:
    """Adds any category this call used that wasn't already known — this is
    the "grows as new cases arrive" half of the loop: whatever Gemini had to
    invent this time becomes an option the prompt offers next time, so the
    taxonomy converges instead of staying a fixed list or fragmenting into
    one-off labels.

    Generic catch-alls are the one thing never registered: a bucket that gets
    offered back to the model on the next call is a bucket that keeps growing,
    which is exactly how the "Other ..." categories ended up outnumbering every
    specific mechanical category combined.
    """
    existing = {
        (mention_type, name.strip().lower())
        for mention_type, name in db.execute(
            select(MentionCategory.mention_type, MentionCategory.name)
        ).all()
    }

    def _register(mentions: list[IssueMentionResult], mention_type: MentionType) -> None:
        for mention in mentions:
            normalized = mention.category.strip()
            key = (mention_type, normalized.lower())
            if not normalized or key in existing or is_generic_category(normalized):
                continue
            db.add(MentionCategory(mention_type=mention_type, name=normalized, is_seed=False))
            existing.add(key)

    _register(result.negative_drivers, MentionType.NEGATIVE_DRIVER)
    _register(result.service_issues, MentionType.SERVICE_ISSUE)
    _register(result.positive_themes, MentionType.POSITIVE_THEME)
    _register(result.agent_compliance_issues, MentionType.AGENT_COMPLIANCE)
    db.flush()
