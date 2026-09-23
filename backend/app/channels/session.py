"""Session store for multi-turn conversations on IVR, WhatsApp, and SMS.

PRIVACY ARCHITECTURE & ZERO-PII GUARANTEE:
- All sessions are strictly keyed by the HMAC-SHA256 pseudonymised handle (`citizen_ref`),
  e.g. 'anon_d4e5f6...'.
- A raw phone number is NEVER stored in the database, session table, or context data.
- If a raw identifier is accidentally provided, it is automatically passed through
  `services/privacy.py::pseudonymise` before hitting the database.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import ChannelSession
from app.services.privacy import pseudonymise

log = logging.getLogger(__name__)


def _ensure_pseudonymised(ref: str) -> str:
    """Guarantee that the handle is HMAC-pseudonymised before any SQL operation."""
    if not ref.startswith("anon_"):
        pseudo = pseudonymise(ref)
        if pseudo:
            return pseudo
    return ref


def get_session(db: Session, citizen_ref: str, channel: str = "ivr") -> ChannelSession | None:
    """Retrieve an existing session for a pseudonymised citizen reference."""
    safe_ref = _ensure_pseudonymised(citizen_ref)
    return (
        db.query(ChannelSession)
        .filter(ChannelSession.citizen_ref == safe_ref, ChannelSession.channel == channel)
        .order_by(ChannelSession.updated_at.desc())
        .first()
    )


def get_or_create_session(
    db: Session,
    citizen_ref: str,
    channel: str = "ivr",
    initial_state: str = "INITIAL",
    initial_language: str = "hi",
) -> ChannelSession:
    """Get active session or create a new one, keyed safely by pseudonymised ref."""
    safe_ref = _ensure_pseudonymised(citizen_ref)
    session = get_session(db, safe_ref, channel=channel)
    if session is None:
        session = ChannelSession(
            citizen_ref=safe_ref,
            channel=channel,
            current_state=initial_state,
            language=initial_language,
            context_data=json.dumps({}),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    return session


def get_channel_session(
    db: Session,
    citizen_ref: str,
    channel: str = "ivr",
) -> ChannelSession:
    """Retrieve or initialize channel session safely."""
    return get_or_create_session(db, citizen_ref, channel=channel)


def save_channel_session(db: Session, session: ChannelSession) -> ChannelSession:
    """Persist session updates with fresh timestamp."""
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session


def update_session(
    db: Session,
    session: ChannelSession,
    *,
    new_state: str | None = None,
    language: str | None = None,
    context_data: dict[str, Any] | None = None,
) -> ChannelSession:
    """Update session state, language, or context."""
    if new_state is not None:
        session.current_state = new_state
    if language is not None:
        session.language = language
    if context_data is not None:
        # Merge with existing context
        existing = json.loads(session.context_data or "{}")
        existing.update(context_data)
        session.context_data = json.dumps(existing)

    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session


def delete_session(db: Session, session: ChannelSession) -> None:
    """Remove a finished or timed-out session."""
    db.delete(session)
    db.commit()


def get_context_dict(session: ChannelSession) -> dict[str, Any]:
    """Parse session context JSON into a dictionary."""
    try:
        return json.loads(session.context_data or "{}")
    except Exception:
        return {}


def is_message_processed(db: Session, citizen_ref: str, message_id: str) -> bool:
    """Check idempotency: whether a Meta webhook message ID has already been handled."""
    safe_ref = _ensure_pseudonymised(citizen_ref)
    session = get_session(db, safe_ref, channel="whatsapp")
    if not session:
        return False
    ctx = get_context_dict(session)
    processed_ids = ctx.get("processed_message_ids", [])
    return message_id in processed_ids


def mark_message_processed(db: Session, citizen_ref: str, message_id: str) -> None:
    """Record a processed message ID to prevent duplicate report creation on webhook retries."""
    safe_ref = _ensure_pseudonymised(citizen_ref)
    session = get_or_create_session(db, safe_ref, channel="whatsapp")
    ctx = get_context_dict(session)
    processed_ids = ctx.get("processed_message_ids", [])
    if message_id not in processed_ids:
        # Keep last 50 message IDs
        processed_ids = (processed_ids + [message_id])[-50:]
        ctx["processed_message_ids"] = processed_ids
        session.context_data = json.dumps(ctx)
        db.commit()
