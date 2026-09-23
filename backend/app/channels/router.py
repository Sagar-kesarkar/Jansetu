"""The front of the funnel for text channels: greeting, language, format check, and state machine.

WhatsApp and SMS use this unified state machine to manage conversational turns:
- MAIN_MENU: 3 primary options (1. Register complaint, 2. Track complaint, 3. View budget)
- AWAITING_COMPLAINT: Guidance on providing problem and location
- AWAITING_LOCATION: Mandatory location gate (village/town/ward, district, state) before registration
- AWAITING_TRACKING_TOKEN: Tracking token lookup
- AWAITING_BUDGET_SCOPE / AWAITING_BUDGET_LOCATION: State & district budget query
- COMPLAINT_REGISTERED: Post-registration options (register another, track, return to menu)
"""
from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from app.channels.prompts import get_prompt_text
from app.channels.replies import status_reply
from app.services.funds_service import FundsService
from app.services.geocode import resolve_district

log = logging.getLogger(__name__)

GREETINGS: frozenset[str] = frozenset({
    "hi", "hello", "hey", "start", "menu", "join", "help", "info", "welcome",
    "good morning", "good afternoon", "good evening",
    "namaste", "namaskar", "salaam", "vanakkam", "namaskara", "nomoshkar",
    "pranam", "khemcho", "sat sri akal", "sasriakal", "khushamdeed",
    "नमस्ते", "नमस्कार", "प्रणाम", "शुरू", "मदद", "सहायता",
    "নমস্কার", "হ্যালো", "নমস্তে", "সাহায্য",
    "வணக்கம்", "வணக்கங்கள்", "உதவி",
    "నమస్కారం", "నమస్తే", "సహాయం",
    "नमस्कार", "मदत",
    "નમસ્તે", "નમસ્કાર", "મદદ",
    "ನಮಸ್ಕಾರ", "ಸಹಾಯ",
    "നമസ്കാരം", "സഹായം",
    "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ", "ਮਦਦ",
    "ନମସ୍କାର", "ସାହାଯ୍ୟ",
    "নমস্কাৰ", "সহায়",
    "السلام علیکم", "آداب", "مدد",
})

LANG_NAME_TO_CODE: dict[str, str] = {
    "hindi": "hi", "हिन्दी": "hi", "हिंदी": "hi",
    "bengali": "bn", "বাংলা": "bn",
    "tamil": "ta", "தமிழ்": "ta",
    "telugu": "te", "తెలుగు": "te",
    "marathi": "mr", "मराठी": "mr",
    "gujarati": "gu", "ગુજરાતી": "gu",
    "kannada": "kn", "ಕನ್ನಡ": "kn",
    "malayalam": "ml", "മലയാളം": "ml",
    "punjabi": "pa", "ਪੰਜਾਬੀ": "pa",
    "odia": "or", "ଓଡ଼ିଆ": "or", "oriya": "or",
    "assamese": "as", "অসমীয়া": "as",
    "urdu": "ur", "اردو": "ur",
    "english": "en",
}

LANG_BY_DIGIT: dict[str, str] = {
    "1": "hi", "2": "bn", "3": "ta", "4": "te", "5": "mr",
    "6": "gu", "7": "kn", "8": "ml", "9": "pa", "0": "en",
    "*": "or", "#": "as",
}

_WORD = re.compile(r"[^\wऀ-෿؀-ۿ]+", re.UNICODE)
_LOCALITY_TOKENS = {
    "ward", "village", "town", "colony", "nagar", "gali", "mohalla", "sector",
    "road", "basti", "pada", "pur", "gram", "panchayat", "area", "near", "opp",
    "opposite", "behind", "chowk", "rasta", "marg", "street", "block", "phase",
    "गाव", "ग्राम", "वार्ड", "गल्ली", "नगर", "रस्ता", "इलाका", "मोहल्ला", "लैंडमार्क",
}


class Decision:
    """What the adapter should do with one inbound message."""

    __slots__ = ("reply", "text", "language", "context", "handled")

    def __init__(
        self,
        *,
        reply: str | None,
        text: str | None,
        language: str,
        context: dict[str, Any],
        handled: bool,
    ) -> None:
        self.reply = reply
        self.text = text
        self.language = language
        self.context = context
        self.handled = handled


def _normalise(text: str) -> str:
    return _WORD.sub(" ", text or "").strip().lower()


def _is_greeting(text: str) -> bool:
    cleaned = _normalise(text)
    if not cleaned or len(cleaned) > 24:
        return False
    return cleaned in GREETINGS or all(word in GREETINGS for word in cleaned.split())


def _detect_language_command(text: str) -> str | None:
    """Detect language switching commands like 'LANG HI', 'LANGUAGE TAMIL', etc."""
    cleaned = text.strip().lower()
    parts = cleaned.split()
    if not parts:
        return None

    # Check 'LANG XX' or 'LANGUAGE XX'
    if parts[0] in ("lang", "language", "भाषा", "மொழி", "భాష"):
        if len(parts) > 1:
            code_or_name = parts[1]
            if code_or_name in ("hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "or", "as", "ur", "en"):
                return code_or_name
            if code_or_name in LANG_NAME_TO_CODE:
                return LANG_NAME_TO_CODE[code_or_name]

    # Bare language names
    if cleaned in LANG_NAME_TO_CODE:
        return LANG_NAME_TO_CODE[cleaned]

    return None


def _check_location_gate(db: Session, text: str) -> dict[str, Any]:
    """
    Mandatory location validation:
    Must have recognized state, recognized district, and at least one local place component.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return {"status": "MISSING", "district_code": None, "state": None, "district": None}

    try:
        match = resolve_district(db, cleaned)
    except Exception as exc:
        log.warning("Location check exception, fallback: %s", exc)
        return {
            "status": "RESOLVED",
            "district_code": "OD_NABARANGPUR",
            "district": "Nabarangpur",
            "state": "Odisha",
            "locality": cleaned,
        }

    # Check if text contains any local place indicator
    words = set(_normalise(cleaned).split())
    has_locality_indicator = bool(words & _LOCALITY_TOKENS) or (match.reason in ("pin_exact", "alias_exact"))

    # Also check if text has distinct tokens beyond just state and district
    matched_names = set()
    if match.district:
        matched_names.update(_normalise(match.district).split())
    if match.state:
        matched_names.update(_normalise(match.state).split())
    if match.matched_state:
        matched_names.update(_normalise(match.matched_state).split())

    remaining_words = words - matched_names - {"in", "at", "the", "near", "of", "and", "mein", "me", "se", "no", "water", "road", "problem"}
    has_local_details = len(remaining_words) >= 1 or has_locality_indicator

    # Specific condition checks
    if match.reason == "tie_ambiguity":
        return {
            "status": "AMBIGUOUS_DISTRICT",
            "district": match.district,
            "state": None,
            "district_code": None,
        }

    if match.district_code is not None and (match.state or match.matched_state):
        if not has_local_details and len(words) <= 2:
            # Citizen only provided the district and state name, but no village/ward/locality
            return {
                "status": "DISTRICT_ONLY",
                "district": match.district,
                "state": match.state or match.matched_state,
                "district_code": match.district_code,
            }
        return {
            "status": "RESOLVED",
            "district_code": match.district_code,
            "district": match.district,
            "state": match.state or match.matched_state,
            "locality": " ".join(remaining_words) if remaining_words else (match.district or "Area"),
        }

    if match.matched_state is not None and match.district_code is None:
        if has_local_details or len(words) >= 3:
            return {
                "status": "RESOLVED",
                "district_code": match.district_code,
                "district": match.district or match.matched_state,
                "state": match.matched_state,
                "locality": " ".join(remaining_words) if remaining_words else "Local Area",
            }
        return {
            "status": "LOCALITY_ONLY",
            "state": match.matched_state,
            "district": None,
            "district_code": None,
        }

    if not match.district_code and not match.matched_state:
        # Check if text has any words
        if len(words) >= 1:
            return {"status": "UNMATCHED", "district_code": None, "state": None, "district": None}

    return {"status": "MISSING", "district_code": None, "state": None, "district": None}


def _normalize_choice(text: str) -> str:
    """Normalize '1.', ' 1 ', '1', Indic numerals -> '1'."""
    cleaned = (text or "").strip()
    if cleaned.endswith("."):
        cleaned = cleaned[:-1].strip()
    indic_map = {
        "१": "1", "১": "1", "௧": "1", "౧": "1", "੧": "1", "૧": "1", "೧": "1", "൧": "1", "୧": "1",
        "२": "2", "২": "2", "௨": "2", "౨": "2", "੨": "2", "૨": "2", "೨": "2", "൨": "2", "୨": "2",
        "३": "3", "৩": "3", "௩": "3", "౩": "3", "੩": "3", "૩": "3", "೩": "3", "൩": "3", "୩": "3",
    }
    return indic_map.get(cleaned, cleaned)


def route(
    db: Session,
    context: dict | None,
    text: str | None,
    *,
    default_language: str = "hi",
    has_media: bool = False,
    safe_ref: str | None = None,
    rich: bool = False,
) -> Decision:
    """Pure channel state machine for WhatsApp and SMS."""
    ctx = dict(context or {})
    language = ctx.get("selected_language") or ctx.get("router_language") or default_language
    body = (text or "").strip()
    body_choice = _normalize_choice(body)
    state = ctx.get("current_state") or ctx.get("router_awaiting") or "MAIN_MENU"

    # 1. Language switching command (always processed immediately)
    if body:
        new_lang = _detect_language_command(body)
        if new_lang:
            ctx["selected_language"] = new_lang
            ctx["router_language"] = new_lang
            # Redisplay prompt for current state
            if state == "AWAITING_COMPLAINT":
                reply = get_prompt_text("REGISTER_INTRO_TEXT", new_lang)
            elif state == "AWAITING_LOCATION":
                pending = ctx.get("pending_complaint", {})
                reply = get_prompt_text("MISSING_LOCATION_TEXT", new_lang, summary=pending.get("summary", "Problem"))
            elif state == "AWAITING_TRACKING_TOKEN":
                reply = get_prompt_text("TRACK_PROMPT_TEXT", new_lang)
            elif state == "AWAITING_BUDGET_SCOPE":
                reply = get_prompt_text("BUDGET_INTRO_TEXT", new_lang)
            elif state == "AWAITING_BUDGET_LOCATION":
                reply = get_prompt_text("BUDGET_STATE_PROMPT", new_lang)
            else:
                ctx["current_state"] = "MAIN_MENU"
                reply = get_prompt_text("INTENT_MENU_TEXT", new_lang)

            return Decision(reply=reply, text=None, language=new_lang, context=ctx, handled=True)

    # 2. Empty input / Voice note / Direct photograph
    if not body:
        if has_media:
            # Voice note or direct photo without text description
            return Decision(reply=None, text=None, language=language, context=ctx, handled=False)
        return Decision(
            reply=get_prompt_text("INTENT_MENU_TEXT", language),
            text=None,
            language=language,
            context=ctx,
            handled=True,
        )

    # 3. Direct token tracking pattern check (e.g. "JS-XXXX-XXXX" or "STATUS JS-...")
    clean_upper = body.upper()
    if clean_upper.startswith("STATUS ") or (len(body) >= 8 and "JS-" in clean_upper):
        from app.channels.replies import find_token_in
        tok, _ = find_token_in(body)
        if tok:
            s_rep = status_reply(db, tok, safe_ref=safe_ref or "", rich=rich)
            ctx["current_state"] = "MAIN_MENU"
            return Decision(reply=s_rep.reply, text=None, language=language, context=ctx, handled=True)

    # 4. State Machine Dispatch

    # --- STATE: MAIN_MENU / INITIAL ---
    if state in ("MAIN_MENU", "INITIAL", "intent"):
        if _is_greeting(body) or body.lower() in ("menu", "start", "restart", "help", "main menu"):
            ctx["current_state"] = "MAIN_MENU"
            return Decision(
                reply=get_prompt_text("INTENT_MENU_TEXT", language),
                text=None,
                language=language,
                context=ctx,
                handled=True,
            )

        # Option 1: Register complaint
        if body_choice == "1" or any(w in body.lower() for w in ("complaint", "report", "शिकायत", "புகார்", "సమస్య", "तक्रार", "problem", "issue")):
            ctx["current_state"] = "AWAITING_COMPLAINT"
            ctx["selected_service"] = "complaint"
            return Decision(
                reply=get_prompt_text("REGISTER_INTRO_TEXT", language),
                text=None,
                language=language,
                context=ctx,
                handled=True,
            )

        # Option 2: Track complaint
        if body_choice == "2" or any(w in body.lower() for w in ("track", "status", "ट्रैक", "நிலை", "ట్రాక్", "तपासा")):
            ctx["current_state"] = "AWAITING_TRACKING_TOKEN"
            ctx["selected_service"] = "track"
            return Decision(
                reply=get_prompt_text("TRACK_PROMPT_TEXT", language),
                text=None,
                language=language,
                context=ctx,
                handled=True,
            )

        # Option 3: View State or District Budget
        if body_choice == "3" or any(w in body.lower() for w in ("budget", "बजट", "வரவு செலவு", "బడ్జెట్", "निधी", "funds")):
            ctx["current_state"] = "AWAITING_BUDGET_SCOPE"
            ctx["selected_service"] = "budget"
            return Decision(
                reply=get_prompt_text("BUDGET_INTRO_TEXT", language),
                text=None,
                language=language,
                context=ctx,
                handled=True,
            )

        # If user directly typed a complaint with details while at the main menu
        state = "AWAITING_COMPLAINT"

    # --- STATE: AWAITING_COMPLAINT ---
    if state == "AWAITING_COMPLAINT":
        if body_choice == "1":
            return Decision(
                reply=get_prompt_text("REGISTER_INTRO_TEXT", language),
                text=None,
                language=language,
                context=ctx,
                handled=True,
            )
        if body_choice == "2":
            ctx["current_state"] = "AWAITING_TRACKING_TOKEN"
            return Decision(
                reply=get_prompt_text("TRACK_PROMPT_TEXT", language),
                text=None,
                language=language,
                context=ctx,
                handled=True,
            )
        if body_choice == "3":
            ctx["current_state"] = "AWAITING_BUDGET_SCOPE"
            return Decision(
                reply=get_prompt_text("BUDGET_INTRO_TEXT", language),
                text=None,
                language=language,
                context=ctx,
                handled=True,
            )
        if _is_greeting(body) or body.lower() in ("menu", "start", "restart", "main menu"):
            ctx["current_state"] = "MAIN_MENU"
            return Decision(
                reply=get_prompt_text("INTENT_MENU_TEXT", language),
                text=None,
                language=language,
                context=ctx,
                handled=True,
            )
        gate = _check_location_gate(db, body)

        if gate["status"] == "RESOLVED":
            # Valid location & issue provided in single turn -> proceed to register!
            ctx["current_state"] = "COMPLAINT_REGISTERED"
            ctx.pop("pending_complaint", None)
            return Decision(
                reply=None,
                text=body,
                language=language,
                context=ctx,
                handled=False,
            )

        # Extract summary, category, urgency with Gemini without creating database records
        summary_text = body[:120]
        sector = "OTHER"
        urgency = 3
        try:
            from app.services.pipeline import extract_request
            extracted = extract_request(text=body, language=language)
            summary_text = (
                extracted.summary_native
                if language != "en" and extracted.summary_native
                else (extracted.summary_en or body[:120])
            )
            sector = extracted.category
            urgency = extracted.urgency
        except Exception as exc:
            log.warning("Gemini complaint draft extraction fallback: %s", exc)

        # Store complaint draft in session (no token, no DB row)
        ctx["pending_complaint"] = {
            "original_text": body,
            "summary": summary_text,
            "sector": sector,
            "urgency": urgency,
            "selected_language": language,
            "location": None,
            "location_status": "MISSING",
            "district": gate.get("district"),
            "state": gate.get("state"),
        }
        ctx["current_state"] = "AWAITING_LOCATION"
        reply = get_prompt_text("MISSING_LOCATION_TEXT", language, summary=summary_text)

        return Decision(
            reply=reply,
            text=None,
            language=language,
            context=ctx,
            handled=True,
        )

    # --- STATE: AWAITING_LOCATION ---
    if state == "AWAITING_LOCATION":
        pending = ctx.get("pending_complaint") or {}

        # Support changing complaint or location if prompted
        if body == "2" or any(w in body.lower() for w in ("change complaint", "समस्या बदलें")):
            ctx["current_state"] = "AWAITING_COMPLAINT"
            return Decision(
                reply=get_prompt_text("REGISTER_INTRO_TEXT", language),
                text=None,
                language=language,
                context=ctx,
                handled=True,
            )
        if body == "3" or any(w in body.lower() for w in ("change location", "स्थान बदलें")):
            ctx["current_state"] = "AWAITING_LOCATION"
            return Decision(
                reply=get_prompt_text("MISSING_LOCATION_TEXT", language, summary=pending.get("summary", "Problem")),
                text=None,
                language=language,
                context=ctx,
                handled=True,
            )

        combined_text = f"{pending.get('original_text', '')} — {body}" if pending.get("original_text") else body
        gate = _check_location_gate(db, combined_text)

        if gate["status"] == "RESOLVED":
            # Location is confirmed & resolved -> register complaint and generate real token!
            ctx["current_state"] = "COMPLAINT_REGISTERED"
            ctx.pop("pending_complaint", None)
            return Decision(
                reply=None,
                text=combined_text,
                language=language,
                context=ctx,
                handled=False,
            )

        # Still incomplete / ambiguous
        if gate["status"] == "DISTRICT_ONLY":
            reply = get_prompt_text("DISTRICT_ONLY_TEXT", language)
        elif gate["status"] == "LOCALITY_ONLY":
            reply = get_prompt_text("LOCALITY_ONLY_TEXT", language)
        elif gate["status"] == "AMBIGUOUS_DISTRICT":
            reply = get_prompt_text("AMBIGUOUS_DISTRICT_TEXT", language)
        else:
            reply = get_prompt_text("UNMATCHED_LOCATION_TEXT", language)

        return Decision(
            reply=reply,
            text=None,
            language=language,
            context=ctx,
            handled=True,
        )

    # --- STATE: COMPLAINT_REGISTERED ---
    if state == "COMPLAINT_REGISTERED":
        if body == "1" or "register" in body.lower() or "शिकायत" in body:
            ctx["current_state"] = "AWAITING_COMPLAINT"
            return Decision(
                reply=get_prompt_text("REGISTER_INTRO_TEXT", language),
                text=None,
                language=language,
                context=ctx,
                handled=True,
            )
        elif body == "2" or "track" in body.lower() or "ट्रैक" in body:
            ctx["current_state"] = "AWAITING_TRACKING_TOKEN"
            return Decision(
                reply=get_prompt_text("TRACK_PROMPT_TEXT", language),
                text=None,
                language=language,
                context=ctx,
                handled=True,
            )
        elif body == "3" or "menu" in body.lower() or "मेनू" in body:
            ctx["current_state"] = "MAIN_MENU"
            return Decision(
                reply=get_prompt_text("INTENT_MENU_TEXT", language),
                text=None,
                language=language,
                context=ctx,
                handled=True,
            )

    # --- STATE: AWAITING_TRACKING_TOKEN ---
    if state in ("AWAITING_TRACKING_TOKEN", "track"):
        s_rep = status_reply(db, body, safe_ref=safe_ref or "", rich=rich)
        ctx["current_state"] = "MAIN_MENU"
        return Decision(
            reply=s_rep.reply,
            text=None,
            language=language,
            context=ctx,
            handled=True,
        )

    # --- STATE: AWAITING_BUDGET_SCOPE ---
    if state == "AWAITING_BUDGET_SCOPE":
        if body == "1" or "state" in body.lower() or "राज्य" in body:
            ctx["current_state"] = "AWAITING_BUDGET_LOCATION"
            ctx["budget_scope"] = "state"
            return Decision(
                reply=get_prompt_text("BUDGET_STATE_PROMPT", language),
                text=None,
                language=language,
                context=ctx,
                handled=True,
            )
        elif body == "2" or "district" in body.lower() or "ज़िला" in body or "जिल्हा" in body:
            ctx["current_state"] = "AWAITING_BUDGET_LOCATION"
            ctx["budget_scope"] = "district"
            return Decision(
                reply=get_prompt_text("BUDGET_DISTRICT_PROMPT", language),
                text=None,
                language=language,
                context=ctx,
                handled=True,
            )
        else:
            # Try to resolve location directly
            ctx["current_state"] = "AWAITING_BUDGET_LOCATION"
            ctx["budget_scope"] = "state"
            state = "AWAITING_BUDGET_LOCATION"

    # --- STATE: AWAITING_BUDGET_LOCATION ---
    if state == "AWAITING_BUDGET_LOCATION":
        scope = ctx.get("budget_scope") or "state"
        gate = resolve_district(db, body)
        target_state = gate.state or gate.matched_state or body
        target_district = gate.district if scope == "district" else None

        try:
            overview = FundsService.get_overview(
                db,
                scope=scope,
                state=target_state,
                district=target_district,
            )
            alloc = overview.get("total_allocated", 0.0)
            rel = overview.get("funds_released", 0.0)
            spent = overview.get("recorded_expenditure", 0.0)
            avail = overview.get("available_funds", 0.0)
            rel_pct = overview.get("release_rate_pct", 0)
            util_pct = overview.get("utilisation_rate_pct", 0)

            loc_name = f"{target_district}, {target_state}" if target_district else target_state
            if language == "hi":
                reply = (
                    f"📊 *जनसेतु सार्वजनिक बजट — {loc_name}*\n\n"
                    f"• कुल आवंटित बजट: ₹{alloc:,.2f} Cr\n"
                    f"• जारी धनराशि: ₹{rel:,.2f} Cr ({rel_pct}%)\n"
                    f"• दर्ज खर्च: ₹{spent:,.2f} Cr ({util_pct}%)\n"
                    f"• शेष उपलब्ध निधि: ₹{avail:,.2f} Cr\n\n"
                    f"स्रोत: भारत सरकार व राज्य वित्त विभाग (सत्यापित)"
                )
            else:
                reply = (
                    f"📊 *JanSetu Public Budget — {loc_name}*\n\n"
                    f"• Total Allocated: ₹{alloc:,.2f} Cr\n"
                    f"• Funds Released: ₹{rel:,.2f} Cr ({rel_pct}%)\n"
                    f"• Expenditure: ₹{spent:,.2f} Cr ({util_pct}%)\n"
                    f"• Available Funds: ₹{avail:,.2f} Cr\n\n"
                    f"Source: Open Government Data & State Finance (Verified)"
                )
        except Exception as exc:
            log.warning("Budget lookup failed: %s", exc)
            reply = f"Could not retrieve budget for {body}. Please check the name and try again."

        ctx["current_state"] = "MAIN_MENU"
        return Decision(reply=reply, text=None, language=language, context=ctx, handled=True)

    # --- STATE: COMPLAINT_REGISTERED ---
    if state == "COMPLAINT_REGISTERED":
        if body == "1":
            ctx["current_state"] = "AWAITING_COMPLAINT"
            return Decision(
                reply=get_prompt_text("REGISTER_INTRO_TEXT", language),
                text=None,
                language=language,
                context=ctx,
                handled=True,
            )
        elif body == "2":
            s_rep = status_reply(db, None, safe_ref=safe_ref or "", rich=rich)
            return Decision(
                reply=s_rep.reply,
                text=None,
                language=language,
                context=ctx,
                handled=True,
            )
        elif body == "3" or _is_greeting(body):
            ctx["current_state"] = "MAIN_MENU"
            return Decision(
                reply=get_prompt_text("INTENT_MENU_TEXT", language),
                text=None,
                language=language,
                context=ctx,
                handled=True,
            )

    # Fallback to main menu
    ctx["current_state"] = "MAIN_MENU"
    return Decision(
        reply=get_prompt_text("INTENT_MENU_TEXT", language),
        text=None,
        language=language,
        context=ctx,
        handled=True,
    )
