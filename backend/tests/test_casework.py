"""The officials' casework layer: replies, statuses, and reporter threads.

The test this module exists for is `test_casework_cannot_move_a_ranking`. Every
other endpoint in the API is read-only over citizen data; these are the first
that let a government user *write*. That creates a failure mode the rest of the
project does not have — if closing a case changed a district's score, the
priority list would become a thing officials manage rather than a thing they are
measured by, and the credibility claim in the pitch would be false.

`app/analytics/` reads category, urgency and district and nothing else, so the
property holds by construction. It is asserted here anyway, because "by
construction" is exactly the kind of guarantee a later convenience join breaks
silently.

Gemini is off for the suite (see conftest), so this also pins the honest
behaviour of the untranslated path: `body_native` stays NULL rather than being
filled with the English text.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db.database import SessionLocal, init_db
from app.db.models import CitizenRequest, District, InfraIndex, InvestmentPlan, RequestResponse
from app.main import app

DISTRICT = "CASE_D1"
REPEAT_REF = "anon_repeatreporter000000"


@pytest.fixture(scope="module", autouse=True)
def seeded_db():
    init_db()
    db = SessionLocal()
    try:
        db.query(RequestResponse).delete()
        db.query(CitizenRequest).delete()
        db.query(InfraIndex).delete()
        db.query(InvestmentPlan).delete()
        db.merge(District(code=DISTRICT, name="Casepur", state="Caseland",
                          population=800_000, latitude=21.5, longitude=79.5,
                          literacy_pct=48.0, internet_pct=13.0, deprivation_index=0.85))
        db.add(InfraIndex(district_code=DISTRICT, category="WATER_SUPPLY", coverage_pct=28.0))
        db.add(InvestmentPlan(district_code=DISTRICT, category="WATER_SUPPLY",
                              scheme="Jal Jeevan Mission", allocated_inr_lakh=40.0))
        # Three from one reporter, three from distinct ones, so the thread view
        # and the queue filters both have something real to assert against.
        for i in range(3):
            db.add(CitizenRequest(
                district_code=DISTRICT, category="WATER_SUPPLY", urgency=4,
                raw_text=f"நீர் இல்லை {i}", summary_en=f"no water {i}", language="ta",
                channel="whatsapp", location_text="Casepur, Caseland", confidence=1.0,
                citizen_ref=REPEAT_REF))
        for i in range(3):
            db.add(CitizenRequest(
                district_code=DISTRICT, category="WATER_SUPPLY", urgency=3,
                raw_text=f"पानी नहीं {i}", summary_en=f"water missing {i}", language="hi",
                channel="ivr", location_text="Casepur, Caseland", confidence=1.0,
                citizen_ref=f"anon_solo{i}"))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture
def first_id(client) -> int:
    return client.get("/requests", params={"citizen_ref": REPEAT_REF}).json()[0]["id"]


# ---------- the constraint ----------

def test_casework_cannot_move_a_ranking(client):
    """Reply to every case and resolve them all; the score must not budge."""
    before = client.get("/hotspots", params={"category": "WATER_SUPPLY"}).json()
    assert before, "need a scored cell to make this assertion meaningful"
    baseline = before[0]["unmet_need_score"]

    for row in client.get("/requests", params={"limit": 100}).json():
        r = client.post(f"/requests/{row['id']}/responses", json={
            "body_en": "Tanker service arranged and pipeline repair sanctioned.",
            "responder_desk": "Rural Water Supply Desk, Casepur",
            "new_status": "RESOLVED",
        })
        assert r.status_code == 201, r.text

    after = client.get("/hotspots", params={"category": "WATER_SUPPLY"}).json()
    assert after[0]["unmet_need_score"] == baseline, (
        "closing every case changed the score — analytics is reading casework state"
    )
    assert after[0]["request_count"] == before[0]["request_count"]

    # And the recommendation built on top of it is equally unmoved.
    recs = client.get("/recommendations", params={"category": "WATER_SUPPLY"}).json()
    assert recs[0]["unmet_need_score"] == baseline


def test_reply_table_carries_no_identifying_columns():
    """Mirrors tests/test_privacy.py for the reply side. A callback field is the
    obvious thing to add to a grievance thread and the thing that would break the
    DPG claim, so the column list is pinned rather than trusted."""
    forbidden = {"name", "phone", "phone_number", "mobile", "email", "address",
                 "ip", "ip_address", "device", "device_id", "officer_name"}
    columns = set(RequestResponse.__table__.columns.keys())
    assert not (columns & forbidden), f"PII column on request_responses: {columns & forbidden}"
    assert "citizen_ref" not in columns, "the reply is linked by request_id; no need to copy the ref"


# ---------- replying ----------

def test_reply_advances_a_new_case_and_records_the_transition(client, first_id):
    client.patch(f"/requests/{first_id}/status", json={"status": "NEW"})

    r = client.post(f"/requests/{first_id}/responses", json={
        "body_en": "Field verification has been scheduled for next week.",
        "responder_desk": "Rural Water Supply Desk, Casepur",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status_before"] == "NEW"
    assert body["status_after"] == "ACKNOWLEDGED", "a reply is itself an acknowledgement"
    assert body["delivery_channel"] == "whatsapp", "delivery follows the channel it arrived on"
    assert body["delivery_state"] == "queued", "nothing here may claim a message was sent"

    detail = client.get(f"/requests/{first_id}").json()
    assert detail["status"] == "ACKNOWLEDGED"
    assert detail["response_count"] >= 1


def test_explicit_status_beats_the_implicit_acknowledgement(client, first_id):
    client.patch(f"/requests/{first_id}/status", json={"status": "NEW"})
    r = client.post(f"/requests/{first_id}/responses", json={
        "body_en": "This request falls outside the department's remit.",
        "responder_desk": "District Collectorate, Casepur",
        "new_status": "REJECTED",
    })
    assert r.json()["status_after"] == "REJECTED"
    assert client.get(f"/requests/{first_id}").json()["status"] == "REJECTED"


def test_untranslated_reply_leaves_body_native_null(client, first_id):
    """With no Gemini key the reply cannot be translated. Copying the English in
    would make the console show a Tamil speaker an English reply labelled as
    theirs, which is worse than showing nothing."""
    r = client.post(f"/requests/{first_id}/responses", json={
        "body_en": "Works have been included in this quarter's programme.",
        "responder_desk": "Rural Water Supply Desk, Casepur",
        "translate": True,
    })
    assert r.json()["body_native"] is None


def test_reply_rejects_a_missing_request(client):
    r = client.post("/requests/999999/responses", json={
        "body_en": "This should not be stored anywhere.",
        "responder_desk": "Nowhere Desk",
    })
    assert r.status_code == 404


# ---------- the queue ----------

def test_reporter_thread_links_requests_without_identifying_anyone(client, first_id):
    detail = client.get(f"/requests/{first_id}").json()
    assert len(detail["from_same_reporter"]) == 2, "three reports from one handle"
    assert detail["citizen_ref"] == REPEAT_REF
    assert detail["citizen_ref"].startswith("anon_")
    # The link is the whole justification for the column existing.
    thread = client.get("/requests", params={"citizen_ref": REPEAT_REF}).json()
    assert len(thread) == 3


def test_queue_filters(client):
    assert len(client.get("/requests", params={"channel": "ivr"}).json()) == 3
    assert len(client.get("/requests", params={"language": "ta"}).json()) == 3
    assert len(client.get("/requests", params={"min_urgency": 4}).json()) == 3
    assert len(client.get("/requests", params={"state": "Caseland"}).json()) == 6
    # Searching the citizen's own words, not only our English summary.
    assert len(client.get("/requests", params={"q": "पानी नहीं"}).json()) == 3


def test_queue_is_newest_first_and_pages(client):
    page1 = client.get("/requests", params={"limit": 4}).json()
    page2 = client.get("/requests", params={"limit": 4, "offset": 4}).json()
    stamps = [r["created_at"] for r in page1]
    assert stamps == sorted(stamps, reverse=True), "a queue must open on what just arrived"
    assert not ({r["id"] for r in page1} & {r["id"] for r in page2}), "offset overlapped"


def test_list_exposes_the_original_text_not_only_our_summary(client):
    row = client.get("/requests", params={"language": "ta"}).json()[0]
    assert row["raw_text"] and row["raw_text"] != row["summary_en"]


def test_stats_counts_the_whole_set_not_the_page(client):
    stats = client.get("/requests/stats").json()
    assert stats["total"] == 6
    assert sum(stats["by_status"].values()) == 6
    assert set(stats["by_status"]) == set(stats["status_order"]), "every status present, even at zero"
    assert stats["by_channel"] == {"whatsapp": 3, "ivr": 3}
    assert stats["open"] + stats["by_status"]["RESOLVED"] + stats["by_status"]["REJECTED"] == 6


def test_unanswered_filter_finds_cases_nobody_has_replied_to(client):
    unanswered = client.get("/requests", params={"unanswered": True}).json()
    assert all(r["response_count"] == 0 for r in unanswered)
    stats = client.get("/requests/stats").json()
    assert len(unanswered) == stats["awaiting_first_reply"]
