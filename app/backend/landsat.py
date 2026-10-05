"""The Landsat 8 scene of 4 August 2014 over the fire, for both maps.

tools/fetch_landsat_scene.py cuts it into two PNGs in the unversioned
data/landsat/ (natural colour and short-wave infrared false colour, WGS 84). The
backend serves them at /landsat/<file> and describes them in /api/config; the
maps show the image only from the moment it was taken, at the scenario clock.
"""

from __future__ import annotations

import json
from typing import Any

from app.backend import scenario

LANDSAT_DIR = scenario.REPO_ROOT / "data" / "landsat"
NAMES = {"natural": "naturliga färger (band 4-3-2)", "swir": "falska färger, kortvågig IR (band 7-5-4)"}


def layer() -> dict[str, Any] | None:
    """The scene for /api/config, or None when it has not been fetched."""
    source_file = LANDSAT_DIR / "SOURCE.json"
    if not source_file.is_file():
        return None
    source = json.loads(source_file.read_text(encoding="utf-8"))
    images = {name: f"/landsat/{image['file']}" for name, image in source["images"].items()
              if (LANDSAT_DIR / image["file"]).is_file()}
    if not images:
        return None
    west, south, east, north = source["bounds_west_south_east_north"]
    return {
        "scene": source["scene"],
        "acquired_utc": source["acquired_utc"],
        "cloud_cover_pct": source.get("cloud_cover_pct"),
        "bounds": [[south, west], [north, east]],
        "images": images,
        "names": {name: NAMES.get(name, name) for name in images},
        "label": f"Landsat 8 OLI {source['acquired_utc'][:10]} {source['acquired_utc'][11:16]} UTC – riktig satellitbild",
        "attribution": source["citation"],
    }


def image(name: str) -> bytes | None:
    """A PNG from data/landsat/ by its file name; None for anything else."""
    target = (LANDSAT_DIR / name).resolve()
    if not target.is_relative_to(LANDSAT_DIR.resolve()) or target.suffix != ".png" or not target.is_file():
        return None
    return target.read_bytes()
