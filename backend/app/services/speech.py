"""Voice intake — Gemini native audio, deliberately not Cloud Speech-to-Text.

Why: Cloud Speech-to-Text (Chirp) is a billed service and needs a Google Cloud
billing account. Gemini 2.5 Flash accepts audio inline on the free AI Studio
tier and handles Indian languages well, so one free API key covers
transcription, translation and structuring. Fewer services, no card required,
and it still satisfies the mandatory Google AI integration.

Trade-off worth stating in the pitch: dedicated ASR wins on long-form accuracy
and streaming. `transcribe()` is a single seam, so swapping in Chirp later is a
one-file change if credits become available.
"""
from __future__ import annotations

import logging

from app.config import get_settings
from app.i18n.languages import LANGUAGES, DEFAULT_LANGUAGE
from app.services import model_pool

log = logging.getLogger(__name__)

_TRANSCRIBE_PROMPT = """Transcribe this audio verbatim.

The speaker is a citizen in India describing a local infrastructure or public
service problem. They are speaking {language_name}.

Rules:
- Write the transcript in the speaker's own language and script, not English.
- Do not summarise, correct grammar, or add anything the speaker did not say.
- Keep place names exactly as pronounced.
- Return only the transcript text, nothing else.
"""

# Gemini accepts these inline; anything else should be converted client-side.
SUPPORTED_MIME = {
    "audio/webm", "audio/ogg", "audio/mpeg", "audio/mp3",
    "audio/wav", "audio/x-wav", "audio/aac", "audio/flac",
}


def transcribe(audio_bytes: bytes, language: str = "hi", mime_type: str = "audio/webm") -> str:
    """Return a transcript in the speaker's own language.

    Never raises: on any failure returns "" so the caller can fall back to text
    intake rather than losing the citizen's report.
    """
    settings = get_settings()
    if not settings.gemini_enabled:
        log.warning("GEMINI_API_KEY not set — cannot transcribe audio")
        return ""

    lang = LANGUAGES.get(language, LANGUAGES[DEFAULT_LANGUAGE])
    try:
        from google.genai import types

        resp = model_pool.generate(
            [
                _TRANSCRIBE_PROMPT.format(language_name=lang.english_name),
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
            ],
            {"temperature": 0.0},  # transcription, not interpretation
        )
        return (resp.text or "").strip()
    except Exception as exc:  # noqa: BLE001 — a demo must degrade, not crash
        log.exception("Gemini audio transcription failed: %s", exc)
        return ""
