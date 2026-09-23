"""The casework side of the API — what the officials' console reads and writes.

The hotspot and recommendation endpoints answer "where should the country spend
next". These answer the question a district officer actually has open on their
screen: what came in, from where, over which channel, when, and has anyone
replied yet.

Two things are deliberate here.

Replying never requires knowing who the citizen is. A reply is addressed to the
same opaque `citizen_ref` the request carried, and handed to the channel adapter
to route. That keeps `docs/DPG_COMPLIANCE.md` indicator 7 true — nothing in this
schema can re-identify a citizen — while still closing the loop, which is the
whole point of a feedback platform that expects to be trusted twice.

Nothing in this module writes a number that reaches a ranking. Status changes and
replies are casework state; `app/analytics/` never reads them. An officer marking
a case RESOLVED must not be able to move a district up or down the priority list,
or the ranking becomes a thing to be managed rather than measured.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import CitizenRequest, District, RequestResponse
from app.i18n.languages import LANGUAGES
from app.models.schemas import (
    NOT_ACTIONABLE,
    OPEN_STATUSES,
    STATUS_ORDER,
    CitizenRequestOut,
    LocationHierarchy,
    RequestDetail,
    RequestStats,
    RequestStatus,
    ResponseIn,
    ResponseOut,
    SiblingRequest,
    StatusPatch,
)
from app.services import evidence
from app.services.place import district_label, official_place
from app.services.translate import translate

log = logging.getLogger(__name__)

router = APIRouter(prefix="/requests", tags=["requests"])

#: Scalar subquery rather than a join with GROUP BY. The list view needs one
#: number per row and a grouped join would collapse rows whose district is NULL,
#: which is exactly the set an officer most needs to see — an unresolved location
#: is a request that will never reach a hotspot.
_RESPONSE_COUNT = (
    select(func.count(RequestResponse.id))
    .where(RequestResponse.request_id == CitizenRequest.id)
    .scalar_subquery()
)


def _as_utc(value: datetime) -> datetime:
    """SQLite gives datetimes back without tzinfo. Treat those as UTC, which is
    what `models._now` wrote, instead of letting a naive/aware comparison raise."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


@router.get("", response_model=list[CitizenRequestOut])
def list_requests(
    state: str | None = Query(None),
    district_code: str | None = Query(None),
    category: str | None = Query(None),
    language: str | None = Query(None),
    channel: str | None = Query(None),
    status: list[RequestStatus] | None = Query(
        None,
        description=(
            "Casework statuses to include. Repeatable: "
            "?status=RESOLVED&status=REJECTED. Omit for the working queue, which "
            "excludes triaged-invalid cases."
        ),
    ),
    citizen_ref: str | None = Query(None, description="Show one reporter's thread"),
    min_urgency: int | None = Query(None, ge=1, le=5),
    unanswered: bool = Query(False, description="Only cases with no official reply yet"),
    q: str | None = Query(None, min_length=2, description="Substring of the original text, summary or place"),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[CitizenRequestOut]:
    rows = db.query(CitizenRequest, District, _RESPONSE_COUNT.label("responses")).outerjoin(
        District, CitizenRequest.district_code == District.code
    )
    if state:
        rows = rows.filter(District.state == state)
    if district_code:
        rows = rows.filter(CitizenRequest.district_code == district_code)
    if category:
        rows = rows.filter(CitizenRequest.category == category)
    if language:
        rows = rows.filter(CitizenRequest.language == language)
    if channel:
        rows = rows.filter(CitizenRequest.channel == channel)
    if status:
        rows = rows.filter(CitizenRequest.status.in_([s.value for s in status]))
    else:
        # Two kinds of row are hidden unless asked for by name, and both are still
        # one query away — `?status=INVALID`, `?status=NEEDS_LOCATION` — which is
        # what makes the exclusion discoverable rather than a filter nobody can see.
        #
        # A triaged-invalid case is hidden because a test message is not work. A
        # NEEDS_LOCATION case is hidden because it is not *yet* work: it names no
        # place, so there is no crew to send and no district to send them to, and
        # leaving it in the working queue would put a row an officer cannot act on
        # at the top of a list sorted by urgency. It stays fully readable, keeps its
        # token, and comes back the moment the citizen answers.
        rows = rows.filter(CitizenRequest.status.notin_(NOT_ACTIONABLE))
    if citizen_ref:
        rows = rows.filter(CitizenRequest.citizen_ref == citizen_ref)
    if min_urgency:
        rows = rows.filter(CitizenRequest.urgency >= min_urgency)
    if unanswered:
        rows = rows.filter(
            ~exists().where(RequestResponse.request_id == CitizenRequest.id)
        )
    if q:
        # Searching raw_text as well as the English summary is what makes this
        # usable in the field: an officer who knows the complaint mentioned a
        # specific canal or school will have heard it in the citizen's language,
        # not in our paraphrase of it.
        #
        # `location_text` is deliberately NOT searched, though it is indexed and
        # would be the obvious third column. It holds the citizen's raw line,
        # which the console is not served (see `_to_out`), and a substring search
        # over a hidden field leaks it a character at a time: an officer who
        # suspects a house number can confirm it by whether the row comes back.
        # The scrubbed levels give the same field usefulness without that.
        like = f"%{q}%"
        rows = rows.filter(or_(
            CitizenRequest.raw_text.like(like),
            CitizenRequest.summary_en.like(like),
            CitizenRequest.loc_locality.like(like),
            CitizenRequest.loc_district.like(like),
            CitizenRequest.loc_ward.like(like),
            CitizenRequest.loc_pin.like(like),
        ))

    result = (
        rows.order_by(CitizenRequest.created_at.desc(), CitizenRequest.id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [_to_out(r, d, n) for r, d, n in result]


@router.get("/stats", response_model=RequestStats)
def request_stats(
    state: str | None = Query(None),
    category: str | None = Query(None),
    db: Session = Depends(get_db),
) -> RequestStats:
    """Counters over the whole filtered set, not over the returned page.

    Declared before `/{request_id}` on purpose: FastAPI matches routes in
    declaration order, and an int path parameter would reject "stats" with a 422
    that gives no hint about route ordering.
    """
    def scoped(query):
        if state or category:
            query = query.outerjoin(District, CitizenRequest.district_code == District.code)
            if state:
                query = query.filter(District.state == state)
            if category:
                query = query.filter(CitizenRequest.category == category)
        return query

    def tally(column) -> dict[str, int]:
        pairs = scoped(db.query(column, func.count(CitizenRequest.id))).group_by(column).all()
        return {str(key): count for key, count in pairs}

    total = scoped(db.query(func.count(CitizenRequest.id))).scalar() or 0
    by_status = tally(CitizenRequest.status)

    awaiting = scoped(
        db.query(func.count(CitizenRequest.id)).filter(
            ~exists().where(RequestResponse.request_id == CitizenRequest.id),
            # "Action required" is the number an officer is answerable for, and
            # nobody is answerable for replying to a test message, or to a report
            # that has not yet said where it is. Counting either here would put work
            # nobody can do into the one figure on the screen that is meant to say
            # how much real work is outstanding. NEEDS_LOCATION rows stay countable
            # as `by_status["NEEDS_LOCATION"]`, which is what the console's "Needs
            # citizen input" tab reads — excluded from the work figure, not hidden.
            CitizenRequest.status.notin_(NOT_ACTIONABLE),
        )
    ).scalar() or 0

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent = scoped(
        db.query(func.count(CitizenRequest.id)).filter(CitizenRequest.created_at >= week_ago)
    ).scalar() or 0

    oldest = scoped(
        db.query(func.min(CitizenRequest.created_at)).filter(
            CitizenRequest.status.in_(OPEN_STATUSES)
        )
    ).scalar()
    oldest_days = (
        round((datetime.now(timezone.utc) - _as_utc(oldest)).total_seconds() / 86400, 1)
        if oldest else None
    )

    return RequestStats(
        total=total,
        open=sum(count for s, count in by_status.items() if s in OPEN_STATUSES),
        awaiting_first_reply=awaiting,
        # Every declared status is present with a zero rather than absent, so the
        # console can render a stable set of columns instead of one that appears
        # and disappears as the backlog moves.
        by_status={s: by_status.get(s, 0) for s in STATUS_ORDER},
        by_channel=tally(CitizenRequest.channel),
        by_language=tally(CitizenRequest.language),
        by_urgency=tally(CitizenRequest.urgency),
        filed_last_7_days=recent,
        oldest_open_days=oldest_days,
    )


@router.get("/{request_id}", response_model=RequestDetail)
def get_request(request_id: int, db: Session = Depends(get_db)) -> RequestDetail:
    row = db.get(CitizenRequest, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No request with id {request_id}")

    district = db.get(District, row.district_code) if row.district_code else None
    base = _to_out(row, district, len(row.responses))

    siblings: list[SiblingRequest] = []
    if row.citizen_ref:
        others = (
            db.query(CitizenRequest)
            .filter(CitizenRequest.citizen_ref == row.citizen_ref, CitizenRequest.id != row.id)
            .order_by(CitizenRequest.created_at.desc())
            .limit(20)
            .all()
        )
        siblings = [
            SiblingRequest(
                id=o.id, category=o.category, urgency=o.urgency, status=o.status,
                summary_en=o.summary_en, created_at=o.created_at,
            )
            for o in others
        ]

    return RequestDetail(
        **base.model_dump(),
        affected_estimate=row.affected_estimate,
        transcript=row.transcript,
        responses=[ResponseOut.model_validate(r) for r in row.responses],
        from_same_reporter=siblings,
    )


@router.get(
    "/{request_id}/photo",
    responses={
        200: {"content": {"image/jpeg": {}}, "description": "The citizen's photograph"},
        404: {"description": "No such request, or no photograph on file"},
    },
)
def get_request_photo(
    request_id: int,
    download: bool = Query(
        False, description="Send as an attachment named after the tracking token"
    ),
    db: Session = Depends(get_db),
) -> FileResponse:
    """The photograph attached to one case.

    The only route to the bytes. `services/evidence.py` writes them outside any
    statically served directory precisely so that this function — which can check
    the request exists — is the sole way in, rather than a `StaticFiles` mount that
    would make every photograph in the system enumerable from one guessed filename.

    `download=1` sets `Content-Disposition: attachment` with the case's tracking
    token as the filename, which is what puts `JS-GDDV-TAXX.jpg` on an officer's
    desktop instead of `photo.jpg`. It has to happen server-side: an `<a download>`
    attribute is ignored by browsers on a cross-origin URL, and the console is
    served from a different port to the API.

    Both failure modes answer 404 with the same shape. A row with `has_photo` true
    and no file is a real case — anything filed before retention existed — and it is
    the console's job to say "attached, not retained", not this route's job to
    invent a distinction in a status code.
    """
    row = db.get(CitizenRequest, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No request with id {request_id}")

    path = evidence.resolve(row.photo_path)
    if path is None:
        raise HTTPException(status_code=404, detail="No photograph on file for this request")

    stored = row.photo_path or ""
    extension = stored.rsplit(".", 1)[-1]
    # Named by tracking token, falling back to the docket number only if a row
    # somehow has a file and no token. Never the citizen's original filename: a
    # phone names photos `IMG_20260823_110815.jpg`, which is a precise capture
    # time, and that is metadata this project does not otherwise keep.
    filename = f"{row.track_token or f'docket-{row.id}'}.{extension}"
    return FileResponse(
        path,
        media_type=evidence.media_type(stored),
        # `filename=` alone would always send `attachment`. Inline is what lets the
        # console show the photograph next to the description it corroborates,
        # which is the point of retaining it at all.
        headers={
            "Content-Disposition": (
                f'{"attachment" if download else "inline"}; filename="{filename}"'
            ),
            # An officer will open the same docket repeatedly while working a case.
            # Private, because this is one citizen's photograph and must not sit in
            # a shared proxy cache.
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.post("/{request_id}/responses", response_model=ResponseOut, status_code=201)
def add_response(
    request_id: int,
    payload: ResponseIn,
    db: Session = Depends(get_db),
) -> ResponseOut:
    """Record an official reply, translated into the language the citizen used.

    The translation is the part worth pausing on. A reply written in English and
    delivered in English to someone who filed in Odia is not an answer, it is a
    receipt. Gemini does that translation on the way out, mirroring what it does
    on the way in — and if there is no key, `translate` returns the text
    unchanged and `body_native` stays NULL, so the console can say the reply went
    out untranslated rather than implying it did not.
    """
    row = db.get(CitizenRequest, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No request with id {request_id}")

    body_native: str | None = None
    if payload.translate and row.language and row.language != "en":
        if row.language not in LANGUAGES:
            log.warning("Request %s has unknown language %r; skipping translation", row.id, row.language)
        else:
            translated = translate(payload.body_en, target=row.language, source="en")
            # `translate` returns its input unchanged when Gemini is unavailable.
            # Storing that would claim a translation that never happened.
            if translated and translated.strip() != payload.body_en.strip():
                body_native = translated.strip()

    previous = row.status
    # A reply is itself an acknowledgement. Leaving a case at NEW after an officer
    # has written to the citizen would make the queue lie about what has been done.
    next_status = payload.new_status.value if payload.new_status else (
        RequestStatus.ACKNOWLEDGED.value if previous == RequestStatus.NEW.value else previous
    )

    reply = RequestResponse(
        request_id=row.id,
        body_en=payload.body_en.strip(),
        body_native=body_native,
        language=row.language,
        responder_desk=payload.responder_desk.strip(),
        status_before=previous,
        status_after=next_status,
        delivery_channel=row.channel,
        delivery_state="queued",
    )
    row.status = next_status
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return ResponseOut.model_validate(reply)


@router.patch("/{request_id}/status", response_model=CitizenRequestOut)
def set_status(
    request_id: int,
    payload: StatusPatch,
    db: Session = Depends(get_db),
) -> CitizenRequestOut:
    row = db.get(CitizenRequest, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No request with id {request_id}")

    previous = row.status
    row.status = payload.status.value
    if previous != row.status:
        db.add(RequestResponse(
            request_id=row.id,
            body_en=f"Status updated from {previous.replace('_', ' ').title()} to {payload.status.value.replace('_', ' ').title()}.",
            body_native=None,
            language=row.language or "en",
            responder_desk="Administration Desk",
            status_before=previous,
            status_after=row.status,
            delivery_channel=row.channel or "web",
            delivery_state="delivered",
        ))
    db.commit()
    db.refresh(row)
    district = db.get(District, row.district_code) if row.district_code else None
    return _to_out(row, district, len(row.responses))


@router.patch("/{request_id}/restore", response_model=CitizenRequestOut)
def restore_request(request_id: int, db: Session = Depends(get_db)) -> CitizenRequestOut:
    """Overrule triage: put a flagged case back into the working queue.

    A separate route rather than `PATCH /status` with `NEW`, for two reasons.

    It refuses anything that is not INVALID. Rescuing is the only transition where
    the officer is contradicting the machine rather than moving their own case
    forward, and a generic status patch would let a mis-click reset a RESOLVED case
    to NEW with the same request body — silently reopening finished work.

    And it lands on NEW, not on some "restored" state. Once an officer says this is
    a real report, it is a real report that nobody has looked at yet, which is
    exactly what NEW means. Inventing a fourth resting place for rescued cases
    would put them in a feed of their own, which is where things go to be forgotten.

    `triage_reason` is deliberately left on the row — see `db/models.py`. The
    record that a judgement was made and overturned is the only signal that triage
    is wrong about a whole class of message.
    """
    row = db.get(CitizenRequest, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No request with id {request_id}")
    if row.status != RequestStatus.INVALID.value:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Request {request_id} is {row.status}, not INVALID. "
                "Use PATCH /requests/{id}/status to move a valid case."
            ),
        )

    log.info("Request %s restored from INVALID (was: %s)", row.id, row.triage_reason)
    row.status = RequestStatus.NEW.value
    db.commit()
    db.refresh(row)
    district = db.get(District, row.district_code) if row.district_code else None
    return _to_out(row, district, len(row.responses))


def _to_out(r: CitizenRequest, d: District | None, response_count: int) -> CitizenRequestOut:
    """The privacy boundary for the officials' console.

    `r.location_text` — the citizen's raw, verbatim location line — is read here
    and never passed on verbatim. What leaves is `place.official_place`: the
    scrubbed hierarchy when extraction produced one, and otherwise the raw line put
    through the same scrub. Either way the string is no finer than a ward.

    The boundary is at the read model rather than at the write path on purpose.
    Scrubbing on write would give a cleaner sentence in the pitch and would cost
    the ability to debug a failed geocode, which is a real and recurring need —
    "Navi Mumbai, Maharashtra" silently resolving to a district 400 km away was
    found precisely by reading the strings that failed. Here, the threat model is
    served: the official is the party a complainant might reasonably fear, and
    they never receive it.
    """
    hierarchy = LocationHierarchy(
        state=r.loc_state,
        district_or_city=r.loc_district,
        locality=r.loc_locality,
        sector_or_ward=r.loc_ward,
        pin_code=r.loc_pin,
    )
    return CitizenRequestOut(
        id=r.id,
        district_code=r.district_code,
        district=d.name if d else None,
        state=d.state if d else None,
        district_label=district_label(d.name if d else None, hierarchy),
        category=r.category,
        urgency=r.urgency,
        summary_en=r.summary_en,
        language=r.language,
        channel=r.channel,
        created_at=r.created_at,
        raw_text=r.raw_text,
        place=official_place(hierarchy, r.location_text),
        location=hierarchy,
        image_verification=r.image_verification,
        has_photo=bool(r.has_photo),
        photo_stored=bool(r.photo_path),
        track_token=r.track_token,
        confidence=r.confidence,
        citizen_ref=r.citizen_ref,
        status=r.status,
        triage_reason=r.triage_reason,
        response_count=response_count,
        # One message can raise two unrelated problems. They are two rows here and
        # stay two rows on the console — an officer's queue must not merge a water
        # complaint into a road complaint because they arrived in one sentence. These
        # fields exist so the pair can be *labelled* ("Part 1 of 2") and reassembled
        # for audit, never recombined into one line of work.
        submission_group_id=r.submission_group_id,
        issue_index=r.issue_index,
        issue_count=r.issue_count,
        title=r.title,
        location_status=r.location_status,
        clarification_question=r.clarification_question,
    )
