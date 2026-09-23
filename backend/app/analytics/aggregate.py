"""Assemble the (district, category) cells that feed scoring.

This is the join the track description asks for in so many words: citizen
feedback + demographic data + infrastructure indices + public investment plans,
in one table.
"""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.analytics.priority import DistrictCategoryInput, urgency_weight
from app.db.models import CitizenRequest, District, InfraIndex, InvestmentPlan
from app.models.schemas import RequestStatus
from app.models.taxonomy import CATEGORIES

#: Rows that must never count as demand.
#:
#: Triage flags messages that are not development requests — test messages,
#: adverts, wrong numbers. They are stored in full and remain rescuable from the
#: console, but until an officer says otherwise they are not evidence of need, and
#: counting them would let anyone raise a district's unmet-need score by typing
#: "test" into WhatsApp forty times.
#:
#: This is the only *kind* of casework status the scoring layer knows about, and it
#: is a deliberate exception rather than a precedent. RESOLVED and REJECTED are *not*
#: excluded: a repaired pipeline was still reported, and letting a closure lower
#: the score would make the ranking something a department could manage by closing
#: cases. INVALID excludes because the report was never a report.
#:
#: NEEDS_LOCATION excludes for a different reason and an arithmetically stricter one.
#: A request that names no place has no district to be counted in, so it cannot reach
#: any cell through the `district_code IS NOT NULL` filter anyway — but the exclusion
#: is stated explicitly because the interesting case is the one after a citizen
#: answers. Until they do, the report is not evidence about anywhere; the moment they
#: do, the status moves to NEW and it counts. Leaving it implicit would mean a future
#: change that fills in a district before the status moves would silently start
#: scoring incomplete reports.
_NOT_DEMAND = (RequestStatus.INVALID.value, RequestStatus.NEEDS_LOCATION.value)


def build_cells(
    db: Session,
    state: str | None = None,
    category: str | None = None,
    min_requests: int = 1,
) -> list[DistrictCategoryInput]:
    q = (
        db.query(
            CitizenRequest.district_code,
            CitizenRequest.category,
            func.count(CitizenRequest.id).label("request_count"),
            func.sum(CitizenRequest.urgency).label("urgency_sum"),
        )
        .filter(CitizenRequest.district_code.isnot(None))
        .filter(CitizenRequest.status.notin_(_NOT_DEMAND))
        .group_by(CitizenRequest.district_code, CitizenRequest.category)
    )
    if category:
        q = q.filter(CitizenRequest.category == category)

    grouped = q.all()
    if not grouped:
        return []

    districts = {d.code: d for d in db.query(District).all()}
    coverage = {
        (i.district_code, i.category): i.coverage_pct for i in db.query(InfraIndex).all()
    }
    allocation: dict[tuple[str, str], float] = {}
    for p in db.query(InvestmentPlan).all():
        allocation[(p.district_code, p.category)] = (
            allocation.get((p.district_code, p.category), 0.0) + (p.allocated_inr_lakh or 0.0)
        )

    # Urgency-weighted demand needs the individual urgencies, not just the sum,
    # because the weighting is non-linear (an emergency is worth more than five
    # routine reports).
    weighted: dict[tuple[str, str], float] = {}
    rows = (
        db.query(CitizenRequest.district_code, CitizenRequest.category, CitizenRequest.urgency)
        .filter(CitizenRequest.district_code.isnot(None))
        # The same exclusion as the count query above. If these two ever disagree,
        # a cell's weighted demand is computed over a different row set than its
        # request count, and the two numbers on the evidence panel stop adding up.
        .filter(CitizenRequest.status.notin_(_NOT_DEMAND))
        .all()
    )
    for dc, cat, urg in rows:
        weighted[(dc, cat)] = weighted.get((dc, cat), 0.0) + urgency_weight(urg)

    cells: list[DistrictCategoryInput] = []
    for dc, cat, count, _urgency_sum in grouped:
        if count < min_requests or cat not in CATEGORIES:
            continue
        d = districts.get(dc)
        if d is None or (state and d.state.lower() != state.lower()):
            continue
        cells.append(
            DistrictCategoryInput(
                district_code=dc,
                district=d.name,
                state=d.state,
                category=cat,
                population=d.population or 0,
                request_count=int(count),
                weighted_demand=round(weighted.get((dc, cat), 0.0), 3),
                coverage_pct=coverage.get((dc, cat)),
                allocation_inr_lakh=allocation.get((dc, cat), 0.0),
                deprivation_index=d.deprivation_index,
                literacy_pct=d.literacy_pct,
                internet_pct=d.internet_pct,
                latitude=d.latitude,
                longitude=d.longitude,
            )
        )
    return cells
