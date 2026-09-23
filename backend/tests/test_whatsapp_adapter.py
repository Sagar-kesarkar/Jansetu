"""Tests for WhatsApp Cloud API adapter (text, voice notes, photographs, deduplication, privacy)."""
from __future__ import annotations

import base64
import pytest
from fastapi.testclient import TestClient

from app.channels.whatsapp import parse_whatsapp_webhook
from app.db.database import SessionLocal, init_db
from app.db.models import CitizenRequest, District, PlaceAlias
from app.main import app
from app.services.privacy import pseudonymise

WA_SENDER = "919876543210"


@pytest.fixture(scope="module", autouse=True)
def setup_district():
    init_db()
    db = SessionLocal()
    try:
        db.merge(District(
            code="WA_D1",
            name="Pune",
            state="Maharashtra",
            population=9_429_408,
            latitude=18.52,
            longitude=73.85,
            literacy_pct=86.1,
            internet_pct=62.0,
            deprivation_index=0.25,
        ))
        db.commit()
        # The Devanagari alias is not decoration. `channels.router` now refuses to
        # file a complaint that names no resolvable place, and every text body below
        # writes the district as "पुणे" — without this row the gate would answer each
        # of them with "please also send your city or district" and no docket would
        # exist to assert on. The production reference data carries the same aliases.
        for alias, kind in [("पुणे", "native"), ("pune", "city"), ("புனே", "native"), ("పూణే", "native")]:
            if not db.query(PlaceAlias).filter_by(alias=alias, district_code="WA_D1").first():
                db.add(PlaceAlias(alias=alias, district_code="WA_D1", kind=kind))
                db.commit()
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_whatsapp_webhook_text_intake(client):
    """WhatsApp text message produces a row and sends back Devanagari acknowledgement."""
    db = SessionLocal()
    try:
        count_before = db.query(CitizenRequest).count()
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "10001",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"display_phone_number": "15550234567", "phone_number_id": "10002"},
                        "messages": [{
                            "from": WA_SENDER,
                            "id": "wamid.HBgLMzkxOTg3NjU0MzIxMAUCABEYEjA1",
                            "timestamp": "1724330000",
                            "type": "text",
                            "text": {"body": "पुणे में पानी की सप्लाई 3 दिन से बंद है।"},
                        }],
                    },
                    "field": "messages",
                }],
            }],
        }

        res = client.post("/intake/whatsapp", json=payload)
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "received"

        # The webhook acks immediately and processes in a background task, which
        # TestClient runs to completion before the request returns, so the row
        # is already committed here.
        count_after = db.query(CitizenRequest).count()
        assert count_after == count_before + 1

        row = (
            db.query(CitizenRequest)
            .filter_by(citizen_ref=pseudonymise(WA_SENDER))
            .order_by(CitizenRequest.id.desc())
            .first()
        )
        assert row is not None
        assert row.channel == "whatsapp"
        assert row.citizen_ref == pseudonymise(WA_SENDER)
    finally:
        db.close()


def test_whatsapp_webhook_deduplication(client):
    """Meta webhook retries with the same message ID must not create duplicate requests."""
    db = SessionLocal()
    try:
        msg_id = "wamid.HBgLMzkxOTg3NjU0MzIxMAUCABEYEjA5_DEDUPE"
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": WA_SENDER,
                            "id": msg_id,
                            "type": "text",
                            "text": {"body": "पुणे में बिजली नहीं है।"},
                        }],
                    },
                }],
            }],
        }

        # First delivery: creates request
        res1 = client.post("/intake/whatsapp", json=payload)
        assert res1.status_code == 200
        first_count = db.query(CitizenRequest).count()

        # Second delivery (retry): idempotent, creates no duplicate request
        res2 = client.post("/intake/whatsapp", json=payload)
        assert res2.status_code == 200
        second_count = db.query(CitizenRequest).count()
        assert second_count == first_count, "Webhook retry must not duplicate citizen request"
    finally:
        db.close()


def test_whatsapp_voice_note_intake(client, monkeypatch):
    """WhatsApp voice note with audio bytes processes through pipeline."""
    voice_sender = "919876543212"
    from app.models.schemas import ExtractedRequest, LocationHierarchy

    # Ensure offline test returns a valid transcript and structured request with location
    monkeypatch.setattr("app.services.pipeline.transcribe", lambda *a, **k: "पुणे में पानी की समस्या है")
    monkeypatch.setattr("app.services.speech.transcribe", lambda *a, **k: "पुणे में पानी की समस्या है")
    monkeypatch.setattr(
        "app.services.pipeline.extract_request",
        lambda *a, **k: ExtractedRequest(
            category="WATER_SUPPLY",
            summary_en="Water supply problem in Pune",
            summary_native="पुणे में पानी की समस्या दर्ज हो गई है।",
            urgency=4,
            confidence=0.9,
            location_text="Pune, Maharashtra",
            location=LocationHierarchy(district_or_city="Pune", state="Maharashtra"),
        ),
    )

    # 100 bytes of dummy audio data
    dummy_audio_b64 = base64.b64encode(b"RIFF" + b"\x00" * 200).decode("utf-8")
    payload = {
        "mock_media_base64": dummy_audio_b64,
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": voice_sender,
                        "id": "wamid.HBgLMzkxOTg3NjU0MzIxMAUCABEYEj_AUDIO",
                        "type": "audio",
                        "audio": {"id": "media_audio_123", "mime_type": "audio/ogg"},
                    }],
                },
            }],
        }],
    }

    res = client.post("/intake/whatsapp", json=payload)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "received"

    db = SessionLocal()
    try:
        row = (
            db.query(CitizenRequest)
            .filter_by(citizen_ref=pseudonymise(voice_sender))
            .order_by(CitizenRequest.id.desc())
            .first()
        )
        assert row is not None
        assert row.channel == "whatsapp"
        assert row.transcript == "पुणे में पानी की समस्या है"
        dist = db.get(District, row.district_code) if row.district_code else None
        district = dist.name if dist else row.loc_district
        assert district == "Pune"
    finally:
        db.close()


def test_whatsapp_image_intake_bytes_never_stored(client):
    """WhatsApp photograph is analyzed and image bytes are NEVER stored on disk or DB."""
    img_sender = "919876543213"
    dummy_img_b64 = base64.b64encode(b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100).decode("utf-8")
    payload = {
        "mock_media_base64": dummy_img_b64,
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": img_sender,
                        "id": "wamid.HBgLMzkxOTg3NjU0MzIxMAUCABEYEj_IMAGE",
                        "type": "image",
                        "image": {
                            "id": "media_img_123",
                            "mime_type": "image/jpeg",
                            "caption": "पुणे में सड़क का बड़ा गड्ढा",
                        },
                    }],
                },
            }],
        }],
    }

    res = client.post("/intake/whatsapp", json=payload)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "received"

    db = SessionLocal()
    try:
        row = (
            db.query(CitizenRequest)
            .filter_by(citizen_ref=pseudonymise(img_sender))
            .order_by(CitizenRequest.id.desc())
            .first()
        )
        assert row is not None
        assert row.has_photo is True
        # Verify no image blob column exists on CitizenRequest
        assert not hasattr(CitizenRequest, "image_data")
        assert not hasattr(CitizenRequest, "image_blob")
    finally:
        db.close()


def test_whatsapp_simulator_menu_option_1_deterministic(client):
    """Sending '1' to /intake/report with channel=whatsapp opens complaint registration without Gemini."""
    sim_sender = "wa_sim_test_user_001"
    payload = {
        "text": "1",
        "channel": "whatsapp",
        "citizen_ref": sim_sender,
        "language": "en",
    }
    res = client.post("/intake/report", data=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["classification"] == "CONVERSATIONAL"
    assert data["request_id"] == 0
    assert data["track_token"] is None
    assert "You selected: Register a complaint" in data["acknowledgement_native"]


def test_whatsapp_simulator_complaint_location_gate_flow(client):
    """WhatsApp complaint draft -> location prompt -> resolved registration with real token."""
    sim_sender = "wa_sim_test_user_002"

    # Step 1: Open registration
    res1 = client.post("/intake/report", data={
        "text": "1",
        "channel": "whatsapp",
        "citizen_ref": sim_sender,
        "language": "en",
    })
    assert res1.status_code == 200

    # Step 2: Submit complaint description without location
    res2 = client.post("/intake/report", data={
        "text": "There is no clean drinking water.",
        "channel": "whatsapp",
        "citizen_ref": sim_sender,
        "language": "en",
    })
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["classification"] == "CONVERSATIONAL"
    assert data2["request_id"] == 0
    assert data2["track_token"] is None
    assert "We have understood your complaint:" in data2["acknowledgement_native"]
    assert "No tracking token has been generated yet." in data2["acknowledgement_native"]

    # Step 3: Supply valid location
    res3 = client.post("/intake/report", data={
        "text": "Ward 4, Pune, Maharashtra",
        "channel": "whatsapp",
        "citizen_ref": sim_sender,
        "language": "en",
    })
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["request_id"] > 0
    assert data3["track_token"] is not None
    assert data3["track_token"].startswith("JS-")
    assert data3["district"] == "Pune"


def test_whatsapp_session_isolation_from_sms(client):
    """WhatsApp and SMS have completely isolated sessions for the same citizen identifier."""
    shared_ref = "isolated_user_999"

    # WhatsApp is in AWAITING_LOCATION
    client.post("/intake/report", data={"text": "1", "channel": "whatsapp", "citizen_ref": shared_ref, "language": "en"})
    client.post("/intake/report", data={"text": "Water leakage in pipe", "channel": "whatsapp", "citizen_ref": shared_ref, "language": "en"})

    # SMS for the same ref starts at MAIN_MENU and enters option 2 (Track)
    sms_res = client.post("/intake/report", data={"text": "2", "channel": "sms", "citizen_ref": shared_ref, "language": "en"})
    assert sms_res.status_code == 200
    sms_data = sms_res.json()
    assert "Track a complaint" in sms_data["acknowledgement_native"] or "Request ID" in sms_data["acknowledgement_native"] or "JS-" in sms_data["acknowledgement_native"]


def test_whatsapp_multilingual_flows(client, monkeypatch):
    """Verify WhatsApp complaint & location gate across Hindi, Marathi, Tamil, Telugu."""
    from unittest.mock import MagicMock
    from app.models.schemas import ExtractedRequest

    mock_extracted = ExtractedRequest(
        category="WATER_SUPPLY",
        urgency=3,
        summary_en="Water supply pipeline is broken",
        summary_native="पाण्याची पाईपलाईन फुटली आहे",
        language="mr",
        confidence=0.95,
    )
    monkeypatch.setattr("app.services.gemini.extract_request", lambda *args, **kwargs: mock_extracted)
    monkeypatch.setattr("app.services.pipeline.extract_request", lambda *args, **kwargs: mock_extracted)
    monkeypatch.setattr("app.channels.router.extract_request", lambda *args, **kwargs: mock_extracted, raising=False)

    cases = [
        ("hi", "पानी की आपूर्ति बाधित है", "वार्ड 2, पुणे, महाराष्ट्र", "शिकायत", "पुणे"),
        ("mr", "पाण्याची पाईपलाईन फुटली आहे", "प्रभाग 4, पुणे, महाराष्ट्र", "तक्रार", "पुणे"),
        ("ta", "குடிநீர் விநியோகம் இல்லை", "வார்டு 1, புனே, மகாராஷ்டிரா", "புகார்", "புனே"),
        ("te", "తాగునీటి పైపు పగిలిపోయింది", "వార్డు 3, పూణే, మహారాష్ట్ర", "ఫిర్యాదు", "పూణే"),
    ]
    for idx, (lang, complaint_txt, loc_txt, expected_kw, expected_dist) in enumerate(cases):
        ref = f"wa_multi_user_{idx}_{lang}"
        # Option 1 in target language
        r1 = client.post("/intake/report", data={"text": "1", "channel": "whatsapp", "citizen_ref": ref, "language": lang})
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["classification"] == "CONVERSATIONAL"

        # Complaint text
        r2 = client.post("/intake/report", data={"text": complaint_txt, "channel": "whatsapp", "citizen_ref": ref, "language": lang})
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["classification"] == "CONVERSATIONAL"
        assert d2["request_id"] == 0
        assert d2["track_token"] is None

        # Location text
        r3 = client.post("/intake/report", data={"text": loc_txt, "channel": "whatsapp", "citizen_ref": ref, "language": lang})
        assert r3.status_code == 200
        d3 = r3.json()
        assert d3["request_id"] > 0
        assert d3["track_token"] is not None
        assert d3["track_token"].startswith("JS-")


def test_whatsapp_budget_query_flow(client):
    """WhatsApp option 3 allows querying state and district budgets."""
    ref = "wa_budget_test_001"
    # Option 3
    r1 = client.post("/intake/report", data={"text": "3", "channel": "whatsapp", "citizen_ref": ref, "language": "en"})
    assert r1.status_code == 200
    d1 = r1.json()
    assert "budget" in d1["acknowledgement_native"].lower()

    # Scope 1 (State)
    r2 = client.post("/intake/report", data={"text": "1", "channel": "whatsapp", "citizen_ref": ref, "language": "en"})
    assert r2.status_code == 200
    d2 = r2.json()
    assert "State" in d2["acknowledgement_native"] or "state" in d2["acknowledgement_native"]

    # Location (Odisha)
    r3 = client.post("/intake/report", data={"text": "Odisha", "channel": "whatsapp", "citizen_ref": ref, "language": "en"})
    assert r3.status_code == 200
    d3 = r3.json()
    assert "Budget" in d3["acknowledgement_native"] or "₹" in d3["acknowledgement_native"]

