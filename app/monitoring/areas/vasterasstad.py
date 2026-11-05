"""Västerås stad, with Svartån in September 2023 as its scenario; Flens kommun's monitoring is the
template (common.py). The base map is the city's own colour map, already fetched for the scenario,
which the user allowed for internal use on 2026-10-28. Its state and inbox live in the unversioned
data/monitoring/vasterasstad/.
"""

from __future__ import annotations

from app.monitoring.areas.common import *  # noqa: F403 - the template's shared satellites, limits and contacts
from app.monitoring.areas.common import built_terrain, built_tiles, data_dir, mcf_layer, scenario_data

NAME = "Västerås stad"
MUNICIPALITY_CODE = "1980"
COUNTY = "Västmanlands län"
# SMHI's id of the county in its warnings (affectedAreas, metadata/area.json), checked 2026-11-04.
SMHI_COUNTY_ID = 19
KRISINFO_WORDS = ("Västmanland", "Västerås")
# west, south, east, north: the municipality (MCF's border, 16.24-16.97 E, 59.45-59.85 N) with a margin.
BBOX = (16.1, 59.4, 17.05, 59.9)
CENTRE = (59.61, 16.55)
DATA_DIR = data_dir("vasterasstad")

_SCENARIO = scenario_data("vasteras-sep2023")
MUNICIPAL_BASEMAPS = [{
    "id": "vasteraskarta", "url": "https://kartserver.vasteras.se/geoserver/wms", "layer": "bakgrundskartor:topowebbkartan",
    "label": "Västerås stad (karta)", "attribution": "Karta © Västerås stad, Lantmäteriet – intern användning",
    "permission": "The user confirmed on 2026-10-28 that Techseed may use Västerås stad's data internally; no public showings.",
    "note": "Västerås stad's colour map (topowebbkartan) from its Origo maps.",
    # The whole municipality in the monitoring's own folder (tools.fetch_municipal_basemap --area
    # vasterasstad); the scenario's map over its area until that is fetched (service.map_dir).
    "dir": DATA_DIR / "municipal-basemap" / "karta",
    "fallback_dir": _SCENARIO / "municipal-basemap" / "karta",
}]
# The municipality (MCF's border, 16.24-16.97 E, 59.45-59.85 N) with a small margin.
MUNICIPAL_BASEMAP_BBOX = (16.21, 59.43, 17.0, 59.87)
OSM_TARGETS_FILE = _SCENARIO / "osm" / "targets-vasteras.geojson"
TERRAIN_FILE = _SCENARIO / "osm" / "terrain-vasteras.geojson"
TERRAIN_DIR = built_terrain("vasterasstad", _SCENARIO / "terrain")
# The offline map over the whole municipality once built (tools/build_offline_tiles.py --area), else the scenario's.
TILES_FILE, MAP_BBOX = built_tiles("vasterasstad", ("vasteras.mbtiles", (16.1, 59.5, 16.9, 59.8)), BBOX)

# SMHI's live flow every 15 minutes (hydroobs parameter 2), as the scenario, checked 2026-11-04.
FLOW_STATIONS = {"2773": "Åkesta kvarn (Svartån)", "2218": "Berg (Kolbäcksån)", "2217": "Gränvad (Sagån)"}
RAIN_STATIONS = {"96560": "Sala A", "96190": "Eskilstuna A"}
# SMHI's weather stations giving values on 2026-11-04, with the parameters each reports.
WEATHER_STATIONS = {
    "96560": {"name": "Sala A", "parameters": [1, 3, 4, 7, 5]},
    "96190": {"name": "Eskilstuna A", "parameters": [1, 7, 5]},
    "96350": {"name": "Västerås", "parameters": [5]},
    # Added 2026-11-04 when every station SMHI lists as active in or within 5 km of the municipality was taken
    # in, as the user asked, even silent ones: a silent station is shown grey as a hint it may be out of order.
    "96390": {"name": "Hallstaberg", "parameters": [5]},
}
FIRE_RISK_POINT = CENTRE
FORECAST_POINT = CENTRE

# MCF's flood mapping of Svartån, as the scenario: the climate-adapted 100-year flow (WMS 12).
FLOOD_HAZARD_WMS = mcf_layer("12", "100-årsflöde, klimatanpassat (MCF)")
FLOOD_HIGHEST_WMS = mcf_layer("9", "Beräknat högsta flöde (MCF)")
FLOOD_ZONE_LABEL = "MCF:s klimatanpassade 100-årsflöde"
FLOOD_ZONE_FILES = [_SCENARIO / "mcf" / "mcf-100ar.geojson"]
LEVEL_SENSOR_FILE = _SCENARIO / "sensors" / "level-points.geojson"
# The city's cloudburst mapping (Svartån 2023's MUNICIPAL_WMS, ArcGIS Server WMS): the greatest water
# depth at a 100-year rain, internal use as the user allowed on 2026-10-28 and in the monitoring on
# 2026-11-04. A model, not an observation.
WMS_OVERLAYS = [
    {"id": "skyfall100", "url": "https://kartor.vasteras.se/arcgis/services/ext/sk_skyfall_wms/MapServer/WMSServer", "layers": "1",
     "label": "Skyfall, största vattendjup vid 100-årsregn (Västerås stad)", "attribution": "Skyfallskartering © Västerås stad – intern användning"},
]
