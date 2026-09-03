from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import Date, asc, cast, desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Call, CallAnalysis, plant_expr
from app.db.session import get_db
from app.schemas.calls import CallDetailOut, CallListItemOut
from app.services import gcs_service

router = APIRouter(prefix="/api/calls", tags=["calls"])

# Columns the Calls page can sort by. Values on CallAnalysis need the outer
# join below; the rest live on Call directly.
_SORT_COLUMNS = {
    "created_at": Call.created_at,
    "recording_date": Call.recording_date,
    "team_code": Call.team_code,
    "agent_name": CallAnalysis.agent_name,
    "status": Call.status,
    "call_quality": CallAnalysis.call_quality,
    "sentiment": CallAnalysis.sentiment,
    "satisfaction_rating": CallAnalysis.satisfaction_rating,
}

# Same date-fallback rule the dashboard uses: prefer the parsed recording
# date, fall back to when the row was ingested. Keeps date_from/date_to
# consistent with how the dashboard's own range filter reads "when the call
# happened".
_EFFECTIVE_DATE = func.coalesce(cast(Call.recording_date, Date), cast(Call.created_at, Date))


@router.get("", response_model=list[CallListItemOut])
def list_calls(
    db: Session = Depends(get_db),
    limit: int = 100,
    offset: int = 0,
    plant: str | None = Query(
        None,
        pattern="^[A-Za-z]{2}$",
        description="Filter to one plant (last 2 letters of the team code, e.g. 'CE' or 'TA'). Omit for all plants.",
    ),
    sort_by: str = Query("created_at", description=f"One of: {', '.join(_SORT_COLUMNS)}"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    status: str | None = Query(None, description="Filter by call status (pending/analyzing/analyzed/failed)."),
    call_quality: str | None = Query(None),
    sentiment: str | None = Query(None),
    agent_name: str | None = Query(None, description="Exact match on the agent name extracted from the call."),
    rating_min: int | None = Query(None, ge=1, le=10),
    rating_max: int | None = Query(None, ge=1, le=10),
    date_from: date | None = Query(None, description="Inclusive; matches the same effective date as recording_date."),
    date_to: date | None = Query(None, description="Inclusive."),
    search: str | None = Query(None, description="Matches object name, team code, or the analysis summary."),
    data_mode: str = Query(
        "live",
        pattern="^(live|synthetic|all)$",
        description=(
            "'live' (default): real calls only. 'synthetic': only Admin-generated dummy calls, for QA without "
            "touching real data. 'all': both."
        ),
    ),
) -> list[Call]:
    if sort_by not in _SORT_COLUMNS:
        raise HTTPException(status_code=400, detail=f"Unknown sort_by '{sort_by}'. Must be one of: {', '.join(_SORT_COLUMNS)}")

    needs_analysis_join = sort_by in ("agent_name", "call_quality", "sentiment", "satisfaction_rating") or any(
        v is not None for v in (status, call_quality, sentiment, agent_name, rating_min, rating_max, search)
    )
    # status filters on Call.status directly, so it doesn't itself need the join
    # — but keeping it in the trigger list above is harmless (join is a no-op
    # cost-wise here since it's 1:1 and outer).

    stmt = select(Call).options(selectinload(Call.analysis))
    if needs_analysis_join:
        stmt = stmt.outerjoin(Call.analysis)

    if data_mode != "all":
        stmt = stmt.where(Call.is_synthetic.is_(data_mode == "synthetic"))
    if plant is not None:
        stmt = stmt.where(plant_expr == plant.upper())
    if status is not None:
        stmt = stmt.where(Call.status == status)
    if call_quality is not None:
        stmt = stmt.where(CallAnalysis.call_quality == call_quality)
    if sentiment is not None:
        stmt = stmt.where(CallAnalysis.sentiment == sentiment)
    if agent_name is not None:
        stmt = stmt.where(CallAnalysis.agent_name == agent_name)
    if rating_min is not None:
        stmt = stmt.where(CallAnalysis.satisfaction_rating >= rating_min)
    if rating_max is not None:
        stmt = stmt.where(CallAnalysis.satisfaction_rating <= rating_max)
    if date_from is not None:
        stmt = stmt.where(_EFFECTIVE_DATE >= date_from)
    if date_to is not None:
        stmt = stmt.where(_EFFECTIVE_DATE <= date_to)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            Call.object_name.ilike(pattern) | Call.team_code.ilike(pattern) | CallAnalysis.summary.ilike(pattern)
        )

    sort_column = _SORT_COLUMNS[sort_by]
    direction = asc if sort_dir == "asc" else desc
    # NULLs last regardless of direction — an unrated/unassigned call
    # shouldn't jump to the top just because NULL sorts first by default.
    stmt = stmt.order_by(sort_column.is_(None), direction(sort_column))

    stmt = stmt.limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())


@router.get("/{call_id}", response_model=CallDetailOut)
def get_call(call_id: UUID, db: Session = Depends(get_db)) -> Call:
    stmt = (
        select(Call)
        .options(selectinload(Call.analysis), selectinload(Call.transcript), selectinload(Call.mentions))
        .where(Call.id == call_id)
    )
    call = db.execute(stmt).scalar_one_or_none()
    if call is None:
        raise HTTPException(status_code=404, detail="Call not found")
    return call


@router.get("/{call_id}/audio")
def get_call_audio(call_id: UUID, db: Session = Depends(get_db)) -> Response:
    """Streams the original recording back to the browser for the Calls tab's
    inline player. Proxied through the backend (rather than a GCS signed URL)
    since that's the access path the rest of the app already uses — see
    gcs_service.download_blob_bytes, otherwise only called by the pipeline."""
    call = db.execute(select(Call).where(Call.id == call_id)).scalar_one_or_none()
    if call is None:
        raise HTTPException(status_code=404, detail="Call not found")
    if call.is_synthetic:
        raise HTTPException(status_code=404, detail="Synthetic calls have no real audio recording.")
    audio_bytes = gcs_service.download_blob_bytes(call.bucket_name, call.object_name)
    return Response(content=audio_bytes, media_type=gcs_service.mime_type_for(call.object_name))
