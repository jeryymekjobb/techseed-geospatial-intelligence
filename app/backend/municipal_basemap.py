"""The municipality's maps as base maps, served from the tiles kept locally.

tools/fetch_municipal_basemap.py fetches each of the scenario's municipal maps (Sundsvall's Kartan
as MUNICIPAL_BASEMAP; Västerås stad's map, grey map and aerial photo as MUNICIPAL_BASEMAPS) as Web
Mercator PNG tiles into its directory, {z}/{x}/{y}.png with a SOURCE.json. The backend serves them at
/basemap/<id>/{z}/{x}/{y}.png and never asks the municipality's service, so the maps work without
internet; a tile that was not fetched is not found.
"""

from __future__ import annotations

import json
from typing import Any

from app.backend import scenario

ID = "kommun"  # the id of a scenario's single MUNICIPAL_BASEMAP


def maps() -> list[dict[str, Any]]:
    """The scenario's municipal maps, each with its id and directory: MUNICIPAL_BASEMAPS, else the single
    MUNICIPAL_BASEMAP in MUNICIPAL_BASEMAP_DIR."""
    if scenario.MUNICIPAL_BASEMAPS:
        return list(scenario.MUNICIPAL_BASEMAPS)
    if scenario.MUNICIPAL_BASEMAP:
        return [{**scenario.MUNICIPAL_BASEMAP, "id": ID, "dir": scenario.MUNICIPAL_BASEMAP_DIR}]
    return []


def find(map_id: str) -> dict[str, Any] | None:
    return next((item for item in maps() if item["id"] == map_id), None)


def source(map_id: str = ID) -> dict[str, Any] | None:
    """The map's SOURCE.json, or None when the scenario has no such map or it is not fetched."""
    item = find(map_id)
    if item is None or item["dir"] is None:
        return None
    try:
        return json.loads((item["dir"] / "SOURCE.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def layers() -> list[dict[str, Any]]:
    """The fetched maps for /api/config: each one's label, credit, lowest and highest fetched zoom, area
    ([[south, west], [north, east]]) and whether it carries place names of its own (an aerial photo does not)."""
    result = []
    for item in maps():
        fetched = source(item["id"])
        if fetched is None:
            continue
        west, south, east, north = fetched["bbox_west_south_east_north"]
        result.append({"id": item["id"], "label": item["label"], "attribution": item["attribution"],
                       "url": f"/basemap/{item['id']}/{{z}}/{{x}}/{{y}}.png", "min_zoom": fetched["min_zoom"],
                       "max_zoom": fetched["max_zoom"], "bounds": [[south, west], [north, east]],
                       "names": item.get("names", True)})
    return result


def layer() -> dict[str, Any] | None:
    """The first fetched map, as /api/config's municipal_basemap, or None."""
    fetched = layers()
    if not fetched:
        return None
    return {key: value for key, value in fetched[0].items() if key != "names"}


def tile(z: int, x: int, y: int, map_id: str = ID) -> bytes | None:
    """A fetched tile's PNG, or None when it was not fetched."""
    item = find(map_id)
    if item is None or item["dir"] is None or not (0 <= z <= 20 and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
        return None
    try:
        return (item["dir"] / str(z) / str(x) / f"{y}.png").read_bytes()
    except OSError:
        return None
