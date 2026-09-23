"""Accountless status tracking — the citizen's half of the loop.

`routers/requests.py` is what an officer reads. This is what the person who filed
the report reads, and the two are deliberately different responses over the same
row rather than one shared shape.

Three things make it different.

**The token is the whole credential.** There is no account, no OTP and no session,
because requiring any of them would exclude the users this platform is aimed at —
someone who filed over IVR from a feature phone has no email address to verify.
That puts the entire security burden on the token's entropy, which is why
`services/tracking.py` issues 30**8 random payloads instead of the PIN-plus-serial
format that would have been friendlier to read out and trivial to walk.

**A malformed token and an unknown token get the same answer.** Distinguishing
them would confirm to somebody guessing which of their guesses were *well-formed*,
which is the only signal an enumerator needs to narrow the space.

**It returns less than the console does.** No `citizen_ref` — see `TrackingOut`
for why that one omission matters more than the rest of the response put together.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import CitizenRequest, District
from app.models.schemas import (
    CITIZEN_STATUS_LABEL,
    STEP_OF_STATUS,
    TRACK_STEPS,
    LocationHierarchy,
    LocationSupplyIn,
    RequestStatus,
    TrackHistoryEntry,
    TrackingOut,
    TrackResponse,
    TrackStep,
)
from app.models.taxonomy import CATEGORIES
from app.services.pipeline import apply_location
from app.services.place import district_label, official_place
from app.services.tracking import find_request

router = APIRouter(prefix="/track", tags=["tracking"])

#: One message for both "not a token" and "not one of ours". See the module
#: docstring — the sameness is the point, so it is written once.
_NOT_FOUND = (
    "We could not find a request with that reference. Check the characters and "
    "try again — references look like JS-7K4M-92QX."
)


@router.get("/{token}", response_model=TrackingOut)
def track(
    token: str = Path(description="Tracking reference, e.g. JS-7K4M-92QX. Case and dashes are ignored."),
    db: Session = Depends(get_db),
) -> TrackingOut:
    row = find_request(db, token)
    if row is None:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    return _tracking_out(db, row)


@router.patch("/{token}/location", response_model=TrackingOut)
def supply_location(
    payload: LocationSupplyIn,
    token: str = Path(description="Tracking reference of the request that is missing a location."),
    db: Session = Depends(get_db),
) -> TrackingOut:
    """The citizen answering "where is this?" for one token.

    Idempotent by design rather than restricted to `NEEDS_LOCATION`: someone who
    realises they named the wrong village may correct it, and `apply_location` only
    lifts the status of a request that was actually waiting, so a correction on a case
    already under review cannot reset an officer's progress.

    The token is the whole credential here, exactly as it is for `GET /track/{token}`.
    That is the accountless design and not an oversight — there is no account to
    authenticate against, and requiring one would exclude the feature-phone users this
    platform is aimed at. What it does mean is that the token's entropy is carrying
    this write as well as the read, which is why `services/tracking.py` issues 30**8
    random payloads. The channel paths are stricter, because they *can* be: a WhatsApp
    or SMS reply must also come from the pseudonymised session that filed the request —
    see `channels/replies.py`.

    Returns the full tracking view rather than a bare acknowledgement, so the page can
    redraw the stepper, the district and the status from one round trip.
    """
    row = find_request(db, token)
    if row is None:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)

    if not apply_location(db, row, payload.location_text):
        raise HTTPException(
            status_code=422,
            detail=(
                "We could not read a place in that. Send a village, town, ward or "
                "district name — for example 'Boisar, Palghar'."
            ),
        )
    return _tracking_out(db, row)


def _tracking_out(db: Session, row: CitizenRequest) -> TrackingOut:
    """One row as the citizen sees it. Shared by the read and the location write so
    the two cannot describe the same request differently."""
    district = db.get(District, row.district_code) if row.district_code else None
    hierarchy = LocationHierarchy(
        state=row.loc_state,
        district_or_city=row.loc_district,
        locality=row.loc_locality,
        sector_or_ward=row.loc_ward,
        pin_code=row.loc_pin,
    )

    reached_at = _step_timestamps(row)
    current = STEP_OF_STATUS.get(row.status, 0)
    steps = [
        TrackStep(
            key=key,
            label=label,
            # Fill forward rather than marking only the current rung: a case that
            # went straight from NEW to IN_PROGRESS still passed review and
            # assignment, and drawing those as unreached would show a broken bar.
            #
            # Rung 0 is unconditional. Every row in the table was submitted — that
            # is what its existence means, and `created_at` dates it — so it stays
            # reached even for a status that sits off the ladder entirely. Letting
            # `current is None` blank the whole rail showed a refused citizen five
            # empty rungs beside a department's written refusal, which reads as
            # "nothing has happened yet" rather than "this ended".
            reached=i == 0 or (current is not None and i <= current),
            at=reached_at.get(i),
        )
        for i, (key, label) in enumerate(TRACK_STEPS)
    ]

    latest = row.responses[-1] if row.responses else None
    updated_at = latest.created_at if latest else row.created_at

    history_entries: list[TrackHistoryEntry] = [
        TrackHistoryEntry(
            timestamp=row.created_at,
            status_label="Grievance Registered",
            desk="Citizen Intake Portal",
            body_en=f"Initial grievance recorded via {row.channel.upper()} channel.",
            body_native=None,
            status_after="NEW",
        )
    ]
    for resp in row.responses:
        history_entries.append(
            TrackHistoryEntry(
                timestamp=resp.created_at,
                status_label=CITIZEN_STATUS_LABEL.get(resp.status_after or "", "Status Updated"),
                desk=resp.responder_desk or "Administration Desk",
                body_en=resp.body_en,
                body_native=resp.body_native,
                status_after=resp.status_after,
            )
        )

    return TrackingOut(
        track_token=row.track_token or "",
        token=row.track_token or "",
        filed_at=row.created_at,
        created_at=row.created_at,
        updated_at=updated_at,
        category=row.category,
        # `category_or_other` can produce OTHER, which has no taxonomy row. Fall
        # back to a readable form of the code rather than to a KeyError.
        category_label=(
            CATEGORIES[row.category].label_en
            if row.category in CATEGORIES
            else row.category.replace("_", " ").title()
        ),
        urgency=row.urgency,
        summary_en=row.summary_en,
        original_text=row.raw_text,
        language=row.language,
        channel=row.channel,
        district=district.name if district else None,
        state=district.state if district else None,
        district_label=district_label(district.name if district else None, hierarchy) or (row.location_text if not district else None),
        # The same scrub the officials' console gets. A citizen seeing their own
        # ward back is the point — it is how they check the platform read them
        # correctly — and reusing `official_place` means there is one definition of
        # "no finer than a ward" rather than two that can drift apart.
        place=official_place(hierarchy, row.location_text),
        status=row.status,
        status_label=CITIZEN_STATUS_LABEL.get(row.status, row.status.replace("_", " ").title()),
        step_index=current,
        steps=steps,
        is_closed=row.status in {RequestStatus.RESOLVED.value, RequestStatus.REJECTED.value},
        latest_response=(
            TrackResponse(
                body_en=latest.body_en,
                body_native=latest.body_native,
                responder_desk=latest.responder_desk,
                created_at=latest.created_at,
            )
            if latest
            else None
        ),
        response_count=len(row.responses),
        history=history_entries,
        status_history=history_entries,
        title=row.title,
        # One flag rather than a status string for the page to match on. The tracking
        # page shows a location form off this and nothing else, and a client
        # string-comparing "NEEDS_LOCATION" is a client that breaks the day the status
        # is renamed.
        needs_location=row.status == RequestStatus.NEEDS_LOCATION.value,
        location_status=row.location_status,
        clarification_question=row.clarification_question,
        issue_index=row.issue_index,
        issue_count=row.issue_count,
        submission_group_id=row.submission_group_id,
    )


def _step_timestamps(row: CitizenRequest) -> dict[int, object]:
    """When each rung was reached, as far as the record actually knows.

    Rung 0 is the filing time, which is certain. Everything above it is inferred
    from `RequestResponse.status_after`, because that is the only place a
    transition is dated — `citizen_requests.status` holds the current value and no
    history. A status changed through `PATCH /requests/{id}/status` without a
    reply therefore leaves no date, and this returns nothing for that rung rather
    than guessing one; a stepper showing a plausible wrong date is worse than one
    showing none.

    Earliest wins on repeats: a case bounced back to review and forward again
    reached that rung the first time.
    """
    stamps: dict[int, object] = {0: row.created_at}
    for reply in row.responses:  # ordered by created_at on the relationship
        index = STEP_OF_STATUS.get(reply.status_after or "", None)
        if index is None or index in stamps:
            continue
        stamps[index] = reply.created_at
    return stamps
