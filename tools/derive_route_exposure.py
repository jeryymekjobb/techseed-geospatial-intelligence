#!/usr/bin/env python3
"""Compute the rain SMHI's radar estimates fell on the scenario's roads and railways.

The scenario's OSM targets (TARGETS_FILE) give the roads and railways: the larger roads
(motorway to tertiary, and unclassified roads with a number) and the railways outside tunnels.
Each line is cut into pieces of about PIECE_KM, and pieces whose middle lies outside MAP_BBOX are
left out (the OSM extract reaches beyond it, and the radar gave implausible sums there). For every 5-minute radar image from the
playback's start to its end this tool reads the rain rate at each piece's middle (as
tools/fetch_smhi_radar.py: Z = 200 R^1.6, SWEREF 99 TM, about 2 km pixels) and adds it up, and
records the sum at the end of every hour. Only the pieces that reach the lowest threshold of
app/backend/routes.py are kept. It is the radar's estimate of the rain, not damage: the
screens say so (routes.py).

    TECHSEED_SCENARIO=vasternorrland2025 .venv/bin/python -m tools.derive_route_exposure

SMHI open data is licensed under Creative Commons Attribution 4.0 SE; the roads and
railways come from OpenStreetMap (ODbL). Numpy and Pillow from the .venv.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import numpy as np
from PIL import Image

from app.backend import routes, scenario
from tools.fetch_smhi_radar import USER_AGENT, day_url, geotransform, moment_of, rain_rate, sweref99tm

PIECE_KM = 1.0
ROAD_TYPES = {"motorway", "trunk", "primary", "secondary", "tertiary"}
STEP_MINUTES = 5


def wanted(properties: dict[str, Any]) -> str | None:
    """'road' or 'rail' for a target worth following, else None."""
    if properties.get("kind") == "road":
        if properties.get("type") in ROAD_TYPES or (properties.get("type") == "unclassified" and properties.get("ref")):
            return "road"
    if properties.get("kind") == "railway" and properties.get("type") == "rail":
        if not (properties.get("name") or "").endswith("tunneln"):
            return "rail"
    return None


def km_between(a: list[float], b: list[float]) -> float:
    """Kilometres between two lon/lat points, flat at their latitude (fine at a kilometre)."""
    mid = math.radians((a[1] + b[1]) / 2)
    return math.hypot((b[0] - a[0]) * math.cos(mid), b[1] - a[1]) * 111.2


def pieces(coords: list[list[float]], piece_km: float = PIECE_KM) -> list[list[list[float]]]:
    """A line (lon/lat) cut at its vertices into pieces of about `piece_km`, each sharing its end
    with the next, so together they draw the whole line."""
    out, current, length = [], [coords[0]], 0.0
    for point in coords[1:]:
        length += km_between(current[-1], point)
        current.append(point)
        if length >= piece_km:
            out.append(current)
            current, length = [point], 0.0
    if len(current) > 1:
        out.append(current)
    return out


def middle(piece: list[list[float]]) -> list[float]:
    """The piece's vertex nearest its middle by length."""
    lengths = [0.0]
    for a, b in zip(piece, piece[1:]):
        lengths.append(lengths[-1] + km_between(a, b))
    half = lengths[-1] / 2
    return piece[min(range(len(piece)), key=lambda i: abs(lengths[i] - half))]


def sample(tiff_bytes: bytes, north: np.ndarray, east: np.ndarray) -> np.ndarray:
    """The radar's rain rate (mm/h) at points in SWEREF 99 TM; 0 without echo or outside."""
    tiff = Image.open(io.BytesIO(tiff_bytes))
    left, top, size_x, size_y = geotransform(tiff)
    values = np.array(tiff)
    cols = np.floor((east - left) / size_x).astype(int)
    rows = np.floor((top - north) / size_y).astype(int)
    inside = (rows >= 0) & (rows < values.shape[0]) & (cols >= 0) & (cols < values.shape[1])
    picked = np.full(north.shape, 255, dtype=np.uint8)
    picked[inside] = values[rows[inside], cols[inside]]
    return np.nan_to_num(rain_rate(picked))


def hourly_sums(frames: list[tuple[datetime, np.ndarray]], start: datetime, hours: int) -> np.ndarray:
    """Cumulative rain (mm) at the end of each hour from `start`, from rain rates every
    STEP_MINUTES: a rate counts for the step it starts. Shape (hours, points)."""
    points = frames[0][1].shape[0] if frames else 0
    per_hour = np.zeros((hours, points))
    for moment, rate in frames:
        index = int((moment - start).total_seconds() // 3600)
        if 0 <= index < hours:
            per_hour[index] += rate * STEP_MINUTES / 60
    return np.cumsum(per_hour, axis=0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--out", type=Path, default=scenario.ROUTE_EXPOSURE_FILE, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.out is None:
        parser.exit(1, f"derive_route_exposure: the scenario {scenario.NAME} has no ROUTE_EXPOSURE_FILE\n")
    targets = json.loads(scenario.TARGETS_FILE.read_text(encoding="utf-8"))["features"]
    west, south, east, north = scenario.MAP_BBOX
    items = []
    for feature in targets:
        kind = wanted(feature["properties"])
        if kind is None or feature["geometry"]["type"] != "LineString":
            continue
        props = feature["properties"]
        for piece in pieces(feature["geometry"]["coordinates"]):
            if not (west <= middle(piece)[0] <= east and south <= middle(piece)[1] <= north):
                continue
            items.append({"kind": kind, "name": props.get("name"), "ref": props.get("ref"), "coords": piece, "middle": middle(piece)})
    lat = np.array([item["middle"][1] for item in items])
    lon = np.array([item["middle"][0] for item in items])
    northing, easting = sweref99tm(lat, lon)
    start, end = scenario.PLAYBACK_START, scenario.PLAYBACK_END
    hours = int((end - start).total_seconds() // 3600)
    frames = []
    day = start.date()
    while day <= (end - timedelta(seconds=1)).date():
        with urlopen(Request(day_url(day), headers={"User-Agent": USER_AGENT}), timeout=300) as response:
            archive = zipfile.ZipFile(io.BytesIO(response.read()))
        for name in sorted(archive.namelist()):
            moment = moment_of(name)
            if moment is None or not start <= moment < end:
                continue
            frames.append((moment, sample(archive.read(name), northing, easting)))
        print(f"{day}: {sum(1 for moment, _ in frames if moment.date() == day)} radar images", flush=True)
        day += timedelta(days=1)
    sums = hourly_sums(frames, start, hours)
    lowest = routes.EXPOSURE_THRESHOLDS_MM[0]
    kept = []
    for index, item in enumerate(items):
        if sums[-1, index] < lowest:
            continue
        kept.append({
            "kind": item["kind"], "name": item["name"], "ref": item["ref"],
            "coords": [[round(lat, 5), round(lon, 5)] for lon, lat in item["coords"]],
            "mm": [round(float(value), 1) for value in sums[:, index]],
        })
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "start_utc": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "hours": hours, "thresholds_mm": list(routes.EXPOSURE_THRESHOLDS_MM),
        "radar_images": len(frames), "pieces_counted": len(items),
        "processed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "processing": (f"OSM roads (motorway to tertiary, numbered unclassified) and railways outside tunnels in pieces of "
                       f"about {PIECE_KM:g} km; SMHI's radar composite every {STEP_MINUTES} minutes at each piece's middle, "
                       "Z = 200 R^1.6, summed from the playback's start; pieces below the lowest threshold left out"),
        "attribution": "SMHI öppna data, väderradar (CC BY 4.0 SE), regn beräknat; vägar och järnvägar © OpenStreetMap contributors",
        "pieces": kept,
    }, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{len(kept)} of {len(items)} pieces reach {lowest:g} mm -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
