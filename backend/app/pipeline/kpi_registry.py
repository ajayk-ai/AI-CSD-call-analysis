"""The declarative list of analysis steps the graph is built from.

Adding a KPI to this dashboard should be adding an entry to `KPI_SPECS` — not
editing the graph, the pipeline, or the persistence layer. `graph.py` reads
this registry and wires one node per spec; `kpi_config_service` reads it to
decide what the Admin toggles show. Nothing else knows the list.

Three things make that work:

* **One structured-output schema per spec.** A node's schema is its whole
  contract, so nodes neither see nor depend on each other's fields.
* **A `version` per spec.** Every node checks, before doing anything, whether
  the checkpoint already holds its output at the current version. Bumping one
  spec's version therefore recomputes exactly that node and nothing else —
  which, since the transcription node is the only one that touches audio, is
  what makes changing a KPI cost cents instead of a full re-transcription.
* **A `tier` per spec.** Only the transcription node needs the strong,
  audio-capable model. Everything downstream reasons over text the transcription
  node already wrote down, and runs on the cheapest tier.

This file only wires prompt -> schema -> tier -> version. The prompt text
itself lives in `prompts.py` — open that file to read or edit what a node
actually asks the model.
"""

from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel

from app.db.models import MentionType
from app.pipeline import prompts
from app.schemas.analysis import (
    ComplianceResult,
    IssuesResult,
    SentimentResult,
    TranscriptionResult,
)


class ModelTier(str, Enum):
    """Which model a node runs on. See config.gemini_transcription_model /
    gemini_extraction_model for what each resolves to and why."""

    TRANSCRIPTION = "transcription"  # strong, audio-capable — one node only
    EXTRACTION = "extraction"  # cheap, text-only — every KPI node


# The prompt placeholder each mention type's known-category list is injected as.
# Keep in sync with the `{negative_categories}` / `{service_categories}` /
# `{positive_categories}` / `{compliance_categories}` placeholders in prompts.py.
CATEGORY_PLACEHOLDER: dict[MentionType, str] = {
    MentionType.NEGATIVE_DRIVER: "negative_categories",
    MentionType.SERVICE_ISSUE: "service_categories",
    MentionType.POSITIVE_THEME: "positive_categories",
    MentionType.AGENT_COMPLIANCE: "compliance_categories",
}


@dataclass(frozen=True)
class KpiSpec:
    key: str
    """Stable identifier. Doubles as the graph node name, the state slot, the
    Admin toggle's config key and the `kpi_versions` key on a stored result —
    so renaming one orphans its checkpointed output (which then recomputes).
    """

    label: str
    description: str
    version: str
    """Bump this to invalidate ONLY this node's cached output."""

    schema: type[BaseModel]
    prompt: str
    """A `str.format()` template from prompts.py — see that file for the
    placeholders each node's prompt expects."""

    needs_categories: tuple[MentionType, ...] = ()
    tier: ModelTier = ModelTier.EXTRACTION
    default_enabled: bool = True
    required: bool = False
    """Required specs can't be switched off from the Admin page — currently
    just transcription, since every other node reads its output."""

    def format_prompt(
        self,
        transcript: str,
        known_categories: dict[MentionType, list[str]],
        known_tags: list[str] | None = None,
    ) -> str:
        values: dict[str, str] = {"transcript": transcript}
        for mention_type in self.needs_categories:
            names = known_categories.get(mention_type) or []
            values[CATEGORY_PLACEHOLDER[mention_type]] = (
                ", ".join(names) if names else "(none recorded yet — propose the first one)"
            )
        if self.needs_categories:
            values["known_tags"] = (
                ", ".join(known_tags) if known_tags else "(none recorded yet — propose the first ones)"
            )
        return self.prompt.format(**values)


# --- The specs ---------------------------------------------------------------

TRANSCRIPTION = KpiSpec(
    key="transcription",
    label="Transcription & Audio Facts",
    description=(
        "The only step that receives the recording. Produces the verbatim and English transcripts plus "
        "the judgements that need the audio itself: agent name, recording quality and connection status."
    ),
    version="v1",
    schema=TranscriptionResult,
    tier=ModelTier.TRANSCRIPTION,
    required=True,
    prompt=prompts.TRANSCRIPTION_PROMPT,
)


SENTIMENT = KpiSpec(
    key="sentiment",
    label="Sentiment & Satisfaction",
    description=(
        "Customer sentiment, the AI-estimated satisfaction rating, any rating the customer stated out "
        "loud, and the call summary. Drives the Sentiment, Satisfaction and Trend cards."
    ),
    version="v1",
    schema=SentimentResult,
    prompt=prompts.SENTIMENT_PROMPT,
)


ISSUES = KpiSpec(
    key="issues",
    label="Issues & Positive Themes",
    description=(
        "Complaint drivers, service/machine issues and things the customer praised, each with a quote "
        "and tags. Drives the two ranked issue tables and the Key Insights correlations."
    ),
    # v2: bans generic "Other ..." categories outright and feeds the existing
    # tag vocabulary back in, after the seeded catch-alls were measured
    # out-competing every specific mechanical category (see migration 0006).
    version="v2",
    schema=IssuesResult,
    needs_categories=(
        MentionType.NEGATIVE_DRIVER,
        MentionType.SERVICE_ISSUE,
        MentionType.POSITIVE_THEME,
    ),
    prompt=prompts.ISSUES_PROMPT,
)


COMPLIANCE = KpiSpec(
    key="compliance",
    label="Agent Script Compliance",
    description=(
        "Whether the agent followed the standard call script, and any specific behaviour issues "
        "(topic deviation, irrelevant talk, skipped steps). Drives the Compliance card and table."
    ),
    # v2: shares the reworded taxonomy rule in prompts.py.
    version="v2",
    schema=ComplianceResult,
    needs_categories=(MentionType.AGENT_COMPLIANCE,),
    prompt=prompts.COMPLIANCE_PROMPT,
)


KPI_SPECS: tuple[KpiSpec, ...] = (TRANSCRIPTION, SENTIMENT, ISSUES, COMPLIANCE)

SPECS_BY_KEY: dict[str, KpiSpec] = {spec.key: spec for spec in KPI_SPECS}

# Everything except transcription — i.e. the nodes that fan out from it, run on
# the cheap tier over text, and can be toggled.
EXTRACTION_SPECS: tuple[KpiSpec, ...] = tuple(
    spec for spec in KPI_SPECS if spec.tier is ModelTier.EXTRACTION
)


def default_enabled_keys() -> set[str]:
    return {spec.key for spec in KPI_SPECS if spec.default_enabled or spec.required}
