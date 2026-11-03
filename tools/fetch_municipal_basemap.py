#!/usr/bin/env python3
"""Fetch the municipality's maps as base map tiles kept locally.

Each of the scenario's municipal maps (municipal_basemap.maps: Sundsvall's MUNICIPAL_BASEMAP, the layer
group Kartan of its geoserver; Västerås stad's MUNICIPAL_BASEMAPS) is fetched by WMS GetMap in Web
Mercator (EPSG:3857) over MUNICIPAL_BASEMAP_BBOX and cut into 256 px PNG tiles in the map's directory,
{z}/{x}/{y}.png, which the backend serves without
internet (app/backend/municipal_basemap.py). Each request covers 4 x 4 tiles with a margin
of MARGIN_PX, so place names are cut at fewer tile edges and the service gets a sixteenth of
the requests; PAUSE_SECONDS lies between the requests. Tiles already fetched are kept, so an
interrupted run continues where it stopped. SOURCE.json, written at the end, records the
service, the layer, the zooms, the area and the time of fetching; the backend shows the map
only once it is there. The user confirmed on 2026-10-14 that the demo may show Sundsvall's map and
keep it locally, and on 2026-10-28 that Techseed may use Västerås stad's data internally.

A map that is white outside the municipality ("white_outside" in MUNICIPAL_BASEMAP; Kartan) has its
pure white, or the colour it has there ("outside_colour"; Flens kommun's 253, 253, 253), made transparent, so the screens' OSM map shows through there; inside the municipality
Kartan has no pure white (checked on 2026-10-29 at zooms 12-16). `--clear-white` does the same to
the tiles already fetched, without asking the service.

    TECHSEED_SCENARIO=sundsvall2026 .venv/bin/python -m tools.fetch_municipal_basemap
    .venv/bin/python -m tools.fetch_municipal_basemap --area flenkommun   # the monitoring's map

A map without WMS ("kind": "arcgis", Flens kommun's Bakgrundskarta_AGOL) is asked by ArcGIS REST
export instead, with the same box and size. The user decided on 2026-11-03 that the monitoring of
Flens kommun uses the municipality's map the same way as Sundsvall's and Västerås's.
"""

from __future__ import annotations

import argparse
import io
import os
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
from PIL import Image

from app.backend import municipal_basemap, scenario

USER_AGENT = "techseed-geospatial-intelligence/0.1 (exhibition demonstrator)"
TILE_PX = 256
META = 4  # tiles per side in one request
MARGIN_PX = 64
PAUSE_SECONDS = 0.5
ATTEMPTS = 3
MIN_ZOOM = 8
MAX_ZOOM = 16
HALF_WORLD_M = 20037508.342789244
WHITE = (255, 255, 255)


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


def block_box_m(z: int, mx: int, my: int) -> tuple[float, float, float, float, int]:
    """The box in Web Mercator metres (left, bottom, right, top) of the block whose first tile is
    (mx, my), with MARGIN_PX around it, and its side in pixels."""
    left, _, _, top = tile_bounds_m(z, mx, my)
    metres_per_px = 2 * HALF_WORLD_M / 2 ** z / TILE_PX
    margin = MARGIN_PX * metres_per_px
    right = left + META * TILE_PX * metres_per_px
    bottom = top - META * TILE_PX * metres_per_px
    return left - margin, bottom - margin, right + margin, top + margin, META * TILE_PX + 2 * MARGIN_PX


def export_url(service: str, z: int, mx: int, my: int) -> str:
    """ArcGIS REST export of a MapServer for the block, for a map without WMS (Flens kommun's
    Bakgrundskarta_AGOL): the same box and size as GetMap, in Web Mercator."""
    left, bottom, right, top, side = block_box_m(z, mx, my)
    return f"{service}/export?" + urlencode({
        "bbox": f"{left},{bottom},{right},{top}", "bboxSR": 3857, "imageSR": 3857, "size": f"{side},{side}",
        "format": "png", "transparent": "false", "f": "image",
    })


def block_url(item: dict, z: int, mx: int, my: int) -> str:
    """The request for one block: ArcGIS REST export for a map of kind "arcgis", else WMS GetMap."""
    if item.get("kind") == "arcgis":
        return export_url(item["url"], z, mx, my)
    return getmap_url(item["url"], item["layer"], z, mx, my)


def getmap_url(service: str, layer: str, z: int, mx: int, my: int) -> str:
    """GetMap for the block whose first tile is (mx, my), with MARGIN_PX around it."""
    left, bottom, right, top, side = block_box_m(z, mx, my)
    return f"{service}?" + urlencode({
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap", "LAYERS": layer, "STYLES": "",
        "CRS": "EPSG:3857", "BBOX": f"{left},{bottom},{right},{top}",
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


def outside_colour(item: dict) -> tuple[int, int, int]:
    """The colour a map has outside the municipality: pure white (Sundsvall's Kartan), or the map's own
    ("outside_colour"; Flens kommun's Bakgrundskarta is 253, 253, 253 there and has pure white roads)."""
    return tuple(item.get("outside_colour", WHITE))


def clear_white(image: Image.Image, colour: tuple[int, int, int] = WHITE) -> Image.Image:
    """The image with its pixels of the colour outside the municipality (pure white) transparent."""
    pixels = np.array(image.convert("RGBA"))
    pixels[(pixels[..., :3] == colour).all(axis=-1), 3] = 0
    return Image.fromarray(pixels, "RGBA")


def clear_white_tiles(out: Path, colour: tuple[int, int, int] = WHITE) -> int:
    """Makes the colour outside the municipality of the fetched tiles transparent; returns how many tiles changed."""
    changed = 0
    for path in sorted(out.glob("*/*/*.png")):
        with Image.open(path) as opened:
            pixels = np.array(opened.convert("RGBA"))
        if not ((pixels[..., :3] == colour).all(axis=-1) & (pixels[..., 3] > 0)).any():
            continue
        part = path.with_suffix(".part")
        clear_white(Image.fromarray(pixels, "RGBA"), colour).save(part, format="PNG", optimize=True)
        os.replace(part, path)
        changed += 1
    return changed


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


def fetch_map(item: dict, bbox: tuple[float, float, float, float], min_zoom: int, max_zoom: int, pause: float) -> int:
    """Fetch one map's tiles into its directory; write its SOURCE.json once every request succeeded. The
    number of failed requests."""
    out, service, layer = item["dir"], item["url"], item.get("layer")
    white_outside = item.get("white_outside", False)
    failed = 0
    for z in range(min_zoom, max_zoom + 1):
        wanted = tile_range(bbox, z)
        blocks = meta_tiles(bbox, z)
        fetched = 0
        for mx, my in blocks:
            missing = [(x, y) for (x, y) in cut_positions(z, mx, my, wanted) if not tile_path(out, z, x, y).is_file()]
            if not missing:
                continue
            try:
                image = fetch_image(block_url(item, z, mx, my))
            except (OSError, ValueError) as exc:
                failed += 1
                print(f"{item['id']} z{z} block {mx},{my}: {exc}")
                continue
            for (x, y), piece in cut(image, z, mx, my, wanted).items():
                path = tile_path(out, z, x, y)
                path.parent.mkdir(parents=True, exist_ok=True)
                # Through a part file: a tile that exists is never asked again, so it must be whole.
                part = path.with_suffix(".part")
                (clear_white(piece, outside_colour(item)) if white_outside else piece).save(part, format="PNG", optimize=True)
                os.replace(part, path)
            fetched += 1
            time.sleep(pause)
        x0, y0, x1, y1 = wanted
        print(f"{item['id']} z{z}: {(x1 - x0 + 1) * (y1 - y0 + 1)} tiles, {fetched} of {len(blocks)} requests made now", flush=True)
    if failed:
        return failed
    (out / "SOURCE.json").write_text(json.dumps({
        "service": service, "layer": layer, "kind": item.get("kind", "wms"), "attribution": item["attribution"],
        "crs": "EPSG:3857", "tile_px": TILE_PX, "min_zoom": min_zoom, "max_zoom": max_zoom,
        "bbox_west_south_east_north": list(bbox),
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "permission": item.get("permission", "The user confirmed on 2026-10-14 that the demo may show the map and keep it locally."),
        "note": item.get("note", "Kartan draws the municipality's, Lantmäteriet's and Trafikverket's layers; white outside the municipality."),
        "white_transparent": white_outside,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--min-zoom", type=int, default=MIN_ZOOM)
    parser.add_argument("--max-zoom", type=int, default=MAX_ZOOM)
    parser.add_argument("--pause", type=float, default=PAUSE_SECONDS, help="seconds between the requests")
    parser.add_argument("--map", help="only this map's id (default: every municipal map of the scenario)")
    parser.add_argument("--clear-white", action="store_true", help="make the fetched tiles' white transparent; fetch nothing")
    parser.add_argument("--area", help="a monitoring area's map (app/monitoring/areas/) instead of the scenario's")
    parser.add_argument("--out", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    bbox = scenario.MUNICIPAL_BASEMAP_BBOX
    if args.area:
        from app.monitoring import areas

        area = areas.load(args.area)
        maps, bbox, owner = list(area.MUNICIPAL_BASEMAPS), area.MUNICIPAL_BASEMAP_BBOX, f"the area {args.area}"
    else:
        maps, owner = municipal_basemap.maps(), f"the scenario {scenario.NAME}"
    items = [item for item in maps if args.map in (None, item["id"])]
    if not items:
        parser.exit(1, f"fetch_municipal_basemap: {owner} has no municipal map {args.map or ''}\n")
    if args.out is not None:  # one map into another directory (the tests)
        items = [{**items[0], "dir": args.out}]
    if args.clear_white:
        white = [item for item in items if item.get("white_outside")]
        if not white:
            parser.exit(1, "fetch_municipal_basemap: no map of the scenario is white outside the municipality\n")
        for item in white:
            changed = clear_white_tiles(item["dir"], outside_colour(item))
            print(f"fetch_municipal_basemap: {item['id']}: {changed} tiles made transparent outside the municipality")
            record = item["dir"] / "SOURCE.json"
            if record.is_file():
                source = json.loads(record.read_text(encoding="utf-8"))
                record.write_text(json.dumps({**source, "white_transparent": True}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0
    failed = sum(fetch_map(item, bbox, args.min_zoom, args.max_zoom, args.pause) for item in items)
    if failed:
        print(f"{failed} requests failed; run again to fetch them")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
