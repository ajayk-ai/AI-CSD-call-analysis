import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Call, CallAnalysis, CallStatus, IssueMention, MentionType, Transcript
from app.schemas.analysis import CallAnalysisResult, IssueMentionResult
from app.services import call_analysis_service, gcs_service

logger = logging.getLogger(__name__)


@dataclass
class PipelineRunSummary:
    found_in_bucket: int = 0
    already_processed: int = 0
    newly_processed: int = 0
    failed: int = 0
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


def _store_result(db: Session, call: Call, result: CallAnalysisResult, model_name: str) -> None:
    # Clear out any previous attempt's rows (e.g. this call previously FAILED
    # partway, or is being re-run) before writing the fresh ones.
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

    db.add(
        Transcript(
            call_id=call.id,
            text=result.transcript,
            language_code=result.language_code,
        )
    )
    db.add(
        CallAnalysis(
            call_id=call.id,
            call_quality=result.call_quality.value,
            sentiment=result.sentiment.value,
            sentiment_summary=result.sentiment_summary,
            satisfaction_rating=result.satisfaction_rating,
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
                )
            )

    _add_mentions(result.negative_drivers, MentionType.NEGATIVE_DRIVER)
    _add_mentions(result.service_issues, MentionType.SERVICE_ISSUE)
    _add_mentions(result.positive_themes, MentionType.POSITIVE_THEME)


def _process_one(db: Session, call: Call) -> None:
    call.status = CallStatus.ANALYZING
    db.flush()

    settings = get_settings()
    audio_bytes = gcs_service.download_blob_bytes(call.bucket_name, call.object_name)
    mime_type = gcs_service.mime_type_for(call.object_name)
    result = call_analysis_service.analyze_call_audio(audio_bytes, mime_type)

    _store_result(db, call, result, model_name=settings.gemini_model)
    call.status = CallStatus.ANALYZED


def run_pipeline(db: Session) -> PipelineRunSummary:
    """Scans the bucket, and transcribes + analyzes every call that isn't
    already ANALYZED. Safe to call repeatedly (e.g. from a UI "Run Analysis"
    button) — already-analyzed calls are skipped, and a call that failed
    partway last time is retried."""
    summary = PipelineRunSummary()

    blobs = gcs_service.list_audio_blobs()
    summary.found_in_bucket = len(blobs)

    for blob in blobs:
        call, is_new = _get_or_create_call(db, blob)
        db.commit()

        if not is_new and call.status == CallStatus.ANALYZED:
            summary.already_processed += 1
            continue

        try:
            _process_one(db, call)
            db.commit()
            summary.newly_processed += 1
        except Exception as exc:  # noqa: BLE001 - one bad call must not stop the batch
            db.rollback()
            logger.exception("Failed to process %s", blob.gcs_uri)
            call.status = CallStatus.FAILED
            call.error_message = str(exc)[:2000]
            db.commit()
            summary.failed += 1
            summary.errors.append(f"{blob.object_name}: {exc}")

    return summary
