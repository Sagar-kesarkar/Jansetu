"""HTTP & CLI Demonstration Harness for JanSetu IVR.

Zero-cost demonstration of the IVR call-flow state machine without requiring
a paid telephony provider (Twilio/Exotel) or Indian DID number.

Walks through:
1. Call Start -> Language Menu Prompts (multilingual).
2. DTMF Keypress (e.g. '1' for Hindi, '2' for Bengali).
3. Audio Recording / Need Description -> Gemini Ingest.
4. Native-script Confirmation & Digit-by-digit Docket Readback.
5. Repeat option or Call Completion.
"""
from __future__ import annotations

import base64
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.channels.ivr import IVRAdapter, IVRStepResult
from app.channels.state import (
    AudioRecordedEvent,
    CallStartEvent,
    DtmfEvent,
    HangupEvent,
    NoInputEvent,
    TextReceivedEvent,
    TimeoutEvent,
)
from app.db.database import SessionLocal

log = logging.getLogger(__name__)


class IVRSimulator:
    def __init__(self, db: Session | None = None) -> None:
        self._db_passed = db is not None
        self.db = db or SessionLocal()
        self.adapter = IVRAdapter(self.db)

    def close(self) -> None:
        if not self._db_passed and self.db:
            self.db.close()

    def step(
        self,
        caller_phone: str,
        action_type: str,
        digits: str | None = None,
        audio_bytes: bytes | None = None,
        audio_mime: str = "audio/wav",
        text_simulation: str | None = None,
    ) -> IVRStepResult:
        """Drive one step of the IVR state machine."""
        act = action_type.lower()
        if act in ("start", "call_start"):
            event = CallStartEvent()
        elif act in ("dtmf", "digit"):
            event = DtmfEvent(digits=digits or "1")
        elif act in ("audio", "record"):
            if audio_bytes:
                event = AudioRecordedEvent(audio_bytes=audio_bytes, audio_mime=audio_mime)
            elif text_simulation:
                # Text simulation fallback for audio intake
                event = TextReceivedEvent(text=text_simulation)
            else:
                event = NoInputEvent()
        elif act in ("timeout",):
            event = TimeoutEvent()
        elif act in ("no_input",):
            event = NoInputEvent()
        elif act in ("hangup", "drop"):
            event = HangupEvent()
        else:
            event = CallStartEvent()

        return self.adapter.handle_event(caller_phone, event)

    def run_full_simulation(
        self,
        caller_phone: str = "919876543210",
        language_digit: str = "1",
        problem_description: str = "हमारे गाँव में पानी की पाइपलाइन टूटी हुई है, 4 दिन से पानी नहीं आया।",
        audio_bytes: bytes | None = None,
    ) -> list[dict[str, Any]]:
        """Walk a complete IVR call from greeting to docket confirmation."""
        history = []

        # Step 1: Call Start -> Greeting & Language Menu
        res1 = self.step(caller_phone, "start")
        history.append({
            "step": 1,
            "action": "call_start",
            "state": res1.next_state,
            "prompts": [p["text"] for p in res1.prompts_to_play],
            "gather_dtmf": res1.gather_dtmf,
        })

        # Step 2: Language Selection (DTMF)
        res2 = self.step(caller_phone, "dtmf", digits=language_digit)
        history.append({
            "step": 2,
            "action": f"dtmf_pressed_{language_digit}",
            "language": res2.language,
            "state": res2.next_state,
            "prompts": [p["text"] for p in res2.prompts_to_play],
            "record_audio": res2.record_audio,
        })

        # Step 3: Record Need Description -> Ingest
        res3 = self.step(
            caller_phone,
            "audio",
            audio_bytes=audio_bytes,
            text_simulation=problem_description if not audio_bytes else None,
        )
        history.append({
            "step": 3,
            "action": "audio_recorded_and_ingested",
            "state": res3.next_state,
            "request_id": res3.request_id,
            "docket_ref": res3.docket_ref,
            "prompts": [p["text"] for p in res3.prompts_to_play],
            "digits_spoken": res3.digits_to_spell,
        })

        # Step 4: Finish call (DTMF '9' to complete)
        res4 = self.step(caller_phone, "dtmf", digits="9")
        history.append({
            "step": 4,
            "action": "dtmf_finish",
            "state": res4.next_state,
            "prompts": [p["text"] for p in res4.prompts_to_play],
            "hangup": res4.hangup,
        })

        return history


def run_cli_demo() -> None:
    """Interactive terminal runner for the IVR state machine."""
    print("=" * 60)
    print("JanSetu IVR Telephony Simulator (Zero-Cost Demonstration)")
    print("=" * 60)
    sim = IVRSimulator()
    phone = input("Enter simulated caller phone [default 919876543210]: ").strip() or "919876543210"

    print("\n[Simulator] Inbound call received...")
    res = sim.step(phone, "start")
    print(f"State: {res.next_state}")
    for p in res.prompts_to_play:
        print(f"🔊 Audio: {p['text']}")

    lang_choice = input("\nEnter DTMF Digit (1=Hindi, 2=Bengali, 3=Tamil, 4=Telugu...): ").strip() or "1"
    res = sim.step(phone, "dtmf", digits=lang_choice)
    print(f"\nState: {res.next_state} (Language: {res.language})")
    for p in res.prompts_to_play:
        print(f"🔊 Audio: {p['text']}")

    print("\n[Simulator] Simulating voice recording of grievance...")
    speech = input("Enter problem description: ").strip() or "हमारे गाँव में बिजली 3 दिन से गुल है।"
    res = sim.step(phone, "audio", text_simulation=speech)
    print(f"\nState: {res.next_state}")
    print(f"✅ Request Ingested! ID: {res.request_id} | Docket Ref: {res.docket_ref}")
    for p in res.prompts_to_play:
        print(f"🔊 Audio: {p['text']}")
    if res.digits_to_spell:
        print(f"🔢 Spoken Docket Digits: {' - '.join(res.digits_to_spell)}")

    res = sim.step(phone, "dtmf", digits="2")
    print(f"\nState: {res.next_state}")
    for p in res.prompts_to_play:
        print(f"🔊 Audio: {p['text']}")
    print("📞 Call Completed and Hung Up.")
    sim.close()


if __name__ == "__main__":
    run_cli_demo()
