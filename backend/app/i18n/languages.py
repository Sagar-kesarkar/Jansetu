"""Supported languages.

The track requires multilingual + voice coverage across "diverse linguistic
regions of India", so language is configuration, not code. `stt_code` is the
BCP-47 tag Google Speech-to-Text expects; `native_name` is what the citizen
sees in the picker (never show someone their own language in English).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str          # short internal code
    stt_code: str      # Google Speech-to-Text / Translation locale
    english_name: str
    native_name: str


LANGUAGES: dict[str, Language] = {
    "hi": Language("hi", "hi-IN", "Hindi", "हिन्दी"),
    "bn": Language("bn", "bn-IN", "Bengali", "বাংলা"),
    "ta": Language("ta", "ta-IN", "Tamil", "தமிழ்"),
    "te": Language("te", "te-IN", "Telugu", "తెలుగు"),
    "mr": Language("mr", "mr-IN", "Marathi", "मराठी"),
    "gu": Language("gu", "gu-IN", "Gujarati", "ગુજરાતી"),
    "kn": Language("kn", "kn-IN", "Kannada", "ಕನ್ನಡ"),
    "ml": Language("ml", "ml-IN", "Malayalam", "മലയാളം"),
    "pa": Language("pa", "pa-Guru-IN", "Punjabi", "ਪੰਜਾਬੀ"),
    "or": Language("or", "or-IN", "Odia", "ଓଡ଼ିଆ"),
    "as": Language("as", "as-IN", "Assamese", "অসমীয়া"),
    "ur": Language("ur", "ur-IN", "Urdu", "اردو"),
    "en": Language("en", "en-IN", "English", "English"),
}

DEFAULT_LANGUAGE = "hi"


def stt_code(lang: str) -> str:
    return LANGUAGES.get(lang, LANGUAGES[DEFAULT_LANGUAGE]).stt_code
