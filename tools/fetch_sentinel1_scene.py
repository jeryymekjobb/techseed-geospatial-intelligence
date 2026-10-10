#!/usr/bin/env python3
"""Cut the scenario's Sentinel-1 radar acquisitions over its map area into images.

For each of the scenario's SENTINEL1_ACQUISITIONS the products of that pass over the map
area (Level-1 GRD, the VV channel; Microsoft Planetary Computer's open STAC catalogue,
sentinel-1-grd, with the anonymous access token its API hands out) are warped to WGS 84
with their ground control points by GDAL in Docker, averaged to about 20 m. Per
acquisition it writes two PNGs:

- the radar image in grey (the amplitude in decibels, stretched between the 2nd and 98th
  percentile of the area); it is not terrain-corrected, so hillsides are a little bright
  or dark and slightly shifted;
- water outside the known water: open water returns little radar, so the image's dark
  pixels are water. The known water is the lakes of OpenStreetMap and the sea, where the
  Copernicus DEM is at sea level. The threshold is the scene's own: the median amplitude
  over the known water, so a pixel counts only if it is as dark as typical open water.
  Pixels darker than it, on at least five of the nine pixels round them and outside the
  known water, are shown red. This is a simple computed mask, not a mapped flood:
  smooth surfaces such as tarmac and radar shadows behind hills are dark as well.
  Where the darkest land (its 5th percentile) is darker than the threshold - wind on the
  water or rain on the ground - the scene is marked not separable and its mask uncertain.

The tool reports the share of the focus area's land the mask covers. The radar is not
calibrated, which the per-scene threshold does not need. Copernicus Sentinel data are
free and open (the Sentinel Data Legal Notice); SOURCE.json records the products, the
threshold and the notice. Numpy and Pillow from the .venv.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from app.backend import scenario
from tools.fetch_landsat_scene import GDAL_IMAGE, STAC, USER_AGENT, docker_command, get_json, user, without_token
from tools.fetch_sentinel2_scene import focus_rows_cols

COLLECTION = "sentinel-1-grd"
TOKEN_URL = f"https://planetarycomputer.microsoft.com/api/sas/v1/token/{COLLECTION}"
SENTINEL1_DIR = scenario.SENTINEL1_DIR
ACQUISITIONS = scenario.SENTINEL1_ACQUISITIONS
BBOX = scenario.MAP_BBOX
SIZE = scenario.SENTINEL2_SIZE  # about 20 m, as the Sentinel-2 images
FOCUS_AREA = scenario.LANDSAT_FOCUS_AREA
SEA_LEVEL_M = 0.5  # the DEM's sea, as known water
LAND_PERCENTILE = 5.0
NEIGHBOURS = 5  # of the 3 x 3 pixels round a pixel, at least this many dark
WATER_RGBA = (255, 0, 0, 220)
NOTICE = (f"Contains modified Copernicus Sentinel data {scenario.PERIOD_START.year}, processed by Techseed "
          "(Planetary Computer, sentinel-1-grd)")
LICENCE = "https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice (free and open)"


def scene_key(acquisition: dict[str, str]) -> str:
    """The acquisition's name in the files: satellite and time, for example S1C_20260816T052132."""
    unit = acquisition["satellite"].replace("Sentinel-", "S")
    return f"{unit}_{acquisition['time_utc'][:19].replace('-', '').replace(':', '')}"


def post_json(url: str, body: dict[str, Any]) -> dict[str, Any]:
    request = Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def pass_items(acquisition: dict[str, str]) -> list[dict]:
    """The products of the pass over the map area: the same orbit, within two minutes of the acquisition."""
    moment = datetime.fromisoformat(acquisition["time_utc"].replace("Z", "+00:00"))
    body = {"collections": [COLLECTION], "bbox": list(BBOX), "limit": 20,
            "datetime": f"{(moment - timedelta(minutes=2)):%Y-%m-%dT%H:%M:%SZ}/{(moment + timedelta(minutes=2)):%Y-%m-%dT%H:%M:%SZ}"}
    items = post_json(f"{STAC}/search", body)["features"]
    if not items:
        raise RuntimeError(f"no {COLLECTION} product at {acquisition['time_utc']} over the map area")
    return sorted(items, key=lambda item: item["id"])


def warp_script(urls: list[str], key: str, bbox: tuple[float, ...] = BBOX, size: tuple[int, int] = SIZE) -> str:
    """Shell script for the GDAL container: the products' VV warped with their GCPs and averaged, as raw rows."""
    west, south, east, north = bbox
    sources = " ".join(f"'/vsicurl/{url}'" for url in urls)
    return "\n".join([
        "set -e", "cd /data",
        f"gdalwarp -q --config GDAL_DISABLE_READDIR_ON_OPEN EMPTY_DIR -overwrite -tps -t_srs EPSG:4326 -te {west} {south} {east} {north} "
        f"-ts {size[0]} {size[1]} -r average -srcnodata 0 -dstnodata 0 -ot UInt16 {sources} vv.tif",
        f"gdal_translate -q -of EHdr vv.tif {key}-vv.bil",
        "rm -f vv.tif *.aux.xml",
    ])


def known_water(size: tuple[int, int], bbox: tuple[float, ...], polygons: list[list[list[float]]]) -> Any:
    """The lakes and sea of OpenStreetMap as a mask over the image (rings of [lon, lat])."""
    import numpy as np
    from PIL import Image, ImageDraw

    west, south, east, north = bbox
    width, height = size
    image = Image.new("1", size, 0)
    draw = ImageDraw.Draw(image)
    for ring in polygons:
        draw.polygon([((lon - west) / (east - west) * width, (north - lat) / (north - south) * height) for lon, lat in ring], fill=1)
    return np.array(image, dtype=bool)


def dem_script(tiles: list[str], bbox: tuple[float, ...] = BBOX, size: tuple[int, int] = SIZE) -> str:
    """Shell script for the GDAL container: the DEM on the images' grid, as raw rows."""
    west, south, east, north = bbox
    inputs = " ".join(f"/dem/{name}" for name in tiles)
    return "\n".join([
        "set -e", "cd /data",
        f"gdalwarp -q -overwrite -t_srs EPSG:4326 -te {west} {south} {east} {north} -ts {size[0]} {size[1]} -r average -ot Float32 {inputs} dem.tif",
        "gdal_translate -q -of EHdr dem.tif dem.bil",
        "rm -f dem.tif *.aux.xml",
    ])


def sea(out: Path, dem_dir: Path, size: tuple[int, int] = SIZE) -> Any:
    """Where the Copernicus DEM is at sea level on the images' grid."""
    import numpy as np

    tiles = sorted(path.name for path in dem_dir.glob("*.tif"))
    command = ["docker", "run", "--rm", "-u", user(), "-v", f"{out.resolve()}:/data", "-v", f"{dem_dir.resolve()}:/dem:ro",
               GDAL_IMAGE, "sh", "-c", dem_script(tiles)]
    run = subprocess.run(command, capture_output=True, text=True)
    if run.returncode != 0:
        raise RuntimeError(f"GDAL failed for the DEM:\n{run.stderr[-2000:]}")
    width, height = size
    heights = np.fromfile(out / "dem.bil", dtype="<f4").reshape(height, width)
    for suffix in (".bil", ".hdr", ".prj", ".bil.aux.xml"):
        (out / f"dem{suffix}").unlink(missing_ok=True)
    return heights <= SEA_LEVEL_M


def water_polygons(terrain_file: Path) -> list[list[list[float]]]:
    """The outer rings of OpenStreetMap's water in the scenario's terrain layer."""
    rings = []
    for feature in json.loads(terrain_file.read_text(encoding="utf-8"))["features"]:
        if feature["properties"].get("terrain") != "vatten":
            continue
        geometry = feature["geometry"]
        polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
        rings += [polygon[0] for polygon in polygons]
    return rings


def radar_images(out: Path, key: str, water: Any, size: tuple[int, int] = SIZE,
                 bbox: tuple[float, ...] = BBOX, focus: tuple[float, ...] = FOCUS_AREA) -> dict[str, Any]:
    """Write the grey radar image and the water mask; return the threshold and the focus area's shares."""
    import numpy as np
    from PIL import Image

    width, height = size
    amplitude = np.fromfile(out / f"{key}-vv.bil", dtype="<u2").reshape(height, width).astype("f4")
    valid = amplitude > 0
    with np.errstate(divide="ignore"):
        decibels = np.where(valid, 20.0 * np.log10(np.maximum(amplitude, 1.0)), np.nan)
    low, high = np.nanpercentile(decibels, [2, 98])
    grey = np.clip((decibels - low) / (high - low) * 254 + 1, 1, 255)
    rgba = np.zeros((height, width, 4), dtype="u1")
    rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = np.where(valid, grey, 0).astype("u1")
    rgba[..., 3] = np.where(valid, 255, 0)
    Image.fromarray(rgba, "RGBA").save(out / f"{key}-radar.png", optimize=True)

    over_water = valid & water
    over_land = valid & ~water
    threshold = float(np.nanmedian(decibels[over_water])) if over_water.any() else float(low)
    # Wind on the water or rain on the ground: the darkest land is as dark as the water, so dark is not water.
    separable = bool(over_land.any()) and float(np.nanpercentile(decibels[over_land], LAND_PERCENTILE)) >= threshold
    dark = (valid & (decibels < threshold)).astype("i4")
    # How many of the 3 x 3 pixels round each pixel are dark: one pixel of speckle is not water.
    padded = np.pad(dark, 1)
    count = sum(padded[1 + dy:1 + dy + height, 1 + dx:1 + dx + width] for dy in (-1, 0, 1) for dx in (-1, 0, 1))
    new_water = (count >= NEIGHBOURS) & (dark == 1) & ~water
    mask = np.zeros((height, width, 4), dtype="u1")
    mask[new_water] = WATER_RGBA
    Image.fromarray(mask, "RGBA").save(out / f"{key}-radarwater.png", optimize=True)

    rows, cols = focus_rows_cols(size, bbox, focus)
    land = valid[rows, cols] & ~water[rows, cols]
    return {
        "threshold_db": round(threshold, 1),
        "separable": separable,
        "focus_area_coverage_pct": round(100.0 * float(valid[rows, cols].mean()), 1),
        "focus_area_new_water_pct": round(100.0 * float(new_water[rows, cols][land].mean()), 2) if land.any() else 0.0,
    }


def process(acquisition: dict[str, str], token: str, out: Path, water: Any) -> dict[str, Any]:
    key = scene_key(acquisition)
    items = pass_items(acquisition)
    urls = [f"{item['assets']['vv']['href']}?{token}" for item in items]
    run = subprocess.run(docker_command(warp_script(urls, key), out), capture_output=True, text=True)
    if run.returncode != 0:
        raise RuntimeError(f"GDAL failed for {key}:\n{without_token(run.stderr, token)[-2000:]}")
    stats = radar_images(out, key, water)
    for suffix in (".bil", ".hdr", ".prj", ".bil.aux.xml"):
        (out / f"{key}-vv{suffix}").unlink(missing_ok=True)
    return {
        "role": "radar", "scene": key, "satellite": acquisition["satellite"], "acquired_utc": acquisition["time_utc"],
        "products": [item["id"] for item in items], **stats,
        "images": {
            "radar": {"file": f"{key}-radar.png", "bands": "VV, 20 log10(DN), 2-98 %"},
            "radarwater": {"file": f"{key}-radarwater.png",
                           "bands": "VV darker than the median over the known water (OSM lakes, DEM sea), outside it"},
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--out", type=Path, default=SENTINEL1_DIR, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not ACQUISITIONS or args.out is None:
        parser.exit(1, f"fetch_sentinel1_scene: the scenario {scenario.NAME} has no Sentinel-1 acquisitions\n")
    token = get_json(TOKEN_URL)["token"]
    args.out.mkdir(parents=True, exist_ok=True)
    water = known_water(SIZE, BBOX, water_polygons(scenario.TERRAIN_FILE)) | sea(args.out, scenario.DEM_DIR)
    records = []
    for acquisition in ACQUISITIONS:
        try:
            record = process(acquisition, token, args.out, water)
        except RuntimeError as exc:
            parser.exit(1, f"fetch_sentinel1_scene: {exc}\n")
        records.append(record)
        print(f"{record['scene']} ({len(record['products'])} produkter) – data över {record['focus_area_coverage_pct']} % av "
              f"fokusområdet, tröskel {record['threshold_db']} dB, vatten utanför sjöar och hav {record['focus_area_new_water_pct']} %"
              + ("" if record["separable"] else " – OSÄKER: vatten och land skiljs dåligt åt"))
    west, south, east, north = BBOX
    (args.out / "SOURCE.json").write_text(json.dumps({
        "scenes": records,
        "bounds_west_south_east_north": [west, south, east, north],
        "size_px": list(SIZE),
        "processed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "processing": (
            "gdalwarp with the products' GCPs (thin plate spline) to EPSG:4326, averaged; not terrain-corrected; "
            f"water: darker than the median over OSM lakes and the DEM's sea, {NEIGHBOURS} of 9 neighbours, shown red; "
            f"not separable where the {LAND_PERCENTILE:.0f}th percentile of land is darker"
        ),
        "notice": NOTICE,
        "licence": LICENCE,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
