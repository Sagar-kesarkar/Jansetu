"""Atomic deduplication store using ChannelEvent table.

Guarantees idempotency across Meta message IDs, Exotel CallSids, RecordingSids,
SMS Sids, and retry callbacks.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ChannelEvent

log = logging.getLogger(__name__)


def acquire_channel_event(
    db: Session,
    provider: str,
    external_event_id: str,
    event_type: str,
) -> tuple[ChannelEvent, bool]:
    """Atomically acquire an event record.

    Returns:
        (channel_event, is_new): If is_new is True, the caller should process the event.
        If False, this is a duplicate retry and the caller should return 200 without re-processing.
    """
    safe_event_id = str(external_event_id).strip()
    existing = (
        db.query(ChannelEvent)
        .filter(
            ChannelEvent.provider == provider,
            ChannelEvent.external_event_id == safe_event_id,
            ChannelEvent.event_type == event_type,
        )
        .first()
    )
    if existing:
        return existing, False

    try:
        event = ChannelEvent(
            provider=provider,
            external_event_id=safe_event_id,
            event_type=event_type,
            status="PROCESSING",
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event, True
    except IntegrityError:
        db.rollback()
        # Another worker or thread inserted it concurrently
        existing = (
            db.query(ChannelEvent)
            .filter(
                ChannelEvent.provider == provider,
                ChannelEvent.external_event_id == safe_event_id,
                ChannelEvent.event_type == event_type,
            )
            .first()
        )
        if existing:
            return existing, False
        raise


def complete_channel_event(
    db: Session,
    event: ChannelEvent,
    *,
    request_id: int | None = None,
    details: str | None = None,
) -> None:
    """Mark event as successfully processed and link request_id."""
    event.status = "PROCESSED"
    if request_id is not None:
        event.request_id = request_id
    if details is not None:
        event.details = details
    event.updated_at = datetime.now(timezone.utc)
    db.commit()


def fail_channel_event(
    db: Session,
    event: ChannelEvent,
    error: str,
) -> None:
    """Mark event as failed with error details."""
    event.status = "FAILED"
    event.details = error[:500]
    event.updated_at = datetime.now(timezone.utc)
    db.commit()
