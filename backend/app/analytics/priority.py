"""The unmet-need index — the analytical core of the platform.

The naive version of this project ranks districts by complaint volume. That
fails for two reasons a planning official would spot in seconds:

1. Volume measures *who is loud*, not *who is underserved*. A well-connected
   district with high smartphone penetration will out-complain a poorer one
   every time. We correct for this explicitly (see participation_adjustment).

2. Volume ignores whether the need is already being met or already funded.
   Recommending a project that is mid-construction destroys trust instantly.

So the score is a weighted blend of four independent signals, three of which
come from official data and cannot be gamed by campaign-style complaint drives:

  demand        - what citizens actually reported, per capita, urgency-weighted
  coverage_gap  - what the infrastructure index says is still missing
  deprivation   - how badly off the district is overall (SDG-style index)
  underfunding  - how little is currently allocated here per person

Because demand carries only ~a third of the weight, a brigading attempt on one
district cannot by itself produce a top recommendation. That property is worth
stating out loud in the pitch.

All weights are configurable and returned with every result, so a state that
wants to prioritise differently can retune without a code change.
"""
from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_WEIGHTS: dict[str, float] = {
    "demand": 0.35,
    "coverage_gap": 0.30,
    "deprivation": 0.20,
    "underfunding": 0.15,
}

# A district reporting far less than average may be under-served by the channel
# rather than satisfied. We scale its demand up — but cap the correction so it
# can never invent a hotspot out of near-zero signal.
PARTICIPATION_FLOOR = 0.15
PARTICIPATION_CAP = 2.5

URGENCY_WEIGHTS = {1: 0.5, 2: 0.75, 3: 1.0, 4: 1.5, 5: 2.5}


@dataclass
class DistrictCategoryInput:
    """One (district, category) cell, assembled by analytics/aggregate.py."""
    district_code: str
    district: str
    state: str
    category: str
    population: int
    request_count: int
    weighted_demand: float                     # sum of urgency weights
    coverage_pct: float | None = None
    allocation_inr_lakh: float = 0.0
    deprivation_index: float | None = None     # 0 (best) .. 1 (worst)
    literacy_pct: float | None = None
    internet_pct: float | None = None
    latitude: float | None = None
    longitude: float | None = None


@dataclass
class ScoredDistrictCategory:
    inp: DistrictCategoryInput
    unmet_need_score: float
    components: dict[str, float] = field(default_factory=dict)
    participation_adjustment: float = 1.0
    rank: int = 0

    @property
    def allocation_per_capita(self) -> float | None:
        if not self.inp.population:
            return None
        # 1 lakh = 100,000 rupees
        return round(self.inp.allocation_inr_lakh * 100_000 / self.inp.population, 2)

    @property
    def coverage_gap_pct(self) -> float | None:
        if self.inp.coverage_pct is None:
            return None
        return round(max(0.0, 100.0 - self.inp.coverage_pct), 2)


def urgency_weight(urgency: int) -> float:
    return URGENCY_WEIGHTS.get(int(urgency), 1.0)


def _minmax(values: list[float]) -> tuple[float, float]:
    lo, hi = (min(values), max(values)) if values else (0.0, 0.0)
    return lo, (hi if hi > lo else lo + 1e-9)


def _norm(value: float, lo: float, hi: float) -> float:
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def participation_adjustment(
    literacy_pct: float | None,
    internet_pct: float | None,
    mean_proxy: float,
) -> float:
    """Scale up demand from districts that are structurally less able to report.

    Rationale: this platform's own reach is uneven, and pretending otherwise
    would bake the digital divide into national spending priorities — the exact
    failure the track is asking us to fix.
    """
    if literacy_pct is None and internet_pct is None:
        return 1.0
    lit = (literacy_pct or 0.0) / 100.0
    net = (internet_pct or 0.0) / 100.0
    proxy = max(0.5 * lit + 0.5 * net, PARTICIPATION_FLOOR)
    if proxy <= 0 or mean_proxy <= 0:
        return 1.0
    return round(min(PARTICIPATION_CAP, max(1.0, mean_proxy / proxy)), 3)


def score(
    rows: list[DistrictCategoryInput],
    weights: dict[str, float] | None = None,
) -> list[ScoredDistrictCategory]:
    """Score and rank every (district, category) cell.

    Normalisation is done across the supplied set, so filtering to one state
    ranks districts against their own peers — which is how state planning
    departments actually think — while an unfiltered call ranks nationally.
    """
    if not rows:
        return []
    w = {**DEFAULT_WEIGHTS, **(weights or {})}

    proxies = []
    for r in rows:
        if r.literacy_pct is not None or r.internet_pct is not None:
            proxies.append(0.5 * (r.literacy_pct or 0) / 100 + 0.5 * (r.internet_pct or 0) / 100)
    mean_proxy = sum(proxies) / len(proxies) if proxies else 0.0

    # Per-capita demand, participation-adjusted, before normalisation.
    adjusted: list[float] = []
    adjustments: list[float] = []
    for r in rows:
        adj = participation_adjustment(r.literacy_pct, r.internet_pct, mean_proxy)
        per_capita = (r.weighted_demand / r.population * 100_000) if r.population else 0.0
        adjustments.append(adj)
        adjusted.append(per_capita * adj)

    d_lo, d_hi = _minmax(adjusted)
    alloc_pc = [
        (r.allocation_inr_lakh * 100_000 / r.population) if r.population else 0.0 for r in rows
    ]
    a_lo, a_hi = _minmax(alloc_pc)
    deps = [r.deprivation_index for r in rows if r.deprivation_index is not None]
    dep_lo, dep_hi = _minmax(deps) if deps else (0.0, 1.0)

    scored: list[ScoredDistrictCategory] = []
    for i, r in enumerate(rows):
        demand_c = _norm(adjusted[i], d_lo, d_hi)
        gap_c = (max(0.0, 100.0 - r.coverage_pct) / 100.0) if r.coverage_pct is not None else 0.5
        dep_c = _norm(r.deprivation_index, dep_lo, dep_hi) if r.deprivation_index is not None else 0.5
        under_c = 1.0 - _norm(alloc_pc[i], a_lo, a_hi)

        components = {
            "demand": round(demand_c, 4),
            "coverage_gap": round(gap_c, 4),
            "deprivation": round(dep_c, 4),
            "underfunding": round(under_c, 4),
        }
        total = 100.0 * sum(w[k] * components[k] for k in components)
        scored.append(
            ScoredDistrictCategory(
                inp=r,
                unmet_need_score=round(total, 2),
                components=components,
                participation_adjustment=adjustments[i],
            )
        )

    scored.sort(key=lambda s: s.unmet_need_score, reverse=True)
    for idx, s in enumerate(scored, start=1):
        s.rank = idx
    return scored


def weights_in_use(weights: dict[str, float] | None = None) -> dict[str, float]:
    return {**DEFAULT_WEIGHTS, **(weights or {})}
