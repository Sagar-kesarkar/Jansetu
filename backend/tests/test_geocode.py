"""District resolution, and the false positive that made it necessary.

A citizen submitted this, through the live web form, and it is the reason this
file exists:

    sector 23,ulwe,410206 NAVI MUMBAI, MAHARASHTRA 410206

The request was stored with `district_code = NULL` and the dashboard showed
"Not matched". Investigating that turned up something worse than the reported
symptom: the shorter form of the same address, "Navi Mumbai, Maharashtra",
resolved to **Nandurbar** with a score of 78.3 against a threshold of 78. The
matcher compared the whole input against the string "District, State", so the
shared word "Maharashtra" supplied most of the similarity and a complaint from a
Mumbai satellite city was filed against a tribal district 400 km away. The user's
longer string escaped that only because the sector number and PIN diluted the
score to 28.5.

A NULL district makes a request invisible. A wrong district makes it evidence for
the wrong place — it inflates one district's demand and depresses another's, in a
system whose entire claim is that the ranking can be trusted. So the tests below
are mostly about refusal: what must resolve, what must resolve *correctly*, and
what the resolver must decline to guess.
"""
from __future__ import annotations

import pytest

from app.db.database import SessionLocal, init_db
from app.db.models import District, PlaceAlias
from app.services.geocode import MATCH_THRESHOLD, resolve_district

#: Enough of the real reference data to reproduce the bug and its fix. Codes are
#: the production ones so a failure here points at a row in districts.csv.
_DISTRICTS = [
    ("MH_NANDURBAR", "Nandurbar", "Maharashtra"),
    ("MH_RAIGAD", "Raigad", "Maharashtra"),
    ("MH_THANE", "Thane", "Maharashtra"),
    ("MH_OSMANABAD", "Osmanabad", "Maharashtra"),
    ("OD_NABARANGPUR", "Nabarangpur", "Odisha"),
    ("AS_BARPETA", "Barpeta", "Assam"),
    # The ambiguity case: one name, two states, neither of them a guess.
    ("MH_AURANGABAD", "Aurangabad", "Maharashtra"),
    ("BR_AURANGABAD", "Aurangabad", "Bihar"),
]

_ALIASES = [
    ("410206", "MH_RAIGAD", "pin"),
    ("ulwe", "MH_RAIGAD", "locality"),
    ("panvel", "MH_RAIGAD", "city"),
    ("navi mumbai", "MH_THANE", "city"),
    ("vashi", "MH_THANE", "locality"),
    ("dharashiv", "MH_OSMANABAD", "alt_name"),
    ("बारपेटा", "AS_BARPETA", "native"),
]


@pytest.fixture(scope="module", autouse=True)
def reference_data():
    init_db()
    db = SessionLocal()
    try:
        for code, name, state in _DISTRICTS:
            db.merge(District(code=code, name=name, state=state, population=1_000_000,
                              literacy_pct=60.0, internet_pct=20.0, deprivation_index=0.6))
        db.commit()
        for alias, code, kind in _ALIASES:
            if not db.query(PlaceAlias).filter_by(alias=alias, district_code=code).first():
                db.add(PlaceAlias(alias=alias, district_code=code, kind=kind))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


# ---------- the regression ----------

def test_the_reported_address_resolves(db):
    """The exact string a citizen submitted, character for character."""
    geo = resolve_district(db, "sector 23,ulwe,410206 NAVI MUMBAI, MAHARASHTRA 410206")
    assert geo.district == "Raigad", f"resolved to {geo.district} via {geo.reason}"
    assert geo.district_code == "MH_RAIGAD"


def test_navi_mumbai_is_never_nandurbar(db):
    """The false positive, pinned.

    Scored 78.3 against a threshold of 78 before the rewrite. This assertion is
    on the district rather than the score because the point is not that the number
    moved — it is that no amount of tuning may put a Konkan address in a tribal
    district in Khandesh.
    """
    for text in ("Navi Mumbai, Maharashtra", "navi mumbai", "NAVI MUMBAI MAHARASHTRA"):
        assert resolve_district(db, text).district != "Nandurbar", f"{text!r} regressed"


def test_a_state_mention_cannot_donate_similarity(db):
    """The mechanism behind the bug: naming a state must not raise the score of a
    district whose name does not appear at all."""
    bare = resolve_district(db, "Kolhapur")
    with_state = resolve_district(db, "Kolhapur, Maharashtra")
    assert bare.district_code is None and with_state.district_code is None
    assert with_state.score <= bare.score + 1e-9, "the state name added similarity"


def test_a_stated_state_is_a_boundary_not_a_hint(db):
    """Nabarangpur is in Odisha. Asking for it in Maharashtra must fail, not
    silently cross the border because the name is a good match."""
    assert resolve_district(db, "Nabarangpur, Odisha").district == "Nabarangpur"
    crossed = resolve_district(db, "Nabarangpur, Maharashtra")
    assert crossed.district_code is None
    assert crossed.matched_state == "Maharashtra"


# ---------- what must resolve ----------

def test_pin_code_alone_is_enough(db):
    geo = resolve_district(db, "410206")
    assert geo.district == "Raigad" and geo.score == 100.0
    assert geo.reason == "PIN 410206"


def test_a_wrong_pin_is_not_approximated(db):
    """410205 is 83% similar to 410206 and a different place. The PIN pass is
    exact for this reason, and an unknown PIN must fall through, not fuzzy-match."""
    assert "PIN" not in resolve_district(db, "410205").reason


def test_a_locality_beats_the_city_it_sits_in(db):
    """Navi Mumbai straddles two districts: Vashi is in Thane, Ulwe in Raigad.
    "Ulwe, Navi Mumbai" contains both aliases and the longer string is the wrong
    answer, so specificity has to outrank length."""
    assert resolve_district(db, "Ulwe, Navi Mumbai").district == "Raigad"
    assert resolve_district(db, "Vashi, Navi Mumbai").district == "Thane"


def test_district_name_still_resolves_with_surrounding_noise(db):
    """The old matcher's one genuine strength must survive the rewrite."""
    geo = resolve_district(db, "Barpeta Road, Assam")
    assert geo.district == "Barpeta"
    assert geo.score >= MATCH_THRESHOLD


def test_native_script_resolves_and_keeps_its_vowel_signs(db):
    """`\\w` does not match combining marks, so the obvious tokeniser turns
    "बारपेटा" into "ब रप ट" and throws away the मात्रा that distinguish Indic
    place names from each other."""
    geo = resolve_district(db, "बारपेटा")
    assert geo.district == "Barpeta"
    assert "बारपेटा" in geo.reason, f"vowel signs were stripped: {geo.reason}"


def test_a_renamed_district_resolves_under_both_names(db):
    """Osmanabad became Dharashiv in 2023. Citizens use both, and a rename is a
    row in place_aliases.csv rather than a decision about which name is correct."""
    assert resolve_district(db, "Dharashiv").district == "Osmanabad"
    assert resolve_district(db, "Osmanabad").district == "Osmanabad"


# ---------- what must be refused ----------

def test_a_name_in_two_states_is_ambiguous_not_arbitrary(db):
    """Aurangabad is in Maharashtra and in Bihar. With no state stated, resolving
    it means picking by list order, which is a coin flip dressed as a result."""
    geo = resolve_district(db, "Aurangabad")
    assert geo.district_code is None, f"guessed {geo.district}, {geo.state}"
    assert "ambiguous" in geo.reason
    assert geo.candidates == ["Aurangabad", "Aurangabad"] or len(geo.candidates) >= 1
    # Naming the state resolves it, which is the whole point of refusing above.
    assert resolve_district(db, "Aurangabad, Bihar").district_code == "BR_AURANGABAD"


def test_a_grammatical_location_is_not_a_place(db):
    """Gemini reliably returns "हमारे गाँव" — "our village" — when a message names
    nowhere. See tests/test_geocode_fallback.py for what depends on this."""
    for text in ("our village", "हमारे गाँव", "my area", "here"):
        assert resolve_district(db, text).district_code is None, f"{text!r} resolved"


def test_an_uncovered_place_reports_the_state_it_recognised(db):
    """Pune is in Maharashtra and not in this fixture. "Nothing matched" and
    "Maharashtra matched, Pune is not covered yet" are different facts: the second
    tells a citizen the platform works and tells us which row to add next."""
    geo = resolve_district(db, "Shivajinagar, Pune, Maharashtra")
    assert geo.district_code is None
    assert geo.matched_state == "Maharashtra"
    assert "no covered district matched" in geo.reason


def test_empty_and_missing_input(db):
    for text in (None, "", "   "):
        geo = resolve_district(db, text)
        assert geo.district_code is None and geo.score == 0.0
