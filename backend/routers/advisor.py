from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any

router = APIRouter(prefix="/api/advisor", tags=["advisor"])

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
