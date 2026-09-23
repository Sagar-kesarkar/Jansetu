"""Tests for Public Funds API, Admin Workflow, and Consistency."""
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.db.financial_models import (
    FinancialImportRun,
    FinancialRecord,
    FinancialSource,
    VerificationStatus,
)
from app.main import app
from app.services.financial_sources.registry import execute_import_run

client = TestClient(app)


@pytest.fixture(autouse=True)
def _seed_test_funds():
    with SessionLocal() as db:
        try:
            execute_import_run(db, "maharashtra_finance", auto_approve=True)
            execute_import_run(db, "data_gov_in", auto_approve=True)
        except Exception:
            pass
    yield


def test_funds_overview_endpoint():
    """GET /api/v1/funds/overview returns 200 with 4 KPI fields and provenance metadata."""
    res = client.get("/api/v1/funds/overview?state=Maharashtra&fiscal_year=2026-27")
    assert res.status_code == 200
    data = res.json()
    assert "total_allocated" in data
    assert "funds_released" in data
    assert "recorded_expenditure" in data
    assert "available_funds" in data
    assert "release_rate_pct" in data
    assert "utilisation_rate_pct" in data
    assert "metadata" in data
    assert data["metadata"]["verification_status"] == "VERIFIED"
    assert data["total_allocated"] > 0
    assert data["funds_released"] > 0


def test_funds_districts_endpoint():
    """GET /api/v1/funds/districts returns comparative list."""
    res = client.get("/api/v1/funds/districts?state=Maharashtra&fiscal_year=2026-27")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if data:
        first = data[0]
        assert "district" in first
        assert "allocated" in first
        assert "released" in first
        assert "spent" in first
        assert "active_grievances" in first


def test_funds_sectors_endpoint():
    """GET /api/v1/funds/sectors returns sector shares and signals."""
    res = client.get("/api/v1/funds/sectors?state=Maharashtra&fiscal_year=2026-27")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if data:
        first = data[0]
        assert "category" in first
        assert "label" in first
        assert "grievance_share_pct" in first
        assert "allocation_share_pct" in first
        assert "assessment" in first


def test_unapproved_records_excluded_from_public_api():
    """Records with PENDING_REVIEW or REJECTED status must never appear in public API aggregates."""
    with SessionLocal() as db:
        source = db.query(FinancialSource).first()
        assert source is not None

        # Create a pending import run
        import_run = FinancialImportRun(
            source_id=source.id,
            status="PENDING_REVIEW",
            fiscal_year="2099-00",
        )
        db.add(import_run)
        db.flush()

        # Add a huge unapproved budget record
        fake_rec = FinancialRecord(
            import_run_id=import_run.id,
            source_id=source.id,
            state_code="MH",
            district_code="MH_PUNE",
            category="WATER_SUPPLY",
            scheme_name="Unapproved Future Scheme",
            financial_stage="BE",
            amount_inr=Decimal("99999999999.00"),
            fiscal_year="2099-00",
            verification_status=VerificationStatus.PENDING_REVIEW.value,
        )
        db.add(fake_rec)
        db.commit()

    # Query public overview for the unapproved fiscal year
    res = client.get("/api/v1/funds/overview?state=Maharashtra&fiscal_year=2099-00")
    assert res.status_code == 200
    data = res.json()
    # Must return 0 because unapproved records are excluded
    assert data["total_allocated"] == 0.0
    assert data["is_data_available"] is False


def test_admin_bulk_approve_exposes_records():
    """Admin bulk approval of an import run transitions records to VERIFIED and exposes them."""
    with SessionLocal() as db:
        source = db.query(FinancialSource).first()
        import_run = FinancialImportRun(
            source_id=source.id,
            status="PENDING_REVIEW",
            fiscal_year="2030-31",
        )
        db.add(import_run)
        db.flush()

        rec = FinancialRecord(
            import_run_id=import_run.id,
            source_id=source.id,
            state_code="MH",
            district_code="MH_PUNE",
            category="ROADS",
            scheme_name="Future Highway 2030",
            financial_stage="BE",
            amount_inr=Decimal("500000000.00"), # 50 Cr
            fiscal_year="2030-31",
            verification_status=VerificationStatus.PENDING_REVIEW.value,
        )
        db.add(rec)
        db.commit()
        run_id = import_run.id

    # Before approval: 0
    res_before = client.get("/api/v1/funds/overview?state=Maharashtra&fiscal_year=2030-31")
    assert res_before.json()["total_allocated"] == 0.0

    # Bulk approve
    res_approve = client.post(
        f"/api/v1/admin/funds/imports/{run_id}/approve",
        json={"reviewer_role": "CHIEF_AUDITOR", "notes": "Verified against state gazette"},
    )
    assert res_approve.status_code == 200
    assert res_approve.json()["status"] == "SUCCESS"

    # After approval: 50 Cr exposed
    res_after = client.get("/api/v1/funds/overview?state=Maharashtra&fiscal_year=2030-31")
    assert res_after.json()["total_allocated"] == 50.0


def test_cross_frontend_consistency():
    """Public Funds overview and backward-compatible /budget/allocations return matching totals."""
    res_overview = client.get("/api/v1/funds/overview?state=Maharashtra&fiscal_year=2026-27")
    res_compat = client.get("/budget/allocations?state=Maharashtra")

    assert res_overview.status_code == 200
    overview_cr = res_overview.json()["total_allocated"]
    compat_lakh = res_compat.json()["total_allocated_lakh"]
    compat_cr = round(compat_lakh / 100.0, 2)

    assert overview_cr == compat_cr


def test_admin_single_record_approve_and_reject():
    """Test approving and rejecting a single financial record with audit trail."""
    with SessionLocal() as db:
        source = db.query(FinancialSource).first()
        import_run = FinancialImportRun(
            source_id=source.id,
            status="PENDING_REVIEW",
            fiscal_year="2035-36",
        )
        db.add(import_run)
        db.flush()

        rec = FinancialRecord(
            import_run_id=import_run.id,
            source_id=source.id,
            state_code="MH",
            district_code="MH_PUNE",
            category="HEALTH",
            scheme_name="District Hospital Expansion",
            financial_stage="BE",
            amount_inr=Decimal("250000000.00"),
            fiscal_year="2035-36",
            verification_status=VerificationStatus.PENDING_REVIEW.value,
        )
        db.add(rec)
        db.commit()
        record_id = rec.id

    # Approve single record
    res_app = client.post(
        f"/api/v1/admin/funds/records/{record_id}/approve",
        json={"reviewer_role": "FINANCE_OFFICER", "notes": "Approved individual line item"},
    )
    assert res_app.status_code == 200
    assert res_app.json()["verification_status"] == "VERIFIED"

    # Reject single record
    res_rej = client.post(
        f"/api/v1/admin/funds/records/{record_id}/reject",
        json={"reviewer_role": "FINANCE_OFFICER", "notes": "Rejected due to revision"},
    )
    assert res_rej.status_code == 200
    assert res_rej.json()["verification_status"] == "REJECTED"
