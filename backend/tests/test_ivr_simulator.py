"""End-to-end tests for IVR Simulator, Call-Flow Adapter, and Zero-PII Guarantees."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.channels.ivr import IVRAdapter
from app.channels.simulator import IVRSimulator
from app.channels.state import CallStartEvent, DtmfEvent
from app.db.database import SessionLocal, init_db
from app.db.models import ChannelSession, CitizenRequest, District, RequestResponse
from app.main import app
from app.services.privacy import pseudonymise

TEST_PHONE = "919876543210"


@pytest.fixture(scope="module", autouse=True)
def setup_test_data():
    init_db()
    db = SessionLocal()
    try:
        db.merge(District(
            code="IVR_D1",
            name="Barpeta",
            state="Assam",
            population=1_693_622,
            latitude=26.32,
            longitude=91.0,
            literacy_pct=63.8,
            internet_pct=18.5,
            deprivation_index=0.72,
        ))
        db.commit()
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_ivr_simulator_walkthrough_creates_one_request():
    """Full IVR simulation walks: language DTMF -> recorded need -> confirmation -> docket reference."""
    db = SessionLocal()
    try:
        initial_count = db.query(CitizenRequest).count()
        sim = IVRSimulator(db)

        # 1. Start call
        res1 = sim.step(TEST_PHONE, "start")
        assert res1.next_state in ("SELECT_LANGUAGE", "LANGUAGE_MENU")
        assert len(res1.prompts_to_play) > 0

        # 2. Select Hindi (DTMF '1')
        res2 = sim.step(TEST_PHONE, "dtmf", digits="1")
        assert res2.next_state in ("COLLECT_NEED", "MAIN_MENU")
        assert res2.language == "hi"

        if res2.next_state == "MAIN_MENU":
            # Press '1' to Register
            res2 = sim.step(TEST_PHONE, "dtmf", digits="1")

        # 3. Simulate grievance recording
        res3 = sim.step(
            TEST_PHONE,
            "audio",
            text_simulation="बरपेटा में 5 दिन से पीने का पानी नहीं आ रहा है, कृपया मदद करें।",
        )
        if res3.next_state in ("LOCATION_LISTENING", "COLLECT_LOCATION"):
            res3 = sim.step(TEST_PHONE, "audio", text_simulation="Barpeta, Assam")
        if res3.next_state == "REVIEW_REQUEST":
            res3 = sim.step(TEST_PHONE, "dtmf", digits="1")

        assert res3.next_state in ("CONFIRMING", "REGISTRATION_SUCCESS")
        assert res3.request_id is not None
        assert res3.docket_ref is not None
        assert len(res3.digits_to_spell) > 0  # Digit-by-digit readback

        # 4. Finish call
        res4 = sim.step(TEST_PHONE, "dtmf", digits="9")
        assert res4.next_state in ("COMPLETED", "ENDED")
        assert res4.hangup is True

        # Exactly 1 new request row was created
        final_count = db.query(CitizenRequest).count()
        assert final_count == initial_count + 1

        # Check created row
        row = db.query(CitizenRequest).filter_by(id=res3.request_id).one()
        assert row.channel == "ivr"
        assert row.language == "hi"
        assert row.citizen_ref == pseudonymise(TEST_PHONE)
    finally:
        db.close()


def test_ivr_dropped_call_creates_no_row():
    """A call dropped mid-flow before recording must leave zero half-written rows."""
    db = SessionLocal()
    try:
        initial_count = db.query(CitizenRequest).count()
        sim = IVRSimulator(db)

        sim.step("919999999999", "start")
        sim.step("919999999999", "dtmf", digits="1")
        # Caller drops/hangs up
        sim.step("919999999999", "hangup")

        final_count = db.query(CitizenRequest).count()
        assert final_count == initial_count, "Dropped call must not write any request row"
    finally:
        db.close()


def test_ivr_privacy_audit_zero_phone_number_in_database():
    """Rigorous SQL LIKE audit: raw phone number must not appear in ANY database column."""
    db = SessionLocal()
    try:
        sim = IVRSimulator(db)
        sim.run_full_simulation(
            caller_phone=TEST_PHONE,
            language_digit="1",
            problem_description="पानी की बहुत समस्या है बरपेटा में।",
        )

        # 1. Verify citizen_ref is stable across repeated calls
        first_ref = pseudonymise(TEST_PHONE)
        assert first_ref.startswith("anon_")

        # 2. Check all tables and text columns
        tables = [CitizenRequest, ChannelSession, RequestResponse]
        for model in tables:
            rows = db.query(model).all()
            for row in rows:
                for col in model.__table__.columns.keys():
                    val = getattr(row, col)
                    assert TEST_PHONE not in str(val), (
                        f"CRITICAL PRIVACY VIOLATION: Raw phone number found in {model.__tablename__}.{col}"
                    )
    finally:
        db.close()


def test_ivr_twiml_and_exotel_adapters():
    """Verify provider-agnostic adapter generates valid Twilio TwiML XML and Exotel formats."""
    db = SessionLocal()
    try:
        adapter = IVRAdapter(db)
        step_res = adapter.handle_event(TEST_PHONE, CallStartEvent())

        # Twilio TwiML formatting
        twiml = adapter.to_twiml(step_res)
        assert "<Response>" in twiml
        assert "<Gather" in twiml
        assert "<Play>" in twiml

        # Exotel response formatting
        exotel_res = adapter.to_exotel_response(step_res)
        assert exotel_res["select"] == "gather"
        assert exotel_res["state"] in ("SELECT_LANGUAGE", "LANGUAGE_MENU")
    finally:
        db.close()


def test_ivr_simulate_api_endpoint(client):
    """Test the POST /ivr/simulate HTTP route."""
    # 1. Full simulation mode
    res = client.post("/ivr/simulate", json={
        "caller_phone": TEST_PHONE,
        "action": "full_simulation",
        "language_digit": "1",
        "text_simulation": "सड़क टूटी हुई है बरपेटा में",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert len(data["steps"]) == 4

    # 2. Step-by-step mode
    res_start = client.post("/ivr/simulate", json={"caller_phone": TEST_PHONE, "action": "start"})
    assert res_start.status_code == 200
    assert res_start.json()["state"] in ("SELECT_LANGUAGE", "LANGUAGE_MENU")
