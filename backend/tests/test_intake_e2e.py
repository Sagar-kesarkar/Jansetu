"""End-to-end flow test — the rule the hackathon states first.

Runs the whole path with Gemini disabled (no GEMINI_API_KEY), which proves the
pipeline degrades instead of crashing. With a key present the same test passes
and the extraction is real; assertions here deliberately avoid depending on
model output so the suite stays deterministic in CI.
"""
import pytest
from fastapi.testclient import TestClient

from app.db.database import SessionLocal, init_db
from app.db.models import CitizenRequest, District, InfraIndex, InvestmentPlan
from app.main import app


@pytest.fixture(scope="module", autouse=True)
def seeded_db():
    init_db()
    db = SessionLocal()
    try:
        db.query(CitizenRequest).delete()
        db.query(InfraIndex).delete()
        db.query(InvestmentPlan).delete()
        db.add(District(code="TEST_D1", name="Testpur", state="Testland",
                        population=1_000_000, latitude=20.0, longitude=80.0,
                        literacy_pct=55.0, internet_pct=15.0, deprivation_index=0.8))
        db.add(InfraIndex(district_code="TEST_D1", category="WATER_SUPPLY", coverage_pct=30.0))
        db.add(InvestmentPlan(district_code="TEST_D1", category="WATER_SUPPLY",
                              scheme="Jal Jeevan Mission", allocated_inr_lakh=50.0))
        for _ in range(5):
            db.add(CitizenRequest(
                district_code="TEST_D1", category="WATER_SUPPLY", urgency=4,
                raw_text="seed", summary_en="seed", language="hi",
                channel="whatsapp", location_text="Testpur, Testland", confidence=1.0))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health_and_capabilities(client):
    assert client.get("/health").json()["status"] == "ok"
    caps = client.get("/capabilities").json()
    assert caps["google_ai"]["billing_account_required"] is False
    assert len(caps["languages"]) >= 12          # multilingual coverage
    assert "WATER_SUPPLY" in caps["categories"]


def test_text_intake_persists_and_resolves_district(client):
    r = client.post("/intake/text", json={
        "text": "हमारे गाँव में पानी नहीं आ रहा है",
        "language": "hi",
        "location_text": "Testpur, Testland",
        "channel": "whatsapp",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["request_id"] > 0
    assert body["district"] == "Testpur"       # geocoding resolved
    assert body["language"] == "hi"
    assert body["acknowledgement_native"]      # citizen gets a reply


def test_hotspots_then_recommendations(client):
    hot = client.get("/hotspots", params={"category": "WATER_SUPPLY"}).json()
    assert hot and hot[0]["district"] == "Testpur"
    assert hot[0]["rank"] == 1

    recs = client.get("/recommendations", params={"category": "WATER_SUPPLY"}).json()
    assert recs, "an end-to-end run must yield at least one recommendation"
    top = recs[0]
    assert top["linked_scheme"] == "Jal Jeevan Mission"
    assert top["est_beneficiaries"] > 0
    assert top["rationale"]
    # Evidence must be present and auditable, not a bare score.
    ev = top["evidence"]
    assert ev["citizen_requests"] >= 5
    assert ev["coverage_gap_pct"] == 70.0
    assert set(ev["weights"]) == {"demand", "coverage_gap", "deprivation", "underfunding"}


def test_voice_intake_rejects_empty_upload(client):
    r = client.post("/intake/voice", files={"audio": ("a.webm", b"", "audio/webm")},
                    data={"language": "hi"})
    assert r.status_code == 422
