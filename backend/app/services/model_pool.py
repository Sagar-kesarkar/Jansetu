"""One Gemini call, tried across several models until one answers.

Every model call in the project goes through `generate()`. It exists for a single
reason, discovered the hard way during a rehearsal: the AI Studio free tier caps
`generate_content` at **20 requests per day per model**, and one demo run spends
that. When the cap is hit, `services.gemini` falls back to a keyword classifier —
the app keeps serving, which is Constraint 2 working exactly as intended, but the
screen quietly stops showing any AI at all. Nothing in the UI announces it. A
judge sees `confidence 0.1`, an untranslated summary, and no way to know the
pipeline was fine ten minutes earlier.

The quota is per *model*, so the fix costs nothing: seven models are seven daily
buckets. `Settings.gemini_model_chain` holds the order.

What this module is careful about:

**It only advances on errors that mean "ask someone else".** A 429 (quota), 404
(model retired for this key) or 503 (model overloaded) are properties of the
model, so the next rung is worth trying. A 400 on a malformed request, or a
schema the response cannot satisfy, will fail identically on all seven — retrying
turns one fast failure into seven slow ones and burns a request from every bucket
on the way. Those raise immediately.

**It remembers where it got to.** `_cursor` is a process-local index that only
moves forward. Without it, every call in a demo re-tries the exhausted primary
first and pays a round trip for a 429 that is already known — about two seconds
of dead air per report, on the one screen where latency is being judged. It
resets when the process restarts, so tomorrow's run starts at the primary again
and a temporary 503 does not permanently demote a good model.

**It is not a retry-with-backoff.** The SDK already retries transient network
faults inside a single model. This is escalation across models, and it deliberately
does not sleep: `RetryInfo` on a 429 asks for a 4-second wait, which is worth
honouring in a batch job and not in front of an audience when six other buckets
are full.

The last rung is not here. When every model refuses, `generate()` raises and each
caller degrades in its own way — `_fallback_extract` for extraction, `""` for
transcription, the original string for translation. That is Constraint 2: the app
runs with no key at all.
"""
from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings

log = logging.getLogger(__name__)

#: HTTP statuses that say "this model cannot serve you; another might".
#: Matched as substrings of the SDK's exception text, which carries the status in
#: its message rather than a typed field we can rely on across SDK versions.
_ESCALATE_ON = ("429", "RESOURCE_EXHAUSTED", "404", "NOT_FOUND", "503", "UNAVAILABLE")

#: How far down the chain we have already been pushed, this process. Only ever
#: moves forward; see the module docstring.
_cursor = 0


def reset_cursor() -> None:
    """Start again at the pinned model. For tests, and for a long-lived process
    that outlives a quota window."""
    global _cursor
    _cursor = 0


def current_model() -> str | None:
    """Which model the next call will try first — surfaced by `/capabilities` so
    an operator can see the pool has been pushed off its primary."""
    chain = get_settings().gemini_model_chain
    if not chain:
        return None
    return chain[min(_cursor, len(chain) - 1)]


def client() -> Any | None:
    """A genai client, or None when no key is configured.

    Imported lazily so the package still imports — and the test suite still
    runs — in an environment where `google-genai` is not installed.
    """
    settings = get_settings()
    if not settings.gemini_enabled:
        return None
    from google import genai

    return genai.Client(api_key=settings.gemini_api_key)


def generate(contents: Any, config: dict | None = None) -> Any:
    """Call `generate_content` on the first model in the chain that answers.

    Raises `RuntimeError` if no key is configured, or the last model's exception
    if every rung refuses. Callers are expected to catch and degrade — none of
    them may propagate a model failure to a citizen.
    """
    global _cursor

    api = client()
    if api is None:
        raise RuntimeError("GEMINI_API_KEY not set")

    chain = get_settings().gemini_model_chain
    if not chain:
        raise RuntimeError("No Gemini model configured")

    last: Exception | None = None
    # Start where the last escalation left us, then walk to the end. Rungs above
    # the cursor are skipped: they refused earlier in this process and asking
    # again costs a round trip to learn the same thing.
    for index in range(min(_cursor, len(chain) - 1), len(chain)):
        model = chain[index]
        try:
            resp = api.models.generate_content(model=model, contents=contents, config=config)
            if index != _cursor:
                _cursor = index
                log.warning("Gemini pool settled on %s (rung %d of %d)", model, index + 1, len(chain))
            return resp
        except Exception as exc:  # noqa: BLE001 — classified immediately below
            text = str(exc)
            if not any(marker in text for marker in _ESCALATE_ON):
                # A bad request, not a busy model. Every rung would reject it.
                raise
            last = exc
            reason = (
                "quota exhausted" if "429" in text or "RESOURCE_EXHAUSTED" in text
                else "not available on this key" if "404" in text or "NOT_FOUND" in text
                else "overloaded"
            )
            log.warning("Gemini model %s: %s — trying the next model", model, reason)

    # Every bucket is empty. Leave the cursor at the end so the callers that
    # follow fail fast into their own fallbacks instead of walking the chain again.
    _cursor = len(chain) - 1
    log.error("All %d Gemini models refused; degrading to non-model path", len(chain))
    raise last or RuntimeError("No Gemini model answered")
