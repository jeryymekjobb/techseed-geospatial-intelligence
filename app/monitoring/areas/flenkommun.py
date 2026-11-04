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
POLL_SECONDS = 300

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
GIS_ATTRIBUTION = "Flens kommun (GIS) – intern användning"
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

# The satellites whose data the monitoring uses, as the demos show only those that send data: NASA
# FIRMS's VIIRS and MODIS satellites, and the Sentinel-1, Sentinel-2 and Landsat satellites of the
# latest images (sentinel1.py, sentinel2.py), by NORAD number (Space-Track's catalogue, checked
# 2026-11-04). Their current element sets come from Space-Track (satellites.py).
SATELLITES = {
    "37849": {"name": "Suomi NPP", "firms": "SNPP", "instrument": "VIIRS", "role": "FIRMS-detektioner (VIIRS)", "half_swath_km": 1520.0},
    "43013": {"name": "NOAA-20", "firms": "N20", "instrument": "VIIRS", "role": "FIRMS-detektioner (VIIRS)", "half_swath_km": 1520.0},
    "54234": {"name": "NOAA-21", "firms": "N21", "instrument": "VIIRS", "role": "FIRMS-detektioner (VIIRS)", "half_swath_km": 1520.0},
    "25994": {"name": "Terra", "firms": "Terra", "instrument": "MODIS", "role": "FIRMS-detektioner (MODIS)", "half_swath_km": 1165.0},
    "27424": {"name": "Aqua", "firms": "Aqua", "instrument": "MODIS", "role": "FIRMS-detektioner (MODIS)", "half_swath_km": 1165.0},
    "62261": {"name": "Sentinel-1C", "firms": None, "instrument": "SAR", "role": "Radar, ser genom moln", "half_swath_km": 125.0},
    "66315": {"name": "Sentinel-1D", "firms": None, "instrument": "SAR", "role": "Radar, ser genom moln", "half_swath_km": 125.0},
    "40697": {"name": "Sentinel-2A", "firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "42063": {"name": "Sentinel-2B", "firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "60989": {"name": "Sentinel-2C", "firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "39084": {"name": "Landsat 8", "firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "49260": {"name": "Landsat 9", "firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
}

# SMHI's stations with the flow every 15 minutes (hydroobs parameter 2), all in Nyköpingsån's
# catchment; Hallbosjön lies just south of the municipality.
FLOW_STATIONS = {
    "2614": "Hebylund Kvarnsjön",
    "2587": "Sibro 2",
    "1273": "Hallbosjön",
}
# SMHI's hourly rain (metobs parameter 7): only Floda A, 11 km west of Flen.
RAIN_STATIONS = {"96040": "Floda A"}

# Proposals, to be tuned with the municipality: a flow is high above the 99th percentile of the
# station's daily flows in SMHI's corrected archive, at two readings in a row, and a record above
# the archive's highest daily flow. Rain of at least RAIN_CONFIRM_MM in 24 hours at a rain station
# confirms a high flow as a second source.
FLOW_HIGH_PERCENTILE = 99.0
RAIN_CONFIRM_MM = 10.0

# NASA FIRMS's near-real-time fire detections over BBOX (needs ~/.firms_map_key or FIRMS_MAP_KEY).
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

# Proposals, as the flow limits: a cloudburst when SMHI's radar estimates at least CLOUDBURST_MM_H
# somewhere in the municipality, confirmed by CLOUDBURST_GAUGE_MM in the last hour at a rain station
# or a warning; raised fire risk when SMHI's fire risk class (FWI, or grass fire) is at least
# FIRE_RISK_CLASS today or tomorrow, at FIRE_RISK_POINT.
CLOUDBURST_MM_H = 20.0
# The satellite monitor logs Sentinel-1's water outside the lakes from this share of the land (%), a proposal.
S1_WATER_LOG_PCT = 0.5
CLOUDBURST_GAUGE_MM = 10.0
FIRE_RISK_CLASS = 5
FIRE_RISK_POINT = CENTRE
FORECAST_POINT = CENTRE
# MCF's (formerly MSB's) flood maps of Nyköpingsån, as in the Flen scenarios
# (app/backend/scenarios/flenkommun2024.py): the climate-adapted 100-year flow.
FLOOD_HAZARD_WMS = {
    "url": "https://gis-tjanster.mcf.se/arcgis/services/Oversvamningskarteringar/karteringar/MapServer/WMSServer",
    "layers": "12",
    "label": "100-årsflöde, klimatanpassat (MCF)",
    "attribution": "Översvämningskartering © MCF (tidigare MSB)",
}
# The same mapping's highest calculated flow (WMS layer 9), as the Flen scenarios show it.
FLOOD_HIGHEST_WMS = {**FLOOD_HAZARD_WMS, "layers": "9", "label": "Beräknat högsta flöde (MCF)"}
# The Flen scenarios' 3D terrain from Copernicus's DEM (tools/build_terrain.py), quantized mesh.
TERRAIN_DIR = REPO_ROOT / "data" / "flenkommun2024" / "terrain"
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

FIRMS_SOURCES = ("VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT", "MODIS_NRT")
FIRMS_DAYS = 2
# Detections within this distance belong to the same fire.
FIRE_CLUSTER_KM = 1.0
# Known heat sources that are not fires in the open (industry, power plants), as
# (name, latitude, longitude, radius in km). None is entered for Flens kommun yet.
KNOWN_HEAT_SOURCES: list[tuple[str, float, float, float]] = []
# Days with planned fires, as (month, day, name): a fire then is not dismissed, but marked as
# possibly planned.
FIRE_CALENDAR = ((4, 30, "valborgsmässoafton"),)

# Who is to be contacted by kind of event, by role only: names and numbers stay out of the
# repository. AN EXAMPLE, not agreed with the municipality or the rescue service.
CONTACTS_NOTE = "Exempel – inte överenskommet med kommunen eller räddningstjänsten"
CONTACTS = {
    "flood": ["Räddningstjänstens inre befäl i beredskap", "Kommunens tjänsteperson i beredskap (TiB)",
              "Kommunens VA-ansvarige i beredskap", "Länsstyrelsens tjänsteperson i beredskap"],
    "fire": ["Räddningstjänstens inre befäl i beredskap", "Kommunens tjänsteperson i beredskap (TiB)",
             "Länsstyrelsens tjänsteperson i beredskap"],
    "erosion": ["Kommunens tjänsteperson i beredskap (TiB)", "SGI:s tjänsteperson i beredskap"],
    "landslide": ["Räddningstjänstens inre befäl i beredskap", "Kommunens tjänsteperson i beredskap (TiB)",
                  "SGI:s tjänsteperson i beredskap"],
    "vma": ["Kommunens tjänsteperson i beredskap (TiB)", "Räddningstjänstens inre befäl i beredskap"],
}
