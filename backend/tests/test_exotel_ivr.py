"""Unit and integration tests for Exotel IVR flow and audio processing."""
import pytest

from app.channels.exotel_ivr import (
    build_exotel_dtmf_response,
    build_exotel_recording_response,
    get_language_menu_manifest,
    get_language_pages,
    process_exotel_recording_async,
)
from app.db.database import SessionLocal
from app.db.models import CitizenRequest
from app.services.privacy import pseudonymise


def test_exotel_language_pagination_manifest():
    """DTMF language menu pages languages dynamically from app.i18n.languages."""
    pages = get_language_pages()
    assert len(pages) >= 2  # 13 languages split across pages

    # Page 0 manifest
    p0 = get_language_menu_manifest(0)
    assert p0["page"] == 0
    assert "1" in p0["digit_map"]
    assert p0["next_key"] == "9"

    # Page 1 manifest
    p1 = get_language_menu_manifest(1)
    assert p1["page"] == 1
    assert p1["prev_key"] == "0"


def test_exotel_dtmf_response_routing():
    """DTMF key selections route correctly to recording or next pages."""
    # Blank digits -> Initial menu prompt
    r0 = build_exotel_dtmf_response(digits=None, page=0)
    assert r0["action"] == "gather"
    assert "GREETING_LANG_MENU" in r0["prompt"]

    # Press '1' (Hindi) -> Record need
    r1 = build_exotel_dtmf_response(digits="1", page=0)
    assert r1["action"] == "record"
    assert r1["selected_language"] == "hi"
    assert "RECORD_NEED_BEEP" in r1["prompt"]

    # Press '9' -> Next page
    r_next = build_exotel_dtmf_response(digits="9", page=0)
    assert r_next["action"] == "gather"
    assert r_next["page"] == 1

    # Invalid digit -> Retry prompt
    r_bad = build_exotel_dtmf_response(digits="88", page=0)
    assert r_bad["action"] == "gather"
    assert "INVALID_OPTION_RETRY" in r_bad["prompt"]


def test_exotel_recording_response():
    """Recording webhook plays fixed confirmation prompt and ends call."""
    res = build_exotel_recording_response(lang="hi")
    assert res["action"] == "play_and_hangup"
    assert "CONFIRMATION_NOTICE" in res["prompt"]
    assert res["hangup"] is True


@pytest.mark.anyio
async def test_exotel_recording_async_ingest(db_session, monkeypatch):
    """Asynchronous audio processing downloads audio, runs ingest, and sends SMS."""
    caller = "919876543210"
    call_sid = "exotel_call_test_1001"

    # Mock audio bytes (RIFF header + dummy PCM)
    dummy_wav = b"RIFF" + b"\x00" * 200

    # Mock transcription and extraction
    monkeypatch.setattr("app.services.pipeline.transcribe", lambda *a, **k: "पुणे में पानी की आपूर्ति बंद है।")
    from app.models.schemas import ExtractedRequest, LocationHierarchy
    monkeypatch.setattr(
        "app.services.pipeline.extract_request",
        lambda *a, **k: ExtractedRequest(
            category="WATER_SUPPLY",
            summary_en="Water supply disruption in Pune",
            summary_native="पुणे में पानी की आपूर्ति बंद है।",
            urgency=4,
            confidence=0.9,
            location_text="Pune, Maharashtra",
            location=LocationHierarchy(district_or_city="Pune", state="Maharashtra"),
        ),
    )

    result = await process_exotel_recording_async(
        db=db_session,
        caller_phone=caller,
        call_sid=call_sid,
        recording_url="https://mock.exotel.com/rec_123.wav",
        lang="hi",
        audio_bytes_override=dummy_wav,
    )

    assert result["status"] == "success"
    assert result["request_id"] > 0

    # Verify request in DB
    req = db_session.get(CitizenRequest, result["request_id"])
    assert req is not None
    assert req.channel == "ivr"
    assert req.citizen_ref == pseudonymise(caller)
    assert req.category == "WATER_SUPPLY"


@pytest.mark.anyio
async def test_exotel_dropped_call_creates_no_row(db_session):
    """Empty recording payload produces no row in database."""
    caller = "919999000888"
    call_sid = "exotel_dropped_call_000"

    result = await process_exotel_recording_async(
        db=db_session,
        caller_phone=caller,
        call_sid=call_sid,
        recording_url="https://mock.exotel.com/empty.wav",
        lang="hi",
        audio_bytes_override=b"",
    )

    assert result["status"] == "empty_recording"
    count = db_session.query(CitizenRequest).filter_by(citizen_ref=pseudonymise(caller)).count()
    assert count == 0


def test_exotel_recording_webhook_route_ingests_via_background_task(client, monkeypatch):
    """POST /ivr/exotel/recording acks immediately and ingests in a background task.

    Regression guard for the recording webhook: the background task must open its
    own DB session. The request-scoped `get_db` session is torn down as soon as the
    webhook returns, so a task that reused it would hit a closed session on a real
    call. TestClient runs the background task to completion before returning, so a
    committed row here proves the task had a live session.
    """
    caller = "919876500011"
    call_sid = "exotel_route_call_2002"

    async def _fake_download(url):
        return b"RIFF" + b"\x00" * 200

    monkeypatch.setattr("app.channels.exotel_ivr.download_recording_bytes", _fake_download)
    monkeypatch.setattr("app.services.pipeline.transcribe", lambda *a, **k: "पुणे में सड़क खराब है।")
    from app.models.schemas import ExtractedRequest, LocationHierarchy
    monkeypatch.setattr(
        "app.services.pipeline.extract_request",
        lambda *a, **k: ExtractedRequest(
            category="ROADS",
            summary_en="Damaged road in Pune",
            summary_native="पुणे में सड़क खराब है।",
            urgency=3,
            confidence=0.9,
            location_text="Pune, Maharashtra",
            location=LocationHierarchy(district_or_city="Pune", state="Maharashtra"),
        ),
    )

    res = client.post(
        "/ivr/exotel/recording",
        json={
            "CallSid": call_sid,
            "From": caller,
            "RecordingUrl": "https://mock.exotel.com/route_rec.wav",
            "RecordingDuration": 6,
            "lang": "hi",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["action"] == "play_and_hangup"
    assert body["hangup"] is True

    db = SessionLocal()
    try:
        row = (
            db.query(CitizenRequest)
            .filter_by(citizen_ref=pseudonymise(caller))
            .order_by(CitizenRequest.id.desc())
            .first()
        )
        assert row is not None, "IVR recording webhook must ingest via the background task"
        assert row.channel == "ivr"
        assert row.category == "ROADS"
    finally:
        db.close()
