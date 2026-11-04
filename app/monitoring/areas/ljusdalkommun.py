"""Ljusdals kommun, with the forest fire at Kårböle 2018 as its scenario; Flens kommun's monitoring
is the template (common.py). The fires come from NASA FIRMS and SMHI's fire risk; the flows are
Ljusnan's at Saras fors and Oppli. Without the municipality's map the base map is OpenStreetMap. Its
state and inbox live in the unversioned data/monitoring/ljusdalkommun/.
"""

from __future__ import annotations

from app.monitoring.areas.common import *  # noqa: F403 - the template's shared satellites, limits and contacts
from app.monitoring.areas.common import built_terrain, built_tiles, data_dir, scenario_data

NAME = "Ljusdals kommun"
MUNICIPALITY_CODE = "2161"
COUNTY = "Gävleborgs län"
# SMHI's id of the county in its warnings (affectedAreas, metadata/area.json), checked 2026-11-04.
SMHI_COUNTY_ID = 21
KRISINFO_WORDS = ("Gävleborg", "Ljusdal")
# west, south, east, north: the municipality (MCF's border, 14.45-16.63 E, 61.48-62.34 N) with a margin.
BBOX = (14.35, 61.4, 16.75, 62.4)
CENTRE = (61.83, 16.09)
DATA_DIR = data_dir("ljusdalkommun")

_SCENARIO = scenario_data("ljusdal2018")
OSM_TARGETS_FILE = _SCENARIO / "osm" / "targets-ljusdal.geojson"
TERRAIN_FILE = _SCENARIO / "osm" / "terrain-ljusdal.geojson"
TERRAIN_DIR = built_terrain("ljusdalkommun", _SCENARIO / "terrain")
# The offline map over the whole municipality once built (tools/build_offline_tiles.py --area), else the scenario's.
TILES_FILE, MAP_BBOX = built_tiles("ljusdalkommun", ("ljusdal.mbtiles", (14.9, 61.75, 15.8, 62.2)), BBOX)

# SMHI's live flow every 15 minutes (hydroobs parameter 2), on Ljusnan, checked 2026-11-04.
FLOW_STATIONS = {"2405": "Saras fors (Ljusnan)", "2399": "Oppli (Ljusnan)"}
RAIN_STATIONS = {"116490": "Delsbo A", "114410": "Hamra A"}
# SMHI's weather stations giving values on 2026-11-04, with the parameters each reports.
WEATHER_STATIONS = {
    "116490": {"name": "Delsbo A", "parameters": [1, 3, 4, 7, 5]},
    "114410": {"name": "Hamra A", "parameters": [1, 3, 4, 7, 5]},
    "126120": {"name": "Ljusdals-Valsjön", "parameters": [5]},
    "115450": {"name": "Los D", "parameters": [5]},
    "125240": {"name": "Kölsillre", "parameters": [5]},
    "125030": {"name": "Hennan D", "parameters": [5]},
}
# The fire risk where Kårböle's forest burned in 2018, the forecast at Ljusdal.
FIRE_RISK_POINT = (61.97, 15.3)
FORECAST_POINT = CENTRE
