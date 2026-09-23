"""The no-key path has to be honest about being a fallback, but it still has to
work. These sentences are the ones `data/scripts/generate_requests.py` puts in
the database, so if the seed corpus is ever rephrased this test fails rather than
the demo silently regressing to "OTHER" for everything."""
from app.i18n.keywords import classify
from app.services.gemini import _fallback_extract, extract_request

# (message, expected category). Deliberately spread across scripts — a table
# that only works in Devanagari would pass a test and fail the video.
NATIVE_CASES = [
    ("हमारे गाँव में पीने का पानी नहीं आ रहा है", "WATER_SUPPLY"),
    ("আমাদের গ্রামে নলের জল আসছে না", "WATER_SUPPLY"),
    ("எங்கள் ஊரில் குழாய் தண்ணீர் வரவில்லை", "WATER_SUPPLY"),
    ("ଆମ ଗାଁରେ ନଳ ପାଣି ଆସୁନାହିଁ", "WATER_SUPPLY"),
    ("ನಮ್ಮ ಹಳ್ಳಿಯಲ್ಲಿ ನಲ್ಲಿ ನೀರು ಬರುತ್ತಿಲ್ಲ", "WATER_SUPPLY"),
    ("गाँव की सड़क पूरी टूट गई है", "ROADS"),
    ("আমাদের রাস্তা সম্পূর্ণ ভেঙে গেছে", "ROADS"),
    ("दिन में आठ घंटे बिजली कटती है", "ELECTRICITY"),
    ("সাত ঘণ্টা বিদ্যুৎ থাকে না", "ELECTRICITY"),
    ("सबसे नज़दीकी अस्पताल तीस किलोमीटर दूर है", "HEALTH"),
    ("গ্রামে কোনো নর্দমা নেই", "SANITATION"),
    ("गाँव के स्कूल में एक भी शिक्षक नहीं है", "EDUCATION"),
    ("यहाँ मोबाइल नेटवर्क नहीं आता", "DIGITAL"),
    ("नहर का पानी खेत तक नहीं पहुँचता", "IRRIGATION"),
    ("no piped water supply in our village for three months", "WATER_SUPPLY"),
    ("the village road is completely broken", "ROADS"),
]


def test_native_script_messages_are_classified():
    for message, expected in NATIVE_CASES:
        assert classify(message) == expected, f"{message!r} -> {classify(message)}"


def test_sanitation_beats_water_when_the_ask_is_a_drain():
    """The overlap case the two-tier weighting exists for: this sentence contains
    the word for water but is asking for drainage."""
    assert classify("बरसात का पानी घरों में घुस जाता है क्योंकि नाली नहीं है") == "SANITATION"


def test_unrecognised_message_is_other_not_a_guess():
    """A wrong sector pollutes that sector's ranking; OTHER only costs us the
    sector breakdown while still counting as demand for the district."""
    assert classify("मुझे कुछ कहना है") == "OTHER"
    assert classify("") == "OTHER"


def test_a_lone_consequence_word_is_not_enough():
    """"Disease" appears in sanitation, water and health complaints alike."""
    assert classify("गाँव में बीमारी फैल रही है") == "OTHER"


def test_fallback_reports_low_confidence_even_when_it_is_right():
    """The 0.1 is a provenance flag, not a certainty estimate — the dashboard
    renders it so a judge can tell which rows the model never saw."""
    result = _fallback_extract("हमारे गाँव में पीने का पानी नहीं आ रहा है", "hi")
    assert result.category == "WATER_SUPPLY"
    assert result.confidence == 0.1


def test_extract_request_uses_the_fallback_with_no_key(monkeypatch):
    """End-to-end proof of constraint 2: with no credential at all, intake still
    produces a usable record rather than raising."""
    monkeypatch.setattr("app.services.gemini._client", lambda: None)
    result = extract_request("गाँव की सड़क पूरी टूट गई है", language="hi")
    assert result.category == "ROADS"
    assert result.confidence == 0.1
