"""Flens kommun: the first area of the continuous monitoring.

The stations are those of the Flen scenarios (app/backend/scenarios/flenkommun2024.py), checked
there on 2026-10-21; the municipality's border is MCF's (Basdata/Kommuner, kommunkod 0482). The base
map is the municipality's own, as the one-pager makes GIS the default: the user decided on
2026-11-03 to use it the same way as Sundsvall's and Västerås's, fetched once and kept locally
(tools/fetch_municipal_basemap.py --area flenkommun), for internal use. OpenStreetMap lies under it,
where the municipal map is white, and its road numbers and railway tunnels over it (the demo's
offline map flenkommun.mbtiles).

Its state, cached border and statistics and the inbox live in the unversioned
data/monitoring/flenkommun/.
"""

from __future__ import annotations

from app.backend.scenarios import REPO_ROOT
from app.monitoring.areas.common import *  # noqa: F403 - the template's shared satellites, limits and contacts

NAME = "Flens kommun"
MUNICIPALITY_CODE = "0482"
COUNTY = "Södermanlands län"
# SMHI's id of the county in its warnings (affectedAreas), checked 2026-11-03.
SMHI_COUNTY_ID = 4
# Krisinformation's VMA and news count when an area of theirs names one of these.
KRISINFO_WORDS = ("Södermanland", "Flen")
# west, south, east, north: the municipality (16.42-17.04 E, 58.87-59.24 N) with a margin, as the
# Flen scenarios' MAP_BBOX.
BBOX = (16.3, 58.8, 17.1, 59.28)
CENTRE = (59.06, 16.73)

DATA_DIR = REPO_ROOT / "data" / "monitoring" / "flenkommun"

# Flens kommun's background map (the folder Flenkartan of gis.flen.se, ArcGIS Server 11.3; copyright
# "Lantmäteriet/GIS"): it covers the whole municipality and is white outside it, and it has no WMS, so
# it is fetched by ArcGIS REST export (checked 2026-11-03). Internal use, as the user decided.
MUNICIPAL_BASEMAPS = [{
    "id": "flen",
    "kind": "arcgis",
    "url": "https://gis.flen.se/arcgis/rest/services/Flenkartan/Bakgrundskarta_AGOL/MapServer",
    "label": "Flens kommun (Bakgrundskarta)",
    "attribution": "Karta © Flens kommun, Lantmäteriet – intern användning",
    "white_outside": True,
    # Not pure white outside the municipality but 253, 253, 253, at every zoom; its roads are pure
    # white and stay (checked 2026-11-03).
    "outside_colour": (253, 253, 253),
    "permission": "The user decided on 2026-11-03 that Techseed may use Flens kommun's map internally and keep it locally.",
    "note": "Flens kommun's Bakgrundskarta_AGOL (Lantmäteriet/GIS), white outside the municipality.",
    "dir": DATA_DIR / "municipal-basemap" / "flen",
}]
# The municipality (16.42-17.04 E, 58.87-59.24 N in OpenStreetMap) with a small margin.
MUNICIPAL_BASEMAP_BBOX = (16.4, 58.85, 17.06, 59.25)
# Flens kommun's own GIS for what an alarm may threaten (app/monitoring/gis.py), checked 2026-11-03:
# the municipal services (Kommunala_verksamheter), the comprehensive plan's care units (only those for
# the elderly) and transport, and the primary map's buildings. Left out after the check of laws and
# rules on 2026-11-03: housing for people with disabilities (until its security and data protection
# are reviewed, the user's decision), social services' premises, addresses and property designations.
_GIS = "https://gis.flen.se/arcgis/rest/services"
GIS_ATTRIBUTION = "Flens kommun (GIS) och OpenStreetMap – intern användning"
GIS_NOTE = "Intern – bygger på Flens kommuns GIS. Äldreomsorgens enheter och boenden för personer med funktionsnedsättning ingår inte."
_SERVICES = f"{_GIS}/Kommunala_verksamheter/MapServer"
GIS_FACILITIES = [
    {"service": _SERVICES, "layer": 10, "fields": ["Namn"], "name_field": "Namn", "category": "Förskola", "group": "school",
     "source": GIS_ATTRIBUTION},
    {"service": _SERVICES, "layer": 9, "fields": ["Namn"], "name_field": "Namn", "category": "Grundskola", "group": "school",
     "source": GIS_ATTRIBUTION},
    {"service": _SERVICES, "layer": 8, "fields": ["Namn"], "name_field": "Namn", "category": "Gymnasium", "group": "school",
     "source": GIS_ATTRIBUTION},
    {"service": _SERVICES, "layer": 5, "fields": ["Vårdcentral"], "name_field": "Vårdcentral", "category": "Vårdcentral", "group": "health",
     "source": GIS_ATTRIBUTION},
    {"service": _SERVICES, "layer": 2, "fields": ["Distrikt"], "name_field": "Distrikt", "category": "Distriktssköterska", "group": "health",
     "source": GIS_ATTRIBUTION},
    {"service": _SERVICES, "layer": 4, "fields": ["Distrikt"], "name_field": "Distrikt", "category": "Folktandvård", "group": "health",
     "source": GIS_ATTRIBUTION},
    # The comprehensive plan's care units for the elderly (OP/Kap2_Samhallsservice, layer 3): the
    # service gives their names but no geometry (checked 2026-11-03), so none is placed until it does.
    {"service": f"{_GIS}/OP/Kap2_Samhallsservice/MapServer", "layer": 3, "fields": ["Namn", "Beskrivnin", "Beskrivn_1"],
     "name_field": "Namn", "category": "Äldreomsorg", "category_field": "Beskrivn_1", "group": "care",
     "only": {"Beskrivnin": ("Äldre",)}, "source": GIS_ATTRIBUTION},
]
GIS_BUILDINGS = {"service": f"{_GIS}/Primärkarta_Flen/MapServer", "layer": 3}
# The comprehensive plan's transport layers (OP/Kap3_Transportinfrastruktur) give no geometry (every
# query with it fails or returns none, checked 2026-11-03), so the roads and railways come from
# OpenStreetMap, marked so, and bus stops are left out.
# What the municipality's services lack, from the Flen scenarios' OpenStreetMap targets, marked as OSM.
OSM_TARGETS_FILE = REPO_ROOT / "data" / "flenkommun2024" / "osm" / "targets-flenkommun.geojson"
OSM_ADDITIONS = {"train_station": "Järnvägsstation", "church": "Kyrka", "chapel": "Kapell"}
OSM_ROAD_TYPES = {"primary": "större väg", "secondary": "större väg", "tertiary": "mindre väg", "unclassified": "mindre väg"}
PLACE_TYPES = ("town", "village", "hamlet")
# OpenStreetMap's lakes of the Flen scenarios, the known water of Sentinel-1's water mask (sentinel1.py).
TERRAIN_FILE = REPO_ROOT / "data" / "flenkommun2024" / "osm" / "terrain-flenkommun.geojson"
# MCF's climate-adapted 100-year flow of Nyköpingsån, as the Flen scenarios (tools/fetch_mcf_flood_maps.py).
FLOOD_ZONE_FILES = [REPO_ROOT / "data" / "flenkommun2024" / "mcf" / "mcf-100ar.geojson"]

# The demo's offline OpenStreetMap of the Flen scenarios (data/tiles/), served by the tiles service.
TILES_FILE = "flenkommun.mbtiles"
MAP_BBOX = (16.3, 58.8, 17.1, 59.28)

# SMHI's stations with the flow every 15 minutes (hydroobs parameter 2), all in Nyköpingsån's
# catchment; Hallbosjön lies just south of the municipality.
FLOW_STATIONS = {
    "2614": "Hebylund Kvarnsjön",
    "2587": "Sibro 2",
    "1273": "Hallbosjön",
}
# SMHI's hourly rain (metobs parameter 7): only Floda A, 11 km west of Flen.
RAIN_STATIONS = {"96040": "Floda A"}

# SMHI's weather stations in and around the municipality, active on 2026-11-03 (metobs's station
# lists), with the parameters each reports (sources.STATION_PARAMETERS): the automatic stations with
# temperature, wind and the hour's rain, and the stations with the rain by the day.
WEATHER_STATIONS = {
    "96040": {"name": "Floda A", "parameters": [1, 3, 4, 7, 5]},
    "96190": {"name": "Eskilstuna A", "parameters": [1, 3, 4, 7, 5]},
    "86420": {"name": "Kolmården-Strömsfors A", "parameters": [1, 3, 4, 7, 5]},
    "19025": {"name": "Höksta", "parameters": [1, 3, 4]},
    "96060": {"name": "Granhed D", "parameters": [5]},
    "96090": {"name": "Hälleforsnäs D", "parameters": [5]},
    "96050": {"name": "Sköldinge", "parameters": [5]},
    "86520": {"name": "Vrena", "parameters": [5]},
    "87600": {"name": "Aspa D", "parameters": [5]},
    "86660": {"name": "Nyköping", "parameters": [5]},
    "87400": {"name": "Oxelösund", "parameters": [1, 5]},
}

FIRE_RISK_POINT = CENTRE
FORECAST_POINT = CENTRE
# MCF's (formerly MSB's) flood maps of Nyköpingsån, as in the Flen scenarios
# (app/backend/scenarios/flenkommun2024.py): the climate-adapted 100-year flow, and the highest
# calculated flow.
FLOOD_HAZARD_WMS = mcf_layer("12", "100-årsflöde, klimatanpassat (MCF)")  # noqa: F405
FLOOD_HIGHEST_WMS = mcf_layer("9", "Beräknat högsta flöde (MCF)")  # noqa: F405
FLOOD_ZONE_LABEL = "MCF:s klimatanpassade 100-årsflöde"
# The Flen scenarios' 3D terrain from Copernicus's DEM (tools/build_terrain.py), quantized mesh.
TERRAIN_DIR = REPO_ROOT / "data" / "flenkommun2024" / "terrain"
# The Flen scenarios' simulated level sensors where larger roads cross MCF's 100-year flow of
# Nyköpingsån (levels.py), each following Sibro 2 or Hallbosjön.
LEVEL_SENSOR_FILE = REPO_ROOT / "data" / "flenkommun2024" / "sensors" / "level-points.geojson"
# Flens kommun's cloudburst mapping of Flen's town (Skyfallskartering, gis.flen.se): the greatest water
# depth at a 100- and a 500-year rain, which the user allowed for internal use on 2026-11-04. It has no
# WMS and is fetched as transparent tiles by ArcGIS REST export (tools/fetch_municipal_basemap.py).
_SKYFALL = f"{_GIS}/Skyfallskartering/MapServer"
_SKYFALL_BBOX = (16.54, 59.02, 16.68, 59.10)
MUNICIPAL_BASEMAPS += [
    {"id": f"skyfall{years}", "kind": "arcgis", "url": _SKYFALL, "layers": f"show:{layer}", "transparent": True,
     "overlay": True, "bbox": _SKYFALL_BBOX, "min_zoom": 12, "max_zoom": 16,
     "label": f"Skyfall, största vattendjup vid {years}-årsregn (Flens kommun)",
     "attribution": "Skyfallskartering © Flens kommun – intern användning",
     "permission": "The user allowed internal use of Flens kommun's cloudburst mapping on 2026-11-04.",
     "note": f"Flens kommun's Skyfallskartering, layer {layer}: the greatest water depth at a {years}-year rain in Flen's town.",
     "dir": DATA_DIR / "municipal-basemap" / f"skyfall{years}"}
    for years, layer in ((100, 8), (500, 3))
]
