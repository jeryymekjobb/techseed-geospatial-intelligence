"""Kramfors kommun, with the cloudburst in Kramfors 2026 and the rain in Västernorrland 2025 as its
scenarios; Flens kommun's monitoring is the template (common.py).

Of SMHI's flow stations near the municipality only Risnäs on Gådeån gives live values (Hjälta and
Sollefteå give their archive only, checked 2026-11-04); the scenarios' level sensors are kept where
they follow it. Without the municipality's map the base map is OpenStreetMap. Its state and inbox
live in the unversioned data/monitoring/kramforskommun/.
"""

from __future__ import annotations

from app.monitoring.areas.common import *  # noqa: F403 - the template's shared satellites, limits and contacts
from app.monitoring.areas.common import built_terrain, built_tiles, data_dir, mcf_layer, scenario_data

NAME = "Kramfors kommun"
MUNICIPALITY_CODE = "2282"
COUNTY = "Västernorrlands län"
# SMHI's id of the county in its warnings (affectedAreas, metadata/area.json), checked 2026-11-04.
SMHI_COUNTY_ID = 22
KRISINFO_WORDS = ("Västernorrland", "Kramfors")
# west, south, east, north: the municipality (MCF's border, 17.18-18.99 E, 62.60-63.21 N) with a margin.
BBOX = (17.1, 62.55, 19.05, 63.25)
CENTRE = (62.93, 17.78)
DATA_DIR = data_dir("kramforskommun")

_SCENARIO = scenario_data("kramfors2026")
OSM_TARGETS_FILE = _SCENARIO / "osm" / "targets-kramfors.geojson"
TERRAIN_FILE = _SCENARIO / "osm" / "terrain-kramfors.geojson"
TERRAIN_DIR = built_terrain("kramforskommun", _SCENARIO / "terrain")
# The offline map over the whole municipality once built (tools/build_offline_tiles.py --area), else the scenario's.
TILES_FILE, MAP_BBOX = built_tiles("kramforskommun", ("kramfors.mbtiles", (17.2, 62.6, 18.3, 63.2)), BBOX)

# SMHI's live flow every 15 minutes (hydroobs parameter 2), checked 2026-11-04.
FLOW_STATIONS = {"2398": "Risnäs (Gådeån)"}
RAIN_STATIONS = {"128390": "Lungö A", "138070": "Västmarkum A"}
# SMHI's weather stations giving values on 2026-11-04, with the parameters each reports.
WEATHER_STATIONS = {
    "128390": {"name": "Lungö A", "parameters": [1, 3, 4, 7, 5]},
    "138070": {"name": "Västmarkum A", "parameters": [1, 3, 4, 7, 5]},
    "127380": {"name": "Härnösand", "parameters": [5]},
    "137090": {"name": "Multrå D", "parameters": [5]},
    "128500": {"name": "Nora-Östanö D", "parameters": [5]},
    "127570": {"name": "Åkroken D", "parameters": [5]},
    "137100": {"name": "Sollefteå", "parameters": [5]},
}
FIRE_RISK_POINT = CENTRE
FORECAST_POINT = CENTRE

# MCF's flood mapping of Ångermanälven, as the scenarios: the 100-year flow (WMS 13).
FLOOD_HAZARD_WMS = mcf_layer("13", "100-årsflöde (MCF)")
FLOOD_HIGHEST_WMS = mcf_layer("9", "Beräknat högsta flöde (MCF)")
FLOOD_ZONE_LABEL = "MCF:s 100-årsflöde"
FLOOD_ZONE_FILES = [_SCENARIO / "mcf" / "mcf-100ar.geojson"]
# Västernorrland 2025's simulated level sensors; only those following Risnäs are kept (levels.py).
LEVEL_SENSOR_FILE = scenario_data("vasternorrland2025") / "sensors" / "level-points.geojson"
