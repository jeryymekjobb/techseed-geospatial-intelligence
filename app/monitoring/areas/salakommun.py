"""Sala kommun, with the forest fire in Västmanland 2014, which burned mostly in Sala, as its
scenario; Flens kommun's monitoring is the template (common.py). The fires come from NASA FIRMS and
SMHI's fire risk; the flows are Tämnarån's at Tärnsjö and Sagån's at Gränvad. Without the
municipality's map the base map is OpenStreetMap. Its state and inbox live in the unversioned
data/monitoring/salakommun/.
"""

from __future__ import annotations

from app.backend.scenarios import REPO_ROOT
from app.monitoring.areas.common import *  # noqa: F403 - the template's shared satellites, limits and contacts
from app.monitoring.areas.common import data_dir

NAME = "Sala kommun"
MUNICIPALITY_CODE = "1981"
COUNTY = "Västmanlands län"
# SMHI's id of the county in its warnings (affectedAreas, metadata/area.json), checked 2026-11-04.
SMHI_COUNTY_ID = 19
KRISINFO_WORDS = ("Västmanland", "Sala")
# west, south, east, north: the municipality (MCF's border, 16.09-16.84 E, 59.76-60.20 N) with a margin.
BBOX = (16.0, 59.7, 16.95, 60.25)
CENTRE = (59.92, 16.6)
DATA_DIR = data_dir("salakommun")

# The Västmanland 2014 scenario's files, which predate the scenarios' data folders.
OSM_TARGETS_FILE = REPO_ROOT / "osm_data" / "targets-vastmanland.geojson"
TERRAIN_FILE = REPO_ROOT / "app" / "layers" / "terrain-vastmanland.geojson"
TERRAIN_DIR = REPO_ROOT / "data" / "terrain"
TILES_FILE = "vastmanland.mbtiles"
MAP_BBOX = (15.5, 59.55, 16.8, 60.3)

# SMHI's live flow every 15 minutes (hydroobs parameter 2), checked 2026-11-04.
FLOW_STATIONS = {"2299": "Tärnsjö (Tämnarån)", "2217": "Gränvad (Sagån)"}
RAIN_STATIONS = {"96560": "Sala A", "106160": "Kerstinbo A"}
# SMHI's weather stations giving values on 2026-11-04, with the parameters each reports.
WEATHER_STATIONS = {
    "96560": {"name": "Sala A", "parameters": [1, 3, 4, 7, 5]},
    "106160": {"name": "Kerstinbo A", "parameters": [1, 3, 4, 7, 5]},
    "106070": {"name": "Avesta", "parameters": [5]},
    "106040": {"name": "Brovallen", "parameters": [5]},
}
# The fire risk where the forest burned in 2014, the forecast at Sala.
FIRE_RISK_POINT = (59.93, 16.15)
FORECAST_POINT = CENTRE
