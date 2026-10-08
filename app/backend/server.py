"""Backend for the demo map, for the scenario chosen in app/backend/scenario.py.

Serves the GUI, the FIRMS detections of the fire, a playback stream that sends
the detections to the GUI in compressed time (Server-Sent Events), the OSM
terrain layer, a proxy for Lantmäteriet services and the live readings of the
TechSeed IoT nodes (MQTT, app/backend/iot.py).

Run from the repository root:

    python3 -m app.backend.server
    python3 -m app.backend.server --scenario vastmanland2014

Only the Python standard library is used, except paho-mqtt for the IoT nodes
(optional; app/requirements-iot.txt).
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import mimetypes
import os
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import parse_qsl, urlsplit

from app.backend import assessment, detection, ems, flood_assessment, flood_sensors, forecast, hydro, iot, landsat, level_sensors, passes, lantmateriet, offline_tiles, radar, satellites, scenario, sensor_sim, spatial, wms
from app.backend.scenario_engine import DETECTION_AFTER, CommandError, ScenarioEngine
from app.backend.scenarios import AVAILABLE, DEFAULT
from tools.firms_extract import daily_summary, select_detections

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
TILES_DIR = Path(__file__).resolve().parents[2] / "data" / "tiles"
# Cesium terrain built by tools/build_terrain.py (not versioned).
TERRAIN_DIR = scenario.TERRAIN_DIR
TICK_SECONDS = 0.25
MIN_SPEED, MAX_SPEED = 60.0, 4 * 86400.0  # simulated seconds per real second


@lru_cache(maxsize=1)
def detections() -> tuple[dict[str, Any], ...]:
    kept, _, _ = select_detections(
        scenario.FIRMS_FILES, start=scenario.PERIOD_START, end=scenario.PERIOD_END, bbox=scenario.FIRE_BBOX,
    )
    return tuple(kept)


WEATHER_VALUES = ("temp_c", "rh_pct", "wind_speed_ms", "wind_dir_deg", "gust_ms", "precip_mm")


def distance_km(latitude: float, longitude: float) -> float:
    centre_lat, centre_lon = scenario.FIRE_CENTRE
    dy = (latitude - centre_lat) * 111.2
    dx = (longitude - centre_lon) * 111.2 * math.cos(math.radians(centre_lat))
    return round(math.hypot(dx, dy), 1)


@lru_cache(maxsize=1)
def weather() -> dict[str, Any]:
    """Hourly SMHI observations per station; values are numbers, missing values None."""
    catalogue = json.loads((scenario.WEATHER_DIR / "stations.json").read_text(encoding="utf-8"))
    stations = []
    for station in catalogue["stations"]:
        with (scenario.WEATHER_DIR / station["file"]).open(encoding="utf-8", newline="") as stream:
            observations = [
                {"time_utc": row["time_utc"], **{key: float(row[key]) if row[key] != "" else None for key in WEATHER_VALUES}}
                for row in csv.DictReader(stream)
            ]
        stations.append({
            "id": station["id"],
            "name": station["name"],
            "latitude": station["latitude"],
            "longitude": station["longitude"],
            "distance_km": distance_km(station["latitude"], station["longitude"]),
            "observations": observations,
        })
    stations.sort(key=lambda station: station["distance_km"])
    return {"source": catalogue["source"], "stations": stations}


# Smallest zoom at which a name is shown, by OSM place type; lakes go by their area.
LABEL_MIN_ZOOM = {"town": 7, "village": 9, "hamlet": 11, "neighbourhood": 12, "locality": 12, "isolated_dwelling": 13, "farm": 13}


def _ring_area_km2(ring: list[list[float]]) -> float:
    lat0 = sum(point[1] for point in ring) / len(ring)
    kx, ky = 111.32 * math.cos(math.radians(lat0)), 110.54
    return abs(sum(a[0] * kx * b[1] * ky - b[0] * kx * a[1] * ky for a, b in zip(ring, ring[1:] + ring[:1]))) / 2.0


@lru_cache(maxsize=1)
def labels() -> dict[str, Any]:
    """Place names (OSM places) and lake names (named water areas) as label points."""
    features = []
    targets = json.loads(scenario.TARGETS_FILE.read_text(encoding="utf-8"))
    for item in targets["features"]:
        props = item["properties"]
        if props["kind"] == "place" and props.get("name") and props["type"] in LABEL_MIN_ZOOM:
            features.append({"type": "Feature", "geometry": item["geometry"],
                             "properties": {"name": props["name"], "kind": props["type"], "min_zoom": LABEL_MIN_ZOOM[props["type"]]}})
    terrain = json.loads(scenario.TERRAIN_FILE.read_text(encoding="utf-8"))
    for item in terrain["features"]:
        props = item["properties"]
        if props["terrain"] != "vatten" or not props.get("name"):
            continue
        polygons = [item["geometry"]["coordinates"]] if item["geometry"]["type"] == "Polygon" else item["geometry"]["coordinates"]
        ring = max((polygon[0] for polygon in polygons), key=len)
        area = sum(_ring_area_km2(polygon[0]) for polygon in polygons)
        centre = [round(sum(p[0] for p in ring) / len(ring), 5), round(sum(p[1] for p in ring) / len(ring), 5)]
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": centre},
                         "properties": {"name": props["name"], "kind": "lake", "area_km2": round(area, 2),
                                        "min_zoom": 9 if area >= 5 else 11 if area >= 0.5 else 13}})
    return {"type": "FeatureCollection", "attribution": scenario.ATTRIBUTION["osm"], "features": features}


@lru_cache(maxsize=1)
def wind_field() -> dict[str, Any]:
    """ERA5-Land 10 m wind per grid point and hour, compact: one list per hour, in point order."""
    points: list[tuple[float, float]] = []
    sources: list[str] = []
    index: dict[tuple[float, float], int] = {}
    hours: dict[str, dict[int, tuple[float, int, float]]] = {}
    # ERA5-Land, and in some scenarios ERA5 over the sea where ERA5-Land has no values.
    files = [scenario.WIND_FILE] + ([scenario.WIND_SEA_FILE] if scenario.WIND_SEA_FILE and scenario.WIND_SEA_FILE.exists() else [])
    for path in files:
        with path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                point = (float(row["latitude"]), float(row["longitude"]))
                if point not in index:
                    index[point] = len(points)
                    points.append(point)
                    sources.append(row.get("source") or "ERA5-Land")
                hours.setdefault(row["time_utc"], {})[index[point]] = (
                    float(row["wind_speed_ms"]), int(row["wind_from_deg"]), float(row["t2m_c"]),
                )
    times = [moment for moment in sorted(hours) if len(hours[moment]) == len(points)]
    return {
        "source": scenario.ATTRIBUTION["era5_land"],
        "points": [list(point) for point in points],
        "sources": sources,  # per point: ERA5-Land, or ERA5 interpolated over the sea
        "times_utc": times,
        # [speed m/s, direction the wind blows from in degrees, 2 m temperature °C] per point
        "values": [[list(hours[moment][position]) for position in range(len(points))] for moment in times],
    }


@lru_cache(maxsize=1)
def synthetic_sensors() -> sensor_sim.SyntheticSensors | flood_sensors.FloodSensors | level_sensors.LevelSensors:
    """The incident's synthetic sensors: heat and smoke round the fire, overflow at the flood's stormwater points,
    or levels where roads cross a river flood's mapped area."""
    if not scenario.WILDFIRE and scenario.LEVEL_SENSOR_FILE:
        return level_sensors.LevelSensors(scenario.LEVEL_SENSOR_FILE, (hydro.stations() or {}).get("stations", ()))
    if not scenario.WILDFIRE:
        # The municipality's stormwater points, where the scenario has them; none otherwise.
        points = scenario.MUNICIPAL_DIR / "critical-stormwater.geojson" if scenario.MUNICIPAL_DIR else None
        return flood_sensors.FloodSensors(points, weather()["stations"],
                                          scenario.PLAYBACK_START, scenario.PLAYBACK_END)
    items = [(parse_utc(item["acq_datetime_utc"]), item["latitude"], item["longitude"]) for item in detections()]
    return sensor_sim.SyntheticSensors(items, wind_field(), scenario.FIRE_CENTRE)


def synthetic_at(state: dict[str, Any]) -> dict[str, Any]:
    """The synthetic sensors at the scenario clock, with mission control's sensor failures;
    none when mission control has switched IoT off."""
    if not state["status"]["iot"]:
        label = sensor_sim.LABEL if scenario.WILDFIRE else level_sensors.LABEL if scenario.LEVEL_SENSOR_FILE else flood_sensors.LABEL
        return {"label": label, "sensors": [], "confirms": 0, "operating": 0, "disabled": True}
    status = state["status"]
    return synthetic_sensors().at(parse_utc(state["clock_utc"]), status["failed_sensors"], status["placed_sensors"])


# Every screen's stream needs the assessor; the first one to connect builds it, the others wait.
_assessor_lock = threading.Lock()


@lru_cache(maxsize=1)
def _assessor() -> assessment.Assessor | flood_assessment.FloodAssessor:
    if not scenario.WILDFIRE:
        images = landsat.layer()
        return flood_assessment.FloodAssessor(weather()["stations"], scenario.SENTINEL1_ACQUISITIONS,
                                              images["scenes"] if images else [], scenario.FIRE_CENTRE,
                                              place_name=scenario.INCIDENT_PLACE, focus_land=scenario.FOCUS_LAND,
                                              gauges=scenario.RAIN_GAUGES, hydro=(hydro.stations() or {}).get("stations", ()))
    return assessment.Assessor(detections(), wind_field(), forecast.forecasts()["states"], scenario.FIRE_CENTRE)


def assessor() -> assessment.Assessor | flood_assessment.FloodAssessor:
    with _assessor_lock:
        return _assessor()


SLOW_BEFORE, SLOW_AFTER = timedelta(minutes=2), timedelta(minutes=6)


def slow_windows() -> list[tuple[datetime, datetime]]:
    """Two minutes before to six after each FIRMS pass (a granule lasts up to five) and each satellite image
    in the playback; for the flood, round every pass of a satellite over the incident (passes.py), as the
    satellite monitor shows them, since it has no detections to slow down for."""
    moments = {parse_utc(item["acq_datetime_utc"]) for item in detections()}
    moments |= {parse_utc(item["time_utc"]) for item in scenario.SENTINEL1_ACQUISITIONS}
    windows: list[tuple[datetime, datetime]] = []
    if not scenario.WILDFIRE:
        windows = [(begin - SLOW_BEFORE, end + SLOW_AFTER) for begin, end, _ in incident_passes()]
    scenes = landsat.layer()
    for scene in scenes["scenes"] if scenes else []:
        moment = parse_utc(scene["acquired_utc"])
        if scenario.PLAYBACK_START <= moment <= scenario.PLAYBACK_END:  # the scenes before and after are outside
            moments.add(moment)
    return sorted(windows + [(moment - SLOW_BEFORE, moment + SLOW_AFTER) for moment in moments])


@lru_cache(maxsize=1)
def incident_passes() -> tuple[tuple[datetime, datetime, str], ...]:
    """The satellites' passes over the incident in the playback (passes.py)."""
    data = satellites.satellites()
    if not data["available"]:
        return ()
    return tuple(passes.incident_passes(data["satellites"], scenario.PLAYBACK_START, scenario.PLAYBACK_END, scenario.FIRE_CENTRE))


def satellite_until(state: dict[str, Any]) -> datetime:
    """The last moment satellite data reaches the screens: the clock, or the start of a SATCOM outage."""
    clock = parse_utc(state["clock_utc"])
    down_since = state["status"]["satcom_down_since"]
    return clock if down_since is None else min(clock, parse_utc(down_since))


def assessment_at(state: dict[str, Any], synthetic: dict[str, Any] | None = None) -> dict[str, Any]:
    """The evidence-based assessment at the scenario clock."""
    return assessor().at(parse_utc(state["clock_utc"]), synthetic or synthetic_at(state), satellite_until(state))


@lru_cache(maxsize=1)
def firms_passes() -> detection.Detections:
    return detection.Detections(list(detections()))


def detection_info(state: dict[str, Any]) -> dict[str, Any] | None:
    """The pass and classification of the running detection sequence, if any."""
    running = state["status"]["detection"]
    if running is None:
        return None
    if not scenario.WILDFIRE:
        # The flood's sequence: a Sentinel-1 acquisition, judged with the sensors just after it (the zoom step's time).
        summary = assessor().pass_at(running["pass_utc"])
        if summary is None:
            return None
        after = {**state, "clock_utc": flood_assessment.format_utc(parse_utc(summary["pass_utc"]) + DETECTION_AFTER)}
        return {**running, "pass": summary, "classification": assessor().classify(summary, synthetic_at(after))}
    summary = firms_passes().pass_at(running["pass_utc"])
    if summary is None:
        return None
    return {**running, "pass": summary, "classification": detection.classify(firms_passes(), summary)}


@lru_cache(maxsize=1)
def timed_features() -> tuple[list[datetime], list[dict[str, Any]]]:
    """Detection times and features in time order, for slicing by the scenario clock."""
    items = detections()
    return [parse_utc(item["acq_datetime_utc"]) for item in items], [feature(item) for item in items]


def features_between(after: datetime | None, until: datetime) -> list[dict[str, Any]]:
    times, features = timed_features()
    low = 0 if after is None else bisect.bisect_right(times, after)
    return features[low:bisect.bisect_right(times, until)]


def feature(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [item["longitude"], item["latitude"]]},
        "properties": {key: value for key, value in item.items() if key not in {"latitude", "longitude", "source_file"}},
    }


def parse_utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def utc_text(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def playback_events(
    items: tuple[dict[str, Any], ...], start: datetime, end: datetime, speed: float, tick: float = TICK_SECONDS
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Events for one playback: `hotspot` per detection in time order, `clock` per tick, then `end`.

    Simulated time advances `speed * tick` seconds per tick; the caller sleeps `tick`
    between `clock` events. Detections before `start` are not sent again.
    """
    pending = [item for item in items if parse_utc(item["acq_datetime_utc"]) > start]
    index = 0
    clock = start
    while clock < end:
        clock = min(end, clock + timedelta(seconds=speed * tick))
        while index < len(pending) and parse_utc(pending[index]["acq_datetime_utc"]) <= clock:
            yield "hotspot", feature(pending[index])
            index += 1
        yield "clock", {"sim_time_utc": utc_text(clock)}
    yield "end", {"sim_time_utc": utc_text(end)}


def map_data() -> dict[str, str] | None:
    """The offline map's source and the date its OpenStreetMap data was fetched (tools/build_offline_tiles.py)."""
    try:
        source = json.loads((TILES_DIR / f"{Path(scenario.TILES_FILE).stem}.SOURCE.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return {"source": "OpenStreetMap", "date_utc": source.get("source_downloaded_utc", "")}


def base_maps(settings: lantmateriet.Settings) -> list[dict[str, Any]]:
    """The base maps mission control can tick (basemaps.js), in the order a map prefers them:
    Lantmäteriet's topowebb when enabled (2D only), the offline OSM map when it runs, OSM online."""
    items = [{"id": "topowebb", "label": "Lantmäteriet topowebb", "only_2d": True}] if settings.topowebb_enabled else []
    if offline_tiles.available():
        items.append({"id": "offline", "label": "Offline-karta (OSM, lokal)", "only_2d": False})
    items.append({"id": "online", "label": "OpenStreetMap online (kräver internet)", "only_2d": False})
    return items


def config(settings: lantmateriet.Settings) -> dict[str, Any]:
    min_lat, max_lat, min_lon, max_lon = scenario.VIEW_BBOX
    fire = scenario.FIRE_BBOX
    west, south, east, north = scenario.MAP_BBOX
    return {
        "scenario": scenario.NAME,
        # The incident's own modules run only for its kind; the words name its place on the screens.
        "incident": scenario.INCIDENT,
        "incident_place": scenario.INCIDENT_PLACE,
        "incident_area": scenario.INCIDENT_AREA,
        # The flood's words: the land the radar's water is counted on and the rain gauges.
        "focus_land": scenario.FOCUS_LAND,
        "rain_gauges": scenario.RAIN_GAUGES,
        "sensor_words": scenario.SENSOR_WORDS,  # the flood's sensors: overflow or level sensors
        # The fire's forecast weather station.
        "forecast_station": scenario.FORECAST_STATION,
        "title": scenario.TITLE,
        "data_label": scenario.DATA_LABEL,
        "control_label": scenario.CONTROL_LABEL,
        "camera_route": scenario.CAMERA_ROUTE,
        # The area of the offline map, the DEM and the Landsat images.
        "map_bounds": [[south, west], [north, east]],
        "view_bounds": [[min_lat, min_lon], [max_lat, max_lon]],
        "fire_centre": list(scenario.FIRE_CENTRE),
        "fire_selection_bounds": [[fire[0], fire[2]], [fire[1], fire[3]]],
        "playback": {
            "start_utc": utc_text(scenario.PLAYBACK_START),
            "end_utc": utc_text(scenario.PLAYBACK_END),
            "min_speed": MIN_SPEED,
            "max_speed": MAX_SPEED,
        },
        "attribution": scenario.ATTRIBUTION,
        "layers": {
            "terrain": "/api/layers/terrain",
            "offline_tiles": offline_tiles.available(),
            "map_data": map_data(),
            "terrain3d": (TERRAIN_DIR / "layer.json").is_file(),
            "satellites": satellites.satellites()["available"],
            "landsat": landsat.layer(),
            "radar": radar.layer(),
            "hydro": hydro.stations() is not None,  # SMHI's flows and lake levels at /api/hydro
            "ems": ems.perimeters() is not None,  # Copernicus EMS's perimeters of the fire at /api/ems
            "wms": wms.sources(),
            "lantmateriet_topowebb": settings.topowebb_enabled,
            "base_maps": base_maps(settings),
            "lantmateriet_fastighet": settings.fastighet_enabled,
            "lantmateriet_fastighet_layers": settings.fastighet_layers if settings.fastighet_enabled else "",
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "TechseedFireMap/0.1"
    settings = lantmateriet.Settings.from_environment()
    # One shared scenario for every screen; tests give their handler its own engine.
    engine = ScenarioEngine(scenario.PLAYBACK_START, scenario.PLAYBACK_END, area=scenario.VIEW_BBOX)
    # The prepared spatial questions run through one psql in the postgis service.
    psql = spatial.Psql()
    # Live readings of the real IoT nodes; main() connects it to the MQTT broker.
    sensors = iot.SensorStore()
    # When set, commands need this token in the X-Control-Token header (for a networked mission control).
    control_token = os.environ.get("SCENARIO_CONTROL_TOKEN") or None

    def handle(self) -> None:
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            # The browser cancelled the request, for example map tiles it no longer needs
            # while the camera moves; there is nobody left to answer and nothing to report.
            self.close_connection = True

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - signature of the base class
        # Keep the console readable; query strings may carry map parameters only.
        print(f"{self.address_string()} {format % args}")

    def send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, body: bytes, content_type: str, cache: str = "no-cache") -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - name required by BaseHTTPRequestHandler
        url = urlsplit(self.path)
        query = dict(parse_qsl(url.query))
        path = url.path
        if path == "/api/config":
            self.send_json(config(self.settings))
        elif path == "/api/hotspots":
            items = detections()
            self.send_json({
                "type": "FeatureCollection",
                "features": [feature(item) for item in items],
                "daily": daily_summary(items),
            })
        elif (path == "/api/forecast" and not scenario.WILDFIRE) or (path == "/api/wind" and not scenario.WIND_FILE.exists()):
            self.send_json({"error": "not_in_scenario"}, HTTPStatus.NOT_FOUND)
        elif path == "/api/forecast":
            self.send_json(forecast.forecasts())
        elif path == "/api/wind":
            self.send_json(wind_field())
        elif path == "/api/weather":
            self.send_json(weather())
        elif path == "/api/ems":
            data = ems.perimeters()
            self.send_json(data if data else {"error": "not_in_scenario"}, HTTPStatus.OK if data else HTTPStatus.NOT_FOUND)
        elif path == "/api/hydro":
            data = hydro.stations()
            self.send_json(data if data else {"error": "not_in_scenario"}, HTTPStatus.OK if data else HTTPStatus.NOT_FOUND)
        elif path == "/api/stream":
            self.stream(query)
        elif path == "/api/sensors":
            self.send_json(self.sensors.snapshot())
        elif path == "/api/satellites":
            self.send_json(satellites.satellites())
        elif path == "/api/questions":
            self.send_json([{"id": key, "question": value["question"]} for key, value in spatial.QUESTIONS.items()])
        elif path == "/api/ask":
            self.ask(query.get("q", ""))
        elif path == "/api/detection":
            self.send_json(detection_info(self.engine.snapshot()))
        elif path == "/api/assessment":
            state = self.engine.snapshot()
            self.send_json({**assessment_at(state), "clock_utc": state["clock_utc"]})
        elif path == "/api/sensors/synthetic":
            state = self.engine.snapshot()
            self.send_json({**synthetic_at(state), "clock_utc": state["clock_utc"]})
        elif path == "/api/scenario":
            self.send_json(self.engine.snapshot())
        elif path == "/api/scenario/stream":
            self.scenario_stream()
        elif path == "/api/layers/labels":
            self.send_json(labels())
        elif path == "/api/layers/terrain":
            self.send_bytes(scenario.TERRAIN_FILE.read_bytes(), "application/geo+json", "max-age=3600")
        elif path.startswith("/lm/"):
            self.lantmateriet(path, query)
        elif path.startswith("/tiles/"):
            self.offline_tile(path)
        elif path.startswith("/terrain/"):
            self.terrain(path)
        elif path.startswith("/wms/"):
            self.wms_map(path.removeprefix("/wms/"), query)
        elif path.startswith("/radar/"):
            body = radar.image(path.removeprefix("/radar/"))
            if body is None:
                self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            else:
                self.send_bytes(body, "image/png", "max-age=86400")
        elif path.startswith(("/landsat/", "/sentinel2/", "/sentinel1/")):
            prefix, _, name = path.lstrip("/").partition("/")
            directory = {"landsat": landsat.LANDSAT_DIR, "sentinel2": landsat.SENTINEL2_DIR, "sentinel1": landsat.SENTINEL1_DIR}[prefix]
            body = landsat.image(name, directory) if directory else None
            if body is None:
                self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            else:
                self.send_bytes(body, "image/png", "max-age=86400")
        else:
            self.static(path)

    def stream(self, query: dict[str, str]) -> None:
        try:
            speed = min(MAX_SPEED, max(MIN_SPEED, float(query.get("speed", 3600))))
            start = parse_utc(query["from"]) if query.get("from") else scenario.PLAYBACK_START
        except ValueError:
            self.send_json({"error": "invalid_playback_parameters"}, HTTPStatus.BAD_REQUEST)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            for event, data in playback_events(detections(), start, scenario.PLAYBACK_END, speed):
                self.wfile.write(f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8"))
                if event == "clock":
                    self.wfile.flush()
                    time.sleep(TICK_SECONDS)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # The GUI closes the stream to pause or restart the playback.
            return

    def do_POST(self) -> None:  # noqa: N802 - name required by BaseHTTPRequestHandler
        path = urlsplit(self.path).path
        if path not in ("/api/scenario/command", "/api/demo/menu"):
            self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        if self.control_token and self.headers.get("X-Control-Token") != self.control_token:
            self.send_json({"error": "control_token_required"}, HTTPStatus.FORBIDDEN)
            return
        if path == "/api/demo/menu":
            self.demo_menu()
            return
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= 4096:
            self.send_json({"error": "invalid_command"}, HTTPStatus.BAD_REQUEST)
            return
        try:
            body = json.loads(self.rfile.read(length))
            at = body.get("at")
            if body.get("command") == "satellite_detection" and not at:
                # The sequence is built on the next real pass after the scenario clock.
                passes = firms_passes() if scenario.WILDFIRE else assessor()
                upcoming = passes.next_pass(parse_utc(self.engine.snapshot()["clock_utc"]))
                if upcoming is None:
                    raise CommandError("no satellite pass with detections after the scenario clock")
                at = upcoming["pass_utc"]
            if body.get("command") == "image" and not landsat.choice_exists(str(body.get("target"))):
                raise CommandError("no such image in the scenario")
            if body.get("command") == "image_types" and not landsat.types_exist(str(body.get("target", ""))):
                raise CommandError("no such image type in the scenario")
            if body.get("command") == "base_maps":
                known = {item["id"] for item in base_maps(self.settings)}
                if not all(item in known for item in str(body.get("target", "")).split(",") if item):
                    raise CommandError("no such base map in the scenario")
            snapshot = self.engine.command(
                str(body.get("command")),
                at=at,
                speed=float(body["speed"]) if body.get("speed") is not None else None,
                target=str(body["target"]) if body.get("target") is not None else None,
                latitude=float(body["latitude"]) if body.get("latitude") is not None else None,
                longitude=float(body["longitude"]) if body.get("longitude") is not None else None,
            )
        except (ValueError, TypeError, AttributeError, CommandError) as exc:
            self.send_json({"error": "invalid_command", "detail": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self.send_json(snapshot)

    def demo_menu(self) -> None:
        """BYT DEMO in mission control: stop, so that tools/start_demo.py shows its menu again.
        It sets TECHSEED_DEMO_MENU_EXIT to the exit code it takes for that; without it there is no menu."""
        code = os.environ.get("TECHSEED_DEMO_MENU_EXIT")
        if not code:
            self.send_json({"error": "no_demo_menu", "detail": "backend är inte startad med tools.start_demo"}, HTTPStatus.CONFLICT)
            return
        self.send_json({"menu": True}, HTTPStatus.ACCEPTED)
        self.server.exit_code = int(code)
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def send_event(self, event: str, data: Any) -> None:
        self.wfile.write(f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8"))

    def scenario_stream(self) -> None:
        """Follow the shared scenario: a full `sync` on connect and after jumps, then
        `hotspot` events as the clock passes detections, a `scenario_event` per new
        mission-control event and a `state` event per tick. During a SATCOM outage
        the detections after its start are held back (`satcom_queue` says how many);
        when the link is back, `satcom_sync` summarises them and they follow as
        `hotspot` events. The real IoT nodes add a
        `sensor` event per new reading and a `sensor_health` event when a node goes
        offline or comes back; they follow real time, not the scenario clock. The
        synthetic sensors in the fire area follow the scenario clock: a
        `synthetic_sensors` event whenever their values change, and an `assessment`
        event whenever the assessment changes."""
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        last_clock: datetime | None = None
        last_visible: datetime | None = None
        last_queue: dict[str, Any] | None = None
        last_outage: Any = ...
        last_jump = None
        last_seq = 0
        last_reading = 0
        health: dict[tuple[str, str], bool] = {}
        last_synthetic: dict[str, Any] | None = None
        last_assessment: dict[str, Any] | None = None
        ended = False
        try:
            while True:
                state = self.engine.snapshot()
                clock = parse_utc(state["clock_utc"])
                visible = satellite_until(state)
                if last_jump != state["jump"] or (last_clock is not None and clock < last_clock):
                    # The sync carries the events in its state, so they are not sent again.
                    self.send_event("sync", {"state": state, "features": features_between(None, visible)})
                else:
                    for item in features_between(last_visible, visible):
                        self.send_event("hotspot", item)
                    for event in state["events"]:
                        if event["seq"] > last_seq:
                            self.send_event("scenario_event", event)
                    self.send_event("state", state)
                # After the restore event, so the screens show the SYNC last.
                outage = state["status"]["last_outage"]
                if last_outage is not ... and outage and outage != last_outage and state["status"]["satcom_up"]:
                    summary = assessor().outage(parse_utc(outage["from_utc"]), parse_utc(outage["to_utc"]))
                    self.send_event("satcom_sync", summary)
                last_outage = outage
                # The fire queues detections; the flood its radar acquisitions and optical images.
                queue = None if visible >= clock else {
                    "since_utc": state["status"]["satcom_down_since"],
                    "queued": len(features_between(visible, clock)) if scenario.WILDFIRE else len(assessor().outage(visible, clock)["passes"]),
                    "unit": "detektioner" if scenario.WILDFIRE else "satellitbilder",
                }
                if queue != last_queue:
                    self.send_event("satcom_queue", queue or {"since_utc": None, "queued": 0})
                    last_queue = queue
                last_seq = state["events"][-1]["seq"] if state["events"] else last_seq
                last_reading, health = self.send_sensor_events(last_reading, health)
                synthetic = synthetic_at(state)
                if synthetic != last_synthetic:
                    self.send_event("synthetic_sensors", {**synthetic, "clock_utc": state["clock_utc"]})
                    last_synthetic = synthetic
                judged = assessment_at(state, synthetic)
                if judged != last_assessment:
                    self.send_event("assessment", {**judged, "clock_utc": state["clock_utc"]})
                    last_assessment = judged
                if state["finished"] and not ended:
                    self.send_event("end", state)
                ended = state["finished"]
                last_clock, last_visible, last_jump = clock, visible, state["jump"]
                self.wfile.flush()
                time.sleep(TICK_SECONDS)
        except (BrokenPipeError, ConnectionResetError):
            return

    def ask(self, question_id: str) -> None:
        state = self.engine.snapshot()
        try:
            answer = spatial.ask(question_id, parse_utc(state["clock_utc"]), self.psql, lambda: assessment_at(state))
        except spatial.UnknownQuestion:
            self.send_json({"error": "unknown_question"}, HTTPStatus.BAD_REQUEST)
            return
        except spatial.Unavailable as exc:
            self.send_json({"error": "postgis_unavailable", "detail": str(exc)}, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        self.send_json({**answer, "clock_utc": state["clock_utc"]})

    def send_sensor_events(self, last_reading: int, health: dict[tuple[str, str], bool]) -> tuple[int, dict[tuple[str, str], bool]]:
        sensors = self.sensors.snapshot()["sensors"]
        for reading in sensors:
            key = (reading["node"], reading["kind"])
            if reading["seq"] > last_reading:
                self.send_event("sensor", reading)
            elif health.get(key) != reading["online"]:
                self.send_event("sensor_health", {"node": reading["node"], "kind": reading["kind"], "online": reading["online"]})
        return max([last_reading, *(reading["seq"] for reading in sensors)]), {
            (reading["node"], reading["kind"]): reading["online"] for reading in sensors
        }

    def wms_map(self, source: str, query: dict[str, str]) -> None:
        try:
            body, content_type = wms.get_map(source, query)
        except KeyError:
            self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        except ValueError as exc:
            self.send_json({"error": "invalid_wms_request", "detail": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except wms.UpstreamError as exc:
            self.send_json({"error": "wms_upstream_error", "status": exc.status}, HTTPStatus.BAD_GATEWAY)
            return
        self.send_bytes(body, content_type, "max-age=3600")

    def offline_tile(self, path: str) -> None:
        parts = path.strip("/").split("/")
        try:
            if len(parts) != 4:
                raise ValueError("bad tile path")
            body, content_type = offline_tiles.tile(int(parts[1]), int(parts[2]), int(parts[3].split(".")[0]))
        except ValueError:
            self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        except offline_tiles.Unavailable:
            self.send_json({"error": "offline_tiles_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        self.send_bytes(body, content_type, "max-age=86400")

    def terrain(self, path: str) -> None:
        target = (TERRAIN_DIR / path.removeprefix("/terrain/")).resolve()
        if not target.is_relative_to(TERRAIN_DIR.resolve()) or target.suffix not in {".json", ".terrain"} or not target.is_file():
            self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        if target.suffix == ".terrain":
            # ctb-tile writes the tiles gzipped; the browser unpacks them.
            self.send_header("Content-Type", "application/vnd.quantized-mesh;extensions=octvertexnormals")
            self.send_header("Content-Encoding", "gzip")
        else:
            self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=86400")
        self.end_headers()
        self.wfile.write(body)

    def lantmateriet(self, path: str, query: dict[str, str]) -> None:
        parts = path.strip("/").split("/")
        try:
            if parts[1:2] == ["topowebb"] and len(parts) == 5:
                body, content_type = lantmateriet.topowebb_tile(self.settings, int(parts[2]), int(parts[3]), int(parts[4].split(".")[0]))
            elif parts[1:] == ["fastighet"]:
                body, content_type = lantmateriet.fastighet_map(self.settings, query)
            else:
                self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
                return
        except lantmateriet.NotConfigured as exc:
            self.send_json({"error": "lantmateriet_not_configured", "service": str(exc)}, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        except ValueError:
            self.send_json({"error": "invalid_map_request"}, HTTPStatus.BAD_REQUEST)
            return
        except lantmateriet.UpstreamError as exc:
            self.send_json({"error": "lantmateriet_upstream_error", "status": exc.status}, HTTPStatus.BAD_GATEWAY)
            return
        self.send_bytes(body, content_type, "max-age=3600")

    def static(self, path: str) -> None:
        relative = "index.html" if path in {"", "/"} else path.lstrip("/")
        target = (FRONTEND_DIR / relative).resolve()
        if not target.is_relative_to(FRONTEND_DIR) or not target.is_file():
            self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type == "application/javascript":
            content_type += "; charset=utf-8"
        self.send_bytes(target.read_bytes(), content_type)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backend for the demo map")
    parser.add_argument("--scenario", choices=AVAILABLE, help=f"the scenario to run (default: TECHSEED_SCENARIO or {DEFAULT})")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--mqtt", default=os.environ.get("IOT_MQTT_BROKER", "127.0.0.1:1883"),
                        help="MQTT broker of the IoT nodes as host:port, or 'off'")
    args = parser.parse_args(argv)
    if args.scenario and args.scenario != scenario.NAME:
        # The modules read the scenario when they are imported: start again with it chosen.
        os.environ["TECHSEED_SCENARIO"] = args.scenario
        os.execv(sys.executable, [sys.executable, "-m", "app.backend.server", *(argv if argv is not None else sys.argv[1:])])
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    settings = Handler.settings
    print(f"{scenario.TITLE} ({scenario.NAME}) on http://{args.host}:{args.port}/ ({len(detections())} detections)")
    print(f"Lantmäteriet topowebb: {'on' if settings.topowebb_enabled else 'off'}, "
          f"fastighetsindelning: {'on' if settings.fastighet_enabled else 'off'}")
    if args.mqtt != "off":
        host, _, port = args.mqtt.rpartition(":")
        iot.start(Handler.sensors, host or "127.0.0.1", int(port))
    print(f"IoT: {Handler.sensors.detail}")
    # The fire's assessment needs the forecasts, which take a few seconds; compute them before the first screen connects.
    assessor()
    # The flood's map services are outside the demo: watch whether they answer.
    wms.watch()
    # Slow the playback down around every satellite pass in the data and the Landsat scene.
    Handler.engine.set_slow_windows(slow_windows())
    if not scenario.WILDFIRE:
        computed = "" if passes.available() else " – sgp4 saknas (app/requirements-orbits.txt), bara kända bildtagningar"
        print(f"Satellite passes over the incident: {len(incident_passes())}{computed}")
    # Start psql now, so the first question is answered without the start-up time.
    try:
        Handler.psql.query("SELECT 1")
        print("PostGIS: questions on")
    except spatial.Unavailable as exc:
        print(f"PostGIS: questions unavailable ({exc})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return getattr(server, "exit_code", 0)  # BYT DEMO's code for tools/start_demo.py


if __name__ == "__main__":
    raise SystemExit(main())
