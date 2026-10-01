"""Proxy for Lantmäteriet map services, so credentials stay on the server.

Configured with environment variables; nothing is enabled without them:

- `LM_USERNAME`, `LM_PASSWORD`: Geotorget credentials (HTTP Basic authentication);
- `LM_TOPOWEBB_URL`: tile URL template with `{z}`, `{x}` and `{y}` for a Web
  Mercator (EPSG:3857) tile matrix set of Topografisk webbkarta Visning;
- `LM_FASTIGHET_WMS_URL`: base URL of the Fastighetsindelning Visning WMS;
- `LM_FASTIGHET_LAYERS`: comma-separated WMS layer names to show, for example
  boundaries only or boundaries and property designations.

The exact URLs come with the Geotorget order and are not part of the repository.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# Only map-image requests are forwarded; other WMS operations are refused.
WMS_PARAMETERS = {"SERVICE", "REQUEST", "VERSION", "LAYERS", "STYLES", "FORMAT", "TRANSPARENT", "SRS", "CRS", "BBOX", "WIDTH", "HEIGHT"}
TIMEOUT_SECONDS = 20


class NotConfigured(Exception):
    pass


class UpstreamError(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(status)
        self.status = status


@dataclass(frozen=True)
class Settings:
    username: str | None
    password: str | None
    topowebb_url: str | None
    fastighet_wms_url: str | None
    fastighet_layers: str = ""

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            os.environ.get("LM_USERNAME") or None,
            os.environ.get("LM_PASSWORD") or None,
            os.environ.get("LM_TOPOWEBB_URL") or None,
            os.environ.get("LM_FASTIGHET_WMS_URL") or None,
            os.environ.get("LM_FASTIGHET_LAYERS", ""),
        )

    @property
    def has_credentials(self) -> bool:
        return bool(self.username and self.password)

    @property
    def topowebb_enabled(self) -> bool:
        return self.has_credentials and bool(self.topowebb_url)

    @property
    def fastighet_enabled(self) -> bool:
        return self.has_credentials and bool(self.fastighet_wms_url) and bool(self.fastighet_layers)


def _get(url: str, settings: Settings) -> tuple[bytes, str]:
    token = base64.b64encode(f"{settings.username}:{settings.password}".encode("utf-8")).decode("ascii")
    request = Request(url, headers={"Authorization": f"Basic {token}", "User-Agent": "techseed-geospatial-intelligence/0.1"})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.read(), response.headers.get("Content-Type", "application/octet-stream")
    except HTTPError as exc:
        raise UpstreamError(exc.code) from None
    except (URLError, TimeoutError):
        raise UpstreamError(504) from None


def topowebb_tile(settings: Settings, z: int, x: int, y: int) -> tuple[bytes, str]:
    if not settings.topowebb_enabled:
        raise NotConfigured("topowebb")
    return _get(str(settings.topowebb_url).format(z=z, x=x, y=y), settings)


def fastighet_map(settings: Settings, query: dict[str, str]) -> tuple[bytes, str]:
    if not settings.fastighet_enabled:
        raise NotConfigured("fastighet")
    parameters = {key.upper(): value for key, value in query.items()}
    if set(parameters) - WMS_PARAMETERS or parameters.get("REQUEST", "").lower() != "getmap":
        raise ValueError("only WMS GetMap with map parameters is forwarded")
    separator = "&" if "?" in str(settings.fastighet_wms_url) else "?"
    return _get(f"{settings.fastighet_wms_url}{separator}{urlencode(parameters)}", settings)
