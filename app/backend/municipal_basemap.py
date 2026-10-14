"""The municipality's map as a base map, served from the tiles kept locally.

tools/fetch_municipal_basemap.py fetches the scenario's MUNICIPAL_BASEMAP (Sundsvall's
Kartan) as Web Mercator PNG tiles into MUNICIPAL_BASEMAP_DIR/{z}/{x}/{y}.png with a
SOURCE.json. The backend serves them at /basemap/kommun/{z}/{x}/{y}.png and never asks
the municipality's service, so the map works without internet; a tile that was not
fetched is not found.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.backend import scenario

ID = "kommun"


def directory() -> Path | None:
    return scenario.MUNICIPAL_BASEMAP_DIR if scenario.MUNICIPAL_BASEMAP else None


def source() -> dict[str, Any] | None:
    """The fetch's SOURCE.json, or None when the scenario has no municipal map or it is not fetched."""
    folder = directory()
    if folder is None:
        return None
    try:
        return json.loads((folder / "SOURCE.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def layer() -> dict[str, Any] | None:
    """The base map for /api/config: its label, credit, lowest and highest fetched zoom and area
    ([[south, west], [north, east]]), or None when it cannot be shown."""
    fetched = source()
    if fetched is None:
        return None
    west, south, east, north = fetched["bbox_west_south_east_north"]
    return {"id": ID, "label": scenario.MUNICIPAL_BASEMAP["label"], "attribution": scenario.MUNICIPAL_BASEMAP["attribution"],
            "url": f"/basemap/{ID}/{{z}}/{{x}}/{{y}}.png", "min_zoom": fetched["min_zoom"], "max_zoom": fetched["max_zoom"],
            "bounds": [[south, west], [north, east]]}


def tile(z: int, x: int, y: int) -> bytes | None:
    """A fetched tile's PNG, or None when it was not fetched."""
    folder = directory()
    if folder is None or not (0 <= z <= 20 and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
        return None
    try:
        return (folder / str(z) / str(x) / f"{y}.png").read_bytes()
    except OSError:
        return None
