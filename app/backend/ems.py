"""Copernicus EMS's mapped perimeters of a fire (tools/fetch_ems_perimeters.py).

/api/ems gives the scenario's products in the order of their images, each shown from the
end of its image's day (the images carry no time of day), so the screens never show a
perimeter before the image it was mapped from existed.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache
from typing import Any

from app.backend import scenario

EMS_DIR = scenario.EMS_DIR


@lru_cache(maxsize=1)
def perimeters() -> dict[str, Any] | None:
    """The products with their image, area, outline and the time they are shown from; None without any."""
    if EMS_DIR is None or not (EMS_DIR / "perimeters.geojson").is_file():
        return None
    collection = json.loads((EMS_DIR / "perimeters.geojson").read_text(encoding="utf-8"))
    source = json.loads((EMS_DIR / "SOURCE.json").read_text(encoding="utf-8"))
    products = []
    for feature in collection["features"]:
        props = feature["properties"]
        if not props.get("image_date"):
            continue
        shown_from = date.fromisoformat(props["image_date"]) + timedelta(days=1)
        products.append({**props, "visible_from_utc": f"{shown_from.isoformat()}T00:00:00Z", "geometry": feature["geometry"]})
    products.sort(key=lambda item: (item["image_date"], item["area_ha"]))
    return {"attribution": source["attribution"], "products": products}
