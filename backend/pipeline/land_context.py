"""
Land context analysis for the AI Land Advisor (DECIDE).

Reuses the existing synthetic-Sentinel-2 fallback + spectral index pipeline
(the same data path used by Change Analysis / Monitoring) to characterise:
  - the user's selected AOI (their land)
  - a surrounding buffer ring (proxy for "nearby" context)

IMPORTANT — honesty about data limitations:
This demo pipeline has no live road network, population, or business-listing
data source available (no CDSE credentials configured, no OSM/Overpass access
in this environment). All "nearby" reasoning below is therefore derived ONLY
from land-cover composition (built-up / vegetation / water / bare-soil
fractions) computed from Sentinel-2-style spectral indices. We never invent
specific roads, businesses, population figures, or facilities — the advisor
explicitly says when a factor cannot be assessed.
"""
import logging
import numpy as np

from pipeline.data_access import generate_synthetic_sentinel2
from pipeline.preprocessing import preprocess_bands

logger = logging.getLogger(__name__)

DATA_LIMITATIONS = [
    "No live road-network data source is connected — accessibility is inferred only "
    "from surrounding built-up density, not actual roads.",
    "No population or business-listing data source is connected — nearby settlement "
    "and commercial activity are inferred only from land-cover composition, not "
    "verified counts.",
    "Land cover is derived from Sentinel-2-style spectral indices (NDVI/NDBI/NDWI/BSI); "
    "small or below-30m features may not be captured.",
]


def _expand_bbox(bbox: list, factor: float = 2.5) -> list:
    """Expand a bbox around its center by `factor` (area context ring)."""
    lon_min, lat_min, lon_max, lat_max = bbox
    cx, cy = (lon_min + lon_max) / 2, (lat_min + lat_max) / 2
    hw = (lon_max - lon_min) / 2 * factor
    hh = (lat_max - lat_min) / 2 * factor
    return [cx - hw, cy - hh, cx + hw, cy + hh]


def _composition(bbox: list) -> dict:
    """Land-cover composition percentages for a bbox using synthetic S2 fallback."""
    seed = int(abs(sum(bbox)) * 100) % 10000
    bands, shape, _ = generate_synthetic_sentinel2(bbox, seed=seed)
    _, indices = preprocess_bands(bands)

    ndvi, ndbi, ndwi = indices["NDVI"], indices["NDBI"], indices["NDWI"]
    total = ndvi.size

    water = ndwi > 0.15
    builtup = (~water) & (ndbi > 0.0)
    vegetation = (~water) & (~builtup) & (ndvi > 0.25)
    bare = ~(water | builtup | vegetation)

    return {
        "built_up_pct": round(float(builtup.sum()) / total * 100, 1),
        "vegetation_pct": round(float(vegetation.sum()) / total * 100, 1),
        "water_pct": round(float(water.sum()) / total * 100, 1),
        "bare_soil_pct": round(float(bare.sum()) / total * 100, 1),
    }


def analyze_context(bbox: list) -> dict:
    """
    Returns AOI composition + surrounding-ring composition + data limitations.
    """
    aoi_comp = _composition(bbox)
    buffer_bbox = _expand_bbox(bbox, factor=2.5)
    surrounding_comp = _composition(buffer_bbox)

    return {
        "aoi": aoi_comp,
        "surrounding": surrounding_comp,
        "buffer_bbox": buffer_bbox,
        "data_limitations": DATA_LIMITATIONS,
    }


# ── Purpose scoring ──────────────────────────────────────────────────────────

BUDGET_TIERS = {
    "low": (0, 1_000_000),          # up to 10 lakh
    "medium": (1_000_000, 10_000_000),   # 10L - 1Cr
    "high": (10_000_000, float("inf")),  # 1Cr+
}


def _budget_tier(budget: float) -> str:
    if budget < BUDGET_TIERS["low"][1]:
        return "low"
    if budget < BUDGET_TIERS["medium"][1]:
        return "medium"
    return "high"


PURPOSE_RULES = {
    "agriculture": {
        "min_budget_tier": "low",
        "score_fn": lambda aoi, sur, tier: (
            50
            + (sur["vegetation_pct"] - 30) * 0.8
            - sur["built_up_pct"] * 0.6
            - (20 if tier == "high" else 0)
        ),
        "why_fn": lambda aoi, sur, tier: [
            f"Surrounding vegetation cover is {sur['vegetation_pct']}%, "
            + ("suggesting an active agricultural/green context." if sur['vegetation_pct'] > 30
               else "which is relatively low for typical agricultural land."),
            f"Surrounding built-up density is {sur['built_up_pct']}%"
            + (" — low development pressure keeps land suitable for farming." if sur['built_up_pct'] < 20
               else " — nearby urbanisation may compete with agricultural use over time."),
            "Agriculture typically needs lower upfront capital than built infrastructure, "
            + ("which fits a lower budget tier well." if tier == "low" else "so a larger budget could achieve more than pure agriculture (e.g. agri-processing, warehousing)."),
        ],
    },
    "residential": {
        "min_budget_tier": "medium",
        "score_fn": lambda aoi, sur, tier: (
            50
            + (sur["built_up_pct"] - 20) * 0.6
            + (sur["vegetation_pct"] * 0.2)
            - (15 if tier == "low" else 0)
        ),
        "why_fn": lambda aoi, sur, tier: [
            f"Surrounding built-up density is {sur['built_up_pct']}%, "
            + ("indicating an already-developing residential context." if sur['built_up_pct'] > 20
               else "which is fairly undeveloped — expect limited nearby amenities."),
            f"Vegetation share of {sur['vegetation_pct']}% nearby suggests "
            + ("some green/open character alongside development." if sur['vegetation_pct'] > 15 else "a mostly built or bare surrounding."),
            "Residential development is capital-intensive; " + (
                "your budget tier supports this." if tier != "low" else "a low budget may only support small-scale or incremental construction."
            ),
        ],
    },
    "commercial": {
        "min_budget_tier": "medium",
        "score_fn": lambda aoi, sur, tier: (
            45
            + (sur["built_up_pct"] - 25) * 0.9
            - sur["vegetation_pct"] * 0.2
            + (10 if tier == "high" else 0)
        ),
        "why_fn": lambda aoi, sur, tier: [
            f"Surrounding built-up density is {sur['built_up_pct']}%"
            + (" — consistent with an accessible, developed area favourable for commercial activity." if sur['built_up_pct'] > 25
               else " — relatively low, which typically means less footfall/accessibility today."),
            "Nearby business density and footfall cannot be verified from this data source; "
            "the built-up percentage is used only as a rough accessibility proxy.",
            "Commercial construction/fit-out is capital-intensive; " + (
                "your budget tier is a reasonable fit." if tier != "low" else "a low budget is unlikely to be sufficient."
            ),
        ],
    },
    "showroom": {
        "min_budget_tier": "medium",
        "score_fn": lambda aoi, sur, tier: (
            45
            + (sur["built_up_pct"] - 25) * 0.9
            - sur["vegetation_pct"] * 0.2
            + (10 if tier == "high" else 0)
        ),
        "why_fn": lambda aoi, sur, tier: [
            f"Surrounding built-up density is {sur['built_up_pct']}%"
            + (", suggesting reasonable road/accessibility proxy and surrounding commercial activity." if sur['built_up_pct'] > 25
               else ", which is low — showrooms typically benefit from higher visibility/traffic areas."),
            "Actual road frontage, traffic counts, and nearby competing showrooms are not verifiable "
            "from this data source and are not assumed.",
            "Showroom fit-out and frontage typically need meaningful capital; " + (
                "your budget tier supports this." if tier != "low" else "a low budget may be a constraint."
            ),
        ],
    },
    "warehouse": {
        "min_budget_tier": "low",
        "score_fn": lambda aoi, sur, tier: (
            55
            + (sur["built_up_pct"] - 10) * 0.4
            - (sur["built_up_pct"] - 40) * 0.5
            - sur["water_pct"] * 0.5
        ),
        "why_fn": lambda aoi, sur, tier: [
            f"Surrounding built-up density is {sur['built_up_pct']}% — warehousing benefits from "
            + ("moderate development (road access proxy) without being in a dense core, which this roughly fits."
               if 10 <= sur['built_up_pct'] <= 40 else "a density outside the typical sweet-spot for logistics sites."),
            f"Water coverage nearby is {sur['water_pct']}%"
            + (" — negligible, so flood/waterlogging risk from this signal is low." if sur['water_pct'] < 5
               else " — worth checking flood risk before committing."),
            "Actual road/highway connectivity cannot be confirmed from this data source.",
        ],
    },
    "school": {
        "min_budget_tier": "medium",
        "score_fn": lambda aoi, sur, tier: (
            45
            + (sur["built_up_pct"] - 20) * 0.6
            + sur["vegetation_pct"] * 0.15
            - (10 if tier == "low" else 0)
        ),
        "why_fn": lambda aoi, sur, tier: [
            f"Surrounding built-up density ({sur['built_up_pct']}%) is used only as a weak population proxy — "
            "actual demand, catchment population, and existing schools nearby cannot be verified here.",
            f"Vegetation share of {sur['vegetation_pct']}% suggests some open space for a campus."
            if sur['vegetation_pct'] > 15 else "Limited nearby open space signal for a campus layout.",
            "Institutional projects (school/hospital) require significant sustained capital and regulatory "
            "approvals not modelled here; " + ("your budget tier is a reasonable starting point." if tier == "high" else "a larger budget or phased approach is typically needed."),
        ],
    },
    "hospital": {
        "min_budget_tier": "high",
        "score_fn": lambda aoi, sur, tier: (
            40
            + (sur["built_up_pct"] - 25) * 0.6
            - (25 if tier != "high" else 0)
        ),
        "why_fn": lambda aoi, sur, tier: [
            f"Surrounding built-up density ({sur['built_up_pct']}%) is used only as a weak population proxy — "
            "verified population, existing healthcare facilities, and demand cannot be assessed here.",
            "Hospitals require heavy capital investment, specialised infrastructure, and regulatory "
            "clearances that are entirely outside this tool's scope.",
            ("Your budget tier is consistent with a project of this scale." if tier == "high"
             else "This budget tier is typically insufficient for hospital-scale development."),
        ],
    },
}


def score_all_purposes(aoi: dict, surrounding: dict, budget: float) -> list:
    """Score every known purpose category. Returns sorted list (desc by score)."""
    tier = _budget_tier(budget)
    results = []
    for purpose, rule in PURPOSE_RULES.items():
        raw = rule["score_fn"](aoi, surrounding, tier)
        score = int(max(0, min(100, round(raw))))
        why = rule["why_fn"](aoi, surrounding, tier)
        results.append({"purpose": purpose, "score": score, "why": why})
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def score_custom_purpose(aoi: dict, surrounding: dict, budget: float, custom_label: str) -> dict:
    """
    Generic, conservative scoring for a user-typed custom purpose.
    No purpose-specific rule exists, so this stays deliberately general and
    says so explicitly rather than pretending to have domain-specific insight.
    """
    tier = _budget_tier(budget)
    balance_score = 50 + (surrounding["built_up_pct"] - surrounding["vegetation_pct"]) * 0.2
    score = int(max(0, min(100, round(balance_score))))
    why = [
        f"'{custom_label}' has no purpose-specific rule in this advisor, so this is a general "
        "development-suitability estimate only — treat it as a starting point, not a verdict.",
        f"Surrounding land cover: {surrounding['built_up_pct']}% built-up, "
        f"{surrounding['vegetation_pct']}% vegetation, {surrounding['water_pct']}% water, "
        f"{surrounding['bare_soil_pct']}% bare/other.",
        f"Budget tier detected: {tier} — sufficient capital access broadens feasible options "
        "regardless of land-cover context.",
    ]
    return {"purpose": custom_label, "score": score, "why": why}
