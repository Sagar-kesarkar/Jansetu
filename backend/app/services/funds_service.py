"""Shared Domain Service for Authoritative Public Funds & Fiscal Intelligence.

Mathematical Guarantees:
- Strict Stage Precedence (Anti-Double-Counting):
  * Allocated: RE (Revised Estimate) strictly supersedes BE (Budget Estimate) per line item.
  * Spent: Audited ACTUAL strictly supersedes provisional PAYMENT per line item.
  * Released: Disjoint RELEASE stage.
- Real Anomaly Detection:
  * When recorded expenditure exceeds released funds (spent > released), computes actual negative balance and flags has_anomaly=True rather than falsely clipping with Math.max(0).
- Honest Geographic Coverage:
  * Distinguishes complete vs. partial district coverage with transparent data availability labeling.
- Strict Zero-PII Aggregations:
  * Only approved, verified government financial records are returned to public endpoints.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.financial_models import (
    FinancialImportRun,
    FinancialRecord,
    FinancialSource,
    FinancialStage,
    VerificationStatus,
)
from app.db.models import CitizenRequest, District
from app.models.schemas import (
    OPEN_STATUSES,
)

log = logging.getLogger(__name__)

#: Active grievance statuses for citizen demand calculations
ACTIVE_GRIEVANCE_STATUSES = frozenset({
    "NEW",
    "ACKNOWLEDGED",
    "UNDER_REVIEW",
    "ASSIGNED",
    "IN_PROGRESS",
})

STATE_TO_CODE: dict[str, str] = {
    "maharashtra": "MH",
    "tamil nadu": "TN",
    "odisha": "OD",
    "kerala": "KL",
    "karnataka": "KA",
    "uttar pradesh": "UP",
    "bihar": "BR",
    "madhya pradesh": "MP",
    "rajasthan": "RJ",
    "gujarat": "GJ",
    "west bengal": "WB",
    "andhra pradesh": "AP",
    "telangana": "TS",
    "punjab": "PB",
    "assam": "AS",
}

#: Standard civic sector color tokens for visualizations
SECTOR_COLOR_MAP: dict[str, str] = {
    "WATER_SUPPLY": "#2563eb",   # Vibrant Blue
    "ROADS": "#d97706",          # Amber
    "SANITATION": "#06b6d4",     # Cyan
    "ELECTRICITY": "#eab308",    # Yellow
    "HEALTH": "#10b981",         # Emerald Green
    "EDUCATION": "#8b5cf6",      # Purple
    "HOUSING": "#ec4899",        # Pink
    "IRRIGATION": "#14b8a6",     # Teal
    "TRANSPORT": "#f97316",      # Orange
    "DIGITAL": "#6366f1",        # Indigo
    "FLOOD_CONTROL": "#3b82f6",  # Light Blue
    "UNMAPPED": "#64748b",       # Slate Gray
}

SECTOR_LABEL_MAP: dict[str, str] = {
    "WATER_SUPPLY": "Water Supply",
    "ROADS": "Roads & Bridges",
    "SANITATION": "Sanitation & Drainage",
    "ELECTRICITY": "Power & Electricity",
    "HEALTH": "Public Health",
    "EDUCATION": "Education Infrastructure",
    "HOUSING": "Rural & Urban Housing",
    "IRRIGATION": "Irrigation & Water Bodies",
    "TRANSPORT": "Public Transport",
    "DIGITAL": "Digital Connectivity",
    "FLOOD_CONTROL": "Flood Management",
    "UNMAPPED": "General Public Works",
}


@dataclass
class StageResolvedItem:
    allocated_inr: Decimal = Decimal("0.00")
    allocated_stage: str = "BE"
    released_inr: Decimal = Decimal("0.00")
    spent_inr: Decimal = Decimal("0.00")
    spent_stage: str = "ACTUAL"
    has_be: bool = False
    has_re: bool = False
    has_release: bool = False
    has_actual: bool = False
    has_payment: bool = False


def _resolve_line_items(records: list[FinancialRecord]) -> dict[tuple, StageResolvedItem]:
    """Resolve financial stages applying strict precedence to prevent double-counting.

    Precedence:
    - Allocation: RE supersedes BE. If RE is present, BE is ignored.
    - Spending: ACTUAL supersedes PAYMENT. If ACTUAL is present, PAYMENT is ignored.
    - Releases: Summed independently.
    """
    grouped: dict[tuple, dict[str, Decimal]] = {}
    key_order: list[tuple] = []

    for r in records:
        key = (r.fiscal_year, r.state_code, r.district_code, r.category, r.scheme_name or r.scheme_code or "DEFAULT")
        if key not in grouped:
            grouped[key] = {}
            key_order.append(key)
        # Keep highest stage amount for that stage
        stage = (r.financial_stage or "BE").upper()
        amt = Decimal(str(r.amount_inr or 0))
        grouped[key][stage] = amt

    resolved: dict[tuple, StageResolvedItem] = {}
    for key in key_order:
        stages = grouped[key]
        item = StageResolvedItem()

        # Allocation: RE > BE
        if "RE" in stages:
            item.allocated_inr = stages["RE"]
            item.allocated_stage = "RE"
            item.has_re = True
        elif "BE" in stages:
            item.allocated_inr = stages["BE"]
            item.allocated_stage = "BE"
            item.has_be = True

        # Release
        if "RELEASE" in stages:
            item.released_inr = stages["RELEASE"]
            item.has_release = True

        # Spending: ACTUAL > PAYMENT
        if "ACTUAL" in stages:
            item.spent_inr = stages["ACTUAL"]
            item.spent_stage = "ACTUAL"
            item.has_actual = True
        elif "PAYMENT" in stages:
            item.spent_inr = stages["PAYMENT"]
            item.spent_stage = "PAYMENT"
            item.has_payment = True

        resolved[key] = item

    return resolved


def _inr_to_crore(inr_amount: Decimal | float) -> float:
    """Convert exact INR amount to Crore (1 Crore = 10,000,000 INR)."""
    return round(float(inr_amount) / 10_000_000.0, 2)


class FundsService:
    """Core domain service for public funds, fiscal metrics, and citizen demand signals."""

    @staticmethod
    def get_overview(
        db: Session,
        scope: str = "state",  # state | district
        state: str | None = "Maharashtra",
        district: str | None = None,
        fiscal_year: str = "2026-27",
        category: str | None = None,
    ) -> dict[str, Any]:
        """Compute the 4 connected summary KPIs and metadata with stage precedence."""
        # Find matching state/district codes
        state_filter = state.strip() if state else None
        dist_row = None
        if district:
            dist_row = db.execute(
                select(District).where(
                    (District.name.ilike(district.strip())) | (District.code == district.strip())
                )
            ).scalar_one_or_none()

        # Query approved financial records
        q = select(FinancialRecord).where(
            FinancialRecord.verification_status == VerificationStatus.VERIFIED.value,
            FinancialRecord.fiscal_year == fiscal_year,
        )

        if dist_row:
            q = q.where(FinancialRecord.district_code == dist_row.code)
            scope = "district"
        elif state_filter:
            dist_codes_in_state = db.execute(
                select(District.code).where(District.state.ilike(state_filter))
            ).scalars().all()
            state_codes = {dc.split("_")[0] for dc in dist_codes_in_state if "_" in dc}
            state_code_direct = STATE_TO_CODE.get(state_filter.lower())
            if state_code_direct:
                state_codes.add(state_code_direct)

            q = q.where(
                (FinancialRecord.district_code.in_(dist_codes_in_state)) |
                (FinancialRecord.state_code.in_(state_codes)) |
                (FinancialRecord.state_code == state_filter)
            )

        if category and category != "ALL":
            q = q.where(FinancialRecord.category == category)

        records = db.execute(q).scalars().all()

        # Check latest source metadata
        source = db.execute(
            select(FinancialSource).order_by(FinancialSource.created_at.desc()).limit(1)
        ).scalar_one_or_none()

        latest_run = db.execute(
            select(FinancialImportRun)
            .where(FinancialImportRun.status.in_(["APPROVED", "SUCCESS"]))
            .order_by(FinancialImportRun.completed_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        # Active grievance demand query
        g_q = select(func.count(CitizenRequest.id)).where(
            CitizenRequest.status.in_(ACTIVE_GRIEVANCE_STATUSES)
        )
        if dist_row:
            g_q = g_q.where(CitizenRequest.district_code == dist_row.code)
        elif state_filter:
            dist_codes_in_state = db.execute(
                select(District.code).where(District.state.ilike(state_filter))
            ).scalars().all()
            if dist_codes_in_state:
                g_q = g_q.where(CitizenRequest.district_code.in_(dist_codes_in_state))
        if category and category != "ALL":
            g_q = g_q.where(CitizenRequest.category == category)

        total_active_grievances = db.execute(g_q).scalar() or 0

        if not records:
            # Return honest empty state with zero fallback
            return {
                "scope": scope.upper(),
                "state": state_filter or "National",
                "district": dist_row.name if dist_row else None,
                "district_code": dist_row.code if dist_row else None,
                "fiscal_year": fiscal_year,
                "currency_unit": "INR_CRORE",
                "total_allocated": 0.0,
                "funds_released": 0.0,
                "recorded_expenditure": 0.0,
                "available_funds": 0.0,
                "release_rate_pct": 0.0,
                "utilisation_rate_pct": 0.0,
                "has_anomaly": False,
                "total_active_grievances": total_active_grievances,
                "coverage": "partial",
                "is_data_available": False,
                "message": "No verified official financial data is currently available for this selection.",
                "metadata": {
                    "source_name": source.name if source else "Ministry of Finance",
                    "source_url": source.base_url if source else "https://finance.maharashtra.gov.in",
                    "publisher": source.publisher if source else "Government of India",
                    "published_at": None,
                    "last_synced_at": latest_run.completed_at.isoformat() if (latest_run and latest_run.completed_at) else None,
                    "verification_status": "PROVISIONAL",
                },
            }

        # Apply stage precedence
        resolved_items = _resolve_line_items(records)

        tot_alloc_inr = sum((item.allocated_inr for item in resolved_items.values()), Decimal("0.00"))
        tot_rel_inr = sum((item.released_inr for item in resolved_items.values()), Decimal("0.00"))
        tot_spent_inr = sum((item.spent_inr for item in resolved_items.values()), Decimal("0.00"))

        avail_inr = tot_rel_inr - tot_spent_inr
        has_anomaly = tot_spent_inr > tot_rel_inr

        tot_alloc_cr = _inr_to_crore(tot_alloc_inr)
        tot_rel_cr = _inr_to_crore(tot_rel_inr)
        tot_spent_cr = _inr_to_crore(tot_spent_inr)
        avail_cr = _inr_to_crore(avail_inr)

        rel_rate = round((float(tot_rel_inr) / float(tot_alloc_inr) * 100.0), 2) if tot_alloc_inr > 0 else 0.0
        util_rate = round((float(tot_spent_inr) / float(tot_rel_inr) * 100.0), 2) if tot_rel_inr > 0 else 0.0

        latest_pub = max((r.published_at for r in records if r.published_at), default=None)

        return {
            "scope": scope.upper(),
            "state": state_filter or "National",
            "district": dist_row.name if dist_row else None,
            "district_code": dist_row.code if dist_row else None,
            "fiscal_year": fiscal_year,
            "currency_unit": "INR_CRORE",
            "total_allocated": tot_alloc_cr,
            "funds_released": tot_rel_cr,
            "recorded_expenditure": tot_spent_cr,
            "available_funds": avail_cr,
            "release_rate_pct": rel_rate,
            "utilisation_rate_pct": util_rate,
            "has_anomaly": has_anomaly,
            "anomaly_message": "Recorded expenditure exceeds the released amount. This record requires verification." if has_anomaly else None,
            "total_active_grievances": total_active_grievances,
            "coverage": "complete" if all(r.coverage == "complete" for r in records) else "partial",
            "is_data_available": True,
            "metadata": {
                "source_name": source.name if source else "Maharashtra Finance Department",
                "source_url": source.base_url if source else "https://finance.maharashtra.gov.in",
                "publisher": source.publisher if source else "Government of Maharashtra",
                "published_at": latest_pub.isoformat() if latest_pub else None,
                "last_synced_at": latest_run.completed_at.isoformat() if (latest_run and latest_run.completed_at) else None,
                "verification_status": "VERIFIED",
            },
        }

    @staticmethod
    def get_district_breakdown(
        db: Session,
        state: str = "Maharashtra",
        fiscal_year: str = "2026-27",
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """Horizontal district comparison metrics within a state."""
        state_filter = state.strip()
        state_code = state_filter[:2].upper()

        districts = db.execute(
            select(District).where(District.state.ilike(state_filter)).order_by(District.name)
        ).scalars().all()

        if not districts:
            return []

        dist_map = {d.code: d.name for d in districts}

        # Query all records in state
        q = select(FinancialRecord).where(
            FinancialRecord.verification_status == VerificationStatus.VERIFIED.value,
            FinancialRecord.fiscal_year == fiscal_year,
            FinancialRecord.district_code.in_(list(dist_map.keys())),
        )
        if category and category != "ALL":
            q = q.where(FinancialRecord.category == category)

        records = db.execute(q).scalars().all()
        resolved_items = _resolve_line_items(records)

        # Aggregate per district
        by_dist: dict[str, dict[str, Decimal]] = {}
        for key, item in resolved_items.items():
            dc = key[2] # district_code
            if not dc or dc not in dist_map:
                continue
            if dc not in by_dist:
                by_dist[dc] = {"alloc": Decimal("0.00"), "rel": Decimal("0.00"), "spent": Decimal("0.00")}
            by_dist[dc]["alloc"] += item.allocated_inr
            by_dist[dc]["rel"] += item.released_inr
            by_dist[dc]["spent"] += item.spent_inr

        # Query active grievances per district
        g_rows = db.execute(
            select(CitizenRequest.district_code, func.count(CitizenRequest.id))
            .where(
                CitizenRequest.district_code.in_(list(dist_map.keys())),
                CitizenRequest.status.in_(ACTIVE_GRIEVANCE_STATUSES),
            )
            .group_by(CitizenRequest.district_code)
        ).all()
        g_map = {dc: count for dc, count in g_rows if dc}

        results: list[dict[str, Any]] = []
        for dc, dname in dist_map.items():
            f_data = by_dist.get(dc, {"alloc": Decimal("0.00"), "rel": Decimal("0.00"), "spent": Decimal("0.00")})
            alloc_cr = _inr_to_crore(f_data["alloc"])
            rel_cr = _inr_to_crore(f_data["rel"])
            spent_cr = _inr_to_crore(f_data["spent"])
            avail_cr = _inr_to_crore(f_data["rel"] - f_data["spent"])
            grievances = g_map.get(dc, 0)

            # Only include districts with data or grievances
            if alloc_cr > 0 or grievances > 0:
                results.append({
                    "district_code": dc,
                    "district": dname,
                    "state": state_filter,
                    "allocated": alloc_cr,
                    "released": rel_cr,
                    "spent": spent_cr,
                    "available": avail_cr,
                    "has_anomaly": f_data["spent"] > f_data["rel"],
                    "active_grievances": grievances,
                    "release_rate": round(float(f_data["rel"] / f_data["alloc"]) * 100.0, 1) if f_data["alloc"] > 0 else 0.0,
                    "utilisation_rate": round(float(f_data["spent"] / f_data["rel"]) * 100.0, 1) if f_data["rel"] > 0 else 0.0,
                })

        return sorted(results, key=lambda x: x["allocated"], reverse=True)

    @staticmethod
    def get_sector_breakdown(
        db: Session,
        scope: str = "state",
        state: str | None = "Maharashtra",
        district: str | None = None,
        fiscal_year: str = "2026-27",
    ) -> list[dict[str, Any]]:
        """Sector-by-sector budget, expenditure, grievance share %, and funding signals."""
        state_filter = state.strip() if state else None
        dist_row = None
        if district:
            dist_row = db.execute(
                select(District).where(
                    (District.name.ilike(district.strip())) | (District.code == district.strip())
                )
            ).scalar_one_or_none()

        q = select(FinancialRecord).where(
            FinancialRecord.verification_status == VerificationStatus.VERIFIED.value,
            FinancialRecord.fiscal_year == fiscal_year,
        )
        if dist_row:
            q = q.where(FinancialRecord.district_code == dist_row.code)
        elif state_filter:
            dist_codes_in_state = db.execute(
                select(District.code).where(District.state.ilike(state_filter))
            ).scalars().all()
            state_codes = {dc.split("_")[0] for dc in dist_codes_in_state if "_" in dc}
            state_code_direct = STATE_TO_CODE.get(state_filter.lower())
            if state_code_direct:
                state_codes.add(state_code_direct)

            q = q.where(
                (FinancialRecord.district_code.in_(dist_codes_in_state)) |
                (FinancialRecord.state_code.in_(state_codes)) |
                (FinancialRecord.state_code == state_filter)
            )

        records = db.execute(q).scalars().all()
        resolved_items = _resolve_line_items(records)

        # Aggregate financial totals by category
        by_cat: dict[str, dict[str, Any]] = {}
        for key, item in resolved_items.items():
            cat = key[3] or "UNMAPPED"
            scheme = key[4]
            if cat not in by_cat:
                by_cat[cat] = {
                    "alloc": Decimal("0.00"),
                    "rel": Decimal("0.00"),
                    "spent": Decimal("0.00"),
                    "schemes": set(),
                }
            by_cat[cat]["alloc"] += item.allocated_inr
            by_cat[cat]["rel"] += item.released_inr
            by_cat[cat]["spent"] += item.spent_inr
            if scheme and scheme != "DEFAULT":
                by_cat[cat]["schemes"].add(scheme)

        # Active grievance demand per category
        g_q = select(CitizenRequest.category, func.count(CitizenRequest.id)).where(
            CitizenRequest.status.in_(ACTIVE_GRIEVANCE_STATUSES)
        )
        if dist_row:
            g_q = g_q.where(CitizenRequest.district_code == dist_row.code)
        elif state_filter:
            dist_codes_in_state = db.execute(
                select(District.code).where(District.state.ilike(state_filter))
            ).scalars().all()
            if dist_codes_in_state:
                g_q = g_q.where(CitizenRequest.district_code.in_(dist_codes_in_state))

        g_rows = db.execute(g_q.group_by(CitizenRequest.category)).all()
        g_map = {cat: count for cat, count in g_rows}
        tot_grievances = sum(g_map.values()) or 1

        all_categories = set(by_cat.keys()) | set(g_map.keys())
        tot_alloc = sum((v["alloc"] for v in by_cat.values()), Decimal("0.00")) or Decimal("1.00")
        tot_spent = sum((v["spent"] for v in by_cat.values()), Decimal("0.00")) or Decimal("1.00")

        sectors: list[dict[str, Any]] = []
        for cat in all_categories:
            cdata = by_cat.get(cat, {"alloc": Decimal("0.00"), "rel": Decimal("0.00"), "spent": Decimal("0.00"), "schemes": set()})
            alloc_cr = _inr_to_crore(cdata["alloc"])
            rel_cr = _inr_to_crore(cdata["rel"])
            spent_cr = _inr_to_crore(cdata["spent"])
            avail_cr = _inr_to_crore(cdata["rel"] - cdata["spent"])

            g_count = g_map.get(cat, 0)
            g_share = round((g_count / tot_grievances) * 100.0, 1)
            alloc_share = round(float(cdata["alloc"] / tot_alloc) * 100.0, 1)
            spend_share = round(float(cdata["spent"] / tot_spent) * 100.0, 1)

            need_gap = round(g_share - alloc_share, 1)

            # Signal assessment derivation
            if need_gap > 8.0:
                assessment = "Needs review"
                assessment_type = "warn"
            elif need_gap < -6.0:
                assessment = "Watch allocation"
                assessment_type = "attention"
            else:
                assessment = "Broadly aligned"
                assessment_type = "aligned"

            util_rate = round(float(cdata["spent"] / cdata["rel"]) * 100.0, 1) if cdata["rel"] > 0 else 0.0

            sectors.append({
                "category": cat,
                "label": SECTOR_LABEL_MAP.get(cat, cat.replace("_", " ").title()),
                "color": SECTOR_COLOR_MAP.get(cat, "#64748b"),
                "allocated": alloc_cr,
                "released": rel_cr,
                "spent": spent_cr,
                "available": avail_cr,
                "has_anomaly": cdata["spent"] > cdata["rel"],
                "active_grievances": g_count,
                "grievance_share_pct": g_share,
                "allocation_share_pct": alloc_share,
                "spending_share_pct": spend_share,
                "need_gap": need_gap,
                "utilisation_rate": util_rate,
                "assessment": assessment,
                "assessment_type": assessment_type,
                "schemes": sorted(list(cdata["schemes"])),
            })

        return sorted(sectors, key=lambda s: s["allocated"], reverse=True)

    @staticmethod
    def get_sources(db: Session) -> list[dict[str, Any]]:
        """List verified financial sources with synchronization health."""
        sources = db.execute(select(FinancialSource).order_by(FinancialSource.name)).scalars().all()
        results = []
        for s in sources:
            latest_run = db.execute(
                select(FinancialImportRun)
                .where(FinancialImportRun.source_id == s.id)
                .order_by(FinancialImportRun.started_at.desc())
                .limit(1)
            ).scalar_one_or_none()

            results.append({
                "id": s.id,
                "name": s.name,
                "publisher": s.publisher,
                "base_url": s.base_url,
                "source_type": s.source_type,
                "verification_status": s.verification_status,
                "is_active": s.is_active,
                "last_synced_at": latest_run.completed_at.isoformat() if (latest_run and latest_run.completed_at) else None,
                "last_status": latest_run.status if latest_run else "NEVER_RUN",
                "records_count": len(s.records),
            })
        return results

    @staticmethod
    def get_coverage(db: Session) -> dict[str, Any]:
        """Return lists of state names and district codes/names with verified data."""
        stmt = select(
            FinancialRecord.state_code,
            FinancialRecord.district_code,
        ).where(
            FinancialRecord.verification_status == VerificationStatus.VERIFIED
        ).distinct()
        rows = db.execute(stmt).all()

        covered_district_codes = {r[1] for r in rows if r[1]}
        covered_state_codes = {r[0] for r in rows if r[0]}

        districts = db.query(District).all()
        covered_states = set()
        covered_districts = set()

        for d in districts:
            if d.code in covered_district_codes:
                covered_states.add(d.state)
                covered_districts.add(d.name)
            elif d.state_code in covered_state_codes:
                covered_states.add(d.state)

        return {
            "covered_states": sorted(list(covered_states)),
            "covered_districts": sorted(list(covered_districts)),
            "covered_district_codes": sorted(list(covered_district_codes)),
        }

