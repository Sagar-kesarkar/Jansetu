from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.analytics.aggregate import build_cells
from app.analytics.explain import to_recommendation
from app.analytics.priority import score
from app.db.database import get_db
from app.models.schemas import RecommendationOut
from app.services.gemini import write_policy_brief

router = APIRouter(prefix="/recommendations", tags=["analysis"])


def _narrate(rec: RecommendationOut) -> str | None:
    """Hand the computed evidence to Gemini to write up.

    Note what is passed: only `rec.evidence` plus identifying labels. The model
    receives no raw citizen text and no database access, so there is nothing for
    it to draw a new number from — it can only narrate figures the pure analytics
    layer already produced.
    """
    return write_policy_brief(rec.evidence.model_dump() | {
        "district": rec.district,
        "state": rec.state,
        "category": rec.category,
        "linked_scheme": rec.linked_scheme,
        "est_beneficiaries": rec.est_beneficiaries,
        "unmet_need_score": rec.unmet_need_score,
    })


@router.get("", response_model=list[RecommendationOut])
def recommendations(
    state: str | None = Query(None),
    category: str | None = Query(None),
    limit: int = Query(10, le=100),
    with_brief: bool = Query(False, description="Generate a Gemini policy brief per item (slower)"),
    db: Session = Depends(get_db),
) -> list[RecommendationOut]:
    """High-priority development projects, ranked.

    `with_brief` is off by default because it costs one Gemini call per row, and
    ten of those will both stall the page and eat a free-tier quota. The
    dashboard leaves this false and uses `/recommendations/brief` for the one
    card the user actually asked about.
    """
    scored = score(build_cells(db, state=state, category=category))[:limit]
    out: list[RecommendationOut] = []
    for s in scored:
        rec = to_recommendation(s)
        if with_brief:
            rec.brief_md = _narrate(rec)
        out.append(rec)
    return out


@router.get("/brief", response_model=RecommendationOut)
def recommendation_brief(
    district_code: str = Query(..., description="District to brief, LGD-keyed code"),
    sector: str = Query(..., description="Category code of the row to brief"),
    state: str | None = Query(None, description="The caller's state filter, if any"),
    category: str | None = Query(None, description="The caller's sector filter, if any"),
    db: Session = Depends(get_db),
) -> RecommendationOut:
    """One brief for one row — what the dashboard's per-card button calls.

    `state` and `category` mirror the list query on purpose. Normalisation runs
    across the queried set, so a brief fetched without the caller's filters would
    come back carrying a different score than the card it was requested from, and
    a number that changes when you click "explain" destroys the audit trail this
    whole screen exists to provide.
    """
    for s in score(build_cells(db, state=state, category=category)):
        if s.inp.district_code == district_code and s.inp.category == sector:
            rec = to_recommendation(s)
            rec.brief_md = _narrate(rec)
            return rec

    raise HTTPException(
        status_code=404,
        detail=f"No scored cell for district {district_code!r} in sector {sector!r}",
    )
