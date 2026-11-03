"""The municipality's own GIS, read through its ArcGIS REST services, for what an alarm may threaten:
the protected objects (preschools, schools, health care, elderly care) and the buildings, with
MCF's 100-year flow. GIS is the default, as the one-pager says; OpenStreetMap only adds what the
municipality's services lack (the railway station, churches, and the roads and railways, whose
plan layers give no geometry), and says so.

What is kept follows the check of laws and rules on 2026-11-03 (CONTEXT.md, the register's R-DP-01,
R-GEO-02, R-CS-06 and R-CS-07): no addresses or property designations, no housing for people with
disabilities (left out until its security and data protection are reviewed, as the user decided),
no social services' premises, no water, sewage, power or other critical infrastructure beyond roads,
railways and bus stops, and nothing that may be a protected object. Internal use only: the data
stay in the unversioned data/monitoring/<area>/gis/ and are shown only on the monitoring's screens.
They are fetched again when older than MAX_AGE.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Callable
from urllib.parse import quote, urlencode

import numpy as np

from app.monitoring import geo

MAX_AGE = timedelta(days=7)
NEAR_KM = 1.0
PAGE = 1000

Fetch = Callable[[str], bytes]


def query_url(service: str, layer: int, offset: int, fields: str) -> str:
    params = {"where": "1=1", "outFields": fields, "returnGeometry": "true", "outSR": "4326", "geometryPrecision": "5",
              "resultOffset": offset, "resultRecordCount": PAGE, "f": "json"}
    # The service's name may hold Swedish letters (Primärkarta_Flen): the path is percent-encoded.
    return f"{quote(service, safe=':/')}/{layer}/query?{urlencode(params)}"


def features(service: str, layer: int, fetch: Fetch, fields: str = "") -> list[dict[str, Any]]:
    """Every feature of one layer, a page at a time."""
    found: list[dict[str, Any]] = []
    while True:
        data = json.loads(fetch(query_url(service, layer, len(found), fields)))
        if "error" in data:
            raise RuntimeError(f"{service}/{layer}: {data['error'].get('message')}")
        page = data.get("features") or []
        found.extend(page)
        if len(page) < PAGE and not data.get("exceededTransferLimit"):
            return found


def _point(geometry: dict[str, Any]) -> tuple[float, float] | None:
    if "x" in geometry:
        return round(geometry["y"], 5), round(geometry["x"], 5)
    if geometry.get("points"):  # a multipoint (the health care layers): its first point
        return round(geometry["points"][0][1], 5), round(geometry["points"][0][0], 5)
    rings = geometry.get("rings") or []
    if rings and rings[0]:
        ring = rings[0]
        return round(sum(p[1] for p in ring) / len(ring), 5), round(sum(p[0] for p in ring) / len(ring), 5)
    return None


def fetch_area(area: ModuleType, fetch: Fetch) -> dict[str, Any]:
    """The protected objects, buildings, transport and flood zone of the area, as kept."""
    facilities = []
    for item in area.GIS_FACILITIES:
        for feature in features(item["service"], item["layer"], fetch, ",".join(item["fields"])):
            values = feature.get("attributes") or {}
            if any(values.get(field) not in allowed for field, allowed in item.get("only", {}).items()):
                continue
            point = _point(feature.get("geometry") or {})
            if point:
                kind = item["category"] if "category_field" not in item else f"{item['category']}: {values.get(item['category_field'])}"
                facilities.append({"name": values.get(item["name_field"]) or kind, "category": kind, "group": item["group"],
                                   "latitude": point[0], "longitude": point[1], "source": item["source"]})
    # One school of several stages is one point per stage in the services: kept once.
    seen: set[tuple[str, str, float, float]] = set()
    facilities = [item for item in facilities
                  if (key := (item["name"], item["category"], round(item["latitude"], 3), round(item["longitude"], 3))) not in seen
                  and not seen.add(key)]
    buildings = [p for p in (_point(f.get("geometry") or {}) for f in features(area.GIS_BUILDINGS["service"],
                                                                               area.GIS_BUILDINGS["layer"], fetch)) if p]
    return {"fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "facilities": facilities,
            "buildings": buildings, "lines": osm_lines(area.OSM_TARGETS_FILE, area.OSM_ROAD_TYPES), "stops": [],
            "attribution": area.GIS_ATTRIBUTION}


def osm_lines(path: Path, road_types: dict[str, str]) -> list[dict[str, Any]]:
    """The roads and railways from the scenarios' OpenStreetMap targets, where the municipality's
    services give none: (kind, label with the road's number, [lat, lon] points)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    lines = []
    for feature in data.get("features") or []:
        values, geometry = feature.get("properties") or {}, feature.get("geometry") or {}
        if geometry.get("type") != "LineString":
            continue
        if values.get("kind") == "road" and values.get("type") in road_types:
            kind, label = "road", f"väg {values['ref']}" if values.get("ref") else road_types[values["type"]]
        elif values.get("kind") == "railway":
            kind, label = "rail", "järnväg"
        else:
            continue
        lines.append({"kind": kind, "label": label, "coords": [[round(lat, 5), round(lon, 5)] for lon, lat, *_ in geometry["coordinates"]]})
    return lines


def osm_additions(path: Path, types: dict[str, str]) -> list[dict[str, Any]]:
    """What the municipality's services lack, from the scenarios' OpenStreetMap targets."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    found = []
    for feature in data.get("features") or []:
        values = feature.get("properties") or {}
        category = types.get(values.get("type"))
        if values.get("kind") != "building" or not category:
            continue
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates")
        if geometry.get("type") == "Point":
            lat, lon = coords[1], coords[0]
        else:
            ring = geo.polygons(geometry)[0][0]
            lat, lon = sum(p[1] for p in ring) / len(ring), sum(p[0] for p in ring) / len(ring)
        found.append({"name": values.get("name") or category, "category": category, "group": "other",
                      "latitude": round(lat, 5), "longitude": round(lon, 5), "source": "© OpenStreetMap contributors"})
    return found


def places(path: Path, types: tuple[str, ...]) -> list[dict[str, Any]]:
    """The place names to label the maps with, from the scenarios' OpenStreetMap targets."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [{"name": f["properties"]["name"], "type": f["properties"]["type"], "latitude": f["geometry"]["coordinates"][1],
             "longitude": f["geometry"]["coordinates"][0]}
            for f in data.get("features") or []
            if (f.get("properties") or {}).get("kind") == "place" and f["properties"].get("type") in types and f["properties"].get("name")]


def inside(points: np.ndarray, polygons: list[list[list[list[float]]]], chunk: int = 2_000_000) -> np.ndarray:
    """Which of the (lat, lon) points lie in any of the polygons, holes left out: ray casting, for each
    ring only over the points inside its box, all its edges at once."""
    result = np.zeros(len(points), dtype=bool)
    if not len(points):
        return result
    lat, lon = points[:, 0], points[:, 1]
    for polygon in polygons:
        hits: dict[int, bool] = {}
        for index, ring in enumerate(polygon):
            ring_array = np.asarray(ring, dtype=float)[:, :2]
            west, south = ring_array.min(axis=0)
            east, north = ring_array.max(axis=0)
            candidates = np.nonzero((lon >= west) & (lon <= east) & (lat >= south) & (lat <= north))[0]
            if not candidates.size:
                continue
            x1, y1 = ring_array[:, 0], ring_array[:, 1]
            x2, y2 = np.roll(x1, -1), np.roll(y1, -1)
            keep = y1 != y2
            x1, y1, x2, y2 = x1[keep], y1[keep], x2[keep], y2[keep]
            step = max(1, chunk // max(len(x1), 1))
            for start in range(0, candidates.size, step):
                part = candidates[start:start + step]
                py, px = lat[part][:, None], lon[part][:, None]
                straddle = (y1 > py) != (y2 > py)
                crossing = (np.count_nonzero(straddle & (px < (x2 - x1) * (py - y1) / (y2 - y1) + x1), axis=1) % 2).astype(bool)
                for point, inner in zip(part, crossing):
                    if index == 0:
                        hits[int(point)] = bool(inner)
                    elif inner:
                        hits[int(point)] = False
        for point, inner in hits.items():
            if inner:
                result[point] = True
    return result


class Assets:
    """The area's GIS data, kept, and what lies near a point or in the flood zone."""

    def __init__(self, area: ModuleType, data_dir: Path, fetch: Fetch) -> None:
        self.area = area
        self.path = data_dir / "gis" / "assets.json"
        self.fetch = fetch
        self.data: dict[str, Any] | None = None
        self.flood: list[list[list[list[float]]]] = []
        self.in_flood: dict[str, Any] = {}

    def load(self, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        if self.data is None:
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.data = None
        fetched = self.data and datetime.fromisoformat(self.data["fetched_utc"].replace("Z", "+00:00"))
        if not self.data or now - fetched >= MAX_AGE:
            try:
                data = fetch_area(self.area, self.fetch)
            except Exception:
                if self.data:  # an old copy is better than none
                    return self.data
                raise
            data["facilities"] += osm_additions(self.area.OSM_TARGETS_FILE, self.area.OSM_ADDITIONS)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            self.data = data
            self.in_flood = {}
        if not self.in_flood:
            self._flood_zone()
        return self.data

    def _flood_zone(self) -> None:
        self.flood = []
        for path in self.area.FLOOD_ZONE_FILES:
            try:
                for feature in json.loads(Path(path).read_text(encoding="utf-8")).get("features") or []:
                    self.flood += geo.polygons(feature.get("geometry"))
            except (OSError, ValueError):
                continue
        data = self.data or {}
        points = lambda items: np.array([[i["latitude"], i["longitude"]] for i in items], dtype=float).reshape(-1, 2)  # noqa: E731
        buildings = np.array(data.get("buildings") or [], dtype=float).reshape(-1, 2)
        self.in_flood = {
            "facilities": [item for item, hit in zip(data.get("facilities", []), inside(points(data.get("facilities", [])), self.flood)) if hit],
            "buildings": int(inside(buildings, self.flood).sum()),
            "lines": self._lines_in_flood(data.get("lines", [])),
            "stops": [item for item, hit in zip(data.get("stops", []), inside(points(data.get("stops", [])), self.flood)) if hit],
        }

    def _lines_in_flood(self, lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """The lines with a point in the flood zone, all their points tested at once."""
        owners = np.array([index for index, line in enumerate(lines) for _ in line["coords"]], dtype=int)
        coords = np.array([point for line in lines for point in line["coords"]], dtype=float).reshape(-1, 2)
        hit = set(owners[inside(coords, self.flood)].tolist())
        return [line for index, line in enumerate(lines) if index in hit]

    def near(self, lat: float, lon: float, km: float = NEAR_KM) -> dict[str, Any]:
        """What lies within km of the point."""
        data = self.data or {}
        close = lambda a, o: geo.distance_km(lat, lon, a, o) <= km  # noqa: E731
        buildings = np.array(data.get("buildings") or [], dtype=float).reshape(-1, 2)
        if len(buildings):
            dlat = np.radians(buildings[:, 0] - lat)
            dlon = np.radians(buildings[:, 1] - lon) * np.cos(np.radians(lat))
            count = int((geo.EARTH_RADIUS_KM * np.hypot(dlat, dlon) <= km).sum())
        else:
            count = 0
        return {"within_km": km,
                "facilities": [item for item in data.get("facilities", []) if close(item["latitude"], item["longitude"])],
                "buildings": count,
                "lines": [line for line in data.get("lines", []) if any(close(a, o) for a, o in line["coords"])],
                "stops": [item for item in data.get("stops", []) if close(item["latitude"], item["longitude"])]}

    def exposure(self, candidate: dict[str, Any]) -> dict[str, Any] | None:
        """What an alarm may threaten: a high flow, the 100-year flow's zone; else what lies near its place."""
        if not self.data:
            return None
        if candidate["key"].startswith("flow-") and self.flood:
            found = {"within_km": None, "zone": "MCF:s klimatanpassade 100-årsflöde", **self.in_flood}
        elif candidate.get("latitude") is not None:
            found = self.near(candidate["latitude"], candidate["longitude"])
        else:
            return None
        return summarise(found, self.data.get("attribution"))


def summarise(found: dict[str, Any], attribution: str | None) -> dict[str, Any]:
    """The exposure as the screens and the briefing show it: the objects by name, the rest as counts."""
    roads = sorted({line["label"] for line in found["lines"] if line["kind"] == "road"})
    rails = sorted({line["label"] for line in found["lines"] if line["kind"] == "rail"})
    return {"where": found.get("zone") or f"inom {str(found['within_km']).replace('.', ',')} km",
            "facilities": [{"name": item["name"], "category": item["category"], "source": item["source"],
                            "latitude": item["latitude"], "longitude": item["longitude"]} for item in found["facilities"]],
            "buildings": found["buildings"], "roads": len([1 for line in found["lines"] if line["kind"] == "road"]),
            "road_kinds": roads, "railways": rails, "stops": len(found["stops"]), "attribution": attribution}


def public(data: dict[str, Any] | None, place_names: list[dict[str, Any]]) -> dict[str, Any]:
    """What the maps draw: the protected objects and the place names; not the buildings or lines."""
    return {"facilities": (data or {}).get("facilities", []), "places": place_names,
            "attribution": (data or {}).get("attribution")}
