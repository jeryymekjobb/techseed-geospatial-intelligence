"""Proxy for the scenario's map services (WMS): the municipality's and MCF's flood maps.

The screens ask the backend for map images at /wms/<source>, so every screen on the
network gets them from the backend. Only GetMap requests for the layers the scenario
lists are forwarded; the services need no login.
"""

from __future__ import annotations

from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.backend import scenario
from app.backend.lantmateriet import WMS_PARAMETERS

TIMEOUT_SECONDS = 20
USER_AGENT = "techseed-geospatial-intelligence/0.1 (exhibition demonstrator)"
# id -> the scenario's service: {"url", "layers": {name: title}, "attribution"}
SOURCES = {key: value for key, value in (("municipal", scenario.MUNICIPAL_WMS), ("mcf", scenario.FLOOD_HAZARD_WMS)) if value}


class UpstreamError(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(status)
        self.status = status


def sources() -> list[dict[str, Any]]:
    """The services for /api/config: their layers by name and title, the attribution and the layers shown from the start."""
    return [{"id": key, "url": f"/wms/{key}", "layers": source["layers"], "attribution": source["attribution"],
             "visible": source.get("visible", [])} for key, source in SOURCES.items()]


def get_map(source_id: str, query: dict[str, str]) -> tuple[bytes, str]:
    source = SOURCES.get(source_id)
    if source is None:
        raise KeyError(source_id)
    parameters = {key.upper(): value for key, value in query.items()}
    if set(parameters) - WMS_PARAMETERS or parameters.get("REQUEST", "").lower() != "getmap":
        raise ValueError("only WMS GetMap with map parameters is forwarded")
    if not parameters.get("LAYERS") or set(parameters["LAYERS"].split(",")) - set(source["layers"]):
        raise ValueError("only the scenario's layers are forwarded")
    url = f"{source['url']}?{urlencode(parameters)}"
    try:
        with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=TIMEOUT_SECONDS) as response:
            return response.read(), response.headers.get("Content-Type", "image/png")
    except HTTPError as exc:
        raise UpstreamError(exc.code) from None
    except URLError as exc:
        raise UpstreamError(502) from exc
