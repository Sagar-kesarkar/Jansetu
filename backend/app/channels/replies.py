"""Token-aware follow-up handling shared by WhatsApp, SMS and IVR.

Splitting one message into several requests created a problem the single-request
pipeline never had: a citizen can now be holding three references, two of which are
waiting on a place. "Boisar, Palghar" arriving on its own is then genuinely
ambiguous, and guessing which case it answers for dispatches an officer to a village
nobody named. Everything in this module exists to make that guess unnecessary.

It is deliberately channel-agnostic and returns text rather than sending it, so the
three adapters keep their own real provider transports (`exotel_sms.send_exotel_sms`,
`whatsapp.send_whatsapp_message`, the IVR prompt list) and only the wording and the
decision live here — one definition of "which token did they mean" instead of three
that can drift.

**Reads are public, writes are owned.** A status lookup by token is answered whoever
asks, exactly as `GET /track/{token}` is: the token *is* the credential, and refusing
over SMS what is already public over HTTPS would be theatre that breaks the real flow
of filing on the web and tracking from a feature phone. A *write* — supplying a
location — additionally requires the request to belong to the pseudonymised session it
arrived on, because otherwise anyone who saw a token over someone's shoulder could
redirect their complaint to another district. An unowned write is answered with the
same words as an unknown token, so the refusal is not an oracle telling a guesser
which of their guesses were real.

**A plain place is only read as an answer when we asked for one.** `expecting=True` is
set by the adapter on the turn it sends the "location required" notice. Without that
flag a second, unrelated complaint sent from the same number would be swallowed as the
first one's location.

PRIVACY: every entry point takes an already-hashed `citizen_ref`. No raw phone number
reaches this module, and none is logged — see `services/privacy.py`.
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.channels.prompts import get_prompt_text
from app.db.models import CitizenRequest, District
from app.models.schemas import (
    CITIZEN_STATUS_LABEL,
    LocationHierarchy,
    RequestStatus,
)
from app.models.taxonomy import department_for
from app.services.pipeline import apply_location, awaiting_location
from app.services.place import official_place
from app.services.tracking import TOKEN_LENGTH, find_request, normalise

log = logging.getLogger(__name__)

#: One answer for "not a token", "not ours" and "not yours". See the module docstring.
NOT_FOUND = (
    "We could not find a request with that reference. Check the characters and try "
    "again — references look like JS-7K4M-92QX."
)

_WORD = re.compile(r"[A-Za-z0-9]+")

#: Words a citizen wraps a token in. Dropped from the front of the remainder so
#: "Location for JS-... is Boisar" leaves "Boisar" rather than "is Boisar".
_FILLER = {
    "location", "loc", "locations", "place", "address", "area", "status", "track",
    "tracking", "for", "of", "is", "at", "in", "the", "my", "our", "request",
    "complaint", "token", "ref", "reference", "id", "jansetu",
}


@dataclass(frozen=True)
class ChannelReply:
    """What to say back, and what it was.

    `kind` is for the adapter's logging and for the tests; the citizen only ever sees
    `reply`. `handled` is always True — a message this module declines to handle is
    signalled by returning None, so an adapter cannot accidentally treat a decline as
    an answer already sent.
    """

    reply: str
    kind: str
    token: str | None = None
    request_id: int | None = None
    handled: bool = True


# ---------- parsing ----------

def _prefixed(raw: str) -> str | None:
    """A token only if the `JS` prefix is present.

    Free text is scanned with the prefix required, because `normalise` also accepts a
    bare eight-character payload and the alphabet is not disjoint from English:
    "MAHARASH" is eight legal characters and would otherwise be read as a tracking
    reference in the middle of an address. The prefix is what makes the match
    deliberate.
    """
    cleaned = "".join(ch for ch in raw.upper() if ch.isalnum())
    if len(cleaned) != TOKEN_LENGTH + 2 or not cleaned.startswith("JS"):
        return None
    return normalise(cleaned)


def find_token_in(text: str | None) -> tuple[str | None, str]:
    """The first tracking reference in a message, and the message with it removed.

    Accepts `JS-W7K2-4M8P`, `js w7k2 4m8p`, `Location for JS-W7K2-4M8P is Boisar,
    Palghar` and a bare `7k4m92qx` when that is the entire message — the last because
    the SMS and WhatsApp "enter your token" prompts get exactly that back, and being
    strict there would fail the citizen who did what was asked.

    The remainder is returned rather than re-derived by the caller so that the token
    text can never survive into a place name and end up stored as a location.
    """
    body = (text or "").strip()
    if not body:
        return None, ""

    whole = normalise(body)
    if whole:
        return whole, ""

    spans = list(_WORD.finditer(body))
    for width in (1, 2, 3):  # a pasted token may arrive split on its dashes
        for i in range(len(spans) - width + 1):
            window = spans[i:i + width]
            token = _prefixed("".join(m.group(0) for m in window))
            if token:
                remainder = body[: window[0].start()] + " " + body[window[-1].end():]
                return token, remainder
    return None, body


def strip_filler(text: str | None) -> str:
    """`" is Boisar, Palghar"` -> `"Boisar, Palghar"`.

    Only leading connective words are dropped, and only English ones. A Hindi
    equivalent survives into the place string, which is the safe direction: an extra
    word lowers the chance `resolve_district` matches and the request is stored
    UNRESOLVED for an officer to read, whereas stripping aggressively could shorten a
    real village name into a different one.
    """
    words = (text or "").split()
    while words and "".join(ch for ch in words[0].lower() if ch.isalnum()) in _FILLER:
        words.pop(0)
    return " ".join(words).strip(" ,:;.-—")


# ---------- status ----------

def _where(db: Session, row: CitizenRequest) -> str:
    """The place, no finer than a ward — the same scrub the officials' console gets."""
    hierarchy = LocationHierarchy(
        state=row.loc_state,
        district_or_city=row.loc_district,
        locality=row.loc_locality,
        sector_or_ward=row.loc_ward,
        pin_code=row.loc_pin,
    )
    place = official_place(hierarchy, row.location_text)
    district = db.get(District, row.district_code) if row.district_code else None
    if district:
        formal = f"{district.name}, {district.state}"
        return formal if not place or place == district.name else f"{place} ({formal})"
    return place or "Not yet provided"


def _updated(row: CitizenRequest) -> str:
    """When the case last moved, as far as the record knows. Filing date until an
    officer has written back — `citizen_requests.status` keeps no history."""
    stamp = row.responses[-1].created_at if row.responses else row.created_at
    return stamp.strftime("%d %b %Y") if stamp else "-"


def status_card(db: Session, row: CitizenRequest, *, rich: bool = False, language: str = "en") -> str:
    """One request as a citizen sees it on a phone.

    `rich` is the WhatsApp card; plain is the SMS line, kept short because it shares a
    160-character segment with the header.
    """
    token = row.track_token or f"#{row.id}"
    label = CITIZEN_STATUS_LABEL.get(row.status, row.status.replace("_", " ").title())
    desk = department_for(row.category)
    tail = ""
    if row.status == RequestStatus.NEEDS_LOCATION.value:
        tail = f"\n\nReply: {token} <village/town, district> to complete it."

    stamp = row.responses[-1].created_at if row.responses else row.created_at
    stamp_str = stamp.strftime("%d %B %Y, %I:%M %p") if stamp else "-"
    summary_str = row.summary_native if language != "en" and row.summary_native else (row.summary_en or "Civic grievance")

    if rich:
        return (
            f"📌 *REQUEST STATUS*\n\n"
            f"*Request ID*\n{token}\n\n"
            f"*Complaint number*\n#{row.id}\n\n"
            f"*Problem*\n{summary_str}\n\n"
            f"*Category*\n{(row.category or 'OTHER').replace('_', ' ').title()}\n\n"
            f"*Location*\n{_where(db, row)}\n\n"
            f"*Status*\n{label}\n\n"
            f"*Department*\n{desk}\n\n"
            f"*Last updated*\n{stamp_str}"
            + tail
        )
    return (
        f"JanSetu {token} (#{row.id}): {label}. Dept: {desk}. "
        f"Location: {_where(db, row)}. Updated: {_updated(row)}." + tail
    )


def status_reply(
    db: Session,
    text: str | None,
    *,
    safe_ref: str,
    rich: bool = False,
) -> ChannelReply:
    """Answer a status question, by token if one was given and by session if not.

    The token path is unauthenticated on purpose (see the module docstring). The
    fallback path is the opposite — with no token there is nothing to authenticate
    against, so it can only ever return the asking session's own latest request.
    """
    token, _ = find_token_in(text)
    if token:
        row = find_request(db, token)
        if row is None:
            return ChannelReply(reply=NOT_FOUND, kind="unknown_token")
        return ChannelReply(
            reply=status_card(db, row, rich=rich),
            kind="status",
            token=row.track_token,
            request_id=row.id,
        )

    row = db.execute(
        select(CitizenRequest)
        .where(CitizenRequest.citizen_ref == safe_ref)
        .order_by(CitizenRequest.created_at.desc(), CitizenRequest.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        return ChannelReply(reply=NOT_FOUND, kind="unknown_token")
    return ChannelReply(
        reply=status_card(db, row, rich=rich),
        kind="status",
        token=row.track_token,
        request_id=row.id,
    )


# ---------- location follow-up ----------

def location_notice(rows: list[CitizenRequest], language: str, *, sms: bool = False) -> str:
    """The "we still need a place" message, one line per waiting reference.

    The human half is localised and the instruction half is not: the reply format has
    to be typed back verbatim by someone who may be copying it character by character,
    and a translated `<village/town, district>` placeholder would be copied as
    translated text and fail to parse. Naming every waiting token in one message is
    also what makes the later reply unambiguous — the citizen has been shown which
    references are outstanding before being asked to pick one.
    """
    if not rows:
        return ""
    lead = get_prompt_text("NEED_LOCATION_TEXT", language)
    if sms:
        lines = [
            f"JanSetu: Location needed for {r.track_token}. "
            f"Reply: {r.track_token} <village/town, district>."
            for r in rows
        ]
        return "\n".join(lines) if len(rows) > 1 else lines[0]
    lines = [
        f"Location required for request {r.track_token}. Reply with the village, town, "
        f"district or landmark, or share a location pin. Your request will be forwarded "
        f"after the location is received."
        if len(rows) == 1
        else f"{r.track_token} — {r.title or r.summary_en}"
        for r in rows
    ]
    if len(rows) == 1:
        return f"{lead}\n\n{lines[0]}"
    return (
        f"{lead}\n\n"
        f"{len(rows)} requests are waiting for a location:\n" + "\n".join(lines) +
        "\n\nReply with the reference and the place together — "
        f"for example: {rows[0].track_token} Boisar, Palghar."
    )


def route_location_reply(
    db: Session,
    *,
    safe_ref: str,
    text: str | None,
    language: str = "hi",
    expecting: bool = False,
) -> ChannelReply | None:
    """Apply a location the citizen sent back, or say why it could not be applied.

    Returns None when this message is not a location follow-up at all, which is the
    signal for the adapter to carry on into normal intake. Every other outcome is a
    `ChannelReply` the adapter must send instead of filing anything.

    The three cases the requirement turns on:

    * **A reference was named.** Unambiguous, so it is applied to that one request and
      to nothing else — after checking the request belongs to this session.
    * **No reference, exactly one request waiting.** Applied, because there is only one
      thing it can mean.
    * **No reference, several waiting.** Refused with the list, because silently
      applying one place to every open request is the specific failure this module
      exists to prevent.
    """
    token, remainder = find_token_in(text)

    if token:
        row = find_request(db, token)
        place = strip_filler(remainder)
        if row is None:
            return ChannelReply(reply=NOT_FOUND, kind="unknown_token")
        if not place:
            # A bare reference is a status question, not a half-finished answer —
            # unless that request is the one still waiting, in which case saying so is
            # more useful than reciting a status the citizen already knows.
            if row.status == RequestStatus.NEEDS_LOCATION.value:
                return ChannelReply(
                    reply=location_notice([row], language),
                    kind="need_place",
                    token=row.track_token,
                    request_id=row.id,
                )
            return status_reply(db, token, safe_ref=safe_ref)
        if row.citizen_ref != safe_ref:
            # Same words as an unknown reference. A distinct "that is not yours" would
            # confirm the token is real to whoever is holding it by accident.
            log.info("Rejected cross-session location write on %s", row.track_token)
            return ChannelReply(reply=NOT_FOUND, kind="not_owned")
        if not apply_location(db, row, place):
            return ChannelReply(
                reply=location_notice([row], language),
                kind="unreadable_place",
                token=row.track_token,
                request_id=row.id,
            )
        return ChannelReply(
            reply=_received(db, row),
            kind="location_applied",
            token=row.track_token,
            request_id=row.id,
        )

    pending = awaiting_location(db, safe_ref)
    if not pending or not expecting:
        return None

    place = strip_filler(text)
    if not place:
        return None

    if len(pending) > 1:
        return ChannelReply(reply=location_notice(pending, language), kind="ambiguous")

    row = pending[0]
    if not apply_location(db, row, place):
        return ChannelReply(
            reply=location_notice([row], language),
            kind="unreadable_place",
            token=row.track_token,
            request_id=row.id,
        )
    return ChannelReply(
        reply=_received(db, row),
        kind="location_applied",
        token=row.track_token,
        request_id=row.id,
    )


def _received(db: Session, row: CitizenRequest) -> str:
    """Confirmation that names the same token the citizen was already given.

    Quoting it again matters more than it looks: the receipt they are holding was
    issued before the request was complete, and a confirmation that omitted the
    reference would read as a second, separate registration.
    """
    return (
        f"Location received for {row.track_token}. Your request has now been forwarded "
        f"to the responsible officials.\n\n{status_card(db, row)}"
    )
