"""The reference endpoint the API was missing.

Every other endpoint here takes a `state` or `district_code` and none of them
would tell you what values are legal. A client had to derive the list by calling
`/hotspots` and collecting distinct states out of the analytics output, which
works only for districts that already have demand data — so a district with no
citizen reports yet was unaddressable through the API that is meant to cover it.

For a project whose fourth constraint is "extending coverage means adding rows to
districts.csv, never editing logic", the list of covered districts is arguably the
most important thing the API publishes.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import District
from app.models.schemas import DistrictOut

router = APIRouter(tags=["reference"])


@router.get("/districts", response_model=list[DistrictOut])
def list_districts(
    state: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[DistrictOut]:
    q = db.query(District)
    if state:
        q = q.filter(District.state == state)
    rows = q.order_by(District.state, District.name).all()
    return [DistrictOut.model_validate(r) for r in rows]


@router.get("/states", response_model=list[str])
def list_states(db: Session = Depends(get_db)) -> list[str]:
    """Distinct states, alphabetical. Cheap enough to be its own call, and it
    saves every client from downloading the district table to populate one
    dropdown."""
    return [s for (s,) in db.query(District.state).distinct().order_by(func.lower(District.state)).all()]
