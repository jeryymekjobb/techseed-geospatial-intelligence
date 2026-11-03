"""The latest Sentinel-1 radar pass over the area, as the scenarios show their radar acquisitions
(tools/fetch_sentinel1_scene.py), but live and without GDAL: Microsoft Planetary Computer's open STAC
catalogue gives the passes (sentinel-1-rtc, terrain-corrected, so hillsides are not bright or dark
as in the scenarios' GRD), and its data API cuts the area's VV backscatter out of each product as a
numpy array in WGS 84. Two images are made, as in the scenarios:

- the radar image in grey, the backscatter in decibels stretched between its 2nd and 98th
  percentile: rough, wet ground and buildings bright, smooth ground and water dark. It shows the
  ground's wetness only in part, together with its roughness and vegetation; it is not a measure of
  soil moisture;
- water outside the known water, in red: pixels darker than the median over OpenStreetMap's lakes,
  on at least five of the nine pixels round them. A simple computed mask, not a mapped flood: tarmac
  and radar shadows are dark too. Where the darkest land is as dark as the water (wind, rain), the
  pass is marked not separable.

Each poll asks again at most once every SEARCH_EVERY; a pass already made is not made again.
Copernicus Sentinel data are free and open; the images say so.
"""

from __future__ import annotations

import io
import json
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
              "orbit": group[0]["properties"].get("sat:orbit_state")}
             for key, group in groups.items()]
    return sorted(found, key=lambda item: item["time_utc"], reverse=True)


def array_url(item: str, bbox: tuple[float, float, float, float]) -> str:
    west, south, east, north = bbox
    width, height = round((east - west) * PIXELS_PER_DEGREE[0]), round((north - south) * PIXELS_PER_DEGREE[1])
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


class Latest:
    """The latest radar pass, kept in data/monitoring/<area>/radar-s1/ between polls and restarts."""

    def __init__(self, bbox: tuple[float, float, float, float], data_dir: Path, terrain_file: Path | None, fetch: Fetch,
                 post: sentinel2.Post = sentinel2.post_json) -> None:
        self.bbox = bbox
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

    def known_water(self, shape: tuple[int, int]) -> np.ndarray:
        if self.water is None or self.water.shape != shape:
            rings = scenario_radar.water_polygons(self.terrain_file) if self.terrain_file and self.terrain_file.is_file() else []
            self.water = scenario_radar.known_water((shape[1], shape[0]), self.bbox, rings)
        return self.water

    def update(self, now: datetime | None = None) -> dict[str, Any] | None:
        now = now or datetime.now(timezone.utc)
        if self.searched and now - self.searched < SEARCH_EVERY:
            return self.meta
        body = {"collections": [COLLECTION], "bbox": list(self.bbox), "limit": 50,
                "datetime": f"{now - RECENT:%Y-%m-%dT%H:%M:%SZ}/{now:%Y-%m-%dT%H:%M:%SZ}",
                "sortby": [{"field": "datetime", "direction": "desc"}]}
        found = passes(json.loads(self.post(sentinel2.STAC_SEARCH, body)).get("features") or [])
        self.searched = now
        if not found or (self.meta and self.meta["items"] == found[0]["items"]):
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
        self.meta = {**latest, **stats, "bbox": list(self.bbox),
                     "attribution": f"Innehåller bearbetade Copernicus Sentinel-data {latest['time_utc'][:4]} (Microsoft Planetary Computer)"}
        (self.dir / "latest.json").write_text(json.dumps(self.meta), encoding="utf-8")
        return self.meta
