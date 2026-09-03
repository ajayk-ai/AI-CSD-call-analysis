from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MentionCategory, MentionType
from app.schemas.analysis import CallAnalysisResult, IssueMentionResult

KnownCategories = dict[MentionType, list[str]]


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


def register_new_categories(db: Session, result: CallAnalysisResult) -> None:
    """Adds any category this call used that wasn't already known — this is
    the "grows as new cases arrive" half of the loop: whatever Gemini had to
    invent this time becomes an option the prompt offers next time, so the
    taxonomy converges instead of staying a fixed list or fragmenting into
    one-off labels."""
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
            if not normalized or key in existing:
                continue
            db.add(MentionCategory(mention_type=mention_type, name=normalized, is_seed=False))
            existing.add(key)

    _register(result.negative_drivers, MentionType.NEGATIVE_DRIVER)
    _register(result.service_issues, MentionType.SERVICE_ISSUE)
    _register(result.positive_themes, MentionType.POSITIVE_THEME)
    _register(result.agent_compliance_issues, MentionType.AGENT_COMPLIANCE)
    db.flush()
