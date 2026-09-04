"""Every LLM prompt used by the analysis pipeline, in one place.

This is the file to open to read or tune what the model is actually asked —
`kpi_registry.py` only wires these strings to a schema/model-tier/version and
should never contain prompt wording itself. One constant per graph node
(`TRANSCRIPTION_PROMPT`, `SENTIMENT_PROMPT`, `ISSUES_PROMPT`,
`COMPLIANCE_PROMPT`), plus the fragments they share, so a wording change or a
new KPI's prompt has exactly one place to land.

Formatting: each `*_PROMPT` is a `str.format()` template. `{transcript}` is
common to every text node; `{negative_categories}` / `{service_categories}` /
`{positive_categories}` / `{compliance_categories}` / `{known_tags}` are filled
in by `KpiSpec.format_prompt()` for the nodes that declare `needs_categories`.
Don't rename a placeholder here without updating `CATEGORY_PLACEHOLDER` in
kpi_registry.py to match.

The wording below is largely the original single monolithic prompt, split
along its own section headings rather than rewritten — it encodes specific
hard-won guidance (the "a dialer artifact is not a resolved customer
interaction" paragraph, the anti-"Other" taxonomy rule) that took real
iterations to get right. Change it deliberately, and bump the owning
`KpiSpec.version` in kpi_registry.py when you do — that's what makes the
change take effect on re-analysis without forcing a full re-transcription.
"""

ANALYST_ROLE = "You are a QA analyst for a heavy-equipment dealership's customer service desk."

# Every text node opens with the transcript. Note it receives the ENGLISH
# transcript: the transcription node has already done the translation work, so
# no downstream node pays to reason across a code-mixed text.
TRANSCRIPT_PREAMBLE = f"""{ANALYST_ROLE} \
Below is the transcript of one customer service call. Read it and answer only the question asked — \
another analyst is handling the other parts of the review.

TRANSCRIPT:
\"\"\"
{{transcript}}
\"\"\"
"""

# Shared by every spec that produces IssueMentionResult lists (issues,
# compliance), so the taxonomy rule can't drift between them.
TAXONOMY_RULE = """\
For each of the category lists below, the same rule applies: reuse an existing category whenever it's a \
reasonable fit — this keeps reporting consistent over time — and only write a new, short, specific label \
when the call genuinely doesn't match anything already listed. Never force a mismatch just to avoid \
creating a new one.

NEVER invent a generic bucket. Category names beginning with or amounting to "Other", "Miscellaneous", \
"General" or "Various" are forbidden — they are always the wrong answer. If a call is about an air \
conditioner, name the category for the air conditioner; if it's about a broken coupling, name the \
coupling. When nothing in the list fits, write a NEW short specific label for what the call is actually \
about. This matters more than it looks: a bucket of unrelated cases tells a reader nothing they can act \
on, and it silently swallows the specific issue that was actually reported.

QUOTE: attach a short verbatim quote from the transcript wherever one exists — it is the evidence for \
the category, and a row without one cannot be checked.

TAGS: attach 1-3 short, lowercase, hyphenated tags naming the concrete dimension of the issue (e.g. \
"pricing", "response-time", "spare-parts"). Tags are how the same underlying problem is found across \
calls that were filed under different categories, so REUSE AN EXISTING TAG whenever one fits rather than \
coining a near-duplicate — "response-time" and "slow-response" as two separate tags help nobody. Tags \
already in use: {known_tags}

Only include a category if the call actually supports it — an empty list is fine and expected for \
calls that don't mention that kind of thing."""


# --- transcription: the only node that receives audio ------------------------

TRANSCRIPTION_PROMPT = f"""{ANALYST_ROLE} \
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
"""


# --- sentiment: text-only, cheap tier -----------------------------------------

SENTIMENT_PROMPT = (
    TRANSCRIPT_PREAMBLE
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
"""
)


# --- issues: text-only, cheap tier --------------------------------------------

ISSUES_PROMPT = (
    TRANSCRIPT_PREAMBLE
    + f"""
{TAXONOMY_RULE}

NEGATIVE DRIVERS (only if a real conversation happened — leave empty for a busy tone, voicemail or dead \
air): for each distinct complaint driver you can identify, existing categories seen so far: \
{{negative_categories}}

SERVICE / MACHINE ISSUES: for each distinct mechanical/technical issue mentioned, existing categories \
seen so far: {{service_categories}}

POSITIVE THEMES: for each distinct thing the customer praised or appreciated, existing categories seen \
so far: {{positive_categories}}
"""
)


# --- compliance: text-only, cheap tier ----------------------------------------

COMPLIANCE_PROMPT = (
    TRANSCRIPT_PREAMBLE
    + f"""
Judge the AGENT's conduct here, not the customer's.

SCRIPT ADHERENCE: whether the agent followed the standard call script — proper greeting, staying on the \
customer's actual issue, proper closing/next-steps. "followed" if the agent hit the standard flow, \
"partial" for minor deviations, "not_followed" if the agent skipped the greeting/closing entirely or \
handled the call in a substantially non-standard way. If no real conversation took place (busy tone, \
voicemail, dead air) there was nothing for the agent to follow — return "followed" and no issues.

{TAXONOMY_RULE}

AGENT COMPLIANCE ISSUES: for each distinct problem with how the AGENT (not the customer) conducted the \
call — topic deviation (wandering off the customer's actual issue), irrelevant talk (personal/unrelated \
conversation), skipped script steps, arguing with the customer, etc. — existing categories seen so far: \
{{compliance_categories}}
"""
)
