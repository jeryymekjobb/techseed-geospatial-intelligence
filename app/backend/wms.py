"""Proxy for the scenario's map services (WMS): the municipality's and MCF's flood maps.

The screens ask the backend for map images at /wms/<source>, so every screen on the
network gets them from the backend. Only GetMap requests for the layers the scenario
lists are forwarded; the services need no login.

The services are outside the demo's control. A service that does not answer within
TIMEOUT_SECONDS is refused at once for DOWN_SECONDS, so the waiting requests do not
take the browser's few connections to the backend and hold up the rest of the screens;
/api/config says whether each service answers, so the screens leave a silent one out.
"""

from __future__ import annotations

import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.backend import scenario
from app.backend.lantmateriet import WMS_PARAMETERS

TIMEOUT_SECONDS = 5
DOWN_SECONDS = 60.0
USER_AGENT = "techseed-geospatial-intelligence/0.1 (exhibition demonstrator)"
# id -> the scenario's service: {"url", "layers": {name: title}, "attribution"}
SOURCES = {key: value for key, value in (("municipal", scenario.MUNICIPAL_WMS), ("mcf", scenario.FLOOD_HAZARD_WMS)) if value}
# id -> until when the service is refused without asking it (time.monotonic())
_down: dict[str, float] = {}
# id -> (when it was asked, whether it answered), for /api/config
_probe: dict[str, tuple[float, bool]] = {}


class UpstreamError(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(status)
        self.status = status


def _fetch(source_id: str, parameters: dict[str, str]) -> tuple[bytes, str]:
    if time.monotonic() < _down.get(source_id, 0.0):
        raise UpstreamError(503)
    url = f"{SOURCES[source_id]['url']}?{urlencode(parameters)}"
    try:
        with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=TIMEOUT_SECONDS) as response:
            return response.read(), response.headers.get("Content-Type", "image/png")
    except HTTPError as exc:
        if exc.code >= 500:
            _down[source_id] = time.monotonic() + DOWN_SECONDS
        raise UpstreamError(exc.code) from None
    except (URLError, OSError) as exc:  # no answer, a refused connection or a time-out (TimeoutError is an OSError)
        _down[source_id] = time.monotonic() + DOWN_SECONDS
        raise UpstreamError(504) from exc


def available(source_id: str) -> bool:
    """Whether the service answers a small map request; asked at most once per DOWN_SECONDS."""
    asked, answered = _probe.get(source_id, (-1e9, False))
    if time.monotonic() - asked < DOWN_SECONDS:
        return answered
    west, south, east, north = scenario.MAP_BBOX
    try:
        _fetch(source_id, {"SERVICE": "WMS", "VERSION": "1.1.1", "REQUEST": "GetMap", "LAYERS": next(iter(SOURCES[source_id]["layers"])),
                           "STYLES": "", "FORMAT": "image/png", "TRANSPARENT": "true", "SRS": "EPSG:4326",
                           "BBOX": f"{west},{south},{east},{north}", "WIDTH": "8", "HEIGHT": "8"})
        answered = True
    except UpstreamError:
        answered = False
    _probe[source_id] = (time.monotonic(), answered)
    return answered


def watch(interval: float = DOWN_SECONDS / 2) -> None:
    """Ask every service in the background, so /api/config never waits for one."""
    def loop() -> None:
        while True:
            for key in SOURCES:
                _probe.pop(key, None)
                available(key)
            time.sleep(interval)
    if SOURCES:
        threading.Thread(target=loop, name="wms-watch", daemon=True).start()


def sources() -> list[dict[str, Any]]:
    """The services for /api/config: their layers by name and title, the attribution, the layers shown
    from the start and whether the service answers."""
    return [{"id": key, "url": f"/wms/{key}", "layers": source["layers"], "attribution": source["attribution"],
             "visible": source.get("visible", []), "available": available(key)} for key, source in SOURCES.items()]


def get_map(source_id: str, query: dict[str, str]) -> tuple[bytes, str]:
    source = SOURCES.get(source_id)
    if source is None:
        raise KeyError(source_id)
    parameters = {key.upper(): value for key, value in query.items()}
    if set(parameters) - WMS_PARAMETERS or parameters.get("REQUEST", "").lower() != "getmap":
        raise ValueError("only WMS GetMap with map parameters is forwarded")
    if not parameters.get("LAYERS") or set(parameters["LAYERS"].split(",")) - set(source["layers"]):
        raise ValueError("only the scenario's layers are forwarded")
    # The screens send an empty STYLES, which the query parsing drops; MCF's service refuses a
    # GetMap without it (an XML error with status 200), while empty means each layer's default style.
    parameters.setdefault("STYLES", "")
    return _fetch(source_id, parameters)
