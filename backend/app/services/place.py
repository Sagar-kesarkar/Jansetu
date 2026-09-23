"""Where the ward boundary is enforced.

Constraint 5 says no address fields, ever. But "the road is broken" is
unactionable at district level — Raigad is 7,000 km² — so a works department
needs to know *which* road, and that means storing something finer than the
district. This module is where that tension is resolved rather than fudged.

The line drawn here is **k-anonymity, not appearance**. A string is acceptable if
it names a place many people share and unacceptable if it can single out a
household:

    Sector 23, Ulwe, 410206              ~18,000 people   ward      -> keep
    Flat 402, Shivaji CHS, Plot 18       one family       address   -> refuse

Two mechanisms, deliberately redundant. The extraction schema in `gemini.py`
offers no field below `sector_or_ward`, so there is nowhere for a house number to
go; and `sanitise` strips one anyway, because a prompt is a request and a regex
is a guarantee. The fallback path has no model at all, which is the second reason
the guarantee cannot live in the prompt.

What is deliberately *not* stripped: `block`. In India a block is a
tehsil-equivalent administrative unit — "Kosagumuda block, Nabarangpur" is a
legitimate and useful location, and a filter that ate it because "block" sounds
like a building would silently coarsen half the country's rural addresses.

Photographs are never stored. `gemini.py` reads the image, keeps its description
and discards the bytes, because a photo of a broken road also contains faces,
door plates and EXIF coordinates — every category constraint 5 forbids, arriving
in a field nobody declared.
"""
from __future__ import annotations

import re

from app.models.schemas import LocationHierarchy

#: A comma-separated segment naming a dwelling, a building or a land parcel.
#: Matched against the whole segment and drops it entirely: stripping only the
#: marker from "Shivaji CHS" leaves "Shivaji", which is still the building.
_BELOW_WARD = re.compile(
    r"""(?ix)
    (?:^|\b) (?:
        flats? | flt | apt | apartments? | house | hno | h\s*[./]?\s*no
      | door | plot | survey | khasra | gut | room | shop | gala | godown
      | tower | wing | floor | storey | bldg | building | chawl | chs
      | c\s*\.?\s*h\s*\.?\s*s | society | soc | sahakari | cooperative | co-?op
      | niwas | nivas | sadan | bhavan | bhawan | residency | complex | heights
      | enclave | cottage | bungalow | villa | quarters? | qtr
    ) (?:\b|$)
    """
)

#: A bare unit designator with no marker word: "B-14", "402/A", "A1204".
#: Bounded to four digits so a six-digit PIN can never match.
_UNIT_TOKEN = re.compile(r"(?i)^(?:[a-z]\s*-?\s*\d{1,4}[a-z]?|\d{1,4}\s*/\s*[a-z0-9]{1,4})$")

#: Values a model returns when it has nothing: refusals, and — more often than is
#: comfortable — the example from its own prompt echoed back verbatim.
_EMPTY_VALUES = {
    "", "-", "--", "n/a", "na", "none", "null", "nil", "unknown", "unspecified",
    "not specified", "not stated", "not mentioned", "not provided", "not given",
    "not available", "unclear", "string", "e.g.", "eg", "tbd", "no",
}

_PIN = re.compile(r"^\d{6}$")

#: Real Indian PINs start 1-8. 0 and 9 are unallocated, so a six-digit number
#: outside that range is a phone fragment or an invoice number, not a place.
_PIN_FIRST = frozenset("12345678")

_PLACEHOLDER_PREFIX = re.compile(r"(?i)^(?:e\.?g\.?|for example|such as|extract the)\b[\s.:,;()-]*")


def _recase(text: str) -> str:
    """Fix casing only when one segment's own casing was uniform.

    Extraction echoes what was typed, and people type addresses in caps lock:
    the reported line produced `sector 23, ulwe, NAVI MUMBAI, MAHARASHTRA`,
    which is the string an officer then reads off the console.

    Applied per segment rather than to the whole line, because a line is
    routinely mixed *between* its parts while each part is uniform in itself —
    "sector 23,NAVI MUMBAI" is exactly that, and judged whole it would escape
    normalisation entirely.

    Mixed case within a segment is left strictly alone, because it is evidence of
    deliberate capitalisation that a blanket `.title()` would destroy —
    "Y.S.R. Kadapa", "MIDC Ulwe", "NCT of Delhi". The cost of the rule is that an
    all-caps acronym standing alone gets flattened ("MIDC" -> "Midc"); that is
    rarer than caps-lock addresses, and wrong in a way that is merely ugly rather
    than misleading.

    Nothing downstream depends on case — the geocoder casefolds every pass — so
    this is presentation only.
    """
    if text != text.upper() and text != text.lower():
        return text
    return re.sub(r"[A-Za-z]+", lambda m: m.group(0).capitalize(), text)


def _clean(value: str | None) -> str | None:
    """Normalise one extracted field, or return None if it says nothing.

    Runs before the privacy filter because a placeholder like "e.g., Sector 23"
    would otherwise be stored as a real ward.
    """
    if value is None:
        return None

    text = _PLACEHOLDER_PREFIX.sub("", str(value)).strip().strip(".,;:-").strip()
    text = re.sub(r"\s+", " ", text)
    if text.casefold() in _EMPTY_VALUES:
        return None
    # A model asked for a district sometimes returns the whole prompt line.
    return text[:96] if text else None


def scrub(value: str | None) -> str | None:
    """Remove anything finer than a ward. Returns None if nothing survives.

    Segment-level rather than word-level: an address is a sequence of
    increasingly specific parts, and the specific ones have to go whole.

    Two passes over the delimiters, because "/" is ambiguous. It separates parts
    in "Sector 23 / Ulwe" but is *internal* to the unit designator "402/A", so a
    single split on it would produce "402" and "A" and let both through as
    ordinary words. Each comma-segment is therefore tested intact before being
    split further.
    """
    text = _clean(value)
    if text is None:
        return None

    kept: list[str] = []
    for segment in re.split(r"[,;|]| - ", text):
        outer = segment.strip()
        if not outer:
            continue
        if _UNIT_TOKEN.match(outer):
            continue  # "402/A" — tested before "/" is treated as a separator
        for part in outer.split("/"):
            part = part.strip()
            if not part or _BELOW_WARD.search(part) or _UNIT_TOKEN.match(part):
                continue
            # A leading bare number is a premises number: "12 Ulwe" -> "Ulwe".
            # "Sector 23" is untouched because the digits trail a word.
            part = re.sub(r"^\d{1,4}\s*[a-z]?\s+(?=\D)", "", part, flags=re.I).strip()
            if part and not _UNIT_TOKEN.match(part):
                kept.append(_recase(part))

    return ", ".join(kept) or None


def clean_pin(value: str | None) -> str | None:
    """Six digits, allocated range, or nothing.

    Strict because the geocoder matches PINs *exactly*: 410206 and 410205 are 83%
    similar and 30 km apart, so a near-miss must fail rather than approximate.
    """
    text = _clean(value)
    if text is None:
        return None
    digits = re.sub(r"\D", "", text)
    if _PIN.match(digits) and digits[0] in _PIN_FIRST:
        return digits
    return None


def sanitise(raw: LocationHierarchy | None) -> LocationHierarchy:
    """The choke point. Every hierarchy reaching the database passes through here.

    Called from `pipeline.ingest` for the same reason `privacy.pseudonymise` is:
    one place that cannot be forgotten, rather than a rule each channel has to
    remember.
    """
    if raw is None:
        return LocationHierarchy()
    return LocationHierarchy(
        state=scrub(raw.state),
        district_or_city=scrub(raw.district_or_city),
        locality=scrub(raw.locality),
        sector_or_ward=scrub(raw.sector_or_ward),
        pin_code=clean_pin(raw.pin_code),
    )


def public_place(h: LocationHierarchy | None) -> str | None:
    """The location string an official is allowed to see.

    This is the whole of option 2: the citizen's raw line stays in the database
    for debugging a failed resolution, and the officials' console is served this
    instead. The threat model is specific — the official is the person a
    complainant might reasonably fear — so the boundary is placed there rather
    than at the database edge, where it would be easier to describe and less use.
    """
    if h is None:
        return None
    parts = [h.sector_or_ward, h.locality, h.district_or_city, h.state]
    joined = ", ".join(p for p in parts if p)
    if h.pin_code:
        joined = f"{joined} {h.pin_code}".strip()
    return joined or None


def official_place(h: LocationHierarchy | None, raw_line: str | None) -> str | None:
    """What the officials' console shows in its "Place" column.

    `public_place` alone was wrong, and wrong in the most misleading direction. The
    structured hierarchy only exists when an extraction call produced it, so every
    seeded row and every row ingested without a Gemini call — the keyless path, and
    the path taken the moment the free tier's daily quota runs out — had no
    hierarchy and rendered as "not stated". An officer reading that concludes the
    citizen never said where the problem was. They usually did: `location_text` held
    "Gadchiroli, Maharashtra" the whole time.

    Falling back to `scrub(location_text)` costs nothing in privacy terms because
    `scrub` *is* the privacy guarantee — the same regex, applied to the same class of
    string, dropping the same below-ward detail. What changes is only whether the
    guarantee gets a chance to run. A hierarchy is still preferred when present: it
    is structured, so it renders in a consistent order rather than in whatever order
    the citizen typed.
    """
    return public_place(h) or scrub(raw_line)


def district_label(resolved: str | None, h: LocationHierarchy | None) -> str | None:
    """"Raigad (Navi Mumbai)" — the official district, plus the place the citizen
    actually named, when they are not the same word.

    Both halves are needed and neither is sufficient. `resolved` is the LGD
    district the geocoder matched, which is the only value that joins against
    census, coverage and budget data — every ranking in this platform is keyed to
    it. But nobody in India files a complaint using their district name: they
    write Navi Mumbai, Ulwe or Kochi. Showing only the district makes an officer
    read "Raigad" for a report about Ulwe and conclude the match was wrong;
    showing only the city drops the key that makes the row aggregable.

    So: district first, because it is the authoritative half, and the citizen's
    own word in brackets so the officer can see the inference and check it.

    The bracket is suppressed when one name contains the other, which is the
    common case rather than an edge one — "Bengaluru" inside "Bengaluru Urban",
    "Mumbai" inside "Mumbai Suburban". "Bengaluru Urban (Bengaluru)" tells a
    reader nothing they did not have and makes the column noisy.

    Returns the citizen's word alone when nothing resolved: it is all there is,
    and `district_code` being NULL is the signal the console styles on.
    """
    named = (h.district_or_city if h else None) or None
    if not resolved:
        return named
    if not named:
        return resolved

    a, b = resolved.casefold(), named.casefold()
    if a == b or b in a or a in b:
        return resolved
    return f"{resolved} ({named})"


def probes(h: LocationHierarchy | None, fallback: str | None = None) -> list[str]:
    """Resolution attempts, most specific first, deduplicated.

    Ordered rather than concatenated because the four passes in `geocode` reward
    precision: a bare PIN hits the exact-match pass, and `"Ulwe, Maharashtra"`
    reaches the alias pass with the state acting as a hard boundary. Handing the
    resolver one long string works too, but throws away the structure Gemini just
    spent a call recovering.
    """
    if h is None:
        h = LocationHierarchy()
    state = h.state
    ordered = [
        h.pin_code,
        _with_state(h.sector_or_ward, h.locality, state),
        _with_state(h.locality, None, state),
        _with_state(h.district_or_city, None, state),
        public_place(h),
        fallback,
    ]

    seen: set[str] = set()
    out: list[str] = []
    for candidate in ordered:
        if not candidate:
            continue
        key = candidate.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(candidate)
    return out


def _with_state(primary: str | None, secondary: str | None, state: str | None) -> str | None:
    if not primary:
        return None
    parts = [primary, secondary, state]
    return ", ".join(p for p in parts if p)
