#!/usr/bin/env python3
"""Fetch SMHI's weather radar composite for the scenario's map area as rain images.

SMHI's open data has the Swedish radar composite every 5 minutes as 8-bit
GeoTIFFs in SWEREF 99 TM (about 2 km pixels), a zip per day. A pixel value v is
the reflectivity v * 0.4 - 30 dBZ; 0 is no echo and 255 outside the radars
(https://opendata.smhi.se/apidocs/radar/data.html). For every --step minutes
this tool cuts the map area out in WGS 84 (nearest pixel, by the Gauss-Krüger
formulas for SWEREF 99 TM), turns the reflectivity into a rain rate with the
Marshall-Palmer relation Z = 200 R^1.6 and colours it in SMHI's classes of rain
by the hour (as app/frontend/rain.js): below 5 dBZ and outside the radars it is
transparent. The rain rate is an estimate from the radar, not a measurement on
the ground.

    .venv/bin/python -m tools.fetch_smhi_radar --start 2026-08-14 --end 2026-08-22 --out data/sundsvall2026/radar

SMHI open data is licensed under Creative Commons Attribution 4.0 SE: name SMHI
as the source and state changes (here: cut-out, reprojection, rain rate and
colours). Numpy and Pillow from the .venv.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
from PIL import Image

from app.backend import scenario

API = "https://opendata-download-radar.smhi.se/api/version/latest/area/sweden/product/comp"
USER_AGENT = "techseed-geospatial-intelligence/0.1 (exhibition demonstrator)"
ATTRIBUTION = ("SMHI öppna data, väderradar (CC BY 4.0 SE); utsnitt, omprojicering, regnintensitet "
               "beräknad med Z = 200·R^1,6 och färgad efter SMHI:s regnklasser")
GAIN, OFFSET = 0.4, -30.0
NO_ECHO, NO_DATA = 0, 255
MIN_DBZ = 5.0  # weaker echoes are not counted as precipitation
# SMHI's classes of rain by the hour's sum (as rain.js): upper limit in mm/h and RGBA.
# The light classes let the map show through; heavy rain and cloudbursts stand out.
CLASSES = [(0.5, (166, 205, 242, 70)), (4.0, (61, 143, 217, 130)), (50.0 - 1e-9, (18, 63, 140, 200)), (math.inf, (122, 31, 162, 230))]
PIXELS_PER_DEGREE = (200, 400)  # longitude, latitude: about 0.5 km, finer than the radar's 2 km


def day_url(day: date) -> str:
    return f"{API}/{day.year}/{day.month:02d}/{day.day:02d}.zip?format=tif"


def sweref99tm(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Northing and easting in SWEREF 99 TM (Lantmäteriet's Gauss-Krüger formulas, GRS 80)."""
    a, f = 6378137.0, 1 / 298.257222101
    k0, lon0, false_east = 0.9996, math.radians(15.0), 500000.0
    e2 = f * (2 - f)
    n = f / (2 - f)
    a_roof = a / (1 + n) * (1 + n ** 2 / 4 + n ** 4 / 64)
    big_a = e2
    big_b = (5 * e2 ** 2 - e2 ** 3) / 6
    big_c = (104 * e2 ** 3 - 45 * e2 ** 4) / 120
    big_d = (1237 * e2 ** 4) / 1260
    beta = [n / 2 - 2 * n ** 2 / 3 + 5 * n ** 3 / 16 + 41 * n ** 4 / 180,
            13 * n ** 2 / 48 - 3 * n ** 3 / 5 + 557 * n ** 4 / 1440,
            61 * n ** 3 / 240 - 103 * n ** 4 / 140,
            49561 * n ** 4 / 161280]
    phi, lam = np.radians(lat), np.radians(lon)
    s = np.sin(phi)
    phi_star = phi - s * np.cos(phi) * (big_a + big_b * s ** 2 + big_c * s ** 4 + big_d * s ** 6)
    d_lam = lam - lon0
    xi = np.arctan(np.tan(phi_star) / np.cos(d_lam))
    eta = np.arctanh(np.cos(phi_star) * np.sin(d_lam))
    north = k0 * a_roof * (xi + sum(b * np.sin(2 * (j + 1) * xi) * np.cosh(2 * (j + 1) * eta) for j, b in enumerate(beta)))
    east = k0 * a_roof * (eta + sum(b * np.cos(2 * (j + 1) * xi) * np.sinh(2 * (j + 1) * eta) for j, b in enumerate(beta))) + false_east
    return north, east


def geotransform(tiff: Image.Image) -> tuple[float, float, float, float]:
    """Top-left easting and northing and the pixel sizes, from the GeoTIFF's tie point and scale."""
    tie = tiff.tag_v2[33922]
    scale = tiff.tag_v2[33550]
    return tie[3], tie[4], scale[0], scale[1]


def cut_out(bbox: tuple[float, float, float, float]) -> tuple[np.ndarray, np.ndarray, tuple[int, int]]:
    """The latitude and longitude of every output pixel's centre over the area (west, south, east, north)."""
    west, south, east, north = bbox
    width = round((east - west) * PIXELS_PER_DEGREE[0])
    height = round((north - south) * PIXELS_PER_DEGREE[1])
    lons = west + (np.arange(width) + 0.5) * (east - west) / width
    lats = north - (np.arange(height) + 0.5) * (north - south) / height
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    return lat_grid, lon_grid, (width, height)


def rain_rate(values: np.ndarray) -> np.ndarray:
    """mm/h from pixel values by Z = 200 R^1.6; NaN where there is no echo, no data or under MIN_DBZ."""
    dbz = values.astype(float) * GAIN + OFFSET
    rate = (10 ** (dbz / 10) / 200) ** (1 / 1.6)
    return np.where((values == NO_ECHO) | (values == NO_DATA) | (dbz < MIN_DBZ), np.nan, rate)


def colours(rate: np.ndarray) -> np.ndarray:
    """RGBA in SMHI's classes of rain; transparent without rain."""
    rgba = np.zeros((*rate.shape, 4), dtype=np.uint8)
    lower = 0.0
    for upper, colour in CLASSES:
        inside = (rate > lower) & (rate <= upper) if upper != math.inf else rate > lower
        rgba[inside] = colour
        lower = upper
    return rgba


def frame_png(tiff_bytes: bytes, lat: np.ndarray, lon: np.ndarray) -> tuple[bytes, float]:
    """The coloured cut-out of one radar image, and the highest rain rate in it (mm/h)."""
    tiff = Image.open(io.BytesIO(tiff_bytes))
    left, top, size_x, size_y = geotransform(tiff)
    values = np.array(tiff)
    north, east = sweref99tm(lat, lon)
    cols = np.floor((east - left) / size_x).astype(int)
    rows = np.floor((top - north) / size_y).astype(int)
    inside = (rows >= 0) & (rows < values.shape[0]) & (cols >= 0) & (cols < values.shape[1])
    picked = np.full(lat.shape, NO_DATA, dtype=np.uint8)
    picked[inside] = values[rows[inside], cols[inside]]
    rate = rain_rate(picked)
    out = io.BytesIO()
    Image.fromarray(colours(rate), "RGBA").save(out, "PNG", optimize=True)
    return out.getvalue(), float(np.nanmax(rate)) if np.isfinite(rate).any() else 0.0


def moment_of(name: str) -> datetime | None:
    """The time of a file in the day's zip, such as radar_2608160600.tif."""
    stem = Path(name).stem.removeprefix("radar_")
    try:
        return datetime.strptime(stem, "%y%m%d%H%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--step", type=int, default=10, help="minutes between frames (a multiple of 5)")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    lat, lon, (width, height) = cut_out(scenario.MAP_BBOX)
    args.out.mkdir(parents=True, exist_ok=True)
    frames = []
    day = args.start
    while day <= args.end:
        with urlopen(Request(day_url(day), headers={"User-Agent": USER_AGENT}), timeout=300) as response:
            archive = zipfile.ZipFile(io.BytesIO(response.read()))
        for name in sorted(archive.namelist()):
            moment = moment_of(name)
            if moment is None or moment.date() != day or (moment.hour * 60 + moment.minute) % args.step:
                continue
            png, highest = frame_png(archive.read(name), lat, lon)
            file = f"radar-{moment:%Y%m%dT%H%M}.png"
            (args.out / file).write_bytes(png)
            frames.append({"time_utc": moment.strftime("%Y-%m-%dT%H:%M:%SZ"), "file": file, "max_mm_per_h": round(highest, 1)})
        print(f"{day}: {sum(1 for item in frames if item['time_utc'].startswith(day.isoformat()))} frames", flush=True)
        day += timedelta(days=1)
    west, south, east, north = scenario.MAP_BBOX
    (args.out / "SOURCE.json").write_text(json.dumps({
        "source": API, "licence": "CC BY 4.0 SE", "attribution": ATTRIBUTION,
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bounds_west_south_east_north": [west, south, east, north], "size_px": [width, height],
        "step_minutes": args.step, "rain_rate": "Z = 200 R^1.6, R in mm/h; below 5 dBZ none",
        "classes_mm_per_h": [upper for upper, _ in CLASSES[:-1]], "frames": frames,
    }, indent=1) + "\n", encoding="utf-8")
    print(f"{len(frames)} frames -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
