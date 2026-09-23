"""Exotel Inbound & Outbound SMS Adapter for JanSetu.

Zero-PII Compliance:
Raw phone numbers exist in transient memory only while calling ingest() and
dispatching immediate transactional SMS responses.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any
import urllib.parse

import httpx
from sqlalchemy.orm import Session

from app.channels.idempotency import acquire_channel_event, complete_channel_event, fail_channel_event
from app.channels.prompts import get_prompt_text
from app.channels.replies import route_location_reply, status_reply
from app.channels.router import route
from app.channels.session import (
    get_channel_session,
    save_channel_session,
)
from app.config import get_settings
from app.models.schemas import Channel
from app.services.pipeline import ingest
from app.services.privacy import pseudonymise
from app.services.tracking import citizen_reference

log = logging.getLogger(__name__)

# DLT Approved Standard Templates
DLT_TEMPLATES = {
    "REGISTRATION_SUCCESS": "Your JanSetu request {reference} has been registered successfully for {district}. Keep this reference for tracking. - JanSetu",
    "LOCATION_CLARIFICATION": "JanSetu needs the village/town and district for your request. Reply: LOC <village/town>, <district>.",
    "TEMPORARY_FAILURE": "JanSetu could not process your request at this moment. Please try again after some time. - JanSetu",
    "STATUS_UPDATE": "Your JanSetu request {reference} current status is: {status}. District: {district}. - JanSetu",
    "HELP": "JanSetu: Send your problem with village & district. Reply LOC <place> for location, or STATUS <ref> to track. - JanSetu",
}


def format_dlt_sms(template_key: str, **kwargs: Any) -> str:
    """Format SMS text according to DLT-registered templates."""
    tpl = DLT_TEMPLATES.get(template_key, "")
    if not tpl:
        return ""
    try:
        return tpl.format(**kwargs)
    except KeyError:
        return tpl


def _confirmation_sms(res: Any, language: str) -> str:
    """The registration confirmation, in the language the citizen chose.

    English goes through the DLT-registered template unchanged, because that is
    what an Indian operator has on file and what will actually deliver at scale.
    Every other language gets the native confirmation plus the token: a citizen who
    picked Tamil from the menu and is answered in English has no way to tell whether
    the twelve characters they are copying down belong to their complaint. The token
    itself stays Latin — it is what they will type back into `/track`.
    """
    reference = citizen_reference(res.track_token, res.request_id)
    if language == "en":
        return format_dlt_sms(
            "REGISTRATION_SUCCESS",
            reference=reference,
            district=res.district or "your district",
        )
    return (
        f"{get_prompt_text('CONFIRMATION_NOTICE', language)} "
        f"{get_prompt_text('DOCKET_REF_INTRO', language)} {reference}"
    )


async def send_exotel_sms(
    to_phone: str,
    body: str,
    *,
    template_id: str | None = None,
    status_callback: str | None = None,
) -> bool:
    """Send transactional SMS via Exotel SMS API.

    Zero-PII: Never logs the full destination phone number.
    """
    settings = get_settings()

    if not settings.exotel_account_sid or not settings.exotel_api_key or not settings.exotel_api_token:
        log.info("Exotel SMS mock dispatch (credentials not set) -> [%s...]", to_phone[:4] if to_phone else "")
        return True

    # Exotel Mumbai endpoint
    region_prefix = f"api.{settings.exotel_region}" if settings.exotel_region != "mumbai" else "api"
    url = f"https://{region_prefix}.exotel.com/v1/Accounts/{settings.exotel_account_sid}/Sms/send.json"

    sender_from = settings.exotel_sms_sender_id or settings.exotel_exophone

    data: dict[str, str] = {
        "From": sender_from,
        "To": to_phone,
        "Body": body,
    }
    if template_id or settings.dlt_success_template_id:
        data["DltTemplateId"] = template_id or settings.dlt_success_template_id
    if settings.dlt_entity_id:
        data["DltEntityId"] = settings.dlt_entity_id

    callback_url = status_callback or f"{settings.public_base_url.rstrip('/')}/callbacks/sms/exotel/status"
    if callback_url:
        data["StatusCallback"] = callback_url

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                data=data,
                auth=(settings.exotel_api_key, settings.exotel_api_token),
            )
            if resp.status_code in (200, 201):
                return True
            log.error("Exotel SMS API error HTTP %s: %s", resp.status_code, resp.text)
            return False
    except Exception as exc:
        log.error("Failed to dispatch Exotel SMS: %s", exc)
        return False


async def process_exotel_inbound_sms(
    db: Session,
    sender: str,
    sms_sid: str,
    body: str,
) -> dict[str, Any]:
    """Process inbound SMS from Exotel.

    Zero-PII Guarantee:
    - Never logs sender phone number.
    - Uses pseudonymise(sender) for session store.
    """
    settings = get_settings()
    event, is_new = acquire_channel_event(db, "exotel", sms_sid, "sms_inbound")
    if not is_new:
        return {"status": "duplicate", "message": "Event already processed"}

    text = body.strip()
    safe_ref = pseudonymise(sender)
    session = get_channel_session(db, safe_ref, channel="sms")
    ctx = session.get_context()

    # 1. HELP command
    if text.upper() in ("HELP", "मदद", "SAHAYATA"):
        msg = format_dlt_sms("HELP")
        await send_exotel_sms(sender, msg, template_id=settings.dlt_status_template_id)
        complete_channel_event(db, event, details="help_command")
        return {"status": "success", "action": "help"}

    # 2. STATUS command / token tracking
    if text.upper().startswith("STATUS"):
        parts = text.split(None, 1)
        ref_query = parts[1].strip() if len(parts) > 1 else None
        s_rep = status_reply(db, ref_query, safe_ref=safe_ref, rich=False)
        await send_exotel_sms(sender, s_rep.reply, template_id=settings.dlt_status_template_id)
        complete_channel_event(db, event, request_id=s_rep.request_id, details="status_query")
        return {"status": "success", "action": "status_query", "message": s_rep.reply}

    # 3. Explicit location reply: LOC <place>
    if text.upper().startswith("LOC "):
        loc_str = text[4:].strip()
        pending = ctx.get("pending_complaint") or {}
        problem_text = pending.get("original_text") or ctx.get("router_issue") or text

        try:
            res = ingest(
                db,
                text=problem_text,
                location_text=loc_str,
                language=ctx.get("selected_language") or ctx.get("router_language", "hi"),
                channel=Channel.SMS,
                citizen_ref=sender,
            )
            # Clear pending state, keep chosen language
            session.set_context(
                {"selected_language": ctx.get("selected_language", "hi"), "current_state": "COMPLETED"}
            )
            session.current_state = "COMPLETED"
            save_channel_session(db, session)

            await send_exotel_sms(
                sender,
                _confirmation_sms(res, ctx.get("selected_language") or ctx.get("router_language", "hi")),
                template_id=settings.dlt_success_template_id,
            )
            complete_channel_event(db, event, request_id=res.request_id, details="clarification_success")
            return {"status": "success", "request_id": res.request_id}
        except Exception as exc:
            fail_channel_event(db, event, str(exc))
            fail_msg = format_dlt_sms("TEMPORARY_FAILURE")
            await send_exotel_sms(sender, fail_msg, template_id=settings.dlt_failure_template_id)
            raise

    # 4. State Machine Routing
    clean_text = text[5:].strip() if text.upper().startswith("NEED ") else text
    current_lang = ctx.get("selected_language") or ctx.get("router_language", "hi")

    decision = route(db, ctx, clean_text, default_language=current_lang, safe_ref=safe_ref, rich=False)
    session.set_context(decision.context)
    save_channel_session(db, session)

    if decision.handled:
        await send_exotel_sms(
            sender,
            decision.reply or "",
            template_id=settings.dlt_location_template_id if "pending_complaint" in decision.context else None,
        )
        complete_channel_event(
            db, event,
            details="gated_no_docket",
        )
        return {
            "status": "pending_clarification" if "pending_complaint" in decision.context else "conversation",
            "message": decision.reply,
        }

    # Process verified complaint with location
    try:
        res = ingest(
            db,
            text=decision.text or clean_text,
            language=decision.language,
            channel=Channel.SMS,
            citizen_ref=sender,
        )
        await send_exotel_sms(
            sender,
            _confirmation_sms(res, decision.language),
            template_id=settings.dlt_success_template_id,
        )
        complete_channel_event(db, event, request_id=res.request_id, details="direct_sms_ingest")
        return {"status": "success", "request_id": res.request_id}
    except Exception as exc:
        fail_channel_event(db, event, str(exc))
        fail_msg = format_dlt_sms("TEMPORARY_FAILURE")
        await send_exotel_sms(sender, fail_msg, template_id=settings.dlt_failure_template_id)
        raise
