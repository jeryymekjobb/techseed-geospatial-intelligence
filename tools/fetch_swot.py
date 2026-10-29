#!/usr/bin/env python3
"""Fetch SWOT's water surface heights of the scenario's lakes and river, and how much they changed.

SWOT (NASA and CNES, launched December 2022) measures the height of the water surface with a radar
interferometer over a 120 km wide swath. This tool finds in NASA's CMR catalogue the passes of its
lake product (L2_HR_LakeSP, the lakes of its prior lake database) and river product (L2_HR_RiverSP,
the reaches of the SWORD river database), version D, over SWOT_AREA: those during the playback, and
as the comparison those in the SWOT_BASELINE_DAYS before it. It downloads each once into RAW_DIR
with the user's NASA Earthdata account (a machine line for urs.earthdata.nasa.gov in ~/.netrc) and
cuts the shapefiles to the area with GDAL (geo_tools: Docker or native).

For every lake in MAP_BBOX and every reach of SWOT_RIVERS in SWOT_AREA that a playback pass measured,
it keeps the height, SWOT's own uncertainty and quality flag, the comparison passes' heights and
flags, and the change from the comparison's mean. Nothing is left out for its quality: each item
says which of its measurements are uncertain and why (uncertainty_notes), and `uncertain` flags it.
Lakes take their names from the scenario's OSM water areas, since SWOT's names lack å, ä and ö;
reaches are named by the nearest flow station or place. It writes SWOT_DIR/swot.json.

    TECHSEED_SCENARIO=ljungan-aug2023 .venv/bin/python -m tools.fetch_swot

NASA's data are free to use without restriction; PO.DAAC asks to be cited.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from app.backend import scenario
from tools import geo_tools
from tools.fetch_landsat_scene import run_gdal

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
COLLECTIONS = {"lake": "SWOT_L2_HR_LakeSP_D", "river": "SWOT_L2_HR_RiverSP_D"}
# The pixel cloud comes in tiles of about 64 km, so its granules tell which passes really cover the area;
# the lake and river products come by continent and would match every pass over Europe.
TILES = "SWOT_L2_HR_PIXC_D"
# The lake product's file for the prior lakes, and the river product's for the reaches.
KINDS = {"lake": "_LakeSP_Prior_", "river": "_RiverSP_Reach_"}
FILL = -1e9  # SWOT's fill value is -999999999999
QUALITY = {0: "god", 1: "osäker (suspect)", 2: "försämrad (degraded)", 3: "dålig (bad)"}
# A comparison whose passes differ more than this, a dark share above DARK_SHARE or a measurement
# uncertainty above SIGMA_M is noted as uncertain too.
SPREAD_M = 0.25
DARK_SHARE = 0.3
SIGMA_M = 0.25
# Lake outlines are simplified to about this many degrees (some 20 m).
SIMPLIFY_DEG = 0.0002
ATTRIBUTION = "NASA/CNES SWOT, Level 2 HR LakeSP och RiverSP version D (PO.DAAC)"


def search(collection: str, start: datetime, end: datetime, area: tuple[float, float, float, float]) -> list[dict[str, Any]]:
    query = {"short_name": collection, "temporal": f"{start:%Y-%m-%dT%H:%M:%SZ},{end:%Y-%m-%dT%H:%M:%SZ}",
             "bounding_box": ",".join(map(str, area)), "page_size": "2000"}
    response = requests.get(CMR + "?" + urllib.parse.urlencode(query), timeout=120)
    response.raise_for_status()
    return response.json()["feed"]["entry"]


def covering_passes(start: datetime, end: datetime, area: tuple[float, float, float, float]) -> set[str]:
    """"<cycle>_<pass>" of every pass whose pixel cloud tiles cover the area (SWOT_L2_HR_PIXC_<cycle>_<pass>_<tile>_…)."""
    return {"_".join(entry["title"].split("_")[4:6]) for entry in search(TILES, start, end, area)}


def granules(kind: str, start: datetime, end: datetime, area: tuple[float, float, float, float]) -> list[dict[str, Any]]:
    """The product's newest granule per cycle and pass between start and end that covers area: title, time, url."""
    passes = covering_passes(start, end, area)
    return [item for item in newest(kind, search(COLLECTIONS[kind], start, end, area)) if item["key"] in passes]


def newest(kind: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for entry in entries:
        title = entry["title"]
        if KINDS[kind] not in title:
            continue
        parts = title.split("_")  # ..._Prior_<cycle>_<pass>_<tile>_<start>_<end>_<CRID>_<counter>
        key = f"{parts[-7]}_{parts[-6]}"
        urls = [link["href"] for link in entry["links"] if link["href"].startswith("https://") and link["href"].endswith(f"{title}.zip")]
        if urls and (key not in found or (parts[-2], parts[-1]) > found[key]["version"]):
            found[key] = {"title": title, "key": key, "time_utc": entry["time_start"][:19] + "Z", "url": urls[0], "version": (parts[-2], parts[-1])}
    return sorted(found.values(), key=lambda item: item["time_utc"])


def download(session: requests.Session, url: str, target: Path) -> None:
    """Earthdata's archive redirects to its login, which requests answers from ~/.netrc."""
    part = target.with_suffix(".part")
    with session.get(url, stream=True, timeout=600) as response:
        response.raise_for_status()
        with part.open("wb") as stream:
            for chunk in response.iter_content(1 << 20):
                stream.write(chunk)
    part.rename(target)


def cut(raw: Path, title: str, area: tuple[float, float, float, float], tools: str) -> list[dict[str, Any]]:
    """The shapefile's features over area as GeoJSON features, lake outlines simplified."""
    west, south, east, north = area
    out = f"{title}.geojson"
    step = ["ogr2ogr", "-f", "GeoJSON", "-spat", str(west), str(south), str(east), str(north),
            *(["-simplify", str(SIMPLIFY_DEG)] if "_LakeSP_" in title else []), out, f"/vsizip/{title}.zip"]
    (raw / out).unlink(missing_ok=True)
    run = run_gdal(([step], []), raw, tools)
    if run.returncode != 0:
        raise RuntimeError(f"GDAL failed for {title}:\n{run.stderr[-2000:]}")
    features = json.loads((raw / out).read_text(encoding="utf-8"))["features"]
    (raw / out).unlink()
    return features


def valid(value: Any) -> bool:
    return value is not None and value > FILL


def day(time_utc: str) -> str:
    moment = datetime.strptime(time_utc[:10], "%Y-%m-%d")
    return f"{moment.day} {['januari', 'februari', 'mars', 'april', 'maj', 'juni', 'juli', 'augusti', 'september', 'oktober', 'november', 'december'][moment.month - 1]}"


def compare(observed: dict[str, Any], baseline: list[dict[str, Any]], kind: str) -> dict[str, Any] | None:
    """One lake's or reach's measurement at a playback pass against the comparison passes, with every
    reason its result is uncertain; None without a height at the pass or in the comparison."""
    quality_key = "quality_f" if kind == "lake" else "reach_q"
    if not valid(observed.get("wse")):
        return None
    before = [item for item in baseline if valid(item.get("wse"))]
    if not before:
        return None
    reference = statistics.mean(item["wse"] for item in before)
    notes = []
    quality = int(observed[quality_key]) if valid(observed.get(quality_key)) else None
    if quality != 0:
        notes.append(f"Mätningen {day(observed['time_str'])} har kvaliteten {QUALITY.get(quality, 'okänd')}.")
    for item in before:
        flag = int(item[quality_key]) if valid(item.get(quality_key)) else None
        if flag != 0:
            notes.append(f"Jämförelsen {day(item['time_str'])} har kvaliteten {QUALITY.get(flag, 'okänd')}.")
    spread = max(item["wse"] for item in before) - min(item["wse"] for item in before)
    if spread > SPREAD_M:
        notes.append(f"Jämförelsemätningarna skiljer {spread:.2f} m sinsemellan.".replace(".", ",", 1))
    sigma = observed.get("wse_u")
    if valid(sigma) and sigma > SIGMA_M:
        notes.append(f"SWOT:s egen osäkerhet är ±{sigma:.2f} m.".replace(".", ",", 1))
    dark = observed.get("dark_frac")
    if valid(dark) and dark > DARK_SHARE:
        notes.append(f"{round(dark * 100)} % av ytan var mörk i radarn och fick sin höjd uppskattad.")
    if kind == "lake" and valid(observed.get("partial_f")) and int(observed["partial_f"]) == 1:
        notes.append("Sjön sågs bara delvis.")
    if kind == "river" and not valid(observed.get("width")):
        notes.append("Ingen bredd kunde mätas; sträckan räknas som osäker.")
    return {"time_utc": observed["time_str"][:19] + "Z", "wse_m": round(observed["wse"], 2),
            "wse_u_m": round(sigma, 2) if valid(sigma) else None, "quality": quality,
            "baseline": [{"time_utc": item["time_str"][:19] + "Z", "wse_m": round(item["wse"], 2),
                          "quality": int(item[quality_key]) if valid(item.get(quality_key)) else None} for item in before],
            "change_m": round(observed["wse"] - reference, 2), "uncertain": bool(notes), "uncertainty_notes": notes}


def centre(geometry: dict[str, Any]) -> tuple[float, float]:
    """A lake outline's or reach line's mean point, [lat, lon]."""
    points: list[list[float]] = []
    def walk(item: Any) -> None:
        if item and isinstance(item[0], (int, float)):
            points.append(item)
        else:
            for part in item:
                walk(part)
    walk(geometry["coordinates"])
    return statistics.mean(point[1] for point in points), statistics.mean(point[0] for point in points)


def distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot((a[0] - b[0]) * 111.2, (a[1] - b[1]) * 111.2 * math.cos(math.radians(a[0])))


def osm_lake_name(point: tuple[float, float], lakes: list[tuple[str, tuple[float, float], float]]) -> str | None:
    """The named OSM water area whose centre is nearest, within its own size or 1 km."""
    best = min(lakes, key=lambda lake: distance_km(point, lake[1]), default=None)
    if best and distance_km(point, best[1]) <= max(1.0, math.sqrt(best[2])):
        return best[0]
    return None


def place_name(point: tuple[float, float], stations: list[tuple[str, tuple[float, float]]],
               places: list[tuple[str, tuple[float, float]]]) -> str | None:
    """The nearest flow station within 10 km, else the nearest place within 8 km."""
    for names, limit in ((stations, 10.0), (places, 8.0)):
        best = min(names, key=lambda item: distance_km(point, item[1]), default=None)
        if best and distance_km(point, best[1]) <= limit:
            return best[0]
    return None


def osm_names() -> tuple[list[tuple[str, tuple[float, float], float]], list[tuple[str, tuple[float, float]]]]:
    lakes, places = [], []
    terrain = json.loads(Path(scenario.TERRAIN_FILE).read_text(encoding="utf-8"))
    for item in terrain["features"]:
        props = item["properties"]
        if props.get("terrain") == "vatten" and props.get("name"):
            lat, lon = centre(item["geometry"])
            ring = item["geometry"]["coordinates"][0] if item["geometry"]["type"] == "Polygon" else item["geometry"]["coordinates"][0][0]
            width = (max(p[0] for p in ring) - min(p[0] for p in ring)) * 111.2 * math.cos(math.radians(lat))
            height = (max(p[1] for p in ring) - min(p[1] for p in ring)) * 111.2
            lakes.append((props["name"], (lat, lon), width * height))
    targets = json.loads(Path(scenario.TARGETS_FILE).read_text(encoding="utf-8"))
    for item in targets["features"]:
        props = item["properties"]
        if props.get("kind") == "place" and props.get("name") and props.get("type") in ("town", "village", "city"):
            lon, lat = item["geometry"]["coordinates"][:2]
            places.append((props["name"], (lat, lon)))
    return lakes, places


def flow_stations() -> list[tuple[str, tuple[float, float]]]:
    path = Path(scenario.HYDRO_DIR) / "stations.json" if scenario.HYDRO_DIR else None
    if path is None or not path.is_file():
        return []
    return [(item["name"].split(" (")[0], (item["latitude"], item["longitude"])) for item in json.loads(path.read_text(encoding="utf-8"))["stations"]]


def inside(point: tuple[float, float], bbox: tuple[float, float, float, float]) -> bool:
    west, south, east, north = bbox
    return west <= point[1] <= east and south <= point[0] <= north


def lines(geometry: dict[str, Any]) -> list[list[list[float]]]:
    """A reach's line(s) or a lake's outer rings as [lat, lon] lists, rounded."""
    coordinates = geometry["coordinates"]
    if geometry["type"] == "LineString":
        parts = [coordinates]
    elif geometry["type"] == "MultiLineString":
        parts = coordinates
    elif geometry["type"] == "Polygon":
        parts = [coordinates[0]]
    else:
        parts = [polygon[0] for polygon in coordinates]
    return [[[round(point[1], 5), round(point[0], 5)] for point in part] for part in parts]


def items(kind: str, observed: list[dict[str, Any]], baseline: list[list[dict[str, Any]]], names: dict[str, Any]) -> list[dict[str, Any]]:
    key = "lake_id" if kind == "lake" else "reach_id"
    before: dict[str, list[dict[str, Any]]] = {}
    for features in baseline:
        for feature in features:
            before.setdefault(feature["properties"][key], []).append(feature["properties"])
    result = []
    for feature in observed:
        props = feature["properties"]
        if feature["geometry"] is None:
            continue
        point = centre(feature["geometry"])
        if kind == "lake" and not inside(point, scenario.MAP_BBOX):
            continue
        if kind == "river" and props.get("river_name") not in scenario.SWOT_RIVERS:
            continue
        measured = compare(props, before.get(props[key], []), kind)
        if measured is None:
            continue
        if kind == "lake":
            name = osm_lake_name(point, names["lakes"])
            area = props.get("area_total")
            extra = {"name": name, "area_km2": round(area, 2) if valid(area) else None}
        else:
            near = place_name(point, names["stations"], names["places"])
            extra = {"name": f"{props['river_name']} vid {near}" if near else props["river_name"],
                     "width_m": round(props["width"]) if valid(props.get("width")) else None}
        result.append({"kind": kind, "id": props[key], **extra, "latitude": round(point[0], 5), "longitude": round(point[1], 5),
                       "lines": lines(feature["geometry"]), **measured})
    return sorted(result, key=lambda item: (item["kind"], item["longitude"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--out", type=Path, default=scenario.SWOT_DIR)
    geo_tools.add_argument(parser)
    args = parser.parse_args(argv)
    if args.out is None or scenario.SWOT_AREA is None:
        parser.exit(1, f"fetch_swot: the scenario {scenario.NAME} has no SWOT heights\n")
    tools = geo_tools.choice(args.tools)
    raw = args.out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    start, end = scenario.PLAYBACK_START, scenario.PLAYBACK_END
    first = start - timedelta(days=scenario.SWOT_BASELINE_DAYS)
    session = requests.Session()  # keeps Earthdata's login cookie between the downloads
    names = dict(zip(("lakes", "places"), osm_names()), stations=flow_stations())
    result: dict[str, Any] = {"source": ATTRIBUTION, "baseline_passes": [], "passes": [], "items": []}
    for kind in ("lake", "river"):
        found = granules(kind, first, end, scenario.SWOT_AREA)
        features = {}
        for granule in found:
            archive = raw / f"{granule['title']}.zip"
            if not archive.is_file():
                print(f"fetch_swot: downloading {granule['title']}", flush=True)
                download(session, granule["url"], archive)
            features[granule["title"]] = cut(raw, granule["title"], scenario.SWOT_AREA, tools)
        baseline = [features[g["title"]] for g in found if g["time_utc"] < f"{start:%Y-%m-%dT%H:%M:%SZ}"]
        for granule in found:
            if granule["time_utc"] < f"{start:%Y-%m-%dT%H:%M:%SZ}":
                result["baseline_passes"].append({"kind": kind, "time_utc": granule["time_utc"], "product": granule["title"]})
                continue
            measured = items(kind, features[granule["title"]], baseline, names)
            print(f"fetch_swot: {granule['title']}: {len(measured)} {kind} items", flush=True)
            if measured:
                result["passes"].append({"kind": kind, "time_utc": granule["time_utc"], "product": granule["title"]})
                result["items"].extend(measured)
    if not result["items"]:
        parser.exit(1, "fetch_swot: SWOT measured no lake or reach of the scenario during the playback\n")
    result["fetched_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (args.out / "swot.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(f"fetch_swot: wrote {len(result['items'])} items to {args.out / 'swot.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
