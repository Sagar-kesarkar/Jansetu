"""The ward boundary — the one place where constraint 5 is negotiated.

Constraint 5 says no address fields, ever. But a district is too coarse to act
on: Raigad is 7,000 km², and "the road is broken" cannot be dispatched against
it. So the platform stores a place down to ward level and refuses anything finer,
and this module asserts that refusal at every layer it has to hold at.

The distinction being enforced is **k-anonymity, not appearance**:

    Sector 23, Ulwe, 410206        ~18,000 people    ward      -> keep
    Flat 402, Shivaji CHS          one household     address   -> refuse

Three separate guarantees are tested here, because each fails differently:

1. `place.scrub` drops below-ward data even when the model returns it. The
   extraction schema has no field for a house number, but a schema is a shape and
   only a filter is a guarantee — and the no-key fallback has no model to instruct
   at all.
2. The officials' console is never served the citizen's raw location line. The
   raw line is still stored, because an unresolved place cannot be debugged
   without the string that failed, but the official — who is the party a
   complainant might reasonably fear — does not receive it.
3. A photograph is read and discarded. Nothing writes the bytes anywhere.

The negative case in `test_a_block_survives_because_it_is_administrative` is the
one most likely to regress. In India a block is a tehsil-equivalent
administrative unit, so a filter that ate "Kosagumuda block" because "block"
sounds like a building would silently coarsen half of rural India's addresses.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.db.database import SessionLocal, engine, init_db
from app.db.models import CitizenRequest, District, PlaceAlias, RequestResponse
from app.main import app
from app.models.schemas import Channel, ExtractedRequest, LocationHierarchy
from app.services import pipeline
from app.services.place import clean_pin, probes, public_place, sanitise, scrub

RAIGAD = "PRIV_RAIGAD"

#: The address the platform failed on, verbatim from the report that prompted
#: this work. Kept exactly as typed — the trailing duplicated PIN and the missing
#: space after the comma are both real, and both are what a hand-written parser
#: would have choked on.
REPORTED = "sector 23,ulwe,410206 NAVI MUMBAI, MAHARASHTRA 410206"


@pytest.fixture(scope="module", autouse=True)
def seeded():
    init_db()
    db = SessionLocal()
    try:
        db.merge(District(code=RAIGAD, name="Raigadpur", state="Maharashtra",
                          population=2_600_000, latitude=18.5, longitude=73.1,
                          literacy_pct=83.0, internet_pct=42.0, deprivation_index=0.41))
        db.query(PlaceAlias).filter(PlaceAlias.district_code == RAIGAD).delete()
        for alias, kind in [("ulwe", "locality"), ("410206", "pin"), ("panvel", "tehsil")]:
            db.add(PlaceAlias(district_code=RAIGAD, alias=alias, kind=kind))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client():
    return TestClient(app)


def _stub(monkeypatch, location: LocationHierarchy, image_note: str | None = None):
    """Pin extraction so these tests exercise the filter, not the model."""
    monkeypatch.setattr(
        pipeline, "extract_request",
        lambda text, language="hi", **_: ExtractedRequest(
            category="ROADS", summary_en="Road broken.", summary_native="सड़क टूटी है।",
            urgency=3, confidence=1.0, location_text=None,
            location=location, image_verification=image_note,
        ),
    )


# ---------- 1. the filter ----------

def test_a_flat_number_cannot_be_stored():
    """The headline refusal. A ward is a place; a flat is a household."""
    assert scrub("Flat 402, Sector 23") == "Sector 23"
    assert scrub("House No 12, Ward 14, Ulwe") == "Ward 14, Ulwe"
    assert scrub("Plot 18, Sector 23, Ulwe") == "Sector 23, Ulwe"


def test_a_building_name_is_dropped_whole_not_stripped_of_its_marker():
    """Stripping only "CHS" leaves "Shivaji", which is still the building — and
    now looks like a locality, which is worse than dropping it: it would be
    stored as a place and shown to an officer as one."""
    assert scrub("Shivaji CHS, Sector 23") == "Sector 23"
    assert scrub("Ganga Niwas, Ulwe") == "Ulwe"
    assert scrub("Sai Residency") is None


def test_a_bare_unit_designator_is_dropped():
    """No marker word at all — the form a citizen actually types."""
    assert scrub("B-14, Sector 23") == "Sector 23"
    assert scrub("402/A, Ulwe") == "Ulwe"
    assert scrub("12 Ulwe") == "Ulwe", "leading premises number"


def test_a_sector_survives_because_it_is_the_permitted_floor():
    """The filter must not swallow the thing it exists to protect."""
    assert scrub("Sector 23") == "Sector 23"
    assert scrub("Ward No 7") == "Ward No 7"
    assert scrub("Phase 2, Kharghar") == "Phase 2, Kharghar"


def test_a_block_survives_because_it_is_administrative():
    """A block is a tehsil-equivalent unit, not a building. Eating this would
    silently coarsen rural addresses across most of the country."""
    assert scrub("Kosagumuda block") == "Kosagumuda block"
    assert scrub("Umerkote Block, Nabarangpur") == "Umerkote Block, Nabarangpur"


def test_a_pin_must_be_six_digits_in_the_allocated_range():
    """Exactness matters here more than anywhere: the geocoder matches PINs
    literally because 410206 and 410205 are 83% similar and 30 km apart."""
    assert clean_pin("410206") == "410206"
    assert clean_pin("410 206") == "410206", "spaced, as printed on envelopes"
    assert clean_pin("41020") is None, "five digits"
    assert clean_pin("4102066") is None, "seven digits"
    assert clean_pin("910206") is None, "0 and 9 are unallocated first digits"
    assert clean_pin("not specified") is None


def test_a_placeholder_echo_is_not_a_place():
    """Models return the example from their own prompt more often than is
    comfortable. Stored unchecked, "e.g., Maharashtra" becomes a state."""
    assert scrub("e.g., Maharashtra") == "Maharashtra"
    assert scrub("not specified") is None
    assert scrub("Unknown") is None
    assert scrub("N/A") is None
    assert scrub("   ") is None


def test_caps_lock_is_normalised_but_deliberate_capitals_are_not():
    """People type addresses in caps lock and extraction echoes what was typed:
    the reported line produced "NAVI MUMBAI, MAHARASHTRA", which is what an
    officer then reads. Mixed case is left alone because it is evidence of
    intent that a blanket .title() would destroy."""
    assert scrub("MAHARASHTRA") == "Maharashtra"
    assert scrub("ulwe") == "Ulwe"
    assert scrub("sector 23,NAVI MUMBAI") == "Sector 23, Navi Mumbai"
    assert scrub("Y.S.R. Kadapa") == "Y.S.R. Kadapa", "mixed case is untouched"
    assert scrub("MIDC Ulwe") == "MIDC Ulwe", "an acronym beside a name survives"


def test_sanitise_applies_the_filter_to_every_level():
    """Field-by-field, because a model that respects the rule in one field is not
    evidence that it respected it in the others."""
    dirty = LocationHierarchy(
        state="Maharashtra", district_or_city="Navi Mumbai", locality="Ulwe",
        sector_or_ward="Flat 402, Shivaji CHS, Sector 23", pin_code="410206",
    )
    clean = sanitise(dirty)
    assert clean.sector_or_ward == "Sector 23"
    assert clean.locality == "Ulwe"
    assert clean.pin_code == "410206"


# ---------- 2. the console boundary ----------

def test_public_place_reads_ward_upwards():
    h = LocationHierarchy(state="Maharashtra", district_or_city="Navi Mumbai",
                          locality="Ulwe", sector_or_ward="Sector 23", pin_code="410206")
    assert public_place(h) == "Sector 23, Ulwe, Navi Mumbai, Maharashtra 410206"
    assert public_place(LocationHierarchy()) is None


def test_the_officials_console_is_never_served_the_raw_line(monkeypatch, client, db):
    """Option 2, asserted. The raw line stays in the database — it is the only
    way to debug a failed resolution — and the console gets the scrubbed
    hierarchy instead. The official is the party a complainant might fear, so the
    boundary belongs at this response, not at the write path."""
    _stub(monkeypatch, LocationHierarchy(
        state="Maharashtra", district_or_city="Navi Mumbai", locality="Ulwe",
        sector_or_ward="Sector 23", pin_code="410206",
    ))
    result = pipeline.ingest(
        db, text="Sector 23 road is broken", language="en",
        channel=Channel.TEXT, location_text="Flat 402, Shivaji CHS, Sector 23, Ulwe 410206",
    )

    stored = db.get(CitizenRequest, result.request_id)
    assert stored.location_text is not None, "raw line must survive for debugging"

    detail = client.get(f"/requests/{result.request_id}")
    assert detail.status_code == 200
    body = detail.json()

    assert "location_text" not in body, "the raw line must not be in the response at all"
    serialised = detail.text.casefold()
    for leaked in ("flat 402", "shivaji", "chs"):
        assert leaked not in serialised, f"{leaked!r} reached the officials' console"

    assert body["place"] == "Sector 23, Ulwe, Navi Mumbai, Maharashtra 410206"
    assert body["location"]["sector_or_ward"] == "Sector 23"


def test_the_console_search_cannot_probe_the_raw_line(monkeypatch, client, db):
    """A subtler leak than displaying it. Substring search over a hidden column
    discloses it a character at a time: an officer who suspects a flat number can
    confirm it by whether the row comes back. So the raw line is not searched."""
    _stub(monkeypatch, LocationHierarchy(locality="Ulwe", state="Maharashtra"))
    result = pipeline.ingest(
        db, text="drain overflowing near the school", language="en",
        channel=Channel.TEXT, location_text="Flat 909, Sunrise Heights, Ulwe",
    )

    hit = client.get("/requests", params={"q": "Sunrise Heights"})
    assert hit.status_code == 200
    assert result.request_id not in [r["id"] for r in hit.json()], "raw line is searchable"

    # The scrubbed levels remain searchable, or the field is useless.
    found = client.get("/requests", params={"q": "Ulwe"})
    assert result.request_id in [r["id"] for r in found.json()]


# ---------- 3. the photograph ----------

def test_no_column_anywhere_can_hold_an_image():
    """Checked against the live schema rather than by reading the code, because
    the claim is about what the database can contain, not about current intent.
    A photograph of a broken road also carries faces, door plates and EXIF
    coordinates — every category constraint 5 forbids, arriving in a field nobody
    declared."""
    columns = {c["name"]: str(c["type"]).upper()
               for c in inspect(engine).get_columns("citizen_requests")}
    assert "image_verification" in columns, "the description is kept"
    assert "has_photo" in columns
    for name, kind in columns.items():
        assert "BLOB" not in kind, f"{name} could store image bytes"
        assert "image_path" not in name and "image_url" not in name


def test_a_photograph_is_recorded_as_having_existed_even_when_unreadable(monkeypatch, db):
    """With no API key an image still arrives and still cannot be described.
    "attached, not analysed" is a different fact from "none sent", and an officer
    needs to be able to tell them apart — otherwise a failed vision call looks
    like a citizen who never bothered."""
    _stub(monkeypatch, LocationHierarchy(locality="Ulwe"), image_note=None)
    result = pipeline.ingest(
        db, text="potholes everywhere", language="en", channel=Channel.TEXT,
        image=b"\xff\xd8\xff\xe0 not really a jpeg", image_mime="image/jpeg",
    )
    stored = db.get(CitizenRequest, result.request_id)
    assert stored.has_photo is True
    assert stored.image_verification is None
    assert result.image_verification is None


def test_an_image_description_reaches_the_console(monkeypatch, client, db):
    _stub(monkeypatch, LocationHierarchy(locality="Ulwe"),
          image_note="An unpaved road surface with standing water and exposed potholes.")
    result = pipeline.ingest(
        db, text="road is broken", language="en", channel=Channel.TEXT,
        image=b"\xff\xd8\xff\xe0 bytes", image_mime="image/jpeg",
    )
    body = client.get(f"/requests/{result.request_id}").json()
    assert body["has_photo"] is True
    assert "standing water" in body["image_verification"]


# ---------- 4. the hierarchy earns its keep ----------

def test_the_reported_address_resolves_through_the_hierarchy(monkeypatch, db):
    """End to end on the address that failed. The PIN is tried first because the
    geocoder matches those exactly, and a PIN is the one thing a citizen states
    that cannot be ambiguous.

    The district name is not pinned to the fixture. 410206 is a real Raigad PIN
    and `data/reference/place_aliases.csv` carries it, so against a seeded
    database the genuine row answers first and against a bare one the fixture
    does. Either outcome is the assertion this test is making — that the PIN
    resolved at all, where the flat string previously produced NULL.
    """
    _stub(monkeypatch, LocationHierarchy(
        state="Maharashtra", district_or_city="Navi Mumbai", locality="Ulwe",
        sector_or_ward="Sector 23", pin_code="410206",
    ))
    result = pipeline.ingest(
        db, text="Sector 23 ki sadak toot gayi hai", language="hi",
        channel=Channel.TEXT, location_text=REPORTED,
    )
    assert result.district in {"Raigadpur", "Raigad"}, result.district
    assert result.state == "Maharashtra"
    assert result.location.pin_code == "410206"
    assert result.location.sector_or_ward == "Sector 23"


def test_probes_are_ordered_most_precise_first():
    """The order is the whole value of decomposing. A flat string reaches the
    fuzzy pass with the state as similarity to be donated to the wrong district —
    which is how "Navi Mumbai, Maharashtra" once resolved to Nandurbar, 400 km
    away. A bare PIN reaches an exact-match pass instead."""
    h = LocationHierarchy(state="Maharashtra", district_or_city="Navi Mumbai",
                          locality="Ulwe", sector_or_ward="Sector 23", pin_code="410206")
    order = probes(h)
    assert order[0] == "410206"
    assert "Ulwe, Maharashtra" in order
    assert order.index("Ulwe, Maharashtra") < order.index("Navi Mumbai, Maharashtra"), \
        "a locality is more specific than the city containing it"


def test_probes_survive_an_empty_hierarchy():
    """The no-key path returns nothing structured, and must still resolve from
    whatever the form supplied."""
    assert probes(None, fallback="Barpeta, Assam") == ["Barpeta, Assam"]
    assert probes(LocationHierarchy()) == []


def test_a_hierarchy_of_only_a_state_does_not_resolve_a_district(monkeypatch, db):
    """Naming a state is a boundary, not an answer. Storing NULL beats guessing:
    a wrong district moves real money to the wrong place."""
    _stub(monkeypatch, LocationHierarchy(state="Maharashtra"))
    result = pipeline.ingest(
        db, text="roads are bad", language="en", channel=Channel.TEXT,
    )
    assert result.district is None
    assert db.get(CitizenRequest, result.request_id).district_code is None
