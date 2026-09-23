"""Citizen-facing intake: voice, text, and messaging apps — the three channels
the track names explicitly.

Every route here answers with an `IntakeEnvelope`, which is an `IntakeResult` with
`classification`, `request_count` and `requests[]` added. One message can raise
several separately actionable problems, and each becomes its own request with its
own token — so the response has to be able to describe more than one. For the
ordinary single-issue case the JSON is unchanged from before splitting existed,
which is why no client needed a version bump: the top level still describes one
request, and `requests[]` simply has one element in it.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.channels.whatsapp import parse_whatsapp_webhook, process_whatsapp_inbound
from app.config import get_settings
from app.db.database import SessionLocal, get_db
from app.models.schemas import Channel, IntakeEnvelope, IntakeTextIn
from app.services.pipeline import ingest

log = logging.getLogger(__name__)

router = APIRouter(prefix="/intake", tags=["intake"])

MAX_AUDIO_BYTES = 10 * 1024 * 1024  # a couple of minutes of webm/opus voice note
MAX_IMAGE_BYTES = 8 * 1024 * 1024   # a phone photo, uncompressed, with headroom

#: Formats Gemini accepts inline. Checked rather than trusted, because an
#: unsupported mime type fails inside the model call as an opaque 400 rather than
#: as something the citizen can be told about.
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


async def _read_image(image: UploadFile | None) -> tuple[bytes | None, str]:
    """Validate and read an optional photograph.

    Returns bytes that are handed to Gemini for a description and then filed by
    `services/evidence.py` under the request's tracking token. The uploaded
    filename is read for nothing — it is attacker-controlled, and the stored name
    is derived from the token instead.
    """
    if image is None:
        return None, "image/jpeg"
    data = await image.read()
    if not data:
        return None, "image/jpeg"
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large; send under 8 MB")
    mime = (image.content_type or "image/jpeg").split(";")[0].strip().lower()
    if mime not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported image type {mime!r}; send JPEG, PNG, WebP or HEIC",
        )
    return data, mime


@router.post("/report", response_model=IntakeEnvelope)
async def intake_report(
    text: str | None = Form(None, description="Citizen's message in their own language"),
    audio: UploadFile | None = File(None, description="Voice note; used if text is absent"),
    image: UploadFile | None = File(None, description="Photograph of the issue. Filed as case evidence."),
    language: str = Form("hi"),
    location_text: str | None = Form(None),
    channel: Channel = Form(Channel.TEXT),
    citizen_ref: str | None = Form(None),
    db: Session = Depends(get_db),
) -> IntakeEnvelope:
    """The full intake: text or voice, in any supported language, plus an optional
    photograph of the problem.

    A separate route rather than an extension of `/text` because a file upload
    needs multipart and `/text` takes JSON — FastAPI cannot serve both content
    types on one path, and changing `/text` would break the citizen web app and
    the WhatsApp handler that already post to it. `/text` and `/voice` remain the
    narrow, well-documented channels; this is the one that carries everything.
    """
    audio_bytes: bytes | None = None
    audio_mime = "audio/webm"
    if audio is not None:
        audio_bytes = await audio.read()
        if audio_bytes and len(audio_bytes) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="Audio too large; send under 10 MB")
        audio_mime = audio.content_type or "audio/webm"
        audio_bytes = audio_bytes or None

    if not text and not audio_bytes:
        raise HTTPException(
            status_code=422,
            detail="Send text, audio, or both. A photograph alone cannot be acted on.",
        )

    image_bytes, image_mime = await _read_image(image)

    # For WhatsApp & SMS messaging channels (live webhooks & simulator handsets), check conversational router
    is_msg_channel = channel in (Channel.WHATSAPP, Channel.SMS, "whatsapp", "sms")
    if is_msg_channel and not audio_bytes and text:
        from app.channels.router import route
        from app.channels.session import get_or_create_session, save_channel_session
        from app.services.privacy import pseudonymise

        safe_ref = pseudonymise(citizen_ref or "sim_handset") or "sim_handset"
        channel_str = "whatsapp" if channel in (Channel.WHATSAPP, "whatsapp") else "sms"
        session = get_or_create_session(db, safe_ref, channel=channel_str)
        ctx = session.get_context() or {}

        decision = route(
            db,
            ctx,
            text,
            default_language=language,
            has_media=bool(image_bytes),
            safe_ref=safe_ref,
            rich=(channel_str == "whatsapp"),
        )
        session.set_context(decision.context)
        save_channel_session(db, session)

        if decision.handled:
            return IntakeEnvelope(
                request_id=0,
                category="OTHER",
                district=None,
                state=None,
                urgency=1,
                transcript=None,
                summary_en="Conversational turn",
                acknowledgement_native=decision.reply or "",
                language=decision.language,
                channel=channel,
                confidence=1.0,
                classification="CONVERSATIONAL",
                citizen_ref=safe_ref,
                request_count=0,
                requests=[],
            )

        if decision.text:
            text = decision.text
        language = decision.language or language

    try:
        return ingest(
            db,
            text=text,
            audio=audio_bytes,
            audio_mime=audio_mime,
            image=image_bytes,
            image_mime=image_mime,
            language=language,
            channel=channel,
            location_text=location_text,
            citizen_ref=citizen_ref,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/text", response_model=IntakeEnvelope)
def intake_text(payload: IntakeTextIn, db: Session = Depends(get_db)) -> IntakeEnvelope:
    try:
        return ingest(
            db,
            text=payload.text,
            language=payload.language,
            channel=payload.channel,
            location_text=payload.location_text,
            citizen_ref=payload.citizen_ref,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/voice", response_model=IntakeEnvelope)
async def intake_voice(
    audio: UploadFile = File(..., description="Recorded audio; container auto-detected"),
    image: UploadFile | None = File(None, description="Optional photograph of the issue"),
    language: str = Form("hi"),
    location_text: str | None = Form(None),
    citizen_ref: str | None = Form(None),
    db: Session = Depends(get_db),
) -> IntakeEnvelope:
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=422, detail="Empty audio upload")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio too large; send under 10 MB")
    image_bytes, image_mime = await _read_image(image)
    try:
        return ingest(
            db,
            audio=data,
            audio_mime=audio.content_type or "audio/webm",
            image=image_bytes,
            image_mime=image_mime,
            language=language,
            channel=Channel.VOICE,
            location_text=location_text,
            citizen_ref=citizen_ref,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/whatsapp", response_class=PlainTextResponse)
def whatsapp_verify(request: Request) -> str:
    """Webhook verification handshake. Kept so the messaging-app channel is real
    rather than claimed — point a WhatsApp Business number here."""
    settings = get_settings()
    params = request.query_params
    if params.get("hub.verify_token") == settings.whatsapp_verify_token:
        return params.get("hub.challenge", "")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/whatsapp")
async def whatsapp_inbound(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Any:
    """Enhanced WhatsApp Cloud API handler for text, voice notes, and photographs.

    Handles:
    - Webhook signature verification (X-Hub-Signature-256) with WHATSAPP_APP_SECRET.
    - Text messages, audio voice notes, and issue photographs.
    - Multi-turn voice + subsequent photo evidence workflow.
    - Webhook deduplication via ChannelEvent to prevent duplicate complaints.
    - Raw phone number passed directly to `ingest` for HMAC pseudonymisation.

    Signature and parse errors are answered synchronously; the download + Gemini
    pipeline runs as a background task so Meta gets a fast acknowledgement.
    """
    import base64
    import json

    raw_body = await request.body()
    settings = get_settings()

    if settings.whatsapp_app_secret:
        sig_header = request.headers.get("x-hub-signature-256")
        from app.channels.whatsapp import validate_whatsapp_signature
        if not validate_whatsapp_signature(raw_body, sig_header, settings.whatsapp_app_secret):
            raise HTTPException(status_code=403, detail="Invalid WhatsApp webhook signature")

    try:
        body = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    msg = parse_whatsapp_webhook(body)

    if msg is None:
        # Fallback for direct minimal payload or unrecognised payload
        try:
            message = body["entry"][0]["changes"][0]["value"]["messages"][0]
            sender = message.get("from")
            text = message.get("text", {}).get("body", "")
            if not text:
                raise HTTPException(status_code=422, detail="Only text, audio, and images handled in this scope")
            return ingest(
                db,
                text=text,
                language=body.get("language", "hi"),
                channel=Channel.WHATSAPP,
                citizen_ref=sender,
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise HTTPException(status_code=422, detail="Unrecognised webhook payload") from exc

    # Optional mock media bytes for test/demo payloads
    mock_bytes = None
    if "mock_media_base64" in body:
        mock_bytes = base64.b64decode(body["mock_media_base64"])

    # Acknowledge Meta immediately, then run the download + Gemini pipeline after
    # the response is sent. Meta expects a fast 2xx and retries on timeout; the
    # ChannelEvent dedup inside process_whatsapp_inbound makes any retry that
    # arrives before processing finishes a no-op, so a duplicate complaint can't
    # be created. The task opens its own Session because the request-scoped
    # `get_db` session is torn down as soon as this handler returns.
    async def _process_whatsapp_bg() -> None:
        task_db = SessionLocal()
        try:
            await process_whatsapp_inbound(task_db, msg, mock_media_bytes=mock_bytes)
        except Exception:
            log.exception("Background WhatsApp processing failed for message %s", msg.message_id)
        finally:
            task_db.close()

    background_tasks.add_task(_process_whatsapp_bg)
    return {"status": "received"}
