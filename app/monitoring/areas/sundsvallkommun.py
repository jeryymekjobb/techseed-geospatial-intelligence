"""Sundsvalls kommun, with Sundsvall 2026, the floods of February and December 2020, November 2023
and Ljungan in August 2023 as its scenarios; Flens kommun's monitoring is the template (common.py).

SMHI's stations on Selångersån and Ljungan in the municipality (Skallböle, Torpshammar) give only
their corrected archive, no live values (checked 2026-11-04), so the flow is read at Norrsjön, on
Ljungan upstream in Ånge; the scenarios' level sensors follow archived or modelled stations and are
left out. The base map is the municipality's Kartan, already fetched for the scenarios, which the
user allowed on 2026-10-14 to be shown and kept locally. Its state and inbox live in the unversioned
data/monitoring/sundsvallkommun/.
"""

from __future__ import annotations

from app.monitoring.areas.common import *  # noqa: F403 - the template's shared satellites, limits and contacts
from app.monitoring.areas.common import built_terrain, built_tiles, data_dir, mcf_layer, scenario_data

NAME = "Sundsvalls kommun"
MUNICIPALITY_CODE = "2281"
COUNTY = "Västernorrlands län"
# SMHI's id of the county in its warnings (affectedAreas, metadata/area.json), checked 2026-11-04.
SMHI_COUNTY_ID = 22
KRISINFO_WORDS = ("Västernorrland", "Sundsvall")
# west, south, east, north: the municipality (MCF's border, 16.25-18.23 E, 62.09-62.95 N) with a margin.
BBOX = (16.15, 62.0, 18.3, 63.0)
CENTRE = (62.39, 17.31)
DATA_DIR = data_dir("sundsvallkommun")

_SCENARIO = scenario_data("sundsvall2026")
MUNICIPAL_BASEMAPS = [{
    "id": "sundsvall", "url": "https://karta.sundsvall.se/geoserver/wms", "layer": "Kartan",
    "label": "Sundsvalls kommun (Kartan)",
    "attribution": "Karta © Sundsvalls kommun, Lantmäteriet, Trafikverket – intern användning",
    "white_outside": True,
    "permission": "The user confirmed on 2026-10-14 that the demo may show the map and keep it locally.",
    "note": "Kartan draws the municipality's, Lantmäteriet's and Trafikverket's layers; white outside the municipality.",
    "dir": _SCENARIO / "municipal-basemap",
}]
# The scenarios' fetched area; a new fetch keeps to it.
MUNICIPAL_BASEMAP_BBOX = (16.9, 62.15, 17.8, 62.62)
OSM_TARGETS_FILE = _SCENARIO / "osm" / "targets-sundsvall.geojson"
TERRAIN_FILE = _SCENARIO / "osm" / "terrain-sundsvall.geojson"
TERRAIN_DIR = built_terrain("sundsvallkommun", _SCENARIO / "terrain")
# The offline map over the whole municipality once built (tools/build_offline_tiles.py --area), else the scenario's.
TILES_FILE, MAP_BBOX = built_tiles("sundsvallkommun", ("sundsvall.mbtiles", (16.9, 62.15, 17.8, 62.62)), BBOX)

# SMHI's live flow every 15 minutes (hydroobs parameter 2), checked 2026-11-04.
FLOW_STATIONS = {"2053": "Norrsjön (Ljungan)",
                 # In or near the municipality, giving SMHI's archive only (silent, shown grey; 2026-11-04).
                 "1650": "Skallböle (Ljungan)", "1471": "Torpshammar (Ljungan)", "2185": "Bergeforsen (Indalsälven)"}
# SMHI's sea level by the hour (cm in RH2000) at Spikarna, in the municipality; the limit a proposal, as Vellinge's.
SEA_LEVEL_STATIONS = {"2061": "Spikarna"}
SEA_LEVEL_HIGH_CM = 100.0
# SMHI's automatic stations with the hour's rain (metobs parameter 7).
RAIN_STATIONS = {"127130": "Brämön A", "126290": "Torpshammar A"}
# SMHI's weather stations giving values on 2026-11-04, with the parameters each reports.
WEATHER_STATIONS = {
    "127130": {"name": "Brämön A", "parameters": [1, 3, 4, 7, 5]},
    "126290": {"name": "Torpshammar A", "parameters": [1, 3, 4, 7, 5]},
    "127310": {"name": "Sundsvall-Timrå Flygplats", "parameters": [1, 3, 4]},
    # Added 2026-11-04 when every station SMHI lists as active in or within 5 km of the municipality was taken
    # in, as the user asked, even silent ones: a silent station is shown grey as a hint it may be out of order.
    "127340": {"name": "Indal", "parameters": [5]},
    "126240": {"name": "Slättån", "parameters": [5]},
    "126170": {"name": "Ulvsjön D", "parameters": [5]},
    # The municipality's own rain gauges, which SMHI publishes and the scenarios show; they report only
    # hours with rain (sources.rain_gauge), all live on 2026-11-04.
    **{key: {"name": name, "parameters": [], "rain_gauge": True} for key, name in (
        ("2222813", "Fillan"), ("2222814", "Heffners"), ("2222818", "Bredsand"), ("2222811", "Essvik"),
        ("2222812", "Bällsta"), ("2222819", "Stångom"), ("2222815", "Stöde"), ("2222816", "Indal"), ("22228110", "Söråker"))},
}
FIRE_RISK_POINT = CENTRE
FORECAST_POINT = CENTRE

# MCF's flood mapping of Selångersån and Ljungan, as the scenarios: the 100-year flow (WMS 13).
FLOOD_HAZARD_WMS = mcf_layer("13", "100-årsflöde (MCF)")
FLOOD_HIGHEST_WMS = mcf_layer("9", "Beräknat högsta flöde (MCF)")
FLOOD_ZONE_LABEL = "MCF:s 100-årsflöde"
FLOOD_ZONE_FILES = [_SCENARIO / "mcf" / "mcf-100ar.geojson"]
# The municipality's cloudburst model (Sundsvall 2026's MUNICIPAL_WMS): the greatest water depth at a
# 30-, 100- and 500-year rain, straight from its geoserver. Its terms allow use only by five
# municipalities unless agreed; the user confirmed its use on 2026-10-06 and in the monitoring on
# 2026-11-04. A model, not an observation.
WMS_OVERLAYS = [
    {"id": f"skyfall{years}", "url": "https://karta.sundsvall.se/geoserver/wms", "layers": f"SundsvallsKommun:{years}-ar_maxvattendjup",
     "label": f"Skyfall, största vattendjup vid {years}-årsregn (Sundsvalls kommun)",
     "attribution": "Skyfallsmodell © Sundsvalls kommun – intern användning"}
    for years in (30, 100, 500)
]
