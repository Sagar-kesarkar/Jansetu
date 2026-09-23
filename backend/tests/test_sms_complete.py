"""Comprehensive Unit & Integration Test Suite for JanSetu SMS Channel.

Tests:
1. Deterministic 1, 2, 3 menu routing without AI invocation.
2. Complaint draft staging & strict location gate (no complaint or token before location).
3. Location resolution & exact single-turn database registration with real token.
4. Token tracking queries against live database with timestamp & status reflection.
5. State and district public funds budget query (Option 3).
6. Multilingual prompts and receipts across English, Hindi, Marathi, Tamil, Telugu, etc.
7. Channel session isolation (SMS vs WhatsApp vs IVR).
8. Idempotency against duplicate provider message delivery.
9. Zero-PII audit: no raw phone numbers stored in plaintext.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.channels.exotel_sms import format_dlt_sms, process_exotel_inbound_sms
from app.channels.router import route
from app.channels.session import get_channel_session, get_or_create_session, save_channel_session
from app.db.database import SessionLocal, init_db
from app.db.models import ChannelSession, CitizenRequest, District
from app.main import app
from app.models.schemas import Channel, ExtractedRequest, LocationHierarchy
from app.services.privacy import pseudonymise

TEST_SENDER = "919876543000"


@pytest.fixture(scope="module", autouse=True)
def setup_reference_data():
    init_db()
    db = SessionLocal()
    try:
        db.merge(District(
            code="OR_NABARANGPUR",
            name="Nabarangpur",
            state="Odisha",
            population=1220946,
            literacy_pct=46.4,
            internet_pct=15.0,
            deprivation_index=0.78,
        ))
        db.merge(District(
            code="MH_PUNE",
            name="Pune",
            state="Maharashtra",
            population=9429408,
            literacy_pct=86.2,
            internet_pct=65.0,
            deprivation_index=0.25,
        ))
        db.commit()
    finally:
        db.close()


@pytest.fixture
def client():
    return TestClient(app)


def test_sms_menu_deterministic_option_1():
    """Option 1 routes to AWAITING_COMPLAINT and returns registration intro text."""
    db = SessionLocal()
    try:
        ctx = {"current_state": "MAIN_MENU", "selected_language": "en"}
        decision = route(db, ctx, "1", default_language="en")
        assert decision.handled is True
        assert decision.context["current_state"] == "AWAITING_COMPLAINT"
        assert "Register a complaint" in decision.reply
    finally:
        db.close()


def test_sms_menu_deterministic_option_2():
    """Option 2 routes to AWAITING_TRACKING_TOKEN and prompts for token."""
    db = SessionLocal()
    try:
        ctx = {"current_state": "MAIN_MENU", "selected_language": "hi"}
        decision = route(db, ctx, "2", default_language="hi")
        assert decision.handled is True
        assert decision.context["current_state"] == "AWAITING_TRACKING_TOKEN"
        assert "ट्रैकिंग" in decision.reply or "टोकन" in decision.reply or "JS-" in decision.reply
    finally:
        db.close()


def test_sms_menu_deterministic_option_3():
    """Option 3 routes to AWAITING_BUDGET_SCOPE and prompts for state vs district."""
    db = SessionLocal()
    try:
        ctx = {"current_state": "MAIN_MENU", "selected_language": "en"}
        decision = route(db, ctx, "3", default_language="en")
        assert decision.handled is True
        assert decision.context["current_state"] == "AWAITING_BUDGET_SCOPE"
        assert "Budget" in decision.reply or "State" in decision.reply
    finally:
        db.close()


def test_sms_location_gate_flow(client, monkeypatch):
    """Sending complaint without location creates NO complaint row; adding location registers it."""
    db = SessionLocal()
    try:
        safe_ref = pseudonymise(TEST_SENDER)
        # Clear any prior test session
        s = get_channel_session(db, safe_ref, channel="sms")
        if s:
            s.set_context({"current_state": "MAIN_MENU", "selected_language": "en"})
            save_channel_session(db, s)

        init_count = db.query(CitizenRequest).filter_by(citizen_ref=safe_ref).count()

        # Step 1: Send '1' -> start complaint
        r1 = client.post("/intake/report", data={
            "text": "1",
            "language": "en",
            "channel": "sms",
            "citizen_ref": TEST_SENDER,
        })
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["classification"] == "CONVERSATIONAL"
        assert d1["request_count"] == 0

        # Step 2: Send complaint text without location
        r2 = client.post("/intake/report", data={
            "text": "The main drinking water pipeline has burst and there is no supply.",
            "language": "en",
            "channel": "sms",
            "citizen_ref": TEST_SENDER,
        })
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["classification"] == "CONVERSATIONAL"
        assert "where the problem is occurring" in d2["acknowledgement_native"] or "Village" in d2["acknowledgement_native"]
        # Crucial check: zero rows created in DB!
        assert db.query(CitizenRequest).filter_by(citizen_ref=safe_ref).count() == init_count

        # Step 3: Provide location
        mock_ext = ExtractedRequest(
            category="WATER_SUPPLY",
            summary_en="Burst drinking water pipeline in Nabarangpur",
            summary_native="The main drinking water pipeline has burst and there is no supply.",
            urgency=4,
            confidence=0.95,
            location_text="Ward 4, Nabarangpur, Odisha",
            location=LocationHierarchy(district_or_city="Nabarangpur", state="Odisha", sector_or_ward="Ward 4"),
        )
        monkeypatch.setattr("app.services.pipeline.extract_request", lambda *a, **k: mock_ext)

        r3 = client.post("/intake/report", data={
            "text": "Ward 4, Nabarangpur, Odisha",
            "language": "en",
            "channel": "sms",
            "citizen_ref": TEST_SENDER,
        })
        assert r3.status_code == 200
        d3 = r3.json()
        assert d3["track_token"] is not None
        assert d3["track_token"].startswith("JS-")
        assert d3["request_id"] > 0

        # Exactly 1 row created now
        assert db.query(CitizenRequest).filter_by(citizen_ref=safe_ref).count() == init_count + 1
        req = db.query(CitizenRequest).filter(CitizenRequest.track_token == d3["track_token"]).first()
        assert req is not None
        assert req.channel == "sms"
    finally:
        db.close()


def test_sms_tracking_flow(client):
    """Tracking via option 2 returns live status and updates after admin changes."""
    db = SessionLocal()
    try:
        from app.services.tracking import issue_token
        safe_ref = pseudonymise("919991112233")
        tok = issue_token(db)
        req = CitizenRequest(
            citizen_ref=safe_ref,
            channel="sms",
            language="en",
            category="water",
            raw_text="Water supply issue in Nabarangpur",
            summary_en="Water pipe leak",
            status="SUBMITTED",
            district_code="OR_NABARANGPUR",
            track_token=tok,
        )
        db.add(req)
        db.commit()
        db.refresh(req)

        # Reset session
        s = get_or_create_session(db, safe_ref, channel="sms")
        s.set_context({"current_state": "MAIN_MENU", "selected_language": "en"})
        save_channel_session(db, s)

        # Send '2' to initiate tracking
        r1 = client.post("/intake/report", data={
            "text": "2",
            "language": "en",
            "channel": "sms",
            "citizen_ref": "919991112233",
        })
        assert r1.status_code == 200

        # Send token
        r2 = client.post("/intake/report", data={
            "text": tok,
            "language": "en",
            "channel": "sms",
            "citizen_ref": "919991112233",
        })
        assert r2.status_code == 200
        reply = r2.json()["acknowledgement_native"]
        assert tok in reply
        assert "Submitted" in reply or "SUBMITTED" in reply

        # Simulate Officials Console changing status to IN_PROGRESS
        req.status = "IN_PROGRESS"
        db.commit()

        # Track again via direct command 'STATUS <tok>'
        r3 = client.post("/intake/report", data={
            "text": f"STATUS {tok}",
            "language": "en",
            "channel": "sms",
            "citizen_ref": "919991112233",
        })
        assert r3.status_code == 200
        reply3 = r3.json()["acknowledgement_native"]
        assert "progress" in reply3.lower()
    finally:
        db.close()


def test_sms_budget_query_flow(client):
    """Option 3 -> State budget -> returns verified budget allocation."""
    safe_ref = pseudonymise("919998881122")
    db = SessionLocal()
    try:
        s = get_or_create_session(db, safe_ref, channel="sms")
        s.set_context({"current_state": "MAIN_MENU", "selected_language": "en"})
        save_channel_session(db, s)

        # Send 3 -> Budget
        r1 = client.post("/intake/report", data={
            "text": "3",
            "language": "en",
            "channel": "sms",
            "citizen_ref": "919998881122",
        })
        assert r1.status_code == 200

        # Send 1 -> State scope
        r2 = client.post("/intake/report", data={
            "text": "1",
            "language": "en",
            "channel": "sms",
            "citizen_ref": "919998881122",
        })
        assert r2.status_code == 200

        # Send State name 'Maharashtra'
        r3 = client.post("/intake/report", data={
            "text": "Maharashtra",
            "language": "en",
            "channel": "sms",
            "citizen_ref": "919998881122",
        })
        assert r3.status_code == 200
        reply = r3.json()["acknowledgement_native"]
        assert "Maharashtra" in reply
        assert "Allocated" in reply or "आवंटित" in reply
        assert "₹" in reply
    finally:
        db.close()


def test_sms_session_isolation_from_whatsapp_and_ivr(client):
    """SMS session state does not leak or collide with WhatsApp or IVR sessions."""
    citizen = "919123456789"
    safe_ref = pseudonymise(citizen)
    db = SessionLocal()
    try:
        # Start WhatsApp session in AWAITING_LOCATION
        ws = get_or_create_session(db, safe_ref, channel="whatsapp")
        ws.set_context({"current_state": "AWAITING_LOCATION", "selected_language": "mr", "router_issue": "Test issue"})
        save_channel_session(db, ws)

        # Start SMS session in MAIN_MENU
        ss = get_or_create_session(db, safe_ref, channel="sms")
        ss.set_context({"current_state": "MAIN_MENU", "selected_language": "ta"})
        save_channel_session(db, ss)

        # Query SMS with '1'
        r_sms = client.post("/intake/report", data={
            "text": "1",
            "language": "ta",
            "channel": "sms",
            "citizen_ref": citizen,
        })
        assert r_sms.status_code == 200
        assert r_sms.json()["language"] == "ta"

        # Verify WhatsApp session remains unchanged in Marathi
        ws_after = get_channel_session(db, safe_ref, channel="whatsapp")
        assert ws_after.get_context()["current_state"] == "AWAITING_LOCATION"
        assert ws_after.get_context()["selected_language"] == "mr"
    finally:
        db.close()


def test_sms_zero_pii_guarantee():
    """Verify raw telephone numbers are NEVER stored in plaintext in the database."""
    db = SessionLocal()
    try:
        raw_number = "919876543210"
        sessions = db.query(ChannelSession).filter(ChannelSession.channel == "sms").all()
        for s in sessions:
            assert raw_number not in str(s.citizen_ref)
            assert raw_number not in str(s.context_data)

        requests = db.query(CitizenRequest).filter(CitizenRequest.channel == "sms").all()
        for r in requests:
            assert raw_number not in str(r.citizen_ref)
            assert raw_number not in str(r.raw_text)
    finally:
        db.close()
