"""The monitoring service: a poll every POLL_SECONDS of the live sources and the inbox, the rules,
the alarms, and a web server on 127.0.0.1 for the operator page.

    .venv/bin/python -m app.monitoring --area flenkommun [--port 8770] [--once] [--data-dir DIR]

--once polls once, prints a summary and exits. Its log is printed and written to
data/monitoring/<area>/monitor.log; --data-dir keeps the state, inbox and log elsewhere, for a trial.
"""

from __future__ import annotations

import argparse
import json
import logging
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import unquote, urlsplit

from app.monitoring import areas, briefing, events, rules, sources
from app.monitoring.alarms import Store

log = logging.getLogger("app.monitoring")
WEB_DIR = Path(__file__).resolve().parent / "web"
VENDOR_DIR = Path(__file__).resolve().parents[1] / "frontend" / "vendor"
STATIC = {"/": ("index.html", "text/html; charset=utf-8"), "/monitor.js": ("monitor.js", "text/javascript; charset=utf-8"),
          "/monitor.css": ("monitor.css", "text/css; charset=utf-8")}
VENDOR_TYPES = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".png": "image/png"}


class Monitor:
    """One area's sources, rules and alarms."""

    def __init__(self, area: ModuleType, fetch: sources.Fetch = sources.fetch_url, data_dir: Path | None = None) -> None:
        self.area = area
        self.fetch = fetch
        self.data_dir = data_dir or area.DATA_DIR
        self.store = Store(self.data_dir / "state.json")
        self.inbox = self.data_dir / "inbox"
        self.poll_lock = threading.Lock()

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
            results["smhi_warnings"] = sources.guarded(
                "smhi_warnings", lambda: sources.read_warnings(area.SMHI_COUNTY_ID, border, fetch))
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
                    "fire_ban": results["mcf_fire_ban"].items, "firms": results["firms"].items}
            candidates, filtered = rules.detect(poll, recent, area)
            status = [result.as_json() for result in (*results.values(), stats)]
            status.append({"source": "inbox", "ok": True, "fetched_utc": sources.utc_text(datetime.now(timezone.utc)), "count": len(batch.events),
                           "error": None, "note": f"{len(batch.refused)} avvisade rader" if batch.refused else None,
                           "attribution": "Händelser in (inkorgen)"})
            self.store.apply(candidates, status, filtered, self._context(poll, stats))
            for result in status:
                if not result["ok"]:
                    log.warning("Källa %s: %s", result["source"], result["error"])
            log.info("Avläsning klar: %d larmkandidater, %d nya händelser, %d avvisade rader",
                     len(candidates), len(batch.events), len(batch.refused))
            return {"candidates": [candidate.as_json() for candidate in candidates], "filtered": filtered, "sources": status,
                    "events": len(batch.events), "refused": len(batch.refused)}

    def _context(self, poll: dict[str, Any], stats: sources.Result) -> dict[str, Any]:
        limits = stats.items[0] if stats.items else {}
        flows = [{"station": item["station"], "name": item["name"], "latitude": item["latitude"], "longitude": item["longitude"],
                  "value": item["readings"][-1]["value"], "time_utc": item["readings"][-1]["time_utc"],
                  "quality": item["readings"][-1]["quality"], "limits": limits.get(item["station"])}
                 for item in poll["flows"] if item["readings"]]
        return {"border": poll["border"], "flows": flows, "rain": poll["rain"], "warnings": poll["warnings"],
                "fire_ban": poll["fire_ban"], "news": [item for item in poll["krisinfo"] if item["kind"] == "news"],
                "firms": poll["firms"]}

    def state(self) -> dict[str, Any]:
        state = self.store.snapshot()
        # New alarms first, then current ones, the latest first within each.
        alarms = sorted(state["alarms"].values(), key=lambda alarm: alarm["updated_utc"], reverse=True)
        alarms.sort(key=lambda alarm: (alarm["state"] != "new", not alarm["current"]))
        return {"area": {"name": self.area.NAME, "bbox": self.area.BBOX, "centre": self.area.CENTRE,
                         "poll_seconds": self.area.POLL_SECONDS, "contacts_note": self.area.CONTACTS_NOTE},
                "polled_utc": state.get("polled_utc"), "alarms": alarms, "sources": state["sources"],
                "filtered": state["filtered"], "events": state["events"][-50:], "refused": state["refused"][-50:],
                "context": state["context"]}

    def briefing_page(self, alarm_id: str) -> str | None:
        state = self.store.snapshot()
        alarm = state["alarms"].get(alarm_id)
        if alarm is None:
            return None
        context = {key: value for key, value in state["context"].items() if key not in ("border", "firms")}
        return briefing.render(briefing.build(alarm, context, self.area))


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
        if path == "/api/state":
            self.send_json(self.monitor.state())
        elif path.startswith("/briefing/"):
            page = self.monitor.briefing_page(unquote(path[len("/briefing/"):]))
            if page is None:
                self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            else:
                self.send_body(page.encode("utf-8"), "text/html; charset=utf-8")
        elif path in STATIC:
            name, content_type = STATIC[path]
            self.send_body((WEB_DIR / name).read_bytes(), content_type)
        elif path.startswith("/vendor/leaflet-1.9.4/"):
            target = (VENDOR_DIR / path[len("/vendor/"):]).resolve()
            if VENDOR_DIR.resolve() in target.parents and target.is_file() and target.suffix in VENDOR_TYPES:
                self.send_body(target.read_bytes(), VENDOR_TYPES[target.suffix])
            else:
                self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
        else:
            self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

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
        parts = urlsplit(self.path).path.split("/")
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
    stop = threading.Event()
    threading.Thread(target=poll_loop, args=(monitor, stop), daemon=True).start()
    Handler.monitor = monitor
    server = ThreadingHTTPServer((arguments.host, arguments.port), Handler)
    log.info("Övervakning av %s: http://%s:%d/ (avläsning var %d s)", area.NAME, arguments.host, arguments.port,
             area.POLL_SECONDS)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
    return 0
