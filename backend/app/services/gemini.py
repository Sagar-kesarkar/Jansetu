"""Gemini integration — the mandatory Google AI component.

Two distinct jobs, deliberately kept separate:

1. `extract_request` turns one messy multilingual utterance into a typed record.
   This is the hard part of the intake problem: a citizen says "paani nahi aa
   raha teen mahine se, bacche school nahi ja rahe" and we need a category, an
   urgency, and a place. Rules and keyword matching fall apart across 13
   languages; a model with a constrained JSON schema does not. `i18n/keywords.py`
   is the keyword version, kept only as the degraded no-key path — comparing the
   two is a fair way to see what the model is actually buying.

2. `write_policy_brief` turns a ranked row of numbers into prose a policymaker
   will actually read. The numbers come from our own scoring, never from the
   model — the model narrates the evidence, it does not invent it. That
   separation is what makes the recommendation auditable.
"""
from __future__ import annotations

import json
import logging

from app.config import get_settings
from app.i18n.keywords import classify
from app.models.schemas import (
    Classification,
    ExtractedIssue,
    ExtractedRequest,
    ExtractedSubmission,
    LocationHierarchy,
)
from app.services import model_pool
from app.models.taxonomy import CATEGORY_CODES, category_or_other

log = logging.getLogger(__name__)

_LOCATION_SCHEMA = {
    "type": "object",
    "properties": {
        "state": {"type": "string"},
        "district_or_city": {"type": "string"},
        "locality": {"type": "string"},
        "sector_or_ward": {"type": "string"},
        "pin_code": {"type": "string"},
    },
}

#: One issue inside a submission. `category` is constrained to the taxonomy so an
#: unmapped sector cannot reach the ranking; everything else is validated again by
#: `ExtractedIssue` before a row is written, because a schema is a request to the
#: model and a Pydantic model is a guarantee.
_ISSUE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "category": {"type": "string", "enum": CATEGORY_CODES + ["OTHER"]},
        "summary_en": {"type": "string"},
        "summary_native": {"type": "string"},
        "urgency": {"type": "integer", "minimum": 1, "maximum": 5},
        "affected_estimate": {"type": "integer"},
        "location_text": {"type": "string"},
        "location": _LOCATION_SCHEMA,
        "location_applies_from_shared_context": {"type": "boolean"},
        "requires_clarification": {"type": "boolean"},
        "clarification_question": {"type": "string"},
        "image_verification": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["category", "summary_en", "summary_native", "urgency", "confidence"],
}

_SUBMISSION_SCHEMA = {
    "type": "object",
    "properties": {
        "classification": {
            "type": "string",
            "enum": [c.value for c in Classification],
        },
        "detected_language": {"type": "string"},
        "shared_location_text": {"type": "string"},
        "shared_location": _LOCATION_SCHEMA,
        "issues": {"type": "array", "items": _ISSUE_SCHEMA},
        "triage_reason": {"type": "string"},
        "clarification_question": {"type": "string"},
        "reply_native": {"type": "string"},
    },
    #: `classification` is required rather than defaulted for the same reason
    #: `is_valid_grievance` was: a model that omits it would be read as the safe
    #: value, and triage that silently never fires looks identical to triage that
    #: finds nothing wrong.
    "required": ["classification", "issues"],
}

_EXTRACTION_PROMPT = """You are processing a development request from a citizen in India.

The message may be in any Indian language, may be transliterated, may contain
local place names, and may be spoken rather than written. Do not correct or
moralise — extract.

FIRST decide what the message is, and put it in `classification`:

- VALID_SINGLE_ISSUE — one actionable local problem, described well enough to file.
- VALID_MULTI_ISSUE — two or more separately actionable problems in one message.
- MISSING_LOCATION — a real problem, but the message names no place at all. Still
  return the issue; it will be filed and the citizen asked where.
- NEEDS_CLARIFICATION — you can tell this is a complaint but not what help is
  being asked for. Return an empty `issues` list and one specific question.
- INVALID_OR_SPAM — not a civic message at all.

You are judging whether the message is understandable and processable. You are NOT
judging whether the reported event actually happened. Nothing you return is
evidence that a borewell is dry or a road is broken — only that somebody said so.

INVALID_OR_SPAM is the narrowest of the five and is limited to: an empty or
meaningless string, repeated random characters, obvious advertising for an
unrelated product or service, content with no identifiable civic need at all, or
clearly malicious input. A genuine complaint that is missing information is
NEEDS_CLARIFICATION or MISSING_LOCATION — never INVALID_OR_SPAM. Judge the message,
not the messenger; when in doubt, treat it as valid. Specifically, these are all
VALID and must not be flagged:
  * a complaint written in one short fragment — "no water 3 days"
  * a complaint with no place named, misspelt, or in a mix of languages
  * a complaint that is angry, blunt, or accuses a department of negligence
  * a complaint about something small, or one you think is somebody else's job
  * a message raising several different problems at once — that is VALID_MULTI_ISSUE
A wrongly flagged message is a citizen who will never know their report was set
aside. Err towards valid.

SPLITTING. Put each separately actionable problem in its own entry in `issues`.
The test is whether it would be assigned, tracked and resolved on its own: bad
drinking water and potholes go to two departments and are two issues. A cause, a
consequence, a supporting detail or a restatement of the same problem is ONE
issue — do not split "the road is broken so the school bus cannot come" into two.
Return at most {max_issues} issues; if the message genuinely raises more, keep the
{max_issues} most serious and describe the rest inside the last summary.

For each issue return:
- title: a short label, under 60 characters, e.g. "Potholes on the main road"
- category: the single best fit from the allowed list
- summary_en: one neutral sentence in English, for the policymaker
- summary_native: one sentence in the SAME language as the input, confirming
  back to the citizen what was understood
- urgency: 1 routine, 3 affects daily life, 5 immediate risk to health or safety
- affected_estimate: number of people affected, ONLY if the message states or
  clearly implies it; otherwise omit
- location_text / location: ONLY when this issue names a place of its own that is
  different from the place the whole message is about. Otherwise omit both and set
  location_applies_from_shared_context to true.
- requires_clarification and clarification_question: only if this one issue is
  unintelligible while the others are fine.
- confidence: your confidence that the category is right, 0 to 1

LOCATION. If the message states one place that the whole complaint is about, put
it in `shared_location_text` (verbatim) and `shared_location` (decomposed). Omit a
place that is only referred to and not named — "our village", "my area", "this
ward" are not names, and returning them prevents any district match. Never guess,
infer or complete a place name that is not in the message: an issue with no usable
location is a normal outcome and is handled by asking the citizen.

`shared_location` and each issue's `location` break a place into administrative
levels. Omit any level the message does not state — do NOT infer, and do NOT
repeat the examples below. Levels:
    state            e.g. Maharashtra
    district_or_city e.g. Navi Mumbai
    locality         the neighbourhood or village, e.g. Ulwe
    sector_or_ward   e.g. Sector 23, or Ward 14
    pin_code         the 6-digit postal code, digits only
  PRIVACY RULE, absolute: sector_or_ward is the finest level permitted. Never
  return a house, flat, plot, door, survey, building, society or street number in
  any field, even when the citizen supplies one. Report the ward it sits in and
  discard the rest.

ALSO RETURN:
- detected_language: the BCP-47-ish code of the language actually used, e.g. hi, ta
- triage_reason: ONLY for INVALID_OR_SPAM. One short sentence, in English, naming
  what the message actually appears to be — "a test message with no problem
  described", "an advertisement for a private service". An officer reads this to
  decide whether to overrule you, so be specific rather than categorical.
- clarification_question: ONLY for NEEDS_CLARIFICATION. One specific question, in
  the citizen's own language.
- reply_native: for INVALID_OR_SPAM or NEEDS_CLARIFICATION only — one polite
  sentence in the citizen's own language inviting them to describe the local
  problem they need help with. Never accusatory.

Citizen message (language={language}):
{text}
{location_block}"""

_LOCATION_BLOCK = """
Location as separately supplied by the citizen (a form field or a channel
profile). Decompose THIS as well as anything stated in the message, and prefer it
where the two disagree about a level — it was typed deliberately, whereas a place
mentioned in passing may be somewhere the citizen is describing rather than
reporting from:
{location_text}
"""

_IMAGE_INSTRUCTION = """
An image has been attached by the citizen. Also return:
- image_verification: one or two sentences describing the infrastructure problem
  visible in the image and the condition of what you see. Be concrete and
  physical — "an unpaved road surface with standing water and exposed potholes
  roughly a foot deep" — because this text is corroboration an official will act
  on, and it is what travels: the description reaches the dashboard and the
  citizen-facing API, while the photograph itself stays behind the officials'
  console as case evidence.

  If the image does not show an infrastructure problem, or does not correspond to
  the complaint, say so plainly rather than inventing agreement. A photograph
  that contradicts the text is useful information.

  Describe the infrastructure only. Do not describe people, faces, clothing,
  vehicle number plates, house numbers, name boards or anything else that could
  identify an individual or a household, and do not transcribe such text if it
  appears in the frame.
"""


def _client():
    """Kept as the one place that answers "is a model reachable at all?".

    The call itself now goes through `model_pool.generate`, which owns model
    selection — see that module for why one call may touch several models.
    """
    return model_pool.client()


def extract_submission(
    text: str,
    language: str = "hi",
    *,
    location_text: str | None = None,
    image: bytes | None = None,
    image_mime: str = "image/jpeg",
) -> ExtractedSubmission:
    """Structure one citizen message into one *or more* issues.

    One message, one model call, N issues out. A citizen who says "the water smells
    and the road has potholes" has raised two things that go to two departments and
    get resolved on two different days, and filing that as a single record means one
    of them is quietly lost — whichever the officer does not act on. So the split
    happens here, at the only point where the whole utterance is still available.

    What this function does *not* do is equally deliberate. It does not mint tokens,
    write rows, resolve districts or decide what may enter an officer's queue —
    `pipeline.ingest_submission` does all of that from the validated result. The
    model reads the message; the backend makes every consequential decision. That
    boundary is constraint 3 and it is what lets us say no number in a ranking came
    out of a language model.

    Falls back to a single-issue keyword record if Gemini is unavailable, so the
    pipeline never drops a request.

    `location_text` is the address the citizen typed into the form, passed in as a
    labelled second input rather than concatenated onto the message. Without it
    the model only sees places mentioned in the complaint, and a citizen who
    writes "the road in Sector 23 is broken" and fills the address field
    separately gets a hierarchy containing the ward and nothing above it — which
    resolves to no district and shows an officer a location too coarse to dispatch.

    `image` is read and not written anywhere by this function; retention is the
    pipeline's decision — see `services/photos.py`.
    """
    client = _client()
    if client is None:
        log.warning("GEMINI_API_KEY not set — using fallback extraction")
        return _fallback_submission(text, language, image=image)

    settings = get_settings()
    prompt = _EXTRACTION_PROMPT.format(
        language=language,
        text=text,
        max_issues=settings.max_issues_per_submission,
        location_block=(
            _LOCATION_BLOCK.format(location_text=location_text) if location_text else ""
        ),
    )
    contents: list = [prompt]
    if image:
        from google.genai import types
        contents = [
            prompt + _IMAGE_INSTRUCTION,
            types.Part.from_bytes(data=image, mime_type=image_mime),
        ]

    try:
        resp = model_pool.generate(
            contents,
            {
                "response_mime_type": "application/json",
                "response_schema": _SUBMISSION_SCHEMA,
                "temperature": 0.1,  # extraction, not creativity
            },
        )
        return _parse_submission(json.loads(resp.text), text, language, image=image)
    except Exception as exc:  # noqa: BLE001 — a demo must degrade, not crash
        log.exception("Gemini extraction failed: %s", exc)
        return _fallback_submission(text, language, image=image)


def _parse_submission(
    data: dict, text: str, language: str, *, image: bytes | None = None
) -> ExtractedSubmission:
    """Turn a raw model response into a validated `ExtractedSubmission`.

    Separate from the call so the normalisations below are testable without a key,
    and because every one of them exists to close a gap between what the schema
    permits and what the rest of the system can survive. In order:

    * a classification the enum does not contain becomes single-issue rather than an
      exception — an unrecognised label must not lose a citizen's report;
    * `issues` is truncated to the configured maximum, because "at most five" in a
      prompt is a request and the slice is the guarantee;
    * a valid classification that came back with no issues is downgraded to
      NEEDS_CLARIFICATION, since there is nothing to file and pretending otherwise
      would write an empty docket;
    * a multi-issue label with one issue is corrected downwards and vice versa, so
      `issue_count` and the label can never disagree on the confirmation screen;
    * `image_verification` is dropped when no bytes were sent, because a model given
      no image sometimes narrates one anyway;
    * `triage_reason` is dropped unless the message was actually flagged.
    """
    settings = get_settings()

    raw_class = str(data.get("classification") or "").strip().upper()
    try:
        classification = Classification(raw_class)
    except ValueError:
        log.warning("Unknown classification %r from Gemini — treating as valid", raw_class)
        classification = Classification.VALID_SINGLE_ISSUE

    issues: list[ExtractedIssue] = []
    for raw in (data.get("issues") or [])[: settings.max_issues_per_submission]:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        item["category"] = category_or_other(item.get("category"))
        item["location"] = (
            LocationHierarchy(**item["location"]) if item.get("location") else None
        )
        if not image:
            item.pop("image_verification", None)
        try:
            issues.append(ExtractedIssue(**item))
        except Exception as exc:  # noqa: BLE001
            # One malformed issue must not cost the others. A submission that loses
            # every issue this way falls through to the empty-issues rule below.
            log.warning("Discarding malformed issue from Gemini: %s", exc)

    valid = classification in (
        Classification.VALID_SINGLE_ISSUE,
        Classification.VALID_MULTI_ISSUE,
        Classification.MISSING_LOCATION,
    )
    if valid and not issues:
        classification = Classification.NEEDS_CLARIFICATION
    elif classification is Classification.VALID_MULTI_ISSUE and len(issues) == 1:
        classification = Classification.VALID_SINGLE_ISSUE
    elif classification is Classification.VALID_SINGLE_ISSUE and len(issues) > 1:
        classification = Classification.VALID_MULTI_ISSUE

    return ExtractedSubmission(
        classification=classification,
        detected_language=data.get("detected_language") or language,
        shared_location=(
            LocationHierarchy(**data["shared_location"])
            if data.get("shared_location")
            else None
        ),
        shared_location_text=data.get("shared_location_text") or None,
        issues=issues,
        triage_reason=(
            data.get("triage_reason")
            if classification is Classification.INVALID_OR_SPAM
            else None
        ),
        clarification_question=(
            data.get("clarification_question")
            if classification is Classification.NEEDS_CLARIFICATION
            else None
        ),
        reply_native=data.get("reply_native") or None,
    )


def extract_request(
    text: str,
    language: str = "hi",
    *,
    location_text: str | None = None,
    image: bytes | None = None,
    image_mime: str = "image/jpeg",
) -> ExtractedRequest:
    """Single-issue projection of `extract_submission`, kept for the callers that
    genuinely want one record.

    Two of them: the WhatsApp photo-evidence path, which is adding a picture to a
    complaint that already exists and so has nothing to split, and the fallback
    tests. It shares the one prompt and the one call rather than keeping a second
    schema alive — two extraction prompts drifting apart is how the no-key path
    ends up triaging differently from the real one.
    """
    submission = extract_submission(
        text,
        language,
        location_text=location_text,
        image=image,
        image_mime=image_mime,
    )
    return collapse(submission, text)


def collapse(submission: ExtractedSubmission, text: str) -> ExtractedRequest:
    """First issue of a submission as a flat `ExtractedRequest`.

    Also the honest answer for a submission with no issues at all: rather than
    raising, it returns the citizen's own words as the summary at fallback
    confidence, so a caller expecting one record always gets one.
    """
    shared_text = submission.shared_location_text
    shared = submission.shared_location or LocationHierarchy()

    if not submission.issues:
        return ExtractedRequest(
            category=classify(text),
            summary_en=text[:200],
            summary_native=text[:200],
            urgency=3,
            affected_estimate=None,
            location_text=shared_text,
            confidence=0.1,
            location=shared,
            image_verification=None,
            is_valid_grievance=submission.classification
            is not Classification.INVALID_OR_SPAM,
            triage_reason=submission.triage_reason,
        )

    first = submission.issues[0]
    return ExtractedRequest(
        category=first.category,
        summary_en=first.summary_en,
        summary_native=first.summary_native,
        urgency=first.urgency,
        affected_estimate=first.affected_estimate,
        location_text=first.location_text or shared_text,
        confidence=first.confidence,
        location=first.location or shared,
        image_verification=first.image_verification,
        is_valid_grievance=submission.classification
        is not Classification.INVALID_OR_SPAM,
        triage_reason=submission.triage_reason,
    )


def _fallback_submission(
    text: str, language: str, *, image: bytes | None = None
) -> ExtractedSubmission:
    """No key, exhausted quota, or a malformed response. Keyword extraction is a
    poor substitute for the model — it cannot read transliteration, infer urgency
    or find a place name — but it keeps the sector right often enough that the
    dashboard stays meaningful, which "everything is OTHER" did not.

    `confidence` stays pinned at 0.1 even on a confident keyword hit. The number
    is being read as provenance, not certainty: 0.1 on screen means "no model
    touched this". Raising it for a good match would hide exactly the thing the
    UI is meant to surface.

    An attached image is acknowledged and not described. There is no offline
    vision path, and inventing a description would be the one failure mode worse
    than having none — an official acting on corroboration that no model ever
    produced. `has_photo` on the row records that a photograph existed, so the
    console can say "attached, not analysed" rather than "no photograph".

    **Always exactly one issue, and never triaged.** Keyword matching cannot tell
    "test test test" from a terse complaint, and it certainly cannot tell where one
    problem ends and the next begins — a split guessed from keywords would file two
    dockets for one pothole. So the no-key path returns VALID_SINGLE_ISSUE for
    everything: the invalid queue stays visibly empty and nothing is ever split
    without a model, which is the honest reading of "no model was available".
    """
    return ExtractedSubmission(
        classification=Classification.VALID_SINGLE_ISSUE,
        detected_language=language,
        # Deliberately empty rather than regex-parsed. `place.probes` falls
        # through to the raw location string, which the four-pass geocoder
        # already handles — including exact PIN matching — so a hand-rolled
        # second parser here would add a way for the two paths to disagree.
        shared_location=None,
        shared_location_text=None,
        issues=[
            ExtractedIssue(
                title=None,
                category=classify(text),
                summary_en=text[:200],
                summary_native=text[:200],
                # 3 = "affects daily life". Urgency is genuinely not recoverable
                # from keywords, so the fallback declines to guess and returns the
                # midpoint.
                urgency=3,
                affected_estimate=None,
                location_text=None,
                location=None,
                confidence=0.1,
                image_verification=None,
            )
        ],
    )


def _fallback_extract(
    text: str, language: str, *, image: bytes | None = None
) -> ExtractedRequest:
    """Flat projection of `_fallback_submission`. See there for why nothing on this
    path is triaged or split."""
    return collapse(_fallback_submission(text, language, image=image), text)


_BRIEF_PROMPT = """Write a short briefing note for a national infrastructure
planning official about one recommended project.

Rules:
- Use ONLY the figures given below. Do not add statistics, costs or dates.
- Three short paragraphs, no bullet points, no headings.
- Paragraph 1: what citizens are reporting and at what volume.
- Paragraph 2: what the official coverage and funding data shows, including
  whether current allocation looks adequate.
- Paragraph 3: what to do next and which scheme it sits under.
- Neutral civil-service register. No adjectives like "urgent" unless the
  urgency figure supports it.

Evidence:
{evidence}
"""


def write_policy_brief(evidence: dict) -> str | None:
    """Narrate a recommendation. Returns None if Gemini is unavailable — the
    dashboard shows the structured evidence either way."""
    try:
        resp = model_pool.generate(
            _BRIEF_PROMPT.format(evidence=json.dumps(evidence, indent=2, default=str)),
            {"temperature": 0.3},
        )
        return resp.text
    except Exception as exc:  # noqa: BLE001
        log.exception("Gemini brief generation failed: %s", exc)
        return None
