"""Proxy for offline map tiles rendered by the `tiles` service (tileserver-gl).

The backend serves them at /tiles/{z}/{x}/{y}.png, so every screen on the network
gets them from the backend and not from 127.0.0.1. `OFFLINE_TILES_URL` overrides
the tile URL template (default: the docker-compose.yml service on port 8081).

A scenario with ROAD_OVERLAY (every scenario by default) also gets /tiles-overlay/{z}/{x}/{y}.png:
the same data in the style tiles/styles/techseed-overlay.json, the railway tunnels (dashed) and the
road numbers on a transparent background, laid over the base map (such as the municipality's in
Sundsvall, which lacks them), the images and the flood maps.
"""

from __future__ import annotations

import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

DEFAULT_URL = "http://127.0.0.1:8081/styles/techseed/256/{z}/{x}/{y}.png"  # tiles/styles/techseed.json
STYLE = "/styles/techseed/"
OVERLAY_STYLE = "/styles/techseed-overlay/"  # tiles/styles/techseed-overlay.json
OVERLAY_URL = "/tiles-overlay/{z}/{x}/{y}.png"
OVERLAY_LABEL = "Vägnummer och järnvägstunnlar (OSM)"
_PROBE_SECONDS = 30.0
_probe: dict[str, float | bool] = {"at": -1e9, "ok": False}


def url_template(overlay: bool = False) -> str:
    template = os.environ.get("OFFLINE_TILES_URL") or DEFAULT_URL
    return template.replace(STYLE, OVERLAY_STYLE) if overlay else template


class Unavailable(Exception):
    pass


def tile(z: int, x: int, y: int, timeout: float = 5.0, overlay: bool = False) -> tuple[bytes, str]:
    if not (0 <= z <= 20 and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
        raise ValueError("tile out of range")
    try:
        with urlopen(url_template(overlay).format(z=z, x=x, y=y), timeout=timeout) as response:
            return response.read(), response.headers.get("Content-Type", "image/png")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise Unavailable(str(exc)) from None


def available() -> bool:
    """Whether the tile service answers; checked at most every 30 seconds."""
    now = time.monotonic()
    if now - float(_probe["at"]) >= _PROBE_SECONDS:
        try:
            tile(0, 0, 0, timeout=1.0)
            _probe["ok"] = True
        except Unavailable:
            _probe["ok"] = False
        _probe["at"] = now
    return bool(_probe["ok"])


def overlay_layer(enabled: bool) -> dict[str, str] | None:
    """The road numbers and railway tunnels overlay for the screens, when the scenario has it and the
    tile service answers."""
    if not enabled or not available():
        return None
    return {"url": OVERLAY_URL, "label": OVERLAY_LABEL, "attribution": "© OpenStreetMap contributors"}
