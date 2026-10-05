#!/usr/bin/env python3
"""Cut the Landsat 8 scene of 4 August 2014 over the fire-map area into two images in data/landsat/.

Landsat 8 passed over the fire at 10:06:44 UTC on 4 August 2014 with 1.7 % cloud
(scene LC08_L2SP_194018_20140804_02_T1, Collection 2 Level-2 surface reflectance).
The scene is read from Microsoft Planetary Computer's open STAC catalogue with the
anonymous access token its API hands out; GDAL in Docker (the same image as
tools/build_terrain.py) reads only the map area from the cloud-optimised GeoTIFFs,
warps it to WGS 84 and writes two PNGs:

- natural colour (bands 4-3-2, reflectance 0-0.25);
- false colour with short-wave infrared (bands 7-5-4, reflectance 0-0.45), in
  which active fire shows orange-red and the burnt area dark.

USGS Landsat data are public domain; data/landsat/SOURCE.json records the scene,
the bands, the stretch and the citation. data/ is not versioned.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
LANDSAT_DIR = REPO_ROOT / "data" / "landsat"
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
TOKEN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/token/landsat-c2-l2"
SCENE = "LC08_L2SP_194018_20140804_02_T1"
GDAL_IMAGE = "tumgis/ctb-quantized-mesh:latest"
HOST_CA_BUNDLE = Path("/etc/ssl/certs/ca-certificates.crt")
# The map view of app/backend/scenario.py as west, south, east, north.
BBOX = (15.85, 59.75, 16.45, 60.08)
# About 30 m, the Landsat resolution: 0.6 degrees of longitude and 0.33 of latitude at 60 N.
SIZE = (1100, 1220)
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


def get_json(url: str) -> dict:
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=60) as response:
        return json.loads(response.read())


def warp_script(urls: dict[str, str], scene: str, bbox: tuple[float, ...] = BBOX, size: tuple[int, int] = SIZE) -> str:
    """Shell script for the GDAL container: one warped GeoTIFF per band, then a PNG per composite."""
    west, south, east, north = bbox
    bands = sorted({band for composite in COMPOSITES.values() for band in composite["bands"]})
    lines = ["set -e", "cd /data"]
    for band in bands:
        lines.append(f"gdalwarp -q -overwrite -t_srs EPSG:4326 -te {west} {south} {east} {north} -ts {size[0]} {size[1]} "
                     f"-r bilinear '/vsicurl/{urls[band]}' {band}.tif")
    for name, composite in COMPOSITES.items():
        low, high = (dn_for(value) for value in composite["reflectance"])
        lines.append(f"gdalbuildvrt -q -separate {name}.vrt " + " ".join(f"{band}.tif" for band in composite["bands"]))
        lines.append(f"gdal_translate -q -ot Byte -scale {low} {high} 1 255 -a_nodata 0 -of PNG {name}.vrt {scene}-{name}.png")
    lines.append("rm -f " + " ".join(f"{band}.tif" for band in bands) + " *.vrt *.aux.xml")
    return "\n".join(lines)


def user() -> str:
    return f"{os.getuid()}:{os.getgid()}"


def docker_command(script: str, out: Path) -> list[str]:
    # The image has no CA certificates; the host's are mounted read-only so TLS is still verified.
    return ["docker", "run", "--rm", "-u", user(), "-v", f"{out}:/data", "-v", f"{HOST_CA_BUNDLE}:/etc/ssl/host-ca.crt:ro",
            "-e", "CURL_CA_BUNDLE=/etc/ssl/host-ca.crt", "-e", "GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR",
            GDAL_IMAGE, "sh", "-c", script]


def without_token(text: str, token: str) -> str:
    """The access token is short-lived and anonymous, but it is still kept out of the output."""
    return text.replace(token, "<token>")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--scene", default=SCENE)
    parser.add_argument("--out", type=Path, default=LANDSAT_DIR, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    item = get_json(f"{STAC}/collections/landsat-c2-l2/items/{args.scene}")
    token = get_json(TOKEN_URL)["token"]
    bands = {band for composite in COMPOSITES.values() for band in composite["bands"]}
    urls = {band: f"{item['assets'][band]['href']}?{token}" for band in bands}
    args.out.mkdir(parents=True, exist_ok=True)
    run = subprocess.run(docker_command(warp_script(urls, args.scene), args.out), capture_output=True, text=True)
    if run.returncode != 0:
        parser.exit(1, f"fetch_landsat_scene: GDAL failed:\n{without_token(run.stderr, token)[-2000:]}\n")
    west, south, east, north = BBOX
    (args.out / "SOURCE.json").write_text(json.dumps({
        "scene": args.scene,
        "acquired_utc": item["properties"]["datetime"][:19] + "Z",
        "cloud_cover_pct": item["properties"].get("eo:cloud_cover"),
        "catalogue": f"{STAC}/collections/landsat-c2-l2/items/{args.scene}",
        "bounds_west_south_east_north": [west, south, east, north],
        "size_px": list(SIZE),
        "images": {
            name: {"file": f"{args.scene}-{name}.png", "bands": composite["names"], "reflectance": list(composite["reflectance"])}
            for name, composite in COMPOSITES.items()
        },
        "processed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "processing": f"gdalwarp to EPSG:4326, bilinear; linear stretch of surface reflectance to 8 bit ({GDAL_IMAGE})",
        "citation": CITATION,
        "licence": LICENCE,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for name in COMPOSITES:
        path = args.out / f"{args.scene}-{name}.png"
        print(f"{path.name}: {path.stat().st_size // 1024} kB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
