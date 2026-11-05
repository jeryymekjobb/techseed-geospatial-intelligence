"""Höörs kommun, by Ringsjöarna, with the winter floods in Skåne 2024 as its scenario; Flens
kommun's monitoring is the template (common.py). Ringsjödammen's flow and level give no live values
(checked 2026-11-04), so the flows are Rönne å's at Heåkra and Kävlingeån's at Ellinge, below the
lakes. The base map is the municipality's own (Geoinfo Mittskåne's Baskarta_Hoor_OpenData), for
internal use (D-2026-11-04b). Its state and inbox live in the unversioned data/monitoring/hoorkommun/.
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
# Höörs kommun's base map on Geoinfo Mittskåne's ArcGIS Server (folder OpenData, shared with Hörby; no
# token; copyright "(C) Höörs kommun och Lantmäteriet", no licence stated; checked 2026-11-04). A sparse
# map of lines and texts, 253, 253, 253 outside the municipality and between its lines, which is made
# transparent, so OpenStreetMap shows under it (tools/fetch_municipal_basemap.py).
MUNICIPAL_BASEMAPS = [{
    "id": "hoor", "kind": "arcgis",
    "url": "https://karta.geoinfomittskane.se/arcgis/rest/services/OpenData/Baskarta_Hoor_OpenData/MapServer",
    "label": "Höörs kommun (Baskarta)",
    "attribution": "Karta © Höörs kommun, Lantmäteriet – intern användning",
    "white_outside": True, "outside_colour": (253, 253, 253),
    "permission": "Internal use in the development department, as the user decided on 2026-11-04 (D-2026-11-04b); no licence stated.",
    "note": "Höörs kommun's Baskarta_Hoor_OpenData (Geoinfo Mittskåne), white outside the municipality.",
    "dir": DATA_DIR / "municipal-basemap" / "hoor",
}]
# The municipality (MCF's border, 13.37-13.67 E, 55.78-56.09 N) with a small margin.
MUNICIPAL_BASEMAP_BBOX = (13.35, 55.76, 13.69, 56.11)

_SCENARIO = scenario_data("skane2024")
OSM_TARGETS_FILE = _SCENARIO / "osm" / "targets-skane.geojson"
TERRAIN_FILE = _SCENARIO / "osm" / "terrain-skane.geojson"
TERRAIN_DIR = built_terrain("hoorkommun", _SCENARIO / "terrain")
# The offline map over the whole municipality once built (tools/build_offline_tiles.py --area), else the scenario's.
TILES_FILE, MAP_BBOX = built_tiles("hoorkommun", ("skane.mbtiles", (13.0, 55.6, 13.9, 55.98)), BBOX)

# SMHI's live flow every 15 minutes (hydroobs parameter 2), checked 2026-11-04.
FLOW_STATIONS = {"2128": "Heåkra (Rönne å)", "2126": "Ellinge (Kävlingeån)",
                 # Ringsjödammen gives no live flow, Snogeröd2 nothing since 2025 (silent, shown grey; 2026-11-04).
                 "2176": "Ringsjödammen övre", "10501": "Snogeröd 2"}
# Ringsjöarna's water level at Ringsjödammen (hydroobs parameter 3, one value a day, the height system not
# named; 54.94 m on 10 February 2024 is the archive's highest, as the Skåne 2024 scenario shows).
WATER_LEVEL_STATIONS = {"2176": "Ringsjödammen övre"}
RAIN_STATIONS = {"53530": "Hörby A"}
# SMHI's weather stations giving values on 2026-11-04, with the parameters each reports.
WEATHER_STATIONS = {
    "53530": {"name": "Hörby A", "parameters": [1, 3, 4, 7, 5]},
    # Added 2026-11-04 when every station SMHI lists as active in or within 5 km of the municipality was taken
    # in, as the user asked, even silent ones: a silent station is shown grey as a hint it may be out of order.
    "63030": {"name": "Sösdala", "parameters": [5]},
    # Rain gauges SMHI publishes near Ringsjöarna (VV, PST), which report only hours with rain
    # (sources.rain_gauge), live on 2026-11-04.
    **{key: {"name": name, "parameters": [], "rain_gauge": True} for key, name in (
        ("22128523", "Kungshult VV"),)},
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
