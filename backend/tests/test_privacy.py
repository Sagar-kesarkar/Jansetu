"""Privacy guarantees, tested rather than asserted in a docstring.

`docs/DPG_COMPLIANCE.md` indicator 7 claims nothing in the schema can
re-identify a citizen. The WhatsApp webhook receives a real phone number, so
that claim is a behaviour of `pipeline.ingest` — and behaviour needs a test or
it regresses the next time a channel is added.
"""
from __future__ import annotations

from app.db.database import SessionLocal, init_db
from app.db.models import CitizenRequest, District
from app.models.schemas import Channel
from app.services.pipeline import ingest
from app.services.privacy import pseudonymise

PHONE = "919876543210"


def test_pseudonymise_is_stable_and_opaque():
    first = pseudonymise(PHONE)
    assert first == pseudonymise(PHONE), "same input must map to the same ref"
    assert PHONE not in first
    assert first.startswith("anon_")
    assert pseudonymise("919876543211") != first


def test_pseudonymise_passes_through_absent_values():
    assert pseudonymise(None) is None
    assert pseudonymise("") is None
    assert pseudonymise("   ") is None


def test_whatsapp_phone_number_is_never_persisted():
    """The end-to-end guarantee: a number handed to ingest cannot be read back
    out of the database, in any column."""
    init_db()
    db = SessionLocal()
    try:
        db.merge(District(code="PRIV_D1", name="Privpur", state="Testland",
                          population=100_000, latitude=21.0, longitude=79.0,
                          literacy_pct=60.0, internet_pct=20.0, deprivation_index=0.5))
        db.commit()

        result = ingest(
            db,
            text="पानी की समस्या है",
            language="hi",
            channel=Channel.WHATSAPP,
            location_text="Privpur, Testland",
            citizen_ref=PHONE,
        )

        row = db.query(CitizenRequest).filter_by(id=result.request_id).one()
        assert row.citizen_ref is not None, "the opaque ref should still exist"
        assert row.citizen_ref == pseudonymise(PHONE)

        # No column anywhere may contain the raw number.
        for column in CitizenRequest.__table__.columns.keys():
            assert PHONE not in str(getattr(row, column)), f"phone leaked into {column}"
    finally:
        db.close()
