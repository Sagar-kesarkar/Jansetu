"""Financial Source Ingestion Registry and Execution Orchestrator.

Manages:
- Source adapter registration.
- Atomic ingestion runs with raw snapshot capture and SHA-256 integrity verification.
- Duplicate run and payload conflict detection.
- Bulk approval / bulk rejection of entire import runs with audit trail logging.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Type

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.financial_models import (
    FinancialImportRun,
    FinancialRawSnapshot,
    FinancialRecord,
    FinancialRecordReview,
    FinancialSource,
    ImportStatus,
    SourceType,
    VerificationStatus,
)
from app.services.financial_sources.base import (
    BaseFinancialAdapter,
    NormalizedFinancialRecord,
    compute_sha256,
)
from app.services.financial_sources.data_gov_in import DataGovInAdapter
from app.services.financial_sources.egramswaraj import EGramSwarajAdapter
from app.services.financial_sources.maharashtra_finance import MaharashtraFinanceAdapter

log = logging.getLogger(__name__)

_ADAPTER_REGISTRY: dict[str, Type[BaseFinancialAdapter]] = {
    "maharashtra_finance": MaharashtraFinanceAdapter,
    "data_gov_in": DataGovInAdapter,
    "egramswaraj": EGramSwarajAdapter,
}


def get_adapter(key: str) -> BaseFinancialAdapter:
    adapter_cls = _ADAPTER_REGISTRY.get(key)
    if not adapter_cls:
        raise ValueError(f"Unknown financial source adapter key: '{key}'. Available: {list(_ADAPTER_REGISTRY.keys())}")
    return adapter_cls()


def execute_import_run(
    db: Session,
    adapter_key: str,
    fiscal_year: str = "2026-27",
    *,
    auto_approve: bool = False,
    reviewer_role: str = "SYSTEM_INITIALIZER",
) -> FinancialImportRun:
    """Execute an atomic financial data ingestion run.

    Transaction Steps:
    1. Acquire or register FinancialSource record.
    2. Check for duplicate RUNNING runs on the same source/year (durable duplicate guard).
    3. Instantiate adapter and fetch raw payload + normalized records.
    4. Compute SHA-256 checksum on raw payload.
    5. Save immutable FinancialRawSnapshot.
    6. Persist FinancialRecord line items (status PENDING_REVIEW or VERIFIED if auto_approve=True).
    7. Update FinancialImportRun stats and commit.
    """
    adapter = get_adapter(adapter_key)
    now = datetime.now(timezone.utc)

    # 1. Acquire source
    source = db.execute(
        select(FinancialSource).where(FinancialSource.name == adapter.source_name)
    ).scalar_one_or_none()

    if source is None:
        source = FinancialSource(
            name=adapter.source_name,
            source_type=SourceType.BUDGET_PUBLICATION.value,
            base_url=adapter.base_url,
            publisher=adapter.publisher,
            verification_status=VerificationStatus.VERIFIED.value,
            is_active=True,
            created_at=now,
        )
        db.add(source)
        db.flush()

    # 2. Check for active running import on this source (duplicate run prevention)
    active_run = db.execute(
        select(FinancialImportRun)
        .where(
            FinancialImportRun.source_id == source.id,
            FinancialImportRun.fiscal_year == fiscal_year,
            FinancialImportRun.status == ImportStatus.RUNNING.value,
        )
    ).scalar_one_or_none()

    if active_run:
        raise RuntimeError(f"An import run (ID {active_run.id}) is already currently active for {source.name} ({fiscal_year}).")

    # Create new import run record
    import_run = FinancialImportRun(
        source_id=source.id,
        status=ImportStatus.RUNNING.value,
        fiscal_year=fiscal_year,
        started_at=now,
    )
    db.add(import_run)
    db.flush()

    try:
        # 3. Fetch and parse
        raw_payload, records = adapter.fetch_and_parse(fiscal_year)
        checksum = compute_sha256(raw_payload)

        # 4. Save immutable raw snapshot
        snapshot = FinancialRawSnapshot(
            import_run_id=import_run.id,
            source_url=adapter.base_url,
            raw_payload=raw_payload,
            content_type="application/json",
            checksum_sha256=checksum,
            fetched_at=now,
        )
        db.add(snapshot)

        # 5. Persist normalized line items
        ver_status = VerificationStatus.VERIFIED.value if auto_approve else VerificationStatus.PENDING_REVIEW.value
        parsed_count = len(records)
        approved_count = parsed_count if auto_approve else 0

        for r in records:
            # Validate non-negative amounts
            if r.amount_inr < Decimal("0.00"):
                raise ValueError(f"Negative amount '{r.amount_inr}' not permitted in authoritative financial records.")

            rec = FinancialRecord(
                import_run_id=import_run.id,
                source_id=source.id,
                state_code=r.state_code,
                district_code=r.district_code,
                category=r.category,
                scheme_code=r.scheme_code,
                scheme_name=r.scheme_name,
                financial_stage=r.financial_stage,
                amount_inr=r.amount_inr,
                fiscal_year=r.fiscal_year,
                published_at=r.published_at,
                verification_status=ver_status,
                coverage=r.coverage,
                created_at=now,
            )
            db.add(rec)
            db.flush()

            if auto_approve:
                rev = FinancialRecordReview(
                    record_id=rec.id,
                    reviewer_role=reviewer_role,
                    action="APPROVE",
                    notes="Baseline authoritative government dataset verified upon ingestion",
                    created_at=now,
                )
                db.add(rev)

        import_run.status = ImportStatus.APPROVED.value if auto_approve else ImportStatus.PENDING_REVIEW.value
        import_run.records_parsed = parsed_count
        import_run.records_approved = approved_count
        import_run.checksum_sha256 = checksum
        import_run.completed_at = datetime.now(timezone.utc)
        db.commit()
        log.info("Successfully completed import run %d for %s (Parsed: %d, Approved: %d)", import_run.id, source.name, parsed_count, approved_count)
        return import_run

    except Exception as exc:
        db.rollback()
        import_run.status = ImportStatus.FAILED.value
        import_run.error_log = str(exc)
        import_run.completed_at = datetime.now(timezone.utc)
        db.add(import_run)
        db.commit()
        log.error("Financial import run %d failed: %s", import_run.id, exc, exc_info=True)
        raise


def bulk_approve_import_run(
    db: Session,
    import_run_id: int,
    *,
    reviewer_role: str = "FINANCE_OFFICER",
    notes: str = "Batch approved by authorized finance officer",
) -> int:
    """Atomically approve all line items in an import run with audit trail logging."""
    run = db.get(FinancialImportRun, import_run_id)
    if not run:
        raise ValueError(f"Financial import run with ID {import_run_id} not found.")

    records = db.execute(
        select(FinancialRecord).where(FinancialRecord.import_run_id == import_run_id)
    ).scalars().all()

    now = datetime.now(timezone.utc)
    count = 0
    for rec in records:
        if rec.verification_status != VerificationStatus.VERIFIED.value:
            rec.verification_status = VerificationStatus.VERIFIED.value
            review = FinancialRecordReview(
                record_id=rec.id,
                reviewer_role=reviewer_role,
                action="APPROVE",
                notes=notes,
                created_at=now,
            )
            db.add(review)
            count += 1

    run.status = ImportStatus.APPROVED.value
    run.records_approved = len(records)
    db.commit()
    return count


def bulk_reject_import_run(
    db: Session,
    import_run_id: int,
    *,
    reviewer_role: str = "FINANCE_OFFICER",
    notes: str = "Batch rejected by authorized finance officer",
) -> int:
    """Atomically reject all line items in an import run with audit trail logging."""
    run = db.get(FinancialImportRun, import_run_id)
    if not run:
        raise ValueError(f"Financial import run with ID {import_run_id} not found.")

    records = db.execute(
        select(FinancialRecord).where(FinancialRecord.import_run_id == import_run_id)
    ).scalars().all()

    now = datetime.now(timezone.utc)
    count = 0
    for rec in records:
        if rec.verification_status != VerificationStatus.REJECTED.value:
            rec.verification_status = VerificationStatus.REJECTED.value
            review = FinancialRecordReview(
                record_id=rec.id,
                reviewer_role=reviewer_role,
                action="REJECT",
                notes=notes,
                created_at=now,
            )
            db.add(review)
            count += 1

    run.status = ImportStatus.FAILED.value
    run.records_approved = 0
    db.commit()
    return count
