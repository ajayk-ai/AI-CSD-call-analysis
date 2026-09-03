"""Durable per-call graph state, so re-analysis doesn't re-transcribe.

The `calls` table already records whether a call finished; what it does not
record is *how far into the analysis* a call got, or what the transcription
node produced. That's the thing worth resuming from: transcription is the only
step that spends audio-input tokens, and it is the step that a KPI change never
invalidates. Checkpointing it means adding, removing or re-running a KPI costs
one cheap text call instead of a full re-transcription of the bucket.

This is a deliberate reversal of the old graph's "no checkpointer" note, which
objected that a checkpointer would have to serialize megabytes of audio per
call. That objection is now designed out rather than argued with: `graph.py`
has no `audio_bytes` state field at all — the transcribe node downloads and
sends within one function — so a checkpoint holds text, never a recording.

Storage is the same Postgres instance the app already uses. LangGraph manages
its own `checkpoints*` tables via `.setup()` and does not participate in
Alembic; that is how the library ships and trying to own those tables in a
migration would fight its own schema versioning.
"""

import logging
import threading

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from app.config import get_settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_checkpointer: BaseCheckpointSaver | None = None
# Held separately from the saver so shutdown can close it: PostgresSaver does
# not own the pool's lifecycle, and leaving it open makes the process hang on
# exit complaining about unstopped worker threads.
_pool = None


def _build_postgres_saver() -> BaseCheckpointSaver:
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg_pool import ConnectionPool

    settings = get_settings()
    pool = ConnectionPool(
        conninfo=settings.libpq_dsn,
        # The pipeline analyzes calls on a ThreadPoolExecutor, and every node
        # boundary is a checkpoint write, so the pool needs to cover the
        # configured concurrency with a little headroom.
        max_size=max(4, settings.analysis_concurrency + 2),
        # autocommit is required by PostgresSaver — it manages its own
        # transactions and pipelining.
        kwargs={"autocommit": True, "prepare_threshold": 0},
        open=True,
    )
    global _pool
    _pool = pool
    saver = PostgresSaver(pool)
    saver.setup()  # idempotent: creates/migrates its own tables
    return saver


def get_checkpointer() -> BaseCheckpointSaver:
    """The process-wide checkpointer, built on first use.

    Falls back to an in-memory saver if Postgres can't be reached. That
    degradation is deliberate: losing cross-process resume is a cost problem,
    but failing to build the checkpointer would be an availability problem, and
    an analysis run that refuses to start is strictly worse than one that has
    to re-transcribe. The warning says exactly what was lost.
    """
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    with _lock:
        if _checkpointer is None:
            try:
                _checkpointer = _build_postgres_saver()
                logger.info("LangGraph checkpointer: Postgres (durable across restarts).")
            except Exception:  # noqa: BLE001 - any failure here degrades, never blocks
                logger.warning(
                    "Could not open the Postgres checkpointer — falling back to in-memory. "
                    "Analysis still works, but transcripts will NOT be reused across restarts, "
                    "so a re-run will pay audio costs again.",
                    exc_info=True,
                )
                _checkpointer = InMemorySaver()
    return _checkpointer


def reset_checkpointer() -> None:
    """Drops the cached instance (closing its pool) so the next call rebuilds
    it. Used on shutdown, by tests, and to recover after the database comes
    back."""
    global _checkpointer, _pool
    with _lock:
        if _pool is not None:
            try:
                _pool.close()
            except Exception:  # noqa: BLE001 - closing must never raise on the way out
                logger.debug("Checkpointer pool did not close cleanly.", exc_info=True)
            _pool = None
        _checkpointer = None
