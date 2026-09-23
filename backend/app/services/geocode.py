"""Resolve free-text place names to an LGD district code.

This is the unglamorous step that decides whether the whole platform works. A
request stored with `district_code = NULL` is not a degraded request, it is an
invisible one: `analytics/aggregate.py` joins on district, so an unresolved row
never reaches a hotspot and the citizen who filed it is unrepresented while the
API still returns them a cheerful 200.

Worse than NULL is a wrong district, and that is what the first version of this
module produced. It fuzzy-matched the citizen's text against the string
"District, State" so that naming a state would "improve the score rather than
confuse it". It did the opposite. Given

    "sector 23, ulwe, 410206 NAVI MUMBAI, MAHARASHTRA"

the shared token "Maharashtra" carried enough of the similarity that
"Navi Mumbai, Maharashtra" scored 78.3 against "Nandurbar, Maharashtra" — over
the 78 threshold — and a complaint from a Mumbai satellite city was filed
against a tribal district 400 km away. That is not a near miss. It is demand
data pointing at the wrong place, which is the one failure this project cannot
survive, because the entire pitch is that the ranking is trustworthy.

So resolution is now four ordered passes, cheapest and most certain first:

    1. PIN code      exact, six digits            → score 100
    2. Alias phrase  exact, longest match wins    → score 97
    3. District name fuzzy, state-gated           → score = name similarity
    4. Alias phrase  fuzzy, state-gated           → score = alias similarity

Three properties matter more than the passes themselves:

**A stated state is a hard boundary, not a hint.** If the text names a state, only
that state's districts are candidates. Naming Maharashtra can no longer help you
match a district in Odisha, and if nothing in Maharashtra fits, the answer is
NULL. This alone kills the Nandurbar class of error.

**Similarity is measured against the district name alone, over token windows.**
The name is scored against every same-length run of words in the input, so
"barpeta road, assam" still resolves to Barpeta at 100 while the surrounding
words neither dilute the score nor donate to it. Comparing whole strings is what
let a state name vote.

**Ties are refused.** India has an Aurangabad in Maharashtra and one in Bihar, a
Bilaspur in three states. With no state stated, a tie between districts is
reported as ambiguous and stored as NULL rather than resolved by list order.

The alias table is the part that makes this work in practice. Nobody files a
complaint using the name of their district; they name their ward, their locality
or their city, or they type a PIN code. Those live in
`data/reference/place_aliases.csv` so that extending coverage stays data — see
constraint 4 — rather than a dict in this file.

Production approach, documented for the deck: replace passes 1–2 with the India
Post PIN directory and the LGD village/tehsil hierarchy, both open data, and use
Gemini to disambiguate the ties that pass 3 currently refuses.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.db.models import District, PlaceAlias

#: Similarity a district or alias name must reach on its own merits. Higher than
#: the old 78 because the score is no longer diluted or inflated by surrounding
#: words: an honest 86 here is a stricter test than 78 was.
MATCH_THRESHOLD = 86

#: A state name has to be nearly exact to gate the candidate set, since gating on
#: a misread state would hide the correct district entirely.
STATE_THRESHOLD = 90

#: Two candidates within this many points with no state to separate them is an
#: ambiguity, not a winner.
TIE_MARGIN = 3.0

#: How narrow a place each alias kind describes. A ward is inside a locality is
#: inside a city, so when several match the same text the narrowest is the one
#: that identifies a district — see the Navi Mumbai case in pass 2.
_SPECIFICITY = {"locality": 4, "tehsil": 3, "city": 2, "alt_name": 1, "native": 1}

_PIN_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")


@dataclass
class GeoMatch:
    district_code: str | None
    district: str | None
    state: str | None
    score: float
    #: How it resolved, or why it did not. Surfaced to the citizen and to the
    #: officials' console: "we recognised Maharashtra but not Navi Mumbai" is
    #: actionable, where a blank "Not matched" invites the user to assume the
    #: platform is broken and stop filing.
    reason: str = ""
    #: Set whenever a state was recognised, including when the district was not.
    #: A half-resolved location is worth reporting; it tells us which state to
    #: add districts for next.
    matched_state: str | None = None
    #: Populated only on an ambiguous refusal, for the log and the error message.
    candidates: list[str] = field(default_factory=list)


def _norm(text: str) -> str:
    """Casefold, drop digits and punctuation, fold Latin accents, keep Indic marks.

    The mark handling is the subtle part. Python's `\\w` does not match Unicode
    combining marks, so the obvious "find runs of word characters" regex splits
    "बारपेटा" into "ब रप ट" — every vowel sign becomes a word boundary. Both sides
    of a comparison would normalise the same way so matching still worked, but
    discarding मात्रा makes genuinely different names collide, which is precisely
    the class of false positive this module was rewritten to eliminate.

    So: letters and marks are kept, everything else becomes a space — except a
    combining mark sitting on an ASCII base, which is a Latin accent and is
    folded away so "Puruliā" and "Purulia" are one token.

    Digits go too. PIN codes are matched exactly in their own pass, and leaving
    house numbers in would only give the fuzzy matcher noise to score ("23"
    against "Barmer").
    """
    out: list[str] = []
    for ch in unicodedata.normalize("NFKD", text):
        category = unicodedata.category(ch)
        if category.startswith("L"):
            out.append(ch.casefold())
        elif category.startswith("M"):
            if not (out and out[-1].isascii()):
                out.append(ch)
        else:
            out.append(" ")
    return " ".join("".join(out).split())


def _window_score(tokens: list[str], target: str) -> float:
    """Best similarity between `target` and any same-length run of `tokens`.

    Equal token counts on both sides is the whole point. `fuzz.ratio` over the
    full input would let a long address dilute a correct short name, and the
    partial_* scorers over-match in the other direction — "pune" is a perfect
    partial match for "rajpunia". Comparing "navi mumbai" against each one-word
    window is what makes the score mean "does this name appear here".
    """
    target_tokens = target.split()
    n = len(target_tokens)
    if not n:
        return 0.0
    if n > len(tokens):
        # Multi-word alias longer than the input: score against all of it, which
        # can only lose. Cheaper than special-casing and never a false positive.
        return float(fuzz.ratio(" ".join(tokens), target))
    return max(
        float(fuzz.ratio(" ".join(tokens[i:i + n]), target))
        for i in range(len(tokens) - n + 1)
    )


def _detect_state(tokens: list[str], states: set[str]) -> tuple[str | None, list[str]]:
    """The state named in the text, plus the tokens with that mention removed.

    Removing them matters. If "maharashtra" stays in the token list it goes on to
    be scored against every district name in pass 3, which is a weaker version of
    the exact bug this module was rewritten to fix: a state name contributing to a
    district's similarity. It cannot cause a false positive on its own any more —
    the gate already restricts candidates — but it inflates the score reported on
    a *failed* match, and a diagnostic that moves for reasons unrelated to the
    thing being diagnosed is worse than no diagnostic.
    """
    best, best_score, best_span = None, 0.0, (0, 0)
    for state in states:
        norm = _norm(state)
        n = len(norm.split())
        if not n:
            continue
        if n > len(tokens):
            score, span = float(fuzz.ratio(" ".join(tokens), norm)), (0, len(tokens))
        else:
            score, span = max(
                ((float(fuzz.ratio(" ".join(tokens[i:i + n]), norm)), (i, i + n))
                 for i in range(len(tokens) - n + 1)),
                key=lambda s: s[0],
            )
        if score > best_score:
            best, best_score, best_span = state, score, span
    if best_score < STATE_THRESHOLD:
        return None, tokens
    return best, tokens[:best_span[0]] + tokens[best_span[1]:]


def _pick(scored: list[tuple[float, str, str, str]], gated: bool) -> tuple | None:
    """Highest scorer above threshold, unless the top two are indistinguishable.

    `gated` means a state was named, so same-name districts in other states are
    already out of the running and a remaining tie is a genuine coincidence
    inside one state — rare enough that taking the first is defensible. Without a
    state, a tie is the Aurangabad problem and must not be guessed.
    """
    if not scored:
        return None
    scored.sort(key=lambda s: (-s[0], s[1]))
    top = scored[0]
    if top[0] < MATCH_THRESHOLD:
        return None
    if not gated and len(scored) > 1 and top[0] - scored[1][0] < TIE_MARGIN:
        if scored[1][1] != top[1]:
            return None
    return top


def resolve_district(db: Session, location_text: str | None) -> GeoMatch:
    if not location_text or not location_text.strip():
        return GeoMatch(None, None, None, 0.0, reason="no location given")

    districts = db.query(District.code, District.name, District.state).all()
    if not districts:
        return GeoMatch(None, None, None, 0.0, reason="no districts loaded")

    by_code = {code: (name, state) for code, name, state in districts}
    tokens = _norm(location_text).split()

    # ---- 1. PIN code, exact ----------------------------------------------
    # Ahead of everything else because it is the only unambiguous identifier a
    # citizen types, and it is exact: "410206" and "410205" are 83% similar and
    # in different tehsils, so this pass must never be fuzzy.
    for pin in _PIN_RE.findall(location_text):
        hit = (
            db.query(PlaceAlias.district_code)
            .filter(PlaceAlias.kind == "pin", PlaceAlias.alias == pin)
            .first()
        )
        if hit and hit[0] in by_code:
            name, state = by_code[hit[0]]
            return GeoMatch(hit[0], name, state, 100.0,
                            reason=f"PIN {pin}", matched_state=state)

    states = {state for _, _, state in districts}
    gate, tokens = _detect_state(tokens, states)
    candidate_codes = (
        {c for c, _, s in districts if s == gate} if gate else set(by_code)
    )

    # ---- 2. Alias phrase, exact ------------------------------------------
    # Most specific kind wins, longest string breaking ties within a kind. Not
    # simply "longest wins": Navi Mumbai straddles two districts, with Vashi and
    # Belapur in Thane and Ulwe and Kharghar in Raigad. For "Ulwe, Navi Mumbai"
    # the longer string is the city and the correct answer is the locality.
    aliases = (
        db.query(PlaceAlias.alias, PlaceAlias.district_code, PlaceAlias.kind)
        .filter(PlaceAlias.kind != "pin")
        .all()
    )
    usable = [a for a in aliases if a[1] in candidate_codes]
    haystack = " ".join(tokens)
    exact = [
        a for a in usable
        if re.search(rf"(?<!\w){re.escape(a[0])}(?!\w)", haystack)
    ]
    if exact:
        alias, code, kind = max(exact, key=lambda a: (_SPECIFICITY.get(a[2], 0), len(a[0])))
        name, state = by_code[code]
        return GeoMatch(code, name, state, 97.0,
                        reason=f"{kind} '{alias}'", matched_state=state)

    # ---- 3. District name, fuzzy, inside the gate ------------------------
    scored = [
        (_window_score(tokens, _norm(name)), code, name, state)
        for code, name, state in districts
        if code in candidate_codes
    ]
    hit = _pick(scored, gated=gate is not None)
    if hit:
        score, code, name, state = hit
        return GeoMatch(code, name, state, score,
                        reason="district name", matched_state=state)

    # ---- 4. Alias phrase, fuzzy ------------------------------------------
    # Catches the typo an exact pass cannot: "ulve" for Ulwe, "panwel" for Panvel.
    alias_scored = [
        (_window_score(tokens, alias), code, by_code[code][0], by_code[code][1])
        for alias, code, _ in usable
    ]
    hit = _pick(alias_scored, gated=gate is not None)
    if hit:
        score, code, name, state = hit
        return GeoMatch(code, name, state, score,
                        reason="approximate locality name", matched_state=state)

    # ---- refuse, and say which kind of refusal it was --------------------
    best = max([s[0] for s in scored + alias_scored], default=0.0)
    near = sorted({s[2] for s in scored + alias_scored if s[0] >= MATCH_THRESHOLD})
    if near:
        return GeoMatch(None, None, None, best, matched_state=gate,
                        candidates=near,
                        reason=f"ambiguous between {' and '.join(near)}")
    if gate:
        return GeoMatch(None, None, None, best, matched_state=gate,
                        reason=f"{gate} recognised, but no covered district matched")
    return GeoMatch(None, None, None, best, reason="no state or district recognised")
