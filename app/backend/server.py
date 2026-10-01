"""Backend for the Västmanland 2014 fire map.

Serves the GUI, the FIRMS detections of the fire, a playback stream that sends
the detections to the GUI in compressed time (Server-Sent Events), the OSM
terrain layer and a proxy for Lantmäteriet services.

Run from the repository root:

    python3 -m app.backend.server

Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import parse_qsl, urlsplit

from app.backend import lantmateriet, scenario
from tools.firms_extract import daily_summary, select_detections

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
TICK_SECONDS = 0.25
MIN_SPEED, MAX_SPEED = 60.0, 4 * 86400.0  # simulated seconds per real second


@lru_cache(maxsize=1)
def detections() -> tuple[dict[str, Any], ...]:
    kept, _, _ = select_detections(
        scenario.FIRMS_FILES, start=scenario.PERIOD_START, end=scenario.PERIOD_END, bbox=scenario.FIRE_BBOX,
    )
    return tuple(kept)


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


def config(settings: lantmateriet.Settings) -> dict[str, Any]:
    min_lat, max_lat, min_lon, max_lon = scenario.VIEW_BBOX
    fire = scenario.FIRE_BBOX
    return {
        "title": scenario.TITLE,
        "data_label": "Historiska data 2014 – uppspelning, inte live",
        "view_bounds": [[min_lat, min_lon], [max_lat, max_lon]],
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
            "lantmateriet_topowebb": settings.topowebb_enabled,
            "lantmateriet_fastighet": settings.fastighet_enabled,
            "lantmateriet_fastighet_layers": settings.fastighet_layers if settings.fastighet_enabled else "",
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "TechseedFireMap/0.1"
    settings = lantmateriet.Settings.from_environment()

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
        elif path == "/api/stream":
            self.stream(query)
        elif path == "/api/layers/terrain":
            self.send_bytes(scenario.TERRAIN_FILE.read_bytes(), "application/geo+json", "max-age=3600")
        elif path.startswith("/lm/"):
            self.lantmateriet(path, query)
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
    parser = argparse.ArgumentParser(description="Backend for the Västmanland 2014 fire map")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    settings = Handler.settings
    print(f"Fire map on http://{args.host}:{args.port}/ ({len(detections())} detections)")
    print(f"Lantmäteriet topowebb: {'on' if settings.topowebb_enabled else 'off'}, "
          f"fastighetsindelning: {'on' if settings.fastighet_enabled else 'off'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
