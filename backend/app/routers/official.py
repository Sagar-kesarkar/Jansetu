"""Protected Officials' Console API Router.

Strict Zero-PII Guarantees:
- Never returns phone numbers, citizen_ref, WhatsApp sender IDs, IVR caller IDs,
  SMS sender IDs, raw audio bytes, or original photographs.
- Exposes scrubbed ward-level places, category, urgency, status, and casework responses.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import CitizenRequest, District, RequestResponse
from app.models.schemas import (
    NOT_ACTIONABLE,
    OPEN_STATUSES,
    STATUS_ORDER,
    LocationHierarchy,
    RequestStatus,
    ResponseOut,
    StatusPatch,
)
from app.models.taxonomy import department_for
from app.services.place import official_place

log = logging.getLogger(__name__)

router = APIRouter(prefix="/official", tags=["official"])


# ---------- Officials Read Schemas (Strictly Zero-PII) ----------

class OfficialRequestOut(BaseModel):
    id: int
    docket_ref: str
    track_token: str | None = None
    category: str
    department: str | None = None
    urgency: int
    title: str | None = None
    summary_en: str
    summary_native: str | None = None
    language: str
    channel: str
    state: str | None = None
    district: str | None = None
    district_code: str | None = None
    place: str | None = None
    has_photo: bool = False
    image_verification: str | None = None
    confidence: float | None = None
    status: str
    triage_reason: str | None = None
    response_count: int = 0
    created_at: datetime

    # ---- one inbound message, several dockets ----
    #
    # Present so the console can *label* a split submission, never so it can merge
    # one. Two problems raised in one sentence go to two departments and are closed
    # on two different days; combining them back into a single row would mean one of
    # the two is worked by a desk that cannot fix it.
    submission_group_id: str | None = None
    issue_index: int = 1
    issue_count: int = 1
    location_status: str | None = None
    clarification_question: str | None = None


class OfficialRequestDetail(OfficialRequestOut):
    raw_text: str | None = None
    transcript: str | None = None
    affected_estimate: int | None = None
    responses: list[ResponseOut] = []


class OfficialDashboardSummary(BaseModel):
    total_requests: int
    open_requests: int
    awaiting_reply: int
    by_status: dict[str, int]
    by_channel: dict[str, int]
    by_category: dict[str, int]
    by_urgency: dict[str, int]
    by_state: dict[str, int]
    filed_last_7_days: int


def _to_official_out(r: CitizenRequest, d: District | None, response_count: int) -> OfficialRequestOut:
    """Format request for officials while stripping all citizen identifiers."""
    hierarchy = LocationHierarchy(
        state=r.loc_state,
        district_or_city=r.loc_district,
        locality=r.loc_locality,
        sector_or_ward=r.loc_ward,
        pin_code=r.loc_pin,
    )
    return OfficialRequestOut(
        id=r.id,
        docket_ref=f"#{r.id}",
        track_token=r.track_token,
        category=r.category,
        department=department_for(r.category),
        urgency=r.urgency,
        title=r.title,
        summary_en=r.summary_en,
        summary_native=r.raw_text,
        language=r.language,
        channel=r.channel,
        state=d.state if d else r.loc_state,
        district=d.name if d else r.loc_district,
        district_code=r.district_code,
        place=official_place(hierarchy, r.location_text),
        has_photo=bool(r.has_photo),
        image_verification=r.image_verification,
        confidence=r.confidence,
        status=r.status,
        triage_reason=r.triage_reason,
        response_count=response_count,
        created_at=r.created_at,
        submission_group_id=r.submission_group_id,
        issue_index=r.issue_index,
        issue_count=r.issue_count,
        location_status=r.location_status,
        clarification_question=r.clarification_question,
    )


_RESPONSE_COUNT = (
    select(func.count(RequestResponse.id))
    .where(RequestResponse.request_id == CitizenRequest.id)
    .scalar_subquery()
)


@router.get("/requests", response_model=list[OfficialRequestOut])
def list_official_requests(
    channel: str | None = Query(None, description="Filter by channel: web, whatsapp, ivr, sms, voice"),
    state: str | None = Query(None, description="Filter by state name"),
    district_code: str | None = Query(None, description="Filter by LGD district code"),
    category: str | None = Query(None, description="Filter by sector category"),
    urgency: int | None = Query(None, ge=1, le=5, description="Filter by exact urgency level"),
    min_urgency: int | None = Query(None, ge=1, le=5, description="Filter by minimum urgency"),
    status: RequestStatus | None = Query(None, description="Filter by casework status"),
    language: str | None = Query(None, description="Filter by language code"),
    date_from: datetime | None = Query(None, description="Filter requests created on or after date"),
    date_to: datetime | None = Query(None, description="Filter requests created on or before date"),
    docket_id: int | None = Query(None, description="Lookup exact docket reference ID"),
    q: str | None = Query(None, min_length=2, description="Search query across summary or scrubbed place"),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[OfficialRequestOut]:
    """List complaints across all channels for officials console."""
    query = db.query(CitizenRequest, District, _RESPONSE_COUNT.label("responses")).outerjoin(
        District, CitizenRequest.district_code == District.code
    )

    if docket_id:
        query = query.filter(CitizenRequest.id == docket_id)
    if channel:
        query = query.filter(CitizenRequest.channel == channel)
    if state:
        query = query.filter(District.state == state)
    if district_code:
        query = query.filter(CitizenRequest.district_code == district_code)
    if category:
        query = query.filter(CitizenRequest.category == category)
    if urgency:
        query = query.filter(CitizenRequest.urgency == urgency)
    if min_urgency:
        query = query.filter(CitizenRequest.urgency >= min_urgency)
    if status:
        query = query.filter(CitizenRequest.status == status.value)
    else:
        # Same default as `routers/requests.py::list_requests`: triaged-invalid and
        # location-less cases are hidden from the working feed and reachable only by
        # asking for them by name — `?status=INVALID`, `?status=NEEDS_LOCATION`. The
        # two surfaces have to agree, or an officer moving between them sees two
        # different backlogs.
        query = query.filter(CitizenRequest.status.notin_(NOT_ACTIONABLE))
    if language:
        query = query.filter(CitizenRequest.language == language)
    if date_from:
        query = query.filter(CitizenRequest.created_at >= date_from)
    if date_to:
        query = query.filter(CitizenRequest.created_at <= date_to)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                CitizenRequest.summary_en.like(like),
                CitizenRequest.raw_text.like(like),
                CitizenRequest.loc_locality.like(like),
                CitizenRequest.loc_district.like(like),
                CitizenRequest.loc_ward.like(like),
                CitizenRequest.loc_pin.like(like),
            )
        )

    rows = query.order_by(CitizenRequest.created_at.desc(), CitizenRequest.id.desc()).limit(limit).offset(offset).all()
    return [_to_official_out(r, d, n) for r, d, n in rows]


@router.get("/requests/{request_id}", response_model=OfficialRequestDetail)
def get_official_request_detail(
    request_id: int,
    db: Session = Depends(get_db),
) -> OfficialRequestDetail:
    """Retrieve detailed casework complaint view."""
    row = db.get(CitizenRequest, request_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"No request with id {request_id}")

    district = db.get(District, row.district_code) if row.district_code else None
    base = _to_official_out(row, district, len(row.responses))

    return OfficialRequestDetail(
        **base.model_dump(),
        raw_text=row.raw_text,
        transcript=row.transcript,
        affected_estimate=row.affected_estimate,
        responses=[ResponseOut.model_validate(r) for r in row.responses],
    )


@router.patch("/requests/{request_id}/status", response_model=OfficialRequestOut)
def update_official_request_status(
    request_id: int,
    payload: StatusPatch,
    db: Session = Depends(get_db),
) -> OfficialRequestOut:
    """Update casework status for a complaint."""
    row = db.get(CitizenRequest, request_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"No request with id {request_id}")

    row.status = payload.status.value
    db.commit()
    db.refresh(row)
    district = db.get(District, row.district_code) if row.district_code else None
    return _to_official_out(row, district, len(row.responses))


@router.get("/dashboard/summary", response_model=OfficialDashboardSummary)
def get_official_dashboard_summary(
    state: str | None = Query(None),
    db: Session = Depends(get_db),
) -> OfficialDashboardSummary:
    """Aggregated summary metrics across all intake channels."""
    def scoped(query):
        if state:
            query = query.outerjoin(District, CitizenRequest.district_code == District.code).filter(
                District.state == state
            )
        return query

    def tally(column) -> dict[str, int]:
        pairs = scoped(db.query(column, func.count(CitizenRequest.id))).group_by(column).all()
        return {str(k): count for k, count in pairs if k is not None}

    total = scoped(db.query(func.count(CitizenRequest.id))).scalar() or 0
    by_status = tally(CitizenRequest.status)

    awaiting = scoped(
        db.query(func.count(CitizenRequest.id)).filter(
            ~exists().where(RequestResponse.request_id == CitizenRequest.id),
            # Nobody is answerable for replying to a test message, nor to a report
            # that has not said where it is. This figure is the one an officer is
            # judged on. Matches `routers/requests.py`.
            CitizenRequest.status.notin_(NOT_ACTIONABLE),
        )
    ).scalar() or 0

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent = scoped(
        db.query(func.count(CitizenRequest.id)).filter(CitizenRequest.created_at >= week_ago)
    ).scalar() or 0

    # Count by state
    state_pairs = (
        db.query(District.state, func.count(CitizenRequest.id))
        .join(CitizenRequest, CitizenRequest.district_code == District.code)
        .group_by(District.state)
        .all()
    )
    by_state = {str(k): count for k, count in state_pairs if k}

    return OfficialDashboardSummary(
        total_requests=total,
        open_requests=sum(count for s, count in by_status.items() if s in OPEN_STATUSES),
        awaiting_reply=awaiting,
        by_status={s: by_status.get(s, 0) for s in STATUS_ORDER},
        by_channel=tally(CitizenRequest.channel),
        by_category=tally(CitizenRequest.category),
        by_urgency=tally(CitizenRequest.urgency),
        by_state=by_state,
        filed_last_7_days=recent,
    )


@router.get("/events/stream")
async def stream_official_events(
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Server-Sent Events (SSE) stream for live updates on incoming complaints."""
    async def event_generator() -> AsyncGenerator[str, None]:
        last_id = db.query(func.max(CitizenRequest.id)).scalar() or 0
        # Rows the cursor has passed but the ticker deliberately did not announce.
        #
        # A live ticker of test messages and adverts trains an officer to ignore the
        # ticker, and an entry nobody can act on does the same — so INVALID and
        # NEEDS_LOCATION rows are held back. They cannot simply be filtered out,
        # though: `last_id` advances past them the moment any later row is announced,
        # and a NEEDS_LOCATION request whose citizen answers ten minutes later would
        # then never appear at all. Held here, it is re-checked on every tick and
        # announced late instead of never.
        deferred: set[int] = set()
        while True:
            await asyncio.sleep(3.0)
            fresh = CitizenRequest.id > last_id
            new_rows = (
                db.query(CitizenRequest, District)
                .outerjoin(District, CitizenRequest.district_code == District.code)
                .filter(or_(fresh, CitizenRequest.id.in_(deferred)) if deferred else fresh)
                .order_by(CitizenRequest.id.asc())
                .all()
            )
            for req, dist in new_rows:
                last_id = max(last_id, req.id)
                if req.status in NOT_ACTIONABLE:
                    # Bounded: a console left open for a week must not accumulate a
                    # set of every message ever flagged. Oldest are simply forgotten,
                    # which costs a late ticker entry and not a row.
                    if len(deferred) < 500:
                        deferred.add(req.id)
                    continue
                deferred.discard(req.id)
                data = {
                    "event": "new_complaint",
                    "id": req.id,
                    "token": req.track_token,
                    "category": req.category,
                    "urgency": req.urgency,
                    "channel": req.channel,
                    "district": dist.name if dist else req.loc_district,
                    "summary_en": req.summary_en,
                    "issue_index": req.issue_index,
                    "issue_count": req.issue_count,
                    "created_at": req.created_at.isoformat() if req.created_at else None,
                }
                yield f"data: {json.dumps(data)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
