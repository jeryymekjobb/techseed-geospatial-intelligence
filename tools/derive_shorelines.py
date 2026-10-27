#!/usr/bin/env python3
"""Derive the beaches' dune vegetation edge from each of the scenario's Sentinel-2 images.

A scenario of coastal erosion (Falsterbo 2012-2026) shows the shoreline's change year by year as
lines. A check on 2026-10-27 (the feasibility study's "Strandlinjekontroll 2026-10-27") found that
Sentinel-2's waterline mostly follows the sea level, while the edge of the vegetation behind the
beach, roughly the dune foot, moved inland after storm Babet. This tool draws that edge:

- per image, GDAL (Docker or native, as the other image tools) reads the bands B03, B04, B08 and
  the scene classification SCL over SHORELINE_AREA in the images' own UTM grid (SHORELINE_EPSG,
  10 m), so the pixels are not resampled;
- the coast of each of SHORELINE_SECTIONS is found in OpenStreetMap's water polygons clipped for
  the offline map (data/osm/<scenario>-coastline/, tools/build_offline_tiles.py), and a transect
  every TRANSECT_SPACING_DEG of longitude runs across it;
- along each transect the waterline is where NDWI (B03 - B08)/(B03 + B08) passes Otsu's threshold
  with land for the next WATERLINE_LAND_M, and the vegetation edge is where NDVI
  (B08 - B04)/(B08 + B04) then first reaches VEGETATION_NDVI;
- a point more than OUTLIER_M from its transect's median over all the images is left out (clear shallow
  water over a sandbank can pass for land in one image), and so is one that jumps more than SPIKE_M
  from both its neighbours.

The sections must face south: the coast is found by going north from the area's southern edge.
The lines go to SHORELINE_FILE as GeoJSON, one feature per image, with the method and an
uncertainty of 10-20 m (one to two pixels); data/ is not versioned. Only numpy and the Python
standard library are used.

    TECHSEED_SCENARIO=falsterbo .venv/bin/python -m tools.derive_shorelines
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from app.backend import scenario
from tools import geo_tools
from tools.build_offline_tiles import WATER_POLYGONS
from tools.fetch_landsat_scene import get_json, run_gdal, without_token
from tools.fetch_sentinel2_scene import TOKEN_URL, datatake_items, dn_for, notice

SECTIONS = scenario.SHORELINE_SECTIONS
EPSG = scenario.SHORELINE_EPSG
AREA = scenario.SHORELINE_AREA  # west, south, east, north
COASTLINE = WATER_POLYGONS.parent / f"{scenario.NAME}-coastline"
TRANSECT_SPACING_DEG = 0.0008  # about 50 m of longitude at 55° N
TRANSECT_HALF_M = 250
STEP_M = 2.0
WATERLINE_LAND_M = 40
VEGETATION_NDVI = 0.3
SPIKE_M = 30
OUTLIER_M = 40
UNCERTAINTY_M = (10, 20)
BANDS = ("B03", "B04", "B08", "SCL")
SATELLITES = {"S2A": "Sentinel-2A", "S2B": "Sentinel-2B", "S2C": "Sentinel-2C"}
LABEL = "Strandlinje (vegetationskant), härledd ur Sentinel-2 – osäkerhet ±10–20 m"
METHOD = (f"Edge where NDVI (B08-B04)/(B08+B04) reaches {VEGETATION_NDVI} landward of the NDWI waterline (Otsu's threshold), "
          f"along transects about 50 m apart across OpenStreetMap's coastline; points over {OUTLIER_M} m from the transect's median over the images and spikes over {SPIKE_M} m left out")


def utm(latitude: float, longitude: float, epsg: int = EPSG) -> tuple[float, float]:
    """WGS 84 to UTM north (EPSG 326zz) by Krüger's series, to the millimetre."""
    a, f = 6378137.0, 1 / 298.257223563
    k0, lon0 = 0.9996, math.radians(-183 + 6 * (epsg - 32600))
    n = f / (2 - f)
    big_a = a / (1 + n) * (1 + n * n / 4 + n ** 4 / 64)
    alpha = (n / 2 - 2 * n * n / 3 + 5 * n ** 3 / 16, 13 * n * n / 48 - 3 * n ** 3 / 5, 61 * n ** 3 / 240)
    phi, lam = math.radians(latitude), math.radians(longitude) - lon0
    e = math.sqrt(f * (2 - f))
    t = math.sinh(math.atanh(math.sin(phi)) - e * math.atanh(e * math.sin(phi)))
    xi, eta = math.atan2(t, math.cos(lam)), math.atanh(math.sin(lam) / math.sqrt(1 + t * t))
    x = eta + sum(alpha[j] * math.cos(2 * (j + 1) * xi) * math.sinh(2 * (j + 1) * eta) for j in range(3))
    y = xi + sum(alpha[j] * math.sin(2 * (j + 1) * xi) * math.cosh(2 * (j + 1) * eta) for j in range(3))
    return 500000 + k0 * big_a * x, k0 * big_a * y


def grid_bounds(area: Sequence[float], epsg: int = EPSG) -> tuple[int, int, int, int]:
    """The area's corners in UTM, widened to whole 10 m pixels of Sentinel-2's grid."""
    west, south, east, north = area
    corners = [utm(lat, lon, epsg) for lat in (south, north) for lon in (west, east)]
    return (math.floor(min(x for x, _ in corners) / 10) * 10, math.floor(min(y for _, y in corners) / 10) * 10,
            math.ceil(max(x for x, _ in corners) / 10) * 10, math.ceil(max(y for _, y in corners) / 10) * 10)


def polygons(collection: dict[str, Any]) -> list[list[list[list[float]]]]:
    found = []
    for feature in collection["features"]:
        geometry = feature["geometry"]
        found += [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    return found


def _in_ring(lon: float, lat: float, ring: Sequence[Sequence[float]]) -> bool:
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def in_water(lon: float, lat: float, water: Sequence) -> bool:
    return any(_in_ring(lon, lat, polygon[0]) and not any(_in_ring(lon, lat, hole) for hole in polygon[1:]) for polygon in water)


def coast(section: dict[str, Any], water: Sequence, south: float, north: float, step: float = 0.00005) -> list[tuple[float, float]]:
    """The section's coast every TRANSECT_SPACING_DEG: the first land north of the area's southern edge."""
    points = []
    count = int(round((section["east"] - section["west"]) / TRANSECT_SPACING_DEG))
    for index in range(count + 1):
        lon = section["west"] + index * TRANSECT_SPACING_DEG
        lat = south
        while lat < north and in_water(lon, lat, water):
            lat += step
        if lat < north and lat > south:
            points.append((round(lon, 6), round(lat, 6)))
    return points


def transects(points: Sequence[tuple[float, float]], water: Sequence) -> list[dict[str, float]]:
    """At each point but the ends, the unit normal to the coast in metres east and north, towards land."""
    found = []
    for index in range(1, len(points) - 1):
        lon, lat = points[index]
        metres_east = 111320.0 * math.cos(math.radians(lat))
        east = (points[index + 1][0] - points[index - 1][0]) * metres_east
        north = (points[index + 1][1] - points[index - 1][1]) * 110574.0
        length = math.hypot(east, north)
        normal_east, normal_north = -north / length, east / length
        if in_water(lon + normal_east * 100 / metres_east, lat + normal_north * 100 / 110574.0, water):
            normal_east, normal_north = -normal_east, -normal_north
        found.append({"longitude": lon, "latitude": lat, "east": normal_east, "north": normal_north})
    return found


def along(transect: dict[str, float], metres: float) -> tuple[float, float]:
    """The point `metres` along the transect from the coast (positive towards land), as longitude and latitude."""
    lat = transect["latitude"]
    return (transect["longitude"] + transect["east"] * metres / (111320.0 * math.cos(math.radians(lat))),
            lat + transect["north"] * metres / 110574.0)


def otsu(values: Any) -> float:
    """Otsu's threshold between the two classes of the values (water and land)."""
    import numpy as np

    values = np.asarray(values, dtype="f8")
    values = values[np.isfinite(values)]
    counts, edges = np.histogram(values, bins=200)
    middles = (edges[:-1] + edges[1:]) / 2
    below = np.cumsum(counts)
    above = below[-1] - below
    mean_below = np.cumsum(counts * middles) / np.maximum(below, 1)
    mean_above = (np.sum(counts * middles) - np.cumsum(counts * middles)) / np.maximum(above, 1)
    return float(middles[np.argmax(below * above * (mean_below - mean_above) ** 2)])


def edge(ndwi: Sequence[float], ndvi: Sequence[float], threshold: float, step: float = STEP_M) -> float | None:
    """The vegetation edge along one transect sampled every `step` from -TRANSECT_HALF_M: metres from its start,
    or None. The waterline is the first fall below the threshold followed by land for WATERLINE_LAND_M; the
    edge is where NDVI first reaches VEGETATION_NDVI from there, both interpolated between samples."""
    if any(math.isnan(value) for value in ndwi):
        return None
    land = int(WATERLINE_LAND_M / step)
    water = next((k for k in range(len(ndwi) - land - 1)
                  if ndwi[k] >= threshold > ndwi[k + 1] and all(value < threshold for value in ndwi[k + 1:k + 1 + land])), None)
    if water is None:
        return None
    k = next((j for j in range(water, len(ndvi) - 1) if ndvi[j] < VEGETATION_NDVI <= ndvi[j + 1]), None)
    if k is None or math.isnan(ndvi[k]) or math.isnan(ndvi[k + 1]):
        return None
    return step * (k + (VEGETATION_NDVI - ndvi[k]) / (ndvi[k + 1] - ndvi[k]))


def despike(distances: Sequence[float | None], limit: float = SPIKE_M) -> list[float | None]:
    """The distances with a point left out where it differs more than `limit` from both its neighbours."""
    kept = list(distances)
    for index in range(1, len(distances) - 1):
        value, before, after = distances[index], distances[index - 1], distances[index + 1]
        if None not in (value, before, after) and abs(value - before) > limit and abs(value - after) > limit:
            kept[index] = None
    return kept


def without_outliers(images: Sequence[Sequence[float | None]], limit: float = OUTLIER_M) -> list[list[float | None]]:
    """Each image's distances along the same transects, with those more than `limit` from the transect's median
    over the images left out."""
    kept = [list(distances) for distances in images]
    for index in range(len(images[0]) if images else 0):
        values = sorted(distances[index] for distances in images if distances[index] is not None)
        if not values:
            continue
        middle = len(values) // 2
        median = values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2
        for distances in kept:
            if distances[index] is not None and abs(distances[index] - median) > limit:
                distances[index] = None
    return kept


def pieces(points: Sequence[tuple[float, float] | None]) -> list[list[list[float]]]:
    """The points as line pieces of at least two, broken where a point is missing."""
    lines: list[list[list[float]]] = []
    current: list[list[float]] = []
    for point in [*points, None]:
        if point is None:
            if len(current) > 1:
                lines.append(current)
            current = []
        else:
            current.append([round(point[0], 6), round(point[1], 6)])
    return lines


class Grid:
    """One image's bands over the UTM bounds, sampled bilinearly at a longitude and latitude."""

    def __init__(self, folder: Path, scene: str, baseline: str, bounds: tuple[int, int, int, int], epsg: int = EPSG) -> None:
        import numpy as np

        self.west, self.south, self.east, self.north = bounds
        self.width, self.height, self.epsg = (self.east - self.west) // 10, (self.north - self.south) // 10, epsg
        read = lambda band, kind: np.fromfile(folder / f"{scene}-{band}.bil", dtype=kind).reshape(self.height, self.width)  # noqa: E731
        offset = dn_for(0.0, baseline)
        green, red, nir = (read(band, "<u2").astype("f4") - offset for band in ("B03", "B04", "B08"))
        # Only missing data is masked: SCL often takes bright beach sand for cloud, and the images are clear.
        missing = (read("SCL", "u1") <= 1) | (green + offset == 0)
        with np.errstate(divide="ignore", invalid="ignore"):
            self.ndwi = np.where(missing, np.nan, (green - nir) / (green + nir))
            self.ndvi = np.where(missing, np.nan, (nir - red) / (nir + red))

    def sample(self, grid: Any, lon: float, lat: float) -> float:
        x, y = utm(lat, lon, self.epsg)
        col, row = (x - self.west) / 10 - 0.5, (self.north - y) / 10 - 0.5
        c0, r0 = math.floor(col), math.floor(row)
        if c0 < 0 or r0 < 0 or c0 + 1 >= self.width or r0 + 1 >= self.height:
            return math.nan
        dc, dr = col - c0, row - r0
        cell = grid[r0:r0 + 2, c0:c0 + 2]
        return float(cell[0, 0] * (1 - dc) * (1 - dr) + cell[0, 1] * dc * (1 - dr) + cell[1, 0] * (1 - dc) * dr + cell[1, 1] * dc * dr)


def image_edges(grid: Grid, sections: list[list[dict[str, float]]]) -> list[float | None]:
    """The image's vegetation edge along every transect of the sections in turn: metres from the coast, or None."""
    steps = [-TRANSECT_HALF_M + STEP_M * k for k in range(int(2 * TRANSECT_HALF_M / STEP_M) + 1)]
    near = [grid.sample(grid.ndwi, *along(item, metres)) for section in sections for item in section for metres in steps[::5]]
    threshold = otsu(near)
    distances = []
    for item in (item for section in sections for item in section):
        points = [along(item, metres) for metres in steps]
        found = edge([grid.sample(grid.ndwi, *point) for point in points], [grid.sample(grid.ndvi, *point) for point in points], threshold)
        distances.append(None if found is None else found - TRANSECT_HALF_M)
    return distances


def section_lines(sections: list[list[dict[str, float]]], distances: Sequence[float | None]) -> list[list[list[float]]]:
    """One image's distances, despiked within each section, as line pieces."""
    lines, start = [], 0
    for section in sections:
        part = despike(distances[start:start + len(section)])
        lines += pieces([None if metres is None else along(item, metres) for item, metres in zip(section, part)])
        start += len(section)
    return lines


def warp_steps(urls: dict[str, list[str]], scene: str, bounds: tuple[int, int, int, int], epsg: int = EPSG) -> tuple[list[list[str]], list[str]]:
    """GDAL's steps: each band over the bounds in the UTM grid at 10 m, nearest neighbour, as raw .bil."""
    steps = []
    for band in BANDS:
        steps.append(["gdalwarp", "-q", "--config", "GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR", "-overwrite", "-t_srs", f"EPSG:{epsg}",
                      "-te", *map(str, bounds), "-tr", "10", "10", "-srcnodata", "0", "-dstnodata", "0", "-r", "near",
                      *(f"/vsicurl/{url}" for url in urls[band]), f"{scene}-{band}.tif"])
        steps.append(["gdal_translate", "-q", "-of", "EHdr", f"{scene}-{band}.tif", f"{scene}-{band}.bil"])
    return steps, [f"{scene}-*.tif", "*.aux.xml"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--out", type=Path, default=scenario.SHORELINE_FILE, help=argparse.SUPPRESS)
    geo_tools.add_argument(parser)
    args = parser.parse_args(argv)
    tools = geo_tools.choice(args.tools)
    if args.out is None or not SECTIONS or not scenario.SENTINEL2_SCENES:
        parser.exit(1, f"derive_shorelines: the scenario {scenario.NAME} has no shoreline sections or Sentinel-2 scenes\n")
    shapefile = COASTLINE / "water_polygons.shp"
    if not shapefile.is_file():
        parser.exit(1, f"derive_shorelines: {shapefile} is missing; build the offline map with the water polygons first\n")
    work = args.out.parent / "work"
    work.mkdir(parents=True, exist_ok=True)
    try:
        for part in COASTLINE.glob("water_polygons.*"):
            shutil.copy(part, work / part.name)
        run = run_gdal(([["ogr2ogr", "-f", "GeoJSON", "water.geojson", "water_polygons.shp"]], []), work, tools)
        if run.returncode != 0:
            parser.exit(1, f"derive_shorelines: GDAL could not read the coastline:\n{run.stderr[-1500:]}\n")
        water = polygons(json.loads((work / "water.geojson").read_text(encoding="utf-8")))
        sections = [transects(coast(section, water, AREA[1], AREA[3]), water) for section in SECTIONS]
        bounds = grid_bounds(AREA)
        token = get_json(TOKEN_URL)["token"]
        images = []
        for role, prefix in scenario.SENTINEL2_SCENES.items():
            items = datatake_items(prefix)
            baseline = items[0]["properties"].get("s2:processing_baseline", "05.00")
            urls = {band: [f"{item['assets'][band]['href']}?{token}" for item in items] for band in BANDS}
            run = run_gdal(warp_steps(urls, prefix, bounds), work, tools)
            if run.returncode != 0:
                parser.exit(1, f"derive_shorelines: GDAL failed for {prefix}:\n{without_token(run.stderr, token)[-1500:]}\n")
            images.append((role, prefix, items[0]["properties"]["datetime"][:19] + "Z", image_edges(Grid(work, prefix, baseline, bounds), sections)))
            for path in work.glob(f"{prefix}-*"):
                path.unlink()
    finally:
        shutil.rmtree(work, ignore_errors=True)
    features = []
    for (role, prefix, acquired, _), distances in zip(images, without_outliers([image[3] for image in images])):
        lines = section_lines(sections, distances)
        features.append({"type": "Feature", "geometry": {"type": "MultiLineString", "coordinates": lines},
                         "properties": {"role": role, "scene": prefix, "satellite": SATELLITES.get(prefix[:3], prefix[:3]),
                                        "acquired_utc": acquired}})
        print(f"{role}: {prefix}, {sum(len(line) for line in lines)} points in {len(lines)} pieces")
    args.out.write_text(json.dumps({
        "type": "FeatureCollection",
        "features": sorted(features, key=lambda feature: feature["properties"]["acquired_utc"]),
        "label": LABEL,
        "method": METHOD,
        "uncertainty_m": list(UNCERTAINTY_M),
        "sections": [section["name"] for section in SECTIONS],
        "derived": True,
        "derived_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "attribution": notice([{"acquired_utc": feature["properties"]["acquired_utc"]} for feature in features])
                       + "; coastline © OpenStreetMap contributors (ODbL)",
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
