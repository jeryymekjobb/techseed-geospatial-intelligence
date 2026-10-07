"""SMHI's weather radar as rain images for the maps (tools/fetch_smhi_radar.py).

The frames are coloured PNGs of the map area in WGS 84, one per step of the
scenario clock; /api/config lists them and /radar/<file> serves them.
"""

from __future__ import annotations

import json
from typing import Any

from app.backend import scenario

RADAR_DIR = scenario.RADAR_DIR


def layer() -> dict[str, Any] | None:
    """The frames for /api/config, or None when the scenario has none."""
    source_file = RADAR_DIR / "SOURCE.json" if RADAR_DIR else None
    if source_file is None or not source_file.is_file():
        return None
    source = json.loads(source_file.read_text(encoding="utf-8"))
    west, south, east, north = source["bounds_west_south_east_north"]
    return {
        "bounds": [[south, west], [north, east]],
        "step_minutes": source["step_minutes"],
        "frames": [{"time_utc": item["time_utc"], "url": f"/radar/{item['file']}"} for item in source["frames"]],
        "attribution": source["attribution"],
    }


def image(name: str) -> bytes | None:
    """A frame by its file name; None for anything else."""
    if RADAR_DIR is None:
        return None
    target = (RADAR_DIR / name).resolve()
    if not target.is_relative_to(RADAR_DIR.resolve()) or target.suffix != ".png" or not target.is_file():
        return None
    return target.read_bytes()
