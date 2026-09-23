"""Request taxonomy.

Each citizen request category is deliberately mapped to (a) the national scheme
that funds that kind of work and (b) the column in the infrastructure index that
measures existing coverage. That mapping is what lets us do the thing the track
actually asks for: compare what citizens say they need against what the
infrastructure data says is missing, and against what is already funded.

Add a category by adding one row here — nothing else in the pipeline needs to
change, which is what keeps this deployable across states with different
priorities.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    code: str
    label_en: str
    linked_scheme: str          # national programme that funds this
    coverage_column: str        # column in data/reference/infra_indices.csv
    project_template: str       # used to name a recommended project
    #: The desk a case of this kind is routed to, as a citizen would be told it.
    #:
    #: Derived, not stored. A citizen tracking a token over SMS asks "who has it?",
    #: and the honest answer is a function of the sector — so it lives here beside
    #: the sector rather than as a column on `citizen_requests` that could drift out
    #: of step with the category on the same row. Generic ("Public Health
    #: Engineering") rather than named, because `RequestResponse.responder_desk`
    #: already carries the specific desk once a real officer has replied, and a
    #: named officer would be personal data on the government side of the wall.
    department: str = "District Administration"


DEFAULT_DEPARTMENT = "District Administration"


CATEGORIES: dict[str, Category] = {
    "WATER_SUPPLY": Category(
        "WATER_SUPPLY", "Drinking water supply", "Jal Jeevan Mission",
        "piped_water_coverage_pct", "Piped water extension - {district}",
        "Public Health Engineering Department"),
    "SANITATION": Category(
        "SANITATION", "Sanitation and drainage", "Swachh Bharat Mission (G)",
        "sanitation_coverage_pct", "Drainage and sanitation upgrade - {district}",
        "Municipal Sanitation Department"),
    "ROADS": Category(
        "ROADS", "Roads and connectivity", "PMGSY",
        "all_weather_road_pct", "All-weather road connectivity - {district}",
        "Public Works Department"),
    "ELECTRICITY": Category(
        "ELECTRICITY", "Electricity supply", "RDSS / Saubhagya",
        "household_electrification_pct", "Distribution network strengthening - {district}",
        "State Electricity Distribution Company"),
    "HEALTH": Category(
        "HEALTH", "Health facilities", "Ayushman Bharat HWC",
        "health_centre_per_lakh", "Health and wellness centre expansion - {district}",
        "District Health Department"),
    "EDUCATION": Category(
        "EDUCATION", "Schools and education", "Samagra Shiksha",
        "school_infra_index", "School infrastructure upgrade - {district}",
        "District Education Department"),
    "DIGITAL": Category(
        "DIGITAL", "Internet and digital access", "BharatNet",
        "broadband_coverage_pct", "Broadband last-mile rollout - {district}",
        "Department of Telecommunications (BharatNet)"),
    "HOUSING": Category(
        "HOUSING", "Housing", "PMAY-G",
        "pucca_housing_pct", "Housing completion drive - {district}",
        "Rural Development Department"),
    "IRRIGATION": Category(
        "IRRIGATION", "Irrigation and water management", "PMKSY",
        "irrigated_area_pct", "Micro-irrigation expansion - {district}",
        "Water Resources Department"),
    "TRANSPORT": Category(
        "TRANSPORT", "Public transport", "State transport / PM-eBus",
        "transport_access_index", "Bus route and depot expansion - {district}",
        "State Transport Corporation"),
}

CATEGORY_CODES = list(CATEGORIES.keys())


def category_or_other(code: str | None) -> str:
    """Gemini occasionally invents a category. Fold anything unknown into
    OTHER rather than dropping the request — a citizen report is never noise."""
    if code and code.upper() in CATEGORIES:
        return code.upper()
    return "OTHER"


def department_for(code: str | None) -> str:
    """Which desk holds a case of this kind.

    Deterministic and total: OTHER and anything unrecognised land on the district
    collectorate, which is where an unclassifiable grievance genuinely goes. Used by
    the SMS and WhatsApp status replies, so it must never raise — a citizen asking
    where their complaint is cannot be answered with a KeyError.
    """
    cat = CATEGORIES.get((code or "").upper())
    return cat.department if cat else DEFAULT_DEPARTMENT
