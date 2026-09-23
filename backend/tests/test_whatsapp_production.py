"""Integration tests for WhatsApp Cloud API signature verification and voice+photo session."""
import base64
import hashlib
import hmac
import pytest

from app.channels.whatsapp import validate_whatsapp_signature
from app.db.database import SessionLocal
from app.db.models import CitizenRequest
from app.models.schemas import ExtractedRequest, LocationHierarchy
from app.services.privacy import pseudonymise


def test_whatsapp_signature_validation():
    """X-Hub-Signature-256 validation verifies payload hash with app secret."""
    secret = "test_meta_app_secret_12345"
    payload = b'{"object": "whatsapp_business_account"}'

    sig = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    assert validate_whatsapp_signature(payload, sig, secret) is True

    # Bad signature
    bad_sig = "sha256=0000000000000000000000000000000000000000000000000000000000000000"
    assert validate_whatsapp_signature(payload, bad_sig, secret) is False


def test_whatsapp_voice_then_subsequent_photo_evidence(client, monkeypatch):
    """Voice note creates complaint; subsequent photo within session attaches image_verification."""
    sender = "919888777666"

    monkeypatch.setattr("app.services.pipeline.transcribe", lambda *a, **k: "सड़क पर गहरा गड्ढा है।")
    monkeypatch.setattr(
        "app.services.pipeline.extract_request",
        lambda *a, **k: ExtractedRequest(
            category="ROADS",
            summary_en="Deep pothole on road in Pune",
            summary_native="सड़क पर गहरा गड्ढा है।",
            urgency=4,
            confidence=0.9,
            location_text="Pune, Maharashtra",
            location=LocationHierarchy(district_or_city="Pune", state="Maharashtra"),
        ),
    )

    # Step 1: Send Voice Note
    dummy_audio_b64 = base64.b64encode(b"RIFF" + b"\x00" * 200).decode("utf-8")
    voice_payload = {
        "mock_media_base64": dummy_audio_b64,
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": sender,
                        "id": "wamid_voice_step_1",
                        "type": "audio",
                        "audio": {"id": "media_audio_111", "mime_type": "audio/ogg"},
                    }],
                },
            }],
        }],
    }

    res1 = client.post("/intake/whatsapp", json=voice_payload)
    assert res1.status_code == 200
    assert res1.json()["status"] == "received"

    db = SessionLocal()
    try:
        row = (
            db.query(CitizenRequest)
            .filter_by(citizen_ref=pseudonymise(sender))
            .order_by(CitizenRequest.id.desc())
            .first()
        )
        assert row is not None, "Voice note must create a complaint docket"
        req_id = row.id
        assert row.category == "ROADS"
        count_after_voice = (
            db.query(CitizenRequest).filter_by(citizen_ref=pseudonymise(sender)).count()
        )
    finally:
        db.close()

    # Step 2: Send Image as follow-up evidence
    monkeypatch.setattr(
        "app.channels.whatsapp.extract_request",
        lambda *a, **k: ExtractedRequest(
            category="ROADS",
            summary_en="Road photo",
            summary_native="फोटो",
            urgency=4,
            confidence=0.9,
            image_verification="Photograph shows a 2-foot deep pothole with exposed gravel on asphalt road.",
        ),
    )

    dummy_img_b64 = base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 100).decode("utf-8")
    img_payload = {
        "mock_media_base64": dummy_img_b64,
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": sender,
                        "id": "wamid_photo_step_2",
                        "type": "image",
                        "image": {"id": "media_img_222", "mime_type": "image/jpeg"},
                    }],
                },
            }],
        }],
    }

    res2 = client.post("/intake/whatsapp", json=img_payload)
    assert res2.status_code == 200
    assert res2.json()["status"] == "received"

    # Must attach to the existing docket and not create a duplicate request
    db = SessionLocal()
    try:
        count_after_photo = (
            db.query(CitizenRequest).filter_by(citizen_ref=pseudonymise(sender)).count()
        )
        assert count_after_photo == count_after_voice, "Follow-up photo must not create a new docket"

        row = db.get(CitizenRequest, req_id)
        assert row is not None
        assert row.has_photo is True
        assert row.image_verification, "Photo evidence analysis must be attached to the docket"
    finally:
        db.close()


def test_whatsapp_webhook_signature_header_rejection(client, monkeypatch):
    """When WHATSAPP_APP_SECRET is set, invalid signature returns HTTP 403."""
    from app.config import Settings
    monkeypatch.setattr("app.routers.intake.get_settings", lambda: Settings(whatsapp_app_secret="prod_secret_key"))

    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "919876543210",
                        "id": "wamid_sig_test_01",
                        "type": "text",
                        "text": {"body": "नमस्ते"},
                    }],
                },
            }],
        }],
    }

    headers = {"X-Hub-Signature-256": "sha256=invalid_signature_hash"}
    res = client.post("/intake/whatsapp", json=payload, headers=headers)
    assert res.status_code == 403
