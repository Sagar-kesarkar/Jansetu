"""The District column: what an officer reads, and why it has two names in it.

The bug this closes was reported as "it is only showing Thane, Maharashtra". A
citizen wrote *Sector 23, Ulwe, 410206 Navi Mumbai, Maharashtra*, the geocoder
correctly resolved Raigad, and the console printed "Raigad" — at which point the
officer's reasonable conclusion is that the platform matched the wrong place,
because nobody in Navi Mumbai calls their district Raigad.

Both names are load-bearing and neither is sufficient:

* the **resolved district** is the LGD key, and it is the only value that joins
  against census, coverage and budget data — every ranking here is keyed to it;
* the **name the citizen used** is the only thing that lets a human verify the
  inference rather than trust it.

So the label is district-first with the citizen's own word in brackets, and the
bracket is suppressed when it would add nothing. The suppression is the part most
likely to regress: "Bengaluru Urban (Bengaluru)" and "Mumbai Suburban (Mumbai)"
are the common case in Indian district naming, not an edge one, and a column full
of them is noise that trains officers to stop reading it.

The resolution half of the same feature is covered in `test_geocode.py`; this file
is display only, and `district_label` is pure, so none of it needs a database.
"""
from __future__ import annotations

import pytest

from app.models.schemas import LocationHierarchy
from app.services.place import district_label


def _h(**fields) -> LocationHierarchy:
    return LocationHierarchy(**fields)


def test_the_reported_bug_shows_both_names():
    """The exact case from the report. "Raigad" alone reads as a mismatch."""
    assert district_label("Raigad", _h(district_or_city="Navi Mumbai",
                                       locality="Ulwe", state="Maharashtra")) \
        == "Raigad (Navi Mumbai)"


@pytest.mark.parametrize("resolved,named,expected", [
    ("Ernakulam", "Kochi", "Ernakulam (Kochi)"),
    ("Khordha", "Bhubaneswar", "Khordha (Bhubaneswar)"),
    ("Kamrup Metropolitan", "Guwahati", "Kamrup Metropolitan (Guwahati)"),
    ("Thane", "Navi Mumbai", "Thane (Navi Mumbai)"),
    ("South Delhi", "New Delhi", "South Delhi (New Delhi)"),
])
def test_a_city_that_is_not_its_districts_name_keeps_both(resolved, named, expected):
    """The whole point of the feature: these are the places where a citizen's word
    and the administrative key are genuinely different words, and an officer
    shown only one of them cannot check the other."""
    assert district_label(resolved, _h(district_or_city=named)) == expected


@pytest.mark.parametrize("resolved,named", [
    ("Bengaluru Urban", "Bengaluru"),   # named is inside resolved
    ("Mumbai Suburban", "Mumbai"),
    ("Kanpur Nagar", "Kanpur"),
    ("Chennai", "Chennai"),             # identical
    ("Pune", "PUNE"),                   # identical but for case
    ("Mumbai City", "Mumbai"),
])
def test_no_bracket_when_it_would_add_nothing(resolved, named):
    """Containment either way, and case-insensitively. "Bengaluru Urban
    (Bengaluru)" tells a reader nothing they did not already have."""
    assert district_label(resolved, _h(district_or_city=named)) == resolved


def test_the_citizens_word_stands_alone_when_nothing_resolved():
    """Bare "Delhi" is the live example: the NCT is four real districts here and
    the geocoder refuses to pick one, so the column shows what the citizen said.
    It is all there is, and `district_code` being NULL is what the console styles
    the row on — the label is not carrying that signal."""
    assert district_label(None, _h(district_or_city="Delhi")) == "Delhi"
    assert district_label(None, _h(district_or_city="Someplace Unknown")) == "Someplace Unknown"


def test_the_district_stands_alone_when_the_citizen_named_no_city():
    """A report resolved from a bare PIN or a lone locality has no city in its
    hierarchy. "Chennai" is the honest answer; inventing a bracket from the
    locality would put the same string in two columns."""
    assert district_label("Chennai", _h(pin_code="600020")) == "Chennai"
    assert district_label("Bengaluru Urban", _h(locality="Whitefield")) == "Bengaluru Urban"
    assert district_label("Raigad", None) == "Raigad"
    assert district_label("Raigad", _h()) == "Raigad"


def test_nothing_in_means_nothing_out():
    """Not None-safety theatre: every seeded row and every row ingested without a
    Gemini call has an empty hierarchy, and an unresolved one has no district
    either. The console must render that as blank, not as the string "None"."""
    assert district_label(None, None) is None
    assert district_label(None, _h()) is None
    assert district_label("", _h(district_or_city="")) is None
