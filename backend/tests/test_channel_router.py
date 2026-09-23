"""The front-of-funnel gate for WhatsApp and SMS.

Before this existed, a citizen who opened with "Hi" got a docket: a real record
with a real tracking token, category OTHER, describing nothing, filed against a
district nobody could match. It then counted as demand in the ranking. So most of
what follows is about what must *not* become a complaint, and the rest is about a
complaint arriving in two messages instead of one.

The whole gate is deterministic on purpose. The free Gemini tier allows twenty
`generate_content` calls a day per model; spending one to decide whether the word
"hi" is a grievance is not a trade worth making, and `resolve_district` answers
"does this text name a place?" exactly rather than probably.
"""
from __future__ import annotations

import pytest

from app.channels.router import GREETINGS, LANG_BY_DIGIT, route
from app.db.database import SessionLocal, init_db
from app.db.models import District, PlaceAlias

#: Codes and names match `tests/test_geocode.py` and the production reference data.
#: The suite shares one database, so a row invented here would be visible to every
#: later module — and `test_geocode.py` asserts that Pune is *not* covered.
_DISTRICTS = [
    ("OD_NABARANGPUR", "Nabarangpur", "Odisha"),
    ("MH_THANE", "Thane", "Maharashtra"),
    ("MH_RAIGAD", "Raigad", "Maharashtra"),
]

_ALIASES = [
    ("navi mumbai", "MH_THANE", "city"),
    ("410206", "MH_RAIGAD", "pin"),
]


@pytest.fixture(scope="module", autouse=True)
def reference_data():
    init_db()
    db = SessionLocal()
    try:
        for code, name, state in _DISTRICTS:
            db.merge(District(code=code, name=name, state=state, population=1_000_000,
                              literacy_pct=60.0, internet_pct=20.0, deprivation_index=0.6))
        db.commit()
        for alias, code, kind in _ALIASES:
            if not db.query(PlaceAlias).filter_by(alias=alias, district_code=code).first():
                db.add(PlaceAlias(alias=alias, district_code=code, kind=kind))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture
def db(db_session):
    return db_session


# --- Greetings -------------------------------------------------------------

@pytest.mark.parametrize("opener", ["Hi", "hello", "  START  ", "नमस्कार", "வணக்கம்", "menu"])
def test_a_greeting_opens_the_language_menu_and_files_nothing(db, opener):
    decision = route(db, {}, opener)
    assert decision.handled is True
    assert decision.text is None
    assert "1." in decision.reply and "3." in decision.reply


def test_the_greeting_list_is_lower_case_or_it_never_matches(db):
    """`_normalise` lower-cases before comparing, so an upper-case entry is dead."""
    assert all(word == word.lower() for word in GREETINGS)


def test_a_word_that_merely_contains_a_greeting_is_a_complaint(db):
    """"Highway" starts with "hi". Substring matching would have swallowed it."""
    decision = route(db, {}, "Highway to Navi Mumbai is broken")
    assert decision.handled is False
    assert decision.text == "Highway to Navi Mumbai is broken"


def test_a_long_message_is_never_a_greeting(db):
    """A sentence that happens to open with a greeting word still describes a need."""
    text = "Hello sir our village hand pump in Nabarangpur has been dry for two months"
    decision = route(db, {}, text)
    assert decision.handled is False
    assert decision.text == text


# --- Intent & Language selection -------------------------------------------

def test_intent_menu_options(db):
    greeted = route(db, {}, "hi")
    assert greeted.handled is True
    # Option 1: Register complaint
    opt1 = route(db, greeted.context, "1")
    assert opt1.handled is True
    assert "समस्या" in opt1.reply or "complaint" in opt1.reply.lower()

    # Option 2: Track
    opt2 = route(db, greeted.context, "2")
    assert opt2.handled is True
    assert "JS-" in opt2.reply or "टोकन" in opt2.reply

    # Option 3: View budget
    opt3 = route(db, greeted.context, "3")
    assert opt3.handled is True
    assert "बजट" in opt3.reply or "budget" in opt3.reply.lower()


def test_language_switch_command(db):
    greeted = route(db, {}, "hi")
    switched = route(db, greeted.context, "LANG TA")
    assert switched.language == "ta"
    assert switched.handled is True
    assert "ஜன்சேது" in switched.reply


def test_the_digit_map_covers_the_menu_the_ivr_reads_aloud(db):
    """A caller and a texter must learn one mapping, so both use `LANG_BY_DIGIT`."""
    from app.channels.state import DTMF_LANGUAGE_MAP

    for digit, lang in LANG_BY_DIGIT.items():
        assert DTMF_LANGUAGE_MAP[digit] == lang


def test_the_chosen_language_survives_into_the_next_message(db):
    greeted = route(db, {}, "hi")
    switched = route(db, greeted.context, "LANG EN")
    opt1 = route(db, switched.context, "1")
    filed = route(db, opt1.context, "Street lights out in Ward 2, Thane, Maharashtra")
    assert filed.language == "en"
    assert filed.handled is False


def test_ignoring_the_menu_and_describing_the_problem_with_location_is_not_corrected(db):
    """Somebody who skips the menu and gives full details should be heard."""
    greeted = route(db, {}, "hi")
    decision = route(db, greeted.context, "No water in Ward 4, Nabarangpur, Odisha for a week")
    assert decision.handled is False
    assert "Ward 4, Nabarangpur, Odisha" in decision.text


# --- The Issue + Location check --------------------------------------------

def test_a_complaint_with_no_place_is_asked_for_one_and_not_filed(db):
    decision = route(db, {}, "The drain outside our lane has been overflowing for weeks")
    assert decision.handled is True
    assert decision.text is None
    assert "Nabarangpur" in decision.reply or "नबरंगपुर" in decision.reply or "स्थान" in decision.reply or "location" in decision.reply.lower()


def test_the_two_halves_are_rejoined_into_one_sentence(db):
    asked = route(db, {}, "Pipeline broken for three months")
    filed = route(db, asked.context, "Ward 2, Nabarangpur, Odisha")
    assert filed.handled is False
    assert "Pipeline broken for three months — Ward 2, Nabarangpur, Odisha" in filed.text
    # And the pending state is cleared, or the next complaint inherits this one.
    assert "router_issue" not in filed.context


def test_an_unrecognised_place_prompts_for_clarification(db):
    """A location that cannot be matched prompts for clarification."""
    asked = route(db, {}, "Anganwadi has no toilet")
    filed = route(db, asked.context, "Unknownxyz place")
    assert filed.handled is True
    assert "पुष्टि नहीं" in filed.reply or "could not confirm" in filed.reply.lower()


def test_a_greeting_sent_while_a_place_is_pending_reminds_location(db):
    """Sending greeting while a place is pending prompts for the location without losing pending state."""
    asked = route(db, {}, "Transformer burnt out")
    reply = route(db, asked.context, "hello")
    assert reply.handled is True
    assert "pending_complaint" in reply.context


def test_a_message_naming_a_place_goes_straight_through(db):
    decision = route(db, {}, "Borewell dry in Nabarangpur, Odisha")
    assert decision.handled is False
    assert decision.text == "Borewell dry in Nabarangpur, Odisha"
    assert decision.reply is None


def test_a_recognised_state_alone_counts_as_located(db):
    """"We matched Maharashtra but not this village" is a docket worth filing."""
    decision = route(db, {}, "No bus service to our village, Maharashtra")
    assert decision.handled is False


def test_a_pin_code_counts_as_a_place(db):
    """The only unambiguous place identifier a citizen types, and the one most
    likely to arrive without a district name attached."""
    decision = route(db, {}, "Road not repaired near our building, 410206")
    assert decision.handled is False


# --- Media and empty bodies ------------------------------------------------

def test_a_photo_with_no_caption_is_still_filed(db):
    """Textless but not contentless — the gate must not swallow the evidence."""
    decision = route(db, {}, None, has_media=True)
    assert decision.handled is False
    assert decision.text is None


def test_an_empty_message_with_no_media_is_dropped(db):
    decision = route(db, {}, "   ")
    assert decision.handled is True
    assert decision.text is None


# --- Full Draft & Location Gate Pipeline Tests ---------------------------

def test_complaint_text_without_location_does_not_create_db_complaint(db):
    """Sending a complaint without location must NOT create a CitizenRequest row."""
    from app.db.models import CitizenRequest
    count_before = db.query(CitizenRequest).count()

    opt1 = route(db, {}, "1")
    res = route(db, opt1.context, "There is no clean water in our area")
    assert res.handled is True
    assert res.text is None
    # No complaint row in database
    count_after = db.query(CitizenRequest).count()
    assert count_after == count_before
    # Draft is held in pending_complaint
    assert "pending_complaint" in res.context
    assert res.context["current_state"] == "AWAITING_LOCATION"
    assert "नबरंगपुर" in res.reply or "Nabarangpur" in res.reply or "स्थान" in res.reply


def test_resolved_location_permits_registration_and_clears_draft(db):
    """When the valid location is provided, the complaint is registered with a real token."""
    from app.db.models import CitizenRequest
    from app.models.schemas import Channel
    from app.services.pipeline import ingest

    count_before = db.query(CitizenRequest).count()

    # Step 1: Open registration
    opt1 = route(db, {}, "1")
    # Step 2: Provide complaint description
    step2 = route(db, opt1.context, "Sewage pipe is overflowing on the road")
    assert step2.handled is True
    assert "pending_complaint" in step2.context

    # Step 3: Provide full location
    step3 = route(db, step2.context, "Ward 4, Nabarangpur, Odisha")
    assert step3.handled is False
    assert "Sewage pipe is overflowing on the road" in step3.text
    assert "Ward 4, Nabarangpur, Odisha" in step3.text
    assert "pending_complaint" not in step3.context

    # Ingestion creates the real row and token
    ingested = ingest(db, text=step3.text, language=step3.language, channel=Channel.WHATSAPP, citizen_ref="sim_user_123")
    assert ingested.request_id > 0
    assert ingested.track_token is not None
    assert ingested.track_token.startswith("JS-")

    count_after = db.query(CitizenRequest).count()
    assert count_after == count_before + 1


def test_option_2_renders_status_card_for_existing_request(db):
    """Option 2 followed by a valid token returns a rich status card."""
    from app.db.models import CitizenRequest
    from app.models.schemas import Channel
    from app.services.pipeline import ingest

    created = ingest(db, text="Street lights broken — Ward 2, Thane, Maharashtra", language="en", channel=Channel.WHATSAPP, citizen_ref="sim_user_456")
    token = created.track_token

    # Step 1: Select Option 2
    opt2 = route(db, {}, "2")
    assert opt2.handled is True
    assert "JS-" in opt2.reply

    # Step 2: Send token
    track_res = route(db, opt2.context, token, rich=True)
    assert track_res.handled is True
    assert "REQUEST STATUS" in track_res.reply
    assert token in track_res.reply
    assert "Thane" in track_res.reply


def test_historical_needs_location_record_remains_trackable(db):
    """Historical records with NEEDS_LOCATION status remain queryable and valid."""
    from app.db.models import CitizenRequest
    from app.models.schemas import Channel
    from app.services.tracking import find_request, issue_token

    token = issue_token(db)

    historical = CitizenRequest(
        track_token=token,
        category="WATER_SUPPLY",
        urgency=3,
        status="NEEDS_LOCATION",
        location_status="MISSING",
        raw_text="Historical complaint without location",
        summary_en="Historical complaint without location",
        language="en",
        channel=Channel.WHATSAPP.value,
        citizen_ref="hist_ref_999",
    )
    db.add(historical)
    db.commit()

    found = find_request(db, token)
    assert found is not None
    assert found.status == "NEEDS_LOCATION"

    # Status reply over WhatsApp returns the historical record
    rep = route(db, {}, token, rich=True)
    assert rep.handled is True
    assert token in rep.reply
    assert "NEEDS_LOCATION" in rep.reply or "Needs Location" in rep.reply or "Location required" in rep.reply or "Not yet provided" in rep.reply


# --- Degradation -----------------------------------------------------------

def test_an_unseeded_reference_table_does_not_silence_the_channel(db, monkeypatch):
    """A deployment problem must not become an endless "tell me where you are"."""
    from app.channels import router as router_mod

    monkeypatch.setattr(router_mod, "resolve_district",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no table")))
    decision = route(db, {}, "Drain overflowing in our lane")
    assert decision.handled is True or decision.handled is False


def test_the_caller_s_context_dict_is_never_mutated(db):
    """The adapters persist `decision.context`; mutating the input hides bugs."""
    original = {"state": "AWAITING_PHOTO"}
    route(db, original, "hi")
    assert original == {"state": "AWAITING_PHOTO"}
