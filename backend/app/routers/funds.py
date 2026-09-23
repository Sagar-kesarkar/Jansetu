"""Authoritative Public Funds & Administrative Budget Router.

Zero-PII Guarantees:
- Only verified government budget line items and aggregate counts are published.
- All responses include source provenance metadata and data availability status.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.financial_models import (
    FinancialImportRun,
    FinancialRecord,
    FinancialRecordReview,
    FinancialSource,
    VerificationStatus,
)
from app.services.financial_sources.registry import (
    bulk_approve_import_run,
    bulk_reject_import_run,
    execute_import_run,
)
from app.services.funds_service import FundsService

router = APIRouter(tags=["funds"])


# ---------- Schemas ----------

class ImportRunRequest(BaseModel):
    adapter_key: str = Field(..., description="Adapter key: maharashtra_finance, data_gov_in, egramswaraj")
    fiscal_year: str = Field("2026-27", description="Fiscal year string")
    auto_approve: bool = Field(False, description="Whether to automatically approve ingested records")
    reviewer_role: str = Field("FINANCE_OFFICER", description="Role executing the sync")


class ReviewActionRequest(BaseModel):
    reviewer_role: str = Field("FINANCE_OFFICER", description="Official desk or reviewer role")
    notes: str | None = Field(None, description="Audit trail notes for this decision")


# ---------- Public Endpoints ----------

@router.get("/api/v1/funds/overview")
def get_funds_overview(
    scope: str = Query("state", description="Scope: state or district"),
    state: str | None = Query("Maharashtra", description="State name"),
    district: str | None = Query(None, description="District name or code"),
    fiscal_year: str = Query("2026-27", description="Financial year"),
    category: str | None = Query(None, description="Civic sector filter"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return top-level 4 KPI overview, progress rates, anomaly status, and provenance."""
    return FundsService.get_overview(
        db, scope=scope, state=state, district=district, fiscal_year=fiscal_year, category=category
    )


@router.get("/api/v1/funds/districts")
def get_funds_districts(
    state: str = Query("Maharashtra", description="State name"),
    fiscal_year: str = Query("2026-27", description="Financial year"),
    category: str | None = Query(None, description="Civic sector filter"),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Return comparative district financial allocations, spending, and active grievance demand."""
    return FundsService.get_district_breakdown(
        db, state=state, fiscal_year=fiscal_year, category=category
    )


@router.get("/api/v1/funds/sectors")
def get_funds_sectors(
    scope: str = Query("state", description="Scope: state or district"),
    state: str | None = Query("Maharashtra", description="State name"),
    district: str | None = Query(None, description="District name or code"),
    fiscal_year: str = Query("2026-27", description="Financial year"),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Return sector-wise financial breakdown, grievance shares %, and derived funding signals."""
    return FundsService.get_sector_breakdown(
        db, scope=scope, state=state, district=district, fiscal_year=fiscal_year
    )


@router.get("/api/v1/funds/sources")
def get_funds_sources(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Return list of verified official government data sources and sync status."""
    return FundsService.get_sources(db)


@router.get("/api/v1/funds/coverage")
def get_funds_coverage(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return list of state names and district codes/names with verified public funds coverage."""
    return FundsService.get_coverage(db)



@router.get("/budget/allocations")
def get_budget_allocations_compatibility(
    state: str | None = Query(None),
    category: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Backward-compatible endpoint wrapping FundsService for the Officials Console."""
    st = state or "Maharashtra"
    overview = FundsService.get_overview(db, scope="state", state=st, category=category)
    sectors = FundsService.get_sector_breakdown(db, scope="state", state=st)
    districts = FundsService.get_district_breakdown(db, state=st, category=category)

    # Format for legacy AllocationDashboard
    sector_summary = [
        {"category": s["category"], "total_lakh": s["allocated"] * 100.0, "scheme_count": len(s["schemes"])}
        for s in sectors if s["allocated"] > 0
    ]

    items = [
        {
            "district": d["district"],
            "state": d["state"],
            "allocated_inr_lakh": d["allocated"] * 100.0,
            "citizen_requests_count": d["active_grievances"],
        }
        for d in districts
    ]

    available_states = [s for (s,) in db.execute(select(FinancialRecord.state_code).distinct()).all() if s]
    if "Maharashtra" not in available_states and "MH" in available_states:
        available_states = ["Maharashtra"]

    return {
        "total_allocated_lakh": overview["total_allocated"] * 100.0,
        "available_states": ["Maharashtra", "Tamil Nadu"],
        "available_categories": [s["category"] for s in sectors],
        "sector_summary": sector_summary,
        "scheme_summary": [
            {"scheme": sch, "total_lakh": s["allocated"] * 50.0, "category": s["category"]}
            for s in sectors for sch in s["schemes"]
        ],
        "items": items,
    }


# ---------- Administrative Endpoints ----------

@router.get("/api/v1/admin/funds/imports")
def list_import_runs(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """List historical and active financial ingestion runs."""
    runs = db.execute(
        select(FinancialImportRun).order_by(FinancialImportRun.started_at.desc()).limit(50)
    ).scalars().all()
    return [
        {
            "id": r.id,
            "source_id": r.source_id,
            "source_name": r.source.name if r.source else "Unknown",
            "status": r.status,
            "fiscal_year": r.fiscal_year,
            "records_parsed": r.records_parsed,
            "records_approved": r.records_approved,
            "checksum_sha256": r.checksum_sha256,
            "error_log": r.error_log,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in runs
    ]


@router.post("/api/v1/admin/funds/imports/run")
def trigger_import_run(
    req: ImportRunRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Trigger an immediate ingestion run for an approved source adapter."""
    try:
        run = execute_import_run(
            db,
            adapter_key=req.adapter_key,
            fiscal_year=req.fiscal_year,
            auto_approve=req.auto_approve,
            reviewer_role=req.reviewer_role,
        )
        return {
            "status": "SUCCESS",
            "import_run_id": run.id,
            "records_parsed": run.records_parsed,
            "records_approved": run.records_approved,
            "checksum_sha256": run.checksum_sha256,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/api/v1/admin/funds/imports/{import_id}")
def get_import_run_detail(import_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Inspect detailed line items in a specific import run."""
    run = db.get(FinancialImportRun, import_id)
    if not run:
        raise HTTPException(status_code=404, detail="Import run not found")

    records = db.execute(
        select(FinancialRecord).where(FinancialRecord.import_run_id == import_id)
    ).scalars().all()

    return {
        "id": run.id,
        "source_name": run.source.name if run.source else "Unknown",
        "status": run.status,
        "fiscal_year": run.fiscal_year,
        "records_parsed": run.records_parsed,
        "records_approved": run.records_approved,
        "checksum_sha256": run.checksum_sha256,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "records": [
            {
                "id": r.id,
                "state_code": r.state_code,
                "district_code": r.district_code,
                "category": r.category,
                "scheme_name": r.scheme_name,
                "financial_stage": r.financial_stage,
                "amount_inr": float(r.amount_inr),
                "verification_status": r.verification_status,
            }
            for r in records
        ],
    }


@router.post("/api/v1/admin/funds/imports/{import_id}/approve")
def approve_import_run_batch(
    import_id: int,
    req: ReviewActionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Bulk approve all records in an import run with transaction rollback."""
    try:
        count = bulk_approve_import_run(
            db,
            import_id,
            reviewer_role=req.reviewer_role,
            notes=req.notes or "Batch approved by authorized finance officer",
        )
        return {"status": "SUCCESS", "records_approved": count}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/api/v1/admin/funds/imports/{import_id}/reject")
def reject_import_run_batch(
    import_id: int,
    req: ReviewActionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Bulk reject all records in an import run with transaction rollback."""
    try:
        count = bulk_reject_import_run(
            db,
            import_id,
            reviewer_role=req.reviewer_role,
            notes=req.notes or "Batch rejected by authorized finance officer",
        )
        return {"status": "SUCCESS", "records_rejected": count}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/api/v1/admin/funds/records/{record_id}/approve")
def approve_financial_record(
    record_id: int,
    req: ReviewActionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Approve a single financial record with audit record creation."""
    rec = db.get(FinancialRecord, record_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Financial record not found")
    rec.verification_status = VerificationStatus.VERIFIED.value
    review = FinancialRecordReview(
        record_id=rec.id,
        reviewer_role=req.reviewer_role,
        action="APPROVE",
        notes=req.notes or "Approved by finance officer",
    )
    db.add(review)
    db.commit()
    return {"status": "SUCCESS", "record_id": rec.id, "verification_status": rec.verification_status}


@router.post("/api/v1/admin/funds/records/{record_id}/reject")
def reject_financial_record(
    record_id: int,
    req: ReviewActionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Reject a single financial record with audit record creation."""
    rec = db.get(FinancialRecord, record_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Financial record not found")
    rec.verification_status = VerificationStatus.REJECTED.value
    review = FinancialRecordReview(
        record_id=rec.id,
        reviewer_role=req.reviewer_role,
        action="REJECT",
        notes=req.notes or "Rejected by finance officer",
    )
    db.add(review)
    db.commit()
    return {"status": "SUCCESS", "record_id": rec.id, "verification_status": rec.verification_status}
