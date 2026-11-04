"""Höörs kommun, by Ringsjöarna, with the winter floods in Skåne 2024 as its scenario; Flens
kommun's monitoring is the template (common.py). Ringsjödammen's flow and level give no live values
(checked 2026-11-04), so the flows are Rönne å's at Heåkra and Kävlingeån's at Ellinge, below the
lakes. Without the municipality's map the base map is OpenStreetMap. Its state and inbox live in the
unversioned data/monitoring/hoorkommun/.
"""

from __future__ import annotations

from app.monitoring.areas.common import *  # noqa: F403 - the template's shared satellites, limits and contacts
from app.monitoring.areas.common import built_terrain, built_tiles, data_dir, mcf_layer, scenario_data

NAME = "Höörs kommun"
MUNICIPALITY_CODE = "1267"
COUNTY = "Skåne län"
# SMHI's id of the county in its warnings (affectedAreas, metadata/area.json), checked 2026-11-04.
SMHI_COUNTY_ID = 12
KRISINFO_WORDS = ("Skåne", "Höör")
# west, south, east, north: the municipality (MCF's border, 13.37-13.67 E, 55.78-56.09 N) with a
# margin that takes in Ringsjöarna's outlet and Ellinge.
BBOX = (13.2, 55.72, 13.75, 56.12)
CENTRE = (55.94, 13.54)
DATA_DIR = data_dir("hoorkommun")
# Without a public map of its own (checked 2026-11-04), Lantmäteriet's Topografisk webbkarta is the base
# map once the Geotorget settings are in ~/.lantmateriet (service.Monitor.lantmateriet_maps).
LANTMATERIET_BASEMAP = True

_SCENARIO = scenario_data("skane2024")
OSM_TARGETS_FILE = _SCENARIO / "osm" / "targets-skane.geojson"
TERRAIN_FILE = _SCENARIO / "osm" / "terrain-skane.geojson"
TERRAIN_DIR = built_terrain("hoorkommun", _SCENARIO / "terrain")
# The offline map over the whole municipality once built (tools/build_offline_tiles.py --area), else the scenario's.
TILES_FILE, MAP_BBOX = built_tiles("hoorkommun", ("skane.mbtiles", (13.0, 55.6, 13.9, 55.98)), BBOX)

# SMHI's live flow every 15 minutes (hydroobs parameter 2), checked 2026-11-04.
FLOW_STATIONS = {"2128": "Heåkra (Rönne å)", "2126": "Ellinge (Kävlingeån)"}
RAIN_STATIONS = {"53530": "Hörby A"}
# SMHI's weather stations giving values on 2026-11-04, with the parameters each reports.
WEATHER_STATIONS = {
    "53530": {"name": "Hörby A", "parameters": [1, 3, 4, 7, 5]},
    "63010": {"name": "Gillastig", "parameters": [5]},
}
FIRE_RISK_POINT = CENTRE
FORECAST_POINT = CENTRE

# MCF's flood mapping of Kävlingeån and Rönne å, as the scenario: the climate-adapted 100-year flow (WMS 12).
FLOOD_HAZARD_WMS = mcf_layer("12", "100-årsflöde, klimatanpassat (MCF)")
FLOOD_HIGHEST_WMS = mcf_layer("9", "Beräknat högsta flöde (MCF)")
FLOOD_ZONE_LABEL = "MCF:s klimatanpassade 100-årsflöde"
FLOOD_ZONE_FILES = [_SCENARIO / "mcf" / "mcf-100ar.geojson"]
# The scenario's simulated level sensors; only those following Ellinge are kept (levels.py).
LEVEL_SENSOR_FILE = _SCENARIO / "sensors" / "level-points.geojson"
