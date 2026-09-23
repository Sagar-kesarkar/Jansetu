"""Accountless tracking — the token, and the citizen's view of their own case.

Why this feature carries its own test file rather than joining `test_casework.py`:
the console's tests assert that an officer can move a case, and their threat model
is "does the workflow work". This one's threat model is **enumeration**. There is
no account, no OTP and no session behind a tracking token — requiring any of them
would exclude the users the platform exists for, someone who filed over IVR from a
feature phone — so the token's entropy is the entire access control, and the tests
that matter are the ones that would notice it weakening.

Four guarantees, each failing differently:

1. **The token cannot be walked.** The rejected design was `JS-<PIN>-<serial>`,
   which is friendlier to read down a phone line and lets anyone who knows one
   token in a PIN read every complaint in that PIN by counting. So: 30**8 random
   payloads, and `test_tokens_are_not_sequential` is what fails if someone
   "improves" it back into a counter.
2. **A malformed token and an unknown token are indistinguishable.** Telling them
   apart confirms to a guesser which of their guesses were well-formed, which is
   the only signal needed to narrow the space.
3. **`normalise` never silently resolves to a *different* valid token.** Two
   near-misses hide here: `JS` is strippable prefix and also two payload letters,
   and dropping an out-of-alphabet character would shift every character after it.
4. **The response withholds `citizen_ref`.** It is a per-reporter handle and
   `GET /requests?citizen_ref=` accepts it, so returning it would turn one
   shoulder-surfed token into a key to that person's entire history. This is the
   single most important thing the response does not contain.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db.database import SessionLocal, init_db
from app.db.models import CitizenRequest, District, RequestResponse
from app.main import app
from app.models.schemas import (
    STEP_OF_STATUS,
    TRACK_STEPS,
    Channel,
    ExtractedRequest,
    LocationHierarchy,
    RequestStatus,
)
from app.services import pipeline
from app.services.tracking import (
    ALPHABET,
    TOKEN_LENGTH,
    backfill,
    find_request,
    format_token,
    issue_token,
    normalise,
)

TRACK_DISTRICT = "TRK_KHORDHA"


@pytest.fixture(scope="module", autouse=True)
def seeded():
    init_db()
    db = SessionLocal()
    try:
        db.merge(District(code=TRACK_DISTRICT, name="Khordhapur", state="Odisha",
                          population=2_250_000, latitude=20.2, longitude=85.6,
                          literacy_pct=86.9, internet_pct=41.7, deprivation_index=0.31))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client():
    return TestClient(app)


def _file(db, monkeypatch, *, text="Handpump is dry.", language="or"):
    """One request through the real pipeline, with extraction pinned.

    Pinned rather than left to the keyless fallback because the fallback's
    category and urgency are inputs to nothing here — what is being tested is the
    token and the view of it, and a deterministic row makes the assertions about
    labels legible.
    """
    monkeypatch.setattr(
        pipeline, "extract_request",
        lambda text, language="hi", **_: ExtractedRequest(
            category="WATER_SUPPLY", summary_en="Handpump has been dry for a week.",
            summary_native="ପାଣି ନାହିଁ।", urgency=4, confidence=0.9, location_text=None,
            location=LocationHierarchy(state="Odisha", district_or_city="Bhubaneswar",
                                       locality="Patia"),
        ),
    )
    return pipeline.ingest(db, text=text, language=language, channel=Channel.TEXT,
                           location_text="Patia, Bhubaneswar, Odisha")


# ---------- 1. the token itself ----------

def test_the_alphabet_excludes_every_character_a_person_would_misread():
    """I/L/O/U/0/1 are absent by design. A token is read aloud down an IVR line
    and copied off a screen by hand, so O-versus-0 is not a cosmetic concern —
    it is a citizen unable to reach their own case. U is excluded separately, to
    keep the generator from ever assembling an offensive word."""
    for banned in "ILOU01":
        assert banned not in ALPHABET
    assert len(ALPHABET) == 30
    assert ALPHABET == "".join(sorted(set(ALPHABET))), "no duplicate weights the draw"


def test_tokens_are_not_sequential(db):
    """The rejected design, asserted against. `JS-410206-0001` would let anyone
    holding one token read every complaint in that PIN by counting upwards."""
    tokens = [issue_token(db, taken=set()) for _ in range(50)]
    payloads = [t.replace("JS-", "").replace("-", "") for t in tokens]

    assert len(set(payloads)) == len(payloads), "collision in 50 draws"
    # A counter would make consecutive payloads adjacent. Random ones share almost
    # no prefix: the chance that any two of 50 share even their first two
    # characters in order is negligible, so any ordering at all is a regression.
    assert payloads != sorted(payloads)
    assert not any(a[:4] == b[:4] for a, b in zip(payloads, payloads[1:]))


def test_the_shape_is_the_one_the_citizen_was_promised():
    assert format_token("7K4M92QX") == "JS-7K4M-92QX"
    assert TOKEN_LENGTH == 8
    issued = format_token("".join(ALPHABET[:8]))
    assert issued.count("-") == 2
    assert len(issued) == len("JS-7K4M-92QX") == 12


def test_no_collision_across_a_large_draw(db):
    """30**8 is 6.5e11, so 20,000 draws colliding would mean the entropy is not
    what the docstring claims. Uses the in-memory `taken` set rather than 20,000
    round trips."""
    seen: set[str] = set()
    for _ in range(20_000):
        seen.add(issue_token(db, taken=seen))
    assert len(seen) == 20_000


# ---------- 2. reading a token back the way a human typed it ----------

@pytest.mark.parametrize("typed", [
    "JS-7K4M-92QX", "js-7k4m-92qx", "JS7K4M92QX", "js7k4m92qx",
    "  JS-7K4M-92QX  ", "JS 7K4M 92QX", "JS_7K4M_92QX", "7K4M92QX", "7k4m-92qx",
])
def test_every_way_a_person_might_type_it_resolves_the_same(typed):
    assert normalise(typed) == "JS-7K4M-92QX"


def test_a_payload_beginning_JS_is_not_mistaken_for_the_prefix():
    """The near-miss that an unguarded `lstrip("JS")` would cause. J and S are
    both payload characters, so `JS4M92QX` is a legitimate prefixless token — and
    stripping unconditionally would turn it into the six-character `4M92QX` and
    fail. The strip is therefore length-guarded."""
    assert normalise("JS4M92QX") == "JS-JS4M-92QX"
    assert normalise("JSJS4M92QX") == "JS-JS4M-92QX"
    assert normalise("JS-JS4M-92QX") == "JS-JS4M-92QX"


@pytest.mark.parametrize("bad", [
    "JS-7K4M-92QO",   # O is not in the alphabet
    "JS-7K4M-92Q1",   # 1 is not in the alphabet
    "JS-7K4M-92Q",    # too short
    "JS-7K4M-92QXX",  # too long
    "garbage", "", "   ", "JS--",
])
def test_a_bad_token_is_refused_rather_than_repaired(bad):
    """Refusing matters more than it looks. Stripping the offending character
    instead would shift everything after it, and `JS-7K4M-92QO7` could silently
    normalise to a *different* well-formed token — somebody else's case."""
    assert normalise(bad) is None


# ---------- 3. the endpoint ----------

def test_a_citizen_can_read_their_own_case_back(db, monkeypatch, client):
    result = _file(db, monkeypatch)
    assert result.track_token, "intake must return a token or there is no way back"

    got = client.get(f"/track/{result.track_token}")
    assert got.status_code == 200
    body = got.json()

    assert body["track_token"] == result.track_token
    assert body["summary_en"] == "Handpump has been dry for a week."
    assert body["original_text"] == "Handpump is dry."
    assert body["category_label"], "an enum member is not a thing to show a citizen"
    assert body["status_label"] == "Submitted"
    assert body["step_index"] == 0
    assert [s["key"] for s in body["steps"]] == [k for k, _ in TRACK_STEPS]
    assert [s["reached"] for s in body["steps"]] == [True, False, False, False, False, False]
    assert body["steps"][0]["at"], "the filing time is the one date that is certain"
    assert body["is_closed"] is False
    assert body["latest_response"] is None and body["response_count"] == 0


def test_the_response_never_carries_the_reporter_handle(db, monkeypatch, client):
    """Guarantee 4, and the reason this test would be worth the file on its own.
    `citizen_ref` is stable across everything a sender ever files and
    `GET /requests?citizen_ref=` accepts it, so one shoulder-surfed token would
    otherwise open that person's whole history."""
    result = _file(db, monkeypatch)
    stored = db.get(CitizenRequest, result.request_id)
    assert stored.citizen_ref, "the row must actually have one to be withholding it"

    got = client.get(f"/track/{result.track_token}")
    assert "citizen_ref" not in got.json()
    assert stored.citizen_ref not in got.text


def test_the_token_is_per_request_not_per_reporter(db, monkeypatch):
    """Two reports from the same sender share a `citizen_ref` and must not share a
    token, which is the whole reason `track_token` is a separate column."""
    monkeypatch.setattr(pipeline, "extract_request",
                        lambda text, language="hi", **_: ExtractedRequest(
                            category="ROADS", summary_en="a", summary_native="a",
                            urgency=2, confidence=0.5, location=LocationHierarchy()))
    a = pipeline.ingest(db, text="First report about the road.", language="en",
                        channel=Channel.WHATSAPP, citizen_ref="+910000000000")
    b = pipeline.ingest(db, text="Second report about the drain.", language="en",
                        channel=Channel.WHATSAPP, citizen_ref="+910000000000")

    rows = [db.get(CitizenRequest, a.request_id), db.get(CitizenRequest, b.request_id)]
    assert rows[0].citizen_ref == rows[1].citizen_ref, "same sender, same handle"
    assert a.track_token != b.track_token, "same sender must not mean same token"


@pytest.mark.parametrize("token", [
    "JS-2222-2222",   # well-formed, not ours
    "JS-7K4M-92QO",   # malformed: O
    "garbage",
    "JS-7K4M-92Q",    # malformed: short
])
def test_unknown_and_malformed_tokens_are_indistinguishable(client, token):
    """Guarantee 2. Different messages would tell a guesser which guesses were
    well-formed, and that is the only signal enumeration needs."""
    got = client.get(f"/track/{token}")
    assert got.status_code == 404
    assert got.json()["detail"] == client.get("/track/JS-2222-2222").json()["detail"]


def test_lookup_ignores_case_and_punctuation_end_to_end(db, monkeypatch, client):
    result = _file(db, monkeypatch)
    messy = result.track_token.replace("-", "").lower()
    got = client.get(f"/track/{messy}")
    assert got.status_code == 200
    assert got.json()["track_token"] == result.track_token


def test_find_request_returns_nothing_for_a_token_nobody_holds(db):
    assert find_request(db, "JS-2222-2222") is None
    assert find_request(db, "not a token") is None


# ---------- 4. the stepper ----------

def test_the_stepper_fills_forward_rather_than_marking_one_rung(db, monkeypatch, client):
    """A case that skipped rungs — e.g. went straight to IN_PROGRESS — still passed
    assignment. Drawing those as unreached would show a citizen a broken bar and
    imply work was skipped."""
    result = _file(db, monkeypatch)
    row = db.get(CitizenRequest, result.request_id)
    row.status = RequestStatus.IN_PROGRESS.value
    db.commit()

    body = client.get(f"/track/{result.track_token}").json()
    assert body["step_index"] == 4
    assert [s["reached"] for s in body["steps"]] == [True, True, True, True, True, False]
    # No date is invented for a rung nothing recorded a transition into.
    assert body["steps"][1]["at"] is None
    assert body["steps"][2]["at"] is None


def test_acknowledged_advances_to_acknowledged_step(db, monkeypatch, client):
    """A desk confirming receipt advances the tracker to the Acknowledged step
    without falsely claiming Under Review."""
    result = _file(db, monkeypatch)
    row = db.get(CitizenRequest, result.request_id)
    row.status = RequestStatus.ACKNOWLEDGED.value
    db.commit()

    body = client.get(f"/track/{result.track_token}").json()
    assert body["step_index"] == 1
    assert body["status_label"] == "Receipt acknowledged"
    assert body["steps"][1]["reached"] is True
    assert body["steps"][2]["reached"] is False


def test_a_refused_case_is_not_drawn_as_a_finished_one(db, monkeypatch, client):
    """REJECTED is a different ending, not a later stage. A filled bar to
    somebody whose request was refused is the worst thing this screen could do."""
    result = _file(db, monkeypatch)
    row = db.get(CitizenRequest, result.request_id)
    row.status = RequestStatus.REJECTED.value
    db.commit()

    body = client.get(f"/track/{result.track_token}").json()
    assert body["step_index"] is None
    # Nothing above the filing rung is claimed: no review, no assignment, and
    # above all no Resolved.
    assert [s["reached"] for s in body["steps"][1:]] == [False, False, False, False, False]
    assert body["is_closed"] is True
    assert body["status_label"] == "Closed without action"
    assert STEP_OF_STATUS[RequestStatus.REJECTED.value] is None


def test_a_refused_case_still_admits_the_report_was_filed(db, monkeypatch, client):
    """Rung 0 is unconditional, and this is the case that proves why.

    "Submitted" is true of every row in the table — that is what its existence
    means, and `created_at` dates it. Letting an off-the-ladder status blank the
    whole rail showed a refused citizen five empty rungs sitting directly above
    the department's written refusal, which reads as "nothing has happened yet"
    rather than "this ended". The bar is not filled; it is one rung long.
    """
    result = _file(db, monkeypatch)
    row = db.get(CitizenRequest, result.request_id)
    row.status = RequestStatus.REJECTED.value
    db.commit()

    body = client.get(f"/track/{result.track_token}").json()
    assert body["steps"][0]["reached"] is True
    assert body["steps"][0]["at"] is not None
    assert sum(s["reached"] for s in body["steps"]) == 1


def test_an_official_reply_reaches_the_citizen_with_a_desk_and_no_name(db, monkeypatch, client):
    result = _file(db, monkeypatch)
    row = db.get(CitizenRequest, result.request_id)
    db.add(RequestResponse(
        request_id=row.id, body_en="A tanker has been scheduled for Thursday.",
        body_native=None, language="or", responder_desk="Water Resources Desk, Khordha",
        status_before=RequestStatus.NEW.value, status_after=RequestStatus.ASSIGNED.value,
        delivery_channel="text", delivery_state="queued",
    ))
    row.status = RequestStatus.ASSIGNED.value
    db.commit()

    body = client.get(f"/track/{result.track_token}").json()
    assert body["response_count"] == 1
    assert body["latest_response"]["body_en"].startswith("A tanker")
    assert body["latest_response"]["responder_desk"] == "Water Resources Desk, Khordha"
    assert body["step_index"] == 3
    # The reply is the only dated transition record, so rung 3 gets a real date.
    assert body["steps"][3]["at"] is not None


# ---------- 5. the migration path ----------

def test_backfill_issues_a_token_to_every_row_that_predates_the_column(db, monkeypatch):
    """The column arrives on an already-seeded database as nullable — SQLite's
    ALTER TABLE cannot add a UNIQUE column — so a NULL is a transient state that
    this closes at boot. Idempotent, because it runs on every boot."""
    result = _file(db, monkeypatch)
    row = db.get(CitizenRequest, result.request_id)
    row.track_token = None
    db.commit()

    assert db.query(CitizenRequest).filter(CitizenRequest.track_token.is_(None)).count() >= 1
    issued = backfill(db)
    assert issued >= 1
    assert db.query(CitizenRequest).filter(CitizenRequest.track_token.is_(None)).count() == 0
    assert backfill(db) == 0, "a second boot must be a no-op"

    tokens = [t for (t,) in db.query(CitizenRequest.track_token).all()]
    assert len(set(tokens)) == len(tokens), "backfill must not mint a duplicate"


def test_the_unique_index_actually_exists_on_the_database(db):
    """`unique=True` on the model is not self-enforcing here. SQLite forbids a
    UNIQUE constraint in `ALTER TABLE ADD COLUMN`, so on a pre-existing database
    the guarantee only holds if `_add_missing_indexes` created the index — and if
    it silently did not, every claim in `tracking.py` is false."""
    from sqlalchemy import inspect

    from app.db.database import engine

    indexes = inspect(engine).get_indexes("citizen_requests")
    match = [i for i in indexes if i["column_names"] == ["track_token"]]
    assert match, "no index on track_token"
    assert match[0]["unique"], "the index exists but does not enforce uniqueness"


def test_tracking_returns_audit_history_and_live_timing(db, monkeypatch, client):
    """Verify tracking endpoint includes created_at, updated_at, token alias and chronological history."""
    result = _file(db, monkeypatch)
    token = result.track_token

    # 1. Initial state
    r1 = client.get(f"/track/{token}")
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["token"] == token
    assert d1["created_at"] is not None
    assert d1["updated_at"] is not None
    assert len(d1["history"]) == 1
    assert d1["history"][0]["status_label"] == "Grievance Registered"
    assert d1["status_history"] == d1["history"]

    # 2. Add an official status change
    req_id = result.request_id
    patch_res = client.patch(f"/requests/{req_id}/status", json={"status": "UNDER_REVIEW"})
    assert patch_res.status_code == 200

    # 3. Read back tracking endpoint
    r2 = client.get(f"/track/{token}")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["status"] == "UNDER_REVIEW"
    assert d2["step_index"] == 2
    assert len(d2["history"]) == 2
    assert d2["history"][0]["status_after"] == "NEW"
    assert d2["history"][1]["status_after"] == "UNDER_REVIEW"
    assert d2["history"][1]["status_label"] == "Under review"
    assert d2["updated_at"] >= d2["created_at"]


def test_full_status_progression_and_audit_history(db, monkeypatch, client):
    """Test full sequential lifecycle: NEW -> ACKNOWLEDGED -> UNDER_REVIEW -> ASSIGNED -> IN_PROGRESS -> RESOLVED."""
    result = _file(db, monkeypatch)
    token = result.track_token
    req_id = result.request_id

    sequence = [
        ("ACKNOWLEDGED", 1, "Receipt acknowledged"),
        ("UNDER_REVIEW", 2, "Under review"),
        ("ASSIGNED", 3, "Assigned to department"),
        ("IN_PROGRESS", 4, "Work in progress"),
        ("RESOLVED", 5, "Resolved"),
    ]

    for status_val, expected_step, expected_label in sequence:
        patch = client.patch(f"/requests/{req_id}/status", json={"status": status_val})
        assert patch.status_code == 200
        got = client.get(f"/track/{token}").json()
        assert got["status"] == status_val
        assert got["step_index"] == expected_step
        assert got["status_label"] == expected_label
        assert got["steps"][expected_step]["reached"] is True

    final = client.get(f"/track/{token}").json()
    assert final["is_closed"] is True
    assert len(final["history"]) == 6
    # Verify events are in chronological order
    timestamps = [h["timestamp"] for h in final["history"]]
    assert timestamps == sorted(timestamps)


def test_idempotent_status_update_does_not_duplicate_audit_events(db, monkeypatch, client):
    """Patching the exact same status repeatedly should not duplicate audit history rows."""
    result = _file(db, monkeypatch)
    token = result.track_token
    req_id = result.request_id

    client.patch(f"/requests/{req_id}/status", json={"status": "UNDER_REVIEW"})
    client.patch(f"/requests/{req_id}/status", json={"status": "UNDER_REVIEW"})
    client.patch(f"/requests/{req_id}/status", json={"status": "UNDER_REVIEW"})

    data = client.get(f"/track/{token}").json()
    assert len(data["history"]) == 2  # Registration + single transition


def test_needs_location_special_status(db, monkeypatch, client):
    """A request with status NEEDS_LOCATION stays at stage 0, shows needs_location=True."""
    result = _file(db, monkeypatch)
    token = result.track_token
    row = db.get(CitizenRequest, result.request_id)
    row.status = RequestStatus.NEEDS_LOCATION.value
    db.commit()

    data = client.get(f"/track/{token}").json()
    assert data["status"] == "NEEDS_LOCATION"
    assert data["needs_location"] is True
    assert data["step_index"] is None
    assert data["steps"][0]["reached"] is True

