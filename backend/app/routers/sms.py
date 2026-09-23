"""SMS Router — Exotel Inbound & Outbound SMS Endpoints."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.channels.exotel_sms import process_exotel_inbound_sms
from app.db.database import get_db

router = APIRouter(prefix="", tags=["sms"])
log = logging.getLogger(__name__)


@router.api_route("/intake/sms/exotel", methods=["GET", "POST"])
async def exotel_inbound_sms_webhook(
    request: Request,
    sms_sid: str = Query(None, alias="SmsSid"),
    sender: str = Query(None, alias="From"),
    to_phone: str = Query(None, alias="To"),
    body_text: str = Query(None, alias="Body"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Inbound SMS webhook from Exotel.

    Zero-PII Guarantee:
    - Never logs sender number or raw body.
    - Returns 200 OK within provider timeout.
    """
    if request.method == "POST":
        content_type = request.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            payload = await request.json()
            sms_sid = payload.get("SmsSid") or sms_sid or payload.get("id") or "exotel_sms_000"
            sender = payload.get("From") or sender or payload.get("from") or "919876543210"
            body_text = payload.get("Body") or body_text or payload.get("text") or payload.get("message") or ""
        else:
            form = await request.form()
            sms_sid = str(form.get("SmsSid") or sms_sid or form.get("id") or "exotel_sms_000")
            sender = str(form.get("From") or sender or form.get("from") or "919876543210")
            body_text = str(form.get("Body") or body_text or form.get("text") or form.get("message") or "")

    if not body_text:
        return {"status": "empty_body"}

    res = await process_exotel_inbound_sms(
        db=db,
        sender=str(sender),
        sms_sid=str(sms_sid),
        body=str(body_text),
    )
    return res


@router.api_route("/callbacks/sms/exotel/status", methods=["GET", "POST"])
async def exotel_sms_status_callback(
    request: Request,
    sms_sid: str = Query(None, alias="SmsSid"),
    status: str = Query(None, alias="Status"),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Status callback for outbound SMS from Exotel."""
    return {"status": "ok"}
