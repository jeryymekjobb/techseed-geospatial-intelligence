"""SMHI's measured flows and lake levels for the flood scenarios that have them (tools/fetch_smhi_hydro.py).

/api/hydro gives each station's series over the period with the highest value measured
before it, so the screens can say when the water is the highest since measuring began.
"""

from __future__ import annotations

import csv
import json
from functools import lru_cache
from typing import Any

from app.backend import scenario

HYDRO_DIR = scenario.HYDRO_DIR


@lru_cache(maxsize=1)
def stations() -> dict[str, Any] | None:
    """The stations with their observations, or None when the scenario has none."""
    catalogue_file = HYDRO_DIR / "stations.json" if HYDRO_DIR else None
    if catalogue_file is None or not catalogue_file.is_file():
        return None
    catalogue = json.loads(catalogue_file.read_text(encoding="utf-8"))
    result = []
    for station in catalogue["stations"]:
        with (HYDRO_DIR / station["file"]).open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        result.append({
            **{key: station[key] for key in ("id", "name", "kind", "unit", "latitude", "longitude", "measured_since", "earlier_max")},
            # SMHI's quality code: G checked and approved, anything else not yet checked.
            "unchecked": any(row["quality"] != "G" for row in rows),
            "observations": [{"time_utc": row["time_utc"], "value": float(row["value"])} for row in rows],
        })
    return {"source": catalogue["source"], "stations": result}
