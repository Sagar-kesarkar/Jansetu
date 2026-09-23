"""Tests for ChannelSession store and privacy guarantees (backend/app/channels/session.py)."""
from __future__ import annotations

import json
import pytest

from app.channels.session import (
    get_context_dict,
    get_or_create_session,
    is_message_processed,
    mark_message_processed,
    update_session,
)
from app.db.database import SessionLocal, init_db
from app.db.models import ChannelSession
from app.services.privacy import pseudonymise

PHONE = "919876543210"


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()


def test_session_lifecycle_and_privacy():
    db = SessionLocal()
    try:
        # Create session with raw phone number — must be pseudonymised automatically
        session = get_or_create_session(db, PHONE, channel="ivr", initial_language="hi")
        assert session.citizen_ref.startswith("anon_")
        assert PHONE not in session.citizen_ref

        # Retrieve again -> same session
        session2 = get_or_create_session(db, PHONE, channel="ivr")
        assert session2.id == session.id

        # Update session
        update_session(db, session, new_state="COLLECT_NEED", language="bn", context_data={"attempts": 1})
        assert session.current_state == "COLLECT_NEED"
        assert session.language == "bn"
        ctx = get_context_dict(session)
        assert ctx.get("attempts") == 1

        # Strict Database Privacy Audit: raw phone number must NEVER appear in any column of channel_sessions
        rows = db.query(ChannelSession).all()
        for row in rows:
            for col in ChannelSession.__table__.columns.keys():
                val = getattr(row, col)
                assert PHONE not in str(val), f"Raw phone number leaked in ChannelSession.{col}"
    finally:
        db.close()


def test_idempotency_message_tracking():
    db = SessionLocal()
    try:
        ref = pseudonymise(PHONE)
        msg_id = "wamid.HBgLMzkxOTg3NjU0MzIxMAUCABEYEjE="

        assert not is_message_processed(db, ref, msg_id)
        mark_message_processed(db, ref, msg_id)
        assert is_message_processed(db, ref, msg_id)
        # Duplicate check returns True
        assert is_message_processed(db, ref, msg_id)
    finally:
        db.close()
