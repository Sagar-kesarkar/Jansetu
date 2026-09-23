"""Translation via Gemini — again avoiding a billed service.

Mostly a safety net: `extract_request` already returns an English summary and a
native-language confirmation in one call, which is cheaper than a second round
trip. This helper exists for UI strings and for the fallback extraction path.
"""
from __future__ import annotations

import logging

from app.config import get_settings
from app.i18n.languages import LANGUAGES, DEFAULT_LANGUAGE
from app.services import model_pool

log = logging.getLogger(__name__)


def translate(text: str, target: str = "en", source: str | None = None) -> str:
    settings = get_settings()
    if not settings.gemini_enabled or not text:
        return text

    tgt = LANGUAGES.get(target, LANGUAGES["en"]).english_name
    src = LANGUAGES.get(source or "", LANGUAGES[DEFAULT_LANGUAGE]).english_name if source else None
    instruction = (
        f"Translate the following text {'from ' + src + ' ' if src else ''}into {tgt}. "
        "Return only the translation, no notes or alternatives.\n\n" + text
    )
    try:
        resp = model_pool.generate(instruction, {"temperature": 0.0})
        return (resp.text or text).strip()
    except Exception as exc:  # noqa: BLE001
        log.exception("Translation failed: %s", exc)
        return text
