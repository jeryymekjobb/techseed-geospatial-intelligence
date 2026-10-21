"""Meteosat's cloud mask over the incident every hour and at each satellite image
(tools/fetch_meteosat_clm.py).

The cloudy share of the map area's SEVIRI pixels says why an optical image is cloudy or missing
and when the sky cleared. The panel draws it against the clock, and each scene gets the share at its
time (`with_cloud`), which the image captions, mission control's list and the log name. Meteosat's
product, a few kilometres per pixel this far north; the screens say so.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.backend import scenario

FILE = scenario.METEOSAT_CLM_FILE
LABEL = "Moln (Meteosat)"
# In the form EUMETSAT's data policy (article 6.3) asks for, with the year the demo shows it.
ATTRIBUTION = "Contains modified EUMETSAT Meteosat product 2026 (MSG Cloud Mask, CC BY 4.0)"


@lru_cache(maxsize=1)
def data() -> dict[str, Any] | None:
    if FILE is None or not FILE.is_file():
        return None
    loaded = json.loads(FILE.read_text(encoding="utf-8"))
    return loaded if loaded.get("hours") or loaded.get("images") else None


def with_cloud(layer: dict[str, Any] | None) -> dict[str, Any] | None:
    """The images' layer (landsat.layer()) with each scene's cloudy share from Meteosat, where known."""
    loaded = data()
    if layer is None or loaded is None:
        return layer
    shares = {item["scene"]: item["cloud_pct"] for item in loaded.get("images", []) if item.get("cloud_pct") is not None}
    return {**layer, "scenes": [{**scene, **({"meteosat_cloud_pct": shares[scene["scene"]]} if scene["scene"] in shares else {})}
                                for scene in layer["scenes"]]}


def layer() -> dict[str, Any] | None:
    """The panel's hourly series, or None without data."""
    loaded = data()
    if loaded is None:
        return None
    return {"label": LABEL, "attribution": ATTRIBUTION, "pixels_in_area": loaded.get("pixels_in_area"), "hours": loaded.get("hours", [])}
