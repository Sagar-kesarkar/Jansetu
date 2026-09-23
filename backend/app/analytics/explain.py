"""Turn a scored cell into a recommendation a human can audit.

The rationale sentence is assembled from the numbers deterministically, so it
is always true even when Gemini is unavailable. The Gemini brief in
`services/gemini.py` is an addition on top, never a replacement.
"""
from __future__ import annotations

from app.analytics.priority import ScoredDistrictCategory, weights_in_use
from app.models.schemas import Evidence, RecommendationOut
from app.models.taxonomy import CATEGORIES


def _beneficiaries(s: ScoredDistrictCategory) -> int:
    """People plausibly served, from population and the coverage shortfall."""
    gap = (s.coverage_gap_pct or 0.0) / 100.0
    if gap <= 0:
        gap = 0.1  # some benefit even where coverage looks complete
    return int(s.inp.population * gap)


def build_rationale(s: ScoredDistrictCategory) -> str:
    cat = CATEGORIES.get(s.inp.category)
    label = cat.label_en.lower() if cat else s.inp.category.lower()
    bits = [
        f"{s.inp.request_count} citizen reports about {label} in {s.inp.district}, "
        f"{s.inp.state} (urgency-weighted demand {s.inp.weighted_demand})"
    ]
    if s.coverage_gap_pct is not None:
        bits.append(f"official coverage leaves a {s.coverage_gap_pct}% gap")
    apc = s.allocation_per_capita
    if apc is not None:
        bits.append(f"current allocation is ₹{apc} per person")
    if s.participation_adjustment > 1.05:
        bits.append(
            f"reported demand scaled by {s.participation_adjustment}x to offset "
            "low literacy and internet access, which suppress reporting here"
        )
    return "; ".join(bits) + "."


def to_recommendation(s: ScoredDistrictCategory, brief_md: str | None = None) -> RecommendationOut:
    cat = CATEGORIES.get(s.inp.category)
    title = (
        cat.project_template.format(district=s.inp.district)
        if cat else f"{s.inp.category} works - {s.inp.district}"
    )
    return RecommendationOut(
        rank=s.rank,
        district_code=s.inp.district_code,
        district=s.inp.district,
        state=s.inp.state,
        category=s.inp.category,
        project_title=title,
        linked_scheme=cat.linked_scheme if cat else "Unmapped",
        unmet_need_score=s.unmet_need_score,
        est_beneficiaries=_beneficiaries(s),
        rationale=build_rationale(s),
        evidence=Evidence(
            citizen_requests=s.inp.request_count,
            weighted_demand=s.inp.weighted_demand,
            coverage_pct=s.inp.coverage_pct,
            coverage_gap_pct=s.coverage_gap_pct,
            allocation_per_capita=s.allocation_per_capita,
            deprivation_index=s.inp.deprivation_index,
            participation_adjustment=s.participation_adjustment,
            literacy_pct=s.inp.literacy_pct,
            internet_pct=s.inp.internet_pct,
            population=s.inp.population,
            component_scores=s.components,
            weights=weights_in_use(),
        ),
        brief_md=brief_md,
    )
