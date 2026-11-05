"""The latest Sentinel-1 radar pass over the area, as the scenarios show their radar acquisitions
(tools/fetch_sentinel1_scene.py), but live and without GDAL: Microsoft Planetary Computer's open STAC
catalogue gives the passes (sentinel-1-rtc, terrain-corrected, so hillsides are not bright or dark
as in the scenarios' GRD), and its data API cuts the area's VV backscatter out of each product as a
numpy array in WGS 84. Two images are made, as in the scenarios:

- the radar image in grey, the backscatter in decibels stretched between its 2nd and 98th
  percentile: rough, wet ground and buildings bright, smooth ground and water dark. It shows the
  ground's wetness only in part, together with its roughness and vegetation; it is not a measure of
  soil moisture;
- water outside the known water, in red: pixels darker than the median over OpenStreetMap's lakes
  and sea (the sea from OSM's coastline water polygons, data/osm/<area>-coastline/, where built),
  on at least five of the nine pixels round them. A simple computed mask, not a mapped flood: tarmac
  and radar shadows are dark too. Where the darkest land is as dark as the water (wind, rain), the
  pass is marked not separable.

- the relative wetness of the ground, by change detection, the principle of Copernicus's soil
  moisture from Sentinel-1: each pixel's backscatter now set between how dry (its 5th percentile)
  and how wet (its 95th) the same place has been in the passes of the same relative orbit in the last
  REFERENCE days, 0 to 100 %, brown dry to blue wet, at about 100 m, smoothed over 3 x 3 of them. It is computed, not measured,
  and uncertain in forest and built-up land, where the backscatter changes little; there, and on the
  lakes and the sea, it is left out.

Each poll asks again at most once every SEARCH_EVERY; a pass already made is not made again. The
dry and wet references are kept and made again when older than REFERENCE_AGE.
Copernicus Sentinel data are free and open; the images say so.
"""

from __future__ import annotations

import io
import json
import struct
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

import numpy as np
from PIL import Image

from app.monitoring import sentinel2
from tools import fetch_sentinel1_scene as scenario_radar

COLLECTION = "sentinel-1-rtc"
DATA_API = sentinel2.DATA_API
RECENT = timedelta(days=12)
REFERENCE = timedelta(days=120)
REFERENCE_AGE = timedelta(days=30)
LOW = 5  # the wetness's pixels: 5 x 5 of the radar image's, about 100 m
MIN_PASSES = 6  # a pixel needs this many passes in its reference
MIN_RANGE_DB = 1.0  # and this much between dry and wet; less is forest, buildings or rock
# Brown dry to blue wet, as soil moisture maps are drawn.
WETNESS_COLOURS = [(0.0, (140, 81, 10)), (0.25, (216, 179, 101)), (0.5, (246, 232, 195)), (0.75, (90, 180, 172)), (1.0, (1, 102, 94))]
WETNESS_ALPHA = 200
SEARCH_EVERY = timedelta(hours=1)
PIXELS_PER_DEGREE = (1500, 3000)  # about 40 m each way at 59 N
NEIGHBOURS = scenario_radar.NEIGHBOURS
WATER_RGBA = scenario_radar.WATER_RGBA
LAND_PERCENTILE = scenario_radar.LAND_PERCENTILE

Fetch = Callable[[str], bytes]


def passes(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The products by pass (one satellite, one orbit, within minutes), newest first."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in items:
        values = item["properties"]
        groups.setdefault((item["id"][:3], values["datetime"][:13]), []).append(item)
    found = [{"time_utc": min(i["properties"]["datetime"] for i in group)[:19] + "Z", "items": [i["id"] for i in group],
              "platform": {"S1A": "Sentinel-1A", "S1B": "Sentinel-1B", "S1C": "Sentinel-1C", "S1D": "Sentinel-1D"}.get(key[0], key[0]),
              "orbit": group[0]["properties"].get("sat:orbit_state"),
              "relative_orbit": group[0]["properties"].get("sat:relative_orbit")}
             for key, group in groups.items()]
    return sorted(found, key=lambda item: item["time_utc"], reverse=True)


def array_url(item: str, bbox: tuple[float, float, float, float], scale: int = 1) -> str:
    west, south, east, north = bbox
    width = round((east - west) * PIXELS_PER_DEGREE[0]) // scale
    height = round((north - south) * PIXELS_PER_DEGREE[1]) // scale
    return (f"{DATA_API}/{west},{south},{east},{north}/{width}x{height}.npy?"
            + urlencode({"collection": COLLECTION, "item": item, "assets": "vv", "nodata": 0}))


def images(vv: np.ndarray, water: np.ndarray) -> tuple[bytes, bytes, dict[str, Any]]:
    """The grey radar image, the red water outside the known water, and the threshold and shares."""
    valid = vv > 0
    with np.errstate(divide="ignore", invalid="ignore"):
        decibels = np.where(valid, 10.0 * np.log10(np.where(valid, vv, 1.0)), np.nan)
    low, high = np.nanpercentile(decibels, [2, 98]) if valid.any() else (0.0, 1.0)
    grey = np.clip((decibels - low) / max(high - low, 1e-6) * 254 + 1, 1, 255)
    rgba = np.zeros((*vv.shape, 4), dtype="u1")
    rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = np.where(valid, grey, 0).astype("u1")
    rgba[..., 3] = np.where(valid, 255, 0)
    over_water, over_land = valid & water, valid & ~water
    threshold = float(np.nanmedian(decibels[over_water])) if over_water.any() else float(low)
    separable = bool(over_land.any()) and float(np.nanpercentile(decibels[over_land], LAND_PERCENTILE)) >= threshold
    dark = (valid & (decibels < threshold)).astype("i4")
    height, width = vv.shape
    padded = np.pad(dark, 1)
    count = sum(padded[1 + dy:1 + dy + height, 1 + dx:1 + dx + width] for dy in (-1, 0, 1) for dx in (-1, 0, 1))
    new_water = (count >= NEIGHBOURS) & (dark == 1) & ~water
    mask = np.zeros((*vv.shape, 4), dtype="u1")
    mask[new_water] = WATER_RGBA
    out_grey, out_water = io.BytesIO(), io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(out_grey, "PNG", optimize=True)
    Image.fromarray(mask, "RGBA").save(out_water, "PNG", optimize=True)
    land = valid & ~water
    return out_grey.getvalue(), out_water.getvalue(), {
        "threshold_db": round(threshold, 1), "separable": separable,
        "coverage_pct": round(100.0 * float(valid.mean()), 1),
        "new_water_pct": round(100.0 * float(new_water[land].mean()), 2) if land.any() else 0.0}


def coarse(vv: np.ndarray, scale: int = LOW) -> np.ndarray:
    """The backscatter in blocks of scale x scale pixels, their mean where all are valid."""
    height, width = (vv.shape[0] // scale) * scale, (vv.shape[1] // scale) * scale
    blocks = vv[:height, :width].reshape(height // scale, scale, width // scale, scale)
    valid = (blocks > 0).all(axis=(1, 3))
    return np.where(valid, blocks.mean(axis=(1, 3)), 0.0).astype("f4")


def decibels(vv: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(vv > 0, 10.0 * np.log10(np.where(vv > 0, vv, 1.0)), np.nan)


def wetness(now_db: np.ndarray, dry: np.ndarray, wet: np.ndarray, count: np.ndarray, water: np.ndarray) -> tuple[bytes, dict[str, Any]]:
    """The relative wetness as a PNG, brown dry to blue wet, and its median over the land it covers."""
    usable = np.isfinite(now_db) & (count >= MIN_PASSES) & ((wet - dry) >= MIN_RANGE_DB) & ~water
    raw = np.where(usable, np.clip((now_db - dry) / np.where(usable, wet - dry, 1.0), 0.0, 1.0), 0.0)
    # The radar's speckle: each pixel the mean of the usable ones of the 3 x 3 round it, about 300 m.
    height, width = raw.shape
    padded, weights = np.pad(raw, 1), np.pad(usable.astype("f4"), 1)
    total = sum(padded[1 + dy:1 + dy + height, 1 + dx:1 + dx + width] for dy in (-1, 0, 1) for dx in (-1, 0, 1))
    count_near = sum(weights[1 + dy:1 + dy + height, 1 + dx:1 + dx + width] for dy in (-1, 0, 1) for dx in (-1, 0, 1))
    share = np.where(usable, total / np.maximum(count_near, 1.0), 0.0)
    stops = np.array([stop for stop, _ in WETNESS_COLOURS])
    rgba = np.zeros((*now_db.shape, 4), dtype="u1")
    for channel in range(3):
        rgba[..., channel] = np.interp(share, stops, [colour[channel] for _, colour in WETNESS_COLOURS]).astype("u1")
    rgba[..., 3] = np.where(usable, WETNESS_ALPHA, 0)
    out = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(out, "PNG", optimize=True)
    return out.getvalue(), {"wetness_median_pct": round(100.0 * float(np.median(share[usable])), 0) if usable.any() else None,
                            "wetness_cover_pct": round(100.0 * float(usable.mean()), 0)}


def sea_polygons(shapefile: Path) -> list[list[list[list[float]]]]:
    """OpenStreetMap's sea from a clipped water_polygons.shp (tools/build_offline_tiles.py), each
    polygon as its rings of [lon, lat]: the shapefile's polygons (type 5) read without GDAL. A ring
    turning clockwise is the sea's edge, one turning anticlockwise an island in it."""
    data = shapefile.read_bytes()
    polygons, at = [], 100
    while at + 8 <= len(data):
        length = struct.unpack(">i", data[at + 4:at + 8])[0] * 2
        record = data[at + 8:at + 8 + length]
        at += 8 + length
        if len(record) < 44 or struct.unpack("<i", record[:4])[0] != 5:
            continue
        parts, count = struct.unpack("<2i", record[36:44])
        starts = list(struct.unpack(f"<{parts}i", record[44:44 + 4 * parts])) + [count]
        points = np.frombuffer(record, "<f8", count * 2, 44 + 4 * parts).reshape(count, 2)
        polygons.append([points[a:b].tolist() for a, b in zip(starts, starts[1:])])
    return polygons


def sea_mask(size: tuple[int, int], bbox: tuple[float, float, float, float], polygons: list[list[list[list[float]]]]) -> np.ndarray:
    """The sea as a mask over the image (width, height), its islands left out."""
    from PIL import ImageDraw

    west, south, east, north = bbox
    width, height = size
    image = Image.new("1", size, 0)
    draw = ImageDraw.Draw(image)
    for rings in polygons:
        for ring in sorted(rings, key=lambda ring: _clockwise(ring), reverse=True):  # the edges first, then the islands
            draw.polygon([((lon - west) / (east - west) * width, (north - lat) / (north - south) * height) for lon, lat in ring],
                         fill=1 if _clockwise(ring) else 0)
    return np.array(image, dtype=bool)


def _clockwise(ring: list[list[float]]) -> bool:
    return sum((x2 - x1) * (y2 + y1) for (x1, y1), (x2, y2) in zip(ring, ring[1:])) > 0


class Latest:
    """The latest radar pass, kept in data/monitoring/<area>/radar-s1/ between polls and restarts."""

    def __init__(self, bbox: tuple[float, float, float, float], data_dir: Path, terrain_file: Path | None, fetch: Fetch,
                 post: sentinel2.Post = sentinel2.post_json, sea_file: Path | None = None) -> None:
        self.bbox = bbox
        self.sea_file = sea_file
        self.dir = data_dir / "radar-s1"
        self.terrain_file = terrain_file
        self.fetch = fetch
        self.post = post
        self.searched: datetime | None = None
        self.water: np.ndarray | None = None
        try:
            self.meta: dict[str, Any] | None = json.loads((self.dir / "latest.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.meta = None

    def png(self, name: str) -> bytes | None:
        try:
            return (self.dir / f"{name}.png").read_bytes()
        except OSError:
            return None

    def _rings(self) -> list[list[list[float]]]:
        return scenario_radar.water_polygons(self.terrain_file) if self.terrain_file and self.terrain_file.is_file() else []

    def known_water(self, shape: tuple[int, int]) -> np.ndarray:
        if self.water is None or self.water.shape != shape:
            self.water = self._water(shape)
        return self.water

    def _water(self, shape: tuple[int, int]) -> np.ndarray:
        """The lakes and, where the area has its coastline, the sea, over an image of the shape."""
        water = scenario_radar.known_water((shape[1], shape[0]), self.bbox, self._rings())
        if self.sea_file and self.sea_file.is_file():
            water |= sea_mask((shape[1], shape[0]), self.bbox, sea_polygons(self.sea_file))
        return water

    def reference(self, orbit: int | None, now: datetime) -> dict[str, Any] | None:
        """How dry and how wet each coarse pixel has been in the passes of the relative orbit in the
        last REFERENCE days, kept in reference-<orbit>.npz and made again when older than REFERENCE_AGE."""
        if orbit is None:
            return None
        path = self.dir / f"reference-{orbit}.npz"
        try:
            kept = dict(np.load(path))
            if now - datetime.fromisoformat(str(kept["made_utc"])) < REFERENCE_AGE:
                return kept
        except (OSError, ValueError, KeyError):
            pass
        body = {"collections": [COLLECTION], "bbox": list(self.bbox), "limit": 250,
                "datetime": f"{now - REFERENCE:%Y-%m-%dT%H:%M:%SZ}/{now:%Y-%m-%dT%H:%M:%SZ}"}
        found = [item for item in passes(json.loads(self.post(sentinel2.STAC_SEARCH, body)).get("features") or [])
                 if item.get("relative_orbit") == orbit]
        stack = []
        for take in found:
            low = None
            for item in take["items"]:
                part = np.load(io.BytesIO(self.fetch(array_url(item, self.bbox, LOW))))[0].astype("f4")
                low = part if low is None else np.where(part > 0, part, low)
            if low is not None:
                stack.append(decibels(low))
        if len(stack) < MIN_PASSES:
            return None
        cube = np.stack(stack)
        # Blocks no pass covered (the sea, outside the swaths) stay NaN, as the wetness expects, without a warning.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            dry, wet = np.nanpercentile(cube, 5, axis=0), np.nanpercentile(cube, 95, axis=0)
        reference = {"dry": dry, "wet": wet,
                     "count": np.isfinite(cube).sum(axis=0), "passes": np.array(len(stack)),
                     "made_utc": np.array(now.isoformat())}
        self.dir.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **reference)
        return reference

    def update(self, now: datetime | None = None) -> dict[str, Any] | None:
        now = now or datetime.now(timezone.utc)
        if self.searched and now - self.searched < SEARCH_EVERY:
            return self.meta
        body = {"collections": [COLLECTION], "bbox": list(self.bbox), "limit": 50,
                "datetime": f"{now - RECENT:%Y-%m-%dT%H:%M:%SZ}/{now:%Y-%m-%dT%H:%M:%SZ}",
                "sortby": [{"field": "datetime", "direction": "desc"}]}
        found = passes(json.loads(self.post(sentinel2.STAC_SEARCH, body)).get("features") or [])
        self.searched = now
        # A pass made before the sea was known water (2026-11-05) is made again.
        if not found or (self.meta and self.meta["items"] == found[0]["items"] and self.meta.get("sea_known")):
            return self.meta
        latest = found[0]
        vv = None
        for item in latest["items"]:
            part = np.load(io.BytesIO(self.fetch(array_url(item, self.bbox))))[0].astype("f4")
            vv = part if vv is None else np.where(part > 0, part, vv)
        grey, water, stats = images(vv, self.known_water(vv.shape))
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "radar.png").write_bytes(grey)
        (self.dir / "water.png").write_bytes(water)
        reference = self.reference(latest.get("relative_orbit"), now)
        if reference is not None:
            low = coarse(vv)
            lakes = self._water(low.shape)
            png, wet_stats = wetness(decibels(low), reference["dry"], reference["wet"], reference["count"], lakes)
            (self.dir / "wetness.png").write_bytes(png)
            stats = {**stats, **wet_stats, "wetness_passes": int(reference["passes"])}
        self.meta = {**latest, **stats, "bbox": list(self.bbox), "sea_known": True,
                     "attribution": f"Innehåller bearbetade Copernicus Sentinel-data {latest['time_utc'][:4]} (Microsoft Planetary Computer)"}
        (self.dir / "latest.json").write_text(json.dumps(self.meta), encoding="utf-8")
        return self.meta
