# Simulation Walkthrough — WhatsApp

> Historical reference, superseded on 23 September 2026. Use the [maintained documentation](../README.md) for current instructions. Earlier claims about uptime, passing-test counts, verified financial feeds, photo deletion and production security are not current assurances. Photographs are retained; financial inputs are demonstration data; officials sign-in is a demo gate. Deployment and live channel verification remain pending.

Simulate an inbound WhatsApp complaint **entirely from the terminal** (no Meta
account, no phone, no credentials) and watch it land on the **officials' admin
dashboard** with:

- **Language translation** — the complaint shows in English (`summary_en`) with the citizen's original script underneath (`raw_text`).
- **City / State** — the "Place" column resolves to a real district + state.
- **Audio → text** — send a real `.mp3` voice note and see it transcribed, then translated.

> This is the first of three files. Companion docs:
> [SIMULATION_WALKTHROUGH_IVR.md](SIMULATION_WALKTHROUGH_IVR.md) ·
> [SIMULATION_WALKTHROUGH_SMS.md](SIMULATION_WALKTHROUGH_SMS.md)

---

## 0. One-time prerequisites (identical for all three channels)

All commands assume the repo root `D:/AI Code for Communities/jansetu`.

**a) Seed the database** — this is what makes the *city/state* appear. Location
extraction can only resolve a place name to a "district, state" if the districts
table is populated.

```bash
cd "D:/AI Code for Communities/jansetu/backend" && python -m app.db.seed
```

(or from the repo root: `make seed`)

**b) Start the backend API on :8080**

```bash
cd "D:/AI Code for Communities/jansetu/backend" && uvicorn app.main:app --reload --port 8080
```

(or `make api`). Tables are auto-created on startup; seeding in step (a) fills them.

**c) Start the admin dashboard (officials' console) on :5174**

```bash
cd "D:/AI Code for Communities/jansetu/frontend-admin" && npm install && npm run dev
```

Open **http://localhost:5174** and sign in:

| Account | Password | Sees |
|---|---|---|
| `state.cell` | `jansetu@2026` | **Every state** — use this so all demo complaints are visible |
| `phed.sitamarhi` | `jansetu@2026` | Bihar only |
| `bdo.nabarangpur` | `jansetu@2026` | Odisha only |

> Sign in as **`state.cell`** for the demo. The default queue filter is
> *unanswered, newest first*, scoped to the officer's home state — a freshly
> simulated complaint is unanswered, so it appears at the top.

**d) Gemini key** — translation and audio→text use Gemini. A working
`GEMINI_API_KEY` already lives in `jansetu/.env` and is loaded automatically
regardless of the working directory. If it were missing, text still ingests but
the English translation is skipped and audio-only messages fail.

**Use place names the seed knows**, so the Place column resolves:

| Say this in the message | Resolves to |
|---|---|
| **Sitamarhi** | Sitamarhi, **Bihar** |
| **Nabarangpur** | Nabarangpur, **Odisha** |
| **Pune** | Pune, **Maharashtra** |

---

## 1. The endpoint

`POST http://localhost:8080/intake/whatsapp`

The body mimics a **Meta WhatsApp Cloud API webhook**. For terminal simulation
there is one extra convenience field, `mock_media_base64`, which stands in for
media that Meta would normally host — so you never need a real media URL.

The handler **acknowledges instantly** with `{"status":"received"}` and finishes
the download + transcription + translation + save in a background task (a few
seconds). The dashboard row appears right after.

The snippets below use Python (the `httpx` library ships with the backend, so
run them in the same environment as the API). Every one is self-contained.

---

## 2. Text complaint (shows translation + city/state)

A Hindi text message naming **Sitamarhi**:

```bash
python - <<'PY'
import httpx
payload = {
    "object": "whatsapp_business_account",
    "language": "hi",  # transcription/translation hint
    "entry": [{"changes": [{"value": {"messages": [{
        "from": "919812300001",              # raw MSISDN; pseudonymised server-side
        "id": "wamid.demo-text-0001",        # unique per message (repeat = dedup, no dupe)
        "type": "text",
        "text": {"body": "सीतामढ़ी में तीन दिन से पानी की सप्लाई बंद है।"}
    }]}}]}]
}
r = httpx.post("http://localhost:8080/intake/whatsapp", json=payload, timeout=30)
print(r.status_code, r.json())   # -> 200 {'status': 'received'}
PY
```

Prefer curl? Write the JSON to a file first (avoids Windows shell encoding
issues with non-ASCII), then post it:

```bash
curl -s -X POST http://localhost:8080/intake/whatsapp -H "Content-Type: application/json" --data-binary @whatsapp_text.json
```

---

## 3. Voice note → text (the `.mp3` audio→text demo)

**Get a sample clip first.** You need *real speech* — record a 5–10 second voice
note on any phone saying a complaint in Hindi (or another supported language)
that **names a seeded place**, e.g. spoken Hindi for:

> "Sitamarhi mein teen din se paani ki supply band hai."

Export/transfer it as `.mp3` (also fine: `.ogg`, `.m4a`, `.wav`). Note the path.

> ⚠️ Do **not** use the files under `data/ivr_prompts/*.wav` for this — those are
> synthetic sine-tone placeholders, not speech, and will not transcribe to
> anything. You need an actual voice recording.

Then send it (set `AUDIO_FILE` to your clip). `mime_type: "audio/mpeg"` is for
`.mp3`; use `audio/ogg` for `.ogg`:

```bash
python - <<'PY'
import base64, httpx
AUDIO_FILE = r"C:\Users\sagar\Downloads\sitamarhi_water.mp3"   # <-- your clip
b64 = base64.b64encode(open(AUDIO_FILE, "rb").read()).decode()
payload = {
    "object": "whatsapp_business_account",
    "language": "hi",                          # language the caller spoke
    "mock_media_base64": b64,                  # stands in for Meta-hosted media
    "entry": [{"changes": [{"value": {"messages": [{
        "from": "919812300002",
        "id": "wamid.demo-audio-0001",
        "type": "audio",
        "audio": {"id": "media-audio-1", "mime_type": "audio/mpeg"}
    }]}}]}]
}
r = httpx.post("http://localhost:8080/intake/whatsapp", json=payload, timeout=60)
print(r.status_code, r.json())
PY
```

The background task base64-decodes the clip, sends it to Gemini for
transcription in the language you set, extracts the structured request, and
translates the summary to English. On the dashboard you'll see the **English
summary** (translation) with the **transcribed original** underneath, and the
**Place** resolved from the spoken city.

---

## 4. Photo evidence (optional, WhatsApp-only)

A photo **cannot stand alone** (an image with no words can't be acted on). Send
it as a follow-up **from the same `from` number** shortly after a text/voice
complaint — it attaches to that open docket as verified evidence. The image
bytes are analysed by Gemini and then **discarded**; only the text description
is stored.

```bash
python - <<'PY'
import base64, httpx
IMG_FILE = r"C:\Users\sagar\Downloads\pothole.jpg"   # <-- any JPEG/PNG
b64 = base64.b64encode(open(IMG_FILE, "rb").read()).decode()
payload = {
    "object": "whatsapp_business_account",
    "mock_media_base64": b64,
    "entry": [{"changes": [{"value": {"messages": [{
        "from": "919812300002",                  # SAME number as the complaint above
        "id": "wamid.demo-image-0001",
        "type": "image",
        "image": {"id": "media-img-1", "mime_type": "image/jpeg",
                   "caption": "सीतामढ़ी की सड़क का गड्ढा"}
    }]}}]}]
}
r = httpx.post("http://localhost:8080/intake/whatsapp", json=payload, timeout=60)
print(r.status_code, r.json())
PY
```

Open the docket's detail view on the dashboard — the photo analysis appears as
**"Photo evidence"** (`image_verification`), and the request count does **not**
increase (it attaches, it doesn't create a new docket).

---

## 5. Verify on the admin dashboard

1. Go to **http://localhost:5174**, signed in as **`state.cell`**.
2. The newest complaint sits at the **top** of the queue (unanswered, newest first).
3. Read across the row:

| Column | What proves the feature |
|---|---|
| **What was reported** | English `summary_en` on top = **translation**; the original Devanagari/native `raw_text` below it |
| **Place** | e.g. **"Sitamarhi, Bihar"** = the **city/state** resolved from the message |
| **Arrived by** | **WhatsApp** channel tag |
| **Filed** | timestamp, seconds ago |

4. Click the row for the detail view: full location hierarchy (down to ward),
   category, urgency, and — if you sent a photo — the **Photo evidence** analysis.

**Terminal cross-check** (the dashboard calls this same open endpoint):

```bash
curl -s "http://localhost:8080/requests?channel=whatsapp&limit=5" | python -m json.tool
```

Each item shows `summary_en` (English), `raw_text` (original), `district`,
`state`, and `channel: "whatsapp"`.

---

## 6. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Row appears but **Place is blank / "unmatched"** | You didn't seed, or the message named a place not in the seed. Run `python -m app.db.seed` and use Sitamarhi / Nabarangpur / Pune. |
| **No English translation**, only original text | Gemini key not loaded. Confirm `GEMINI_API_KEY` in `jansetu/.env`. |
| Audio message gives an error / empty transcript | The clip isn't real speech (don't use the sine-tone prompt WAVs), the file path is wrong, or the key is missing. |
| Complaint **not visible** in the queue | You're signed in as a state-scoped officer (e.g. `phed.sitamarhi`) and the complaint is in another state. Use `state.cell`, or clear the state filter. |
| `{"status":"received"}` but no row after several seconds | Give the background Gemini call a moment on first run; then re-check `/requests`. Check the uvicorn console for a logged exception. |
| Sent the same message twice, only one row | Working as intended — identical `id` is de-duplicated. Change `id` to simulate a new message. |

---

**Privacy note:** the raw phone number exists only in memory during ingest; it is
HMAC-pseudonymised before storage. Photos are analysed then dropped — no image
bytes are persisted. Location is never stored below ward level.
