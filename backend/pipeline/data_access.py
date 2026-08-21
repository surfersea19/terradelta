"""
Sentinel-2 data access via Copernicus Data Space Ecosystem (CDSE) STAC API.
Falls back to generating synthetic demo data if no credentials, no matching
imagery, or any real-download step fails.

IMPORTANT — current status (see backend/pipeline/synthetic_training.py and
the project's DETECT assessment for the full writeup):
  - The legacy `catalogue.dataspace.copernicus.eu/stac` endpoint this module
    used to call was deprecated by CDSE on 2025-11-17. This module now uses
    the current endpoint (`stac.dataspace.copernicus.eu/v1`) and the current
    lowercase `sentinel-2-l2a` collection id.
  - Real band download is implemented via each STAC asset's
    `alternate.https.href` (the CDSE "zipper" per-file download URL), which
    requires only the OAuth bearer token already implemented in
    get_cdse_token() — no separate S3 keys needed.
  - This has NOT been exercised against a live CDSE account: this dev
    environment has no network route to CDSE domains, and no CDSE_USERNAME/
    CDSE_PASSWORD have been configured yet. Every download step is wrapped
    defensively — any failure (auth, network, missing asset, schema drift)
    falls back to clearly-labeled synthetic data rather than crashing or
    silently mixing fabricated data into a "real" result. The `data_source`
    field returned by load_bands_for_job() must be surfaced to the user
    (API response, PDF) so real vs. synthetic is never ambiguous.
"""
import os
import json
import logging
import tempfile
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import requests
from typing import Optional
from dotenv import load_dotenv

# main.py already calls load_dotenv() when the app boots via uvicorn, but this
# module is also imported standalone (scripts, debugging, tests) without ever
# importing main.py — in that case CDSE_USERNAME/CDSE_PASSWORD were never
# loaded into os.environ and get_cdse_token() failed before even attempting
# a network request. load_dotenv() is idempotent/safe to call again here.
load_dotenv()

logger = logging.getLogger(__name__)

# Current CDSE STAC endpoint (legacy catalogue.dataspace.copernicus.eu/stac
# was deprecated 2025-11-17 — see https://documentation.dataspace.copernicus.eu/APIs/STAC.html)
CDSE_STAC_SEARCH_URL = "https://stac.dataspace.copernicus.eu/v1/search"
CDSE_COLLECTION = "sentinel-2-l2a"
CDSE_TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

BANDS = ["B02", "B03", "B04", "B08", "B11", "B12"]

# SCL (Scene Classification Layer) class codes considered cloud/shadow/cirrus.
# https://sentinels.copernicus.eu/web/sentinel/technical-guides/sentinel-2-msi/level-2a/algorithm
SCL_CLOUD_CLASSES = {3, 8, 9, 10}  # shadow, cloud-medium, cloud-high, cirrus


def get_cdse_token() -> Optional[str]:
    """Get OAuth token for CDSE. Returns None if credentials not set or auth fails."""
    username = os.getenv("CDSE_USERNAME")
    password = os.getenv("CDSE_PASSWORD")
    if not username or not password:
        logger.warning("CDSE_USERNAME/CDSE_PASSWORD not set — check backend/.env "
                       "is present and loaded (see load_dotenv() at top of this module).")
        return None
    try:
        resp = requests.post(CDSE_TOKEN_URL, data={
            "grant_type": "password",
            "username": username,
            "password": password,
            "client_id": "cdse-public",
        }, timeout=10)
        resp.raise_for_status()
        return resp.json()["access_token"]
    except requests.exceptions.HTTPError as e:
        # Surface the CDSE error body (e.g. invalid_grant) rather than just the HTTP status
        body = e.response.text[:300] if e.response is not None else ""
        logger.warning(f"CDSE token request failed ({e}): {body}")
        return None
    except Exception as e:
        logger.warning(f"CDSE token error: {e}")
        return None


def search_sentinel2(bbox: list, target_date: str, cloud_max: int = 20,
                     date_window_days: int = 15) -> list:
    """
    Search CDSE STAC (current v1 endpoint) for Sentinel-2 L2A products near
    target_date over bbox. Returns list of STAC items sorted by cloud cover
    ascending. bbox: [lon_min, lat_min, lon_max, lat_max]
    """
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    start = (dt - timedelta(days=date_window_days)).strftime("%Y-%m-%dT00:00:00Z")
    end = (dt + timedelta(days=date_window_days)).strftime("%Y-%m-%dT23:59:59Z")

    body = {
        "collections": [CDSE_COLLECTION],
        "bbox": [float(x) for x in bbox],
        "datetime": f"{start}/{end}",
        # NOTE: this was previously 20. Over a +/-15 day window, a bbox can
        # legitimately match more than 20 Sentinel-2 acquisitions (multiple
        # overlapping tiles/relative orbits, ~5-day revisit per satellite).
        # CDSE's default result order is NOT sorted by cloud cover, so a
        # genuinely low-cloud scene (e.g. 6.8%) can sit beyond position 20
        # and be truncated by the server BEFORE our client-side cloud filter
        # below ever sees it -- causing valid <=20%-cloud scenes to be
        # silently missed even though the filter/threshold logic itself is
        # correct. Raising the limit fixes this without changing the cloud
        # threshold, comparison logic, or search window.
        "limit": 100,
    }

    try:
        resp = requests.post(CDSE_STAC_SEARCH_URL, json=body, timeout=20)
        resp.raise_for_status()
        items = resp.json().get("features", [])
        # Filter by whole-tile cloud cover (coarse pre-filter; AOI-level cloud
        # % is recomputed from the SCL band after download, see
        # _compute_aoi_cloud_fraction)
        filtered = [
            item for item in items
            if item.get("properties", {}).get("eo:cloud_cover", 100) <= cloud_max
        ]
        filtered.sort(key=lambda x: x.get("properties", {}).get("eo:cloud_cover", 100))
        logger.info(f"Found {len(filtered)} suitable S2 items near {target_date}")
        return filtered
    except Exception as e:
        logger.warning(f"CDSE STAC search failed: {e}")
        return []


def generate_synthetic_sentinel2(bbox: list, seed: int = 42) -> dict:
    """
    Generate realistic synthetic Sentinel-2 band arrays for demo/testing.
    Returns dict of band arrays (normalized float32, [0,1]).
    Creates a synthetic scene with built-up, vegetation, water, bare soil zones.
    """
    rng = np.random.default_rng(seed)
    H, W = 200, 200  # ~2km x 2km at 10m

    # Base land cover map
    land_cover = np.zeros((H, W), dtype=int)
    # Urban core (center)
    land_cover[80:130, 80:130] = 1   # built-up
    # Vegetation patches
    land_cover[10:60, 10:70] = 2     # vegetation
    land_cover[140:190, 130:190] = 2
    # Water body
    land_cover[150:180, 10:50] = 3   # water
    # Roads (thin lines)
    land_cover[100, :] = 1           # horizontal road
    land_cover[:, 100] = 1           # vertical road

    # Sentinel-2 reflectance values per land cover class (approximate)
    # [B02, B03, B04, B08, B11, B12]
    class_reflectance = {
        0: [0.08, 0.09, 0.10, 0.15, 0.12, 0.08],   # bare soil / sparse
        1: [0.12, 0.13, 0.12, 0.18, 0.25, 0.20],   # built-up (higher SWIR)
        2: [0.03, 0.06, 0.04, 0.35, 0.15, 0.08],   # dense vegetation (high NIR)
        3: [0.06, 0.09, 0.05, 0.05, 0.01, 0.01],   # water (low all)
    }

    bands = {}
    band_names = ["B02", "B03", "B04", "B08", "B11", "B12"]
    for i, bname in enumerate(band_names):
        arr = np.zeros((H, W), dtype=np.float32)
        for cls, refl in class_reflectance.items():
            mask = land_cover == cls
            arr[mask] = refl[i]
        # Add spatial variation + noise
        noise = rng.normal(0, 0.01, (H, W)).astype(np.float32)
        arr = np.clip(arr + noise, 0, 1)
        bands[bname] = arr

    return bands, (H, W), None  # arrays, shape, affine (None for synthetic)


def generate_change_scene(bands_t1: dict, change_fraction: float = 0.15,
                          seed: int = 99, return_mask: bool = False,
                          intensity: float = 1.0):
    """
    Create T2 bands by simulating urban expansion on top of T1 scene.
    Adds new built-up areas (NDBI increase, NDVI decrease).

    intensity (0-1) scales how far each patch has shifted toward its final
    built-up spectral signature, WITHOUT changing patch locations/sizes
    (those are drawn first from the same seeded RNG sequence regardless of
    intensity). This lets the synthetic fallback show a believable gradual
    progression across several dates rather than an instantaneous jump —
    see _progression_fraction() in this module.

    If return_mask=True, also returns the ground-truth boolean change mask
    for the inserted patches (used to build a self-consistent synthetic
    training set — see pipeline/synthetic_training.py).
    """
    rng = np.random.default_rng(seed)
    H, W = next(iter(bands_t1.values())).shape
    bands_t2 = {k: v.copy() for k, v in bands_t1.items()}
    change_mask = np.zeros((H, W), dtype=np.uint8)

    # Create new construction patches (simulate development)
    n_patches = int(5 + change_fraction * 20)
    for _ in range(n_patches):
        cy = rng.integers(20, H - 20)
        cx = rng.integers(20, W - 20)
        ph = rng.integers(5, 25)
        pw = rng.integers(5, 25)
        r0, r1 = max(0, cy - ph // 2), min(H, cy + ph // 2)
        c0, c1 = max(0, cx - pw // 2), min(W, cx + pw // 2)

        # Shift to built-up spectral signature, scaled by intensity.
        # NIR (B08) uses a MULTIPLICATIVE reduction, not a fixed absolute
        # subtraction — an absolute subtraction can drive already-low-NIR
        # base pixels (bare soil/urban fringe, common under random patch
        # placement) toward zero, which flips NDWI = (B03-B08)/(B03+B08)
        # strongly positive and gets misread by human_change_filter's flood
        # rule as "water expansion", silently suppressing genuine
        # construction detections. A proportional reduction stays bounded
        # relative to the base value and avoids that failure mode.
        bands_t2["B02"][r0:r1, c0:c1] = np.clip(
            bands_t2["B02"][r0:r1, c0:c1] + intensity * rng.uniform(0.03, 0.06), 0, 1)
        bands_t2["B03"][r0:r1, c0:c1] = np.clip(
            bands_t2["B03"][r0:r1, c0:c1] + intensity * rng.uniform(0.03, 0.06), 0, 1)
        bands_t2["B04"][r0:r1, c0:c1] = np.clip(
            bands_t2["B04"][r0:r1, c0:c1] + intensity * rng.uniform(0.02, 0.05), 0, 1)
        bands_t2["B08"][r0:r1, c0:c1] = np.clip(
            bands_t2["B08"][r0:r1, c0:c1] * (1 - intensity * rng.uniform(0.15, 0.35)), 0.05, 1)
        bands_t2["B11"][r0:r1, c0:c1] = np.clip(
            bands_t2["B11"][r0:r1, c0:c1] + intensity * rng.uniform(0.05, 0.12), 0, 1)  # SWIR rises
        bands_t2["B12"][r0:r1, c0:c1] = np.clip(
            bands_t2["B12"][r0:r1, c0:c1] + intensity * rng.uniform(0.03, 0.08), 0, 1)

        if intensity > 0.1:
            change_mask[r0:r1, c0:c1] = 1

    # Add small temporal noise (always present — sensor/atmospheric noise floor)
    for bname in bands_t2:
        noise = rng.normal(0, 0.005, bands_t2[bname].shape).astype(np.float32)
        bands_t2[bname] = np.clip(bands_t2[bname] + noise, 0, 1)

    if return_mask:
        return bands_t2, change_mask
    return bands_t2


def _progression_fraction(date_str: str) -> float:
    """
    Maps a calendar date to a 0-1 "development progress" fraction, used only
    by the synthetic fallback to make a multi-date request show a believable
    gradual change instead of either (a) an identical scene for every date
    after the first, or (b) an unrelated random scene per date. Purely a
    demo-continuity device — has no bearing on real Sentinel-2 retrieval.
    """
    d = datetime.strptime(date_str, "%Y-%m-%d")
    epoch_start = datetime(2015, 6, 23)   # Sentinel-2A launch
    epoch_end = datetime(2030, 1, 1)
    frac = (d - epoch_start).days / (epoch_end - epoch_start).days
    return float(np.clip(frac, 0.0, 1.0))


def _find_asset_href(item: dict, band_or_scl: str) -> Optional[str]:
    """
    Find the downloadable HTTPS href for a given band (e.g. 'B04') or 'SCL'
    within a STAC item's assets. CDSE asset keys are typically like
    'B04_10m' / 'B11_20m' / 'SCL_20m'; we match by substring since exact
    naming has varied across CDSE STAC API versions.
    Prefers assets[...]['alternate']['https']['href'] (the zipper download
    URL that works with just the OAuth bearer token); falls back to the
    asset's own 'href' if it's already an https:// URL (some catalogs expose
    band assets directly over HTTPS/COG rather than via SAFE zip nodes).
    """
    assets = item.get("assets", {})
    candidates = [k for k in assets if band_or_scl in k]
    if not candidates:
        return None
    # Prefer the highest-resolution match if multiple (e.g. B04_10m over B04_60m)
    candidates.sort()
    asset = assets[candidates[0]]

    alt = asset.get("alternate", {}).get("https", {}).get("href")
    if alt:
        return alt
    href = asset.get("href", "")
    if href.startswith("https://"):
        return href
    return None


def _download_asset(url: str, token: str, timeout: int = 60) -> Optional[Path]:
    """Download a single band asset to a temp file. Returns the path, or
    None on any failure (auth, network, 404, etc.) — caller must handle."""
    try:
        resp = requests.get(
            url, headers={"Authorization": f"Bearer {token}"},
            stream=True, timeout=timeout,
        )
        resp.raise_for_status()
        suffix = ".jp2" if url.lower().endswith((".jp2)/$value", ".jp2")) or "jp2" in url.lower() else ".tif"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        for chunk in resp.iter_content(chunk_size=1 << 16):
            if chunk:
                tmp.write(chunk)
        tmp.close()
        return Path(tmp.name)
    except Exception as e:
        logger.warning(f"Asset download failed for {url[:80]}...: {e}")
        return None


def _read_reprojected(asset_path: Path, target_grid, resampling_name: str = "bilinear") -> Optional[np.ndarray]:
    """Open a downloaded band file and reproject/resample it onto the shared
    target_grid (see pipeline/geo_grid.py). Returns a (H, W) float32 array,
    or None on failure."""
    try:
        import rasterio
        from rasterio.warp import reproject, Resampling
        from rasterio.enums import Resampling as ResamplingEnum

        resampling = ResamplingEnum.bilinear if resampling_name == "bilinear" else ResamplingEnum.nearest

        with rasterio.open(asset_path) as src:
            dst = np.zeros((target_grid.height, target_grid.width), dtype=np.float32)
            reproject(
                source=rasterio.band(src, 1),
                destination=dst,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=target_grid.transform,
                dst_crs=target_grid.crs,
                resampling=resampling,
            )
        return dst
    except Exception as e:
        logger.warning(f"Reprojection failed for {asset_path}: {e}")
        return None
    finally:
        try:
            asset_path.unlink(missing_ok=True)
        except Exception:
            pass


def download_real_scene(item: dict, token: str, target_grid) -> Optional[tuple]:
    """
    Download all 6 reflectance bands + SCL for one STAC item, reproject onto
    target_grid. Returns (bands: dict[str, np.ndarray float32 [0,1]],
    cloud_fraction: float) or None if any required band is unavailable.
    Band DN values are Sentinel-2 L2A native (0-10000 scale); normalized to
    [0,1] here to match the rest of the pipeline's expected reflectance range.
    """
    bands = {}
    for b in BANDS:
        href = _find_asset_href(item, b)
        if not href:
            logger.warning(f"No asset found for band {b} in item {item.get('id')}")
            return None
        local = _download_asset(href, token)
        if local is None:
            return None
        arr = _read_reprojected(local, target_grid, resampling_name="bilinear")
        if arr is None:
            return None
        bands[b] = np.clip(arr / 10000.0, 0, 1).astype(np.float32)

    # SCL for real cloud masking — optional; proceed without if unavailable
    cloud_fraction = 0.0
    scl_href = _find_asset_href(item, "SCL")
    if scl_href:
        local = _download_asset(scl_href, token)
        if local is not None:
            scl = _read_reprojected(local, target_grid, resampling_name="nearest")
            if scl is not None:
                cloud_mask = np.isin(np.round(scl).astype(int), list(SCL_CLOUD_CLASSES))
                cloud_fraction = float(cloud_mask.mean() * 100)
                bands["_cloud_mask"] = cloud_mask
    else:
        logger.info("No SCL asset found — proceeding without per-AOI cloud masking")

    return bands, cloud_fraction


def load_bands_for_date(bbox: list, date: str, output_dir: Path) -> dict:
    """
    Main entry: retrieve one date's Sentinel-2 scene for bbox. Tries real
    CDSE retrieval first, falls back to synthetic data.

    One scene per calendar date (not per date-pair) — this lets the
    orchestrator retrieve N dates once each and difference consecutive pairs,
    matching how real Sentinel-2 acquisitions actually work and avoiding
    redundant downloads of shared dates across consecutive intervals.

    Returns a dict:
      bands: {band_name: np.array float32 [0,1]}
      actual_date: str — the real acquisition date used (may differ from the
        requested date by up to the search window if using real imagery)
      cloud_pct: float
      shape: (H, W)
      data_source: "real_sentinel2" | "synthetic_fallback"
      fallback_reason: str | None — always populated when data_source is
        "synthetic_fallback", so this is never silently mislabeled as real.
    """
    from pipeline.geo_grid import build_target_grid

    token = get_cdse_token()
    reason = None

    if not token:
        reason = "No CDSE credentials configured (CDSE_USERNAME/CDSE_PASSWORD unset or auth failed)."
    else:
        try:
            items = search_sentinel2(bbox, date)
            if not items:
                reason = f"No cloud-free Sentinel-2 scene found near {date}."
            else:
                target_grid = build_target_grid(bbox, resolution_m=10.0)
                scene = download_real_scene(items[0], token, target_grid)
                if scene is None:
                    reason = "Real asset download failed (network, auth, or missing band asset)."
                else:
                    bands, cloud_pct = scene
                    bands.pop("_cloud_mask", None)
                    actual_date = items[0].get("properties", {}).get("datetime", date)[:10]
                    logger.info(f"Real Sentinel-2 imagery retrieved for {actual_date} "
                               f"(requested {date}), cloud={cloud_pct:.1f}%")
                    return {
                        "bands": bands, "actual_date": actual_date,
                        "cloud_pct": cloud_pct,
                        "shape": (target_grid.height, target_grid.width),
                        "data_source": "real_sentinel2",
                        "fallback_reason": None,
                    }
        except Exception as e:
            reason = f"Real retrieval raised an unexpected error: {e}"

    # ── Synthetic fallback ───────────────────────────────────────────────
    # Fixed base terrain per bbox (NOT per date) + a fixed set of "development
    # patches" in fixed locations, whose intensity scales with how late the
    # requested date is (see _progression_fraction). This shows a believable
    # gradual progression across several requested dates instead of either
    # (a) an identical scene for every date after the first — the previous
    # bug, where seed depended only on bbox — or (b) unrelated random scenes
    # per date, which would make ~100% of the AOI look "changed" every step.
    logger.warning(f"Falling back to synthetic Sentinel-2-style data for "
                   f"bbox={bbox}, date={date}: {reason}")
    bbox_seed = int(abs(sum(bbox)) * 100) % 10000
    base_bands, shape, _ = generate_synthetic_sentinel2(bbox, seed=bbox_seed)
    frac = _progression_fraction(date)
    bands = generate_change_scene(base_bands, change_fraction=0.18,
                                  seed=bbox_seed + 500, intensity=frac)
    cloud_pct = float(np.random.default_rng(bbox_seed + sum(map(ord, date)) % 1000).uniform(2, 15))

    return {
        "bands": bands, "actual_date": date,
        "cloud_pct": cloud_pct, "shape": shape,
        "data_source": "synthetic_fallback",
        "fallback_reason": reason,
    }
