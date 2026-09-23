"""Multilingual keyword table for the no-Gemini fallback path.

`ARCHITECTURE.md` promises that when Gemini is unavailable the pipeline
degrades to "keyword extraction". This is that keyword extraction. Without it
the fallback labelled every request OTHER, which matters more than it sounds:
free-tier quota can run out mid-demo, and a screen that classifies a clear
complaint about drinking water as "Other" reads as broken rather than degraded.

Vocabulary is lifted from the phrasing in `data/scripts/generate_requests.py`
so the table and the seed corpus cannot drift apart, and extended with the terms
a real citizen would reach for in each language.

Two tiers, because the categories genuinely overlap in natural speech. "There is
no drain in the village and rainwater enters our homes" contains the word for
water but is a sanitation complaint, so `STRONG` terms (the thing being asked
for) outweigh `WEAK` ones (the consequence being described).
"""
from __future__ import annotations

# Category -> (strong terms, weak terms). Matching is plain substring, which is
# the right tool here: Indian scripts are unspaced enough that word-boundary
# regexes misfire, and these terms are long enough not to collide by accident.
KEYWORDS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "WATER_SUPPLY": (
        ("नल", "नळ", "নল", "ନଳ", "ನಲ್ಲಿ", "குழாய்", "पीने का पानी", "piped water",
         "tap water", "drinking water", "handpump", "हैंडपंप", "बोरिंग"),
        ("पानी", "पाणी", "জল", "পানী", "ପାଣି", "ನೀರು", "தண்ணீர்", "water"),
    ),
    "SANITATION": (
        ("नाली", "गटार", "নর্দমা", "ନର୍ଦମା", "ಚರಂಡಿ", "வடிகால்", "নলা", "शौचालय",
         "drain", "drainage", "sewage", "toilet", "sanitation", "कचरा", "garbage"),
        ("बीमारी", "রোগ", "ରୋଗ", "ರೋಗ", "நோய்", "disease", "गंदगी"),
    ),
    "ROADS": (
        ("सड़क", "रस्ता", "রাস্তা", "ৰাস্তা", "ରାସ୍ତା", "ರಸ್ತೆ", "சாலை", "road",
         "pothole", "गड्ढे", "पुल", "bridge", "culvert"),
        ("कीचड़", "चिखल", "কাদা", " କାଦୁଅ", "ಕೆಸರ", "சேறு", "mud"),
    ),
    "ELECTRICITY": (
        ("बिजली", "वीज", "বিদ্যুৎ", "বিজুলী", "ବିଦ୍ୟୁତ", "ವಿದ್ಯುತ್", "மின்சாரம்",
         "electricity", "power cut", "powercut", "transformer", "ट्रांसफार्मर",
         "खंभा", "street light", "स्ट्रीट लाइट"),
        ("अंधेरा", "कटती", "outage"),
    ),
    "HEALTH": (
        ("अस्पताल", "रुग्णालय", "হাসপাতাল", "চিকিৎসালয়", "ଡାକ୍ତରଖାନା", "ಆಸ್ಪತ್ರೆ",
         "மருத்துவமனை", "hospital", "clinic", "डॉक्टर", "doctor", "health centre",
         "health center", "phc", "उपकेंद्र", "एम्बुलेंस", "ambulance"),
        ("गर्भवती", "pregnant", "दवा", "medicine", "टीका", "vaccine"),
    ),
    "EDUCATION": (
        ("स्कूल", "विद्यालय", "স্কুল", "ବିଦ୍ୟାଳୟ", "ಶಾಲೆ", "பள்ளி", "school",
         "teacher", "शिक्षक", "अध्यापक", "classroom", "कक्षा", "आंगनवाड़ी",
         "anganwadi"),
        ("बच्चे", "पढ़", "students", "छात्र"),
    ),
    "DIGITAL": (
        ("नेटवर्क", "मोबाइल", "इंटरनेट", "network", "internet", "broadband",
         "signal", "सिग्नल", "wifi", "wi-fi", "बीएसएनएल", "टावर", "tower"),
        ("ऑनलाइन", "online", "digital"),
    ),
    "HOUSING": (
        ("आवास", "मकान", "पक्का घर", "कच्चा घर", "housing", "pucca", "kutcha",
         "छत", "roof", "shelter", "झोपड़ी"),
        ("रहने", "घर बनाने"),
    ),
    "IRRIGATION": (
        ("नहर", "सिंचाई", "canal", "irrigation", "tube well", "tubewell",
         "बोरवेल", "borewell", "नाला बांध", "check dam", "तालाब", "pond"),
        ("फसल", "खेत", "crop", "field", "किसान", "farmer"),
    ),
    "TRANSPORT": (
        ("बस सेवा", "बस स्टैंड", "बस अड्डा", "bus", "depot", "डिपो",
         "public transport", "सार्वजनिक परिवहन", "ऑटो", "auto rickshaw"),
        ("परिवहन", "transport", "आवागमन"),
    ),
}

_STRONG_WEIGHT = 3
_WEAK_WEIGHT = 1


def classify(text: str) -> str:
    """Best-effort category for a message, or "OTHER" if nothing matches.

    Deliberately returns OTHER rather than guessing on a single weak signal: an
    uncategorised request still counts as citizen demand for the district, while
    a miscategorised one pollutes a sector's ranking.
    """
    if not text:
        return "OTHER"

    lowered = text.lower()
    best_category, best_score = "OTHER", 0

    for category, (strong, weak) in KEYWORDS.items():
        score = sum(_STRONG_WEIGHT for term in strong if term.lower() in lowered)
        score += sum(_WEAK_WEIGHT for term in weak if term.lower() in lowered)
        if score > best_score:
            best_category, best_score = category, score

    # A lone weak term is a consequence word ("disease", "crop") that half the
    # categories share — not enough to assign a sector.
    return best_category if best_score >= _STRONG_WEIGHT else "OTHER"
