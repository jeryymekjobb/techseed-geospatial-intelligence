#!/usr/bin/env python3
"""Fetch Copernicus EMS's mapped perimeters of the scenario's fire as one GeoJSON.

Copernicus Emergency Management Service rapid mapping publishes each activation's
delineation and monitoring products as zipped shapefiles. For the scenario's EMS_AREA
(activation and area of interest, for example EMSR298 area 01 Enskogen) this tool finds
the products on the activation's page, reads each one's observed event (the burnt and
burning area) and its source table - the latest post-event image and its date - with
GDAL in Docker, and writes data/<scenario>/ems/perimeters.geojson: one feature per
product with the image's date and source and the area in hectares (in SWEREF 99 TM).

The image dates carry no time of day, so the screens show a perimeter from the end of its
image's day, never before the image existed. Copernicus EMS products are free to use with
the attribution "© European Union, Copernicus Emergency Management Service"; SOURCE.json
records the activation, the products and their files' URLs.

    TECHSEED_SCENARIO=ljusdal2018 .venv/bin/python -m tools.fetch_ems_perimeters

--zips reads the products' zip files from a directory instead of downloading them (the
same file names as on the page), for example when they were fetched earlier.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from app.backend import scenario
from tools.fetch_landsat_scene import GDAL_IMAGE, USER_AGENT, user

PAGE = "https://mapping.emergency.copernicus.eu/activations/{activation}/"
ATTRIBUTION = "© European Union, Copernicus Emergency Management Service ({activation})"


def download(url: str) -> bytes:
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=120) as response:
        return response.read()


def product_urls(page: str, activation: str, area: str) -> dict[str, str]:
    """The newest version of each delineation product of the area on the activation's page, by product (MAP, MONIT01 …)."""
    pattern = re.compile(rf"https://[^\"'\s]*/{activation}_{area}_01DELINEATION_([A-Z0-9]+)_v(\d+)_vector\.zip")
    found: dict[str, tuple[int, str]] = {}
    for match in pattern.finditer(page):
        product, version = match.group(1), int(match.group(2))
        if product not in found or version > found[product][0]:
            found[product] = (version, match.group(0))
    return {product: url for product, (_, url) in sorted(found.items(), key=lambda item: (item[0] != "MAP", item[0]))}


def latest_source(rows: list[dict[str, str]]) -> tuple[str, str] | None:
    """The newest dated image of a product's source table (dd/mm/yyyy): its ISO date and name."""
    dated = []
    for row in rows:
        match = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", row.get("src_date") or "")
        if match:
            day, month, year = match.groups()
            dated.append((f"{year}-{month}-{day}", row.get("source_nam") or ""))
    return max(dated) if dated else None


def convert(directory: Path) -> tuple[dict, list[dict[str, str]]]:
    """The observed event in WGS 84 with each part's hectares, and the source table, by GDAL in Docker."""
    event = next(directory.glob("*observed_event_a.shp")).stem
    source = next(directory.glob("*source*.dbf")).stem
    script = (f"cd /data && ogr2ogr -f GeoJSON -t_srs EPSG:4326 -dialect sqlite -sql "
              f"\"SELECT geometry, ST_Area(ST_Transform(geometry, 3006)) / 10000.0 AS ha FROM '{event}'\" event.geojson {event}.shp"
              f" && ogr2ogr -f CSV source.csv {source}.dbf")
    subprocess.run(["docker", "run", "--rm", "-u", user(), "-v", f"{directory.resolve()}:/data", GDAL_IMAGE, "sh", "-c", script],
                   check=True, capture_output=True, text=True)
    with (directory / "source.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return json.loads((directory / "event.geojson").read_text(encoding="utf-8")), rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--out", type=Path, default=scenario.EMS_DIR)
    parser.add_argument("--zips", type=Path, help="read the products' zip files from here instead of downloading them")
    args = parser.parse_args(argv)
    if not scenario.EMS_AREA or args.out is None:
        parser.exit(1, f"fetch_ems_perimeters: the scenario {scenario.NAME} has no EMS area\n")
    activation, area = scenario.EMS_AREA["activation"], scenario.EMS_AREA["area"]
    if args.zips:
        listing = " ".join(f"https://local/{path.name}" for path in args.zips.glob(f"{activation}_{area}_*_vector.zip"))
        urls = product_urls(listing, activation, area)
    else:
        urls = product_urls(download(PAGE.format(activation=activation)).decode("utf-8", "replace"), activation, area)
    if not urls:
        parser.exit(1, f"fetch_ems_perimeters: no delineation products of {activation} {area} on its page\n")
    args.out.mkdir(parents=True, exist_ok=True)
    features = []
    for product, url in urls.items():
        work = args.out / f"work-{product}"
        work.mkdir(exist_ok=True)
        data = (args.zips / url.rsplit("/", 1)[1]).read_bytes() if args.zips else download(url)
        zipfile.ZipFile(io.BytesIO(data)).extractall(work)
        event, source_rows = convert(work)
        latest = latest_source(source_rows)
        hectares = round(sum(feature["properties"]["ha"] for feature in event["features"]))
        parts = [feature["geometry"] for feature in event["features"]]
        polygons = [polygon for geometry in parts
                    for polygon in (geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]])]
        features.append({"type": "Feature", "geometry": {"type": "MultiPolygon", "coordinates": polygons}, "properties": {
            "product": product, "image_date": latest[0] if latest else None, "image_source": latest[1] if latest else None,
            "area_ha": hectares, "parts": len(parts)}})
        for path in work.iterdir():
            path.unlink()
        work.rmdir()
        print(f"{product}: {latest} – {hectares} ha in {len(parts)} parts", flush=True)
    (args.out / "perimeters.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}) + "\n", encoding="utf-8")
    (args.out / "SOURCE.json").write_text(json.dumps({
        "activation": activation, "area": area, "page": PAGE.format(activation=activation),
        # The products' files: their URLs, or only their names when read from local copies (--zips).
        "products": {product: url.rsplit("/", 1)[1] for product, url in urls.items()} if args.zips else urls,
        "attribution": ATTRIBUTION.format(activation=activation),
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "observed event (burnt and burning area) of each delineation product; image_date is its newest post-event image",
    }, indent=1) + "\n", encoding="utf-8")
    print(f"{len(features)} products -> {args.out / 'perimeters.geojson'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
