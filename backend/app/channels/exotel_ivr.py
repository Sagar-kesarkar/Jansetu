"""Exotel Real IVR Call-Flow & Audio Processing Adapter.

Zero-PII Compliance:
- Raw caller number exists only in memory to call ingest() and dispatch the confirmation SMS.
- Recording audio is streamed/held in memory only and immediately discarded.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.channels.exotel_sms import format_dlt_sms, send_exotel_sms
from app.channels.idempotency import acquire_channel_event, complete_channel_event, fail_channel_event
from app.config import get_settings
from app.i18n.languages import LANGUAGES
from app.models.schemas import Channel
from app.services.pipeline import ingest

log = logging.getLogger(__name__)

PAGE_SIZE = 7


def get_language_pages() -> list[list[tuple[str, str]]]:
    """Generate paginated language list dynamically from app.i18n.languages.LANGUAGES."""
    lang_items = list(LANGUAGES.items())
    return [lang_items[i : i + PAGE_SIZE] for i in range(0, len(lang_items), PAGE_SIZE)]


def get_language_menu_manifest(page: int = 0) -> dict[str, Any]:
    """Build dynamic DTMF mapping for a given language page."""
    pages = get_language_pages()
    total_pages = len(pages)
    curr_page = max(0, min(page, total_pages - 1))
    page_langs = pages[curr_page]

    digit_map: dict[str, str] = {}
    for idx, (code, _) in enumerate(page_langs, start=1):
        digit_map[str(idx)] = code

    has_next = curr_page < total_pages - 1
    has_prev = curr_page > 0

    return {
        "page": curr_page,
        "total_pages": total_pages,
        "digit_map": digit_map,
        "next_key": "9" if has_next else None,
        "prev_key": "0" if has_prev else "0",  # 0 is repeat or prev
        "languages": page_langs,
    }


def build_exotel_dtmf_response(
    digits: str | None = None,
    page: int = 0,
    current_lang: str = "hi",
) -> dict[str, Any]:
    """Determine next IVR step based on DTMF input."""
    manifest = get_language_menu_manifest(page)
    clean_digits = (digits or "").strip()

    if not clean_digits:
        # Initial greeting and language menu
        return {
            "action": "gather",
            "prompt": f"/ivr/prompts/{current_lang}/GREETING_LANG_MENU.wav",
            "num_digits": 1,
            "timeout_sec": 10,
            "page": manifest["page"],
        }

    # Next page
    if clean_digits == "9" and manifest["next_key"]:
        next_manifest = get_language_menu_manifest(page + 1)
        return {
            "action": "gather",
            "prompt": f"/ivr/prompts/{current_lang}/GREETING_LANG_MENU.wav",
            "num_digits": 1,
            "timeout_sec": 10,
            "page": next_manifest["page"],
        }

    # Previous page / repeat
    if clean_digits == "0":
        prev_page = max(0, page - 1)
        prev_manifest = get_language_menu_manifest(prev_page)
        return {
            "action": "gather",
            "prompt": f"/ivr/prompts/{current_lang}/GREETING_LANG_MENU.wav",
            "num_digits": 1,
            "timeout_sec": 10,
            "page": prev_manifest["page"],
        }

    # Language selected
    if clean_digits in manifest["digit_map"]:
        selected_lang = manifest["digit_map"][clean_digits]
        return {
            "action": "record",
            "selected_language": selected_lang,
            "prompt": f"/ivr/prompts/{selected_lang}/RECORD_NEED_BEEP.wav",
            "max_duration_sec": 45,
            "finish_on_key": "#",
        }

    # Invalid digit
    return {
        "action": "gather",
        "prompt": f"/ivr/prompts/{current_lang}/INVALID_OPTION_RETRY.wav",
        "num_digits": 1,
        "timeout_sec": 10,
        "page": manifest["page"],
    }


def build_exotel_recording_response(
    lang: str = "hi",
) -> dict[str, Any]:
    """Exotel response playing confirmation prompt and ending the call."""
    return {
        "action": "play_and_hangup",
        "prompt": f"/ivr/prompts/{lang}/CONFIRMATION_NOTICE.wav",
        "hangup": True,
    }


async def download_recording_bytes(
    recording_url: str,
) -> bytes:
    """Download Exotel recording securely via HTTPS with Basic Auth.

    Held in memory only.
    """
    settings = get_settings()
    auth = None
    if settings.exotel_api_key and settings.exotel_api_token:
        auth = (settings.exotel_api_key, settings.exotel_api_token)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(recording_url, auth=auth)
        resp.raise_for_status()
        audio_data = resp.content

        if len(audio_data) > settings.max_audio_bytes:
            raise ValueError(f"Recording exceeds max limit: {len(audio_data)} > {settings.max_audio_bytes}")

        return audio_data


async def process_exotel_recording_async(
    db: Session,
    caller_phone: str,
    call_sid: str,
    recording_url: str,
    *,
    recording_duration: int = 0,
    lang: str = "hi",
    audio_bytes_override: bytes | None = None,
) -> dict[str, Any]:
    """Asynchronously process IVR recording and dispatch confirmation SMS.

    Zero-PII Guarantee:
    - Never logs caller phone number.
    - Media bytes are ephemeral.
    """
    settings = get_settings()
    event, is_new = acquire_channel_event(db, "exotel", call_sid, "ivr_recording")
    if not is_new:
        return {"status": "duplicate", "message": "Event already processed"}

    # 1. Download or retrieve audio bytes
    try:
        if audio_bytes_override is not None:
            audio_bytes = audio_bytes_override
        else:
            audio_bytes = await download_recording_bytes(recording_url)

        if not audio_bytes or len(audio_bytes) < 32:
            fail_channel_event(db, event, "Empty or invalid audio recording")
            return {"status": "empty_recording"}

        # 2. Ingest complaint through pipeline
        res = ingest(
            db,
            audio=audio_bytes,
            audio_mime="audio/wav",
            language=lang,
            channel=Channel.IVR,
            citizen_ref=caller_phone,
        )

        # 3. Send confirmation SMS only after ingest succeeds
        conf_msg = format_dlt_sms(
            "REGISTRATION_SUCCESS",
            reference=f"#{res.request_id}",
            district=res.district or "your district",
        )
        await send_exotel_sms(caller_phone, conf_msg, template_id=settings.dlt_success_template_id)

        complete_channel_event(db, event, request_id=res.request_id, details="ivr_ingest_success")
        return {"status": "success", "request_id": res.request_id}
    except Exception as exc:
        log.error("Exotel IVR recording processing failed: %s", exc)
        fail_channel_event(db, event, str(exc))
        # Failure SMS alert
        fail_msg = format_dlt_sms("TEMPORARY_FAILURE")
        await send_exotel_sms(caller_phone, fail_msg, template_id=settings.dlt_failure_template_id)
        raise
    finally:
        # Guarantee audio bytes are dereferenced
        del audio_bytes_override
