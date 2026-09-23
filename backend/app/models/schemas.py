"""API contracts. These are the stable boundary between the intake side, the
analytics side and the dashboard — agree on these first and the three
workstreams can be built in parallel without stepping on each other."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Channel(str, Enum):
    """How the request arrived. The track asks for voice, text AND messaging
    apps, so channel is first-class and reported on in the dashboard."""
    VOICE = "voice"
    TEXT = "text"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    IVR = "ivr"


# ---------- intake ----------

class IntakeTextIn(BaseModel):
    text: str = Field(min_length=3, description="Citizen's message in their own language")
    language: str = Field(default="hi", description="Short language code, see app/i18n")
    location_text: str | None = Field(default=None, description="Free-text place, e.g. 'Barpeta, Assam'")
    channel: Channel = Channel.TEXT
    citizen_ref: str | None = Field(default=None, description="Opaque handle; never store PII")


class LocationHierarchy(BaseModel):
    """A place, decomposed as far down as the privacy model permits — and no further.

    Five levels, and the absence of a sixth is the point: there is no field for a
    house, flat, plot or street number, so the extraction schema itself has
    nowhere to put one. `services/place.py` strips one anyway if a model tries,
    because a schema is a shape and a filter is a guarantee.

    Why decomposed at all, when the raw line was already stored: the geocoder's
    four passes reward precision. A bare PIN matches exactly, and a locality
    carrying its own state reaches the alias pass with the state as a hard
    boundary rather than as similarity that can be donated to the wrong district.
    Flat text made 'Navi Mumbai, Maharashtra' resolve to Nandurbar, 400 km away.
    """
    state: str | None = None
    district_or_city: str | None = None
    locality: str | None = Field(default=None, description="Neighbourhood or village, e.g. 'Ulwe'")
    sector_or_ward: str | None = Field(
        default=None,
        description="Finest permitted granularity: 'Sector 23', 'Ward 14'. Never a premises.",
    )
    pin_code: str | None = Field(default=None, description="Six digits, or absent")

    def is_empty(self) -> bool:
        return not any(self.model_dump().values())


class ExtractedRequest(BaseModel):
    """What Gemini turns an unstructured utterance into."""
    category: str
    summary_en: str
    summary_native: str
    urgency: int = Field(ge=1, le=5, description="1 = routine, 5 = emergency")
    affected_estimate: int | None = Field(default=None, description="People affected, if stated")
    location_text: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    location: LocationHierarchy = Field(
        default_factory=LocationHierarchy,
        description="Structured place. Never below ward level.",
    )
    image_verification: str | None = Field(
        default=None,
        description=(
            "What the attached photograph shows and the condition of it, written "
            "by Gemini. Present only when an image was submitted. The photograph "
            "itself is not retained."
        ),
    )
    #: Whether this message is actually a development need at all.
    #:
    #: A public channel receives things that are not grievances: a test message, an
    #: advertisement, abuse aimed at the operator, "how do I use this", a wrong
    #: number. Each one currently becomes a docket with a category and an urgency,
    #: and then counts as demand — which inflates a district's score on the
    #: strength of somebody typing "test test test" four times.
    #:
    #: Defaults to True and every failure path leaves it True. A message the model
    #: could not judge must reach an officer, because the cost of a wrongly hidden
    #: complaint falls on a citizen who has no way to discover it happened, while
    #: the cost of a wrongly shown one is an officer's ten seconds.
    is_valid_grievance: bool = Field(
        default=True,
        description="False when the message is not a development request at all.",
    )
    triage_reason: str | None = Field(
        default=None,
        description=(
            "Why the message was judged not to be a grievance, in one short "
            "sentence. Shown to the officer reviewing the invalid queue, so it has "
            "to be specific enough to disagree with."
        ),
    )


class Classification(str, Enum):
    """What one inbound submission turned out to be.

    Replaces the earlier valid/invalid boolean, which could only say "this is not
    a request" and so had to say it about messages that were plainly requests with
    something missing. The five values separate three different questions that the
    boolean collapsed into one: is it processable, does it contain more than one
    actionable thing, and is anything needed from the citizen before an officer can
    act.

    None of them is a judgement about whether the reported event really happened.
    A model can tell whether a message is understandable; it cannot tell whether
    the borewell is actually dry. Nothing downstream may read these as proof.
    """
    #: One actionable issue, enough detail to file.
    VALID_SINGLE_ISSUE = "VALID_SINGLE_ISSUE"
    #: Several independently actionable issues in one message — split into a
    #: request each, sharing a submission group.
    VALID_MULTI_ISSUE = "VALID_MULTI_ISSUE"
    #: Understandable as a complaint, but what is being asked for cannot be
    #: identified. Answered with a specific question, not filed.
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    #: A real issue with no usable place. Filed, tokened, and held out of the
    #: actionable queue until the citizen supplies a location.
    MISSING_LOCATION = "MISSING_LOCATION"
    #: Not a civic message at all: empty, random characters, advertising, or
    #: malicious. Deliberately the narrowest of the five — a genuine complaint
    #: missing information belongs in NEEDS_CLARIFICATION or MISSING_LOCATION.
    INVALID_OR_SPAM = "INVALID_OR_SPAM"
    #: Conversational turn (menu selection, missing location prompt, budget prompt, status lookup).
    CONVERSATIONAL = "CONVERSATIONAL"


class LocationStatus(str, Enum):
    """Whether a filed request knows where it is. Decided by the backend, never
    by the model: `RESOLVED` means `resolve_district` returned an LGD code."""
    #: Matched to a district in `data/reference/districts.csv`.
    RESOLVED = "RESOLVED"
    #: A place was named but no district matched. Still actionable — an officer
    #: can read "Kosagumuda block" even when the reference table cannot.
    UNRESOLVED = "UNRESOLVED"
    #: No usable place at all. The one case that holds a request back.
    MISSING = "MISSING"


class ExtractedIssue(BaseModel):
    """One independently actionable thing inside a submission.

    "Independently actionable" is the whole test. A water complaint and a road
    complaint go to two departments, get two work orders and are resolved on two
    different days, so they are two issues. A cause, a consequence and a
    supporting detail of the same problem are one.
    """
    title: str | None = Field(default=None, description="Short label, e.g. 'Potholes on the main road'")
    category: str
    summary_en: str
    summary_native: str
    urgency: int = Field(default=3, ge=1, le=5)
    affected_estimate: int | None = None
    #: Set only when this issue names its own place, distinct from the submission's
    #: shared location. Null is the common case and means "use the shared one".
    location: LocationHierarchy | None = None
    location_text: str | None = None
    #: The model's own reading of whether the shared location covers this issue.
    #: Advisory: `pipeline` decides, because "never invent a location" has to be a
    #: guarantee rather than a request.
    location_applies_from_shared_context: bool = True
    requires_clarification: bool = False
    clarification_question: str | None = None
    image_verification: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ExtractedSubmission(BaseModel):
    """One inbound message, structured — possibly into several issues.

    This is the full shape of a Gemini extraction call. `ExtractedRequest` above is
    the single-issue projection of it, kept because the photo-evidence path and the
    fallback tests both want one record rather than a list.
    """
    classification: Classification = Classification.VALID_SINGLE_ISSUE
    detected_language: str | None = None
    #: One place stated for the whole message. Copied to every issue that does not
    #: state its own — rule 1 of the location rules.
    shared_location: LocationHierarchy | None = None
    shared_location_text: str | None = None
    issues: list[ExtractedIssue] = Field(default_factory=list)
    #: Present only for INVALID_OR_SPAM. Named for the officer who may overrule it.
    triage_reason: str | None = None
    #: Present only for NEEDS_CLARIFICATION. One specific question, in the
    #: citizen's own language.
    clarification_question: str | None = None
    #: What to say back when nothing was filed, in the citizen's own language.
    reply_native: str | None = None


class IntakeResult(BaseModel):
    """Returned to the citizen — acknowledgement in their own language matters
    for trust, and it doubles as the demo's proof that the round trip works."""
    request_id: int
    track_token: str | None = Field(
        default=None,
        description=(
            "The citizen's tracking reference, e.g. 'JS-7K4M-92QX'. Show this "
            "prominently: it is the only way back to the case, because there is "
            "no account to log in to. Random rather than sequential so it cannot "
            "be walked — see backend/app/services/tracking.py."
        ),
    )
    category: str
    district: str | None
    state: str | None
    district_label: str | None = Field(
        default=None,
        description=(
            "'Raigad (Navi Mumbai)' — the resolved district plus the place the "
            "citizen actually named. Show this rather than `district` alone: a "
            "person who wrote Navi Mumbai and is shown only 'Raigad' has no way "
            "to tell a correct district match from a wrong one."
        ),
    )
    urgency: int
    transcript: str | None
    summary_en: str
    acknowledgement_native: str
    language: str
    channel: Channel
    confidence: float = Field(
        ge=0.0, le=1.0,
        description=(
            "Extraction confidence. Surfaced deliberately: the fallback path "
            "reports 0.1, and the UI shows that rather than hiding it, because "
            "visible uncertainty is more trustworthy than false precision."
        ),
    )
    citizen_ref: str | None = Field(
        default=None,
        description=(
            "Opaque reporter handle. Contains nothing derived from personal data. "
            "This identifies the *reporter*, not this report — on messaging "
            "channels it is stable across everything that sender files — so it is "
            "deliberately not the tracking key. Use `track_token` for that."
        ),
    )
    location: LocationHierarchy = Field(
        default_factory=LocationHierarchy,
        description=(
            "What the platform understood the place to be, echoed back so the "
            "citizen can see it was read correctly before an officer acts on it."
        ),
    )
    image_verification: str | None = Field(
        default=None,
        description="Gemini's reading of the attached photograph, if one was sent.",
    )
    title: str | None = Field(
        default=None,
        description="Short label for this one issue, e.g. 'Potholes on the main road'.",
    )
    status: str | None = Field(
        default=None,
        description=(
            "Casework status as filed. Normally 'NEW'; 'NEEDS_LOCATION' when the "
            "message named no usable place, which is the signal for the citizen UI "
            "to show the 'Add location' panel."
        ),
    )
    location_status: str | None = Field(
        default=None,
        description="RESOLVED, UNRESOLVED or MISSING — see LocationStatus.",
    )
    issue_index: int = Field(
        default=1,
        description="1-based position of this issue within its submission.",
    )
    issue_count: int = Field(
        default=1,
        description=(
            "How many requests the one message became. 1 for the ordinary case; the "
            "citizen UI shows 'Request 1 of 2' only when this exceeds 1."
        ),
    )
    submission_group_id: str | None = Field(
        default=None,
        description=(
            "Shared across every request split out of one message, so a split "
            "submission can be re-assembled for audit without the officials' "
            "console ever merging the rows back into one line of work."
        ),
    )
    clarification_question: str | None = Field(
        default=None,
        description="One specific question to put back to the citizen, in their language.",
    )


class IntakeEnvelope(IntakeResult):
    """What `POST /intake/*` returns now that one message can become many requests.

    Deliberately a *subclass* of `IntakeResult` rather than a wrapper around a list.
    One message becoming two requests is the interesting case but not the common
    one, and every existing caller — the three channel adapters, the citizen
    confirmation card, `submitReport` in the frontend, and a year of tests — reads
    `track_token` and `category` off the top level of this response. Inheriting
    means that for `request_count == 1` the JSON is byte-identical to what those
    callers already handle, and for `request_count > 1` the top level describes
    request 1 while `requests[]` carries all of them in order.

    So no version bump, no parallel endpoint, and no client that breaks the day
    splitting is switched on.

    When nothing was filed at all — INVALID_OR_SPAM, or NEEDS_CLARIFICATION —
    `request_id` is 0 and `requests` is empty, reusing the "no record" convention
    already used for conversational replies on WhatsApp. `acknowledgement_native`
    carries what to say back.
    """
    classification: Classification = Classification.VALID_SINGLE_ISSUE
    request_count: int = Field(
        default=1,
        description="How many rows were written. 0 for spam or an unanswerable message.",
    )
    requests: list[IntakeResult] = Field(
        default_factory=list,
        description=(
            "Every request created from this one message, in reading order. Holds a "
            "single element in the ordinary case, so a client can read this list "
            "uniformly and ignore the flattened top level entirely."
        ),
    )
    triage_reason: str | None = Field(
        default=None,
        description="Why triage set this message aside. Present only for INVALID_OR_SPAM.",
    )


class RequestStatus(str, Enum):
    """Casework state for the officials' console."""
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"
    #: Triage decided this was not a development request. Distinct from REJECTED,
    #: which is a human closing a real grievance without action — conflating the
    #: two would hide every machine misjudgement inside a pile of legitimate
    #: refusals, and the whole point of a separate state is that the misjudgements
    #: stay findable and reversible. Set only by the intake pipeline, cleared only
    #: by an officer through `PATCH /requests/{id}/restore`.
    INVALID = "INVALID"
    #: A real request that nobody can act on, because it does not say where.
    #: It is filed, it has a token, and the citizen can come back to it — holding
    #: the record back until a location arrives would mean losing the report
    #: whenever the follow-up never comes. It stays out of the actionable queue and
    #: out of demand analytics until `PATCH /track/{token}/location` supplies one.
    NEEDS_LOCATION = "NEEDS_LOCATION"


#: Display order for the console's status filter and counters.
STATUS_ORDER: list[str] = [s.value for s in RequestStatus]

#: A case is "open" until somebody has closed it either way.
OPEN_STATUSES: set[str] = {
    RequestStatus.NEW.value,
    RequestStatus.ACKNOWLEDGED.value,
    RequestStatus.UNDER_REVIEW.value,
    RequestStatus.ASSIGNED.value,
    RequestStatus.IN_PROGRESS.value,
}

#: Cases nobody should be asked to work: closed either way, or never a request.
#: The console's default feed excludes these, and `analytics/aggregate.py`
#: excludes INVALID from demand — a docket that says "test test test" must not
#: raise a district's unmet-need score.
CLOSED_STATUSES: set[str] = {
    RequestStatus.RESOLVED.value,
    RequestStatus.REJECTED.value,
}

#: Never actionable, for two different reasons: one was judged not to be a request,
#: the other is a request that does not say where. Both are excluded from the
#: officials' working queue, from "action required" counters, and from
#: `analytics/aggregate.py` — a report with no district cannot raise any district's
#: score, and a report that says "test test test" must not raise one either.
#:
#: Kept separate from CLOSED_STATUSES because these are not endings. Both states
#: are reversible and both have a route back: an officer overrules triage, a citizen
#: supplies the missing place.
NOT_ACTIONABLE: set[str] = {
    RequestStatus.INVALID.value,
    RequestStatus.NEEDS_LOCATION.value,
}


# ---------- accountless tracking ----------

#: The ladder a citizen is shown, in order. Five rungs, not seven.
#:
#: The console's `RequestStatus` has seven members because casework needs that
#: resolution; a citizen checking a token needs to know how far along their
#: report is, and "ACKNOWLEDGED" vs "NEW" is an internal distinction that would
#: read as two names for the same nothing. So the ladder is coarser than the
#: state machine and the mapping below is explicit rather than positional —
#: adding a console status must not silently shift what a citizen sees.
TRACK_STEPS: list[tuple[str, str]] = [
    ("SUBMITTED", "Submitted"),
    ("ACKNOWLEDGED", "Acknowledged"),
    ("UNDER_REVIEW", "Under Review"),
    ("ASSIGNED", "Assigned to Dept"),
    ("IN_PROGRESS", "In Progress"),
    ("RESOLVED", "Resolved"),
]

#: Which rung each casework status sits on. None means off the ladder entirely.
STEP_OF_STATUS: dict[str, int | None] = {
    RequestStatus.NEW.value: 0,
    RequestStatus.ACKNOWLEDGED.value: 1,
    RequestStatus.UNDER_REVIEW.value: 2,
    RequestStatus.ASSIGNED.value: 3,
    RequestStatus.IN_PROGRESS.value: 4,
    RequestStatus.RESOLVED.value: 5,
    RequestStatus.REJECTED.value: None,
    RequestStatus.INVALID.value: None,
    RequestStatus.NEEDS_LOCATION.value: None,
}

#: Plain-language status names. The console shows `SCREAMING_SNAKE_CASE` because
#: an officer is reading a state machine; a citizen is reading about their own
#: complaint and should never be shown an enum member.
CITIZEN_STATUS_LABEL: dict[str, str] = {
    RequestStatus.NEW.value: "Submitted",
    RequestStatus.ACKNOWLEDGED.value: "Receipt acknowledged",
    RequestStatus.UNDER_REVIEW.value: "Under review",
    RequestStatus.ASSIGNED.value: "Assigned to department",
    RequestStatus.IN_PROGRESS.value: "Work in progress",
    RequestStatus.RESOLVED.value: "Resolved",
    RequestStatus.REJECTED.value: "Closed without action",
    RequestStatus.INVALID.value: "Needs more detail before it can be acted on",
    RequestStatus.NEEDS_LOCATION.value: "Waiting for the location of the problem",
}


class TrackStep(BaseModel):
    """One rung of the citizen-facing stepper."""
    key: str
    label: str
    reached: bool
    at: datetime | None = Field(
        default=None,
        description=(
            "When this rung was reached, where it is known. Derived from the "
            "status transitions recorded on official replies, so a case that "
            "jumped rungs reports reached=true with at=null rather than "
            "inventing a date."
        ),
    )


class TrackHistoryEntry(BaseModel):
    """One chronological event in the request's audit timeline."""
    timestamp: datetime
    status_label: str
    desk: str
    body_en: str | None = None
    body_native: str | None = None
    status_after: str | None = None


class TrackResponse(BaseModel):
    """The latest official reply, as the citizen sees it.

    No officer name, by design — `responder_desk` is a role. The console holds no
    officer identity either, so there is nothing to withhold here that is stored
    somewhere else.
    """
    body_en: str
    body_native: str | None = None
    responder_desk: str
    created_at: datetime


class TrackingOut(BaseModel):
    """Everything the "Track Status" page renders, for one token."""
    track_token: str
    token: str | None = None  # alias for track_token
    filed_at: datetime
    created_at: datetime | None = None  # alias for filed_at
    updated_at: datetime | None = None
    category: str
    category_label: str
    urgency: int
    summary_en: str
    original_text: str | None = None
    language: str
    channel: str

    district: str | None = None
    state: str | None = None
    district_label: str | None = Field(
        default=None,
        description="'Raigad (Navi Mumbai)' — official district plus the place the citizen named.",
    )
    place: str | None = Field(
        default=None,
        description="Ward-level locality. Never a premises — same scrub as the officials' console.",
    )

    status: str = Field(description="Raw casework status, for clients that want the state machine")
    status_label: str = Field(description="Plain-language status for display")
    step_index: int | None = Field(
        description="Rung reached on `steps`, or null when the case is off the ladder (closed without action)"
    )
    steps: list[TrackStep]
    is_closed: bool = Field(description="Resolved or closed without action — no further movement expected")

    latest_response: TrackResponse | None = None
    response_count: int = 0
    history: list[TrackHistoryEntry] = Field(default_factory=list)
    status_history: list[TrackHistoryEntry] = Field(default_factory=list)

    title: str | None = None
    needs_location: bool = Field(
        default=False,
        description=(
            "True when this request is held back for want of a place. The tracking "
            "page reads this one flag to decide whether to show the location form, "
            "rather than string-matching the status."
        ),
    )
    location_status: str | None = None
    clarification_question: str | None = None
    issue_index: int = 1
    issue_count: int = Field(
        default=1,
        description="Above 1 means this token is one of several split from a single message.",
    )
    submission_group_id: str | None = None


class LocationSupplyIn(BaseModel):
    """A citizen answering "where is this?" for one token.

    One field, and it is free text on purpose. The person filling it in is on a
    phone, may be writing in Odia, and knows their village rather than its LGD
    code — so this goes through exactly the same `sanitise` → `probes` →
    `resolve_district` path as an intake location line, and is subject to the same
    scrub. Nothing below ward level survives storage.
    """
    location_text: str = Field(
        min_length=2, max_length=300,
        description="Village, town, ward, district or landmark, in any script.",
    )



# ---------- read models ----------

class CitizenRequestOut(BaseModel):
    id: int
    district_code: str | None
    district: str | None
    state: str | None
    #: What the console's District column should actually print: the resolved LGD
    #: district, plus the place the citizen named where that differs — "Raigad
    #: (Navi Mumbai)", "Ernakulam (Kochi)". `district` stays the bare authoritative
    #: name because that is what joins against every other government dataset;
    #: this is the display string, and an officer needs both halves to tell a
    #: correct inference from a wrong one. See `services/place.py::district_label`.
    district_label: str | None = None
    category: str
    urgency: int
    summary_en: str
    language: str
    channel: str
    created_at: datetime

    # Added for the officials' console. All optional with defaults, so any client
    # written against the earlier shape keeps working.
    #
    # `raw_text` is the citizen's own words, untranslated. It is in the list
    # response rather than only the detail view on purpose: an officer scanning a
    # queue of English summaries is reading our paraphrase of a complaint, and the
    # original is the only thing that can contradict it.
    raw_text: str | None = None
    confidence: float | None = None

    # The citizen's own raw location line is deliberately NOT here.
    #
    # It is still stored — an unresolved place is impossible to debug without the
    # string that failed — but it is not served to the officials' console. The
    # threat model is specific: the official is the person a complainant might
    # reasonably fear, so the boundary belongs between the database and this
    # response rather than at the write path, where it would be easier to
    # describe and would cost the ability to diagnose a geocoding failure.
    #
    # `place` is the scrubbed rendering from `services/place.py::public_place`,
    # never finer than a ward. Full hierarchy in `location` for filtering.
    place: str | None = Field(
        default=None,
        description="Ward-level location an officer may see. Never a premises or street number.",
    )
    location: LocationHierarchy = Field(default_factory=LocationHierarchy)
    image_verification: str | None = Field(
        default=None,
        description=(
            "Gemini's description of the citizen's photograph. This is what "
            "travels; the photograph itself is only reachable through "
            "GET /requests/{id}/photo."
        ),
    )
    has_photo: bool = Field(
        default=False,
        description="A photo was submitted. True even if no description was produced.",
    )
    photo_stored: bool = Field(
        default=False,
        description=(
            "The photograph is on file and can be fetched from "
            "GET /requests/{id}/photo. False with has_photo true means it was "
            "received before retention existed, or the write failed."
        ),
    )
    #: The citizen's own tracking reference, shown to the officer on purpose.
    #:
    #: It is a bearer credential for `GET /track/{token}` — anyone holding it can
    #: read the case's status without an account, which is the whole point of an
    #: accountless receipt. Serving it here adds no exposure the officer does not
    #: already have (they are looking at the entire case) and closes a real gap: a
    #: citizen who phones in quoting "JS-GDDV-TAXX" was, until now, quoting a
    #: reference nobody on the government side could see. It is also what names the
    #: downloaded photograph, so the file on an officer's desktop and the reference
    #: in the citizen's hand are the same string.
    track_token: str | None = Field(
        default=None,
        description="The citizen's tracking reference, e.g. JS-GDDV-TAXX.",
    )
    citizen_ref: str | None = Field(
        default=None,
        description="Opaque, non-reversible reporter handle. Never a name, number or address.",
    )
    status: str = RequestStatus.NEW.value
    #: Why triage set `status` to INVALID. Served in the *list* response, not only
    #: the detail view, because the invalid queue is worked by scanning: an officer
    #: deciding which of forty flagged rows to rescue needs the reason on the row.
    triage_reason: str | None = Field(
        default=None,
        description="Gemini's one-sentence reason for flagging this as not a request.",
    )
    response_count: int = 0

    #: Split-submission provenance. `issue_count > 1` is what the console renders as
    #: "Part 1 of 2". The rows themselves stay separate: two departments, two work
    #: orders, two resolution dates — recombining them into one line of work is
    #: exactly the failure this feature exists to prevent.
    submission_group_id: str | None = None
    issue_index: int = 1
    issue_count: int = 1
    title: str | None = None
    location_status: str | None = Field(
        default=None,
        description="RESOLVED, UNRESOLVED or MISSING. MISSING is what puts a row in 'Needs citizen input'.",
    )
    clarification_question: str | None = None

    model_config = {"from_attributes": True}


class ResponseOut(BaseModel):
    """One official reply on a request's thread."""
    id: int
    request_id: int
    body_en: str
    body_native: str | None
    language: str
    responder_desk: str
    status_before: str | None
    status_after: str | None
    delivery_channel: str
    delivery_state: str = Field(
        description=(
            "'queued' means stored and ready for the channel adapter. Outbound "
            "WhatsApp and IVR require a paid Meta Business app and telephony "
            "account, so nothing here claims a message was delivered."
        ),
    )
    created_at: datetime

    model_config = {"from_attributes": True}


class ResponseIn(BaseModel):
    body_en: str = Field(min_length=5, description="The officer's reply, in English")
    responder_desk: str = Field(
        min_length=2, max_length=128,
        description="Role or desk issuing the reply, e.g. 'Water Resources Desk, Nabarangpur'. Not a person's name.",
    )
    new_status: RequestStatus | None = Field(
        default=None, description="Move the case at the same time as replying"
    )
    translate: bool = Field(
        default=True,
        description="Translate the reply into the citizen's language via Gemini. No-ops without a key.",
    )


class StatusPatch(BaseModel):
    status: RequestStatus


class SiblingRequest(BaseModel):
    """Another request from the same opaque handle.

    The only cross-request link the privacy model permits, and the reason
    `citizen_ref` exists at all: an officer can see that this handle has reported
    the same failure three times without learning anything about who it is.
    """
    id: int
    category: str
    urgency: int
    status: str
    summary_en: str
    created_at: datetime


class RequestDetail(CitizenRequestOut):
    affected_estimate: int | None = None
    transcript: str | None = None
    responses: list[ResponseOut] = Field(default_factory=list)
    from_same_reporter: list[SiblingRequest] = Field(default_factory=list)


class RequestStats(BaseModel):
    """Header counters for the console. Computed in SQL, not in the browser —
    the queue is capped at 1000 rows and a count taken from a truncated page
    would understate the backlog exactly when it matters most."""
    total: int
    open: int
    awaiting_first_reply: int
    by_status: dict[str, int]
    by_channel: dict[str, int]
    by_language: dict[str, int]
    by_urgency: dict[str, int]
    filed_last_7_days: int
    oldest_open_days: float | None
    status_order: list[str] = Field(default_factory=lambda: list(STATUS_ORDER))


class DistrictOut(BaseModel):
    """One covered district. `code` is the LGD key, which is what makes this
    joinable against any other government dataset without a fuzzy name match."""
    code: str
    name: str
    state: str
    population: int
    latitude: float | None = None
    longitude: float | None = None

    model_config = {"from_attributes": True}


class HotspotOut(BaseModel):
    district_code: str
    district: str
    state: str
    category: str
    request_count: int
    weighted_demand: float
    population: int
    coverage_pct: float | None
    allocation_per_capita: float | None
    unmet_need_score: float
    rank: int
    latitude: float | None = None
    longitude: float | None = None


class Evidence(BaseModel):
    """Every recommendation must be traceable back to its inputs. Policymakers
    will not act on a black-box ranking, and judges will ask how the number
    was produced."""
    citizen_requests: int
    weighted_demand: float
    coverage_pct: float | None
    coverage_gap_pct: float | None
    allocation_per_capita: float | None
    deprivation_index: float | None
    participation_adjustment: float
    # The two inputs to participation_adjustment. Without them the multiplier is
    # an unexplained number, which is the one thing this model cannot afford: the
    # whole claim is that quiet districts are quiet because of literacy and
    # connectivity, and a reader has to be able to check that against the district.
    literacy_pct: float | None = None
    internet_pct: float | None = None
    population: int | None = None
    component_scores: dict[str, float]
    weights: dict[str, float]


class RecommendationOut(BaseModel):
    rank: int
    district_code: str
    district: str
    state: str
    category: str
    project_title: str
    linked_scheme: str
    unmet_need_score: float
    est_beneficiaries: int
    rationale: str
    evidence: Evidence
    brief_md: str | None = Field(default=None, description="Gemini-written policy brief")
