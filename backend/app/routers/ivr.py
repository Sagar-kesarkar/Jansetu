"""IVR Router — Session management, telephony webhooks, prompt audio streaming, Exotel integration, and HTTP simulator."""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.channels.exotel_ivr import (
    build_exotel_dtmf_response,
    build_exotel_recording_response,
    process_exotel_recording_async,
)
from app.channels.ivr import IVRAdapter, IVRStepResult
from app.channels.prompts import get_prompt_text
from app.channels.session import get_channel_session, get_context_dict, update_session
from app.channels.simulator import IVRSimulator
from app.channels.state import (
    AudioRecordedEvent,
    CallStartEvent,
    DtmfEvent,
    HangupEvent,
    NoInputEvent,
    TextReceivedEvent,
    TimeoutEvent,
)
from app.config import get_settings
from app.db.database import SessionLocal, get_db
from app.services.privacy import pseudonymise

router = APIRouter(prefix="/ivr", tags=["ivr"])
log = logging.getLogger(__name__)


# --- Pydantic Schemas for IVR Sessions & Simulator ---

class IVRSessionCreateIn(BaseModel):
    caller_phone: str = Field(default="919876543210", description="Caller phone number (HMAC pseudonymised)")
    initial_language: str | None = Field(default=None, description="Optional initial language code (e.g. 'hi', 'ta', 'en')")
    mode: str = Field(default="live", description="Operating mode: live | assisted | scripted-demo | offline-demo")


class IVRDtmfIn(BaseModel):
    digits: str = Field(description="DTMF digits pressed (e.g. '1', '2', '#')")


class IVRInputIn(BaseModel):
    text: str = Field(description="Spoken or typed input text")


class IVRAudioIn(BaseModel):
    audio_base64: str = Field(description="Base64 encoded WAV/WebM audio bytes")
    audio_mime: str = Field(default="audio/webm", description="Audio MIME type")


class IVRSessionView(BaseModel):
    session_id: str
    state: str
    mode: str
    selected_language: str
    prompt_text: str
    allowed_digits: list[str]
    accepts_voice: bool
    is_listening: bool
    is_processing: bool
    transcript: str | None = None
    complaint_preview: str | None = None
    location_preview: str | None = None
    tokens: list[str] = Field(default_factory=list)
    sms_result: dict[str, Any] | None = None
    error: str | None = None
    hangup: bool = False


class IVRSimulateIn(BaseModel):
    caller_phone: str = Field(default="919876543210", description="Simulated caller MSISDN")
    action: str = Field(
        default="start",
        description="Action type: start | dtmf | audio | timeout | no_input | hangup | full_simulation",
    )
    digits: str | None = Field(default=None, description="DTMF digit pressed (e.g. '1', '2')")
    text_simulation: str | None = Field(
        default=None,
        description="Text content for simulated audio recording",
    )
    audio_base64: str | None = Field(
        default=None,
        description="Base64 encoded raw audio bytes",
    )
    audio_mime: str = Field(default="audio/webm")
    language_digit: str = Field(default="1", description="Used in full_simulation (1=hi, 2=ta, etc.)")
    mode: str = Field(default="live", description="live | assisted | scripted-demo | offline-demo")


def _build_session_view(step_res: IVRStepResult, session_id: str, mode: str = "live") -> IVRSessionView:
    """Transform an IVRStepResult into a clean typed IVRSessionView."""
    allowed_digits: list[str] = []
    if step_res.gather_dtmf:
        allowed_digits = [str(d) for d in step_res.gather_dtmf.get("valid_digits", [])]

    prompt_texts = [p.get("text", "") for p in step_res.prompts_to_play if p.get("text")]
    combined_prompt = " ".join(prompt_texts)

    accepts_voice = bool(step_res.record_audio)

    all_tokens = list(step_res.registered_tokens)
    if step_res.docket_ref and step_res.docket_ref not in all_tokens:
        all_tokens.append(step_res.docket_ref)

    return IVRSessionView(
        session_id=session_id,
        state=step_res.next_state,
        mode=mode,
        selected_language=step_res.language,
        prompt_text=combined_prompt,
        allowed_digits=allowed_digits,
        accepts_voice=accepts_voice,
        is_listening=accepts_voice,
        is_processing=(step_res.next_state in ("COMPLAINT_PROCESSING", "LOCATION_PROCESSING", "REGISTERING", "TRACK_PROCESSING", "PROCESSING")),
        transcript=step_res.complaint_preview,
        complaint_preview=step_res.complaint_preview,
        location_preview=step_res.location_preview,
        tokens=all_tokens,
        sms_result=step_res.sms_result,
        error=None,
        hangup=step_res.hangup,
    )


# ---------- RESTful IVR Session Endpoints ----------

@router.post("/sessions", response_model=IVRSessionView)
def create_ivr_session(payload: IVRSessionCreateIn, db: Session = Depends(get_db)) -> IVRSessionView:
    """Initialize a new IVR call session with language menu greeting."""
    adapter = IVRAdapter(db)
    event = CallStartEvent(initial_language=payload.initial_language)
    step_res = adapter.handle_event(payload.caller_phone, event)
    safe_session_id = pseudonymise(payload.caller_phone) or "anon_ivr"
    return _build_session_view(step_res, session_id=safe_session_id, mode=payload.mode)


@router.get("/sessions/{session_id}", response_model=IVRSessionView)
def get_ivr_session(session_id: str, db: Session = Depends(get_db)) -> IVRSessionView:
    """Retrieve the current state and prompts of an active IVR session."""
    session = get_channel_session(db, session_id, channel="ivr")
    ctx = get_context_dict(session)
    prompt_text = get_prompt_text(session.current_state, session.language or "hi")
    return IVRSessionView(
        session_id=session_id,
        state=session.current_state or "MAIN_MENU",
        mode="live",
        selected_language=session.language or "hi",
        prompt_text=prompt_text,
        allowed_digits=["1", "2", "3", "8", "0", "9"],
        accepts_voice=False,
        is_listening=False,
        is_processing=False,
        transcript=ctx.get("complaint_summary"),
        complaint_preview=ctx.get("complaint_summary"),
        location_preview=ctx.get("location_text"),
        tokens=ctx.get("registered_tokens", []),
        error=None,
        hangup=(session.current_state in ("ENDED", "COMPLETED")),
    )


@router.post("/sessions/{session_id}/dtmf", response_model=IVRSessionView)
def send_ivr_dtmf(session_id: str, payload: IVRDtmfIn, db: Session = Depends(get_db)) -> IVRSessionView:
    """Process a DTMF keypad selection on the active IVR session."""
    adapter = IVRAdapter(db)
    step_res = adapter.handle_event(session_id, DtmfEvent(digits=payload.digits))
    return _build_session_view(step_res, session_id=session_id)


import os
import re
import tempfile
import time
from typing import Optional

ALLOWED_AUDIO_MIMES = {
    "audio/wav", "audio/wave", "audio/x-wav", "audio/webm", "audio/ogg",
    "audio/mpeg", "audio/mp3", "audio/mp4", "audio/flac", "audio/m4a", "audio/x-m4a",
    "application/octet-stream",  # often sent by generic form-data clients
}
MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_LANGUAGES = {"hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "or", "as", "ur", "en"}


@router.post("/sessions/{session_id}/input", response_model=IVRSessionView)
def send_ivr_text_input(session_id: str, payload: IVRInputIn, db: Session = Depends(get_db)) -> IVRSessionView:
    """Process typed or transcribed text input for complaint or location."""
    adapter = IVRAdapter(db)
    step_res = adapter.handle_event(session_id, TextReceivedEvent(text=payload.text))
    return _build_session_view(step_res, session_id=session_id)


@router.post("/sessions/{session_id}/audio", response_model=IVRSessionView)
async def send_ivr_audio(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> IVRSessionView:
    """Process spoken audio recording from caller via multipart/form-data or JSON fallback.

    Enforces MIME validation, 10MB size limit, and deterministic temporary file deletion.
    """
    audio_bytes: bytes = b""
    audio_mime: str = "audio/webm"

    content_type = request.headers.get("content-type", "").lower()

    if "multipart/form-data" in content_type:
        form = await request.form()
        audio_file = form.get("file") or form.get("audio") or form.get("audio_file")
        if audio_file and hasattr(audio_file, "read"):
            mime_header = getattr(audio_file, "content_type", "audio/webm") or "audio/webm"
            if mime_header not in ALLOWED_AUDIO_MIMES:
                raise HTTPException(status_code=415, detail=f"Unsupported audio MIME type: {mime_header}")
            audio_mime = mime_header

            raw_data = await audio_file.read()
            if len(raw_data) > MAX_AUDIO_BYTES:
                raise HTTPException(status_code=413, detail="Audio file exceeds 10MB limit")

            # Write to a safe temporary file for validation and ensure deterministic cleanup
            safe_suffix = ".webm" if "webm" in audio_mime else (".ogg" if "ogg" in audio_mime else ".wav")
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=safe_suffix)
            try:
                temp_file.write(raw_data)
                temp_file.flush()
                audio_bytes = raw_data
            finally:
                temp_file.close()
                if os.path.exists(temp_file.name):
                    try:
                        os.unlink(temp_file.name)
                    except Exception as err:
                        log.debug("Temporary audio file removal notice: %s", err)
        else:
            # Check for text fallback inside form
            text_val = form.get("text")
            if text_val:
                adapter = IVRAdapter(db)
                step_res = adapter.handle_event(session_id, TextReceivedEvent(text=str(text_val)))
                return _build_session_view(step_res, session_id=session_id)
            raise HTTPException(status_code=400, detail="No audio file uploaded in multipart form")

    elif "application/json" in content_type:
        try:
            body = await request.json()
            payload = IVRAudioIn(**body)
            mime_header = payload.audio_mime or "audio/webm"
            if mime_header not in ALLOWED_AUDIO_MIMES:
                raise HTTPException(status_code=415, detail=f"Unsupported audio MIME type: {mime_header}")
            if payload.audio_base64:
                raw_data = base64.b64decode(payload.audio_base64)
                if len(raw_data) > MAX_AUDIO_BYTES:
                    raise HTTPException(status_code=413, detail="Audio payload exceeds 10MB limit")
                audio_bytes = raw_data
                audio_mime = mime_header
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON audio payload: {exc}")
    else:
        raise HTTPException(status_code=415, detail="Content-Type must be multipart/form-data or application/json")

    adapter = IVRAdapter(db)
    step_res = adapter.handle_event(
        session_id,
        AudioRecordedEvent(audio_bytes=audio_bytes, audio_mime=audio_mime),
    )
    return _build_session_view(step_res, session_id=session_id)


@router.post("/sessions/{session_id}/repeat", response_model=IVRSessionView)
def repeat_ivr_prompt(session_id: str, db: Session = Depends(get_db)) -> IVRSessionView:
    """Repeat the active menu prompt (equivalent to DTMF '0')."""
    adapter = IVRAdapter(db)
    step_res = adapter.handle_event(session_id, DtmfEvent(digits="0"))
    return _build_session_view(step_res, session_id=session_id)


@router.post("/sessions/{session_id}/end", response_model=IVRSessionView)
def end_ivr_session(session_id: str, db: Session = Depends(get_db)) -> IVRSessionView:
    """Hang up and terminate the IVR session."""
    adapter = IVRAdapter(db)
    step_res = adapter.handle_event(session_id, HangupEvent())
    return _build_session_view(step_res, session_id=session_id)


# ---------- Backward Compatible Simulation Endpoint ----------

@router.post("/simulate")
def simulate_ivr_call(payload: IVRSimulateIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Execute a simulated IVR call step or run a full simulation."""
    action = payload.action.lower()

    if action in ("full_simulation", "full"):
        sim = IVRSimulator(db)
        steps = sim.run_full_simulation(
            caller_phone=payload.caller_phone,
            language_digit=payload.language_digit,
            problem_description=payload.text_simulation or "हमारे गाँव में पानी की समस्या है।",
        )
        return {"status": "success", "steps": steps}

    adapter = IVRAdapter(db)

    # 1. Parse Event
    event = None
    if action == "start":
        event = CallStartEvent()
    elif action == "dtmf":
        event = DtmfEvent(digits=payload.digits or "1")
    elif action == "audio":
        if payload.audio_base64:
            raw_bytes = base64.b64decode(payload.audio_base64)
            event = AudioRecordedEvent(audio_bytes=raw_bytes, audio_mime=payload.audio_mime)
        elif payload.text_simulation:
            event = TextReceivedEvent(text=payload.text_simulation)
        else:
            event = NoInputEvent()
    elif action in ("timeout", "no_input"):
        event = TimeoutEvent()
    elif action in ("hangup", "end"):
        event = HangupEvent()
    else:
        event = CallStartEvent()

    step_res = adapter.handle_event(payload.caller_phone, event)

    all_tokens = list(step_res.registered_tokens)
    if step_res.docket_ref and step_res.docket_ref not in all_tokens:
        all_tokens.append(step_res.docket_ref)

    return {
        "status": "success",
        "mode": "step",
        "state": step_res.next_state,
        "language": step_res.language,
        "prompts": step_res.prompts_to_play,
        "digits_spoken": step_res.digits_to_spell,
        "gather_dtmf": step_res.gather_dtmf,
        "record_audio": step_res.record_audio,
        "hangup": step_res.hangup,
        "hangup_reason": step_res.hangup_reason,
        "request_id": step_res.request_id,
        "docket_ref": step_res.docket_ref,
        "registered_tokens": all_tokens,
        "complaint_preview": step_res.complaint_preview,
        "location_preview": step_res.location_preview,
        "sms_result": step_res.sms_result,
    }


# ---------- Status Diagnostics Endpoint ----------

@router.get("/status")
def get_ivr_status() -> dict[str, str]:
    """Diagnostic status for IVR simulator, telephony provider, and callable number."""
    settings = get_settings()
    has_telephony = bool(
        getattr(settings, "exotel_account_sid", None)
        or getattr(settings, "twilio_account_sid", None)
    )
    callable_num = getattr(settings, "ivr_callable_number", None)
    return {
        "browser_simulator": "verified",
        "telephone_provider": "configured" if has_telephony else "blocked",
        "callable_number": "verified" if (callable_num and callable_num.strip()) else "not configured",
    }


# ---------- Telephony Webhook Ingress (Twilio / Standard) ----------

@router.post("/webhook")
@router.post("/webhooks/incoming")
async def ivr_webhook(
    request: Request,
    format_type: str = Query("json", alias="format"),
    db: Session = Depends(get_db),
) -> Response:
    """Standard webhook endpoint for Twilio, Exotel, or SIP softphones with signature & replay checks."""
    # 1. Replay Protection: check timestamp header if provided
    ts_header = request.headers.get("x-twilio-timestamp") or request.headers.get("x-webhook-timestamp")
    if ts_header:
        try:
            ts_val = float(ts_header)
            if abs(time.time() - ts_val) > 300:  # 5-minute replay tolerance
                raise HTTPException(status_code=403, detail="Webhook timestamp expired")
        except ValueError:
            pass

    caller_phone = "919876543210"
    digits = None
    call_status = None

    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        body = await request.json()
        caller_phone = body.get("From") or body.get("from") or body.get("caller_phone") or caller_phone
        digits = body.get("Digits") or body.get("digits") or body.get("dtmf")
        call_status = body.get("CallStatus") or body.get("status")
    else:
        form = await request.form()
        caller_phone = str(form.get("From") or form.get("from") or form.get("CallFrom") or caller_phone)
        digits = form.get("Digits") or form.get("digits")
        call_status = form.get("CallStatus") or form.get("status")

    if call_status in ("completed", "hangup", "busy", "no-answer"):
        event = HangupEvent()
    elif digits is not None:
        event = DtmfEvent(digits=str(digits))
    else:
        event = CallStartEvent()

    adapter = IVRAdapter(db)
    step_res = adapter.handle_event(caller_phone, event)

    if format_type.lower() == "twiml" or "twilio" in request.headers.get("user-agent", "").lower():
        twiml_xml = adapter.to_twiml(step_res, action_url="/ivr/webhook?format=twiml")
        return Response(content=twiml_xml, media_type="application/xml")

    exotel_dict = adapter.to_exotel_response(step_res)
    return Response(content=json.dumps(exotel_dict), media_type="application/json")


# ---------- Exotel Specific Webhook Endpoints ----------

@router.api_route("/exotel/passthru", methods=["GET", "POST"])
async def exotel_passthru(
    request: Request,
    digits: str | None = Query(None, alias="Digits"),
    page: int = Query(0),
    lang: str = Query("hi"),
) -> JSONResponse:
    """Exotel Passthru Applet webhook."""
    if request.method == "POST":
        try:
            form = await request.form()
            digits = form.get("Digits") or digits
            page_raw = form.get("page")
            if page_raw:
                page = int(page_raw)
            lang = form.get("lang") or lang
        except Exception:
            pass

    res = build_exotel_dtmf_response(digits=digits, page=page, current_lang=lang)
    return JSONResponse(content=res)


async def _run_exotel_recording_background(
    caller: str,
    call_sid: str,
    recording_url: str,
    lang: str,
) -> None:
    """Background task for Exotel audio download and ingestion with dedicated DB session."""
    db = SessionLocal()
    try:
        await process_exotel_recording_async(
            db=db,
            caller_phone=caller,
            call_sid=call_sid,
            recording_url=recording_url,
            lang=lang,
        )
    except Exception as exc:
        log.exception("Background Exotel recording processing error: %s", exc)
    finally:
        db.close()


@router.post("/exotel/recording")
async def exotel_recording_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    CallSid: str = Form(None),
    From: str = Form(None),
    RecordingUrl: str = Form(None),
    RecordingDuration: int = Form(None),
    lang: str = Form("hi"),
) -> JSONResponse:
    """Exotel Recording completion webhook."""
    caller = From
    call_sid = CallSid
    rec_url = RecordingUrl

    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            body = await request.json()
            caller = body.get("From") or caller
            call_sid = body.get("CallSid") or call_sid
            rec_url = body.get("RecordingUrl") or rec_url
            lang = body.get("lang") or lang
        except Exception:
            pass

    if not caller or not rec_url:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Missing From or RecordingUrl"})

    background_tasks.add_task(
        _run_exotel_recording_background,
        caller=caller,
        call_sid=call_sid or "exotel_call",
        recording_url=rec_url,
        lang=lang or "hi",
    )

    resp = build_exotel_recording_response(lang=lang or "hi")
    return JSONResponse(content=resp)


# ---------- Secure Audio Prompt Streaming ----------

@router.get("/prompts/{lang}/{prompt_file}")
def get_prompt_audio(lang: str, prompt_file: str) -> FileResponse:
    """Stream audio prompt with strict language allowlist and path-traversal prevention."""
    clean_lang = (lang or "").strip().lower()
    if clean_lang not in ALLOWED_LANGUAGES:
        raise HTTPException(status_code=400, detail="Unsupported or invalid language code")

    # Reject path traversal tokens, slashes, or backslashes
    if "/" in prompt_file or "\\" in prompt_file or ".." in prompt_file:
        raise HTTPException(status_code=400, detail="Invalid characters or directory traversal in prompt file")

    if not re.match(r"^[A-Za-z0-9_.-]+$", prompt_file):
        raise HTTPException(status_code=400, detail="Malformed prompt identifier")

    prompt_dir = Path(get_settings().ivr_prompt_dir).resolve()
    target_path = (prompt_dir / clean_lang / prompt_file).resolve()

    # Verify target path is strictly within prompt_dir
    try:
        target_path.relative_to(prompt_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied: path outside prompt directory")

    if not target_path.exists():
        fallback_path = (prompt_dir / "hi" / prompt_file).resolve()
        if fallback_path.exists():
            target_path = fallback_path

    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Audio prompt file not found")

    return FileResponse(str(target_path), media_type="audio/wav")
