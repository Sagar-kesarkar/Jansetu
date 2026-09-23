from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analytics.hotspots import find_hotspots
from app.db.database import get_db
from app.models.schemas import HotspotOut

router = APIRouter(prefix="/hotspots", tags=["analysis"])


@router.get("", response_model=list[HotspotOut])
def hotspots(
    state: str | None = Query(None, description="Rank within one state instead of nationally"),
    category: str | None = Query(None),
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
) -> list[HotspotOut]:
    return find_hotspots(db, state=state, category=category, limit=limit)
