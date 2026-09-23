"""Tests for the unmet-need index.

These encode the two properties the scoring must have to be credible to a
planning official: need beats volume, and a complaint drive cannot buy a
district the top slot.
"""
from app.analytics.priority import (
    DEFAULT_WEIGHTS,
    PARTICIPATION_CAP,
    DistrictCategoryInput,
    participation_adjustment,
    score,
)


def cell(code, *, pop=1_000_000, demand=100.0, coverage=60.0, alloc=300.0,
         dep=0.5, lit=70.0, net=30.0):
    return DistrictCategoryInput(
        district_code=code, district=code, state="Test", category="WATER_SUPPLY",
        population=pop, request_count=int(demand), weighted_demand=demand,
        coverage_pct=coverage, allocation_inr_lakh=alloc,
        deprivation_index=dep, literacy_pct=lit, internet_pct=net,
    )


def test_weights_sum_to_one():
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9


def test_underserved_district_outranks_loud_well_served_one():
    rows = [
        cell("LOUD_RICH", demand=400.0, coverage=92.0, alloc=900.0, dep=0.20, lit=85.0, net=60.0),
        cell("QUIET_POOR", demand=40.0, coverage=28.0, alloc=120.0, dep=0.88, lit=48.0, net=12.0),
    ]
    assert score(rows)[0].inp.district_code == "QUIET_POOR"


def test_demand_inflation_cannot_win_alone():
    """A 20x brigading attempt must not flip the ranking."""
    rows = [
        cell("LOUD_RICH", demand=8000.0, coverage=92.0, alloc=900.0, dep=0.20, lit=85.0, net=60.0),
        cell("QUIET_POOR", demand=40.0, coverage=28.0, alloc=120.0, dep=0.88, lit=48.0, net=12.0),
    ]
    result = score(rows)
    assert result[0].inp.district_code == "QUIET_POOR"
    assert result[0].unmet_need_score <= 100.0


def test_participation_adjustment_favours_low_access():
    low = participation_adjustment(45.0, 10.0, mean_proxy=0.45)
    high = participation_adjustment(88.0, 65.0, mean_proxy=0.45)
    assert low > high >= 1.0
    assert low <= PARTICIPATION_CAP


def test_scores_bounded_and_ranks_dense():
    rows = [cell(f"D{i}", demand=float(i * 7), coverage=30.0 + i * 2,
                 alloc=100.0 + i * 20, dep=0.9 - i * 0.03) for i in range(10)]
    result = score(rows)
    assert [s.rank for s in result] == list(range(1, 11))
    assert all(0.0 <= s.unmet_need_score <= 100.0 for s in result)


def test_empty_input():
    assert score([]) == []
