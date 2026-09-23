"""Demand hotspots — the map layer of the dashboard."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.analytics.aggregate import build_cells
from app.analytics.priority import score
from app.models.schemas import HotspotOut


def find_hotspots(
    db: Session,
    state: str | None = None,
    category: str | None = None,
    limit: int = 50,
) -> list[HotspotOut]:
    scored = score(build_cells(db, state=state, category=category))
    out: list[HotspotOut] = []
    for s in scored[:limit]:
        out.append(
            HotspotOut(
                district_code=s.inp.district_code,
                district=s.inp.district,
                state=s.inp.state,
                category=s.inp.category,
                request_count=s.inp.request_count,
                weighted_demand=s.inp.weighted_demand,
                population=s.inp.population,
                coverage_pct=s.inp.coverage_pct,
                allocation_per_capita=s.allocation_per_capita,
                unmet_need_score=s.unmet_need_score,
                rank=s.rank,
                latitude=s.inp.latitude,
                longitude=s.inp.longitude,
            )
        )
    return out
