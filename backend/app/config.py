"""Central configuration. Everything comes from the environment so the same
image runs locally and on Cloud Run without code changes."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"


class Settings(BaseSettings):
    # env_file is absolute on purpose. Every Makefile target (`api`, `seed`,
    # `test`) runs from backend/, but the README tells you to create .env at the
    # repo root — so a relative ".env" loads nothing and the app silently runs
    # keyless with Gemini disabled. Both locations are accepted; the repo-root
    # file is listed last so it wins.
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / "backend" / ".env", REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Google AI ---
    gemini_api_key: str = ""
    # This pin has had to move twice, both times because the free tier moved under
    # it, and both times verified by calling the model rather than by reading a
    # changelog.
    #
    #   gemini-2.0-flash      the original pin. Now 404 NOT_FOUND — retired, not
    #                         deprecated, so there is no grace period to plan around.
    #   gemini-2.5-flash      the replacement, and correct for months. Its free-tier
    #                         allowance is *20 generate requests per day per model*
    #                         (quotaId GenerateRequestsPerDayPerProjectPerModel-
    #                         FreeTier). Twenty is roughly one rehearsal: extraction
    #                         is one call per report and each reply translation is
    #                         another, so a demo run plus a couple of test reports
    #                         exhausts it and everything afterwards silently takes
    #                         the fallback path — reports stop being summarised in
    #                         English and replies stop being translated.
    #   gemini-2.5-flash-lite would have had its own daily bucket, but this key gets
    #                         404 "no longer available to new users".
    #   gemini-3.5-flash      current pin. Its own quota bucket, callable on this
    #                         key, and it does both jobs this project needs:
    #                         constrained-JSON extraction and inline audio
    #                         transcription.
    #
    # Still deliberately not `gemini-flash-latest`. An alias would survive the next
    # retirement, but it resolves to whatever is under load that day — and
    # gemini-3.7-flash answered 503 "experiencing high demand" while this was being
    # verified. A demo that fails in front of judges is worse than a pin to bump.
    gemini_model: str = "gemini-3.5-flash"

    # Models tried, in order, when `gemini_model` returns 429 / 404 / 503.
    #
    # This is the single most important line for whether a live demo shows real
    # multilingual AI or keyword matching. The free tier's hard limit is
    #
    #     GenerateRequestsPerDayPerProjectPerModel-FreeTier = 20
    #
    # and the operative word is *PerModel*. Twenty requests is roughly one
    # rehearsal: each citizen report costs one call, a voice note costs two, and
    # a per-card policy brief costs another. Exhausting it does not break the app
    # — `_fallback_extract` keeps it serving — but it silently replaces the thing
    # being demonstrated with a keyword classifier, which is the worst possible
    # failure because nothing on screen says so.
    #
    # Because the bucket is per model, seven models are seven buckets: ~140 free
    # calls a day instead of 20, with no billing account and no second key. That
    # is the whole reason this list exists.
    #
    # Order is newest-and-best first, descending to lighter models: a request
    # that falls through five rungs should get slower and cheaper, never wrong.
    # Every entry must be multimodal, because the same pool serves inline audio
    # transcription and photo reading — a text-only rung would silently drop a
    # voice note. That is why `gemma-4-31b-it` is absent despite answering fine
    # on text, and why the *-image, *-tts and deep-research models are absent too.
    #
    # All seven were verified callable on a free key with constrained JSON output.
    # `gemini-2.5-flash-lite` is deliberately absent: 404 "no longer available to
    # new users" on a key created now.
    gemini_model_fallbacks: str = (
        "gemini-3.6-flash,"
        "gemini-3.7-flash,"
        "gemini-3-flash-preview,"
        "gemini-2.5-flash,"
        "gemini-3.5-flash-lite,"
        "gemini-3.1-flash-lite"
    )
    # Optional — only needed if you later migrate to billed Google Cloud
    # services. The free path uses the Gemini API key alone.
    google_cloud_project: str = ""

    # --- App & Public URLs ---
    database_url: str = "sqlite:///./jansetu.db"
    cors_origins: str = "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174"
    log_level: str = "INFO"
    public_base_url: str = "http://localhost:8080"
    officials_console_origin: str = "http://localhost:5174"

    # --- Messaging & Telephony Channels ---
    # Secret used to pseudonymise inbound channel identifiers (see
    # services/privacy.py). Left empty, a random per-process value is used:
    # safe by default, at the cost of refs not being stable across restarts.
    citizen_ref_salt: str = ""
    ivr_prompt_dir: str = str(DATA_DIR / "ivr_prompts")
    # Where a citizen's photograph is retained so an officer can look at it.
    #
    # Deliberately outside any directory the app serves statically. The bytes are
    # reachable only through `GET /requests/{id}/photo`, which is the officials'
    # console route — so the file is behind the same door as the rest of the case
    # rather than sitting at a guessable URL. See `services/evidence.py` for what
    # that costs and why the trade was made.
    evidence_dir: str = str(DATA_DIR / "evidence")
    max_audio_bytes: int = 10 * 1024 * 1024  # 10 MB
    max_image_bytes: int = 10 * 1024 * 1024  # 10 MB

    #: Ceiling on how many separate requests one message may be split into.
    #:
    #: The prompt asks for at most this many and the pipeline slices to it anyway,
    #: because a prompt is a request and a slice is a guarantee. Five is chosen to be
    #: comfortably above real behaviour — a citizen listing three or four problems in
    #: one WhatsApp message is ordinary, twenty is a model that has started splitting
    #: sentences instead of issues, and the cap is what stops that from becoming
    #: twenty dockets and twenty tokens on an officer's queue.
    max_issues_per_submission: int = 5

    # --- Exotel IVR & SMS (Production) ---
    exotel_account_sid: str = ""
    exotel_api_key: str = ""
    exotel_api_token: str = ""
    exotel_exophone: str = ""
    exotel_sms_sender_id: str = "JANSTU"
    exotel_region: str = "mumbai"  # mumbai or singapore
    exotel_app_id: str = ""
    exotel_webhook_secret: str = ""
    exotel_stream_enabled: bool = False

    # --- India DLT SMS Compliance ---
    dlt_entity_id: str = ""
    dlt_success_template_id: str = ""
    dlt_location_template_id: str = ""
    dlt_failure_template_id: str = ""
    dlt_status_template_id: str = ""

    # --- Meta WhatsApp Business Cloud API ---
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = "local_dev_token"
    whatsapp_app_secret: str = ""
    whatsapp_graph_api_version: str = "v21.0"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def gemini_model_chain(self) -> list[str]:
        """The pinned model followed by its fallbacks, de-duplicated, in order.

        De-duplication matters because the primary is usually also worth keeping
        in the fallback string when someone edits `GEMINI_MODEL` in `.env` — a
        chain that tries the same exhausted model twice wastes a round trip and
        two seconds of demo time on a 429 that is already known.
        """
        seen: dict[str, None] = {}
        for name in [self.gemini_model, *self.gemini_model_fallbacks.split(",")]:
            name = name.strip()
            if name:
                seen.setdefault(name, None)
        return list(seen)


@lru_cache
def get_settings() -> Settings:
    return Settings()
