from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Call
from app.db.session import get_db
from app.schemas.calls import CallDetailOut, CallListItemOut

router = APIRouter(prefix="/api/calls", tags=["calls"])


@router.get("", response_model=list[CallListItemOut])
def list_calls(db: Session = Depends(get_db), limit: int = 100, offset: int = 0) -> list[Call]:
    stmt = (
        select(Call)
        .options(selectinload(Call.analysis))
        .order_by(Call.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
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
