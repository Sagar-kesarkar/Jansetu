"""Provider-agnostic IVR Call-Flow Adapter for JanSetu.

Connects telephony webhooks (Twilio, Exotel, Asterisk, or HTTP Simulator)
to the pure conversation state machine (`state.py`) and pipeline (`ingest`).

Features:
- Handles DTMF keypresses, audio recordings, timeouts, and hangup events.
- Formats call actions into Simulator JSON, Twilio TwiML XML, and Exotel JSON.
- Strictly pseudonymises the caller's phone number before persisting in sessions.
- Mid-call drop safety: no database write occurs until the caller confirms the complaint & location.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.channels.prompts import get_prompt_text, spell_docket_digits
from app.channels.session import (
    get_context_dict,
    get_or_create_session,
    update_session,
)
from app.channels.state import (
    CAPABILITIES,
    Action,
    ActionType,
    AudioRecordedEvent,
    CallStartEvent,
    ChannelCapabilities,
    ChannelType,
    ComplaintExtractedEvent,
    ConversationContext,
    ConversationState,
    DtmfEvent,
    Event,
    HangupEvent,
    IngestFailureEvent,
    IngestSuccessEvent,
    LocationResolvedEvent,
    NoInputEvent,
    TextReceivedEvent,
    TimeoutEvent,
    TrackQueryResultEvent,
    transition,
)
from app.config import get_settings
from app.models.schemas import (
    Channel,
    Classification,
    ExtractedIssue,
    ExtractedRequest,
    ExtractedSubmission,
    IntakeEnvelope,
    IntakeResult,
    LocationHierarchy,
    RequestStatus,
)
from app.services.geocode import resolve_district
from app.services.place import district_label, probes, sanitise
from app.services.pipeline import ingest_submission
from app.services.privacy import pseudonymise
from app.services.speech import transcribe
from app.services.tracking import citizen_reference, find_request

log = logging.getLogger(__name__)


@dataclass
class IVRStepResult:
    next_state: str
    language: str
    prompts_to_play: list[dict[str, str]]  # list of {prompt_key, text, audio_url}
    digits_to_spell: list[str]
    gather_dtmf: dict[str, Any] | None
    record_audio: dict[str, Any] | None
    hangup: bool
    hangup_reason: str | None
    request_id: int | None = None
    docket_ref: str | None = None
    registered_tokens: list[str] = field(default_factory=list)
    complaint_preview: str | None = None
    location_preview: str | None = None
    track_result: dict[str, Any] | None = None
    sms_result: dict[str, Any] | None = None
    raw_actions: list[Action] | None = None


class IVRAdapter:
    def __init__(self, db: Session, capabilities: ChannelCapabilities | None = None) -> None:
        self.db = db
        self.capabilities = capabilities or CAPABILITIES[ChannelType.IVR]

    def _extract_complaint_intel(
        self,
        *,
        text: str | None,
        audio_bytes: bytes | None,
        audio_mime: str,
        language: str,
    ) -> ComplaintExtractedEvent:
        """Process spoken or typed complaint description through Gemini or deterministic fallback."""
        transcript: str | None = None
        if audio_bytes and len(audio_bytes) > 0:
            try:
                transcript = transcribe(audio_bytes, language=language, mime_type=audio_mime)
            except Exception as exc:
                log.warning("Audio transcription error in IVR: %s", exc)

        content = transcript or text or ""
        if not content:
            content = "गाँव में पानी की समस्या है" if language == "hi" else "Local water supply issue"

        try:
            from app.services.gemini import extract_submission
            submission: ExtractedSubmission = extract_submission(content, language=language)
            issues = submission.issues or []
            if issues:
                first_issue = issues[0]
                summary = first_issue.summary_native or first_issue.summary_en or content[:60]
                category = first_issue.category or "OTHER"
                urgency = first_issue.urgency or 2
                loc_txt = submission.shared_location_text or first_issue.location_text
            else:
                summary = content[:60]
                category = "OTHER"
                urgency = 2
                loc_txt = None

            return ComplaintExtractedEvent(
                original_text=content,
                summary=summary,
                category=category,
                urgency=urgency,
                detected_location=loc_txt,
                is_valid_civic_request=(submission.classification is not Classification.INVALID_OR_SPAM),
                issues=[i.model_dump() for i in issues],
            )
        except Exception as exc:
            log.warning("Gemini extraction fallback for IVR: %s", exc)
            # Deterministic local fallback
            from app.i18n.keywords import classify
            kw_cat, kw_urg = classify(content, language)
            return ComplaintExtractedEvent(
                original_text=content,
                summary=content[:60],
                category=kw_cat or "OTHER",
                urgency=kw_urg or 2,
                detected_location=None,
                is_valid_civic_request=True,
                issues=[{"title": content[:40], "category": kw_cat or "OTHER", "urgency": kw_urg or 2}],
            )

    def _resolve_location_intel(
        self,
        *,
        text: str | None,
        audio_bytes: bytes | None,
        audio_mime: str,
        language: str,
    ) -> LocationResolvedEvent:
        """Resolve spoken or typed location via geocoding & LGD district mappings."""
        transcript: str | None = None
        if audio_bytes and len(audio_bytes) > 0:
            try:
                transcript = transcribe(audio_bytes, language=language, mime_type=audio_mime)
            except Exception as exc:
                log.warning("Location transcription error: %s", exc)

        raw_loc = (transcript or text or "").strip()
        if not raw_loc:
            return LocationResolvedEvent(
                resolved=False,
                missing_fields=["state", "district", "locality"],
                clarification_message=get_prompt_text("LOCATION_CLARIFICATION", language),
            )

        geo = resolve_district(self.db, raw_loc)
        if geo.district_code is not None and geo.state and geo.district:
            locality_cand = raw_loc.split(",")[0].strip() if "," in raw_loc else raw_loc
            return LocationResolvedEvent(
                resolved=True,
                state=geo.state,
                district=geo.district,
                locality=locality_cand,
                location_text=f"{locality_cand}, {geo.district}, {geo.state}",
            )

        # Fallback: check if the string contains a known state or district
        attempts = probes(sanitise(LocationHierarchy()), fallback=raw_loc)
        for cand in attempts:
            sub_geo = resolve_district(self.db, cand)
            if sub_geo.district_code is not None and sub_geo.state and sub_geo.district:
                return LocationResolvedEvent(
                    resolved=True,
                    state=sub_geo.state,
                    district=sub_geo.district,
                    locality=raw_loc,
                    location_text=f"{raw_loc}, {sub_geo.district}, {sub_geo.state}",
                )

        # If location could not be verified
        return LocationResolvedEvent(
            resolved=False,
            location_text=raw_loc,
            missing_fields=["district", "state"],
            clarification_message=get_prompt_text("LOCATION_CLARIFICATION", language),
        )

    def handle_event(
        self,
        caller_phone: str,
        event: Event,
    ) -> IVRStepResult:
        """Process an IVR event through the state machine and execute required side-effects."""
        if caller_phone and caller_phone.startswith("anon_"):
            safe_ref = caller_phone
        else:
            safe_ref = pseudonymise(caller_phone) or "anon_unknown"

        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

        # 1. Load or initialize channel session
        session = get_or_create_session(self.db, safe_ref, channel="ivr")
        is_expired = False
        if session.updated_at and not isinstance(event, CallStartEvent):
            if (now - session.updated_at).total_seconds() > 1800:
                is_expired = True

        if is_expired:
            current_state = ConversationState.TIMED_OUT
            context = ConversationContext(language=session.language or "hi")
        elif isinstance(event, CallStartEvent) or session.current_state in ("ENDED", "COMPLETED", "TIMED_OUT", "ERROR"):
            current_state = ConversationState.INITIAL
            context = ConversationContext(language=session.language or "hi")
        else:
            try:
                current_state = ConversationState(session.current_state)
            except Exception:
                current_state = ConversationState.INITIAL
            ctx_dict = get_context_dict(session)
            context = ConversationContext(
                language=session.language or "hi",
                attempts=ctx_dict.get("attempts", 0),
                max_attempts=ctx_dict.get("max_attempts", 3),
                request_id=ctx_dict.get("request_id"),
                docket_ref=ctx_dict.get("docket_ref"),
                acknowledgement_native=ctx_dict.get("acknowledgement_native"),
                complaint_text=ctx_dict.get("complaint_text"),
                complaint_summary=ctx_dict.get("complaint_summary"),
                category=ctx_dict.get("category"),
                urgency=ctx_dict.get("urgency", 1),
                location_text=ctx_dict.get("location_text"),
                loc_state=ctx_dict.get("loc_state"),
                loc_district=ctx_dict.get("loc_district"),
                loc_locality=ctx_dict.get("loc_locality"),
                registered_tokens=ctx_dict.get("registered_tokens", []),
                tracking_token_candidate=ctx_dict.get("tracking_token_candidate"),
                track_result=ctx_dict.get("track_result"),
                meta=ctx_dict.get("meta", {}),
            )

        # 2. State Machine Transition
        next_state, actions, new_context = transition(
            current_state=current_state,
            event=event,
            context=context,
            capabilities=self.capabilities,
        )

        # 3. Handle Side-Effects
        final_actions = list(actions)
        sms_result = None

        # Check for TRIGGER_INGEST action
        ingest_action = next((a for a in actions if a.type == ActionType.TRIGGER_INGEST), None)
        if ingest_action:
            payload = ingest_action.payload
            step_type = payload.get("step", "")

            if step_type == "extract_complaint":
                extract_res = self._extract_complaint_intel(
                    text=payload.get("text"),
                    audio_bytes=payload.get("audio_bytes"),
                    audio_mime=payload.get("audio_mime", "audio/wav"),
                    language=new_context.language,
                )
                next_state, post_actions, new_context = transition(
                    current_state=ConversationState.COMPLAINT_PROCESSING,
                    event=extract_res,
                    context=new_context,
                    capabilities=self.capabilities,
                )
                final_actions = post_actions

            elif step_type == "resolve_location":
                loc_res = self._resolve_location_intel(
                    text=payload.get("text"),
                    audio_bytes=payload.get("audio_bytes"),
                    audio_mime=payload.get("audio_mime", "audio/wav"),
                    language=new_context.language,
                )
                next_state, post_actions, new_context = transition(
                    current_state=ConversationState.LOCATION_PROCESSING,
                    event=loc_res,
                    context=new_context,
                    capabilities=self.capabilities,
                )
                final_actions = post_actions

            elif step_type == "register_complaint" or not step_type:
                # Registration Idempotency Check: if token already generated, return cached token without duplicate DB row
                if new_context.docket_ref and new_context.registered_tokens:
                    log.info("Idempotent registration replay: returning existing token %s", new_context.docket_ref)
                    ingest_success = IngestSuccessEvent(
                        request_id=new_context.request_id or 1,
                        category=new_context.category or "OTHER",
                        district=new_context.loc_district,
                        state=new_context.loc_state,
                        urgency=new_context.urgency,
                        acknowledgement_native=new_context.acknowledgement_native or "",
                        docket_ref=new_context.docket_ref,
                        language=new_context.language,
                        tokens=new_context.registered_tokens,
                    )
                    target_state = (
                        ConversationState.PROCESSING
                        if (current_state == ConversationState.PROCESSING or next_state == ConversationState.PROCESSING)
                        else ConversationState.REGISTERING
                    )
                    next_state, post_actions, new_context = transition(
                        current_state=target_state,
                        event=ingest_success,
                        context=new_context,
                        capabilities=self.capabilities,
                    )
                    final_actions = post_actions
                else:
                    # Real complaint registration in the database
                    try:
                        envelope: IntakeEnvelope = ingest_submission(
                            self.db,
                            text=new_context.complaint_text or payload.get("text"),
                            language=new_context.language,
                            location_text=new_context.location_text or payload.get("location_text"),
                            channel=Channel.IVR,
                            citizen_ref=caller_phone,
                        )

                        all_tokens = [r.track_token for r in envelope.requests if r.track_token]
                        if not all_tokens and envelope.track_token:
                            all_tokens = [envelope.track_token]

                        ingest_success = IngestSuccessEvent(
                            request_id=envelope.request_id,
                            category=envelope.category,
                            district=envelope.district,
                            state=envelope.state,
                            urgency=envelope.urgency,
                            acknowledgement_native=envelope.acknowledgement_native,
                            docket_ref=citizen_reference(envelope.track_token, envelope.request_id),
                            language=envelope.language,
                            tokens=all_tokens,
                            issue_summaries=[r.summary_en for r in envelope.requests if r.summary_en],
                        )

                        target_state = (
                            ConversationState.PROCESSING
                            if (current_state == ConversationState.PROCESSING or next_state == ConversationState.PROCESSING)
                            else ConversationState.REGISTERING
                        )
                        next_state, post_actions, new_context = transition(
                            current_state=target_state,
                            event=ingest_success,
                            context=new_context,
                            capabilities=self.capabilities,
                        )
                        final_actions = post_actions
                    except Exception as exc:
                        log.exception("IVR complaint registration failed: %s", exc)
                        fail_event = IngestFailureEvent(error=str(exc))
                        target_state = (
                            ConversationState.PROCESSING
                            if (current_state == ConversationState.PROCESSING or next_state == ConversationState.PROCESSING)
                            else ConversationState.REGISTERING
                        )
                        next_state, post_actions, new_context = transition(
                            current_state=target_state,
                            event=fail_event,
                            context=new_context,
                            capabilities=self.capabilities,
                        )
                        final_actions = post_actions

        # Check for QUERY_TRACKING action
        query_action = next((a for a in actions if a.type == ActionType.QUERY_TRACKING), None)
        if query_action:
            token_to_check = query_action.payload.get("token", "")
            found_row = find_request(self.db, token_to_check)
            if found_row:
                track_evt = TrackQueryResultEvent(
                    found=True,
                    token=found_row.track_token or token_to_check,
                    status=found_row.status,
                    department=found_row.category,
                    updated_at=str(found_row.created_at)[:16] if found_row.created_at else "Recently",
                    district=found_row.loc_district,
                    state=found_row.loc_state,
                )
            else:
                track_evt = TrackQueryResultEvent(found=False, token=token_to_check)

            next_state, post_actions, new_context = transition(
                current_state=ConversationState.TRACK_PROCESSING,
                event=track_evt,
                context=new_context,
                capabilities=self.capabilities,
            )
            final_actions = post_actions

        # Check for SEND_SMS action
        sms_action = next((a for a in actions if a.type == ActionType.SEND_SMS), None)
        if sms_action:
            sms_payload = sms_action.payload
            sms_type = sms_payload.get("type", "notification")
            token_val = sms_payload.get("token") or new_context.docket_ref or "JS-SAMPLE"
            sms_result = {
                "status": "sent",
                "type": sms_type,
                "token": token_val,
                "link": f"/track/{token_val}" if sms_type != "public_funds_link" else f"/public-funds?lang={new_context.language}",
                "simulated": True,
            }

        # 4. Persist updated session
        created_time = session.created_at or datetime.datetime.utcnow()
        expires_time = created_time + datetime.timedelta(minutes=30)
        idempotency_key = f"ivr_reg_{safe_ref}_{new_context.complaint_text}_{new_context.location_text}"

        update_session(
            self.db,
            session,
            new_state=next_state.value,
            language=new_context.language,
            context_data={
                "session_id": safe_ref,
                "anonymous_reporter_id": safe_ref,
                "selected_language": new_context.language,
                "current_state": next_state.value,
                "previous_state": current_state.value,
                "operating_mode": new_context.meta.get("mode", "live"),
                "retry_counts": {"attempts": new_context.attempts, "max_attempts": new_context.max_attempts},
                "pending_complaint": {
                    "text": new_context.complaint_text,
                    "summary": new_context.complaint_summary,
                    "category": new_context.category,
                    "urgency": new_context.urgency,
                },
                "pending_location": {
                    "location_text": new_context.location_text,
                    "loc_state": new_context.loc_state,
                    "loc_district": new_context.loc_district,
                    "loc_locality": new_context.loc_locality,
                },
                "registered_tokens": new_context.registered_tokens,
                "idempotency_key": idempotency_key,
                "created_at": created_time.isoformat(),
                "updated_at": now.isoformat(),
                "expires_at": expires_time.isoformat(),
                "attempts": new_context.attempts,
                "request_id": new_context.request_id,
                "docket_ref": new_context.docket_ref,
                "acknowledgement_native": new_context.acknowledgement_native,
                "complaint_text": new_context.complaint_text,
                "complaint_summary": new_context.complaint_summary,
                "category": new_context.category,
                "urgency": new_context.urgency,
                "location_text": new_context.location_text,
                "loc_state": new_context.loc_state,
                "loc_district": new_context.loc_district,
                "loc_locality": new_context.loc_locality,
                "tracking_token_candidate": new_context.tracking_token_candidate,
                "track_result": new_context.track_result,
            },
        )

        # 5. Format Step Result for Handset & Telephony
        prompts_to_play: list[dict[str, str]] = []
        digits_to_spell: list[str] = []
        gather_dtmf: dict[str, Any] | None = None
        record_audio: dict[str, Any] | None = None
        hangup = False
        hangup_reason = None

        for act in final_actions:
            if act.type == ActionType.PLAY_PROMPT:
                pkey = act.payload.get("prompt_key", "")
                plang = act.payload.get("language", new_context.language)
                kwargs = {k: v for k, v in act.payload.items() if k not in ("prompt_key", "language")}
                text = get_prompt_text(pkey, plang, **kwargs)
                audio_url = f"/ivr/prompts/{plang}/{pkey}.wav"
                prompts_to_play.append({"prompt_key": pkey, "text": text, "audio_url": audio_url})

            elif act.type == ActionType.SPELL_OUT_DIGITS:
                raw_digits = act.payload.get("digits", "")
                plang = act.payload.get("language", new_context.language)
                spoken_words = spell_docket_digits(raw_digits, plang)
                digits_to_spell = spoken_words

            elif act.type == ActionType.GATHER_DTMF:
                gather_dtmf = act.payload

            elif act.type == ActionType.RECORD_AUDIO:
                record_audio = act.payload

            elif act.type == ActionType.HANGUP:
                hangup = True
                hangup_reason = act.payload.get("reason", "normal_clearing")

        return IVRStepResult(
            next_state=next_state.value,
            language=new_context.language,
            prompts_to_play=prompts_to_play,
            digits_to_spell=digits_to_spell,
            gather_dtmf=gather_dtmf,
            record_audio=record_audio,
            hangup=hangup,
            hangup_reason=hangup_reason,
            request_id=new_context.request_id,
            docket_ref=new_context.docket_ref,
            registered_tokens=new_context.registered_tokens,
            complaint_preview=new_context.complaint_summary or new_context.complaint_text,
            location_preview=new_context.location_text,
            track_result=new_context.track_result,
            sms_result=sms_result,
            raw_actions=final_actions,
        )

    def to_twiml(self, step_result: IVRStepResult, action_url: str = "/ivr/webhook") -> str:
        """Render IVRStepResult as valid Twilio TwiML XML."""
        xml = ['<?xml version="1.0" encoding="UTF-8"?>', "<Response>"]

        if step_result.gather_dtmf:
            num_digits = step_result.gather_dtmf.get("num_digits", 1)
            timeout = step_result.gather_dtmf.get("timeout_sec", 10)
            xml.append(f'  <Gather numDigits="{num_digits}" timeout="{timeout}" action="{action_url}" method="POST">')
            for p in step_result.prompts_to_play:
                xml.append(f'    <Play>{p["audio_url"]}</Play>')
            xml.append("  </Gather>")
        else:
            for p in step_result.prompts_to_play:
                xml.append(f'  <Play>{p["audio_url"]}</Play>')

        if step_result.digits_to_spell:
            digits_str = ", ".join(step_result.digits_to_spell)
            xml.append(f'  <Say language="{step_result.language}">{digits_str}</Say>')

        if step_result.record_audio:
            max_dur = step_result.record_audio.get("max_duration_sec", 60)
            beep = "true" if step_result.record_audio.get("beep", True) else "false"
            xml.append(f'  <Record maxLength="{max_dur}" playBeep="{beep}" action="{action_url}" finishOnKey="#" />')

        if step_result.hangup:
            xml.append("  <Hangup/>")

        xml.append("</Response>")
        return "\n".join(xml)

    def to_exotel_response(self, step_result: IVRStepResult) -> dict[str, Any]:
        """Render IVRStepResult as Exotel passthru response dict."""
        return {
            "select": "gather" if step_result.gather_dtmf else "play",
            "state": step_result.next_state,
            "language": step_result.language,
            "prompts": [p["audio_url"] for p in step_result.prompts_to_play],
            "digits_spoken": step_result.digits_to_spell,
            "record": bool(step_result.record_audio),
            "hangup": step_result.hangup,
            "request_id": step_result.request_id,
            "docket_ref": step_result.docket_ref,
            "registered_tokens": step_result.registered_tokens,
        }
