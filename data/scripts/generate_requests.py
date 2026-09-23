#!/usr/bin/env python3
"""Generate a realistic multilingual corpus of citizen development requests.

Why synthetic: there is no public, consented, geotagged corpus of Indian
citizen infrastructure complaints in twelve languages. The hackathon rules
allow "sample data ... where live data isn't available", so this generator
exists and its assumptions are written down rather than hidden.

The important design decision: request volume is driven by internet
penetration, NOT by need. Districts with better connectivity generate more
reports even where coverage is worse elsewhere. That is what happens in every
real digital grievance system, and it is the bias the unmet-need index corrects
via its participation adjustment. If the seed data were unbiased, the
correction would have nothing to demonstrate.

Every row carries `category_hint` and `urgency_hint` — the ground truth used to
seed the database in bulk, and also usable as an eval set for measuring how
accurately Gemini extraction recovers them.

Usage:  python data/scripts/generate_requests.py [--count 600]
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1]
SEED = 20260822

# Phrase bank. Five highest-signal categories are covered in all eight
# languages spoken across the seeded states; the remaining categories fall back
# to Hindi and English. Extend by adding keys — nothing else changes.
PHRASES: dict[str, dict[str, str]] = {
    "WATER_SUPPLY": {
        "hi": "हमारे गाँव में तीन महीने से नल का पानी नहीं आ रहा है, महिलाओं को दो किलोमीटर दूर से पानी लाना पड़ता है",
        "bn": "আমাদের গ্রামে তিন মাস ধরে নলের জল আসছে না, মহিলাদের দুই কিলোমিটার দূর থেকে জল আনতে হয়",
        "ta": "எங்கள் ஊரில் மூன்று மாதங்களாக குழாய் தண்ணீர் வரவில்லை, பெண்கள் இரண்டு கிலோமீட்டர் நடந்து தண்ணீர் எடுக்க வேண்டியிருக்கிறது",
        "mr": "आमच्या गावात तीन महिन्यांपासून नळाला पाणी येत नाही, महिलांना दोन किलोमीटर दूरवरून पाणी आणावे लागते",
        "or": "ଆମ ଗାଁରେ ତିନି ମାସ ହେଲା ନଳରେ ପାଣି ଆସୁନାହିଁ, ମହିଳାମାନେ ଦୁଇ କିଲୋମିଟର ଦୂରରୁ ପାଣି ଆଣୁଛନ୍ତି",
        "kn": "ನಮ್ಮ ಹಳ್ಳಿಯಲ್ಲಿ ಮೂರು ತಿಂಗಳಿಂದ ನಲ್ಲಿಯಲ್ಲಿ ನೀರು ಬರುತ್ತಿಲ್ಲ, ಮಹಿಳೆಯರು ಎರಡು ಕಿಲೋಮೀಟರ್ ದೂರದಿಂದ ನೀರು ತರಬೇಕಾಗಿದೆ",
        "as": "আমাৰ গাঁৱত তিনি মাহৰ পৰা নলত পানী অহা নাই, মহিলাসকলে দুই কিলোমিটাৰ দূৰৰ পৰা পানী আনিব লগা হৈছে",
        "en": "No piped water in our village for three months, women walk two kilometres to fetch water",
    },
    "ROADS": {
        "hi": "बरसात में सड़क कीचड़ में बदल जाती है, एम्बुलेंस गाँव तक नहीं आ पाती",
        "bn": "বর্ষায় রাস্তা কাদায় ভরে যায়, অ্যাম্বুলেন্স গ্রামে ঢুকতে পারে না",
        "ta": "மழைக்காலத்தில் சாலை சேறாக மாறுகிறது, ஆம்புலன்ஸ் கிராமத்திற்கு வர முடியவில்லை",
        "mr": "पावसाळ्यात रस्ता चिखलात बदलतो, रुग्णवाहिका गावात येऊ शकत नाही",
        "or": "ବର୍ଷାରେ ରାସ୍ତା କାଦୁଅ ହୋଇଯାଏ, ଆମ୍ବୁଲାନ୍ସ ଗାଁକୁ ଆସିପାରେ ନାହିଁ",
        "kn": "ಮಳೆಗಾಲದಲ್ಲಿ ರಸ್ತೆ ಕೆಸರಾಗುತ್ತದೆ, ಆಂಬ್ಯುಲೆನ್ಸ್ ಹಳ್ಳಿಗೆ ಬರಲು ಸಾಧ್ಯವಿಲ್ಲ",
        "as": "বৰষুণত ৰাস্তা বোকা হৈ পৰে, এম্বুলেন্স গাঁৱলৈ আহিব নোৱাৰে",
        "en": "The road turns to mud in the monsoon and ambulances cannot reach our village",
    },
    "ELECTRICITY": {
        "hi": "दिन में आठ घंटे बिजली कटती है, बच्चे रात में पढ़ नहीं पाते",
        "bn": "দিনে আট ঘণ্টা বিদ্যুৎ থাকে না, বাচ্চারা রাতে পড়তে পারে না",
        "ta": "நாளொன்றுக்கு எட்டு மணி நேரம் மின்சாரம் இல்லை, குழந்தைகள் இரவில் படிக்க முடியவில்லை",
        "mr": "दिवसात आठ तास वीज नसते, मुलांना रात्री अभ्यास करता येत नाही",
        "or": "ଦିନକୁ ଆଠ ଘଣ୍ଟା ବିଦ୍ୟୁତ ନାହିଁ, ପିଲାମାନେ ରାତିରେ ପଢ଼ି ପାରୁନାହାଁନ୍ତି",
        "kn": "ದಿನಕ್ಕೆ ಎಂಟು ಗಂಟೆ ವಿದ್ಯುತ್ ಇರುವುದಿಲ್ಲ, ಮಕ್ಕಳು ರಾತ್ರಿ ಓದಲು ಆಗುತ್ತಿಲ್ಲ",
        "as": "দিনত আঠ ঘণ্টা বিজুলী নাথাকে, ল'ৰা-ছোৱালীয়ে ৰাতি পঢ়িব নোৱাৰে",
        "en": "Eight hours of power cuts daily, children cannot study at night",
    },
    "HEALTH": {
        "hi": "सबसे नज़दीकी अस्पताल तीस किलोमीटर दूर है, गर्भवती महिलाओं को बहुत परेशानी होती है",
        "bn": "সবচেয়ে কাছের হাসপাতাল ত্রিশ কিলোমিটার দূরে, গর্ভবতী মহিলাদের খুব কষ্ট হয়",
        "ta": "அருகிலுள்ள மருத்துவமனை முப்பது கிலோமீட்டர் தொலைவில் உள்ளது, கர்ப்பிணிப் பெண்கள் மிகவும் சிரமப்படுகிறார்கள்",
        "mr": "जवळचे रुग्णालय तीस किलोमीटर दूर आहे, गर्भवती महिलांना खूप त्रास होतो",
        "or": "ନିକଟତମ ଡାକ୍ତରଖାନା ତିରିଶ କିଲୋମିଟର ଦୂରରେ, ଗର୍ଭବତୀ ମହିଳାମାନଙ୍କୁ ବହୁତ ଅସୁବିଧା ହୁଏ",
        "kn": "ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆ ಮೂವತ್ತು ಕಿಲೋಮೀಟರ್ ದೂರದಲ್ಲಿದೆ, ಗರ್ಭಿಣಿ ಮಹಿಳೆಯರಿಗೆ ತುಂಬಾ ತೊಂದರೆಯಾಗುತ್ತಿದೆ",
        "as": "আটাইতকৈ নিকটৱৰ্তী চিকিৎসালয় ত্ৰিশ কিলোমিটাৰ দূৰত, গৰ্ভৱতী মহিলাসকলৰ বহুত অসুবিধা হয়",
        "en": "Nearest hospital is thirty kilometres away, pregnant women suffer badly",
    },
    "SANITATION": {
        "hi": "गाँव में नाली नहीं है, बरसात का पानी घरों में घुस जाता है और बीमारी फैलती है",
        "bn": "গ্রামে নর্দমা নেই, বৃষ্টির জল ঘরে ঢুকে যায় এবং রোগ ছড়ায়",
        "ta": "கிராமத்தில் வடிகால் இல்லை, மழைநீர் வீடுகளுக்குள் புகுந்து நோய் பரவுகிறது",
        "mr": "गावात गटार नाही, पावसाचे पाणी घरात शिरते आणि आजार पसरतो",
        "or": "ଗାଁରେ ନର୍ଦମା ନାହିଁ, ବର୍ଷା ପାଣି ଘରେ ପଶିଯାଏ ଏବଂ ରୋଗ ବ୍ୟାପେ",
        "kn": "ಹಳ್ಳಿಯಲ್ಲಿ ಚರಂಡಿ ಇಲ್ಲ, ಮಳೆ ನೀರು ಮನೆಗಳಿಗೆ ನುಗ್ಗಿ ರೋಗ ಹರಡುತ್ತದೆ",
        "as": "গাঁৱত নলা নাই, বৰষুণৰ পানী ঘৰত সোমাই ৰোগ বিয়পে",
        "en": "No drainage in the village, rainwater enters homes and disease spreads",
    },
    "DIGITAL": {
        "hi": "गाँव में मोबाइल नेटवर्क नहीं आता, ऑनलाइन काम के लिए शहर जाना पड़ता है",
        "en": "No mobile network in the village, we travel to town for any online work",
    },
    "EDUCATION": {
        "hi": "स्कूल की इमारत टूटी हुई है, बच्चे पेड़ के नीचे बैठकर पढ़ते हैं",
        "en": "The school building is broken, children sit under a tree to study",
    },
    "IRRIGATION": {
        "hi": "नहर का पानी खेतों तक नहीं पहुँचता, फसल सूख जाती है",
        "en": "Canal water does not reach the fields and the crop dries up",
    },
}

# Urgency distribution per category — health and water skew higher because the
# consequences are immediate.
URGENCY_BIAS = {
    "WATER_SUPPLY": (3, 5), "HEALTH": (3, 5), "ELECTRICITY": (2, 4),
    "ROADS": (2, 4), "SANITATION": (2, 5), "DIGITAL": (1, 3),
    "EDUCATION": (2, 4), "IRRIGATION": (2, 4),
}

CHANNELS = ["whatsapp", "voice", "text", "ivr", "sms"]
CHANNEL_WEIGHTS = [0.42, 0.25, 0.18, 0.10, 0.05]


def read_districts() -> list[dict]:
    with (DATA_DIR / "reference" / "districts.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def generate(count: int) -> list[dict]:
    rng = random.Random(SEED)
    districts = read_districts()

    # Reporting propensity: internet access dominates, population contributes
    # mildly. This is the bias, made explicit.
    weights = []
    for d in districts:
        net = float(d["internet_pct"]) / 100.0
        pop = int(d["population"])
        weights.append((net ** 1.6) * (pop ** 0.35))

    categories = list(PHRASES.keys())
    rows: list[dict] = []
    for i in range(count):
        d = rng.choices(districts, weights=weights, k=1)[0]
        category = rng.choice(categories)
        available = PHRASES[category]

        # Most people write in the district's main language; some use Hindi or
        # English, which is what real intake channels look like.
        preferred = d["primary_language"]
        lang = preferred if preferred in available else "hi"
        if rng.random() < 0.18:
            lang = rng.choice([l for l in available if l != lang] or [lang])

        lo, hi = URGENCY_BIAS.get(category, (2, 4))
        rows.append({
            "id": i + 1,
            "text": available[lang],
            "language": lang,
            "location_text": f"{d['name']}, {d['state']}",
            "district_code": d["code"],
            "channel": rng.choices(CHANNELS, weights=CHANNEL_WEIGHTS, k=1)[0],
            "category_hint": category,
            "urgency_hint": rng.randint(lo, hi),
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=600)
    args = ap.parse_args()

    rows = generate(args.count)
    out = DATA_DIR / "synthetic" / "citizen_requests.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    langs = sorted({r["language"] for r in rows})
    print(f"wrote {len(rows)} requests -> {out.relative_to(DATA_DIR.parent)}")
    print(f"languages: {', '.join(langs)}")
    print(f"districts covered: {len({r['district_code'] for r in rows})}/{len(read_districts())}")


if __name__ == "__main__":
    main()
