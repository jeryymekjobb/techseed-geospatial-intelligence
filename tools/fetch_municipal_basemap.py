#!/usr/bin/env python3
"""Fetch the municipality's map as base map tiles kept locally, for the Sundsvall scenario.

The scenario's MUNICIPAL_BASEMAP (the layer group Kartan of Sundsvall's geoserver) is fetched
by WMS GetMap in Web Mercator (EPSG:3857) over MUNICIPAL_BASEMAP_BBOX and cut into 256 px
PNG tiles in MUNICIPAL_BASEMAP_DIR/{z}/{x}/{y}.png, which the backend serves without
internet (app/backend/municipal_basemap.py). Each request covers 4 x 4 tiles with a margin
of MARGIN_PX, so place names are cut at fewer tile edges and the service gets a sixteenth of
the requests; PAUSE_SECONDS lies between the requests. Tiles already fetched are kept, so an
interrupted run continues where it stopped. SOURCE.json, written at the end, records the
service, the layer, the zooms, the area and the time of fetching; the backend shows the map
only once it is there. The user confirmed on 2026-10-14 that the demo may show the map and
keep it locally.

    TECHSEED_SCENARIO=sundsvall2026 .venv/bin/python -m tools.fetch_municipal_basemap
"""

from __future__ import annotations

import argparse
import io
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image

from app.backend import scenario

USER_AGENT = "techseed-geospatial-intelligence/0.1 (exhibition demonstrator)"
TILE_PX = 256
META = 4  # tiles per side in one request
MARGIN_PX = 64
PAUSE_SECONDS = 0.5
ATTEMPTS = 3
MIN_ZOOM = 8
MAX_ZOOM = 16
HALF_WORLD_M = 20037508.342789244


def tile_range(bbox: tuple[float, float, float, float], z: int) -> tuple[int, int, int, int]:
    """The tiles (x0, y0, x1, y1, inclusive) that cover a lon/lat box (west, south, east, north) at zoom z."""
    west, south, east, north = bbox

    def column(lon: float) -> int:
        return min(2 ** z - 1, int((lon + 180.0) / 360.0 * 2 ** z))

    def row(lat: float) -> int:
        lat_rad = math.radians(lat)
        return min(2 ** z - 1, int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * 2 ** z))

    return column(west), row(north), column(east), row(south)


def tile_bounds_m(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """A tile's box in Web Mercator metres (min x, min y, max x, max y)."""
    size = 2 * HALF_WORLD_M / 2 ** z
    return -HALF_WORLD_M + x * size, HALF_WORLD_M - (y + 1) * size, -HALF_WORLD_M + (x + 1) * size, HALF_WORLD_M - y * size


def meta_tiles(bbox: tuple[float, float, float, float], z: int) -> list[tuple[int, int]]:
    """The 4 x 4 blocks (their first tile's x and y) that hold the box's tiles at zoom z."""
    x0, y0, x1, y1 = tile_range(bbox, z)
    return [(mx, my) for my in range(y0 - y0 % META, y1 + 1, META) for mx in range(x0 - x0 % META, x1 + 1, META)]


def getmap_url(service: str, layer: str, z: int, mx: int, my: int) -> str:
    """GetMap for the block whose first tile is (mx, my), with MARGIN_PX around it."""
    left, _, _, top = tile_bounds_m(z, mx, my)
    metres_per_px = 2 * HALF_WORLD_M / 2 ** z / TILE_PX
    margin = MARGIN_PX * metres_per_px
    right = left + META * TILE_PX * metres_per_px
    bottom = top - META * TILE_PX * metres_per_px
    side = META * TILE_PX + 2 * MARGIN_PX
    return f"{service}?" + urlencode({
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap", "LAYERS": layer, "STYLES": "",
        "CRS": "EPSG:3857", "BBOX": f"{left - margin},{bottom - margin},{right + margin},{top + margin}",
        "WIDTH": side, "HEIGHT": side, "FORMAT": "image/png",
    })


def cut_positions(z: int, mx: int, my: int, wanted: tuple[int, int, int, int]) -> list[tuple[int, int]]:
    """The tiles of the block whose first tile is (mx, my) inside the wanted range (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = wanted
    return [(mx + dx, my + dy) for dy in range(META) for dx in range(META) if x0 <= mx + dx <= x1 and y0 <= my + dy <= y1]


def cut(image: Image.Image, z: int, mx: int, my: int, wanted: tuple[int, int, int, int]) -> dict[tuple[int, int], Image.Image]:
    """The block's tiles inside the wanted range, by (x, y), cut out of its image."""
    tiles = {}
    for x, y in cut_positions(z, mx, my, wanted):
        left, top = MARGIN_PX + (x - mx) * TILE_PX, MARGIN_PX + (y - my) * TILE_PX
        tiles[(x, y)] = image.crop((left, top, left + TILE_PX, top + TILE_PX))
    return tiles


def tile_path(out: Path, z: int, x: int, y: int) -> Path:
    return out / str(z) / str(x) / f"{y}.png"


def fetch_image(url: str) -> Image.Image:
    for attempt in range(ATTEMPTS):
        try:
            with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=120) as response:
                body = response.read()
                if not response.headers.get("Content-Type", "").startswith("image/"):
                    raise ValueError(body[:200].decode("utf-8", "replace"))
            return Image.open(io.BytesIO(body)).convert("RGBA")
        except (OSError, ValueError):
            if attempt == ATTEMPTS - 1:
                raise
            time.sleep(5 * (attempt + 1))
    raise AssertionError("unreachable")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--min-zoom", type=int, default=MIN_ZOOM)
    parser.add_argument("--max-zoom", type=int, default=MAX_ZOOM)
    parser.add_argument("--pause", type=float, default=PAUSE_SECONDS, help="seconds between the requests")
    parser.add_argument("--out", type=Path, default=scenario.MUNICIPAL_BASEMAP_DIR, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not scenario.MUNICIPAL_BASEMAP or args.out is None:
        parser.exit(1, f"fetch_municipal_basemap: the scenario {scenario.NAME} has no municipal map\n")
    service, layer = scenario.MUNICIPAL_BASEMAP["url"], scenario.MUNICIPAL_BASEMAP["layer"]
    bbox = scenario.MUNICIPAL_BASEMAP_BBOX
    failed = 0
    for z in range(args.min_zoom, args.max_zoom + 1):
        wanted = tile_range(bbox, z)
        blocks = meta_tiles(bbox, z)
        fetched = 0
        for mx, my in blocks:
            missing = [(x, y) for (x, y) in cut_positions(z, mx, my, wanted) if not tile_path(args.out, z, x, y).is_file()]
            if not missing:
                continue
            try:
                image = fetch_image(getmap_url(service, layer, z, mx, my))
            except (OSError, ValueError) as exc:
                failed += 1
                print(f"z{z} block {mx},{my}: {exc}")
                continue
            for (x, y), piece in cut(image, z, mx, my, wanted).items():
                path = tile_path(args.out, z, x, y)
                path.parent.mkdir(parents=True, exist_ok=True)
                piece.save(path, optimize=True)
            fetched += 1
            time.sleep(args.pause)
        x0, y0, x1, y1 = wanted
        print(f"z{z}: {(x1 - x0 + 1) * (y1 - y0 + 1)} tiles, {fetched} of {len(blocks)} requests made now")
    if failed:
        print(f"{failed} requests failed; run again to fetch them")
        return 1
    (args.out / "SOURCE.json").write_text(json.dumps({
        "service": service, "layer": layer, "attribution": scenario.MUNICIPAL_BASEMAP["attribution"],
        "crs": "EPSG:3857", "tile_px": TILE_PX, "min_zoom": args.min_zoom, "max_zoom": args.max_zoom,
        "bbox_west_south_east_north": list(bbox),
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "permission": "The user confirmed on 2026-10-14 that the demo may show the map and keep it locally.",
        "note": "Kartan draws the municipality's, Lantmäteriet's and Trafikverket's layers; white outside the municipality.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
