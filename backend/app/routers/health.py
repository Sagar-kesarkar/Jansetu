from fastapi import APIRouter

from app.config import get_settings
from app.i18n.languages import LANGUAGES
from app.models.taxonomy import CATEGORY_CODES
from app.services import model_pool

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/capabilities")
def capabilities() -> dict:
    """Which Google AI capabilities are live, plus language and category
    coverage. Useful during a demo — it answers "is the AI actually wired up?"
    without anyone reading the logs, and it documents that the whole stack runs
    on one free Gemini API key."""
    s = get_settings()
    chain = s.gemini_model_chain
    active = model_pool.current_model()
    return {
        "google_ai": {
            "provider": "Gemini API (AI Studio free tier)",
            "model": s.gemini_model,
            # Which model the next call will actually use. It differs from `model`
            # once the pinned one has been pushed off by a 429, and that is the
            # single most useful thing to know mid-demo: the free tier caps
            # generate_content at 20/day *per model*, so this field answers "how
            # many buckets have we already burned?" without reading the logs.
            "active_model": active,
            "model_chain": chain,
            "model_chain_position": (chain.index(active) + 1) if active in chain else None,
            "enabled": s.gemini_enabled,
            "used_for": [
                "speech-to-text (native audio input)",
                "translation",
                "structured extraction of citizen requests",
                "policy brief generation",
            ],
            "billing_account_required": False,
        },
        "languages": [
            {"code": l.code, "name": l.english_name, "native": l.native_name}
            for l in LANGUAGES.values()
        ],
        "categories": CATEGORY_CODES,
    }
