"""Tests for Stage Precedence, Anti-Double-Counting, and Anomaly Detection."""
from decimal import Decimal
import pytest

from app.db.financial_models import FinancialRecord
from app.services.funds_service import (
    _inr_to_crore,
    _resolve_line_items,
)


def test_inr_to_crore_conversion():
    assert _inr_to_crore(Decimal("10000000.00")) == 1.0  # 1 Cr = 10,000,000 INR
    assert _inr_to_crore(Decimal("1800000000.00")) == 180.0 # 180 Cr
    assert _inr_to_crore(Decimal("0.00")) == 0.0


def test_stage_precedence_re_supersedes_be():
    """When both RE and BE exist for the same scheme line item, RE must supersede BE."""
    records = [
        FinancialRecord(
            fiscal_year="2026-27",
            state_code="MH",
            district_code="MH_PUNE",
            category="WATER_SUPPLY",
            scheme_name="Jal Jeevan Mission",
            financial_stage="BE",
            amount_inr=Decimal("100000000.00"), # 10 Cr BE
        ),
        FinancialRecord(
            fiscal_year="2026-27",
            state_code="MH",
            district_code="MH_PUNE",
            category="WATER_SUPPLY",
            scheme_name="Jal Jeevan Mission",
            financial_stage="RE",
            amount_inr=Decimal("120000000.00"), # 12 Cr RE
        ),
    ]

    resolved = _resolve_line_items(records)
    key = ("2026-27", "MH", "MH_PUNE", "WATER_SUPPLY", "Jal Jeevan Mission")
    assert key in resolved
    item = resolved[key]
    assert item.allocated_stage == "RE"
    assert item.allocated_inr == Decimal("120000000.00") # Exactly 12 Cr, never 22 Cr


def test_stage_precedence_actual_supersedes_payment():
    """When both ACTUAL and PAYMENT exist for the same scheme line item, ACTUAL must supersede PAYMENT."""
    records = [
        FinancialRecord(
            fiscal_year="2026-27",
            state_code="MH",
            district_code="MH_PUNE",
            category="WATER_SUPPLY",
            scheme_name="Jal Jeevan Mission",
            financial_stage="PAYMENT",
            amount_inr=Decimal("60000000.00"), # 6 Cr provisional payment
        ),
        FinancialRecord(
            fiscal_year="2026-27",
            state_code="MH",
            district_code="MH_PUNE",
            category="WATER_SUPPLY",
            scheme_name="Jal Jeevan Mission",
            financial_stage="ACTUAL",
            amount_inr=Decimal("80000000.00"), # 8 Cr audited actual
        ),
    ]

    resolved = _resolve_line_items(records)
    key = ("2026-27", "MH", "MH_PUNE", "WATER_SUPPLY", "Jal Jeevan Mission")
    assert key in resolved
    item = resolved[key]
    assert item.spent_stage == "ACTUAL"
    assert item.spent_inr == Decimal("80000000.00") # Exactly 8 Cr, never 14 Cr


def test_disjoint_stage_bucketing():
    """BE, RELEASE, and ACTUAL must be stored in distinct buckets."""
    records = [
        FinancialRecord(
            fiscal_year="2026-27",
            state_code="MH",
            district_code="MH_PUNE",
            category="ROADS",
            scheme_name="PMGSY",
            financial_stage="BE",
            amount_inr=Decimal("1400000000.00"),
        ),
        FinancialRecord(
            fiscal_year="2026-27",
            state_code="MH",
            district_code="MH_PUNE",
            category="ROADS",
            scheme_name="PMGSY",
            financial_stage="RELEASE",
            amount_inr=Decimal("1300000000.00"),
        ),
        FinancialRecord(
            fiscal_year="2026-27",
            state_code="MH",
            district_code="MH_PUNE",
            category="ROADS",
            scheme_name="PMGSY",
            financial_stage="ACTUAL",
            amount_inr=Decimal("1200000000.00"),
        ),
    ]

    resolved = _resolve_line_items(records)
    key = ("2026-27", "MH", "MH_PUNE", "ROADS", "PMGSY")
    item = resolved[key]
    assert item.allocated_inr == Decimal("1400000000.00")
    assert item.released_inr == Decimal("1300000000.00")
    assert item.spent_inr == Decimal("1200000000.00")
    # Available = Released - Spent
    avail = item.released_inr - item.spent_inr
    assert avail == Decimal("100000000.00") # 10 Cr remaining
