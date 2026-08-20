"""
Common target grid computation for real Sentinel-2 retrieval.

Two acquisitions of the same AOI can come from different tiles/orbits with
slightly different footprints and native CRS. Before differencing T1/T2 we
need both reprojected onto ONE fixed pixel grid — same CRS, same transform,
same shape — otherwise per-pixel differencing is meaningless.

This module defines that grid: local UTM zone (metric, so "10m pixels" is
literal), 10m resolution, centered on the AOI bbox.
"""
import logging
import math
from dataclasses import dataclass

from affine import Affine
from pyproj import CRS, Transformer

logger = logging.getLogger(__name__)


@dataclass
class TargetGrid:
    crs: CRS
    transform: Affine
    width: int
    height: int
    bbox_wgs84: list  # original [lon_min, lat_min, lon_max, lat_max]


def utm_epsg_for_lonlat(lon: float, lat: float) -> int:
    """Return the EPSG code of the UTM zone containing (lon, lat)."""
    zone = int(math.floor((lon + 180) / 6) % 60) + 1
    return (32600 if lat >= 0 else 32700) + zone


def build_target_grid(bbox: list, resolution_m: float = 10.0) -> TargetGrid:
    """
    bbox: [lon_min, lat_min, lon_max, lat_max] in WGS84 (EPSG:4326).
    Returns a TargetGrid covering the bbox in the local UTM CRS at a fixed
    pixel size, so multiple dates can be reprojected onto identical arrays.
    """
    lon_min, lat_min, lon_max, lat_max = bbox
    cx, cy = (lon_min + lon_max) / 2, (lat_min + lat_max) / 2

    epsg = utm_epsg_for_lonlat(cx, cy)
    utm_crs = CRS.from_epsg(epsg)

    transformer = Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
    x_min, y_min = transformer.transform(lon_min, lat_min)
    x_max, y_max = transformer.transform(lon_max, lat_max)
    x_min, x_max = min(x_min, x_max), max(x_min, x_max)
    y_min, y_max = min(y_min, y_max), max(y_min, y_max)

    width = max(1, int(round((x_max - x_min) / resolution_m)))
    height = max(1, int(round((y_max - y_min) / resolution_m)))

    transform = Affine.translation(x_min, y_max) * Affine.scale(resolution_m, -resolution_m)

    logger.info(f"Target grid: EPSG:{epsg}, {width}x{height} px @ {resolution_m}m")
    return TargetGrid(crs=utm_crs, transform=transform, width=width, height=height,
                       bbox_wgs84=bbox)
