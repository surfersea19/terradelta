import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from typing import List, Dict, Any, Optional

from pipeline.land_context import analyze_context, score_all_purposes, score_custom_purpose

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/advisor", tags=["advisor"])


# ── F4: AI Land Advisor (map-based, budget + purpose) ───────────────────────

KNOWN_PURPOSES = {
    "agriculture", "residential", "commercial", "showroom",
    "warehouse", "school", "hospital",
}


class LandAdvisorRequest(BaseModel):
    bbox: List[float]           # [lon_min, lat_min, lon_max, lat_max] — the user's land
    budget: float                # in local currency units (e.g. INR)
    purpose: str                 # one of KNOWN_PURPOSES, or "custom"
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
    Core DECIDE endpoint. Given an AOI (the user's land), a budget, and an
    intended purpose, returns a recommendation + explicit reasoning based on
    land-cover context — never fabricating roads, businesses, or population
    figures. If a purpose isn't in our rule set, it's scored generically and
    that limitation is stated plainly.
    """
    context = analyze_context(request.bbox)
    aoi, surrounding = context["aoi"], context["surrounding"]

    all_scores = score_all_purposes(aoi, surrounding, request.budget)

    if request.purpose == "custom":
        label = (request.custom_purpose or "").strip() or "Custom purpose"
        requested = score_custom_purpose(aoi, surrounding, request.budget, label)
    elif request.purpose in KNOWN_PURPOSES:
        requested = next((r for r in all_scores if r["purpose"] == request.purpose), None)
        if requested is None:
            raise HTTPException(status_code=400, detail="Unknown purpose")
    else:
        raise HTTPException(status_code=400, detail=f"Unknown purpose '{request.purpose}'")

    if requested["score"] >= 65:
        label = "Good fit"
    elif requested["score"] >= 40:
        label = "Moderate fit"
    else:
        label = "Poor fit"

    return {
        "aoi_bbox": request.bbox,
        "context": {
            "aoi": aoi,
            "surrounding": surrounding,
        },
        "recommendation": {
            "purpose": requested["purpose"],
            "score": requested["score"],
            "label": label,
            "why": requested["why"],
        },
        "alternatives": [r for r in all_scores if r["purpose"] != requested.get("purpose")][:6],
        "data_limitations": context["data_limitations"],
        "disclaimer": (
            "This is an advisory estimate based on land-cover context only. It is not a "
            "guaranteed business, financial, or legal recommendation. Verify with local "
            "surveys, permits, and domain experts before making a land-use decision."
        ),
    }

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
        "recommendations": recs
    }
