"""
Explorer router — F2: Change Explorer endpoints.
GET /api/explorer/locations
GET /api/explorer/location/{location_id}
"""
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/explorer", tags=["explorer"])

EXPLORER_DATA_DIR = Path(__file__).parent.parent / "explorer_data"

# Hardcoded pre-analyzed notable locations
EXPLORER_LOCATIONS = [
    {
        "id": "atal-setu",
        "title": "India's Longest Sea Bridge",
        "hint": "A massive linear structure built across a bay in a major Indian coastal city. Completed in early 2024.",
        "category": "Bridge / Infrastructure",
        "region": "South Asia",
        "before_year": 2019,
        "after_year": 2024,
        "reveal": {
            "name": "Atal Setu, Mumbai",
            "change_type": "Bridge Construction",
            "stats": {"changed_area_ha": 18.5, "change_percent": 22, "num_clusters": 3, "mean_confidence": 0.82},
            "description": (
                "The Atal Setu (Mumbai Trans Harbour Link) is India's longest sea bridge at 21.8 km, "
                "connecting Sewri in Mumbai to Nhava Sheva in Navi Mumbai. Construction began in 2018 "
                "and the bridge opened to traffic in January 2024. The Sentinel-2 change signal shows "
                "the bridge deck, approach roads, and reclaimed land clearly as high-confidence impervious "
                "surface expansion over the bay."
            ),
        },
    },
    {
        "id": "gift-city",
        "title": "A Greenfield Financial District Rising from Farmland",
        "hint": "A planned smart city built on previously agricultural land in western India.",
        "category": "Urban Development",
        "region": "South Asia",
        "before_year": 2015,
        "after_year": 2023,
        "reveal": {
            "name": "GIFT City, Gujarat",
            "change_type": "Greenfield Urban Development",
            "stats": {"changed_area_ha": 420, "change_percent": 68, "num_clusters": 8, "mean_confidence": 0.87},
            "description": (
                "GIFT City (Gujarat International Finance Tec-City) is India's first operational smart city "
                "and International Financial Services Centre. Built on 886 acres of agricultural land near "
                "Gandhinagar, the development shows a dramatic transformation from open farmland to dense "
                "built-up towers, roads, and infrastructure. The change map highlights the phased "
                "construction in distinct spatial clusters."
            ),
        },
    },
    {
        "id": "jewar-airport",
        "title": "A New International Airport Under Construction",
        "hint": "A major airport site under development near India's capital, replacing farmland.",
        "category": "Airport Infrastructure",
        "region": "South Asia",
        "before_year": 2020,
        "after_year": 2024,
        "reveal": {
            "name": "Noida International Airport (Jewar), Uttar Pradesh",
            "change_type": "Airport Construction",
            "stats": {"changed_area_ha": 1300, "change_percent": 55, "num_clusters": 12, "mean_confidence": 0.79},
            "description": (
                "The Noida International Airport at Jewar is one of India's largest airport projects. "
                "Phase 1 involves 1,334 hectares of land. Sentinel-2 imagery captures the large-scale "
                "land clearing, runway grading, taxiway foundations, and terminal construction zones. "
                "The high BSI (bare soil index) signal dominates the change map, reflecting mass "
                "earthwork typical of early airport construction phases."
            ),
        },
    },
    {
        "id": "palm-jumeirah",
        "title": "An Artificial Archipelago Built into the Sea",
        "hint": "A famous palm-shaped artificial island development in the Middle East.",
        "category": "Land Reclamation",
        "region": "Middle East",
        "before_year": 2001,
        "after_year": 2006,
        "reveal": {
            "name": "Palm Jumeirah, Dubai",
            "change_type": "Land Reclamation & Development",
            "stats": {"changed_area_ha": 560, "change_percent": 100, "num_clusters": 1, "mean_confidence": 0.95},
            "description": (
                "Palm Jumeirah is the world's largest artificial island, constructed by reclaiming "
                "land from the Persian Gulf. Built using sand dredged from the seabed and rock breakwaters, "
                "the change detection shows the full land reclamation signal — a near-zero NDWI "
                "(water disappears) and strong NDBI increase as sand and concrete replace ocean. "
                "This is one of the most dramatic human land-change events visible from space."
            ),
        },
    },
    {
        "id": "dholera-sir",
        "title": "India's First Greenfield Smart City from Scratch",
        "hint": "A massive planned industrial city being built on salt flats in western India.",
        "category": "Smart City Development",
        "region": "South Asia",
        "before_year": 2017,
        "after_year": 2023,
        "reveal": {
            "name": "Dholera Special Investment Region, Gujarat",
            "change_type": "Greenfield Industrial City",
            "stats": {"changed_area_ha": 980, "change_percent": 38, "num_clusters": 15, "mean_confidence": 0.71},
            "description": (
                "Dholera SIR spans 920 km² and is India's largest greenfield smart city project, "
                "planned to eventually house 2 million people. Change detection across 2017–2023 shows "
                "road network grading, trunk infrastructure corridors, and the first residential/industrial "
                "zones. Moderate confidence reflects the early-stage nature of development, where earthworks "
                "on salt flats produce ambiguous spectral signatures."
            ),
        },
    },
    {
        "id": "amaravati",
        "title": "A Planned State Capital Abandoned Mid-Construction",
        "hint": "A greenfield capital city in southern India where construction started then largely halted.",
        "category": "Urban Development / Stalled",
        "region": "South Asia",
        "before_year": 2015,
        "after_year": 2022,
        "reveal": {
            "name": "Amaravati, Andhra Pradesh",
            "change_type": "Greenfield Capital City (Partial Construction)",
            "stats": {"changed_area_ha": 340, "change_percent": 29, "num_clusters": 6, "mean_confidence": 0.76},
            "description": (
                "Amaravati was designed as Andhra Pradesh's new capital city after the bifurcation of "
                "the state in 2014. Construction began 2016 with roads, government buildings, and "
                "residential zones. After a change of government in 2019, most work stalled. "
                "The change map captures completed road networks and cleared/graded land that "
                "remained undeveloped — a rare case of partial human change followed by stasis."
            ),
        },
    },
    {
        "id": "neom-backbone",
        "title": "A 170km Straight-Line City Being Built in a Desert",
        "hint": "An extraordinary linear megaproject under construction in a remote desert peninsula.",
        "category": "Megaproject",
        "region": "Middle East",
        "before_year": 2020,
        "after_year": 2024,
        "reveal": {
            "name": "NEOM — The Line, Saudi Arabia",
            "change_type": "Desert Megaproject Construction",
            "stats": {"changed_area_ha": 2400, "change_percent": 12, "num_clusters": 4, "mean_confidence": 0.68},
            "description": (
                "NEOM's 'The Line' is a planned 170km linear city being constructed in the Tabuk region "
                "of northwest Saudi Arabia. Sentinel-2 captures site preparation: the massive excavation "
                "corridor, construction camp clusters, and access road networks visible as strong BSI "
                "and NDBI signals against the background desert. Lower confidence reflects the ongoing "
                "spectrally mixed construction phase and limited building-height signal at 10m resolution."
            ),
        },
    },
    {
        "id": "bangalore-peripheral",
        "title": "Rapid IT Corridor Expansion on a City's Fringe",
        "hint": "A major Indian tech city where farmland on the urban edge converted rapidly to tech parks and apartments.",
        "category": "Urban Sprawl",
        "region": "South Asia",
        "before_year": 2016,
        "after_year": 2023,
        "reveal": {
            "name": "Sarjapur–Whitefield Corridor, Bengaluru",
            "change_type": "IT Hub & Residential Expansion",
            "stats": {"changed_area_ha": 780, "change_percent": 52, "num_clusters": 22, "mean_confidence": 0.80},
            "description": (
                "The Sarjapur–Whitefield corridor in southeastern Bengaluru experienced explosive "
                "growth between 2016 and 2023, driven by IT campus expansion and high-density "
                "residential development. Sentinel-2 change detection shows fragmented but pervasive "
                "built-up expansion replacing paddy fields and scrubland, consistent with the "
                "piecemeal land conversion pattern of Indian peri-urban growth."
            ),
        },
    },
]


@router.get("/locations")
async def get_locations():
    """Return all pre-analyzed explorer locations (metadata only, no reveal)."""
    preview_locations = []
    for loc in EXPLORER_LOCATIONS:
        preview_locations.append({
            "id":          loc["id"],
            "title":       loc["title"],
            "hint":        loc["hint"],
            "category":    loc["category"],
            "region":      loc["region"],
            "before_year": loc["before_year"],
            "after_year":  loc["after_year"],
            # Placeholder image URLs (in production: real pre-computed images)
            "before_url":  f"/explorer-static/{loc['id']}/before.png",
            "after_url":   f"/explorer-static/{loc['id']}/after.png",
            "change_url":  f"/explorer-static/{loc['id']}/change.png",
        })
    return {"locations": preview_locations, "total": len(preview_locations)}


@router.get("/location/{location_id}")
async def get_location(location_id: str):
    """Return full data including reveal for a specific location."""
    loc = next((l for l in EXPLORER_LOCATIONS if l["id"] == location_id), None)
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    return {
        **loc,
        "before_url": f"/explorer-static/{loc['id']}/before.png",
        "after_url":  f"/explorer-static/{loc['id']}/after.png",
        "change_url": f"/explorer-static/{loc['id']}/change.png",
    }
