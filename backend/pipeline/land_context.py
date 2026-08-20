"""
Land context analysis for the AI Land Advisor (DECIDE).

Reuses the existing synthetic-Sentinel-2 fallback + spectral index pipeline
(the same data path used by Change Analysis / Monitoring) to characterise:
  - the user's selected AOI (their land)
  - a surrounding buffer ring (proxy for "nearby" context)

Enhancement (feature/ai-land-advisor):
  - Attempts a real OSM Overpass query for nearby amenities/roads if network
    is available. Gracefully falls back to land-cover-only mode and clearly
    states which data source was used.

IMPORTANT — honesty about data limitations:
We never invent specific roads, businesses, population figures, or facilities
that we haven't actually fetched. Every inferred fact is labelled as such.
"""
import logging
import math
import urllib.request
import urllib.error
import json
from typing import Optional
import numpy as np

from pipeline.data_access import generate_synthetic_sentinel2
from pipeline.preprocessing import preprocess_bands

logger = logging.getLogger(__name__)

# ── OSM Overpass helpers ─────────────────────────────────────────────────────

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OSM_TIMEOUT  = 6   # seconds — keep snappy for demo

# Amenity tags we care about, grouped by relevance category
AMENITY_QUERIES = {
    "education":   ["school", "college", "university", "kindergarten"],
    "healthcare":  ["hospital", "clinic", "pharmacy", "doctors"],
    "commercial":  ["marketplace", "bank", "supermarket", "fuel"],
    "transport":   ["bus_station", "taxi", "ferry_terminal"],
}

HIGHWAY_TAGS = ["trunk", "primary", "secondary", "tertiary", "motorway"]


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def _bbox_center(bbox):
    lon_min, lat_min, lon_max, lat_max = bbox
    return (lat_min + lat_max) / 2, (lon_min + lon_max) / 2


def _overpass_query(bbox: list, radius_m: int = 5000) -> Optional[dict]:
    """
    Query Overpass for amenities + major roads near the AOI center.
    Returns a structured dict or None if the query fails / times out.
    """
    clat, clon = _bbox_center(bbox)

    # Build a compact Overpass QL query for amenities + roads within radius
    amenity_values = "|".join(
        v for vals in AMENITY_QUERIES.values() for v in vals
    )
    highway_values = "|".join(HIGHWAY_TAGS)

    ql = f"""
[out:json][timeout:{OSM_TIMEOUT}];
(
  node(around:{radius_m},{clat},{clon})[amenity~"^({amenity_values})$"];
  way(around:{radius_m},{clat},{clon})[highway~"^({highway_values})$"];
  node(around:{radius_m},{clat},{clon})[shop~"^(supermarket|mall|department_store)$"];
);
out center {min(radius_m // 50, 200)};
"""
    try:
        req = urllib.request.Request(
            OVERPASS_URL,
            data=ql.strip().encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=OSM_TIMEOUT + 2) as resp:
            raw = resp.read().decode()
        return json.loads(raw)
    except Exception as exc:
        logger.warning("Overpass query failed (will use land-cover fallback): %s", exc)
        return None


def _parse_osm_proximity(osm_data: dict, bbox: list) -> dict:
    """Parse OSM response into structured proximity facts."""
    clat, clon = _bbox_center(bbox)
    elements = osm_data.get("elements", [])

    counts = {cat: 0 for cat in AMENITY_QUERIES}
    nearest_amenity_km: Optional[float] = None
    road_types_found: set = set()
    has_major_road = False
    named_nearby = []   # (name, type, dist_km)

    for el in elements:
        tags = el.get("tags", {})
        amenity = tags.get("amenity", "")
        highway = tags.get("highway", "")
        shop    = tags.get("shop", "")

        # Coordinates: node has lat/lon directly; way has center
        if el.get("type") == "node":
            elat, elon = el.get("lat", clat), el.get("lon", clon)
        elif el.get("type") == "way":
            center = el.get("center", {})
            elat = center.get("lat", clat)
            elon = center.get("lon", clon)
        else:
            continue

        dist_km = _haversine_km(clat, clon, elat, elon)

        if highway in HIGHWAY_TAGS:
            road_types_found.add(highway)
            if highway in ("trunk", "primary", "motorway"):
                has_major_road = True
            continue  # roads don't count as amenities

        for cat, vals in AMENITY_QUERIES.items():
            if amenity in vals or shop in ("supermarket", "mall", "department_store"):
                counts[cat] += 1
                if nearest_amenity_km is None or dist_km < nearest_amenity_km:
                    nearest_amenity_km = dist_km
                name = tags.get("name", amenity or shop)
                if len(named_nearby) < 8 and name and name != amenity:
                    named_nearby.append({"name": name, "type": amenity or shop, "dist_km": round(dist_km, 2)})
                break

    return {
        "source": "osm_live",
        "amenity_counts": counts,
        "nearest_amenity_km": round(nearest_amenity_km, 2) if nearest_amenity_km is not None else None,
        "road_types": sorted(road_types_found),
        "has_major_road": has_major_road,
        "named_nearby": sorted(named_nearby, key=lambda x: x["dist_km"])[:6],
        "total_amenities": sum(counts.values()),
    }


def _proximity_fallback(aoi: dict, surrounding: dict) -> dict:
    """
    When Overpass is unavailable, infer proximity signals ONLY from land cover.
    We never fabricate counts — we produce 'inferred' flags instead.
    """
    built = surrounding["built_up_pct"]
    return {
        "source": "land_cover_inferred",
        "amenity_counts": None,        # cannot determine without OSM
        "nearest_amenity_km": None,
        "road_types": [],
        "has_major_road": None,        # unknown
        "named_nearby": [],
        "total_amenities": None,
        # Derived qualitative signals
        "connectivity_proxy": (
            "high" if built > 40 else
            "medium" if built > 15 else
            "low"
        ),
        "urbanisation_proxy": (
            "urban" if built > 50 else
            "peri-urban" if built > 20 else
            "rural"
        ),
    }


# ── Bbox area estimate ────────────────────────────────────────────────────────

def _area_ha(bbox: list) -> float:
    """Approximate area of bbox in hectares using haversine-based calculation."""
    lon_min, lat_min, lon_max, lat_max = bbox
    clat = (lat_min + lat_max) / 2
    width_km  = _haversine_km(clat, lon_min, clat, lon_max)
    height_km = _haversine_km(lat_min, lon_min, lat_max, lon_min)
    return round(width_km * height_km * 100, 2)   # km² → ha


# ── Composition from synthetic S2 ────────────────────────────────────────────

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

    water      = ndwi > 0.15
    builtup    = (~water) & (ndbi > 0.0)
    vegetation = (~water) & (~builtup) & (ndvi > 0.25)
    bare       = ~(water | builtup | vegetation)

    return {
        "built_up_pct":    round(float(builtup.sum())    / total * 100, 1),
        "vegetation_pct":  round(float(vegetation.sum()) / total * 100, 1),
        "water_pct":       round(float(water.sum())      / total * 100, 1),
        "bare_soil_pct":   round(float(bare.sum())       / total * 100, 1),
    }


# ── Main context function ─────────────────────────────────────────────────────

def analyze_context(bbox: list) -> dict:
    """
    Returns:
      - aoi / surrounding land-cover composition
      - OSM proximity facts (or land-cover inference fallback)
      - area_ha estimate
      - data_limitations list
    """
    aoi_comp        = _composition(bbox)
    buffer_bbox     = _expand_bbox(bbox, factor=2.5)
    surrounding_comp = _composition(buffer_bbox)

    # Try live OSM data; fall back gracefully
    osm_raw   = _overpass_query(bbox, radius_m=5000)
    if osm_raw is not None:
        proximity = _parse_osm_proximity(osm_raw, bbox)
        data_limitations = [
            "Land cover is derived from Sentinel-2-style spectral indices (NDVI/NDBI/NDWI); "
            "small or below-30m features may not be captured.",
            "OSM facility data is community-maintained and may be incomplete in some regions.",
            "Area and distance estimates are approximate (WGS-84 haversine).",
        ]
    else:
        proximity = _proximity_fallback(aoi_comp, surrounding_comp)
        data_limitations = [
            "OSM Overpass was unavailable — road and facility proximity are inferred from "
            "surrounding land-cover density only, not actual OSM data.",
            "Land cover is derived from Sentinel-2-style spectral indices (NDVI/NDBI/NDWI); "
            "small or below-30m features may not be captured.",
            "Accessibility signals (connectivity, urbanisation) are proxies based on built-up %, "
            "not verified road-network or population data.",
        ]

    return {
        "aoi":              aoi_comp,
        "surrounding":      surrounding_comp,
        "buffer_bbox":      buffer_bbox,
        "proximity":        proximity,
        "area_ha":          _area_ha(bbox),
        "data_limitations": data_limitations,
    }


# ── Purpose scoring ───────────────────────────────────────────────────────────

BUDGET_TIERS = {
    "low":    (0,            1_000_000),
    "medium": (1_000_000,   10_000_000),
    "high":   (10_000_000,  float("inf")),
}


def _budget_tier(budget: float) -> str:
    if budget < BUDGET_TIERS["low"][1]:    return "low"
    if budget < BUDGET_TIERS["medium"][1]: return "medium"
    return "high"


def _connectivity_score(proximity: dict) -> float:
    """Return 0-1 connectivity signal, regardless of OSM availability."""
    if proximity["source"] == "osm_live":
        roads = proximity.get("road_types", [])
        if "trunk" in roads or "motorway" in roads:  return 1.0
        if "primary" in roads:                        return 0.8
        if "secondary" in roads:                      return 0.6
        if "tertiary" in roads:                       return 0.4
        return 0.2
    else:
        proxy = proximity.get("connectivity_proxy", "low")
        return {"high": 0.75, "medium": 0.50, "low": 0.25}.get(proxy, 0.3)


def _amenity_score(proximity: dict, categories: list) -> float:
    """Return 0-1 amenity availability for listed categories."""
    if proximity["source"] != "osm_live" or proximity["amenity_counts"] is None:
        return 0.5  # unknown — neutral
    counts = proximity["amenity_counts"]
    total  = sum(counts.get(c, 0) for c in categories)
    return min(1.0, total / 10.0)


PURPOSE_RULES = {
    "agriculture": {
        "icon": "🌾",
        "min_budget_tier": "low",
        "score_fn": lambda aoi, sur, prox, tier: (
            50
            + (sur["vegetation_pct"] - 30) * 0.8
            - sur["built_up_pct"] * 0.6
            + _connectivity_score(prox) * 8
            - (20 if tier == "high" else 0)
        ),
        "why_fn": lambda aoi, sur, prox, tier: [
            f"Surrounding vegetation cover is {sur['vegetation_pct']}% — "
            + ("strong green/agricultural signal." if sur['vegetation_pct'] > 30
               else "relatively low for prime farmland."),
            f"Built-up density of {sur['built_up_pct']}% in the buffer zone "
            + ("keeps development pressure low — good for sustained farming."
               if sur['built_up_pct'] < 20
               else "indicates urbanisation pressure that may raise land cost over time."),
            ("Budget is well-matched to agricultural use, which has a lower capital floor than built projects."
             if tier == "low"
             else "Your budget exceeds typical agricultural needs — consider agri-processing, storage, or mixed use."),
            *([f"Road connectivity ({', '.join(prox['road_types'])}) supports logistics access."]
              if prox.get("road_types") else []),
        ],
    },
    "residential": {
        "icon": "🏠",
        "min_budget_tier": "medium",
        "score_fn": lambda aoi, sur, prox, tier: (
            50
            + (sur["built_up_pct"] - 20) * 0.6
            + sur["vegetation_pct"] * 0.2
            + _connectivity_score(prox) * 10
            + _amenity_score(prox, ["education", "healthcare", "commercial"]) * 12
            - (15 if tier == "low" else 0)
        ),
        "why_fn": lambda aoi, sur, prox, tier: [
            f"Surrounding built-up density: {sur['built_up_pct']}% — "
            + ("indicates an already-developing residential context with likely amenities."
               if sur['built_up_pct'] > 20
               else "suggests a peri-urban or rural edge — growth potential but limited current amenities."),
            f"Vegetation share of {sur['vegetation_pct']}% nearby "
            + ("adds residential greenery value." if sur['vegetation_pct'] > 15
               else "is low — limited green character."),
            ("Capital tier supports residential construction." if tier != "low"
             else "Low budget may only support incremental/self-build construction."),
            *([f"Nearby amenities: {prox['total_amenities']} nodes found within 5 km (education, healthcare, commercial)."]
              if prox.get("total_amenities") else []),
        ],
    },
    "commercial": {
        "icon": "🏢",
        "min_budget_tier": "medium",
        "score_fn": lambda aoi, sur, prox, tier: (
            45
            + (sur["built_up_pct"] - 25) * 0.9
            - sur["vegetation_pct"] * 0.2
            + _connectivity_score(prox) * 15
            + _amenity_score(prox, ["commercial", "transport"]) * 10
            + (10 if tier == "high" else 0)
        ),
        "why_fn": lambda aoi, sur, prox, tier: [
            f"Built-up density of {sur['built_up_pct']}% "
            + ("is consistent with an accessible, economically active area."
               if sur['built_up_pct'] > 25
               else "is relatively low — commercial footfall may be limited today."),
            f"Road connectivity score: {'high' if _connectivity_score(prox) > 0.6 else 'moderate' if _connectivity_score(prox) > 0.35 else 'low'} — "
            + ("strong road access proxy for commercial viability."
               if _connectivity_score(prox) > 0.6
               else "moderate access — verify actual road quality on-ground."),
            ("Capital tier supports commercial fit-out and construction." if tier != "low"
             else "Low budget is unlikely to cover commercial-grade construction."),
        ],
    },
    "showroom": {
        "icon": "🚗",
        "min_budget_tier": "medium",
        "score_fn": lambda aoi, sur, prox, tier: (
            45
            + (sur["built_up_pct"] - 25) * 0.9
            - sur["vegetation_pct"] * 0.15
            + _connectivity_score(prox) * 18
            + (10 if tier == "high" else 0)
        ),
        "why_fn": lambda aoi, sur, prox, tier: [
            f"Showrooms require high road visibility — connectivity score: {'high' if _connectivity_score(prox) > 0.6 else 'moderate' if _connectivity_score(prox) > 0.35 else 'low'}.",
            f"Surrounding built-up density ({sur['built_up_pct']}%) "
            + ("suggests reasonable passing traffic volume."
               if sur['built_up_pct'] > 25
               else "is low — showrooms typically benefit from denser/high-traffic surroundings."),
            ("Capital tier is adequate for showroom fit-out and frontage." if tier != "low"
             else "Low budget may constrain showroom-quality construction and display space."),
        ],
    },
    "warehouse": {
        "icon": "📦",
        "min_budget_tier": "low",
        "score_fn": lambda aoi, sur, prox, tier: (
            55
            + (sur["built_up_pct"] - 10) * 0.4
            - max(0, sur["built_up_pct"] - 40) * 0.5
            + _connectivity_score(prox) * 12
            - sur["water_pct"] * 0.6
        ),
        "why_fn": lambda aoi, sur, prox, tier: [
            f"Built-up density of {sur['built_up_pct']}% — "
            + ("ideal peri-urban density for a logistics/warehousing site."
               if 10 <= sur['built_up_pct'] <= 40
               else "outside the typical sweet-spot for warehousing (moderate density preferred for road access without prime-land costs)."),
            f"Water cover of {sur['water_pct']}% — "
            + ("low flood/waterlogging risk signal." if sur['water_pct'] < 5
               else "worth checking flood risk before committing."),
            f"Road connectivity: {'good' if _connectivity_score(prox) > 0.6 else 'moderate' if _connectivity_score(prox) > 0.35 else 'limited'} — "
            "logistics sites critically depend on arterial road access.",
        ],
    },
    "school": {
        "icon": "🏫",
        "min_budget_tier": "medium",
        "score_fn": lambda aoi, sur, prox, tier: (
            45
            + (sur["built_up_pct"] - 20) * 0.55
            + sur["vegetation_pct"] * 0.15
            + _connectivity_score(prox) * 8
            - _amenity_score(prox, ["education"]) * 12
            - (10 if tier == "low" else 0)
        ),
        "why_fn": lambda aoi, sur, prox, tier: [
            f"Surrounding built-up density ({sur['built_up_pct']}%) used as a population-density proxy — "
            "actual student catchment requires a proper demographic survey.",
            f"Vegetation share ({sur['vegetation_pct']}%) — "
            + ("supports an open campus character." if sur['vegetation_pct'] > 15
               else "limited open space signal nearby."),
            *([f"Existing education facilities in 5 km: {prox['amenity_counts'].get('education',0)} — "
               + ("some competition/saturation risk." if prox['amenity_counts'].get('education',0) > 3
                  else "low competition; potential unmet demand.")]
              if prox.get("amenity_counts") else ["Existing school density nearby: unknown (OSM unavailable)."]),
            ("Institutional-scale investment requires sustained capital." if tier != "low"
             else "A phased construction approach may be necessary at this budget tier."),
        ],
    },
    "hospital": {
        "icon": "🏥",
        "min_budget_tier": "high",
        "score_fn": lambda aoi, sur, prox, tier: (
            40
            + (sur["built_up_pct"] - 25) * 0.6
            + _connectivity_score(prox) * 10
            - _amenity_score(prox, ["healthcare"]) * 15
            - (25 if tier != "high" else 0)
        ),
        "why_fn": lambda aoi, sur, prox, tier: [
            f"Surrounding built-up density ({sur['built_up_pct']}%) as population proxy — "
            "verified patient catchment requires census + health-utilisation data.",
            *([f"Existing healthcare facilities in 5 km: {prox['amenity_counts'].get('healthcare',0)} — "
               + ("high saturation — strong business case needed." if prox['amenity_counts'].get('healthcare',0) > 3
                  else "low competition — potential unmet demand.")]
              if prox.get("amenity_counts") else ["Existing healthcare density: unknown (OSM unavailable)."]),
            f"Road connectivity: {'strong' if _connectivity_score(prox) > 0.6 else 'moderate' if _connectivity_score(prox) > 0.35 else 'limited'} — "
            "emergency access and ambulance routes are critical.",
            ("Budget tier is consistent with hospital-scale investment." if tier == "high"
             else "Budget is insufficient for a hospital at this stage; consider a clinic or diagnostic centre."),
        ],
    },
}


def score_all_purposes(aoi: dict, surrounding: dict, budget: float,
                        proximity: Optional[dict] = None) -> list:
    """Score every known purpose category. Returns sorted list (desc by score)."""
    tier = _budget_tier(budget)
    prox = proximity or _proximity_fallback(aoi, surrounding)
    results = []
    for purpose, rule in PURPOSE_RULES.items():
        raw   = rule["score_fn"](aoi, surrounding, prox, tier)
        score = int(max(0, min(100, round(raw))))
        why   = rule["why_fn"](aoi, surrounding, prox, tier)
        results.append({
            "purpose": purpose,
            "icon":    rule["icon"],
            "score":   score,
            "why":     why,
        })
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def score_custom_purpose(aoi: dict, surrounding: dict, budget: float,
                          custom_label: str,
                          proximity: Optional[dict] = None) -> dict:
    """Generic, conservative scoring for a user-typed custom purpose."""
    tier  = _budget_tier(budget)
    prox  = proximity or _proximity_fallback(aoi, surrounding)
    conn  = _connectivity_score(prox)
    balance_score = 50 + (surrounding["built_up_pct"] - surrounding["vegetation_pct"]) * 0.2 + conn * 5
    score = int(max(0, min(100, round(balance_score))))
    why = [
        f"'{custom_label}' has no purpose-specific scoring rule — this is a general "
        "development-suitability estimate based on land-cover and connectivity only.",
        f"Surrounding land cover: {surrounding['built_up_pct']}% built-up, "
        f"{surrounding['vegetation_pct']}% vegetation, {surrounding['water_pct']}% water, "
        f"{surrounding['bare_soil_pct']}% bare/other.",
        f"Connectivity proxy: {'high' if conn > 0.6 else 'moderate' if conn > 0.35 else 'low'} — "
        "road access affects most land uses.",
        f"Budget tier: {tier}.",
    ]
    return {"purpose": custom_label, "icon": "✏️", "score": score, "why": why}
