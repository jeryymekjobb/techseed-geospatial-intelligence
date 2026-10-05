"""The Landsat 8 scenes before, during and after the fire, for both maps.

tools/fetch_landsat_scene.py cuts three scenes - 10 June, 4 August and 14 September
2014 - into PNGs in the unversioned data/landsat/: natural colour, short-wave infrared
false colour and the moisture index NDMI, all in WGS 84 over the map area. The backend
serves them at /landsat/<file> and describes them in /api/config. The maps show the
latest scene taken up to the scenario clock; the scene after the fire is shown only
when chosen, marked as a comparison taken after it.
"""

from __future__ import annotations

import json
from typing import Any

from app.backend import scenario

LANDSAT_DIR = scenario.REPO_ROOT / "data" / "landsat"
NAMES = {
    "swir": "falska färger, kortvågig IR (band 7-5-4)",
    "natural": "naturliga färger (band 4-3-2)",
    "ndmi": "fukt i vegetationen, NDMI (band 5 och 6)",
}
ROLES = {"before": "Före branden", "during": "Under branden", "after": "Efter branden – jämförelse"}


def layer() -> dict[str, Any] | None:
    """The scenes for /api/config, or None when none has been fetched."""
    source_file = LANDSAT_DIR / "SOURCE.json"
    if not source_file.is_file():
        return None
    source = json.loads(source_file.read_text(encoding="utf-8"))
    scenes = []
    for record in source.get("scenes", []):
        images = {name: f"/landsat/{image['file']}" for name, image in record["images"].items()
                  if (LANDSAT_DIR / image["file"]).is_file()}
        if not images:
            continue
        acquired = record["acquired_utc"]
        scenes.append({
            "role": record["role"],
            "scene": record["scene"],
            "acquired_utc": acquired,
            "cloud_pct": record.get("fire_area_cloud_pct"),
            "coverage_pct": record.get("fire_area_coverage_pct"),
            "images": images,
            "label": f"{ROLES.get(record['role'], record['role'])}: Landsat 8, {acquired[:10]} {acquired[11:16]} UTC",
        })
    if not scenes:
        return None
    west, south, east, north = source["bounds_west_south_east_north"]
    return {
        "scenes": sorted(scenes, key=lambda item: item["acquired_utc"]),
        "bounds": [[south, west], [north, east]],
        "names": NAMES,
        "ndmi_colours": source.get("ndmi_colours"),
        "attribution": source["citation"],
    }


def image(name: str) -> bytes | None:
    """A PNG from data/landsat/ by its file name; None for anything else."""
    target = (LANDSAT_DIR / name).resolve()
    if not target.is_relative_to(LANDSAT_DIR.resolve()) or target.suffix != ".png" or not target.is_file():
        return None
    return target.read_bytes()
