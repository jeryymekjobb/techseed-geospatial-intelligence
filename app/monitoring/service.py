"""The monitoring service: a poll every POLL_SECONDS of the live sources and the inbox, the rules,
the alarms, and a web server on 127.0.0.1 for the three screens, at the demos' paths so that
tools/open_screens.py places them as the demos': the main screen with the 3D globe (/3d.html), the
satellite monitor (/monitor.html) and mission control with the alarms (/control.html). VISA 2D /
VISA 3D in mission control switches the main screen between the globe and the 2D map (/2d.html),
which follow /api/view as the scenarios' main screen follows mission control's view.

    .venv/bin/python -m app.monitoring --area flenkommun [--port 8770] [--once] [--data-dir DIR]

tools/start_demo.py starts it from the start page (Övervakning) on the demos' port; BYT in mission
control then stops it with TECHSEED_DEMO_MENU_EXIT and the start page comes back. --once polls once,
prints a summary and exits. Its log is printed and written to data/monitoring/<area>/monitor.log;
--data-dir keeps the state, inbox and log elsewhere, for a trial.

The base maps are the demos': the municipality's map kept locally (/basemap/<id>/), the offline
OpenStreetMap from the tiles service (/tiles/) and its road numbers and railway tunnels
(/tiles-overlay/; app/backend/offline_tiles.py); online OpenStreetMap only when neither answers.
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import mimetypes
import os
import re
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import unquote, urlsplit

from app.backend import lantmateriet, offline_tiles
from app.backend import iot
from app.backend.scenarios import REPO_ROOT
from app.monitoring import (areas, briefing, events, geo, gis, levels, meteosat, radar, rules, satellites, sentinel1, sentinel2,
                            sources, weather)
from app.monitoring.alarms import Store

log = logging.getLogger("app.monitoring")
WEB_DIR = Path(__file__).resolve().parent / "web"
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
VENDOR_DIR = FRONTEND_DIR / "vendor"
VENDOR_LIBRARIES = ("leaflet-1.9.4", "cesium-1.146.0", "satellite.js-7.1.0")
HTML, JS, CSS = "text/html; charset=utf-8", "text/javascript; charset=utf-8", "text/css; charset=utf-8"
# The screens at the demos' paths, and the demos' own orbit and satellite-monitor code and styles.
STATIC = {"/control.html": (WEB_DIR / "control.html", HTML), "/control.js": (WEB_DIR / "control.js", JS),
          "/control.css": (WEB_DIR / "control.css", CSS), "/3d.html": (WEB_DIR / "globe.html", HTML),
          "/globe.js": (WEB_DIR / "globe.js", JS), "/globe.css": (WEB_DIR / "globe.css", CSS),
          "/2d.html": (WEB_DIR / "map2d.html", HTML), "/map2d.js": (WEB_DIR / "map2d.js", JS),
          "/monitor.html": (WEB_DIR / "satellites.html", HTML), "/satellites.js": (WEB_DIR / "satellites.js", JS),
          "/orbits.js": (FRONTEND_DIR / "orbits.js", JS), "/wind_barbs.js": (FRONTEND_DIR / "wind_barbs.js", JS), "/satmonitor.js": (FRONTEND_DIR / "satmonitor.js", JS),
          "/credits.js": (FRONTEND_DIR / "credits.js", JS),
          "/styles.css": (FRONTEND_DIR / "styles.css", CSS)}
TILE = re.compile(r"/(tiles|tiles-overlay)/(\d{1,2})/(\d+)/(\d+)\.png")
BASEMAP_TILE = re.compile(r"/basemap/([a-z0-9]+)/(\d{1,2})/(\d+)/(\d+)\.png")
# The map layers mission control switches on the main screen, and whether each starts on.
LAYERS = {"municipal": True, "flood": True, "radar": True, "wind": True, "chart": False, "facilities": True, "names": True,
          "stations": True, "firms": True, "satellite": False, "s1radar": False, "s1water": True,
          "s1wetness": False, "landsat": False, "flood_highest": False, "skyfall30": False, "skyfall100": False, "skyfall500": False,
          # One switch for every simulated sensor: the level sensors (levels.py) and the IoT nodes not marked real.
          "simulated": True}
# OpenStreetMap's standard map outside the municipality, the one-pager's fallback where there is no
# GIS map: it has land cover at every zoom and no edge; the demos' offline map takes its place only
# when it does not answer.
ONLINE_OSM = {"url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png", "attribution": "© OpenStreetMap contributors"}


class Monitor:
    """One area's sources, rules and alarms."""

    def __init__(self, area: ModuleType, fetch: sources.Fetch = sources.fetch_url, data_dir: Path | None = None,
                 post: sentinel2.Post = sentinel2.post_json) -> None:
        self.area = area
        self.fetch = fetch
        self.data_dir = data_dir or area.DATA_DIR
        self.store = Store(self.data_dir / "state.json")
        self.inbox = self.data_dir / "inbox"
        self.poll_lock = threading.Lock()
        # The main screen's map chosen in mission control, "3d" or "2d"; it starts on the globe.
        self.view = "3d"
        self.radar = radar.Radar(area.BBOX, fetch)
        self.weather = weather.Weather(area.BBOX, fetch)
        self.assets = gis.Assets(area, self.data_dir, fetch) if hasattr(area, "GIS_FACILITIES") else None
        self.image = sentinel2.Latest(area.BBOX, self.data_dir, fetch, post)
        self.landsat = sentinel2.Latest(area.BBOX, self.data_dir, fetch, post, kind=sentinel2.LANDSAT)
        self.terrain_dir: Path | None = getattr(area, "TERRAIN_DIR", None)
        # Lantmäteriet's Topografisk webbkarta as the base map where the municipality has none of its own
        # (LANTMATERIET_BASEMAP), once the Geotorget settings are in ~/.lantmateriet or the environment.
        self.lantmateriet = lantmateriet.Settings.from_file_or_environment()
        # The scenarios' simulated level sensors (levels.py) and Meteosat's cloud mask (meteosat.py).
        # The sensors follow a monitored flow station, or a sea level station as "sea-<station>".
        self.levels = levels.load(getattr(area, "LEVEL_SENSOR_FILE", None),
                                  set(area.FLOW_STATIONS) | {f"sea-{key}" for key in getattr(area, "SEA_LEVEL_STATIONS", {})},
                                  getattr(area, "LEVEL_SENSOR_STATIONS", {}))
        self.clouds = meteosat.CloudMask(area.BBOX, self.data_dir) if getattr(area, "METEOSAT_CLM", False) else None
        # The sea is known water too where the area's offline map has OSM's coastline (build_offline_tiles.py --area).
        self.radar_pass = sentinel1.Latest(area.BBOX, self.data_dir, getattr(area, "TERRAIN_FILE", None), fetch, post,
                                           REPO_ROOT / "data" / "osm" / f"{self.data_dir.name}-coastline" / "water_polygons.shp")
        # The IoT nodes, as the demos' (app/backend/iot.py): MQTT techseed/<node>/<kind>, simulated
        # unless a node says otherwise; connected by main() when a broker is given.
        self.sensors = iot.SensorStore()
        self.places = gis.places(area.OSM_TARGETS_FILE, area.PLACE_TYPES) if hasattr(area, "OSM_TARGETS_FILE") else []
        # Mission control's map layers: shown on the main screen or not; as in the scenarios, the
        # weather chart and the satellite image start off.
        self.layers = dict(LAYERS)
        # UPPLÄSNING: new alarms read aloud (app/backend/speech.py); off at the start, as in the scenarios.
        self.speech = False
        self.speaker: Any = None
        # SPARA INSTÄLLNINGAR in mission control: the display settings the monitoring starts with, as the
        # scenarios' SPARA PROFIL; in the unversioned data directory, not the repository.
        self.settings_file = self.data_dir / "settings.json"
        saved = self.saved_settings()
        if saved:
            self.layers.update(saved["layers"])
            self.view, self.speech = saved["view"], saved["speech"]

    def settings(self) -> dict[str, Any]:
        """The display settings in use: the map layers, the simulated sensors, 2D or 3D and UPPLÄSNING."""
        return {"layers": dict(self.layers), "view": self.view, "speech": self.speech}

    def saved_settings(self) -> dict[str, Any] | None:
        """The saved settings, of known layers and values only, or None."""
        try:
            data = json.loads(self.settings_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        layers = data.get("layers") if isinstance(data.get("layers"), dict) else {}
        return {"layers": {key: value for key, value in layers.items() if key in LAYERS and isinstance(value, bool)},
                "view": data.get("view") if data.get("view") in ("2d", "3d") else "3d",
                "speech": data.get("speech") if isinstance(data.get("speech"), bool) else False,
                "saved_utc": data.get("saved_utc")}

    def save_settings(self) -> dict[str, Any]:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        data = {**self.settings(), "saved_utc": sources.utc_text(datetime.now(timezone.utc))}
        self.settings_file.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return self.settings_status()

    def settings_status(self) -> dict[str, Any]:
        """Whether the settings in use differ from those the monitoring starts with (the saved ones, else
        the defaults), for mission control's button."""
        saved = self.saved_settings()
        start = ({"layers": {**LAYERS, **saved["layers"]}, "view": saved["view"], "speech": saved["speech"]} if saved
                 else {"layers": dict(LAYERS), "view": "3d", "speech": False})
        return {"saved_utc": saved["saved_utc"] if saved else None, "unsaved": self.settings() != start}

    def _firms(self) -> list[dict[str, Any]]:
        key = sources.firms_key()
        try:
            return sources.read_firms(key, self.area.FIRMS_SOURCES, self.area.BBOX, self.area.FIRMS_DAYS, self.fetch)
        except Exception as error:  # noqa: BLE001 - the key must not reach the log or the page
            raise RuntimeError(str(error).replace(key, "<key>")) from None

    def poll(self) -> dict[str, Any]:
        """Read every source and the inbox, run the rules and update the alarms."""
        with self.poll_lock:
            area, fetch = self.area, self.fetch
            results: dict[str, sources.Result] = {}
            results["mcf_border"] = sources.guarded(
                "mcf_border", lambda: [sources.cached_border(area.MUNICIPALITY_CODE, self.data_dir / "border.geojson", fetch)])
            border = results["mcf_border"].items[0] if results["mcf_border"].items else None
            stats = sources.guarded("smhi_flow_statistics", lambda: [sources.cached_statistics(
                area.FLOW_STATIONS, area.FLOW_HIGH_PERCENTILE, self.data_dir / "flow-statistics.json", fetch)])
            results["smhi_flow"] = sources.guarded("smhi_flow", lambda: sources.read_flows(area.FLOW_STATIONS, fetch))
            silent = [item["name"] for item in results["smhi_flow"].items if not item["readings"]]
            if silent:
                results["smhi_flow"].note = "inga värden senaste dygnet: " + ", ".join(silent)
            results["smhi_rain"] = sources.guarded("smhi_rain", lambda: sources.read_rain(area.RAIN_STATIONS, fetch))
            if getattr(area, "WATER_LEVEL_STATIONS", None):
                results["smhi_water_level"] = sources.guarded("smhi_water_level", lambda: sources.read_water_levels(
                    area.WATER_LEVEL_STATIONS, fetch, self.data_dir / "water-level-records.json"))
            if getattr(area, "SEA_LEVEL_STATIONS", None):
                results["smhi_sea_level"] = sources.guarded("smhi_sea_level",
                                                            lambda: sources.read_sea_level(area.SEA_LEVEL_STATIONS, fetch))
            results["smhi_warnings"] = sources.guarded(
                "smhi_warnings", lambda: sources.read_warnings(area.SMHI_COUNTY_ID, border, fetch))
            results["smhi_radar"] = sources.guarded("smhi_radar", lambda: [self.radar.update(border)])
            results["smhi_grid"] = sources.guarded("smhi_grid", lambda: [self.weather.update()] and [self.weather.summary()])
            results["smhi_fire_risk"] = sources.guarded(
                "smhi_fire_risk", lambda: sources.read_fire_risk(*area.FIRE_RISK_POINT, fetch))
            results["smhi_forecast"] = sources.guarded("smhi_forecast", lambda: sources.read_forecast(*area.FORECAST_POINT, fetch))
            results["sentinel2"] = sources.guarded("sentinel2", lambda: [meta] if (meta := self.image.update()) else [])
            results["landsat"] = sources.guarded("landsat", lambda: [meta] if (meta := self.landsat.update()) else [])
            if self.clouds:
                results["meteosat_clm"] = sources.guarded("meteosat_clm", lambda: [meta] if (meta := self.clouds.update()) else [])
            results["sentinel1"] = sources.guarded("sentinel1", lambda: [meta] if (meta := self.radar_pass.update()) else [])
            results["smhi_stations"] = sources.guarded(
                "smhi_stations", lambda: sources.read_weather_stations(getattr(area, "WEATHER_STATIONS", {}), fetch))
            results["krisinformation"] = sources.guarded(
                "krisinformation", lambda: sources.read_krisinformation(area.KRISINFO_WORDS, fetch))
            results["mcf_fire_ban"] = sources.guarded("mcf_fire_ban", lambda: sources.read_fire_ban(area.MUNICIPALITY_CODE, fetch))
            results["firms"] = sources.guarded("firms", self._firms)
            batch = events.read_inbox(self.inbox)
            recent = self.store.add_events([event.as_json() for event in batch.events],
                                           [refusal.as_json() for refusal in batch.refused])
            poll = {"border": border, "flow_stats": stats.items[0] if stats.items else {},
                    "flows": results["smhi_flow"].items, "rain": results["smhi_rain"].items,
                    "warnings": results["smhi_warnings"].items, "krisinfo": results["krisinformation"].items,
                    "fire_ban": results["mcf_fire_ban"].items, "firms": results["firms"].items,
                    "radar": results["smhi_radar"].items[0] if results["smhi_radar"].items else None,
                    "fire_risk": results["smhi_fire_risk"].items, "forecast": results["smhi_forecast"].items,
                    "weather_stations": results["smhi_stations"].items,
                    "sea_level": results["smhi_sea_level"].items if "smhi_sea_level" in results else [],
                    "water_levels": results["smhi_water_level"].items if "smhi_water_level" in results else []}
            assets = sources.guarded("gis", lambda: [self.assets.load()] if self.assets else [])
            candidates, filtered = rules.detect(poll, recent, area)
            # What each alarm may threaten, from the municipality's GIS (gis.py).
            if assets.ok and self.assets:
                for candidate in candidates:
                    candidate.exposure = self.assets.exposure(candidate.as_json())
            status = [result.as_json() for result in (*results.values(), stats, assets)]
            status.append({"source": "inbox", "ok": True, "fetched_utc": sources.utc_text(datetime.now(timezone.utc)), "count": len(batch.events),
                           "error": None, "note": f"{len(batch.refused)} avvisade rader" if batch.refused else None,
                           "attribution": "Händelser in (inkorgen)"})
            raised = self.store.apply(candidates, status, filtered, self._context(poll, stats))
            if self.speech and raised:
                self.say([f"{'Simulerat larm' if alarm['simulated'] else 'Nytt larm'} i {area.NAME}: {alarm['title']}."
                          for alarm in raised])
            for result in status:
                if not result["ok"]:
                    log.warning("Källa %s: %s", result["source"], result["error"])
            log.info("Avläsning klar: %d larmkandidater, %d nya händelser, %d avvisade rader",
                     len(candidates), len(batch.events), len(batch.refused))
            return {"candidates": [candidate.as_json() for candidate in candidates], "filtered": filtered, "sources": status,
                    "events": len(batch.events), "refused": len(batch.refused)}

    def _context(self, poll: dict[str, Any], stats: sources.Result) -> dict[str, Any]:
        limits = stats.items[0] if stats.items else {}
        # The flows with their latest day for mission control's charts.
        flows = [{"station": item["station"], "name": item["name"], "latitude": item["latitude"], "longitude": item["longitude"],
                  "value": item["readings"][-1]["value"], "time_utc": item["readings"][-1]["time_utc"],
                  "quality": item["readings"][-1]["quality"],
                  "limits": None if (limits.get(item["station"]) or {}).get("missing") else limits.get(item["station"]),
                  "series": [{"time_utc": reading["time_utc"], "value": reading["value"]} for reading in item["readings"]]}
                 for item in poll["flows"] if item["readings"]]
        return {"border": poll["border"], "flows": flows, "rain": poll["rain"], "warnings": poll["warnings"],
                "fire_ban": poll["fire_ban"], "news": [item for item in poll["krisinfo"] if item["kind"] == "news"],
                "firms": poll["firms"], "radar": poll["radar"], "fire_risk": poll["fire_risk"], "forecast": poll["forecast"],
                "weather": self.weather.summary(), "satellite_image": self.image.meta, "landsat_image": self.landsat.meta,
                "radar_pass": self.radar_pass.meta, "cloud_mask": self.clouds.meta if self.clouds else None,
                "level_sensors": levels.readings(self.levels, poll["flows"], limits, poll.get("sea_level", []),
                                                 getattr(self.area, "SEA_LEVEL_HIGH_CM", None)),
                "sea_level": [{**gauge, "limit_cm": getattr(self.area, "SEA_LEVEL_HIGH_CM", None)} for gauge in poll.get("sea_level", [])],
                "water_levels": poll.get("water_levels", []),
                # Every station that gave no value lately, shown grey and listed in mission control as a hint it may be out of order.
                "silent": self._silent(poll),
                "weather_stations": poll.get("weather_stations", [])}

    @staticmethod
    def _silent(poll: dict[str, Any]) -> list[dict[str, Any]]:
        kinds = (("flows", "flöde"), ("sea_level", "havsnivå"), ("water_levels", "vattenstånd"), ("weather_stations", "väder och regn"))
        return [{"station": item["station"], "name": item["name"], "kind": kind, "latitude": item.get("latitude"),
                 "longitude": item.get("longitude"), "last_utc": item.get("last_utc")}
                for key, kind in kinds for item in poll.get(key, []) if item.get("silent") and item.get("latitude") is not None]

    def state(self) -> dict[str, Any]:
        state = self.store.snapshot()
        # New alarms first, then current ones, the latest first within each.
        alarms = sorted(state["alarms"].values(), key=lambda alarm: alarm["updated_utc"], reverse=True)
        alarms.sort(key=lambda alarm: (alarm["state"] != "new", not alarm["current"]))
        return {"area": {"name": self.area.NAME, "bbox": self.area.BBOX, "centre": self.area.CENTRE,
                         "poll_seconds": self.area.POLL_SECONDS, "contacts_note": self.area.CONTACTS_NOTE},
                "view": self.view, "layers": self.layers, "speech": self.speech, "settings": self.settings_status(),
                "iot": self.sensors.snapshot(),
                "polled_utc": state.get("polled_utc"), "alarms": alarms, "sources": state["sources"],
                "filtered": state["filtered"], "events": state["events"][-50:], "refused": state["refused"][-50:],
                "context": state["context"]}

    def say(self, texts: list[str]) -> None:
        """Read the lines aloud with the scenarios' voice alma, Piper's synthetic Swedish voice."""
        if self.speaker is None:
            from app.backend import speech

            self.speaker = speech.Speaker()
        self.speaker.say([(text, "alma") for text in texts])

    @staticmethod
    def map_dir(item: dict[str, Any]) -> Path:
        """A municipal map's folder: its own once fetched (SOURCE.json), else its fallback (a scenario's map)."""
        own = item["dir"]
        return own if (own / "SOURCE.json").is_file() or "fallback_dir" not in item else item["fallback_dir"]

    def municipal_maps(self, overlays: bool = False) -> list[dict[str, Any]]:
        """The area's municipal maps that are fetched (their SOURCE.json written), for the screens: the
        base maps, or with `overlays` the maps laid over them (the cloudburst mapping)."""
        found = []
        for item in getattr(self.area, "MUNICIPAL_BASEMAPS", []):
            if bool(item.get("overlay")) != overlays:
                continue
            try:
                source = json.loads((self.map_dir(item) / "SOURCE.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            found.append({"id": item["id"], "label": item["label"], "attribution": item["attribution"],
                          "url": f"/basemap/{item['id']}/{{z}}/{{x}}/{{y}}.png", "min_zoom": source["min_zoom"],
                          "max_zoom": source["max_zoom"], "bbox": source["bbox_west_south_east_north"]})
        return found

    def lantmateriet_maps(self) -> list[dict[str, Any]]:
        """Lantmäteriet's Topografisk webbkarta through /lm/topowebb/, for an area without its own map, once configured."""
        if not getattr(self.area, "LANTMATERIET_BASEMAP", False) or not self.lantmateriet.topowebb_enabled:
            return []
        return [{"id": "lmtopowebb", "label": "Lantmäteriet (Topografisk webbkarta)", "attribution": "© Lantmäteriet",
                 "url": "/lm/topowebb/{z}/{x}/{y}.png", "min_zoom": 5, "max_zoom": 17, "bbox": list(self.area.BBOX)}]

    def wms_overlays(self) -> list[dict[str, Any]]:
        """The area's maps laid over the others straight from the municipality's WMS (WMS_OVERLAYS)."""
        return [{"id": item["id"], "label": item["label"], "attribution": item["attribution"], "bbox": list(self.area.BBOX),
                 "wms": {"url": item["url"], "layers": item["layers"]}} for item in getattr(self.area, "WMS_OVERLAYS", [])]

    def config(self) -> dict[str, Any]:
        """What the screens need to start: the area and the base maps."""
        offline = offline_tiles.available()
        return {"area": {"name": self.area.NAME, "bbox": self.area.BBOX, "centre": self.area.CENTRE,
                         "poll_seconds": self.area.POLL_SECONDS,
                         # What the satellite monitor logs of Sentinel-1's water outside the lakes (sentinel1.py).
                         "s1_water_log_pct": getattr(self.area, "S1_WATER_LOG_PCT", 0.5)},
                "maps": {"municipal": self.municipal_maps() + self.lantmateriet_maps(),
                         "offline": {"url": "/tiles/{z}/{x}/{y}.png", "bbox": getattr(self.area, "MAP_BBOX", self.area.BBOX),
                                     "attribution": "© OpenStreetMap contributors"} if offline else None,
                         "overlay": {"url": offline_tiles.OVERLAY_URL, "label": offline_tiles.OVERLAY_LABEL,
                                     "attribution": "© OpenStreetMap contributors"} if offline else None,
                         "online": ONLINE_OSM},
                "layers": {"radar": {"url": "/api/radar.png", "bbox": self.area.BBOX, "label": "Väderradar (SMHI)",
                                     "attribution": radar.ATTRIBUTION},
                           "flood": getattr(self.area, "FLOOD_HAZARD_WMS", None),
                           "flood_highest": getattr(self.area, "FLOOD_HIGHEST_WMS", None),
                           # The cloudburst mappings: fetched tiles (Flen's) and live WMS (Sundsvall's, Västerås's).
                           "overlays": self.municipal_maps(overlays=True) + self.wms_overlays()},
                # The scenarios' 3D terrain, when the area has it (/terrain/).
                "terrain": "/terrain/" if self.terrain_dir and (self.terrain_dir / "layer.json").is_file() else None}

    def border(self) -> dict[str, Any] | None:
        try:
            return json.loads((self.data_dir / "border.geojson").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def satellites(self) -> dict[str, Any]:
        return satellites.satellites(self.area)

    def briefing_page(self, alarm_id: str) -> str | None:
        state = self.store.snapshot()
        alarm = state["alarms"].get(alarm_id)
        if alarm is None:
            return None
        context = {key: value for key, value in state["context"].items() if key not in ("border", "firms")}
        return briefing.render(briefing.build(alarm, context, self.area))


def clip_to_border(png: bytes, border: dict[str, Any] | None, z: int, x: int, y: int) -> bytes:
    """A tile with everything outside the municipality's border made transparent; unchanged without a border."""
    if not border:
        return png
    from PIL import Image, ImageChops, ImageDraw

    tile = Image.open(io.BytesIO(png)).convert("RGBA")
    mask = Image.new("L", tile.size, 0)
    draw = ImageDraw.Draw(mask)
    for polygon in geo.polygons(border):
        for index, ring in enumerate(polygon):
            draw.polygon([geo.tile_pixel(lat, lon, z, x, y, tile.size[0]) for lon, lat, *_ in ring], fill=0 if index else 255)
    tile.putalpha(ImageChops.multiply(tile.getchannel("A"), mask))
    out = io.BytesIO()
    tile.save(out, "PNG")
    return out.getvalue()


class Handler(BaseHTTPRequestHandler):
    monitor: Monitor

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - signature of the base class
        pass

    def send_body(self, body: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_body(json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", status)

    def do_GET(self) -> None:  # noqa: N802 - name required by BaseHTTPRequestHandler
        path = urlsplit(self.path).path
        tile = TILE.fullmatch(path)
        basemap = BASEMAP_TILE.fullmatch(path)
        if path == "/":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/control.html")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif path == "/api/state":
            self.send_json(self.monitor.state())
        elif path == "/api/config":
            self.send_json(self.monitor.config())
        elif path == "/api/radar.png":
            # An empty image until the first poll has fetched the radar.
            self.send_body(self.monitor.radar.png or radar.EMPTY_PNG, "image/png")
        elif path == "/api/view":
            self.send_json({"view": self.monitor.view, "layers": self.monitor.layers})
        elif path in ("/api/satellite.png", "/api/landsat.png"):
            png = (self.monitor.image if path == "/api/satellite.png" else self.monitor.landsat).png
            self.send_body(png or radar.EMPTY_PNG, "image/png")
        elif path.startswith("/terrain/"):
            self.terrain(path)
        elif path.startswith("/lm/topowebb/"):
            self.topowebb(path)
        elif path in ("/api/s1radar.png", "/api/s1water.png", "/api/s1wetness.png"):
            png = self.monitor.radar_pass.png(path[len("/api/s1"):-len(".png")])
            self.send_body(png or radar.EMPTY_PNG, "image/png")
        elif path == "/api/assets":
            self.send_json(gis.public(self.monitor.assets.data if self.monitor.assets else None, self.monitor.places))
        elif path == "/api/weather":
            self.send_json(self.monitor.weather.latest or {"wind": [], "chart": None})
        elif path == "/api/satellites":
            self.send_json(self.monitor.satellites())
        elif tile:
            self.offline_tile(tile.group(1) == "tiles-overlay", *(int(value) for value in tile.groups()[1:]))
        elif basemap:
            self.municipal_tile(basemap.group(1), *(int(value) for value in basemap.groups()[1:]))
        elif path.startswith("/briefing/"):
            page = self.monitor.briefing_page(unquote(path[len("/briefing/"):]))
            if page is None:
                self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            else:
                self.send_body(page.encode("utf-8"), "text/html; charset=utf-8")
        elif path in STATIC:
            file, content_type = STATIC[path]
            self.send_body(file.read_bytes(), content_type)
        elif path.startswith("/vendor/") and path.split("/")[2] in VENDOR_LIBRARIES:
            self.vendor(path)
        else:
            self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def vendor(self, path: str) -> None:
        """The web libraries the demos keep in app/frontend/vendor/ (tools/fetch_web_vendor.py)."""
        library = VENDOR_DIR / path.split("/")[2]
        target = (VENDOR_DIR / unquote(path[len("/vendor/"):])).resolve()
        if library.resolve() not in target.parents or not target.is_file():
            self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in ("application/javascript", "application/json"):
            content_type += "; charset=utf-8"
        self.send_body(target.read_bytes(), content_type)

    def topowebb(self, path: str) -> None:
        """Lantmäteriet's tiles through the service, so the Geotorget credentials stay on the server."""
        parts = path.removeprefix("/lm/topowebb/").removesuffix(".png").split("/")
        if not getattr(self.monitor.area, "LANTMATERIET_BASEMAP", False) or len(parts) != 3 or not all(part.isdigit() for part in parts):
            self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            body, content_type = lantmateriet.topowebb_tile(self.monitor.lantmateriet, *(int(part) for part in parts))
        except lantmateriet.NotConfigured:
            self.send_json({"error": "not_configured"}, HTTPStatus.NOT_FOUND)
            return
        except ValueError:
            self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        except lantmateriet.UpstreamError as error:
            self.send_json({"error": "upstream", "status": error.status}, HTTPStatus.BAD_GATEWAY)
            return
        self.send_body(body, content_type)

    def terrain(self, path: str) -> None:
        """The scenarios' 3D terrain, as the demo's backend serves it (app/backend/server.py)."""
        root = self.monitor.terrain_dir
        target = (root / path.removeprefix("/terrain/")).resolve() if root else None
        if target is None or not target.is_relative_to(root.resolve()) or target.suffix not in {".json", ".terrain"} or not target.is_file():
            self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        if target.suffix == ".terrain":
            self.send_header("Content-Type", "application/vnd.quantized-mesh;extensions=octvertexnormals")
            self.send_header("Content-Encoding", "gzip")
        else:
            self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=86400")
        self.end_headers()
        self.wfile.write(body)

    def offline_tile(self, overlay: bool, z: int, x: int, y: int) -> None:
        try:
            body, content_type = offline_tiles.tile(z, x, y, overlay=overlay)
        except ValueError:
            self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
        except offline_tiles.Unavailable:
            self.send_json({"error": "tiles_unavailable"}, HTTPStatus.BAD_GATEWAY)
        else:
            # The road numbers and railway tunnels only over the municipal map, which lacks them;
            # OpenStreetMap's own map outside it has them already.
            if overlay:
                body, content_type = clip_to_border(body, self.monitor.border(), z, x, y), "image/png"
            self.send_body(body, content_type)

    def municipal_tile(self, map_id: str, z: int, x: int, y: int) -> None:
        item = next((item for item in getattr(self.monitor.area, "MUNICIPAL_BASEMAPS", []) if item["id"] == map_id), None)
        target = Monitor.map_dir(item) / str(z) / str(x) / f"{y}.png" if item else None
        if target is None or not target.is_file():
            self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
        else:
            self.send_body(target.read_bytes(), "image/png")

    def foreign_post(self) -> HTTPStatus | None:
        """As the demo's server (app/backend/server.py): only JSON, and a browser's Origin must be
        this server's own, so another web page cannot confirm or dismiss an alarm."""
        content_type = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if content_type != "application/json":
            return HTTPStatus.UNSUPPORTED_MEDIA_TYPE
        origin = self.headers.get("Origin")
        if origin is not None and urlsplit(origin).netloc.lower() != (self.headers.get("Host") or "").lower():
            return HTTPStatus.FORBIDDEN
        return None

    def do_POST(self) -> None:  # noqa: N802 - name required by BaseHTTPRequestHandler
        refused = self.foreign_post()
        if refused is not None:
            self.send_json({"error": "json_from_this_page_only"}, refused)
            return
        path = urlsplit(self.path).path
        if path == "/api/demo/menu":
            self.demo_menu()
            return
        if path == "/api/view":
            self.set_view()
            return
        if path == "/api/layers":
            self.set_layers()
            return
        if path == "/api/speech":
            self.set_speech()
            return
        if path == "/api/settings":
            settings = self.monitor.save_settings()
            log.info("Operatören: inställningarna sparade")
            self.send_json(settings)
            return
        parts = path.split("/")
        if len(parts) != 5 or parts[:3] != ["", "api", "alarms"] or parts[4] not in ("confirm", "dismiss"):
            self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 <= length <= 4096:
            self.send_json({"error": "too_large"}, HTTPStatus.BAD_REQUEST)
            return
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
            note = str(body.get("note") or "") if isinstance(body, dict) else ""
            alarm = self.monitor.store.act(unquote(parts[3]), parts[4], note)
        except KeyError:
            self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        except ValueError:
            self.send_json({"error": "invalid"}, HTTPStatus.BAD_REQUEST)
            return
        log.info("Operatören: %s %s", parts[4], alarm["id"])
        self.send_json(alarm)

    def set_view(self) -> None:
        """VISA 2D / VISA 3D in mission control: the main screen's map."""
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length)) if 0 < length <= 256 else {}
            view = body.get("view") if isinstance(body, dict) else None
        except ValueError:
            view = None
        if view not in ("2d", "3d"):
            self.send_json({"error": 'view needs "2d" or "3d"'}, HTTPStatus.BAD_REQUEST)
            return
        self.monitor.view = view
        self.send_json({"view": view})

    def set_speech(self) -> None:
        """UPPLÄSNING in mission control: {"speech": bool}; off stops what is being read."""
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length)) if 0 < length <= 64 else {}
        except ValueError:
            body = None
        if not isinstance(body, dict) or not isinstance(body.get("speech"), bool):
            self.send_json({"error": 'speech needs true or false'}, HTTPStatus.BAD_REQUEST)
            return
        self.monitor.speech = body["speech"]
        if not self.monitor.speech and self.monitor.speaker is not None:
            self.monitor.speaker.stop()
        self.send_json({"speech": self.monitor.speech})

    def set_layers(self) -> None:
        """The map layers in mission control: {"<layer>": bool, ...}, of LAYERS."""
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length)) if 0 < length <= 256 else {}
        except ValueError:
            body = None
        if not isinstance(body, dict) or not body or any(key not in self.monitor.layers or not isinstance(value, bool)
                                                         for key, value in body.items()):
            self.send_json({"error": "layers needs known layers as true or false"}, HTTPStatus.BAD_REQUEST)
            return
        self.monitor.layers.update(body)
        self.send_json({"layers": self.monitor.layers})

    def demo_menu(self) -> None:
        """BYT in mission control: stop with the exit code tools/start_demo.py set in
        TECHSEED_DEMO_MENU_EXIT, so that it shows its start page again; without it, nothing."""
        code = os.environ.get("TECHSEED_DEMO_MENU_EXIT")
        if not code:
            self.send_json({"error": "no_demo_menu", "detail": "övervakningen är inte startad med tools.start_demo"},
                           HTTPStatus.CONFLICT)
            return
        self.send_json({"menu": True}, HTTPStatus.ACCEPTED)
        self.server.exit_code = int(code)
        threading.Thread(target=self.server.shutdown, daemon=True).start()


def poll_loop(monitor: Monitor, stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            monitor.poll()
        except Exception:  # noqa: BLE001 - the loop goes on after a failed poll
            log.exception("Avläsningen misslyckades")
        stop.wait(monitor.area.POLL_SECONDS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--area", choices=areas.AVAILABLE, default="flenkommun")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--once", action="store_true", help="poll once, print a summary and exit")
    parser.add_argument("--data-dir", type=Path, help="the state, inbox and log (default: the area's DATA_DIR)")
    parser.add_argument("--mqtt", default=os.environ.get("IOT_MQTT_BROKER", "127.0.0.1:1883"),
                        help="the MQTT broker of the IoT nodes, host:port, or 'off'")
    arguments = parser.parse_args(argv)
    area = areas.load(arguments.area)
    data_dir = arguments.data_dir or area.DATA_DIR
    (data_dir / "inbox").mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(data_dir / "monitor.log", encoding="utf-8")])
    monitor = Monitor(area, data_dir=data_dir)
    if arguments.once:
        summary = monitor.poll()
        for item in summary["sources"]:
            print(f"{item['source']:22} {'ok' if item['ok'] else 'FEL'} {item['count']:4}  {item['error'] or item['note'] or ''}")
        for item in summary["candidates"]:
            print(f"LARM {item['kind_word']:13} {item['severity']:9} {item['title']}")
        for item in summary["filtered"]:
            print(f"Utelämnat: {item['what']} – {item['reason']}")
        return 0
    if arguments.mqtt != "off":
        host, _, port = arguments.mqtt.rpartition(":")
        iot.start(monitor.sensors, host or "127.0.0.1", int(port))
    stop = threading.Event()
    threading.Thread(target=poll_loop, args=(monitor, stop), daemon=True).start()
    Handler.monitor = monitor
    server = ThreadingHTTPServer((arguments.host, arguments.port), Handler)
    server.daemon_threads = True
    server.exit_code = 0
    log.info("Övervakning av %s: http://%s:%d/ (avläsning var %d s)", area.NAME, arguments.host, arguments.port,
             area.POLL_SECONDS)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
    return server.exit_code
