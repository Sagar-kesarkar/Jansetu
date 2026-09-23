"""Meta WhatsApp Business Cloud API adapter.

Handles:
- Webhook signature verification (X-Hub-Signature-256) with WHATSAPP_APP_SECRET.
- Inbound webhook parsing for text, audio voice notes, and photographs.
- Two-hop media retrieval (Graph API metadata -> short-lived media stream) with bearer token.
- Multi-turn voice + photo evidence workflow attaching image_verification to existing docket.
- Atomic deduplication using ChannelEvent table.
- Fast webhook acknowledgement (<10s) with async background task processing.
- Outbound native-script acknowledgement with docket reference via Graph API.

PRIVACY:
- Raw sender phone number is passed directly to `ingest(citizen_ref=...)` for HMAC hashing.
- Phone number is never logged or written to disk.
- Media bytes are ephemeral in memory only.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.channels.idempotency import acquire_channel_event, complete_channel_event, fail_channel_event
from app.channels.replies import route_location_reply, status_reply
from app.channels.router import route
from app.channels.session import (
    get_channel_session,
    save_channel_session,
)
from app.config import get_settings
from app.models.schemas import Channel, IntakeResult
from app.services.gemini import extract_request
from app.services.pipeline import ingest
from app.services.privacy import pseudonymise
from app.services.tracking import citizen_reference

log = logging.getLogger(__name__)

MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_IMAGE_BYTES = 8 * 1024 * 1024   # 8 MB


def _conversational_reply(reply: str | None, language: str, safe_ref: str) -> IntakeResult:
    """An `IntakeResult` for a turn that opened no docket.

    The webhook discards this, but the simulator and the tests read it, and the
    return type is `IntakeResult`. `request_id=0` is the same "no record" marker
    the duplicate-message branch already uses.
    """
    return IntakeResult(
        request_id=0,
        category="OTHER",
        district=None,
        state=None,
        urgency=1,
        transcript=None,
        summary_en="Conversational turn - no request filed",
        acknowledgement_native=reply or "",
        language=language,
        channel=Channel.WHATSAPP,
        confidence=1.0,
        citizen_ref=safe_ref,
    )


def validate_whatsapp_signature(payload_bytes: bytes, signature_header: str | None, app_secret: str) -> bool:
    """Validate X-Hub-Signature-256 header from Meta."""
    if not app_secret:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected_sig = signature_header[7:]
    computed_sig = hmac.new(app_secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_sig, computed_sig)


class WhatsAppMessage:
    def __init__(
        self,
        sender: str,
        message_id: str,
        text: str | None = None,
        audio_id: str | None = None,
        audio_mime: str | None = None,
        image_id: str | None = None,
        image_mime: str | None = None,
        image_caption: str | None = None,
        language: str = "hi",
    ) -> None:
        self.sender = sender
        self.message_id = message_id
        self.text = text
        self.audio_id = audio_id
        self.audio_mime = audio_mime or "audio/ogg"
        self.image_id = image_id
        self.image_mime = image_mime or "image/jpeg"
        self.image_caption = image_caption
        self.language = language


def parse_whatsapp_webhook(payload: dict[str, Any]) -> WhatsAppMessage | None:
    """Extract normalized message from Meta Cloud API webhook payload."""
    try:
        entry = payload.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        if not messages:
            return None

        msg = messages[0]
        sender = msg.get("from")
        message_id = msg.get("id")
        if not sender or not message_id:
            return None

        msg_type = msg.get("type", "text")
        text = None
        audio_id = None
        audio_mime = None
        image_id = None
        image_mime = None
        image_caption = None

        if msg_type == "text":
            text = msg.get("text", {}).get("body", "")
        elif msg_type in ("audio", "voice"):
            audio_obj = msg.get("audio") or msg.get("voice") or {}
            audio_id = audio_obj.get("id")
            audio_mime = audio_obj.get("mime_type", "audio/ogg")
        elif msg_type == "image":
            img_obj = msg.get("image", {})
            image_id = img_obj.get("id")
            image_mime = img_obj.get("mime_type", "image/jpeg")
            image_caption = img_obj.get("caption")

        language = payload.get("language", "hi")

        return WhatsAppMessage(
            sender=str(sender),
            message_id=str(message_id),
            text=text,
            audio_id=audio_id,
            audio_mime=audio_mime,
            image_id=image_id,
            image_mime=image_mime,
            image_caption=image_caption,
            language=language,
        )
    except (IndexError, KeyError, TypeError) as exc:
        log.warning("Failed to parse WhatsApp webhook: %s", exc)
        return None


async def fetch_media_bytes(media_id: str) -> tuple[bytes, str]:
    """Two-hop retrieval of media bytes from Meta Graph API."""
    settings = get_settings()
    if not settings.whatsapp_token:
        raise ValueError("WHATSAPP_TOKEN not configured")

    headers = {"Authorization": f"Bearer {settings.whatsapp_token}"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Hop 1: Retrieve temporary media download URL
        meta_url = f"https://graph.facebook.com/{settings.whatsapp_graph_api_version}/{media_id}"
        meta_res = await client.get(meta_url, headers=headers)
        meta_res.raise_for_status()
        meta_data = meta_res.json()
        download_url = meta_data.get("url")
        mime_type = meta_data.get("mime_type", "application/octet-stream")

        if not download_url:
            raise ValueError(f"No media download URL in Meta response: {meta_data}")

        # Hop 2: Download raw binary stream
        media_res = await client.get(download_url, headers=headers)
        media_res.raise_for_status()
        media_bytes = media_res.content

        return media_bytes, mime_type


async def send_whatsapp_message(to: str, message_text: str) -> bool:
    """Send outbound text message via Meta Graph API."""
    settings = get_settings()
    if not settings.whatsapp_token or not settings.whatsapp_phone_number_id:
        log.info("WhatsApp mock dispatch (credentials not set) -> [%s...]", to[:4] if to else "")
        return True

    url = f"https://graph.facebook.com/{settings.whatsapp_graph_api_version}/{settings.whatsapp_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message_text},
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload, headers=headers)
            if res.status_code in (200, 201):
                return True
            log.error("WhatsApp message send error HTTP %s: %s", res.status_code, res.text)
            return False
    except Exception as exc:
        log.error("Failed to send WhatsApp message: %s", exc)
        return False


async def process_whatsapp_inbound(
    db: Session,
    msg: WhatsAppMessage,
    *,
    mock_media_bytes: bytes | None = None,
) -> IntakeResult:
    """Process inbound WhatsApp message with deduplication, voice, text, and photo evidence."""
    event, is_new = acquire_channel_event(db, "whatsapp", msg.message_id, "whatsapp_message")
    safe_ref = pseudonymise(msg.sender)
    if not is_new:
        log.info("Duplicate WhatsApp message %s ignored", msg.message_id)
        from app.db.models import CitizenRequest, District
        existing_row = db.get(CitizenRequest, event.request_id) if event.request_id else None
        dist = db.get(District, existing_row.district_code) if existing_row and existing_row.district_code else None
        return IntakeResult(
            request_id=event.request_id or 0,
            category=existing_row.category if existing_row else "OTHER",
            district=dist.name if dist else (existing_row.loc_district if existing_row else None),
            state=dist.state if dist else (existing_row.loc_state if existing_row else None),
            urgency=existing_row.urgency if existing_row else 1,
            transcript=existing_row.transcript if existing_row else None,
            summary_en=existing_row.summary_en if existing_row else "Duplicate message",
            acknowledgement_native="Message already received.",
            language=existing_row.language if existing_row else msg.language,
            channel=Channel.WHATSAPP,
            confidence=existing_row.confidence if existing_row else 1.0,
            citizen_ref=safe_ref,
        )

    session = get_channel_session(db, safe_ref, channel="whatsapp")
    ctx = session.get_context()

    # 1. Location follow-up on existing pending request
    if ctx.get("state") != "AWAITING_PHOTO" and msg.text:
        loc_reply = route_location_reply(
            db,
            safe_ref=safe_ref,
            text=msg.text,
            language=ctx.get("router_language") or msg.language,
            expecting=bool(ctx.get("router_issue") or ctx.get("router_awaiting") == "router_issue"),
        )
        if loc_reply is not None:
            await send_whatsapp_message(msg.sender, loc_reply.reply)
            complete_channel_event(db, event, request_id=loc_reply.request_id, details=f"location_reply_{loc_reply.kind}")
            return _conversational_reply(loc_reply.reply, msg.language, safe_ref)

    # 2. STATUS command / token tracking
    if msg.text and msg.text.strip().upper().startswith("STATUS"):
        parts = msg.text.strip().split(None, 1)
        ref_query = parts[1].strip() if len(parts) > 1 else None
        s_rep = status_reply(db, ref_query, safe_ref=safe_ref, rich=True)
        await send_whatsapp_message(msg.sender, s_rep.reply)
        complete_channel_event(db, event, request_id=s_rep.request_id, details="status_query")
        return _conversational_reply(s_rep.reply, msg.language, safe_ref)

    # Greeting, language menu and the Issue+Location check, before any media is
    # downloaded. A "Hi" used to open a docket describing nothing; the gate answers
    # it with the language menu instead. Skipped while a photo is expected against
    # an existing docket, because that branch owns the conversation.
    has_media = bool(msg.audio_id or msg.image_id)
    if ctx.get("state") != "AWAITING_PHOTO":
        decision = route(db, ctx, msg.text, default_language=msg.language,
                         has_media=has_media, safe_ref=safe_ref, rich=True)
        session.set_context(decision.context)
        save_channel_session(db, session)
        if decision.handled:
            await send_whatsapp_message(msg.sender, decision.reply or "")
            complete_channel_event(db, event, details="gated_no_docket")
            return _conversational_reply(decision.reply, decision.language, safe_ref)
        # The rejoined "issue — place" sentence, and the language the citizen chose
        # from the menu, both replace what arrived on this single message.
        if decision.text:
            msg.text = decision.text
        msg.language = decision.language
        ctx = decision.context

    audio_bytes: bytes | None = None
    image_bytes: bytes | None = None

    try:
        # Fetch media if IDs are present
        if msg.audio_id:
            if mock_media_bytes:
                audio_bytes = mock_media_bytes
            else:
                audio_bytes, msg.audio_mime = await fetch_media_bytes(msg.audio_id)

        if msg.image_id:
            if mock_media_bytes:
                image_bytes = mock_media_bytes
            else:
                image_bytes, msg.image_mime = await fetch_media_bytes(msg.image_id)

        # Multi-turn Voice + Image evidence:
        # Check if an image was sent for an active pending complaint session
        if image_bytes and ctx.get("state") == "AWAITING_PHOTO" and ctx.get("last_request_id"):
            from app.db.models import CitizenRequest, District
            existing_req = db.get(CitizenRequest, ctx["last_request_id"])
            if existing_req:
                # Analyze image with Gemini
                extracted_img = extract_request(
                    text=msg.text or "Photo evidence of reported issue",
                    language=msg.language,
                    image=image_bytes,
                    image_mime=msg.image_mime,
                )
                if extracted_img.image_verification:
                    existing_req.image_verification = extracted_img.image_verification
                    existing_req.has_photo = True
                    db.commit()

                # Clear session, but keep the chosen language for the next complaint.
                session.set_context(
                    {"router_language": ctx["router_language"]} if ctx.get("router_language") else {}
                )
                session.current_state = "COMPLETED"
                save_channel_session(db, session)

                ack_msg = f"Photo evidence attached to docket #{existing_req.id}. Thank you."
                await send_whatsapp_message(msg.sender, ack_msg)
                complete_channel_event(db, event, request_id=existing_req.id, details="photo_evidence_attached")

                dist_row = db.get(District, existing_req.district_code) if existing_req.district_code else None

                return IntakeResult(
                    request_id=existing_req.id,
                    category=existing_req.category,
                    district=dist_row.name if dist_row else existing_req.loc_district,
                    state=dist_row.state if dist_row else existing_req.loc_state,
                    urgency=existing_req.urgency,
                    transcript=existing_req.transcript,
                    summary_en=existing_req.summary_en,
                    acknowledgement_native=ack_msg,
                    language=existing_req.language,
                    channel=Channel.WHATSAPP,
                    confidence=existing_req.confidence or 0.9,
                    citizen_ref=existing_req.citizen_ref,
                )

        # Ingest new complaint
        text_content = msg.text or msg.image_caption
        if not text_content and image_bytes:
            text_content = "Photograph of public issue"

        result = ingest(
            db,
            text=text_content,
            audio=audio_bytes,
            audio_mime=msg.audio_mime,
            image=image_bytes,
            image_mime=msg.image_mime,
            language=msg.language,
            channel=Channel.WHATSAPP,
            citizen_ref=msg.sender,
        )

        # Multi-issue acknowledgment formatting
        if getattr(result, "request_count", 1) > 1 and getattr(result, "requests", None):
            tokens_lines = []
            for req_item in result.requests:
                t = citizen_reference(req_item.track_token, req_item.request_id)
                lbl = req_item.title or req_item.summary_en or req_item.category
                tokens_lines.append(f"📌 Request {req_item.issue_index} of {req_item.issue_count} ({lbl}): {t}")
            token_block = "\n".join(tokens_lines)
        else:
            token_block = f"📌 Tracking token: {citizen_reference(result.track_token, result.request_id)}"

        # If a voice note was submitted, open session for optional subsequent photo evidence
        if audio_bytes:
            # Keeps `router_language` so a citizen who picked Tamil from the menu is
            # still answered in Tamil on the photo turn that follows.
            session.set_context({**ctx, "last_request_id": result.request_id, "state": "AWAITING_PHOTO"})
            session.current_state = "AWAITING_PHOTO"
            save_channel_session(db, session)

            ack_text = (
                f"{result.acknowledgement_native}\n\n"
                f"{token_block}\n"
                f"If you have photo evidence, please send a photo now."
            )
        else:
            ack_text = (
                f"{result.acknowledgement_native}\n\n"
                f"{token_block}"
            )

        # Send native acknowledgment
        await send_whatsapp_message(msg.sender, ack_text)
        complete_channel_event(db, event, request_id=result.request_id, details="whatsapp_ingest_success")
        return result
    except Exception as exc:
        log.error("Failed to process WhatsApp message: %s", exc)
        fail_channel_event(db, event, str(exc))
        raise
    finally:
        del audio_bytes
        del image_bytes
        del mock_media_bytes
