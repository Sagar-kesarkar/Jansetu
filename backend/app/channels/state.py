"""Pure conversation state machine for JanSetu channels (IVR, WhatsApp, SMS).

Architecture & Layering Rules:
- Pure Python: no I/O, no database, no network, no LLM calls.
- Pure transition function: (current_state, event, context, capabilities) -> (next_state, actions, context).
- Deterministic and 100% testable in unit tests without external dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConversationState(str, Enum):
    NEW = "NEW"
    INITIAL = "INITIAL"
    SELECT_LANGUAGE = "SELECT_LANGUAGE"
    LANGUAGE_MENU = "LANGUAGE_MENU"
    MORE_LANGUAGES_MENU = "MORE_LANGUAGES_MENU"
    MAIN_MENU = "MAIN_MENU"
    REGISTER_INTRO = "REGISTER_INTRO"
    COLLECT_NEED = "COLLECT_NEED"
    COMPLAINT_LISTENING = "COMPLAINT_LISTENING"
    COMPLAINT_PROCESSING = "COMPLAINT_PROCESSING"
    LOCATION_LISTENING = "LOCATION_LISTENING"
    COLLECT_LOCATION = "COLLECT_LOCATION"
    LOCATION_PROCESSING = "LOCATION_PROCESSING"
    CLARIFICATION_LISTENING = "CLARIFICATION_LISTENING"
    REVIEW_REQUEST = "REVIEW_REQUEST"
    REGISTERING = "REGISTERING"
    REGISTRATION_SUCCESS = "REGISTRATION_SUCCESS"
    CONFIRMING = "CONFIRMING"
    TOKEN_MENU = "TOKEN_MENU"
    TRACK_INTRO = "TRACK_INTRO"
    TRACK_TOKEN_LISTENING = "TRACK_TOKEN_LISTENING"
    TRACK_TOKEN_CONFIRMATION = "TRACK_TOKEN_CONFIRMATION"
    TRACK_PROCESSING = "TRACK_PROCESSING"
    TRACK_RESULT = "TRACK_RESULT"
    FUNDS_INTRO = "FUNDS_INTRO"
    FUNDS_SMS_CONFIRMATION = "FUNDS_SMS_CONFIRMATION"
    FUNDS_SMS_RESULT = "FUNDS_SMS_RESULT"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    TIMED_OUT = "TIMED_OUT"
    ERROR = "ERROR"
    ERROR_RECOVERY = "ERROR_RECOVERY"
    ENDED = "ENDED"


class ChannelType(str, Enum):
    IVR = "ivr"
    WHATSAPP = "whatsapp"
    SMS = "sms"


@dataclass(frozen=True)
class ChannelCapabilities:
    text_in: bool
    audio_in: bool
    image_in: bool
    dtmf_in: bool
    reply_format: str  # "audio_only", "text_native", "text_transliterated"


CAPABILITIES: dict[ChannelType, ChannelCapabilities] = {
    ChannelType.IVR: ChannelCapabilities(
        text_in=False,
        audio_in=True,
        image_in=False,
        dtmf_in=True,
        reply_format="audio_only",
    ),
    ChannelType.WHATSAPP: ChannelCapabilities(
        text_in=True,
        audio_in=True,
        image_in=True,
        dtmf_in=False,
        reply_format="text_native",
    ),
    ChannelType.SMS: ChannelCapabilities(
        text_in=True,
        audio_in=False,
        image_in=False,
        dtmf_in=False,
        reply_format="text_transliterated",
    ),
}

# Primary DTMF Language Map (Menu 1)
DTMF_LANGUAGE_MAP_PAGE_1: dict[str, str] = {
    "1": "hi",  # Hindi
    "2": "ta",  # Tamil
    "3": "te",  # Telugu
    "4": "en",  # English
    "5": "mr",  # Marathi
}

# Secondary DTMF Language Map (Menu 2 - More Languages)
DTMF_LANGUAGE_MAP_PAGE_2: dict[str, str] = {
    "1": "bn",  # Bengali
    "2": "gu",  # Gujarati
    "3": "kn",  # Kannada
    "4": "ml",  # Malayalam
    "5": "or",  # Odia
    "6": "pa",  # Punjabi
    "7": "as",  # Assamese
    "8": "ur",  # Urdu
}

# Unified legacy DTMF map for direct digit-to-language matching
DTMF_LANGUAGE_MAP: dict[str, str] = {
    "1": "hi",
    "2": "bn",
    "3": "ta",
    "4": "te",
    "5": "mr",
    "6": "gu",
    "7": "kn",
    "8": "ml",
    "9": "pa",
    "0": "en",
    "*": "or",
    "#": "as",
}


# --- Actions emitted by state transitions ---

class ActionType(str, Enum):
    PLAY_PROMPT = "PLAY_PROMPT"
    GATHER_DTMF = "GATHER_DTMF"
    RECORD_AUDIO = "RECORD_AUDIO"
    TRIGGER_INGEST = "TRIGGER_INGEST"
    SPELL_OUT_DIGITS = "SPELL_OUT_DIGITS"
    SEND_MESSAGE = "SEND_MESSAGE"
    SEND_SMS = "SEND_SMS"
    QUERY_TRACKING = "QUERY_TRACKING"
    HANGUP = "HANGUP"


@dataclass(frozen=True)
class Action:
    type: ActionType
    payload: dict[str, Any] = field(default_factory=dict)


# --- Events consumed by state transitions ---

@dataclass(frozen=True)
class Event:
    pass


@dataclass(frozen=True)
class CallStartEvent(Event):
    channel: ChannelType = ChannelType.IVR
    initial_language: str | None = None


@dataclass(frozen=True)
class DtmfEvent(Event):
    digits: str


@dataclass(frozen=True)
class AudioRecordedEvent(Event):
    audio_bytes: bytes
    audio_mime: str = "audio/wav"


@dataclass(frozen=True)
class TextReceivedEvent(Event):
    text: str
    location_hint: bool | None = None


@dataclass(frozen=True)
class ImageReceivedEvent(Event):
    image_bytes: bytes
    image_mime: str = "image/jpeg"
    caption: str | None = None


@dataclass(frozen=True)
class IngestSuccessEvent(Event):
    request_id: int
    category: str
    district: str | None
    state: str | None
    urgency: int
    acknowledgement_native: str
    docket_ref: str
    language: str
    needs_location: bool = False
    tokens: list[str] = field(default_factory=list)
    issue_summaries: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class IngestFailureEvent(Event):
    error: str


@dataclass(frozen=True)
class ComplaintExtractedEvent(Event):
    original_text: str
    summary: str
    category: str
    urgency: int
    detected_location: str | None = None
    is_valid_civic_request: bool = True
    issues: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class LocationResolvedEvent(Event):
    resolved: bool
    state: str | None = None
    district: str | None = None
    locality: str | None = None
    location_text: str | None = None
    missing_fields: list[str] = field(default_factory=list)
    clarification_message: str | None = None


@dataclass(frozen=True)
class TrackQueryResultEvent(Event):
    found: bool
    token: str
    status: str | None = None
    department: str | None = None
    updated_at: str | None = None
    district: str | None = None
    state: str | None = None


@dataclass(frozen=True)
class TimeoutEvent(Event):
    pass


@dataclass(frozen=True)
class NoInputEvent(Event):
    pass


@dataclass(frozen=True)
class HangupEvent(Event):
    pass


# --- Conversation Context ---

@dataclass
class ConversationContext:
    language: str = "hi"
    attempts: int = 0
    max_attempts: int = 3
    audio_data: bytes | None = None
    audio_mime: str = "audio/wav"
    text_data: str | None = None
    image_data: bytes | None = None
    image_mime: str = "image/jpeg"
    request_id: int | None = None
    docket_ref: str | None = None
    acknowledgement_native: str | None = None
    error_message: str | None = None
    complaint_text: str | None = None
    complaint_summary: str | None = None
    category: str | None = None
    urgency: int = 1
    location_text: str | None = None
    loc_state: str | None = None
    loc_district: str | None = None
    loc_locality: str | None = None
    registered_tokens: list[str] = field(default_factory=list)
    tracking_token_candidate: str | None = None
    track_result: dict[str, Any] | None = None
    issues: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def copy(self) -> "ConversationContext":
        return ConversationContext(
            language=self.language,
            attempts=self.attempts,
            max_attempts=self.max_attempts,
            audio_data=self.audio_data,
            audio_mime=self.audio_mime,
            text_data=self.text_data,
            image_data=self.image_data,
            image_mime=self.image_mime,
            request_id=self.request_id,
            docket_ref=self.docket_ref,
            acknowledgement_native=self.acknowledgement_native,
            error_message=self.error_message,
            complaint_text=self.complaint_text,
            complaint_summary=self.complaint_summary,
            category=self.category,
            urgency=self.urgency,
            location_text=self.location_text,
            loc_state=self.loc_state,
            loc_district=self.loc_district,
            loc_locality=self.loc_locality,
            registered_tokens=list(self.registered_tokens),
            tracking_token_candidate=self.tracking_token_candidate,
            track_result=dict(self.track_result) if self.track_result else None,
            issues=list(self.issues),
            meta=dict(self.meta),
        )


def _build_main_menu_actions(language: str) -> list[Action]:
    return [
        Action(ActionType.PLAY_PROMPT, {"prompt_key": "MAIN_MENU", "language": language}),
        Action(ActionType.GATHER_DTMF, {
            "num_digits": 1,
            "timeout_sec": 10,
            "valid_digits": ["1", "2", "3", "8", "0", "9"],
        }),
    ]


def _build_lang_menu_actions() -> list[Action]:
    return [
        Action(ActionType.PLAY_PROMPT, {"prompt_key": "GREETING_LANG_MENU", "language": "hi"}),
        Action(ActionType.GATHER_DTMF, {
            "num_digits": 1,
            "timeout_sec": 10,
            "valid_digits": ["1", "2", "3", "4", "5", "6", "0"],
        }),
    ]


def _build_more_lang_menu_actions(current_lang: str = "hi") -> list[Action]:
    return [
        Action(ActionType.PLAY_PROMPT, {"prompt_key": "MORE_LANGUAGES_MENU", "language": current_lang}),
        Action(ActionType.GATHER_DTMF, {
            "num_digits": 1,
            "timeout_sec": 10,
            "valid_digits": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
        }),
    ]


def transition(
    current_state: ConversationState,
    event: Event,
    context: ConversationContext,
    capabilities: ChannelCapabilities,
) -> tuple[ConversationState, list[Action], ConversationContext]:
    """Pure transition function for the JanSetu conversation state machine.

    Takes (current_state, event, context, capabilities) and returns
    (next_state, list_of_actions, updated_context).
    """
    ctx = context.copy()
    actions: list[Action] = []

    # Global Hangup handling
    if isinstance(event, HangupEvent):
        return ConversationState.COMPLETED, [Action(ActionType.HANGUP, {"reason": "caller_hung_up"})], ctx

    # Global CallStart handling
    if isinstance(event, CallStartEvent):
        max_att = context.max_attempts
        ctx = ConversationContext(max_attempts=max_att)
        if event.initial_language:
            ctx.language = event.initial_language
            if capabilities.dtmf_in:
                actions.extend(_build_main_menu_actions(ctx.language))
                return ConversationState.MAIN_MENU, actions, ctx
            elif capabilities.audio_in and not capabilities.text_in:
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "REGISTER_INTRO", "language": ctx.language}))
                actions.append(Action(ActionType.RECORD_AUDIO, {"max_duration_sec": 60, "beep": True}))
                return ConversationState.REGISTER_INTRO, actions, ctx
            elif capabilities.text_in:
                actions.append(Action(ActionType.SEND_MESSAGE, {"prompt_key": "REGISTER_INTRO_TEXT", "language": ctx.language}))
                return ConversationState.REGISTER_INTRO, actions, ctx

        ctx.attempts = 0
        if capabilities.dtmf_in:
            actions.extend(_build_lang_menu_actions())
            return ConversationState.LANGUAGE_MENU, actions, ctx
        else:
            actions.append(Action(ActionType.SEND_MESSAGE, {"prompt_key": "GREETING_LANG_MENU_TEXT", "language": "hi"}))
            return ConversationState.LANGUAGE_MENU, actions, ctx

    # 1. INITIAL / NEW state (Direct message ingress for WhatsApp/SMS)
    if current_state in (ConversationState.INITIAL, ConversationState.NEW):
        if isinstance(event, TextReceivedEvent) and capabilities.text_in:
            ctx.text_data = event.text
            actions.append(Action(ActionType.TRIGGER_INGEST, {
                "text": event.text,
                "audio_bytes": None,
                "audio_mime": "audio/webm",
                "image_bytes": None,
                "image_mime": "image/jpeg",
                "language": ctx.language,
            }))
            return ConversationState.PROCESSING, actions, ctx

        elif isinstance(event, AudioRecordedEvent) and capabilities.audio_in:
            ctx.audio_data = event.audio_bytes
            ctx.audio_mime = event.audio_mime
            actions.append(Action(ActionType.TRIGGER_INGEST, {
                "text": None,
                "audio_bytes": event.audio_bytes,
                "audio_mime": event.audio_mime,
                "image_bytes": None,
                "image_mime": "image/jpeg",
                "language": ctx.language,
            }))
            return ConversationState.PROCESSING, actions, ctx

    # 2. SELECT_LANGUAGE / LANGUAGE_MENU
    elif current_state in (ConversationState.SELECT_LANGUAGE, ConversationState.LANGUAGE_MENU):
        if isinstance(event, DtmfEvent) and capabilities.dtmf_in:
            digit = event.digits.strip()
            if digit == "0":
                actions.extend(_build_lang_menu_actions())
                return current_state, actions, ctx
            elif digit == "6":
                ctx.attempts = 0
                actions.extend(_build_more_lang_menu_actions(ctx.language))
                return ConversationState.MORE_LANGUAGES_MENU, actions, ctx
            elif digit in DTMF_LANGUAGE_MAP_PAGE_1 or digit in DTMF_LANGUAGE_MAP:
                selected_lang = DTMF_LANGUAGE_MAP_PAGE_1.get(digit) or DTMF_LANGUAGE_MAP.get(digit) or "hi"
                ctx.language = selected_lang
                ctx.attempts = 0

                if current_state == ConversationState.SELECT_LANGUAGE:
                    # Legacy 4-step sequence: direct transition to COLLECT_NEED
                    actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "RECORD_NEED_BEEP", "language": ctx.language}))
                    actions.append(Action(ActionType.RECORD_AUDIO, {"max_duration_sec": 60, "beep": True, "finish_on_key": "#"}))
                    return ConversationState.COLLECT_NEED, actions, ctx
                else:
                    # Full 24-state sequence: transition to MAIN_MENU
                    actions.extend(_build_main_menu_actions(ctx.language))
                    return ConversationState.MAIN_MENU, actions, ctx
            else:
                ctx.attempts += 1
                if ctx.attempts >= ctx.max_attempts:
                    actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "TIMEOUT_HANGUP", "language": ctx.language}))
                    actions.append(Action(ActionType.HANGUP, {"reason": "max_invalid_attempts"}))
                    return ConversationState.TIMED_OUT, actions, ctx
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "INVALID_OPTION_RETRY", "language": "hi"}))
                actions.extend(_build_lang_menu_actions())
                return current_state, actions, ctx

        elif isinstance(event, TextReceivedEvent) and capabilities.text_in:
            text_clean = event.text.strip().lower()
            if text_clean in DTMF_LANGUAGE_MAP_PAGE_1:
                ctx.language = DTMF_LANGUAGE_MAP_PAGE_1[text_clean]
            elif text_clean in DTMF_LANGUAGE_MAP:
                ctx.language = DTMF_LANGUAGE_MAP[text_clean]
            ctx.attempts = 0
            actions.append(Action(ActionType.SEND_MESSAGE, {"prompt_key": "REGISTER_INTRO_TEXT", "language": ctx.language}))
            return ConversationState.COLLECT_NEED, actions, ctx

        elif isinstance(event, (TimeoutEvent, NoInputEvent)):
            ctx.attempts += 1
            if ctx.attempts >= ctx.max_attempts:
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "TIMEOUT_HANGUP", "language": ctx.language}))
                actions.append(Action(ActionType.HANGUP, {"reason": "timeout"}))
                return ConversationState.TIMED_OUT, actions, ctx
            actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "NO_INPUT_RETRY", "language": "hi"}))
            actions.extend(_build_lang_menu_actions())
            return current_state, actions, ctx

    # 3. MORE_LANGUAGES_MENU
    elif current_state == ConversationState.MORE_LANGUAGES_MENU:
        if isinstance(event, DtmfEvent) and capabilities.dtmf_in:
            digit = event.digits.strip()
            if digit == "0":
                actions.extend(_build_more_lang_menu_actions(ctx.language))
                return ConversationState.MORE_LANGUAGES_MENU, actions, ctx
            elif digit == "9":
                ctx.attempts = 0
                actions.extend(_build_lang_menu_actions())
                return ConversationState.LANGUAGE_MENU, actions, ctx
            elif digit in DTMF_LANGUAGE_MAP_PAGE_2:
                ctx.language = DTMF_LANGUAGE_MAP_PAGE_2[digit]
                ctx.attempts = 0
                actions.extend(_build_main_menu_actions(ctx.language))
                return ConversationState.MAIN_MENU, actions, ctx
            else:
                ctx.attempts += 1
                if ctx.attempts >= ctx.max_attempts:
                    actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "TIMEOUT_HANGUP", "language": ctx.language}))
                    actions.append(Action(ActionType.HANGUP, {"reason": "max_invalid_attempts"}))
                    return ConversationState.TIMED_OUT, actions, ctx
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "INVALID_OPTION_RETRY", "language": ctx.language}))
                actions.extend(_build_more_lang_menu_actions(ctx.language))
                return ConversationState.MORE_LANGUAGES_MENU, actions, ctx

        elif isinstance(event, (TimeoutEvent, NoInputEvent)):
            ctx.attempts += 1
            if ctx.attempts >= ctx.max_attempts:
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "TIMEOUT_HANGUP", "language": ctx.language}))
                actions.append(Action(ActionType.HANGUP, {"reason": "timeout"}))
                return ConversationState.TIMED_OUT, actions, ctx
            actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "NO_INPUT_RETRY", "language": ctx.language}))
            actions.extend(_build_more_lang_menu_actions(ctx.language))
            return ConversationState.MORE_LANGUAGES_MENU, actions, ctx

    # 4. MAIN_MENU
    elif current_state == ConversationState.MAIN_MENU:
        if isinstance(event, DtmfEvent) and capabilities.dtmf_in:
            digit = event.digits.strip()
            if digit == "1":
                ctx.attempts = 0
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "REGISTER_INTRO", "language": ctx.language}))
                actions.append(Action(ActionType.RECORD_AUDIO, {"max_duration_sec": 60, "beep": True, "finish_on_key": "#"}))
                actions.append(Action(ActionType.GATHER_DTMF, {"num_digits": 1, "timeout_sec": 15, "valid_digits": ["#"]}))
                return ConversationState.COMPLAINT_LISTENING, actions, ctx

            elif digit == "2":
                ctx.attempts = 0
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "TRACK_INTRO", "language": ctx.language}))
                actions.append(Action(ActionType.RECORD_AUDIO, {"max_duration_sec": 30, "beep": True}))
                return ConversationState.TRACK_TOKEN_LISTENING, actions, ctx

            elif digit == "3":
                ctx.attempts = 0
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "FUNDS_INTRO", "language": ctx.language}))
                actions.append(Action(ActionType.GATHER_DTMF, {
                    "num_digits": 1,
                    "timeout_sec": 10,
                    "valid_digits": ["1", "2", "0"],
                }))
                return ConversationState.FUNDS_INTRO, actions, ctx

            elif digit == "8":
                ctx.attempts = 0
                actions.extend(_build_lang_menu_actions())
                return ConversationState.LANGUAGE_MENU, actions, ctx

            elif digit == "0":
                actions.extend(_build_main_menu_actions(ctx.language))
                return ConversationState.MAIN_MENU, actions, ctx

            elif digit == "9":
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "THANK_YOU", "language": ctx.language}))
                actions.append(Action(ActionType.HANGUP, {"reason": "caller_ended_call"}))
                return ConversationState.COMPLETED, actions, ctx

            else:
                ctx.attempts += 1
                if ctx.attempts >= ctx.max_attempts:
                    actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "TIMEOUT_HANGUP", "language": ctx.language}))
                    actions.append(Action(ActionType.HANGUP, {"reason": "max_invalid_attempts"}))
                    return ConversationState.TIMED_OUT, actions, ctx
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "INVALID_OPTION_RETRY", "language": ctx.language}))
                actions.extend(_build_main_menu_actions(ctx.language))
                return ConversationState.MAIN_MENU, actions, ctx

        elif isinstance(event, (TimeoutEvent, NoInputEvent)):
            ctx.attempts += 1
            if ctx.attempts >= ctx.max_attempts:
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "TIMEOUT_HANGUP", "language": ctx.language}))
                actions.append(Action(ActionType.HANGUP, {"reason": "timeout"}))
                return ConversationState.TIMED_OUT, actions, ctx
            actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "NO_INPUT_RETRY", "language": ctx.language}))
            actions.extend(_build_main_menu_actions(ctx.language))
            return ConversationState.MAIN_MENU, actions, ctx

    # 5. REGISTER_INTRO / COMPLAINT_LISTENING / COLLECT_NEED
    elif current_state in (ConversationState.REGISTER_INTRO, ConversationState.COMPLAINT_LISTENING, ConversationState.COLLECT_NEED):
        if isinstance(event, AudioRecordedEvent) and capabilities.audio_in:
            if not event.audio_bytes or len(event.audio_bytes) < 32:
                ctx.attempts += 1
                if ctx.attempts >= ctx.max_attempts:
                    actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "TIMEOUT_HANGUP", "language": ctx.language}))
                    actions.append(Action(ActionType.HANGUP, {"reason": "empty_audio_recording"}))
                    return ConversationState.TIMED_OUT, actions, ctx
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "NO_INPUT_RETRY", "language": ctx.language}))
                actions.append(Action(ActionType.RECORD_AUDIO, {"max_duration_sec": 60, "beep": True}))
                return current_state, actions, ctx

            ctx.audio_data = event.audio_bytes
            ctx.audio_mime = event.audio_mime
            ctx.attempts = 0
            if current_state == ConversationState.COLLECT_NEED:
                # Legacy direct processing
                actions.append(Action(ActionType.TRIGGER_INGEST, {
                    "text": ctx.text_data,
                    "audio_bytes": event.audio_bytes,
                    "audio_mime": event.audio_mime,
                    "language": ctx.language,
                }))
                return ConversationState.PROCESSING, actions, ctx
            else:
                if capabilities.dtmf_in:
                    actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "PROCESSING_WAIT", "language": ctx.language}))
                actions.append(Action(ActionType.TRIGGER_INGEST, {
                    "step": "extract_complaint",
                    "text": ctx.text_data,
                    "audio_bytes": event.audio_bytes,
                    "audio_mime": event.audio_mime,
                    "language": ctx.language,
                }))
                return ConversationState.COMPLAINT_PROCESSING, actions, ctx

        elif isinstance(event, TextReceivedEvent):
            # Location hint gate for messaging channels (WhatsApp/SMS)
            if not capabilities.dtmf_in and event.location_hint is False and "issue_text" not in ctx.meta:
                ctx.meta["issue_text"] = event.text
                actions.append(Action(ActionType.SEND_MESSAGE, {
                    "prompt_key": "NEED_LOCATION_TEXT",
                    "language": ctx.language,
                }))
                return ConversationState.COLLECT_NEED, actions, ctx

            # Either location_hint is True, or it's a second message, or it's IVR
            pending = ctx.meta.pop("issue_text", None)
            final_text = f"{pending} — {event.text}" if pending else event.text
            ctx.text_data = final_text
            ctx.complaint_text = final_text
            ctx.attempts = 0

            if current_state == ConversationState.COLLECT_NEED:
                actions.append(Action(ActionType.TRIGGER_INGEST, {
                    "text": final_text,
                    "audio_bytes": None,
                    "audio_mime": "audio/webm",
                    "language": ctx.language,
                }))
                return ConversationState.PROCESSING, actions, ctx
            else:
                if capabilities.dtmf_in:
                    actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "PROCESSING_WAIT", "language": ctx.language}))
                actions.append(Action(ActionType.TRIGGER_INGEST, {
                    "step": "extract_complaint",
                    "text": final_text,
                    "audio_bytes": None,
                    "audio_mime": "audio/webm",
                    "language": ctx.language,
                }))
                return ConversationState.COMPLAINT_PROCESSING, actions, ctx

        elif isinstance(event, ImageReceivedEvent) and capabilities.image_in:
            ctx.image_data = event.image_bytes
            ctx.image_mime = event.image_mime
            if event.caption:
                ctx.text_data = event.caption
            actions.append(Action(ActionType.TRIGGER_INGEST, {
                "step": "extract_complaint",
                "text": ctx.text_data,
                "image_bytes": event.image_bytes,
                "image_mime": event.image_mime,
                "language": ctx.language,
            }))
            return ConversationState.COMPLAINT_PROCESSING, actions, ctx

        elif isinstance(event, (TimeoutEvent, NoInputEvent)):
            ctx.attempts += 1
            if ctx.attempts >= ctx.max_attempts:
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "TIMEOUT_HANGUP", "language": ctx.language}))
                actions.append(Action(ActionType.HANGUP, {"reason": "timeout_in_complaint_recording"}))
                return ConversationState.TIMED_OUT, actions, ctx
            actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "NO_INPUT_RETRY", "language": ctx.language}))
            actions.append(Action(ActionType.RECORD_AUDIO, {"max_duration_sec": 60, "beep": True}))
            return current_state, actions, ctx

    # 6. COMPLAINT_PROCESSING
    elif current_state == ConversationState.COMPLAINT_PROCESSING:
        if isinstance(event, ComplaintExtractedEvent):
            ctx.complaint_text = event.original_text
            ctx.complaint_summary = event.summary
            ctx.category = event.category
            ctx.urgency = event.urgency
            ctx.issues = event.issues
            ctx.attempts = 0

            if event.detected_location:
                ctx.location_text = event.detected_location

            actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "LOCATION_PROMPT", "language": ctx.language}))
            actions.append(Action(ActionType.RECORD_AUDIO, {"max_duration_sec": 45, "beep": True, "finish_on_key": "#"}))
            return ConversationState.LOCATION_LISTENING, actions, ctx

        elif isinstance(event, IngestFailureEvent):
            ctx.error_message = event.error
            actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "ERROR_MSG", "language": ctx.language}))
            actions.append(Action(ActionType.HANGUP, {"reason": "complaint_extraction_failed"}))
            return ConversationState.ERROR, actions, ctx

    # 7. LOCATION_LISTENING / COLLECT_LOCATION / CLARIFICATION_LISTENING
    elif current_state in (ConversationState.LOCATION_LISTENING, ConversationState.COLLECT_LOCATION, ConversationState.CLARIFICATION_LISTENING):
        if isinstance(event, AudioRecordedEvent) and capabilities.audio_in:
            if not event.audio_bytes or len(event.audio_bytes) < 32:
                ctx.attempts += 1
                if ctx.attempts >= ctx.max_attempts:
                    actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "LOCATION_FAILED_CLOSING", "language": ctx.language}))
                    actions.append(Action(ActionType.HANGUP, {"reason": "location_unresolved_timeout"}))
                    return ConversationState.COMPLETED, actions, ctx
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "LOCATION_CLARIFICATION", "language": ctx.language}))
                actions.append(Action(ActionType.RECORD_AUDIO, {"max_duration_sec": 45, "beep": True}))
                return ConversationState.CLARIFICATION_LISTENING, actions, ctx

            if current_state == ConversationState.COLLECT_LOCATION:
                # Legacy path completes directly to CONFIRMING
                return ConversationState.CONFIRMING, actions, ctx

            actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "PROCESSING_WAIT", "language": ctx.language}))
            actions.append(Action(ActionType.TRIGGER_INGEST, {
                "step": "resolve_location",
                "audio_bytes": event.audio_bytes,
                "audio_mime": event.audio_mime,
                "language": ctx.language,
            }))
            return ConversationState.LOCATION_PROCESSING, actions, ctx

        elif isinstance(event, TextReceivedEvent):
            loc_text = event.text.strip()
            ctx.location_text = loc_text
            actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "PROCESSING_WAIT", "language": ctx.language}))
            actions.append(Action(ActionType.TRIGGER_INGEST, {
                "step": "resolve_location",
                "text": loc_text,
                "language": ctx.language,
            }))
            return ConversationState.LOCATION_PROCESSING, actions, ctx

        elif isinstance(event, (TimeoutEvent, NoInputEvent)):
            ctx.attempts += 1
            if ctx.attempts >= ctx.max_attempts:
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "LOCATION_FAILED_CLOSING", "language": ctx.language}))
                actions.append(Action(ActionType.HANGUP, {"reason": "location_timeout"}))
                return ConversationState.COMPLETED, actions, ctx
            actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "LOCATION_CLARIFICATION", "language": ctx.language}))
            actions.append(Action(ActionType.RECORD_AUDIO, {"max_duration_sec": 45, "beep": True}))
            return ConversationState.CLARIFICATION_LISTENING, actions, ctx

    # 8. LOCATION_PROCESSING
    elif current_state == ConversationState.LOCATION_PROCESSING:
        if isinstance(event, LocationResolvedEvent):
            if event.resolved:
                ctx.loc_state = event.state
                ctx.loc_district = event.district
                ctx.loc_locality = event.locality
                ctx.location_text = event.location_text or f"{event.locality or ''}, {event.district or ''}, {event.state or ''}".strip(", ")
                ctx.attempts = 0

                loc_display = ctx.location_text or f"{event.district or ''}, {event.state or ''}"
                summary_display = ctx.complaint_summary or ctx.complaint_text or "Local issue"

                actions.append(Action(ActionType.PLAY_PROMPT, {
                    "prompt_key": "REVIEW_REQUEST",
                    "language": ctx.language,
                    "summary": summary_display,
                    "location": loc_display,
                }))
                actions.append(Action(ActionType.GATHER_DTMF, {
                    "num_digits": 1,
                    "timeout_sec": 12,
                    "valid_digits": ["1", "2", "3", "0", "9"],
                }))
                return ConversationState.REVIEW_REQUEST, actions, ctx
            else:
                ctx.attempts += 1
                if ctx.attempts >= ctx.max_attempts:
                    actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "LOCATION_FAILED_CLOSING", "language": ctx.language}))
                    actions.append(Action(ActionType.HANGUP, {"reason": "location_unresolved_after_retries"}))
                    return ConversationState.COMPLETED, actions, ctx
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "LOCATION_CLARIFICATION", "language": ctx.language}))
                actions.append(Action(ActionType.RECORD_AUDIO, {"max_duration_sec": 45, "beep": True}))
                return ConversationState.CLARIFICATION_LISTENING, actions, ctx

        elif isinstance(event, IngestFailureEvent):
            actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "LOCATION_CLARIFICATION", "language": ctx.language}))
            actions.append(Action(ActionType.RECORD_AUDIO, {"max_duration_sec": 45, "beep": True}))
            return ConversationState.CLARIFICATION_LISTENING, actions, ctx

    # 9. REVIEW_REQUEST
    elif current_state == ConversationState.REVIEW_REQUEST:
        if isinstance(event, DtmfEvent) and capabilities.dtmf_in:
            digit = event.digits.strip()
            if digit == "1":
                ctx.attempts = 0
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "PROCESSING_WAIT", "language": ctx.language}))
                actions.append(Action(ActionType.TRIGGER_INGEST, {
                    "step": "register_complaint",
                    "text": ctx.complaint_text,
                    "summary": ctx.complaint_summary,
                    "location_text": ctx.location_text,
                    "category": ctx.category,
                    "urgency": ctx.urgency,
                    "language": ctx.language,
                }))
                return ConversationState.REGISTERING, actions, ctx

            elif digit == "2":
                ctx.attempts = 0
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "REGISTER_INTRO", "language": ctx.language}))
                actions.append(Action(ActionType.RECORD_AUDIO, {"max_duration_sec": 60, "beep": True, "finish_on_key": "#"}))
                return ConversationState.COMPLAINT_LISTENING, actions, ctx

            elif digit == "3":
                ctx.attempts = 0
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "LOCATION_PROMPT", "language": ctx.language}))
                actions.append(Action(ActionType.RECORD_AUDIO, {"max_duration_sec": 45, "beep": True, "finish_on_key": "#"}))
                return ConversationState.LOCATION_LISTENING, actions, ctx

            elif digit == "0":
                loc_display = ctx.location_text or "Location"
                summary_display = ctx.complaint_summary or ctx.complaint_text or "Complaint"
                actions.append(Action(ActionType.PLAY_PROMPT, {
                    "prompt_key": "REVIEW_REQUEST",
                    "language": ctx.language,
                    "summary": summary_display,
                    "location": loc_display,
                }))
                actions.append(Action(ActionType.GATHER_DTMF, {
                    "num_digits": 1,
                    "timeout_sec": 12,
                    "valid_digits": ["1", "2", "3", "0", "9"],
                }))
                return ConversationState.REVIEW_REQUEST, actions, ctx

            elif digit == "9":
                actions.extend(_build_main_menu_actions(ctx.language))
                return ConversationState.MAIN_MENU, actions, ctx

            else:
                ctx.attempts += 1
                if ctx.attempts >= ctx.max_attempts:
                    actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "TIMEOUT_HANGUP", "language": ctx.language}))
                    actions.append(Action(ActionType.HANGUP, {"reason": "max_invalid_attempts"}))
                    return ConversationState.TIMED_OUT, actions, ctx
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "INVALID_OPTION_RETRY", "language": ctx.language}))
                return ConversationState.REVIEW_REQUEST, actions, ctx

    # 10. REGISTERING / PROCESSING
    elif current_state in (ConversationState.REGISTERING, ConversationState.PROCESSING):
        if isinstance(event, IngestSuccessEvent):
            if event.needs_location:
                # Missing location gate -> prompt location
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "RECORD_LOCATION_BEEP", "language": ctx.language}))
                actions.append(Action(ActionType.RECORD_AUDIO, {"max_duration_sec": 45, "beep": True}))
                return ConversationState.COLLECT_LOCATION, actions, ctx

            ctx.request_id = event.request_id
            ctx.docket_ref = event.docket_ref
            ctx.registered_tokens = event.tokens if event.tokens else [event.docket_ref]
            ctx.acknowledgement_native = event.acknowledgement_native
            ctx.language = event.language or ctx.language
            ctx.attempts = 0

            if capabilities.dtmf_in:
                actions.append(Action(ActionType.PLAY_PROMPT, {
                    "prompt_key": "REGISTRATION_SUCCESS",
                    "language": ctx.language,
                }))
                actions.append(Action(ActionType.SPELL_OUT_DIGITS, {
                    "digits": event.docket_ref,
                    "language": ctx.language,
                }))
                actions.append(Action(ActionType.PLAY_PROMPT, {
                    "prompt_key": "TOKEN_MENU",
                    "language": ctx.language,
                }))
                actions.append(Action(ActionType.GATHER_DTMF, {
                    "num_digits": 1,
                    "timeout_sec": 12,
                    "valid_digits": ["1", "2", "0", "9"],
                }))
                return ConversationState.CONFIRMING if current_state == ConversationState.PROCESSING else ConversationState.REGISTRATION_SUCCESS, actions, ctx
            else:
                msg = f"{event.acknowledgement_native}\n\n📌 Tracking token: {event.docket_ref}"
                actions.append(Action(ActionType.SEND_MESSAGE, {
                    "text": msg,
                    "language": ctx.language,
                }))
                return ConversationState.COMPLETED, actions, ctx

        elif isinstance(event, IngestFailureEvent):
            ctx.error_message = event.error
            actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "ERROR_MSG", "language": ctx.language}))
            actions.append(Action(ActionType.HANGUP, {"reason": "ingest_failure"}))
            return ConversationState.ERROR, actions, ctx

    # 11. REGISTRATION_SUCCESS / TOKEN_MENU / CONFIRMING
    elif current_state in (ConversationState.REGISTRATION_SUCCESS, ConversationState.TOKEN_MENU, ConversationState.CONFIRMING):
        if isinstance(event, DtmfEvent) and capabilities.dtmf_in:
            digit = event.digits.strip()
            if digit == "1":
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "REGISTRATION_SUCCESS", "language": ctx.language}))
                actions.append(Action(ActionType.SPELL_OUT_DIGITS, {
                    "digits": ctx.docket_ref or "",
                    "language": ctx.language,
                }))
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "TOKEN_MENU", "language": ctx.language}))
                actions.append(Action(ActionType.GATHER_DTMF, {
                    "num_digits": 1,
                    "timeout_sec": 12,
                    "valid_digits": ["1", "2", "0", "9"],
                }))
                return current_state, actions, ctx

            elif digit == "2":
                if current_state == ConversationState.CONFIRMING:
                    # Legacy: DTMF '2' completes call
                    actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "THANK_YOU", "language": ctx.language}))
                    actions.append(Action(ActionType.HANGUP, {"reason": "caller_finished"}))
                    return ConversationState.COMPLETED, actions, ctx
                else:
                    # Send SMS and stay in menu
                    actions.append(Action(ActionType.SEND_SMS, {
                        "type": "token_confirmation",
                        "token": ctx.docket_ref,
                        "language": ctx.language,
                    }))
                    actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "SMS_SENT_NOTICE", "language": ctx.language}))
                    actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "TOKEN_MENU", "language": ctx.language}))
                    actions.append(Action(ActionType.GATHER_DTMF, {
                        "num_digits": 1,
                        "timeout_sec": 12,
                        "valid_digits": ["1", "2", "0", "9"],
                    }))
                    return current_state, actions, ctx

            elif digit == "0":
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "REGISTRATION_SUCCESS", "language": ctx.language}))
                actions.append(Action(ActionType.SPELL_OUT_DIGITS, {
                    "digits": ctx.docket_ref or "",
                    "language": ctx.language,
                }))
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "TOKEN_MENU", "language": ctx.language}))
                actions.append(Action(ActionType.GATHER_DTMF, {
                    "num_digits": 1,
                    "timeout_sec": 12,
                    "valid_digits": ["1", "2", "0", "9"],
                }))
                return current_state, actions, ctx

            elif digit == "9":
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "THANK_YOU", "language": ctx.language}))
                actions.append(Action(ActionType.HANGUP, {"reason": "caller_finished"}))
                return ConversationState.COMPLETED, actions, ctx

            else:
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "THANK_YOU", "language": ctx.language}))
                actions.append(Action(ActionType.HANGUP, {"reason": "caller_finished"}))
                return ConversationState.COMPLETED, actions, ctx

        elif isinstance(event, (TimeoutEvent, NoInputEvent)):
            actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "THANK_YOU", "language": ctx.language}))
            actions.append(Action(ActionType.HANGUP, {"reason": "timeout_after_confirmation"}))
            return ConversationState.COMPLETED, actions, ctx

    # 12. TRACK_INTRO / TRACK_TOKEN_LISTENING
    elif current_state in (ConversationState.TRACK_INTRO, ConversationState.TRACK_TOKEN_LISTENING):
        if isinstance(event, (AudioRecordedEvent, TextReceivedEvent)):
            token_candidate = ""
            if isinstance(event, TextReceivedEvent):
                token_candidate = event.text.strip().upper()
            elif isinstance(event, AudioRecordedEvent):
                token_candidate = ctx.tracking_token_candidate or "JS-SAMPLE"

            ctx.tracking_token_candidate = token_candidate
            ctx.attempts = 0
            actions.append(Action(ActionType.PLAY_PROMPT, {
                "prompt_key": "TRACK_TOKEN_CONFIRMATION",
                "language": ctx.language,
                "token": token_candidate,
            }))
            actions.append(Action(ActionType.SPELL_OUT_DIGITS, {
                "digits": token_candidate,
                "language": ctx.language,
            }))
            actions.append(Action(ActionType.GATHER_DTMF, {
                "num_digits": 1,
                "timeout_sec": 10,
                "valid_digits": ["1", "2", "0", "9"],
            }))
            return ConversationState.TRACK_TOKEN_CONFIRMATION, actions, ctx

        elif isinstance(event, (TimeoutEvent, NoInputEvent)):
            ctx.attempts += 1
            if ctx.attempts >= ctx.max_attempts:
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "TIMEOUT_HANGUP", "language": ctx.language}))
                actions.append(Action(ActionType.HANGUP, {"reason": "timeout_tracking"}))
                return ConversationState.TIMED_OUT, actions, ctx
            actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "NO_INPUT_RETRY", "language": ctx.language}))
            actions.append(Action(ActionType.RECORD_AUDIO, {"max_duration_sec": 30, "beep": True}))
            return ConversationState.TRACK_TOKEN_LISTENING, actions, ctx

    # 13. TRACK_TOKEN_CONFIRMATION
    elif current_state == ConversationState.TRACK_TOKEN_CONFIRMATION:
        if isinstance(event, DtmfEvent) and capabilities.dtmf_in:
            digit = event.digits.strip()
            if digit == "1":
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "PROCESSING_WAIT", "language": ctx.language}))
                actions.append(Action(ActionType.QUERY_TRACKING, {"token": ctx.tracking_token_candidate}))
                return ConversationState.TRACK_PROCESSING, actions, ctx

            elif digit == "2":
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "TRACK_INTRO", "language": ctx.language}))
                actions.append(Action(ActionType.RECORD_AUDIO, {"max_duration_sec": 30, "beep": True}))
                return ConversationState.TRACK_TOKEN_LISTENING, actions, ctx

            elif digit == "0":
                actions.append(Action(ActionType.PLAY_PROMPT, {
                    "prompt_key": "TRACK_TOKEN_CONFIRMATION",
                    "language": ctx.language,
                    "token": ctx.tracking_token_candidate or "",
                }))
                actions.append(Action(ActionType.SPELL_OUT_DIGITS, {
                    "digits": ctx.tracking_token_candidate or "",
                    "language": ctx.language,
                }))
                actions.append(Action(ActionType.GATHER_DTMF, {
                    "num_digits": 1,
                    "timeout_sec": 10,
                    "valid_digits": ["1", "2", "0", "9"],
                }))
                return ConversationState.TRACK_TOKEN_CONFIRMATION, actions, ctx

            elif digit == "9":
                actions.extend(_build_main_menu_actions(ctx.language))
                return ConversationState.MAIN_MENU, actions, ctx

    # 14. TRACK_PROCESSING
    elif current_state == ConversationState.TRACK_PROCESSING:
        if isinstance(event, TrackQueryResultEvent):
            if event.found:
                ctx.track_result = {
                    "token": event.token,
                    "status": event.status,
                    "department": event.department,
                    "updated_at": event.updated_at,
                    "district": event.district,
                    "state": event.state,
                }
                actions.append(Action(ActionType.PLAY_PROMPT, {
                    "prompt_key": "TRACK_RESULT",
                    "language": ctx.language,
                    "token": event.token,
                    "status": event.status or "Under Review",
                    "department": event.department or "Public Grievance Desk",
                    "updated_at": event.updated_at or "Recently",
                }))
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "TRACK_RESULT_MENU", "language": ctx.language}))
                actions.append(Action(ActionType.GATHER_DTMF, {
                    "num_digits": 1,
                    "timeout_sec": 12,
                    "valid_digits": ["1", "2", "9"],
                }))
                return ConversationState.TRACK_RESULT, actions, ctx
            else:
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "TRACK_NOT_FOUND", "language": ctx.language}))
                actions.append(Action(ActionType.GATHER_DTMF, {
                    "num_digits": 1,
                    "timeout_sec": 10,
                    "valid_digits": ["1", "9"],
                }))
                return ConversationState.TRACK_RESULT, actions, ctx

    # 15. TRACK_RESULT
    elif current_state == ConversationState.TRACK_RESULT:
        if isinstance(event, DtmfEvent) and capabilities.dtmf_in:
            digit = event.digits.strip()
            if digit == "1":
                if ctx.track_result:
                    tr = ctx.track_result
                    actions.append(Action(ActionType.PLAY_PROMPT, {
                        "prompt_key": "TRACK_RESULT",
                        "language": ctx.language,
                        "token": tr["token"],
                        "status": tr["status"],
                        "department": tr["department"],
                        "updated_at": tr["updated_at"],
                    }))
                    actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "TRACK_RESULT_MENU", "language": ctx.language}))
                    actions.append(Action(ActionType.GATHER_DTMF, {"num_digits": 1, "timeout_sec": 12, "valid_digits": ["1", "2", "9"]}))
                    return ConversationState.TRACK_RESULT, actions, ctx
                else:
                    actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "TRACK_INTRO", "language": ctx.language}))
                    actions.append(Action(ActionType.RECORD_AUDIO, {"max_duration_sec": 30, "beep": True}))
                    return ConversationState.TRACK_TOKEN_LISTENING, actions, ctx

            elif digit == "2" and ctx.track_result:
                actions.append(Action(ActionType.SEND_SMS, {
                    "type": "track_link",
                    "token": ctx.track_result["token"],
                    "language": ctx.language,
                }))
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "SMS_SENT_NOTICE", "language": ctx.language}))
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "TRACK_RESULT_MENU", "language": ctx.language}))
                actions.append(Action(ActionType.GATHER_DTMF, {"num_digits": 1, "timeout_sec": 12, "valid_digits": ["1", "2", "9"]}))
                return ConversationState.TRACK_RESULT, actions, ctx

            elif digit == "9":
                actions.extend(_build_main_menu_actions(ctx.language))
                return ConversationState.MAIN_MENU, actions, ctx

    # 16. FUNDS_INTRO / FUNDS_SMS_CONFIRMATION
    elif current_state in (ConversationState.FUNDS_INTRO, ConversationState.FUNDS_SMS_CONFIRMATION):
        if isinstance(event, DtmfEvent) and capabilities.dtmf_in:
            digit = event.digits.strip()
            if digit == "1":
                actions.append(Action(ActionType.SEND_SMS, {
                    "type": "public_funds_link",
                    "language": ctx.language,
                }))
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "FUNDS_SMS_RESULT", "language": ctx.language}))
                actions.append(Action(ActionType.GATHER_DTMF, {"num_digits": 1, "timeout_sec": 10, "valid_digits": ["9", "0"]}))
                return ConversationState.FUNDS_SMS_RESULT, actions, ctx

            elif digit == "2":
                actions.extend(_build_main_menu_actions(ctx.language))
                return ConversationState.MAIN_MENU, actions, ctx

            elif digit == "0":
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "FUNDS_INTRO", "language": ctx.language}))
                actions.append(Action(ActionType.GATHER_DTMF, {"num_digits": 1, "timeout_sec": 10, "valid_digits": ["1", "2", "0"]}))
                return ConversationState.FUNDS_INTRO, actions, ctx

    # 17. FUNDS_SMS_RESULT
    elif current_state == ConversationState.FUNDS_SMS_RESULT:
        if isinstance(event, DtmfEvent) and capabilities.dtmf_in:
            digit = event.digits.strip()
            if digit == "9":
                actions.extend(_build_main_menu_actions(ctx.language))
                return ConversationState.MAIN_MENU, actions, ctx
            elif digit == "0":
                actions.append(Action(ActionType.PLAY_PROMPT, {"prompt_key": "FUNDS_SMS_RESULT", "language": ctx.language}))
                return ConversationState.FUNDS_SMS_RESULT, actions, ctx

    # Terminal states fallback
    if current_state in (ConversationState.COMPLETED, ConversationState.TIMED_OUT, ConversationState.ERROR, ConversationState.ENDED):
        return ConversationState.COMPLETED, [Action(ActionType.HANGUP, {"reason": "already_terminated"})], ctx

    # Default safety error handler
    return ConversationState.ERROR, [
        Action(ActionType.PLAY_PROMPT, {"prompt_key": "ERROR_MSG", "language": ctx.language}),
        Action(ActionType.HANGUP, {"reason": "unhandled_transition"}),
    ], ctx
