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

The prompt text below is the previous single monolithic prompt, split along its
own section headings. The wording is deliberately preserved rather than
rewritten — it encodes specific hard-won guidance (the "a dialer artifact is
not a resolved customer interaction" paragraph, the anti-"Other" taxonomy rule)
that took real iterations to get right.
"""

from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel

from app.db.models import MentionType
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
    needs_categories: tuple[MentionType, ...] = ()
    tier: ModelTier = ModelTier.EXTRACTION
    default_enabled: bool = True
    required: bool = False
    """Required specs can't be switched off from the Admin page — currently
    just transcription, since every other node reads its output."""

    def format_prompt(self, transcript: str, known_categories: dict[MentionType, list[str]]) -> str:
        values: dict[str, str] = {"transcript": transcript}
        for mention_type in self.needs_categories:
            names = known_categories.get(mention_type) or []
            values[CATEGORY_PLACEHOLDER[mention_type]] = (
                ", ".join(names) if names else "(none recorded yet — propose the first one)"
            )
        return self.prompt.format(**values)


# --- Shared prompt fragments -------------------------------------------------

# Used by every spec that produces IssueMentionResult lists, so the taxonomy
# rule can't drift between them.
_TAXONOMY_RULE = """\
For each of the category lists below, the same rule applies: reuse an existing category whenever it's a \
reasonable fit — this keeps reporting consistent over time — and only write a new, short, specific label \
when the call genuinely doesn't match anything already listed. Never force a mismatch just to avoid \
creating a new one, and — just as important — never reach for a generic/"Other"-sounding category as a \
shortcut when a more specific label (existing or new) actually describes the case. A generic bucket is \
only acceptable as a last resort when the case truly matches nothing recognizable; prefer minting a new, \
specific category over collapsing distinct issues into a catch-all, since a catch-all full of unrelated \
cases is useless for reporting. Where possible, attach a short verbatim quote, and attach 1-3 short, \
specific tags (e.g. "pricing", "response-time", "spare-parts") describing the concrete dimension of the \
issue, so it can be cross-referenced against other calls even when its category differs.

Only include a category if the call actually supports it — an empty list is fine and expected for \
calls that don't mention that kind of thing."""

_ANALYST_ROLE = "You are a QA analyst for a heavy-equipment dealership's customer service desk."

# Every text node opens with the transcript. Note it receives the ENGLISH
# transcript: the transcription node has already done the translation work, so
# no downstream node pays to reason across a code-mixed text.
_TRANSCRIPT_PREAMBLE = f"""{_ANALYST_ROLE} \
Below is the transcript of one customer service call. Read it and answer only the question asked — \
another analyst is handling the other parts of the review.

TRANSCRIPT:
\"\"\"
{{transcript}}
\"\"\"
"""


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
    prompt=f"""{_ANALYST_ROLE} \
Listen to the attached call recording and write down what is on it, along with the few judgements that \
require actually hearing the audio.

TRANSCRIPT: produce a full verbatim transcript. If the call is code-mixed (e.g. Hindi/English), \
transcribe it as spoken rather than translating — this field is the record of what was actually said.

ENGLISH TRANSCRIPT: separately, render the same conversation fully in English. If the call was already \
entirely in English this is the same text. If it was code-mixed or in another language, translate it \
faithfully — keep speaker turns and meaning, don't summarize or clean up the customer's complaints. \
Everything downstream reads THIS version, so it needs to be complete, not a gist.

AGENT NAME: if the agent explicitly states their own name anywhere in the call — almost always in the \
opening ("This is Rahul from Bull Machine service...", "Rahul speaking") — extract it as a clean, \
proper-case name with no titles or filler ("Rahul", not "this is Rahul sir"). If the agent never states \
a name, leave this null. Do not guess a name from context.

CALL QUALITY: this is about the RECORDING only — "good_clear" if the audio is coherent and clearly \
usable, "partial_usable" if parts are noisy/inaudible but the gist is still analyzable, \
"rejected_corrupted" if the audio itself is broken, silent, or too short to make out anything at all. \
Whether an actual conversation took place is a SEPARATE question — see CONNECTION STATUS below. A call \
that connects, has clean audio, and still turns out to be a busy tone or voicemail is "good_clear" \
audio with connection_status "no_answer_busy" or "voicemail_ivr_only" — not rejected_corrupted.

CONNECTION STATUS: whether the call itself connected and became a real conversation, independent of \
recording clarity.
  - "connected": a real conversation between agent and customer happened, start to finish (even if it \
was later cut short mid-call — see dropped_during_call).
  - "dropped_during_call": the conversation started normally but was cut off partway through, e.g. by a \
network/signal issue — there IS real conversation content to analyze up to that point.
  - "dropped_at_greeting": the call connects and the agent starts the greeting, but it cuts off before \
the customer says anything of substance — effectively no conversation happened.
  - "no_answer_busy": a busy tone, ringing tone, or an automated network message ("the number you have \
dialed is currently busy", "the person you are calling is not answering").
  - "voicemail_ivr_only": a voicemail greeting or an IVR menu with no human on the line.
  - "silent_dead_air": the line connects but there is nothing but silence/dead air — a technical/network \
problem, not a corrupted recording (the recording itself may be perfectly clear).
This is easy to get wrong because the recording often sounds clean, which tempts you to wave it through \
as a normal call. Don't. A dialer artifact or a dropped connection is not a resolved customer \
interaction, and mislabeling one silently drags down every average on the report.
""",
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
    prompt=_TRANSCRIPT_PREAMBLE
    + """
SENTIMENT: the customer's overall sentiment — "positive", "neutral", or "negative".

SATISFACTION RATING: your best ESTIMATE of the customer's satisfaction, 1 (furious/unresolved) to 10 \
(delighted). Use 9-10 for a genuinely satisfied customer, 8 for a borderline/lukewarm case (no real \
complaint, but not delighted either — "on the fence"), and 7 or below for anyone not satisfied. Pick the \
number that puts the call on the correct side of those lines rather than defaulting to the middle. If \
the transcript shows no real conversation took place — a busy tone, voicemail, dead air, or a call that \
cut off during the greeting — there is no customer opinion to measure; the reporting layer discards the \
rating for those calls, so just return 5 and don't try to infer a mood from silence.

CUSTOMER STATED RATING: separate from your estimate above. ONLY fill this in if the customer explicitly \
says an actual number out loud on the call — e.g. the agent asks "on a scale of 1 to 10..." and the \
customer answers with a number. Leave it null in every other case, including when the customer merely \
says they're "happy" or "unhappy" without a number. Do not infer a number from tone — that is what \
satisfaction_rating above is for.

SUMMARY: two to three sentences on what actually happened on the call.
""",
)


ISSUES = KpiSpec(
    key="issues",
    label="Issues & Positive Themes",
    description=(
        "Complaint drivers, service/machine issues and things the customer praised, each with a quote "
        "and tags. Drives the two ranked issue tables and the Key Insights correlations."
    ),
    version="v1",
    schema=IssuesResult,
    needs_categories=(
        MentionType.NEGATIVE_DRIVER,
        MentionType.SERVICE_ISSUE,
        MentionType.POSITIVE_THEME,
    ),
    prompt=_TRANSCRIPT_PREAMBLE
    + f"""
{_TAXONOMY_RULE}

NEGATIVE DRIVERS (only if a real conversation happened — leave empty for a busy tone, voicemail or dead \
air): for each distinct complaint driver you can identify, existing categories seen so far: \
{{negative_categories}}

SERVICE / MACHINE ISSUES: for each distinct mechanical/technical issue mentioned, existing categories \
seen so far: {{service_categories}}

POSITIVE THEMES: for each distinct thing the customer praised or appreciated, existing categories seen \
so far: {{positive_categories}}
""",
)


COMPLIANCE = KpiSpec(
    key="compliance",
    label="Agent Script Compliance",
    description=(
        "Whether the agent followed the standard call script, and any specific behaviour issues "
        "(topic deviation, irrelevant talk, skipped steps). Drives the Compliance card and table."
    ),
    version="v1",
    schema=ComplianceResult,
    needs_categories=(MentionType.AGENT_COMPLIANCE,),
    prompt=_TRANSCRIPT_PREAMBLE
    + f"""
Judge the AGENT's conduct here, not the customer's.

SCRIPT ADHERENCE: whether the agent followed the standard call script — proper greeting, staying on the \
customer's actual issue, proper closing/next-steps. "followed" if the agent hit the standard flow, \
"partial" for minor deviations, "not_followed" if the agent skipped the greeting/closing entirely or \
handled the call in a substantially non-standard way. If no real conversation took place (busy tone, \
voicemail, dead air) there was nothing for the agent to follow — return "followed" and no issues.

{_TAXONOMY_RULE}

AGENT COMPLIANCE ISSUES: for each distinct problem with how the AGENT (not the customer) conducted the \
call — topic deviation (wandering off the customer's actual issue), irrelevant talk (personal/unrelated \
conversation), skipped script steps, arguing with the customer, etc. — existing categories seen so far: \
{{compliance_categories}}
""",
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
