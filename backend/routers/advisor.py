"""
AI Land Advisor — FastAPI router.

feature/ai-land-advisor: enhanced to pass OSM proximity data through
scoring functions and return richer response payload (area_ha, proximity
facts, icon per purpose).

The /recommendations endpoint (used by the primary agent's change-detection
results panel) is left completely untouched.
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from typing import List, Dict, Any, Optional

from pipeline.land_context import (
    analyze_context,
    score_all_purposes,
    score_custom_purpose,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/advisor", tags=["advisor"])


# ── F4: AI Land Advisor ──────────────────────────────────────────────────────

KNOWN_PURPOSES = {
    "agriculture", "residential", "commercial", "showroom",
    "warehouse", "school", "hospital",
}


class LandAdvisorRequest(BaseModel):
    bbox: List[float]
    budget: float
    purpose: str
    custom_purpose: Optional[str] = None

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v):
        if len(v) != 4:
            raise ValueError("bbox must have 4 values")
        lon_min, lat_min, lon_max, lat_max = v
        if lon_max <= lon_min or lat_max <= lat_min:
            raise ValueError("Invalid bbox")
        return [float(x) for x in v]

    @field_validator("budget")
    @classmethod
    def validate_budget(cls, v):
        if v < 0:
            raise ValueError("budget must be >= 0")
        return v


@router.post("/analyze")
def analyze_land(request: LandAdvisorRequest):
    """
    Core DECIDE endpoint.

    Returns:
      - recommendation for the requested purpose with score + reasoning
      - all-purpose comparison scores (for radar / alternatives)
      - land-cover composition for AOI + surrounding buffer
      - OSM proximity context (or land-cover inference fallback)
      - area_ha estimate
      - data_limitations + disclaimer
    """
    context     = analyze_context(request.bbox)
    aoi         = context["aoi"]
    surrounding = context["surrounding"]
    proximity   = context["proximity"]

    # Score all purposes (pass proximity so scoring is OSM-aware)
    all_scores = score_all_purposes(aoi, surrounding, request.budget, proximity)

    if request.purpose == "custom":
        label     = (request.custom_purpose or "").strip() or "Custom purpose"
        requested = score_custom_purpose(aoi, surrounding, request.budget, label, proximity)
    elif request.purpose in KNOWN_PURPOSES:
        requested = next((r for r in all_scores if r["purpose"] == request.purpose), None)
        if requested is None:
            raise HTTPException(status_code=400, detail="Unknown purpose")
    else:
        raise HTTPException(status_code=400, detail=f"Unknown purpose '{request.purpose}'")

    score = requested["score"]
    fit_label = "Excellent fit" if score >= 75 else "Good fit" if score >= 60 else "Moderate fit" if score >= 40 else "Poor fit"
    fit_color = "green" if score >= 60 else "yellow" if score >= 40 else "red"

    return {
        "aoi_bbox": request.bbox,
        "area_ha":  context["area_ha"],
        "context": {
            "aoi":        aoi,
            "surrounding": surrounding,
        },
        "proximity":  proximity,
        "recommendation": {
            "purpose":   requested["purpose"],
            "icon":      requested.get("icon", "🏗️"),
            "score":     score,
            "label":     fit_label,
            "color":     fit_color,
            "why":       requested["why"],
        },
        # All scores for radar / comparison bar — exclude the requested one
        "all_scores": all_scores,
        "alternatives": [
            r for r in all_scores if r["purpose"] != requested.get("purpose")
        ][:6],
        "data_limitations": context["data_limitations"],
        "disclaimer": (
            "This is an advisory estimate based on land-cover spectral indices and "
            "publicly-available OpenStreetMap data. It is not a guaranteed business, "
            "financial, or legal recommendation. Always verify with local surveys, "
            "regulatory permits, and qualified domain experts before making any "
            "land-use decision."
        ),
    }


# ── /recommendations — DO NOT MODIFY — used by primary agent's ResultsPanel ──

class AdvisorRequest(BaseModel):
    changed_area_ha: float
    change_percent: float
    num_clusters: int
    mean_confidence: float
    land_type_guess: str = "mixed"


@router.post("/recommendations")
def get_recommendations(request: AdvisorRequest):
    """
    Returns heuristic-based recommendations based on change statistics.
    No fabrication, strictly rule-based.
    PRIMARY AGENT ENDPOINT — DO NOT MODIFY.
    """
    recs = []

    if request.change_percent > 50:
        recs.append("High change percentage detected. Immediate on-ground survey recommended to verify development scale.")
    elif request.change_percent > 10:
        recs.append("Moderate change observed. Consider cross-referencing with local permit records.")

    if request.changed_area_ha > 100:
        recs.append("Large scale land conversion (>100ha). Review environmental impact assessment compliance.")

    if request.num_clusters > 10:
        recs.append("Highly fragmented change detected. This may indicate uncoordinated urban sprawl or scattered illegal settlements.")
    elif request.num_clusters == 1 and request.changed_area_ha > 50:
        recs.append("Single large cluster detected. Likely a major organized infrastructure or industrial project.")

    if request.mean_confidence < 0.6:
        recs.append("Low model confidence. The detected changes could be seasonal agricultural variations or temporary earthworks. Ground truth required.")

    if not recs:
        recs.append("Minor or routine changes detected. Continue periodic monitoring.")

    return {
        "summary": f"Based on {request.changed_area_ha}ha of changed area across {request.num_clusters} clusters.",
        "recommendations": recs,
    }
