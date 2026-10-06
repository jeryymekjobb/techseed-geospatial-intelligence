#!/usr/bin/env python3
"""Cut the scenario's Landsat 8 scenes - before, during and after the incident - over its map area into images.

The scenes are the scenario's LANDSAT_SCENES (Collection 2 Level-2 surface
reflectance); for Västmanland 2014, cloud over the whole scene:

- 10 June 2014, 10:00 UTC (path 193): before the fire, clear over the fire area;
- 4 August 2014, 10:06 UTC (path 194): Landsat 8 over the fire as it spread fastest;
- 14 September 2014, 10:00 UTC (path 193): after the fire, clear over the whole burnt area.

Scenes from path 195 (for example 26 July and 27 August) look closer in time but only
graze the fire area at the scene's eastern edge; the tool reports the share of the
fire area each scene covers and warns below MIN_COVERAGE_PCT.

The scene is read from Microsoft Planetary Computer's open STAC catalogue with the
anonymous access token its API hands out; GDAL in Docker (the same image as
tools/build_terrain.py) reads only the map area from the cloud-optimised GeoTIFFs and
warps it to WGS 84. Per scene it writes three PNGs:

- natural colour (bands 4-3-2, reflectance 0-0.25);
- false colour with short-wave infrared (bands 7-5-4, reflectance 0-0.45), in
  which active fire shows orange-red and the burnt area dark;
- NDMI, the normalised difference moisture index (B5 - B6) / (B5 + B6): the water
  in the vegetation, brown dry to blue moist; clouds, their shadows and water from
  the scene's QA_PIXEL mask are left transparent (the index says nothing about water).

The NDMI and the share of cloud over the fire area are computed with numpy and the
PNG written with Pillow, so run it with the repository's .venv. USGS Landsat data
are public domain; data/landsat/SOURCE.json records the scenes, the bands, the
stretch, the cloud over the fire and the citation. data/ is not versioned.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.backend import scenario

REPO_ROOT = Path(__file__).resolve().parents[1]
LANDSAT_DIR = scenario.LANDSAT_DIR
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
TOKEN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/token/landsat-c2-l2"
SCENES = scenario.LANDSAT_SCENES
# The area each scene's coverage and cloud share is reported for, as west, south, east, north.
FIRE_AREA = scenario.LANDSAT_FOCUS_AREA
# QA_PIXEL bits: 0 fill, 1 dilated cloud, 2 cirrus, 3 cloud, 4 cloud shadow, 7 water.
QA_FILL, QA_CLOUDY, QA_WATER = 1, (1 << 1) | (1 << 2) | (1 << 3) | (1 << 4), 1 << 7
# NDMI colours, brown dry to blue moist (stops: index, RGB).
# Healthy boreal forest lies around 0.3-0.5, so the blue end reaches 0.6.
NDMI_COLOURS = [(-0.2, (140, 81, 10)), (0.0, (216, 179, 101)), (0.15, (246, 232, 195)),
                (0.3, (199, 234, 229)), (0.45, (90, 180, 172)), (0.6, (1, 102, 94))]
MIN_COVERAGE_PCT = 95.0  # a scene must have data over this share of the fire area
RAW_BANDS = {"nir08": "B5", "swir16": "B6", "qa_pixel": "QA"}
GDAL_IMAGE = "tumgis/ctb-quantized-mesh:latest"
HOST_CA_BUNDLE = Path("/etc/ssl/certs/ca-certificates.crt")
# The scenario's map area, as the offline map tiles (west, south, east, north), so the image
# fills the whole map on a wide screen and where the 2D map can be panned; about 30 m per pixel.
BBOX = scenario.MAP_BBOX
SIZE = scenario.LANDSAT_SIZE
# Collection 2 Level-2 surface reflectance = DN * 0.0000275 - 0.2.
SCALE, OFFSET = 0.0000275, -0.2
COMPOSITES = {
    "natural": {"bands": ["red", "green", "blue"], "names": "4-3-2", "reflectance": (0.0, 0.25)},
    "swir": {"bands": ["swir22", "nir08", "red"], "names": "7-5-4", "reflectance": (0.0, 0.45)},
}
CITATION = "Landsat 8-9 OLI/TIRS Collection 2 Level-2 Science Products, courtesy of the U.S. Geological Survey, doi:10.5066/P9OGBGM6"
LICENCE = "https://www.usgs.gov/core-science-systems/hdds/data-policy (public domain)"
USER_AGENT = "techseed-geospatial-intelligence/0.1"


def dn_for(reflectance: float) -> int:
    """The Level-2 digital number of a surface reflectance."""
    return round((reflectance - OFFSET) / SCALE)


def get_json(url: str, attempts: int = 3) -> dict:
    """GET JSON; a server error (5xx) or a network error is tried again, the catalogue has brief outages."""
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=60) as response:
                return json.loads(response.read())
        except HTTPError as exc:
            if exc.code < 500 or attempt == attempts:
                raise
        except URLError:
            if attempt == attempts:
                raise
        time.sleep(5 * attempt)
    raise RuntimeError("unreachable")


def warp_script(urls: dict[str, str], scene: str, bbox: tuple[float, ...] = BBOX, size: tuple[int, int] = SIZE) -> str:
    """Shell script for the GDAL container: one warped GeoTIFF per band, then a PNG per composite."""
    west, south, east, north = bbox
    bands = sorted({band for composite in COMPOSITES.values() for band in composite["bands"]} | set(RAW_BANDS))
    lines = ["set -e", "cd /data"]
    for band in bands:
        # The QA mask holds bit flags: nearest neighbour, never interpolated.
        method = "near" if band == "qa_pixel" else "bilinear"
        # Not listing the remote directory speeds up /vsicurl/. Set per command: globally it stops
        # GDAL 2.4 from writing the EHdr files below (exit 1 without a message).
        lines.append(f"gdalwarp -q --config GDAL_DISABLE_READDIR_ON_OPEN EMPTY_DIR -overwrite -t_srs EPSG:4326 -te {west} {south} {east} {north} -ts {size[0]} {size[1]} "
                     f"-r {method} '/vsicurl/{urls[band]}' {band}.tif")
    for band in RAW_BANDS:
        # Plain little-endian UInt16 rows for numpy (EHdr: a .bil file and a .hdr header).
        lines.append(f"gdal_translate -q -of EHdr {band}.tif {scene}-{band}.bil")
    for name, composite in COMPOSITES.items():
        low, high = (dn_for(value) for value in composite["reflectance"])
        lines.append(f"gdalbuildvrt -q -separate {name}.vrt " + " ".join(f"{band}.tif" for band in composite["bands"]))
        lines.append(f"gdal_translate -q -ot Byte -scale {low} {high} 1 255 -a_nodata 0 -of PNG {name}.vrt {scene}-{name}.png")
    lines.append("rm -f " + " ".join(f"{band}.tif" for band in bands) + " *.vrt *.aux.xml")
    return "\n".join(lines)


def fire_area_rows_cols(size: tuple[int, int] = SIZE, bbox: tuple[float, ...] = BBOX) -> tuple[slice, slice]:
    """The rows and columns of the image that cover the fire area."""
    west, south, east, north = bbox
    fw, fs_, fe, fn = FIRE_AREA
    width, height = size
    cols = slice(round((fw - west) / (east - west) * width), round((fe - west) / (east - west) * width))
    rows = slice(round((north - fn) / (north - south) * height), round((north - fs_) / (north - south) * height))
    return rows, cols


def ndmi_image(out: Path, scene: str, size: tuple[int, int] = SIZE) -> tuple[float, float]:
    """Write the NDMI PNG from the raw bands; return the shares of the fire area with data and under cloud, in per cent.

    The cloud share is over the whole fire area, so a scene that only grazes it cannot look clear."""
    import numpy as np
    from PIL import Image

    width, height = size
    read = lambda band: np.fromfile(out / f"{scene}-{band}.bil", dtype="<u2").reshape(height, width)  # noqa: E731
    nir, swir, qa = (read(band) for band in RAW_BANDS)
    fill = (qa & QA_FILL) > 0
    cloudy = (qa & QA_CLOUDY) > 0
    water = (qa & QA_WATER) > 0
    valid = ~fill & ~cloudy & ~water & (nir > 0) & (swir > 0)
    nir_r = nir.astype("f4") * SCALE + OFFSET
    swir_r = swir.astype("f4") * SCALE + OFFSET
    with np.errstate(divide="ignore", invalid="ignore"):
        ndmi = (nir_r - swir_r) / (nir_r + swir_r)
    valid &= np.isfinite(ndmi)
    rgba = np.zeros((height, width, 4), dtype="u1")
    stops = np.array([stop for stop, _ in NDMI_COLOURS], dtype="f4")
    for channel in range(3):
        rgba[..., channel] = np.interp(ndmi, stops, [rgb[channel] for _, rgb in NDMI_COLOURS]).round().astype("u1")
    rgba[..., 3] = np.where(valid, 230, 0)
    Image.fromarray(rgba, "RGBA").save(out / f"{scene}-ndmi.png", optimize=True)
    rows, cols = fire_area_rows_cols(size)
    has_data = ~fill[rows, cols] & (nir[rows, cols] > 0)
    total = has_data.size
    coverage = round(100.0 * float(has_data.sum()) / total, 1)
    cloud = round(100.0 * float((cloudy[rows, cols] & has_data).sum()) / total, 1)
    return coverage, cloud


def user() -> str:
    return f"{os.getuid()}:{os.getgid()}"


def docker_command(script: str, out: Path) -> list[str]:
    # The image has no CA certificates; the host's are mounted read-only so TLS is still verified.
    return ["docker", "run", "--rm", "-u", user(), "-v", f"{out.resolve()}:/data", "-v", f"{HOST_CA_BUNDLE}:/etc/ssl/host-ca.crt:ro",
            "-e", "CURL_CA_BUNDLE=/etc/ssl/host-ca.crt", GDAL_IMAGE, "sh", "-c", script]


def without_token(text: str, token: str) -> str:
    """The access token is short-lived and anonymous, but it is still kept out of the output."""
    return text.replace(token, "<token>")


def process(scene: str, token: str, out: Path) -> dict:
    """Cut one scene into its PNGs and return its record for SOURCE.json."""
    item = get_json(f"{STAC}/collections/landsat-c2-l2/items/{scene}")
    bands = {band for composite in COMPOSITES.values() for band in composite["bands"]} | set(RAW_BANDS)
    urls = {band: f"{item['assets'][band]['href']}?{token}" for band in bands}
    run = subprocess.run(docker_command(warp_script(urls, scene), out), capture_output=True, text=True)
    if run.returncode != 0:
        raise RuntimeError(f"GDAL failed for {scene}:\n{without_token(run.stderr, token)[-2000:]}")
    coverage, fire_cloud = ndmi_image(out, scene)
    for band in RAW_BANDS:
        for suffix in (".bil", ".hdr", ".prj", ".bil.aux.xml"):
            (out / f"{scene}-{band}{suffix}").unlink(missing_ok=True)
    return {
        "scene": scene,
        "acquired_utc": item["properties"]["datetime"][:19] + "Z",
        "cloud_cover_pct": item["properties"].get("eo:cloud_cover"),
        "fire_area_coverage_pct": coverage,
        "fire_area_cloud_pct": fire_cloud,
        "catalogue": f"{STAC}/collections/landsat-c2-l2/items/{scene}",
        "images": {
            **{name: {"file": f"{scene}-{name}.png", "bands": composite["names"], "reflectance": list(composite["reflectance"])}
               for name, composite in COMPOSITES.items()},
            "ndmi": {"file": f"{scene}-ndmi.png", "bands": "(5-6)/(5+6)", "index": [stop for stop, _ in NDMI_COLOURS]},
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--scenes", nargs="+", choices=sorted(SCENES), default=list(SCENES), help="which of the three scenes")
    parser.add_argument("--scene-id", action="append", default=[], metavar="ROLE=ID", help="use another scene for a role")
    parser.add_argument("--out", type=Path, default=LANDSAT_DIR, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    scenes = dict(SCENES)
    for choice in args.scene_id:
        role, _, scene = choice.partition("=")
        if role not in SCENES or not scene:
            parser.error(f"--scene-id needs ROLE=ID with ROLE one of {', '.join(SCENES)}")
        scenes[role] = scene
    token = get_json(TOKEN_URL)["token"]
    args.out.mkdir(parents=True, exist_ok=True)
    records = []
    for role in args.scenes:
        try:
            record = process(scenes[role], token, args.out)
        except RuntimeError as exc:
            parser.exit(1, f"fetch_landsat_scene: {exc}\n")
        records.append({"role": role, **record})
        warning = "" if record["fire_area_coverage_pct"] >= MIN_COVERAGE_PCT else " – VARNING: täcker inte fokusområdet"
        print(f"{role}: {record['scene']} – data över {record['fire_area_coverage_pct']} % av fokusområdet, "
              f"moln över {record['fire_area_cloud_pct']} %{warning}")
    west, south, east, north = BBOX
    (args.out / "SOURCE.json").write_text(json.dumps({
        "scenes": records,
        "bounds_west_south_east_north": [west, south, east, north],
        "size_px": list(SIZE),
        "ndmi_colours": [[stop, list(rgb)] for stop, rgb in NDMI_COLOURS],
        "processed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "processing": (f"gdalwarp to EPSG:4326 (bilinear; QA nearest) and a linear stretch of surface reflectance to 8 bit "
                       f"({GDAL_IMAGE}); NDMI with numpy, clouds and shadows from QA_PIXEL transparent"),
        "citation": CITATION,
        "licence": LICENCE,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
