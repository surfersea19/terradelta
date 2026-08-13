"""
Post-processing of raw probability maps into clean change masks and polygons.
Steps: threshold → morphological cleaning → small component removal → vectorization
"""
import numpy as np
import logging
from scipy import ndimage

logger = logging.getLogger(__name__)


def threshold_probability(prob_map: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    """Convert probability map to binary mask."""
    return (prob_map > threshold).astype(np.uint8)


def morphological_clean(binary: np.ndarray) -> np.ndarray:
    """
    Opening (remove isolated noise pixels) then closing (fill small holes).
    """
    opened = ndimage.binary_opening(binary, structure=np.ones((3, 3)))
    closed = ndimage.binary_closing(opened, structure=np.ones((5, 5)))
    return closed.astype(np.uint8)


def remove_small_components(binary: np.ndarray, min_pixels: int = 9) -> np.ndarray:
    """
    Remove connected components smaller than min_pixels.
    min_pixels=9 → ~900 m² at 10m resolution (below reliable detection floor).
    """
    labeled, n_labels = ndimage.label(binary)
    result = np.zeros_like(binary)
    for i in range(1, n_labels + 1):
        component_mask = labeled == i
        if component_mask.sum() >= min_pixels:
            result[component_mask] = 1
    return result


def postprocess_change_map(prob_map: np.ndarray,
                           threshold: float = 0.5,
                           min_area_pixels: int = 9) -> np.ndarray:
    """Full post-processing pipeline. Returns clean binary uint8 mask."""
    binary = threshold_probability(prob_map, threshold)
    cleaned = morphological_clean(binary)
    filtered = remove_small_components(cleaned, min_area_pixels)
    return filtered


def vectorize_changes(change_mask: np.ndarray,
                      bbox: list,
                      prob_map: np.ndarray = None) -> list:
    """
    Convert binary change mask to GeoJSON-compatible feature list.
    bbox: [lon_min, lat_min, lon_max, lat_max]
    Returns list of GeoJSON Feature dicts.
    """
    H, W = change_mask.shape
    lon_min, lat_min, lon_max, lat_max = bbox

    # Pixel size in degrees
    px_lon = (lon_max - lon_min) / W
    px_lat = (lat_max - lat_min) / H

    labeled, n_labels = ndimage.label(change_mask)
    features = []

    for label_id in range(1, n_labels + 1):
        component = labeled == label_id
        rows, cols = np.where(component)

        if len(rows) == 0:
            continue

        # Bounding box of component in pixel coords
        r_min, r_max = rows.min(), rows.max()
        c_min, c_max = cols.min(), cols.max()

        # Convert to geographic coordinates
        lon_c_min = lon_min + c_min * px_lon
        lon_c_max = lon_min + (c_max + 1) * px_lon
        lat_c_min = lat_max - (r_max + 1) * px_lat   # lat is top-to-bottom
        lat_c_max = lat_max - r_min * px_lat

        # Create a simple polygon (bounding box of cluster)
        # For real pipeline: use rasterio.features.shapes for exact outlines
        polygon_coords = [[
            [lon_c_min, lat_c_max],
            [lon_c_max, lat_c_max],
            [lon_c_max, lat_c_min],
            [lon_c_min, lat_c_min],
            [lon_c_min, lat_c_max],
        ]]

        area_pixels = int(component.sum())
        area_ha = round(area_pixels * 100 / 10000, 3)  # 100m² per pixel

        mean_conf = 0.7
        if prob_map is not None:
            vals = prob_map[component]
            mean_conf = round(float(vals.mean()), 3)

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": polygon_coords,
            },
            "properties": {
                "cluster_id": label_id,
                "area_pixels": area_pixels,
                "area_ha": area_ha,
                "confidence": mean_conf,
            }
        }
        features.append(feature)

    return features


def build_geojson(features: list) -> dict:
    """Wrap features in a GeoJSON FeatureCollection."""
    return {
        "type": "FeatureCollection",
        "features": features,
    }
