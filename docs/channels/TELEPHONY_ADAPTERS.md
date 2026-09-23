# Telephony Provider Adapters & Call-Flow Architecture

> Historical reference, superseded on 23 September 2026. Use the [maintained documentation](../README.md) for current instructions. Earlier claims about uptime, passing-test counts, verified financial feeds, photo deletion and production security are not current assurances. Photographs are retained; financial inputs are demonstration data; officials sign-in is a demo gate. Deployment and live channel verification remain pending.

JanSetu's IVR is built as a **provider-agnostic conversation state machine** (`backend/app/channels/state.py` and `backend/app/channels/ivr.py`).

In accordance with **Constraint 1 (₹0 infrastructure, no credit card)**, JanSetu does not require a paid telephony subscription or Indian DID number to run, test, or evaluate. It provides:
1. **Interactive HTTP Simulator** (`POST /ivr/simulate` & `app.channels.simulator`) for local evaluation and demo videos.
2. **Standard Webhook Adapter** (`POST /ivr/webhook`) that generates native responses for both **Twilio (TwiML XML)** and **Exotel (JSON)**.

---

## 1. Adapter Architecture

```
                       Telephony Provider / Simulator
                     (Twilio, Exotel, Linphone, HTTP)
                                    │
                         POST /ivr/webhook or /simulate
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   app.channels.ivr::IVRAdapter                         │
│                                                                        │
│  - Hashing Choke Point: MSISDN -> HMAC-SHA256 (anon_...)               │
│  - Session Store: ChannelSession (strictly pseudonymised, zero PII)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   app.channels.state::transition                       │
│                     (Pure Python State Machine)                        │
│                                                                        │
│  INITIAL -> SELECT_LANGUAGE -> COLLECT_NEED -> CONFIRMING -> COMPLETED │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ ActionType.TRIGGER_INGEST
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   app.services.pipeline::ingest                        │
│                                                                        │
│  - Speech Recognition: Gemini Multimodal Audio                         │
│  - Structured Extraction: Category, Urgency, Ward-level Place          │
│  - Geocoding: LGD District Resolution                                  │
│  - Native Acknowledgement: Devanagari/Script Confirmation              │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Twilio TwiML vs Exotel Protocols Side-by-Side

JanSetu generates both formats from the exact same state machine step:

| Step / Action | Twilio TwiML XML (`format=twiml`) | Exotel JSON (`format=json`) |
|---|---|---|
| **Language Selection Menu** | `<Response>`<br>&nbsp;&nbsp;`<Gather numDigits="1" timeout="10" action="/ivr/webhook?format=twiml">`<br>&nbsp;&nbsp;&nbsp;&nbsp;`<Play>/ivr/prompts/hi/GREETING_LANG_MENU.wav</Play>`<br>&nbsp;&nbsp;`</Gather>`<br>`</Response>` | `{"select": "gather", "state": "SELECT_LANGUAGE", "prompts": ["/ivr/prompts/hi/GREETING_LANG_MENU.wav"], "gather_dtmf": {"num_digits": 1, "timeout_sec": 10}}` |
| **Record Need Description** | `<Response>`<br>&nbsp;&nbsp;`<Play>/ivr/prompts/hi/RECORD_NEED_BEEP.wav</Play>`<br>&nbsp;&nbsp;`<Record maxLength="45" playBeep="true" action="/ivr/webhook?format=twiml" finishOnKey="#" />`<br>`</Response>` | `{"select": "play", "state": "COLLECT_NEED", "prompts": ["/ivr/prompts/hi/RECORD_NEED_BEEP.wav"], "record": true, "max_duration_sec": 45}` |
| **Native Acknowledgment & Docket Readback** | `<Response>`<br>&nbsp;&nbsp;`<Play>/ivr/prompts/hi/CONFIRMATION_NOTICE.wav</Play>`<br>&nbsp;&nbsp;`<Play>/ivr/prompts/hi/DOCKET_REF_INTRO.wav</Play>`<br>&nbsp;&nbsp;`<Say language="hi">ए, बी, तीन, चार, पाँच</Say>`<br>&nbsp;&nbsp;`<Gather numDigits="1" timeout="10" action="/ivr/webhook?format=twiml">`<br>&nbsp;&nbsp;&nbsp;&nbsp;`<Play>/ivr/prompts/hi/REPEAT_MENU.wav</Play>`<br>&nbsp;&nbsp;`</Gather>`<br>`</Response>` | `{"select": "gather", "state": "CONFIRMING", "prompts": ["/ivr/prompts/hi/CONFIRMATION_NOTICE.wav", "/ivr/prompts/hi/DOCKET_REF_INTRO.wav"], "digits_spoken": ["एक", "दो", "तीन"], "request_id": 42, "docket_ref": "anon_123"}` |
| **Hangup / Call End** | `<Response>`<br>&nbsp;&nbsp;`<Play>/ivr/prompts/hi/THANK_YOU.wav</Play>`<br>&nbsp;&nbsp;`<Hangup/>`<br>`</Response>` | `{"select": "play", "state": "COMPLETED", "prompts": ["/ivr/prompts/hi/THANK_YOU.wav"], "hangup": true}` |

---

## 3. Telephony Audio Specification

- **Sampling Rate**: 8,000 Hz (8 kHz narrowband telephony standard).
- **Channels**: 1 (Mono).
- **Encoding**: 16-bit Signed Linear PCM WAV.
- **Location**: `data/ivr_prompts/<lang>/<prompt_name>.wav` and `data/ivr_prompts/digits/<digit>.wav`.
- **Pre-generated Assets**: Synthesized via `app.channels.generate_audio` across all 13 Indian languages with zero external dependencies.

---

## 4. Privacy and Session Storage

1. **No MSISDN Persistence**: The calling line identifier (`From`) is passed to `ingest(citizen_ref=...)` and immediately hashed with salted HMAC-SHA256 (`services/privacy.py`).
2. **Session Key**: `ChannelSession` is indexed only by `anon_<digest>`, guaranteeing zero raw phone numbers anywhere in SQLite storage.
3. **Dropped Call Safety**: If a caller hangs up before finishing recording, the session is cleared and no request row is created.
