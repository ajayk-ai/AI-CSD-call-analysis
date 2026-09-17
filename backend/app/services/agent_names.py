"""Canonicalizes agent names extracted by the AI model.

Agent names come from transcribing what was said on the call (see
schemas.analysis.CallAnalysisResult.agent_name), so the same person can be
spelled several different ways across calls — "Gautham", "Gautam", "Goutham",
"Gouthaman" — and, occasionally, the model returns a sentence instead of a
name when none was actually stated ("The agent's name is not mentioned in
the audio."). Both fragment and pollute any breakdown grouped by the raw
agent_name column, so every place that groups or filters by agent should go
through the mapping this module builds instead of comparing the raw value
directly.
"""

from collections import Counter, defaultdict
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CallAnalysis

UNASSIGNED_AGENT = "Unassigned"

# Similarity ratio (difflib.SequenceMatcher, case-insensitive) above which two
# raw spellings are treated as the same person. Tuned against real observed
# variants of one name ("Gautham"/"Gautam" = 0.92, "Gautham"/"Goutham" = 0.86,
# "Goutham"/"Gouthaman" = 0.88, all clustering together transitively) while
# keeping distinct people apart ("Nikita"/"Nita" = 0.80, "Vijayabalaji"/
# "Vijayabharathi" = 0.77, "Sanjana"/"Sanjay" = 0.77).
_FUZZY_THRESHOLD = 0.85

# Substrings seen in extraction failures where the model explained itself
# instead of leaving the field null.
_NOT_A_NAME_MARKERS = ("not mention", "not stat", "not given", "not provided", "unknown", "n/a")


def _looks_like_a_name(raw: str) -> bool:
    lowered = raw.strip().lower()
    if not lowered:
        return False
    if any(marker in lowered for marker in _NOT_A_NAME_MARKERS):
        return False
    # A real name is a word or two; anything this long or wordy is the model
    # explaining itself rather than naming someone.
    return len(raw) <= 30 and raw.count(" ") <= 3


def build_agent_name_map(db: Session) -> dict[str, str]:
    """Raw agent_name (as stored) -> canonical display/grouping name.

    Clusters distinct raw values by string similarity rather than against a
    fixed roster, since the true agent list isn't known in advance. Computed
    fresh per request from the full, unfiltered set of names ever seen
    (deliberately ignoring range/plant/data-mode filters), so the grouping
    doesn't shift depending on which subset of calls the current request
    happens to scope to. O(n^2) pairwise comparisons over a few dozen
    distinct names is inexpensive enough to redo on every call.

    Uses union-find over every pair above the threshold rather than greedily
    assigning each name to the first matching cluster it meets — greedy
    assignment is order-dependent and can split a single person into two
    clusters: e.g. with "Gautham", "Gautam", "Goutham", "Gouthaman", a
    longest-first greedy pass puts "Gouthaman" and "Goutham" together before
    "Gautham" ever gets compared against "Goutham", leaving "Gautham"/
    "Gautam" stranded in a second cluster even though "Gautham"-"Goutham" are
    themselves above the threshold. Union-find merges both clusters as soon
    as any bridging pair links them, regardless of processing order.
    """
    raw_names = db.execute(
        select(CallAnalysis.agent_name).where(CallAnalysis.agent_name.isnot(None)).distinct()
    ).scalars().all()
    counts = Counter(raw_names)

    names = [n for n in counts if _looks_like_a_name(n)]
    mapping: dict[str, str] = {n: UNASSIGNED_AGENT for n in counts if n not in names}

    parent = {n: n for n in names}

    def find(n: str) -> str:
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            if SequenceMatcher(None, a.lower(), b.lower()).ratio() >= _FUZZY_THRESHOLD:
                union(a, b)

    clusters: dict[str, list[str]] = defaultdict(list)
    for name in names:
        clusters[find(name)].append(name)

    for members in clusters.values():
        # Most common spelling wins as the display name; ties broken
        # alphabetically so the choice is deterministic run to run.
        canonical = sorted(members, key=lambda n: (-counts[n], n))[0]
        for member in members:
            mapping[member] = canonical

    return mapping


def canonical_agent(raw: str | None, agent_map: dict[str, str]) -> str:
    if raw is None:
        return UNASSIGNED_AGENT
    return agent_map.get(raw, raw)


def raw_names_for(canonical: str, agent_map: dict[str, str]) -> list[str]:
    """Every raw spelling that canonicalizes to `canonical` — filtering by
    ``CallAnalysis.agent_name.in_(...)`` needs every variant, not just the
    display name that was clicked or selected."""
    matches = [raw for raw, canon in agent_map.items() if canon == canonical]
    # Falls back to matching the value literally if it's not a known raw
    # name (e.g. stale request built from a name no longer in the data).
    return matches or [canonical]
