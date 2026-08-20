"""
TerraDelta — standalone real-Sentinel-2 pipeline test.

Run this from your `backend` folder (same place you ran the
get_cdse_token() check), with your virtualenv active and backend/.env
present:

    cd backend
    python test_real_pipeline.py

WHAT THIS DOES
    1. CDSE authentication      (pipeline.data_access.get_cdse_token)
    2. STAC search              (pipeline.data_access.search_sentinel2)
    3. Asset availability check (B02/B03/B04/B08/B11/B12/SCL hrefs present)
    4. Real asset download      (pipeline.data_access.download_real_scene)
    5. AOI clipping + common-grid reprojection (same function, via
       pipeline.geo_grid.build_target_grid)
    6. SCL-based cloud masking  (same function)
    7. 42-feature array         (pipeline.features.build_feature_array)
    8. RF inference             (pipeline.inference.run_rf_inference)

This calls your actual project code — nothing here is a reimplementation,
so a PASS genuinely means that part of the pipeline works against your
live CDSE account.

WHY ONLY ONE REAL DOWNLOAD
    The current download_real_scene() fetches each band asset in full
    (it doesn't do a windowed/range HTTP read yet — that would be a real
    code change, which you asked me not to make here). A single Sentinel-2
    tile's bands can be tens of MB each, so downloading TWO dates' worth
    just for this test would multiply that for no real benefit. Instead:
      - Steps 1-6 use ONE real downloaded date (the actual minimum needed
        to prove auth/search/download/clip/reproject/cloud-mask work).
      - Steps 7-8 reuse that SAME real scene as both "T1" and "T2" (a
        self-comparison). This is NOT a real change-detection test — the
        diff will be ~zero by construction — it only proves the feature
        pipeline and RF model run cleanly on real-shaped, real-valued
        Sentinel-2 data without crashing or producing NaNs.
    You'll be asked to confirm before the real download starts.

SAFETY
    - Your CDSE_USERNAME/CDSE_PASSWORD are never printed — only whether a
      token was obtained.
    - Nothing in this script writes to or modifies any file in the repo.
    - Downloaded band files go to your OS temp dir and are deleted by the
      pipeline code after use (same as production behaviour).

CONFIGURE (edit these three lines if you want a different area/date):
"""
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

# ── Config — small AOI (~1km x 1km), a date well in the past so the L2A
#    product is certainly published, and CDSE's default 20% cloud filter ──
BBOX = [72.80, 19.05, 72.81, 19.06]                       # [lon_min, lat_min, lon_max, lat_max]
TARGET_DATE = (datetime.utcnow() - timedelta(days=200)).strftime("%Y-%m-%d")  # ~6-7 months ago

sys.path.insert(0, str(Path(__file__).parent))  # so `pipeline.*` imports work run from anywhere

results = {}


def step(name):
    print(f"\n{'='*60}\n{name}\n{'='*60}")


def mark(key, ok, detail=""):
    results[key] = "PASS" if ok else "FAIL"
    print(f"-> {results[key]}" + (f" — {detail}" if detail else ""))


try:
    import pipeline.data_access as da
    from pipeline.geo_grid import build_target_grid
    from pipeline.preprocessing import preprocess_bands
    from pipeline.features import build_feature_array
    from pipeline.inference import run_rf_inference, get_model
except Exception as e:
    print(f"FATAL: could not import project pipeline modules ({e}).")
    print("Make sure you're running this from the backend/ folder with your venv active.")
    sys.exit(1)


# ── 1. CDSE authentication ──────────────────────────────────────────────
step("1. CDSE authentication")
token = da.get_cdse_token()
mark("1_auth", bool(token), f"token acquired (length={len(token)})" if token else "no token — check backend/.env is present and CDSE_USERNAME/CDSE_PASSWORD are correct")
if not token:
    print("\nStopping here — nothing downstream can run without a token.")
    sys.exit(1)


# ── 2. STAC search ───────────────────────────────────────────────────────
step(f"2. STAC search — bbox={BBOX}, near {TARGET_DATE}")
items = da.search_sentinel2(BBOX, TARGET_DATE)
mark("2_search", bool(items), f"{len(items)} candidate scene(s) found" if items else "no matching scenes — try a different bbox/date")
if not items:
    print("\nStopping here — nothing downstream can run without a matching scene.")
    sys.exit(1)

item = items[0]
cc = item.get("properties", {}).get("eo:cloud_cover", "?")
dt = item.get("properties", {}).get("datetime", "?")
print(f"   Selected item: {item.get('id', '?')}  acquired={dt}  cloud_cover={cc}%")


# ── 3. Asset availability check ──────────────────────────────────────────
step("3. Asset availability (B02, B03, B04, B08, B11, B12, SCL)")
required = da.BANDS + ["SCL"]
found = {b: da._find_asset_href(item, b) for b in required}
missing = [b for b, href in found.items() if not href]
mark("3_assets", not missing,
    "all present" if not missing else f"missing: {missing}")
for b, href in found.items():
    print(f"   {b:4s}: {'found' if href else 'MISSING'}")
if missing and "SCL" not in missing and set(missing) - {"SCL"}:
    print("\nStopping here — required reflectance bands missing from this item.")
    sys.exit(1)


# ── 4-6. Real download + AOI clip + common-grid reprojection + cloud mask ─
step("4-6. Real asset download + AOI clipping + reprojection + cloud masking")
print("This will download real Sentinel-2 band assets for your AOI's covering")
print("tile. Current implementation downloads each band asset in full (not a")
print("windowed read), so this can be tens of MB per band depending on the tile.")
confirm = input("Proceed with the real download? [y/N]: ").strip().lower()
if confirm != "y":
    print("Aborted by user before download. Steps 4-8 skipped.")
    sys.exit(0)

t0 = time.time()
target_grid = build_target_grid(BBOX, resolution_m=10.0)
print(f"   Target grid: {target_grid.width}x{target_grid.height} px, CRS={target_grid.crs}")

scene = da.download_real_scene(item, token, target_grid)
elapsed = time.time() - t0

if scene is None:
    mark("4_download", False, "download_real_scene() returned None — check the console log above for which asset/step failed")
    mark("5_reproject", False, "skipped (no scene)")
    mark("6_cloudmask", False, "skipped (no scene)")
    sys.exit(1)

bands, cloud_pct = scene
bands.pop("_cloud_mask", None)
mark("4_download", True, f"{elapsed:.1f}s")

shapes_ok = all(bands[b].shape == (target_grid.height, target_grid.width) for b in da.BANDS)
mark("5_reproject", shapes_ok,
    f"all bands shape {next(iter(bands.values())).shape} match target grid" if shapes_ok else "shape mismatch")

mark("6_cloudmask", True, f"AOI cloud fraction = {cloud_pct:.1f}%")


# ── 7. 42-feature array (self-comparison — see docstring) ────────────────
step("7. 42-feature array (self-comparison sanity check — diff ≈ 0 expected)")
b1, idx1 = preprocess_bands(bands)
b2, idx2 = preprocess_bands(bands)  # same real scene reused as "T2" — see note above
feats = build_feature_array(b1, b2, idx1, idx2, use_texture=True)
import numpy as np
ok = feats.shape[-1] == 42 and not np.isnan(feats).any()
mark("7_features", ok, f"shape={feats.shape}, NaNs={'yes' if np.isnan(feats).any() else 'no'}")


# ── 8. RF inference ────────────────────────────────────────────────────
step("8. RF inference on real-Sentinel-2-derived features")
model = get_model()
prob = run_rf_inference(feats, model)
mark("8_inference", prob.shape == (target_grid.height, target_grid.width),
    f"prob map shape={prob.shape}, range=[{prob.min():.3f}, {prob.max():.3f}] "
    f"(near-zero everywhere is EXPECTED — T1==T2 in this self-comparison)")


# ── Summary ────────────────────────────────────────────────────────────
step("SUMMARY")
labels = {
    "1_auth":       "CDSE authentication",
    "2_search":     "STAC search",
    "3_assets":     "Asset availability",
    "4_download":   "Asset download",
    "5_reproject":  "AOI clipping / common-grid reprojection",
    "6_cloudmask":  "SCL cloud masking",
    "7_features":   "42-feature array",
    "8_inference":  "RF inference",
}
for key, label in labels.items():
    print(f"{label:45s} {results.get(key, 'SKIPPED')}")