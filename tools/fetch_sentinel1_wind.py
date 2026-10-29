#!/usr/bin/env python3
"""Fetch Sentinel-1's wind over the sea (the OCN product) for the scenario's map area and playback.

Sentinel-1's Level-2 ocean product gives the wind 10 m over the sea, retrieved from the radar
image, on a grid of about 1 km. This tool finds the scenario's OCN products in Copernicus Data
Space's open catalogue (those that cover MAP_BBOX between PLAYBACK_START and PLAYBACK_END),
downloads each once into RAW_DIR with the user's Copernicus Data Space account (a machine line for
identity.dataspace.copernicus.eu in ~/.netrc) and keeps, per pass, every STEP-th cell over the
sea in the map area whose wind the product flags valid and not of poor quality: its speed and the
direction it blows from. It writes SENTINEL1_WIND_DIR/wind.json.

    TECHSEED_SCENARIO=ljungan-aug2023 .venv/bin/python -m tools.fetch_sentinel1_wind

A pass's wind is measured at that moment only; the screens show it for some hours after. Copernicus
Sentinel data are free and open (the Sentinel Data Legal Notice).
"""

from __future__ import annotations

import argparse
import io
import json
import math
import netrc
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from app.backend import scenario
from tools.netcdf3 import NetCDF3

CATALOGUE = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
DOWNLOAD = "https://zipper.dataspace.copernicus.eu/odata/v1/Products({id})/$value"
TOKEN = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
NETRC_HOST = "identity.dataspace.copernicus.eu"
# Every STEP-th row and column of the product's 1 km grid: about 2 km between the arrows.
STEP = 2
# The product's wind quality: good, medium, low and poor; poor is left out.
WORST_QUALITY = 2
ATTRIBUTION = "Contains modified Copernicus Sentinel data 2023 (Sentinel-1 Level-2 OCN, wind over the sea)"


def query(bbox: tuple[float, float, float, float], start: datetime, end: datetime) -> str:
    west, south, east, north = bbox
    polygon = f"POLYGON(({west} {south},{east} {south},{east} {north},{west} {north},{west} {south}))"
    stamp = lambda moment: moment.strftime("%Y-%m-%dT%H:%M:%S.000Z")  # noqa: E731
    condition = (f"Collection/Name eq 'SENTINEL-1' and contains(Name,'_OCN_') and ContentDate/Start gt {stamp(start)}"
                 f" and ContentDate/Start lt {stamp(end)} and OData.CSC.Intersects(area=geography'SRID=4326;{polygon}')")
    return CATALOGUE + "?" + urllib.parse.urlencode({"$filter": condition, "$orderby": "ContentDate/Start", "$top": "100"})


def token() -> str:
    login = netrc.netrc().authenticators(NETRC_HOST)
    if login is None:
        raise SystemExit(f"fetch_sentinel1_wind: no line for {NETRC_HOST} in ~/.netrc")
    body = urllib.parse.urlencode({"client_id": "cdse-public", "grant_type": "password", "username": login[0], "password": login[2]})
    with urllib.request.urlopen(TOKEN, body.encode(), timeout=60) as response:
        return json.load(response)["access_token"]


def download(product: dict[str, Any], target: Path, access: str) -> None:
    request = urllib.request.Request(DOWNLOAD.format(id=product["Id"]), headers={"Authorization": f"Bearer {access}"})
    part = target.with_suffix(".part")
    with urllib.request.urlopen(request, timeout=600) as response:
        part.write_bytes(response.read())
    part.rename(target)


def measurement(archive: Path) -> NetCDF3:
    with zipfile.ZipFile(archive) as opened:
        [name] = [item for item in opened.namelist() if "/measurement/" in item and item.endswith(".nc")]
        return NetCDF3(opened.read(name))


def sensing_time(product_name: str) -> datetime:
    """The pass's first sensing time from the product's name (S1A_IW_OCN__2SDV_20230809T050638_…)."""
    return datetime.strptime(product_name.split("_")[5], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)


def mean_direction(degrees: list[float]) -> int:
    """The mean of directions as the direction of the mean unit vector, in whole degrees."""
    x = sum(math.sin(math.radians(value)) for value in degrees)
    y = sum(math.cos(math.radians(value)) for value in degrees)
    return round(math.degrees(math.atan2(x, y))) % 360


def wind_points(grid: NetCDF3, bbox: tuple[float, float, float, float], step: int = STEP) -> list[list[float]]:
    """[latitude, longitude, speed m/s, from degrees] of every step-th valid sea cell in bbox."""
    west, south, east, north = bbox
    latitude, longitude = grid.array("owiLat"), grid.array("owiLon")
    speed, direction = grid.array("owiWindSpeed"), grid.array("owiWindDirection")
    mask, quality = grid.array("owiMask"), grid.array("owiWindQuality")
    keep = np.zeros(speed.shape, dtype=bool)
    keep[::step, ::step] = True
    keep &= (mask == 0) & (speed >= 0) & (quality >= 0) & (quality <= WORST_QUALITY)
    keep &= (longitude >= west) & (longitude <= east) & (latitude >= south) & (latitude <= north)
    return [[round(float(latitude[row, column]), 4), round(float(longitude[row, column]), 4),
             round(float(speed[row, column]), 1), round(float(direction[row, column])) % 360]
            for row, column in zip(*np.nonzero(keep))]


def summary(product_name: str, points: list[list[float]]) -> dict[str, Any]:
    speeds = sorted(point[2] for point in points)
    return {"time_utc": sensing_time(product_name).strftime("%Y-%m-%dT%H:%M:%SZ"), "satellite": f"Sentinel-{product_name[1:3]}",
            "product": product_name.removesuffix(".SAFE"), "median_ms": round(speeds[len(speeds) // 2], 1),
            "max_ms": speeds[-1], "from_deg": mean_direction([point[3] for point in points]), "points": points}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--out", type=Path, default=scenario.SENTINEL1_WIND_DIR)
    args = parser.parse_args(argv)
    if args.out is None:
        parser.exit(1, f"fetch_sentinel1_wind: the scenario {scenario.NAME} has no Sentinel-1 wind\n")
    raw = args.out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(query(scenario.MAP_BBOX, scenario.PLAYBACK_START, scenario.PLAYBACK_END), timeout=60) as response:
        products = json.load(response)["value"]
    access = None
    passes = []
    for product in products:
        archive = raw / f"{product['Name'].removesuffix('.SAFE')}.zip"
        if not archive.is_file():
            access = access or token()
            print(f"fetch_sentinel1_wind: downloading {product['Name']}", flush=True)
            download(product, archive, access)
        points = wind_points(measurement(archive), scenario.MAP_BBOX)
        print(f"fetch_sentinel1_wind: {product['Name']}: {len(points)} points over the sea", flush=True)
        if points:
            passes.append(summary(product["Name"], points))
    if not passes:
        parser.exit(1, "fetch_sentinel1_wind: no Sentinel-1 wind over the sea in the map area\n")
    result = {"source": ATTRIBUTION, "grid_km": STEP, "passes": passes,
              "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    (args.out / "wind.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(f"fetch_sentinel1_wind: wrote {len(passes)} passes to {args.out / 'wind.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
