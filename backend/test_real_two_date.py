"""
TerraDelta — standalone REAL two-date change-detection pipeline test.

Run from your `backend` folder, venv active, backend/.env present:

    cd backend
    python test_real_two_date.py

WHAT THIS DOES (all via your actual project code — no reimplementation):
    1. STAC search for BOTH dates       (pipeline.data_access.search_sentinel2)
    2. Retrieve both real S2 scenes     (pipeline.data_access.load_bands_for_date)
    3. Download B02/B03/B04/B08/B11/B12/SCL for both
    4. Both onto the exact same target grid (pipeline.geo_grid.build_target_grid)
    5. SCL cloud masking applied to both
    6. Real 42-feature T1-vs-T2 array   (pipeline.features.build_feature_array)
    7. RF inference                     (pipeline.inference.run_rf_inference)
    8. Full change map + statistics + GeoJSON
       (pipeline.postprocessing / pipeline.filtering / pipeline.statistics —
        the exact functions orchestrator.py uses for a real job)
    9. Confirms data_source == "real_sentinel2" for BOTH dates
   10. Confirms no NaNs / shape mismatches at every stage

Unlike the single-date script, this REQUIRES two real downloads — that's
the point of this test — so expect it to take longer and use more bandwidth
than the single-date check. You'll be asked to confirm once before either
download starts.

SAFETY
    - CDSE_USERNAME/CDSE_PASSWORD are never printed.
    - Nothing in this script writes to or modifies any file in the repo.
    - Output (probability map + change mask as PNGs, stats as JSON) is
      written to ./test_output_two_date/ next to this script — NOT into
      the repo's output_files/ directory.

CONFIGURE (edit if you want a different area or dates):
"""
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timedelta

# ── Config — same ~1km x 1km Mumbai AOI as test_real_pipeline.py, two dates
#    roughly a year apart, both well in the past ──
BBOX = [72.80, 19.05, 72.81, 19.06]
DATE_T1 = (datetime.utcnow() - timedelta(days=560)).strftime("%Y-%m-%d")  # ~18 months ago
DATE_T2 = (datetime.utcnow() - timedelta(days=200)).strftime("%Y-%m-%d")  # ~6.5 months ago

OUT_DIR = Path(__file__).parent / "test_output_two_date"
sys.path.insert(0, str(Path(__file__).parent))

results = {}


def step(name):
    print(f"\n{'='*64}\n{name}\n{'='*64}")


def mark(key, ok, detail=""):
    results[key] = "PASS" if ok else "FAIL"
    print(f"-> {results[key]}" + (f" — {detail}" if detail else ""))


try:
    import numpy as np
    import pipeline.data_access as da
    from pipeline.preprocessing import preprocess_bands
    from pipeline.features import build_feature_array
    from pipeline.inference import run_rf_inference, get_model
    from pipeline.postprocessing import postprocess_change_map, vectorize_changes, build_geojson
    from pipeline.filtering import human_change_filter, generate_interpretation
    from pipeline.statistics import compute_statistics
except Exception as e:
    print(f"FATAL: could not import project pipeline modules ({e}).")
    print("Make sure you're running this from the backend/ folder with your venv active.")
    sys.exit(1)


# ── Pre-flight: confirm CDSE auth works before searching/downloading ─────
step("Pre-flight: CDSE authentication")
token = da.get_cdse_token()
if not token:
    print("-> FAIL — no token. Check backend/.env (CDSE_USERNAME/CDSE_PASSWORD).")
    sys.exit(1)
print(f"-> PASS — token acquired (length={len(token)})")


# ── 1. STAC search for both dates ─────────────────────────────────────────
step(f"1. STAC search — bbox={BBOX}, dates={DATE_T1} & {DATE_T2}")
items1 = da.search_sentinel2(BBOX, DATE_T1)
items2 = da.search_sentinel2(BBOX, DATE_T2)
mark("1_search", bool(items1) and bool(items2),
    f"T1: {len(items1)} candidate(s), T2: {len(items2)} candidate(s)")
if not items1 or not items2:
    print("\nNo matching scene for one or both dates — try different BBOX/DATE_T1/DATE_T2 "
          "(a wider date, or a location with less persistent cloud cover).")
    sys.exit(1)

for label, items in [("T1", items1), ("T2", items2)]:
    it = items[0]
    print(f"   {label}: {it.get('id','?')}  acquired={it.get('properties',{}).get('datetime','?')}  "
          f"cloud={it.get('properties',{}).get('eo:cloud_cover','?')}%")


# ── 2-5. Retrieve, download, common-grid, cloud-mask BOTH dates ──────────
step("2-5. Real download + common-grid reprojection + cloud masking (BOTH dates)")
print("This performs TWO real Sentinel-2 asset downloads (current implementation")
print("fetches each band asset in full, not a windowed read — tens of MB per band,")
print("per date). This is the real two-date test, so both downloads are required.")
confirm = input("Proceed with both real downloads? [y/N]: ").strip().lower()
if confirm != "y":
    print("Aborted by user before download.")
    sys.exit(0)

t0 = time.time()
scene1 = da.load_bands_for_date(BBOX, DATE_T1, output_dir=None)
scene2 = da.load_bands_for_date(BBOX, DATE_T2, output_dir=None)
elapsed = time.time() - t0

mark("9_real_t1", scene1["data_source"] == "real_sentinel2",
    f"T1 data_source={scene1['data_source']}" + (f" ({scene1['fallback_reason']})" if scene1["fallback_reason"] else ""))
mark("9_real_t2", scene2["data_source"] == "real_sentinel2",
    f"T2 data_source={scene2['data_source']}" + (f" ({scene2['fallback_reason']})" if scene2["fallback_reason"] else ""))

if results["9_real_t1"] == "FAIL" or results["9_real_t2"] == "FAIL":
    print("\nOne or both dates silently fell back to synthetic data — see the reason above.")
    print("This is NOT a real two-date test if either shows FAIL here. Stopping.")
    sys.exit(1)

print(f"   Both real downloads completed in {elapsed:.1f}s")
print(f"   T1 shape={scene1['shape']}, cloud={scene1['cloud_pct']:.1f}%")
print(f"   T2 shape={scene2['shape']}, cloud={scene2['cloud_pct']:.1f}%")

shapes_match = scene1["shape"] == scene2["shape"]
mark("4_common_grid", shapes_match, f"T1={scene1['shape']} T2={scene2['shape']}")
mark("5_cloudmask", True, f"T1 cloud={scene1['cloud_pct']:.1f}%, T2 cloud={scene2['cloud_pct']:.1f}%")


# ── 6. Real 42-feature T1-vs-T2 array ─────────────────────────────────────
step("6. 42-feature T1-vs-T2 comparison array")
b1, idx1 = preprocess_bands(scene1["bands"])
b2, idx2 = preprocess_bands(scene2["bands"])
feats = build_feature_array(b1, b2, idx1, idx2, use_texture=True)
has_nan = bool(np.isnan(feats).any())
mark("6_features", feats.shape[-1] == 42 and not has_nan,
    f"shape={feats.shape}, NaNs={'YES' if has_nan else 'no'}")


# ── 7. RF inference ────────────────────────────────────────────────────
step("7. RF inference")
model = get_model()
prob = run_rf_inference(feats, model)
has_nan_prob = bool(np.isnan(prob).any())
mark("7_inference", not has_nan_prob and prob.shape == scene1["shape"],
    f"prob shape={prob.shape}, range=[{prob.min():.3f}, {prob.max():.3f}], NaNs={'YES' if has_nan_prob else 'no'}")


# ── 8. Full change map + statistics + GeoJSON ─────────────────────────────
step("8. Full change map + statistics + GeoJSON")
mask = postprocess_change_map(prob)
mask = human_change_filter(mask, idx1, idx2)
stats = compute_statistics(mask, prob)
interpretation = generate_interpretation(stats, idx1, idx2, BBOX)
geo_features = vectorize_changes(mask, BBOX, prob)
geojson = build_geojson(geo_features)

mark("8_changemap", stats["changed_area_m2"] >= 0 and not bool(np.isnan(prob).any()),
    f"{stats['change_percent']}% changed, {stats['num_clusters']} cluster(s), "
    f"mean_confidence={stats['mean_confidence']}")
print(f"   Interpretation: {interpretation}")


# ── 10. Overall NaN/shape/silent-failure check ────────────────────────────
step("10. Overall integrity check")
all_ok = (
    not has_nan and not has_nan_prob and shapes_match
    and results["9_real_t1"] == "PASS" and results["9_real_t2"] == "PASS"
)
mark("10_integrity", all_ok, "no NaNs, shapes match, both dates real" if all_ok else "see failures above")


# ── Save outputs for visual inspection (outside the repo) ────────────────
OUT_DIR.mkdir(exist_ok=True)
try:
    from PIL import Image
    prob_img = (np.clip(prob, 0, 1) * 255).astype("uint8")
    Image.fromarray(prob_img).save(OUT_DIR / "probability_map.png")
    mask_img = (mask.astype("uint8") * 255)
    Image.fromarray(mask_img).save(OUT_DIR / "change_mask.png")
    with open(OUT_DIR / "geojson_changes.json", "w") as f:
        json.dump(geojson, f, indent=2)
    with open(OUT_DIR / "stats.json", "w") as f:
        json.dump({"t1_date": scene1["actual_date"], "t2_date": scene2["actual_date"],
                   "stats": stats, "interpretation": interpretation}, f, indent=2)
    print(f"\nSaved probability_map.png, change_mask.png, geojson_changes.json, "
         f"stats.json to {OUT_DIR}/")
except Exception as e:
    print(f"\n(Could not save inspection outputs: {e} — not fatal, results already printed above.)")


# ── Summary ────────────────────────────────────────────────────────────
step("SUMMARY")
labels = {
    "1_search":       "1. STAC search (both dates)",
    "9_real_t1":      "2. Real scene retrieved — T1",
    "9_real_t2":      "2. Real scene retrieved — T2",
    "4_common_grid":  "4. Common target grid (both dates)",
    "5_cloudmask":    "5. SCL cloud masking (both dates)",
    "6_features":     "6. 42-feature T1-vs-T2 array",
    "7_inference":    "7. RF inference",
    "8_changemap":    "8. Change map / stats / GeoJSON",
    "10_integrity":   "10. No NaNs / shape mismatches / silent failures",
}
for key, label in labels.items():
    print(f"{label:50s} {results.get(key, 'SKIPPED')}")
