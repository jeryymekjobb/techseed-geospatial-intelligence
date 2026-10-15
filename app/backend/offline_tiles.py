"""Proxy for offline map tiles rendered by the `tiles` service (tileserver-gl).

The backend serves them at /tiles/{z}/{x}/{y}.png, so every screen on the network
gets them from the backend and not from 127.0.0.1. `OFFLINE_TILES_URL` overrides
the tile URL template (default: the docker-compose.yml service on port 8081).
"""

from __future__ import annotations

import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

DEFAULT_URL = "http://127.0.0.1:8081/styles/techseed/256/{z}/{x}/{y}.png"  # tiles/styles/techseed.json
_PROBE_SECONDS = 30.0
_probe: dict[str, float | bool] = {"at": -1e9, "ok": False}


def url_template() -> str:
    return os.environ.get("OFFLINE_TILES_URL") or DEFAULT_URL


class Unavailable(Exception):
    pass


def tile(z: int, x: int, y: int, timeout: float = 5.0) -> tuple[bytes, str]:
    if not (0 <= z <= 20 and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
        raise ValueError("tile out of range")
    try:
        with urlopen(url_template().format(z=z, x=x, y=y), timeout=timeout) as response:
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
