"""Unit tests for the pure conversation state machine (backend/app/channels/state.py).

Tests are pure and offline: no database, no network, no LLM calls.
"""
from __future__ import annotations

import pytest

from app.channels.state import (
    CAPABILITIES,
    ActionType,
    AudioRecordedEvent,
    CallStartEvent,
    ChannelType,
    ComplaintExtractedEvent,
    ConversationContext,
    ConversationState,
    DtmfEvent,
    HangupEvent,
    ImageReceivedEvent,
    IngestFailureEvent,
    IngestSuccessEvent,
    LocationResolvedEvent,
    NoInputEvent,
    TextReceivedEvent,
    TimeoutEvent,
    transition,
)


def test_ivr_full_happy_path_state_transitions():
    """Test full IVR call lifecycle: Start -> Lang Menu -> Main Menu -> Record -> Processing -> Location -> Review -> Registering -> Confirm -> Finish."""
    caps = CAPABILITIES[ChannelType.IVR]
    ctx = ConversationContext()

    # 1. Call Start -> LANGUAGE_MENU
    state, actions, ctx = transition(ConversationState.INITIAL, CallStartEvent(), ctx, caps)
    assert state in (ConversationState.LANGUAGE_MENU, ConversationState.SELECT_LANGUAGE)
    assert any(a.type == ActionType.PLAY_PROMPT and a.payload["prompt_key"] == "GREETING_LANG_MENU" for a in actions)
    assert any(a.type == ActionType.GATHER_DTMF for a in actions)

    # 2. Press '1' for Hindi -> MAIN_MENU
    state, actions, ctx = transition(state, DtmfEvent(digits="1"), ctx, caps)
    assert state == ConversationState.MAIN_MENU
    assert ctx.language == "hi"

    # 3. Press '1' to Register a Civic Request -> COMPLAINT_LISTENING
    state, actions, ctx = transition(state, DtmfEvent(digits="1"), ctx, caps)
    assert state in (ConversationState.COMPLAINT_LISTENING, ConversationState.REGISTER_INTRO)
    assert any(a.type == ActionType.RECORD_AUDIO for a in actions)

    # 4. Audio Recorded -> COMPLAINT_PROCESSING (triggers complaint extraction)
    dummy_wav = b"RIFF" + b"\x00" * 200
    state, actions, ctx = transition(state, AudioRecordedEvent(audio_bytes=dummy_wav), ctx, caps)
    assert state == ConversationState.COMPLAINT_PROCESSING
    assert any(a.type == ActionType.TRIGGER_INGEST for a in actions)

    # 5. Complaint extracted -> LOCATION_LISTENING
    extract_evt = ComplaintExtractedEvent(
        original_text="पानी की समस्या",
        summary="Water supply breakdown",
        category="WATER_SUPPLY",
        urgency=4,
    )
    state, actions, ctx = transition(state, extract_evt, ctx, caps)
    assert state == ConversationState.LOCATION_LISTENING

    # 6. Location audio recorded -> LOCATION_PROCESSING
    state, actions, ctx = transition(state, AudioRecordedEvent(audio_bytes=dummy_wav), ctx, caps)
    assert state == ConversationState.LOCATION_PROCESSING

    # 7. Location resolved -> REVIEW_REQUEST
    loc_evt = LocationResolvedEvent(
        resolved=True,
        state="Assam",
        district="Barpeta",
        locality="Town",
        location_text="Barpeta Town, Barpeta, Assam",
    )
    state, actions, ctx = transition(state, loc_evt, ctx, caps)
    assert state == ConversationState.REVIEW_REQUEST

    # 8. Press '1' to Confirm & Register -> REGISTERING
    state, actions, ctx = transition(state, DtmfEvent(digits="1"), ctx, caps)
    assert state == ConversationState.REGISTERING

    # 9. Ingest Success -> REGISTRATION_SUCCESS
    success_evt = IngestSuccessEvent(
        request_id=42,
        category="WATER_SUPPLY",
        district="Barpeta",
        state="Assam",
        urgency=4,
        acknowledgement_native="आपकी पानी की शिकायत दर्ज कर ली गई है।",
        docket_ref="JS-7K4M-92QX",
        language="hi",
        tokens=["JS-7K4M-92QX"],
    )
    state, actions, ctx = transition(state, success_evt, ctx, caps)
    assert state in (ConversationState.REGISTRATION_SUCCESS, ConversationState.CONFIRMING)
    assert ctx.request_id == 42
    assert ctx.docket_ref == "JS-7K4M-92QX"
    assert any(a.type == ActionType.SPELL_OUT_DIGITS for a in actions)
    assert any(a.type == ActionType.GATHER_DTMF for a in actions)

    # 10. Press '1' to Repeat docket reference -> Stays in REGISTRATION_SUCCESS
    state, actions, ctx = transition(state, DtmfEvent(digits="1"), ctx, caps)
    assert state in (ConversationState.REGISTRATION_SUCCESS, ConversationState.CONFIRMING)
    assert any(a.type == ActionType.SPELL_OUT_DIGITS for a in actions)

    # 11. Press '9' to Finish -> COMPLETED with HANGUP
    state, actions, ctx = transition(state, DtmfEvent(digits="9"), ctx, caps)
    assert state == ConversationState.COMPLETED
    assert any(a.type == ActionType.HANGUP for a in actions)


def test_ivr_dropped_call_mid_recording_triggers_no_ingest():
    """Caller hangs up during language selection or audio recording -> leaves cleanly with no ingest action."""
    caps = CAPABILITIES[ChannelType.IVR]
    ctx = ConversationContext()

    state, actions, ctx = transition(ConversationState.INITIAL, CallStartEvent(), ctx, caps)
    assert state in (ConversationState.LANGUAGE_MENU, ConversationState.SELECT_LANGUAGE)

    # Caller hangs up
    state, actions, ctx = transition(state, HangupEvent(), ctx, caps)
    assert state == ConversationState.COMPLETED
    assert not any(a.type == ActionType.TRIGGER_INGEST for a in actions)
    assert any(a.type == ActionType.HANGUP for a in actions)


def test_ivr_invalid_dtmf_and_timeout_retry_limit():
    """Invalid DTMF or silence increments attempt counter and eventually hangs up."""
    caps = CAPABILITIES[ChannelType.IVR]
    ctx = ConversationContext(max_attempts=2)

    state, actions, ctx = transition(ConversationState.INITIAL, CallStartEvent(), ctx, caps)
    assert state in (ConversationState.LANGUAGE_MENU, ConversationState.SELECT_LANGUAGE)

    # Attempt 1: Invalid DTMF digit
    state, actions, ctx = transition(state, DtmfEvent(digits="99"), ctx, caps)
    assert state in (ConversationState.LANGUAGE_MENU, ConversationState.SELECT_LANGUAGE)
    assert ctx.attempts == 1
    assert any(a.type == ActionType.PLAY_PROMPT and a.payload["prompt_key"] == "INVALID_OPTION_RETRY" for a in actions)

    # Attempt 2: Invalid DTMF digit reaches max_attempts -> TIMED_OUT
    state, actions, ctx = transition(state, DtmfEvent(digits="99"), ctx, caps)
    assert state == ConversationState.TIMED_OUT
    assert any(a.type == ActionType.HANGUP for a in actions)


def test_whatsapp_text_and_image_flow():
    """WhatsApp conversation transitions for text and image inputs."""
    caps = CAPABILITIES[ChannelType.WHATSAPP]
    ctx = ConversationContext(language="hi")

    # Direct text input from initial state
    state, actions, ctx = transition(
        ConversationState.INITIAL,
        TextReceivedEvent(text="सड़क टूटी हुई है"),
        ctx,
        caps,
    )
    assert state == ConversationState.PROCESSING
    assert any(a.type == ActionType.TRIGGER_INGEST and a.payload["text"] == "सड़क टूटी हुई है" for a in actions)

    # Ingest success completes with native message reply
    success_evt = IngestSuccessEvent(
        request_id=10,
        category="ROADS",
        district="Pune",
        state="Maharashtra",
        urgency=3,
        acknowledgement_native="सड़क की समस्या दर्ज हो गई है।",
        docket_ref="anon_road123",
        language="hi",
    )
    state, actions, ctx = transition(state, success_evt, ctx, caps)
    assert state == ConversationState.COMPLETED
    assert any(a.type == ActionType.SEND_MESSAGE and "सड़क की समस्या" in a.payload["text"] for a in actions)


# --- The Issue + Location gate inside COLLECT_NEED --------------------------
#
# The adapters run `channels.router` in front of the FSM, but the FSM has to hold
# the same rule on its own: `channels/simulator.py` drives it directly, and a state
# machine that files a placeless complaint while the adapter refuses one is two
# behaviours for one product.


def test_a_placeless_text_is_asked_for_a_location_before_ingest():
    caps = CAPABILITIES[ChannelType.WHATSAPP]
    ctx = ConversationContext(language="hi")

    state, actions, ctx = transition(
        ConversationState.COLLECT_NEED,
        TextReceivedEvent(text="नाली महीनों से बह रही है", location_hint=False),
        ctx,
        caps,
    )
    assert state == ConversationState.COLLECT_NEED
    assert any(
        a.type == ActionType.SEND_MESSAGE and a.payload["prompt_key"] == "NEED_LOCATION_TEXT"
        for a in actions
    )
    # Nothing is filed yet, and the issue is held for the next message.
    assert not any(a.type == ActionType.TRIGGER_INGEST for a in actions)
    assert ctx.meta["issue_text"] == "नाली महीनों से बह रही है"


def test_the_place_reply_is_rejoined_and_then_ingested():
    caps = CAPABILITIES[ChannelType.WHATSAPP]
    ctx = ConversationContext(language="hi")

    _, _, ctx = transition(
        ConversationState.COLLECT_NEED,
        TextReceivedEvent(text="नाली बह रही है", location_hint=False),
        ctx,
        caps,
    )
    state, actions, ctx = transition(
        ConversationState.COLLECT_NEED,
        TextReceivedEvent(text="नबरंगपुर, ओडिशा", location_hint=True),
        ctx,
        caps,
    )
    assert state == ConversationState.PROCESSING
    ingest = next(a for a in actions if a.type == ActionType.TRIGGER_INGEST)
    assert ingest.payload["text"] == "नाली बह रही है — नबरंगपुर, ओडिशा"
    # The pending issue is cleared, or the next complaint inherits this one.
    assert "issue_text" not in ctx.meta


def test_a_second_placeless_message_is_filed_rather_than_looped():
    """One follow-up, not a trap. A village the reference table lacks still counts."""
    caps = CAPABILITIES[ChannelType.WHATSAPP]
    ctx = ConversationContext(language="hi")

    _, _, ctx = transition(
        ConversationState.COLLECT_NEED,
        TextReceivedEvent(text="हैंडपंप खराब है", location_hint=False),
        ctx,
        caps,
    )
    state, actions, ctx = transition(
        ConversationState.COLLECT_NEED,
        TextReceivedEvent(text="छोटेपुर टोला", location_hint=False),
        ctx,
        caps,
    )
    assert state == ConversationState.PROCESSING
    assert any(a.type == ActionType.TRIGGER_INGEST for a in actions)


def test_a_caller_on_a_phone_line_is_never_asked_to_text_a_place():
    """IVR is exempt: `dtmf_in` marks a channel that cannot receive a typed reply.

    A caller who has already spoken their need and hung up cannot be sent a
    follow-up message, so the recording is filed as spoken and the district is
    resolved from whatever the transcript names.
    """
    caps = CAPABILITIES[ChannelType.IVR]
    ctx = ConversationContext(language="hi")

    state, actions, ctx = transition(
        ConversationState.COLLECT_NEED,
        TextReceivedEvent(text="हमारे गाँव में पानी नहीं है", location_hint=False),
        ctx,
        caps,
    )
    assert state == ConversationState.PROCESSING
    assert any(a.type == ActionType.TRIGGER_INGEST for a in actions)


def test_an_unchecked_location_hint_does_not_block_ingest():
    """`None` means the check never ran — no database, or a channel that skips it."""
    caps = CAPABILITIES[ChannelType.SMS]
    ctx = ConversationContext(language="hi")

    state, actions, ctx = transition(
        ConversationState.COLLECT_NEED,
        TextReceivedEvent(text="बिजली नहीं है"),
        ctx,
        caps,
    )
    assert state == ConversationState.PROCESSING
    assert any(a.type == ActionType.TRIGGER_INGEST for a in actions)


def test_ivr_needs_location_transitions_to_collect_location():
    caps = CAPABILITIES[ChannelType.IVR]
    ctx = ConversationContext(language="hi")

    success_evt = IngestSuccessEvent(
        request_id=42,
        category="WATER_SUPPLY",
        district=None,
        state=None,
        urgency=3,
        acknowledgement_native="शिकायत दर्ज हुई।",
        docket_ref="JS-TEST-1234",
        language="hi",
        needs_location=True,
    )
    state, actions, ctx = transition(ConversationState.PROCESSING, success_evt, ctx, caps)
    assert state == ConversationState.COLLECT_LOCATION
    assert any(a.type == ActionType.PLAY_PROMPT and a.payload["prompt_key"] == "RECORD_LOCATION_BEEP" for a in actions)
    assert any(a.type == ActionType.RECORD_AUDIO for a in actions)

    # Audio recorded for location completes and transitions to CONFIRMING
    dummy_wav = b"RIFF" + b"\x00" * 200
    state, actions, ctx = transition(state, AudioRecordedEvent(audio_bytes=dummy_wav), ctx, caps)
    assert state == ConversationState.CONFIRMING

    # Keypad 9 completes call
    state, actions, ctx = transition(state, DtmfEvent(digits="9"), ctx, caps)
    assert state == ConversationState.COMPLETED
    assert any(a.type == ActionType.HANGUP for a in actions)
