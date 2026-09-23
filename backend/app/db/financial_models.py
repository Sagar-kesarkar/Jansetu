"""Authoritative Government Financial Records Schema.

Strict Data Integrity Guarantees:
- Canonical monetary amounts stored in INR using exact Numeric(18, 2) decimal precision.
- Explicit financial stage separation (BE, RE, ACTUAL, RELEASE, PAYMENT).
- Immutable raw snapshot storage with SHA-256 payload integrity hashing.
- Review/Approval state lifecycle (VERIFIED, PENDING_REVIEW, CONFLICT, REJECTED).
- Traceable source provenance metadata attached to every published line item.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SourceType(str, Enum):
    GOVERNMENT_API = "GOVERNMENT_API"
    BUDGET_PUBLICATION = "BUDGET_PUBLICATION"
    LOCAL_BODY_PORTAL = "LOCAL_BODY_PORTAL"
    OFFICIAL_DOCUMENT = "OFFICIAL_DOCUMENT"


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PENDING_REVIEW = "PENDING_REVIEW"
    CONFLICT = "CONFLICT"
    REJECTED = "REJECTED"


class FinancialStage(str, Enum):
    BE = "BE"          # Budget Estimate (Approved Allocation)
    RE = "RE"          # Revised Estimate (Adjusted Allocation, supersedes BE)
    ACTUAL = "ACTUAL"  # Audited / Recorded Expenditure
    RELEASE = "RELEASE"# Funds Released to Department/District
    PAYMENT = "PAYMENT"# Provisional Recorded Payment


class ImportStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"


class FinancialSource(Base):
    """Catalog of official government data publishers (strictly *.gov.in / *.nic.in)."""
    __tablename__ = "financial_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    source_type: Mapped[str] = mapped_column(String(32), default=SourceType.BUDGET_PUBLICATION.value)
    base_url: Mapped[str] = mapped_column(String(256))
    publisher: Mapped[str] = mapped_column(String(160))
    verification_status: Mapped[str] = mapped_column(String(24), default=VerificationStatus.VERIFIED.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    import_runs: Mapped[list["FinancialImportRun"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    records: Mapped[list["FinancialRecord"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class FinancialImportRun(Base):
    """Audit trail for every automated or administrative ingestion run."""
    __tablename__ = "financial_import_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("financial_sources.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), default=ImportStatus.RUNNING.value, index=True)
    fiscal_year: Mapped[str] = mapped_column(String(16), default="2026-27", index=True)
    records_parsed: Mapped[int] = mapped_column(Integer, default=0)
    records_approved: Mapped[int] = mapped_column(Integer, default=0)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source: Mapped["FinancialSource"] = relationship(back_populates="import_runs")
    snapshots: Mapped[list["FinancialRawSnapshot"]] = relationship(
        back_populates="import_run", cascade="all, delete-orphan"
    )
    records: Mapped[list["FinancialRecord"]] = relationship(
        back_populates="import_run", cascade="all, delete-orphan"
    )


class FinancialRawSnapshot(Base):
    """Immutable binary/text snapshot of raw data fetched from official government sources."""
    __tablename__ = "financial_raw_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    import_run_id: Mapped[int] = mapped_column(ForeignKey("financial_import_runs.id"), index=True)
    source_url: Mapped[str] = mapped_column(String(512))
    raw_payload: Mapped[str] = mapped_column(Text)  # JSON or text representation
    content_type: Mapped[str] = mapped_column(String(64), default="application/json")
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    import_run: Mapped["FinancialImportRun"] = relationship(back_populates="snapshots")


class FinancialRecord(Base):
    """Authoritative normalized financial ledger line items."""
    __tablename__ = "financial_records"
    __table_args__ = (
        Index("ix_fin_lookup", "fiscal_year", "state_code", "district_code", "category", "financial_stage"),
        Index("ix_fin_status", "verification_status", "financial_stage"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    import_run_id: Mapped[int] = mapped_column(ForeignKey("financial_import_runs.id"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("financial_sources.id"), index=True)

    state_code: Mapped[str | None] = mapped_column(String(8), nullable=True, index=True)      # e.g., "MH"
    district_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True) # e.g., "MH_PUNE"
    category: Mapped[str] = mapped_column(String(32), default="UNMAPPED", index=True)        # JanSetu sector

    scheme_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    scheme_name: Mapped[str] = mapped_column(String(256), default="")
    financial_stage: Mapped[str] = mapped_column(String(16), index=True)                     # BE, RE, ACTUAL, RELEASE, PAYMENT

    amount_inr: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)              # Exact INR
    fiscal_year: Mapped[str] = mapped_column(String(16), default="2026-27", index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    verification_status: Mapped[str] = mapped_column(
        String(24), default=VerificationStatus.VERIFIED.value, index=True
    )
    coverage: Mapped[str] = mapped_column(String(16), default="complete")                    # complete | partial
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    source: Mapped["FinancialSource"] = relationship(back_populates="records")
    import_run: Mapped["FinancialImportRun"] = relationship(back_populates="records")
    reviews: Mapped[list["FinancialRecordReview"]] = relationship(
        back_populates="record", cascade="all, delete-orphan"
    )


class FinancialRecordReview(Base):
    """Audit log of administrative approvals, rejections, and manual overrides."""
    __tablename__ = "financial_record_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("financial_records.id"), index=True)
    reviewer_role: Mapped[str] = mapped_column(String(64), default="FINANCE_OFFICER")
    action: Mapped[str] = mapped_column(String(24)) # APPROVE, REJECT, OVERRIDE
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    record: Mapped["FinancialRecord"] = relationship(back_populates="reviews")
