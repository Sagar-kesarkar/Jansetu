"""District resolution is the step that decides whether a request counts at all.

A request stored with `district_code = NULL` is not a degraded request — it is an
invisible one. `analytics/aggregate.py` builds (district x sector) cells, so a row
with no district joins to nothing: it never reaches a hotspot, never reaches a
recommendation, and the citizen who filed it is silently unrepresented while the
API still returns them a cheerful 200.

Which is why the shadowing case below has its own test. The real Gemini model
returns `location_text: "हमारे गाँव"` — "our village" — for a message that names
no place. That is a location grammatically and useless as an identifier, and
before the fix it overrode the place the citizen had already picked in the form.
"""
import pytest

from app.db.database import SessionLocal, init_db
from app.db.models import CitizenRequest, District
from app.models.schemas import Channel, ExtractedRequest, LocationHierarchy
from app.services import pipeline


@pytest.fixture(scope="module", autouse=True)
def district_fixture():
    init_db()
    db = SessionLocal()
    try:
        if not db.query(District).filter_by(code="GEO_D1").first():
            db.add(District(code="GEO_D1", name="Barpetapur", state="Assamland",
                            population=500_000, latitude=26.0, longitude=91.0,
                            literacy_pct=60.0, internet_pct=20.0, deprivation_index=0.6))
            db.commit()
    finally:
        db.close()
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def _stub_extraction(monkeypatch, location_text, location=None):
    """Pin the model's output so this tests the pipeline, not Gemini.

    `**_` absorbs `image` and `image_mime`: this fixture cares about place
    resolution, and a signature that has to be updated every time an unrelated
    extraction input is added is a test that breaks for the wrong reasons.
    """
    monkeypatch.setattr(
        pipeline, "extract_request",
        lambda text, language="hi", **_: ExtractedRequest(
            category="WATER_SUPPLY", summary_en="No water.", summary_native="पानी नहीं।",
            urgency=3, affected_estimate=None, location_text=location_text, confidence=1.0,
            location=location or LocationHierarchy(),
        ),
    )


def test_unresolvable_extracted_place_does_not_discard_the_form_value(monkeypatch, db):
    """The regression. "our village" must not beat a district the citizen chose."""
    _stub_extraction(monkeypatch, "हमारे गाँव")
    result = pipeline.ingest(
        db, text="हमारे गाँव में पानी नहीं आ रहा है", language="hi",
        channel=Channel.TEXT, location_text="Barpetapur, Assamland",
    )
    assert result.district == "Barpetapur", "request would have been invisible to analytics"
    assert db.get(CitizenRequest, result.request_id).district_code == "GEO_D1"


def test_a_real_extracted_place_still_wins_over_the_form(monkeypatch, db):
    """The fallback must not swallow the feature it is protecting: when the
    message names a place that resolves, the citizen's own words take priority."""
    _stub_extraction(monkeypatch, "Barpetapur")
    result = pipeline.ingest(
        db, text="Barpetapur has had no water for weeks", language="en",
        channel=Channel.TEXT, location_text="Somewhere Else, Nowhere",
    )
    assert result.district == "Barpetapur"


def test_no_place_anywhere_is_stored_without_a_district(monkeypatch, db):
    """Storing NULL beats guessing. A wrong district moves real money to the
    wrong place; an unresolved one is at least visibly unresolved."""
    _stub_extraction(monkeypatch, None)
    result = pipeline.ingest(
        db, text="पानी नहीं आ रहा है", language="hi", channel=Channel.TEXT,
    )
    assert result.district is None
    assert db.get(CitizenRequest, result.request_id).district_code is None
