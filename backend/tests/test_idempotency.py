"""Unit tests for atomic ChannelEvent deduplication store."""
from app.channels.idempotency import acquire_channel_event, complete_channel_event, fail_channel_event
from app.db.models import ChannelEvent


def test_channel_event_acquisition_and_deduplication(db_session):
    """Acquiring the same event twice returns is_new=True then is_new=False."""
    provider = "exotel"
    event_id = "test_call_sid_12345"
    event_type = "ivr_recording"

    # First attempt: new event
    event1, is_new1 = acquire_channel_event(db_session, provider, event_id, event_type)
    assert is_new1 is True
    assert event1.status == "PROCESSING"
    assert event1.external_event_id == event_id

    # Second attempt: duplicate event
    event2, is_new2 = acquire_channel_event(db_session, provider, event_id, event_type)
    assert is_new2 is False
    assert event2.id == event1.id


def test_channel_event_completion_and_failure(db_session):
    """Complete and fail state transitions record details properly."""
    event, is_new = acquire_channel_event(db_session, "whatsapp", "wamid_9999", "whatsapp_message")
    assert is_new is True

    complete_channel_event(db_session, event, request_id=42, details="ingest_complete")
    assert event.status == "PROCESSED"
    assert event.request_id == 42
    assert event.details == "ingest_complete"

    # Separate event failing
    event_fail, _ = acquire_channel_event(db_session, "exotel", "sms_failed_001", "sms_inbound")
    fail_channel_event(db_session, event_fail, "District not found")
    assert event_fail.status == "FAILED"
    assert "District not found" in event_fail.details
