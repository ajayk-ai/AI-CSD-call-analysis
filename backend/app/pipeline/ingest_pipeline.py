import logging
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
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
from app.pipeline.graph import CallAnalysisState, get_call_analysis_graph, prescreen_reason
from app.pipeline.kpi_registry import ModelTier
from app.schemas.analysis import CallAnalysisResult, IssueMentionResult
from app.services import category_service, gcs_service, kpi_config_service, llm_service

logger = logging.getLogger(__name__)

_PRESCREEN_MODEL_NAME = "prescreen (no model call)"


def _model_label() -> str:
    """What goes in `call_analysis.model_name`.

    A row is no longer the product of a single model, so record both tiers —
    otherwise the audit column would name the cheap extraction model on a row
    whose transcript came from the expensive one.
    """
    return (
        f"{llm_service.model_name_for(ModelTier.TRANSCRIPTION)} (audio) + "
        f"{llm_service.model_name_for(ModelTier.EXTRACTION)} (kpi)"
    )


@dataclass
class PipelineRunSummary:
    found_in_bucket: int = 0
    already_processed: int = 0
    newly_processed: int = 0
    # Subset of newly_processed that never reached the model — see graph.prescreen_reason.
    skipped_by_prescreen: int = 0
    failed: int = 0
    # How many recordings this run was allowed to send to Gemini (None = no cap).
    limit_applied: int | None = None
    # Recordings still waiting after this run — what the *next* click will pick
    # up. Non-zero means the limit stopped the run, not that the bucket is done.
    remaining_pending: int = 0
    errors: list[str] = field(default_factory=list)


def _get_or_create_call(db: Session, blob: gcs_service.AudioBlob) -> tuple[Call, bool]:
    """Returns (call, is_new). Existing ANALYZED calls are left untouched by the caller."""
    existing = db.execute(select(Call).where(Call.gcs_uri == blob.gcs_uri)).scalar_one_or_none()
    if existing:
        return existing, False

    call = Call(
        gcs_uri=blob.gcs_uri,
        bucket_name=blob.bucket_name,
        object_name=blob.object_name,
        team_code=blob.team_code,
        recording_date=blob.recording_date,
        size_bytes=blob.size_bytes,
        status=CallStatus.PENDING,
    )
    db.add(call)
    db.flush()
    return call, True


def _clear_previous_attempt(db: Session, call: Call) -> None:
    """Drops rows from any earlier attempt (a call that previously FAILED
    partway, or is being deliberately re-run) so a retry doesn't duplicate."""
    existing_transcript = db.execute(
        select(Transcript).where(Transcript.call_id == call.id)
    ).scalar_one_or_none()
    if existing_transcript:
        db.delete(existing_transcript)
    existing_analysis = db.execute(
        select(CallAnalysis).where(CallAnalysis.call_id == call.id)
    ).scalar_one_or_none()
    if existing_analysis:
        db.delete(existing_analysis)
    db.query(IssueMention).filter(IssueMention.call_id == call.id).delete()
    db.flush()


def _store_result(db: Session, call: Call, result: CallAnalysisResult, model_name: str) -> None:
    _clear_previous_attempt(db, call)

    db.add(
        Transcript(
            call_id=call.id,
            text=result.transcript,
            english_text=result.transcript_english or None,
            language_code=result.language_code,
        )
    )
    db.add(
        CallAnalysis(
            call_id=call.id,
            # The model's schema enums and the DB's enums are separate types
            # that share their string values — convert, don't pass the raw
            # string: a mapped Enum column resolves plain strings against
            # member *names*, which are uppercase and would not match.
            call_quality=CallQuality(result.call_quality.value),
            connection_status=ConnectionStatus(result.connection_status.value),
            sentiment=Sentiment(result.sentiment.value),
            sentiment_summary=result.sentiment_summary,
            satisfaction_rating=result.satisfaction_rating,
            customer_stated_rating=result.customer_stated_rating,
            agent_name=result.agent_name,
            script_adherence=ScriptAdherence(result.script_adherence.value),
            summary=result.summary,
            raw_model_output=result.model_dump_json(),
            model_name=model_name,
        )
    )

    def _add_mentions(mentions: list[IssueMentionResult], mention_type: MentionType) -> None:
        for mention in mentions:
            db.add(
                IssueMention(
                    call_id=call.id,
                    mention_type=mention_type,
                    category=mention.category,
                    quote=mention.quote,
                    tags=mention.tags,
                )
            )

    _add_mentions(result.negative_drivers, MentionType.NEGATIVE_DRIVER)
    _add_mentions(result.service_issues, MentionType.SERVICE_ISSUE)
    _add_mentions(result.positive_themes, MentionType.POSITIVE_THEME)
    _add_mentions(result.agent_compliance_issues, MentionType.AGENT_COMPLIANCE)


def _store_prescreen_skip(db: Session, call: Call, reason: str) -> None:
    """A prescreened-out call still gets an analysis row, because
    "rejected / corrupted" is exactly the conclusion the model would have
    reached — we just reached it for free. Recording it keeps the call
    counted in the dashboard's call-quality breakdown instead of silently
    vanishing from the denominator."""
    _clear_previous_attempt(db, call)
    db.add(
        CallAnalysis(
            call_id=call.id,
            call_quality=CallQuality.REJECTED_CORRUPTED,
            # Too small to contain speech — never became a conversation, which
            # is exactly what silent_dead_air means for the connection KPI.
            connection_status=ConnectionStatus.SILENT_DEAD_AIR,
            sentiment=Sentiment.NEUTRAL,
            sentiment_summary=reason,
            satisfaction_rating=1,
            summary=reason,
            model_name=_PRESCREEN_MODEL_NAME,
        )
    )


@dataclass(frozen=True)
class _CallJob:
    """Plain snapshot of the fields the graph needs.

    Worker threads must not touch ORM instances: the Session is configured
    with expire_on_commit=True, so reading `call.bucket_name` after a commit
    would trigger a lazy refresh against the shared Session from several
    threads at once. Copying the primitives out on the main thread keeps the
    workers entirely free of DB access.
    """

    call_id: uuid.UUID
    bucket_name: str
    object_name: str
    size_bytes: int | None


def _run_graph(
    job: _CallJob,
    known_categories: dict[MentionType, list[str]],
    known_tags: list[str],
    enabled_keys: frozenset[str],
) -> CallAnalysisState:
    """Runs one call through the graph. Touches no DB session, so this is safe
    to call from a worker thread.

    `thread_id` is the call's own id, which is what makes the checkpointer
    useful: the same call always resumes its own state, so a re-run finds the
    transcript already there and skips straight to whichever KPI nodes are new
    or out of date.

    `known_categories` goes through `configurable` rather than through the
    graph's input state deliberately — it's run-scoped context that changes
    between chunks, and putting it in state would freeze one run's taxonomy
    into the checkpoint.
    """
    return get_call_analysis_graph(enabled_keys).invoke(
        {
            "bucket_name": job.bucket_name,
            "object_name": job.object_name,
            "size_bytes": job.size_bytes,
        },
        config={
            "configurable": {
                "thread_id": str(job.call_id),
                "known_categories": known_categories,
                "known_tags": known_tags,
            }
        },
    )


def _chunks(items: list[Call], size: int) -> list[list[Call]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def run_pipeline(
    db: Session,
    limit: int | None = None,
    force: bool = False,
    on_progress: Callable[[int, int], None] | None = None,
) -> PipelineRunSummary:
    """Scans the bucket and analyzes every call that isn't already ANALYZED.

    Safe to call repeatedly (e.g. from the dashboard's "Run Analysis" button):
    already-analyzed calls are skipped, and one that failed partway last time
    is retried.

    `force=True` re-analyzes calls that are already ANALYZED too — the
    deliberate, manually-triggered path for backfilling new analysis fields
    (added after a KPI is enabled or a spec's version is bumped) onto
    historical calls.

    Note what "re-analyze" now costs: the graph resumes each call from its
    checkpoint, so a forced re-run does NOT re-download or re-transcribe
    anything whose transcript is already stored at the current transcription
    version — it runs only the KPI nodes that are new or stale, on the cheap
    text tier. It is still subject to `limit`, because on a call that has never
    been transcribed (or after a transcription version bump) the full audio
    cost does apply.

    `limit` caps how many recordings this run may **send to Gemini** — a spend
    guard, so `limit=5` proves the whole flow for the price of five recordings
    before committing to the full bucket. `None` falls back to
    `settings.pipeline_run_limit`; 0 means no cap.

    Objects the prescreen gates out cost nothing, so they deliberately do NOT
    consume the budget — they ride along for free and still get recorded, which
    keeps them in the dashboard's call-quality denominator. `limit=5` therefore
    means "5 analyzed recordings", not "5 rows touched".

    `on_progress(processed, total)` is invoked after each call is persisted,
    so a background runner can report progress.

    Calls are processed in concurrent chunks. The known-category taxonomy is
    reloaded between chunks rather than before every single call — within a
    chunk, a category discovered by one call isn't yet visible to its
    siblings. That's the deliberate trade for concurrency; the taxonomy still
    converges chunk over chunk and run over run. Set `analysis_concurrency=1`
    for strict per-call convergence at the cost of wall-clock time.
    """
    settings = get_settings()
    summary = PipelineRunSummary()

    blobs = gcs_service.list_audio_blobs()
    summary.found_in_bucket = len(blobs)

    pending: list[Call] = []
    for blob in blobs:
        call, is_new = _get_or_create_call(db, blob)
        if not force and not is_new and call.status == CallStatus.ANALYZED:
            summary.already_processed += 1
            continue
        pending.append(call)
    db.commit()

    effective_limit = settings.pipeline_run_limit if limit is None else limit
    summary.limit_applied = effective_limit if effective_limit > 0 else None

    if summary.limit_applied is not None:
        budget = summary.limit_applied
        selected: list[Call] = []
        for call in pending:
            if prescreen_reason(call.size_bytes) is not None:
                # Free — concluded from listing metadata, no download, no model
                # call. Never charge it against the budget.
                selected.append(call)
            elif budget > 0:
                selected.append(call)
                budget -= 1
        # Recordings the cap deferred to the next run. (Calls that FAIL below
        # are retried next run too, but they're reported via `failed`.)
        summary.remaining_pending = len(pending) - len(selected)
        pending = selected

    total = len(pending)
    if on_progress:
        on_progress(0, total)

    if not pending:
        return summary

    concurrency = max(1, settings.analysis_concurrency)
    done = 0

    # Read once per run, not per call: toggling a KPI mid-run would otherwise
    # give some calls a different set of nodes than others in the same batch.
    enabled_keys = kpi_config_service.enabled_keys(db)
    logger.info("Analysis KPIs enabled for this run: %s", ", ".join(sorted(enabled_keys)))

    for chunk in _chunks(pending, concurrency):
        known_categories = category_service.get_known_categories(db)
        known_tags = category_service.get_known_tags(db)

        for call in chunk:
            call.status = CallStatus.ANALYZING
        db.commit()

        # Snapshot before dispatching — see _CallJob for why.
        jobs = [_CallJob(c.id, c.bucket_name, c.object_name, c.size_bytes) for c in chunk]

        if concurrency == 1:
            outcomes = [_safe_run(jobs[0], known_categories, known_tags, enabled_keys)]
        else:
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                outcomes = list(
                    executor.map(
                        lambda j: _safe_run(j, known_categories, known_tags, enabled_keys), jobs
                    )
                )

        # Persist serially on this thread — the workers above never touch the
        # Session, so there's no cross-thread sharing to get wrong.
        for call, (state, error) in zip(chunk, outcomes):
            if error is not None:
                db.rollback()
                # logger.error, not .exception — we're outside the except block
                # that caught this; _safe_run handed the exception back to us.
                logger.error("Failed to process %s", call.gcs_uri, exc_info=error)
                call.status = CallStatus.FAILED
                call.error_message = str(error)[:2000]
                db.commit()
                summary.failed += 1
                summary.errors.append(f"{call.object_name}: {error}")
                continue

            try:
                skipped_reason = state.get("skipped_reason") if state else None
                if skipped_reason:
                    _store_prescreen_skip(db, call, skipped_reason)
                    summary.skipped_by_prescreen += 1
                else:
                    # The graph returns plain JSON (see CallAnalysisState.result
                    # for why); this is where it becomes a typed object again.
                    result = CallAnalysisResult.model_validate(state["result"])
                    category_service.register_new_categories(db, result)
                    _store_result(db, call, result, model_name=_model_label())

                call.status = CallStatus.ANALYZED
                db.commit()
                summary.newly_processed += 1
                done += 1
                if on_progress:
                    on_progress(done, total)
            except Exception as exc:  # noqa: BLE001 - one bad call must not stop the batch
                db.rollback()
                logger.exception("Failed to persist %s", call.gcs_uri)
                call.status = CallStatus.FAILED
                call.error_message = str(exc)[:2000]
                db.commit()
                summary.failed += 1
                summary.errors.append(f"{call.object_name}: {exc}")

    return summary


def _safe_run(
    job: _CallJob,
    known_categories: dict[MentionType, list[str]],
    known_tags: list[str],
    enabled_keys: frozenset[str],
) -> tuple[CallAnalysisState | None, Exception | None]:
    """Runs the graph and captures any exception, so that one bad recording
    doesn't tear down the whole thread pool / batch."""
    try:
        return _run_graph(job, known_categories, known_tags, enabled_keys), None
    except Exception as exc:  # noqa: BLE001 - reported per call by the caller
        return None, exc
