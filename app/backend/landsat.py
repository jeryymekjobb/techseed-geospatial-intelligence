"""The satellite images before, during and after the incident, for both maps.

tools/fetch_landsat_scene.py cuts the scenario's Landsat scenes - for Västmanland 10 June,
4 August and 14 September 2014 - into PNGs in its unversioned Landsat directory
(data/landsat/): natural colour, short-wave infrared false colour and the moisture index
NDMI; tools/fetch_sentinel2_scene.py adds Sentinel-2 natural colour and NDWI water, and
tools/fetch_sentinel1_scene.py Sentinel-1 radar and its computed water, for the scenarios
that have them. All are in WGS 84 over the map area. The backend serves them at
/landsat/<file>, /sentinel2/<file> and /sentinel1/<file> and describes them in /api/config. The
maps show the latest scene with the chosen image taken up to the scenario clock; a scene
in the role "after" taken later is shown only when chosen, marked as a comparison.
"""

from __future__ import annotations

import json
from typing import Any

from app.backend import scenario

LANDSAT_DIR = scenario.LANDSAT_DIR
# Sentinel-2 scenes (tools/fetch_sentinel2_scene.py), for the scenarios that have them.
SENTINEL2_DIR = scenario.SENTINEL2_DIR
SENTINEL1_DIR = scenario.SENTINEL1_DIR
NAMES = {
    "swir": "falska färger, kortvågig IR (band 7-5-4)",
    "natural": "naturliga färger",
    "ndmi": "fukt i vegetationen, NDMI (band 5 och 6)",
    "water": "vatten, NDWI (Sentinel-2; moln bortmaskade)",
    "radar": "radar (Sentinel-1, VV; ser genom moln, ej terrängkorrigerad)",
    "radarwater": "vatten i radarbilden utanför sjöar och hav (beräknat, enkel tröskel)",
}
ROLES = scenario.LANDSAT_ROLES
SATELLITES = {"LC08": "Landsat 8", "LC09": "Landsat 9", "S2A": "Sentinel-2A", "S2B": "Sentinel-2B", "S2C": "Sentinel-2C",
              "S1C": "Sentinel-1C", "S1D": "Sentinel-1D"}
ROLE_TEXTS = {**ROLES, "radar": "Radarbild"}


def _scenes(directory: Any, prefix: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """The scenes of one SOURCE.json with their images that exist, and the source record."""
    source_file = directory / "SOURCE.json" if directory else None
    if source_file is None or not source_file.is_file():
        return [], None
    source = json.loads(source_file.read_text(encoding="utf-8"))
    scenes = []
    for record in source.get("scenes", []):
        images = {name: f"/{prefix}/{image['file']}" for name, image in record["images"].items()
                  if (directory / image["file"]).is_file()}
        if not images:
            continue
        acquired = record["acquired_utc"]
        satellite = SATELLITES.get(record["scene"].split("_")[0], record["scene"].split("_")[0])
        scenes.append({
            "role": record["role"],
            "scene": record["scene"],
            "satellite": satellite,
            "acquired_utc": acquired,
            "cloud_pct": record.get("fire_area_cloud_pct", record.get("focus_area_cloud_pct")),
            "coverage_pct": record.get("fire_area_coverage_pct", record.get("focus_area_coverage_pct")),
            "images": images,
            "label": f"{ROLE_TEXTS.get(record['role'], record['role'])}: {satellite}, {acquired[:10]} {acquired[11:16]} UTC",
            # The radar's computed water: its share of the town's land, and whether water and land could be told apart.
            **({"new_water_pct": record["focus_area_new_water_pct"], "separable": record["separable"]}
               if "focus_area_new_water_pct" in record else {}),
        })
    return scenes, source


def layer() -> dict[str, Any] | None:
    """The Landsat and Sentinel-2 scenes for /api/config, or None when none has been fetched."""
    landsat_scenes, landsat_source = _scenes(LANDSAT_DIR, "landsat")
    sentinel_scenes, sentinel_source = _scenes(SENTINEL2_DIR, "sentinel2")
    radar_scenes, radar_source = _scenes(SENTINEL1_DIR, "sentinel1")
    scenes = landsat_scenes + sentinel_scenes + radar_scenes
    if not scenes:
        return None
    first = landsat_source if landsat_scenes else sentinel_source if sentinel_scenes else radar_source
    west, south, east, north = first["bounds_west_south_east_north"]
    shown = {name for scene in scenes for name in scene["images"]}
    attribution = "; ".join(text for text in [
        landsat_source.get("citation") if landsat_scenes else None,
        sentinel_source.get("notice") if sentinel_scenes else None,
        radar_source.get("notice") if radar_scenes and not sentinel_scenes else None,
    ] if text)
    return {
        "scenes": sorted(scenes, key=lambda item: item["acquired_utc"]),
        "bounds": [[south, west], [north, east]],
        "names": {name: text for name, text in NAMES.items() if name in shown},
        "ndmi_colours": landsat_source.get("ndmi_colours") if landsat_scenes else None,
        "attribution": attribution,
    }


def image(name: str, directory: Any = None) -> bytes | None:
    """A PNG from the scenario's Landsat (or the given) directory by its file name; None for anything else."""
    directory = directory or LANDSAT_DIR
    target = (directory / name).resolve()
    if not target.is_relative_to(directory.resolve()) or target.suffix != ".png" or not target.is_file():
        return None
    return target.read_bytes()
