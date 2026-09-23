"""Unit and integration tests for the Exotel inbound and outbound SMS adapter.

The location clarification used to cost one Gemini call per inbound message —
`extract_request` was run purely to ask "does this text name a place?" — which on a
free tier capped at twenty calls a day per model is the entire day's budget spent
before a single complaint is filed. The check now runs through
`channels.router`, deterministically, against the same reference table the
pipeline resolves against. These tests hold that line: `app.services.pipeline`
is still mocked, because the *extraction* is a model call, but nothing in this
module calls a model any more.
"""
import pytest

from app.channels.exotel_sms import format_dlt_sms, process_exotel_inbound_sms
from app.db.database import SessionLocal, init_db
from app.db.models import CitizenRequest, District
from app.models.schemas import ExtractedRequest, LocationHierarchy
from app.services.privacy import pseudonymise


@pytest.fixture(scope="module", autouse=True)
def reference_data():
    """A resolvable district, or the gate cannot tell a located message from a bare one.

    Thane rather than Pune, and with the code and name `tests/test_geocode.py` uses:
    the suite shares one database across modules, and that file asserts Pune is *not*
    covered in order to test the "we recognised the state but not the district" path.
    A row invented here would be visible there and would break it.
    """
    init_db()
    db = SessionLocal()
    try:
        db.merge(District(code="MH_THANE", name="Thane", state="Maharashtra",
                          population=11_060_148, literacy_pct=84.5, internet_pct=55.0,
                          deprivation_index=0.3))
        db.commit()
    finally:
        db.close()
    yield


def test_dlt_template_formatting():
    """DLT template formatting injects variables in exact positions."""
    msg = format_dlt_sms("REGISTRATION_SUCCESS", reference="#101", district="Pune")
    assert "Your JanSetu request #101 has been registered successfully for Pune." in msg
    assert "- JanSetu" in msg

    clarify = format_dlt_sms("LOCATION_CLARIFICATION")
    assert "Reply: LOC <village/town>, <district>." in clarify


@pytest.mark.anyio
async def test_exotel_sms_direct_intake_with_location(db_session, monkeypatch):
    """SMS with self-contained location is ingested immediately and confirmation sent."""
    sender = "919876543210"
    sms_sid = "sms_test_direct_001"
    body = "पानी नहीं आ रहा है। Village Mokhada, District Thane."

    mock_ext = ExtractedRequest(
        category="WATER_SUPPLY",
        summary_en="Water supply problem in Thane",
        summary_native="पानी नहीं आ रहा है।",
        urgency=4,
        confidence=0.9,
        location_text="Thane, Maharashtra",
        location=LocationHierarchy(district_or_city="Thane", state="Maharashtra"),
    )
    monkeypatch.setattr("app.services.pipeline.extract_request", lambda *a, **k: mock_ext)

    res = await process_exotel_inbound_sms(db_session, sender, sms_sid, body)
    assert res["status"] == "success"
    assert res["request_id"] > 0

    req = db_session.get(CitizenRequest, res["request_id"])
    assert req is not None
    assert req.channel == "sms"
    assert req.citizen_ref == pseudonymise(sender)


@pytest.mark.anyio
async def test_exotel_sms_missing_location_clarification_flow(db_session, monkeypatch):
    """SMS without location initiates clarification session; reply LOC ... completes it."""
    sender = "919999888777"

    # Step 1: Inbound message without location
    sms1_sid = "sms_no_loc_001"
    body1 = "हमारे यहाँ बिजली के तार टूट गए हैं।"

    mock_with_loc = ExtractedRequest(
        category="ELECTRICITY",
        summary_en="Broken electricity wires in Thane",
        summary_native="हमारे यहाँ बिजली के तार टूट गए हैं।",
        urgency=4,
        confidence=0.9,
        location_text="Thane, Maharashtra",
        location=LocationHierarchy(district_or_city="Thane", state="Maharashtra"),
    )
    monkeypatch.setattr("app.services.pipeline.extract_request", lambda *a, **k: mock_with_loc)

    res1 = await process_exotel_inbound_sms(db_session, sender, sms1_sid, body1)
    assert res1["status"] == "pending_clarification"

    # Verify no complaint created yet
    assert db_session.query(CitizenRequest).filter_by(citizen_ref=pseudonymise(sender)).count() == 0

    # Step 2: Citizen replies with LOC Thane
    sms2_sid = "sms_loc_reply_002"
    res2 = await process_exotel_inbound_sms(db_session, sender, sms2_sid, "LOC Thane, Maharashtra")
    assert res2["status"] == "success"
    assert res2["request_id"] > 0

    # Complaint is now created exactly once
    req = db_session.get(CitizenRequest, res2["request_id"])
    assert req is not None
    assert req.category == "ELECTRICITY"


@pytest.mark.anyio
async def test_exotel_sms_bare_place_reply_also_completes_the_flow(db_session, monkeypatch):
    """The DLT template teaches "LOC <place>", but nobody should have to obey it.

    A citizen answering "where are you?" with "Thane, Maharashtra" and nothing else
    is the common case; requiring a keyword would lose the complaint that was
    already typed out in full one message earlier.
    """
    sender = "919777666555"
    monkeypatch.setattr(
        "app.services.pipeline.extract_request",
        lambda *a, **k: ExtractedRequest(
            category="ROADS", summary_en="Broken road", summary_native="सड़क टूटी है",
            urgency=3, confidence=0.9, location_text="Thane, Maharashtra",
            location=LocationHierarchy(district_or_city="Thane", state="Maharashtra"),
        ),
    )

    first = await process_exotel_inbound_sms(db_session, sender, "sms_bare_01",
                                            "सड़क पिछले छह महीने से टूटी पड़ी है")
    assert first["status"] == "pending_clarification"

    second = await process_exotel_inbound_sms(db_session, sender, "sms_bare_02", "Thane, Maharashtra")
    assert second["status"] == "success"

    req = db_session.get(CitizenRequest, second["request_id"])
    # `raw_text` is what the citizen actually sent, before extraction. The stashed
    # issue must be in there — filing only the bare place name would lose the need.
    assert "सड़क" in req.raw_text
    assert "Thane" in req.raw_text


@pytest.mark.anyio
async def test_exotel_sms_greeting_returns_the_language_menu(db_session):
    """"Hi" used to open a docket describing nothing. Now it opens the menu."""
    sender = "919111222333"
    res = await process_exotel_inbound_sms(db_session, sender, "sms_greet_01", "Hi")
    assert res["status"] == "conversation"
    assert "1." in res["message"]
    assert db_session.query(CitizenRequest).filter_by(citizen_ref=pseudonymise(sender)).count() == 0


@pytest.mark.anyio
async def test_exotel_sms_language_digit_is_answered_in_that_language(db_session):
    sender = "919111222444"
    await process_exotel_inbound_sms(db_session, sender, "sms_lang_01", "Hi")
    # LANG TA command switches session language to Tamil
    res = await process_exotel_inbound_sms(db_session, sender, "sms_lang_02", "LANG TA")
    assert res["status"] == "conversation"
    assert "ஜன்சேது" in res["message"]


@pytest.mark.anyio
async def test_exotel_sms_confirmation_is_in_the_chosen_language(db_session, monkeypatch):
    """A citizen answered in English cannot tell whether the token is theirs."""
    from app.channels import exotel_sms

    sent: list[str] = []

    async def _capture(to, body, **kwargs):
        sent.append(body)
        return True

    monkeypatch.setattr(exotel_sms, "send_exotel_sms", _capture)
    monkeypatch.setattr(
        "app.services.pipeline.extract_request",
        lambda *a, **k: ExtractedRequest(
            category="WATER_SUPPLY", summary_en="No water", summary_native="पानी नहीं",
            urgency=4, confidence=0.9, location_text="Thane, Maharashtra",
            location=LocationHierarchy(district_or_city="Thane", state="Maharashtra"),
        ),
    )

    sender = "919555444333"
    await process_exotel_inbound_sms(db_session, sender, "sms_conf_01", "Hi")
    await process_exotel_inbound_sms(db_session, sender, "sms_conf_02", "1")  # Hindi
    res = await process_exotel_inbound_sms(db_session, sender, "sms_conf_03",
                                          "पानी नहीं आ रहा, Thane, Maharashtra")
    assert res["status"] == "success"
    confirmation = sent[-1]
    assert "जनसेतु" in confirmation
    # The token itself stays Latin — it is what gets typed back into /track.
    assert "JS-" in confirmation


@pytest.mark.anyio
async def test_exotel_sms_help_and_status_lookup(db_session):
    """HELP and STATUS commands return appropriate responses without creating complaints."""
    sender = "919876543210"

    # HELP command
    res_help = await process_exotel_inbound_sms(db_session, sender, "sms_help_01", "HELP")
    assert res_help["status"] == "success"
    assert res_help["action"] == "help"

    # STATUS command
    res_status = await process_exotel_inbound_sms(db_session, sender, "sms_status_01", "STATUS #999")
    assert res_status["status"] == "success"
    assert res_status["action"] == "status_query"
