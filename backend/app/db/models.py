"""Tables.

Note what is NOT here: no citizen names, phone numbers or addresses. Requests
carry an opaque `citizen_ref` and a district code. A platform meant to be
adopted by governments has to be defensible on privacy from day one, and it
also keeps us clear of DPG privacy expectations.

That holds for the reply side too — see `RequestResponse`. An officials' console
that can answer a citizen is the point at which most grievance systems start
storing a phone number "just for the callback". This one addresses replies to the
same opaque ref and leaves routing to the channel adapter.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class District(Base):
    """Keyed on the LGD (Local Government Directory) code — the government's own
    identifier. Using it means our output can be joined against any other
    official dataset without a fuzzy name match."""
    __tablename__ = "districts"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    state: Mapped[str] = mapped_column(String(128), index=True)
    population: Mapped[int] = mapped_column(Integer, default=0)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    literacy_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    internet_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    deprivation_index: Mapped[float | None] = mapped_column(Float, nullable=True)

    requests: Mapped[list["CitizenRequest"]] = relationship(back_populates="district")


class PlaceAlias(Base):
    """Every other name a district goes by: its cities, localities, tehsils, PIN
    codes and native-script spellings.

    This table exists because of a real failure. A citizen submitted "sector
    23, ulwe, 410206 NAVI MUMBAI, MAHARASHTRA" and the fuzzy district matcher
    returned Nandurbar — a tribal district 400 km away — because the shared word
    "Maharashtra" carried enough similarity to clear the threshold. Nobody in
    India files a complaint using the name of their district. They name their
    ward, their locality, their city, or they write the PIN code, and none of
    those are in `districts.csv`.

    The alias layer is what makes that gap fixable as data. Constraint 4 of this
    project says extending coverage means adding rows, never editing logic — a
    hardcoded {"navi mumbai": "MH_RAIGAD"} dict in `services/geocode.py` would
    have broken that on the first city we added.

    `kind` is descriptive, not behavioural, with one exception: PIN codes are
    matched exactly rather than fuzzily, since "410206" and "410205" are 83%
    similar and different places.
    """
    __tablename__ = "place_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    district_code: Mapped[str] = mapped_column(ForeignKey("districts.code"), index=True)
    #: Stored lowercased and whitespace-collapsed; the loader normalises so the
    #: matcher never has to.
    alias: Mapped[str] = mapped_column(String(128), index=True)
    kind: Mapped[str] = mapped_column(String(16), default="locality", index=True)


class InfraIndex(Base):
    """Existing coverage per district per category, from public datasets."""
    __tablename__ = "infra_indices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    district_code: Mapped[str] = mapped_column(ForeignKey("districts.code"), index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    coverage_pct: Mapped[float | None] = mapped_column(Float, nullable=True)


class InvestmentPlan(Base):
    """What is already budgeted. Without this the platform would recommend
    projects that are already funded — the fastest way to lose credibility
    with an actual planning department."""
    __tablename__ = "investment_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    district_code: Mapped[str] = mapped_column(ForeignKey("districts.code"), index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    scheme: Mapped[str] = mapped_column(String(128), default="")
    allocated_inr_lakh: Mapped[float] = mapped_column(Float, default=0.0)
    fiscal_year: Mapped[str] = mapped_column(String(16), default="2026-27")


class CitizenRequest(Base):
    __tablename__ = "citizen_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    district_code: Mapped[str | None] = mapped_column(ForeignKey("districts.code"), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    urgency: Mapped[int] = mapped_column(Integer, default=3)
    affected_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)

    raw_text: Mapped[str] = mapped_column(Text)          # original language
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)  # if voice
    summary_en: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(8), default="hi")
    channel: Mapped[str] = mapped_column(String(16), default="text")
    location_text: Mapped[str | None] = mapped_column(String(256), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    citizen_ref: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=_now, index=True)

    # The citizen's accountless receipt: "JS-7K4M-92QX". Unique and indexed
    # because it is the sole lookup key for status tracking — see
    # `services/tracking.py` for why it is random rather than PIN-plus-serial.
    #
    # Separate from `citizen_ref` on purpose, not by oversight. For WhatsApp, SMS
    # and IVR, `citizen_ref` is the HMAC of the sender and is therefore stable
    # across everything that sender ever files; using it as the tracking key would
    # mean one token shown over a shoulder opens that person's whole history. This
    # column is per request.
    #
    # Nullable so `_add_missing_columns` can ALTER it onto a database seeded
    # before it existed; `backfill` in the tracking service fills those rows at
    # startup, so a NULL is a transient state rather than a supported one.
    track_token: Mapped[str | None] = mapped_column(
        String(16), nullable=True, unique=True, index=True
    )

    # Structured place, decomposed by Gemini and filtered by
    # `services/place.py::sanitise` before it gets here. Five levels and no sixth:
    # there is no column for a house, flat or plot, which is what keeps constraint
    # 5 true while still telling a works department which road to send a crew to.
    #
    # `location_text` above holds the citizen's raw line and stays out of the
    # officials' console; these columns are what it is served instead.
    loc_state: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    loc_district: Mapped[str | None] = mapped_column(String(96), nullable=True)
    loc_locality: Mapped[str | None] = mapped_column(String(96), nullable=True, index=True)
    loc_ward: Mapped[str | None] = mapped_column(String(96), nullable=True)
    loc_pin: Mapped[str | None] = mapped_column(String(6), nullable=True, index=True)

    # What Gemini saw in the citizen's photograph, whether there was one, and
    # where the file went.
    #
    # This started out as two columns and a firm rule: the photograph was read for
    # a description and discarded, never written anywhere. The reasoning still
    # holds — a picture of a broken road also carries faces, door plates and EXIF
    # coordinates, every category constraint 5 forbids, arriving in a field nobody
    # declared.
    #
    # It is now retained, because an officer being asked to send a crew wants to
    # see the road, and a description they cannot check is corroboration on trust.
    # The trade is made explicit rather than quietly: the bytes live outside any
    # statically served directory, are reachable only through the console's own
    # request route, and are named by tracking token so the filename says nothing
    # about the reporter. `image_verification` remains the thing analytics and the
    # citizen-facing API see; the file is casework evidence, not data.
    #
    # Three columns, not one. With no API key an image is still received and still
    # cannot be described, and "photo attached, not analysed" is a different fact
    # from "no photo" — and a row filed before retention existed has `has_photo`
    # true with no file, which `photo_path` being NULL is what distinguishes.
    image_verification: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_photo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    #: Filename only, relative to `settings.evidence_dir`. Not an absolute path:
    #: the directory moves between a laptop and a container, and a stored absolute
    #: path would make every existing row unreadable after the first deploy.
    photo_path: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # Casework state, for the officials' console. `server_default` rather than a
    # Python-side default only: without it, ALTER TABLE ADD COLUMN on a database
    # seeded before this column existed cannot satisfy NOT NULL, and every
    # pre-existing row would need a backfill pass to be readable.
    status: Mapped[str] = mapped_column(String(16), default="NEW", server_default="NEW", index=True)

    #: Why triage set `status` to INVALID, in Gemini's own words.
    #:
    #: Kept on the row rather than only logged, because the officer's job in the
    #: invalid queue is to disagree with it. "Appears to be a test message with no
    #: stated problem" is arguable; a bare INVALID with no reason is not, and an
    #: officer given nothing to argue with will either rescue everything or nothing.
    #:
    #: Nullable and left in place after a rescue on purpose. A restored case that
    #: still carries the reason it was flagged records that the judgement was made
    #: and overturned, which is the only way to find out that triage is wrong about
    #: a whole category of message — clearing it would erase the evidence.
    triage_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- one message, several requests ----
    #
    # A citizen who reports bad drinking water and a broken road in one sentence has
    # raised two things that go to two departments and are resolved on two different
    # days. They are filed as two rows with two tokens, and these four columns are
    # what lets them be reassembled for audit without ever being recombined into one
    # line of an officer's work.
    #
    # All nullable or server-defaulted, because `db/database.py::_add_missing_columns`
    # is this project's migration mechanism and SQLite cannot add a NOT NULL column
    # without a default to a table that already has rows.

    #: Shared by every row split out of one inbound message. Set on single-issue rows
    #: too, so a query never has to special-case the common shape.
    submission_group_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    #: 1-based position within the submission — the "1" in "Part 1 of 2".
    issue_index: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    #: How many rows the message became. 1 for the ordinary case; the console shows
    #: the part indicator only above 1.
    issue_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    #: Short human label for this one issue, e.g. "Potholes on the main road".
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)

    #: RESOLVED, UNRESOLVED or MISSING — see `schemas.LocationStatus`.
    #:
    #: Decided by the pipeline from whether `resolve_district` matched, never by the
    #: model. MISSING is the only value that holds a request back, and it pairs with
    #: `status = NEEDS_LOCATION`: the row exists, has a token and can be tracked, but
    #: stays out of the actionable queue and out of demand analytics until a citizen
    #: says where. Filing it anyway rather than refusing the message is the point —
    #: a request rejected for a missing village is a request that is never made again.
    location_status: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)

    #: One specific question to put back to the citizen, in their own language.
    clarification_question: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: The provider's own id for the message that produced this row — a WhatsApp
    #: `message_id`, an Exotel `SmsSid`. Retried webhooks are normal, and this is the
    #: second line of defence behind `ChannelEvent`'s unique constraint: it makes
    #: "did this message already become requests?" answerable from the requests table
    #: itself, which is what a duplicate delivery arriving mid-transaction needs.
    #:
    #: Not personal data: a provider message id identifies a message, not a person.
    original_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    district: Mapped["District | None"] = relationship(back_populates="requests")
    responses: Mapped[list["RequestResponse"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
        order_by="RequestResponse.created_at",
    )


class RequestResponse(Base):
    """What an official replied, in which language, and what it changed.

    Note what is still absent, because a grievance thread is the usual place
    personal data leaks into a system like this: no citizen contact detail, and
    `responder_desk` is a role — "Water Resources Desk, Nabarangpur" — not a
    named officer. The reply is addressed to a `citizen_ref` and delivered by the
    channel adapter, which is the only component that ever holds a routing
    identifier, and does not persist it.

    Statuses are recorded per reply rather than only on the request, so the
    console can show how a case moved rather than just where it ended up.
    """
    __tablename__ = "request_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("citizen_requests.id"), index=True)

    body_en: Mapped[str] = mapped_column(Text)
    # The same reply in the language the citizen wrote in. Nullable because with
    # no Gemini key there is no translation, and storing the English text twice
    # would misrepresent an untranslated reply as a translated one.
    body_native: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="en")
    responder_desk: Mapped[str] = mapped_column(String(128), default="")

    status_before: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status_after: Mapped[str | None] = mapped_column(String(16), nullable=True)

    delivery_channel: Mapped[str] = mapped_column(String(16), default="text")
    # "queued" is the honest value. Outbound WhatsApp and IVR need a Meta
    # Business app and a telephony account, neither of which is free or
    # instant, so nothing in this repository claims to have sent a message.
    delivery_state: Mapped[str] = mapped_column(String(16), default="queued")
    created_at: Mapped[datetime] = mapped_column(default=_now, index=True)

    request: Mapped["CitizenRequest"] = relationship(back_populates="responses")


class ChannelSession(Base):
    """Multi-turn conversation session for IVR and messaging channels.

    PRIVACY GUARANTEE:
    `citizen_ref` is strictly the HMAC-SHA256 pseudonymised handle (e.g.
    'anon_...'), never the raw calling line or WhatsApp MSISDN. Storing a phone
    number here would violate Constraint 5 and DPG privacy compliance.

    `context_data` is a JSON-encoded dictionary storing session-scoped working
    state (e.g. prompt attempts, language choice, last processed message ID for
    idempotency).
    """
    __tablename__ = "channel_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    citizen_ref: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(16), default="ivr", index=True)
    current_state: Mapped[str] = mapped_column(String(32), default="INITIAL", index=True)
    language: Mapped[str] = mapped_column(String(8), default="hi")
    context_data: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    created_at: Mapped[datetime] = mapped_column(default=_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now, index=True)

    def get_context(self) -> dict:
        import json
        try:
            return json.loads(self.context_data or "{}")
        except Exception:
            return {}

    def set_context(self, data: dict) -> None:
        import json
        self.context_data = json.dumps(data)


class ChannelEvent(Base):
    """Atomic event deduplication store for external channel webhooks and callbacks.

    Ensures idempotency across Meta message IDs, Exotel CallSids, RecordingSids,
    SMS Sids, and retry callbacks.

    PRIVACY GUARANTEE:
    Stores only provider IDs and request links. Never stores raw phone numbers.
    """
    __tablename__ = "channel_events"
    __table_args__ = (
        UniqueConstraint("provider", "external_event_id", "event_type", name="uq_channel_event"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)  # "exotel", "whatsapp", "simulator"
    external_event_id: Mapped[str] = mapped_column(String(128), index=True)  # CallSid, MessageId, RecordingSid
    event_type: Mapped[str] = mapped_column(String(32), index=True)  # "sms_inbound", "ivr_recording", "whatsapp_message", "status_callback"
    status: Mapped[str] = mapped_column(String(32), default="RECEIVED", server_default="RECEIVED", index=True)  # RECEIVED, PROCESSING, PROCESSED, FAILED, DUPLICATE
    request_id: Mapped[int | None] = mapped_column(ForeignKey("citizen_requests.id"), nullable=True, index=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now, index=True)


