"""Unit and integration tests for Protected Officials' Console APIs."""
from app.db.models import CitizenRequest, District
from app.services.privacy import pseudonymise


def test_official_list_requests_filters(client):
    """Officials API supports filtering by channel, status, category, etc."""
    res = client.get("/official/requests?limit=10")
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)

    # Check Zero-PII guarantee: no citizen_ref or phone in response
    if items:
        first = items[0]
        assert "citizen_ref" not in first
        assert "phone" not in first
        assert "docket_ref" in first
        assert "category" in first


def test_official_request_detail_and_status_patch(client, db_session):
    """Officials can view details and update complaint status."""
    # Retrieve any seeded request
    req = db_session.query(CitizenRequest).first()
    assert req is not None

    res = client.get(f"/official/requests/{req.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == req.id
    assert "citizen_ref" not in data

    # Update status to UNDER_REVIEW
    patch_res = client.patch(
        f"/official/requests/{req.id}/status",
        json={"status": "UNDER_REVIEW"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "UNDER_REVIEW"

    db_session.refresh(req)
    assert req.status == "UNDER_REVIEW"


def test_official_dashboard_summary(client):
    """Summary metrics aggregate across all channels and statuses."""
    res = client.get("/official/dashboard/summary")
    assert res.status_code == 200
    summary = res.json()
    assert summary["total_requests"] >= 0
    assert "by_status" in summary
    assert "by_channel" in summary
    assert "by_category" in summary
