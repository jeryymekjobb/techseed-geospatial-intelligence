"""The rain of 25-27 May 2021 in Flens kommun: road 53 flooded south of Sparreholm.

Chosen 2026-10-21 from the feasibility study reports/2026-10-21-forstudie-flen-claude-opus-5-5.md
as the second event for the whole municipality, beside winter 2024 (flenkommun2024). SMHI warned of
heavy rain on Wednesday 26 May (SVT); on 25 May intense rain gave up to 60 mm in a day in parts of
eastern Götaland and Svealand (SMHI). On the morning of 27 May road 53 between Sparreholm and
Nyköping was flooded, the most water south of Sparreholm in Flens kommun, "between Spånga and
Hossebo, level with Skälby" (SVT 27 May 2021, 06:41; Trafikverket expected the road clear at about
21). Hebylund Kvarnsjön passed its record on 27 May; Sibro 2 and Hallbosjön rose until early June.
Like Skåne 2024 this is a replayed event with real data, not a scenario.

Its data live in the unversioned data/flenkommun2021/; the offline map, DEM, terrain and OSM layers
are flenkommun2024's (the same area, OSM as fetched in 2026).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.backend.scenarios import REPO_ROOT

DATA = REPO_ROOT / "data" / "flenkommun2021"
# The map area's offline map, DEM, terrain and OSM layers, shared with flenkommun2024.
SHARED = REPO_ROOT / "data" / "flenkommun2024"

INCIDENT = "flood"
INCIDENT_PLACE = "Nyköpingsån"
INCIDENT_AREA = "Flens kommun"

TITLE = "Regnet i Flens kommun 2021"
DATA_LABEL = "Historiska data maj–juni 2021 – uppspelning, inte live"
CONTROL_LABEL = "Scenario: FLOOD – Flens kommun maj 2021, historiska data"
# The summary the main screen shows, and the satellite monitor reads aloud, when the scenario
# comes to its start (satlog.js summaryState): what the demo shows and what is real.
SUMMARY = [
    "Regnet i Flens kommun i slutet av maj 2021. Det återges med verkliga data, inte i realtid.",
    "Kraftigt regn den 25 och 26 maj. På morgonen den 27 maj stod väg 53 under vatten söder om Sparreholm.",
    "SMHI:s vattenföring, nederbörd och väderradar, och MCF:s 100-årsflöde för Nyköpingsån, beräknat för ett framtida klimat.",
    "Radarbilder från Sentinel-1, också samma morgon som vägen svämmade över, och bilder från Sentinel-2 och Landsat 8.",
    "Nivågivarna är simulerade och följer SMHI:s stationer.",
]

FIRMS_FILES: list = []
TERRAIN_FILE = SHARED / "osm" / "terrain-flenkommun.geojson"
TARGETS_FILE = SHARED / "osm" / "targets-flenkommun.geojson"
WEATHER_DIR = DATA / "smhi"
# SMHI's measured flows (tools/fetch_smhi_hydro.py).
HYDRO_DIR = DATA / "hydro"
WIND_FILE = DATA / "era5-land" / "era5-land-flenkommun-2021.csv"
RADAR_DIR = DATA / "radar"
DEM_DIR = SHARED / "dem"
TERRAIN_DIR = SHARED / "terrain"
LANDSAT_DIR = DATA / "landsat"
# MET Norway's archived weather forecasts, as issued (tools/fetch_met_forecasts.py, met_forecast.py).
MET_FORECAST_DIR = DATA / "met-forecast"
# SMHI's observed lightning (tools/fetch_smhi_lightning.py).
LIGHTNING_DIR = DATA / "lightning"
SENTINEL2_DIR = DATA / "sentinel2"
SENTINEL1_DIR = DATA / "sentinel1"
MCF_DIR = DATA / "mcf"
# Meteosat's cloud mask every hour and at each image (tools/fetch_meteosat_clm.py).
METEOSAT_CLM_FILE = DATA / "meteosat-clm" / "clm.json"
TLE_DIR = DATA / "tle"
TLE_FILE_NAME = "tle-2021.json"

# Road 53 level with Skälby, where it was flooded.
FIRE_CENTRE = (58.983, 16.84)
FIRE_BBOX = (58.85, 59.24, 16.4, 17.05)  # min_lat, max_lat, min_lon, max_lon
# Map view: the municipality, from Hälleforsnäs in the north to Hallbosjön just south of it.
VIEW_BBOX = (58.85, 59.24, 16.4, 17.05)
# The offline map, the DEM and the satellite images (west, south, east, north): the municipality
# (16.42-17.04 E, 58.87-59.24 N in OpenStreetMap) with Hebylund Kvarnsjön and Floda A in the west
# and Hallbosjön in the south.
MAP_BBOX = (16.3, 58.8, 17.1, 59.28)
PERIOD_START = date(2021, 5, 18)
PERIOD_END = date(2021, 6, 9)
PLAYBACK_START = datetime(2021, 5, 20, 0, 0, tzinfo=timezone.utc)
PLAYBACK_END = datetime(2021, 6, 8, 0, 0, tzinfo=timezone.utc)
# Sentinel-1A passes at 05:07 UTC on 27 May, the morning road 53 was flooded.
CHECK_START_UTC = "2021-05-27T05:00:00Z"
# The demo check: just after that pass the level sensor that follows Hebylund alarms (above its record
# since 02 UTC) and the assessment reaches "Possible flood". Its SATCOM outage starts in the evening
# before the radar acquisition at 05:15 UTC on 1 June.
CHECK_PEAK_UTC = "2021-05-27T05:30:00Z"
CHECK_SENSORS = "1/8"
CHECK_OUTCOME = "Possible flood"
CHECK_SATCOM_UTC = "2021-05-31T21:00:00Z"

DATABASE = "flenkommun2021"
TILES_FILE = "flenkommun.mbtiles"

CAMERA_ROUTE = [
    {"lon": 12, "lat": 52, "height": 16_000_000, "pitch": -90, "seconds": 1.8},  # Earth over Europe
    {"lon": 15, "lat": 59, "height": 3_000_000, "pitch": -90, "seconds": 2.0},   # Southern Scandinavia
    {"lon": 16.7, "lat": 59.0, "height": 600_000, "pitch": -80, "seconds": 2.0},  # Södermanland
    {"lon": 16.7, "lat": 58.75, "height": 90_000, "pitch": -60, "seconds": 2.2},  # Flens kommun
]

# The flood's words for the land the radar's water is counted on and for the gauges.
FOCUS_LAND = "marken i Flens kommun"
RAIN_GAUGES = "SMHI:s mätare"
# SMHI's hourly rain (parameter 7) in the area, checked 2026-10-21: only Floda A, 11 km west of
# Flen; Eskilstuna A lies north of the map area.
RAIN_STATIONS = {"96040": "Floda A"}
# SMHI's stations that report the rain by the day (parameter 5, 06-06 UTC) in the map area,
# checked 2026-10-21 (tools/fetch_smhi_daily.py, daily_rain.py).
DAILY_RAIN_STATIONS = {
    "96060": "Granhed D", "96050": "Sköldinge", "96090": "Hälleforsnäs D", "96010": "Frändesta",
    "86520": "Vrena", "86500": "Björkvik D",
}
DAILY_RAIN_DIR = DATA / "smhi-daily"
# SMHI's hydrological stations with the flow every 15 minutes (parameter 2) in the area, all in
# Nyköpingsån's catchment, checked 2026-10-21. Christineholm's regulating dam has no 15-minute
# archive.
HYDRO_STATIONS = {
    "2614:2": "Hebylund Kvarnsjön",  # a small catchment west of Flen, 58 km²
    "2587:2": "Sibro 2",             # 775 km²
    "1273:2": "Hallbosjön",          # just south of the municipality, 1992 km²
}

# The satellites that imaged the area in the period (Planetary Computer catalogue, checked
# 2026-10-21) and the ISS, by NORAD number.
TLE_SATELLITES = {
    "39634": "Sentinel-1A", "41456": "Sentinel-1B", "40697": "Sentinel-2A", "42063": "Sentinel-2B",
    "39084": "Landsat 8", "25544": "ISS", "40732": "Meteosat-11",
}
TLE_START, TLE_END = "2021-05-15", "2021-06-11"
SATELLITE_ROLES = {
    "39634": {"firms": None, "instrument": "SAR", "role": "Radar, ser genom moln", "half_swath_km": None},
    "41456": {"firms": None, "instrument": "SAR", "role": "Radar, ser genom moln", "half_swath_km": None},
    "40697": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "42063": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "39084": {"firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "25544": {"firms": None, "instrument": None, "role": "Rymdstationen", "half_swath_km": None},
    # Meteosat-11 (MSG-4) at 0 degrees from 2018, whose cloud mask the demo shows (meteosat_clm.py).
    "40732": {"firms": None, "instrument": "SEVIRI", "role": "Geostationär, ser området hela tiden", "half_swath_km": None, "geostationary": True},
}
SATELLITE_LABEL = "Position 2021, beräknad ur banelement (SGP4) – inte en observation"

# Landsat has no usable scene: 19 May covers 82 % of the focus area with 49 % cloud over it, and
# 28 May is 43 % cloud (checked 2026-10-21). The optical images are Sentinel-2's.
LANDSAT_SCENES: dict = {}
LANDSAT_ROLES = {"before": "Före regnet", "during": "Under regnet", "after": "Efter regnet"}
LANDSAT_FOCUS_AREA = (16.45, 58.88, 16.95, 59.12)  # Flen, Sparreholm, Båven, Yngaren and road 53 by Skälby
# About 30 m over MAP_BBOX: 0.8 degrees of longitude and 0.48 of latitude at 59.0 N.
LANDSAT_SIZE = (1530, 1780)
# Sentinel-1 acquisitions on the descending tracks that cover the focus area whole (Planetary Computer
# catalogue, sentinel-1-grd, checked 2026-10-21; the start of the pass's product): before the rain,
# the morning after it, the morning road 53 was flooded and as the flows peaked.
SENTINEL1_ACQUISITIONS = [
    {"time_utc": "2021-05-20T05:15:36Z", "satellite": "Sentinel-1A", "norad": "39634"},
    {"time_utc": "2021-05-26T05:14:55Z", "satellite": "Sentinel-1B", "norad": "41456"},
    {"time_utc": "2021-05-27T05:07:25Z", "satellite": "Sentinel-1A", "norad": "39634"},
    {"time_utc": "2021-06-01T05:15:37Z", "satellite": "Sentinel-1A", "norad": "39634"},
    {"time_utc": "2021-06-02T05:06:44Z", "satellite": "Sentinel-1B", "norad": "41456"},
]
# Sentinel-2 (tools/fetch_sentinel2_scene.py): the clearest datatakes before, during and after, by
# product name up to the relative orbit (catalogue tile cloud 2-43 %; the tool measures the focus
# area's own: 47 % on 18 May, 2 % on 28 May, 25 % on 2 June).
SENTINEL2_SCENES = {
    "before": "S2B_MSIL2A_20210518T100559_R022",
    "during": "S2B_MSIL2A_20210528T100559_R022",
    "after": "S2A_MSIL2A_20210602T101031_R022",
}
# About 20 m over MAP_BBOX.
SENTINEL2_SIZE = (2295, 2670)

# What local media reported, each read 2026-10-21. The road's place is road 53 in OSM nearest Skälby,
# which the photo caption names; the article says only "south of Sparreholm". The time is the
# article's, as the flooding has no time of its own, and is marked approximate.
ROUTE_REPORT = "SVT Sörmland"
ROUTE_IMPACT_LABEL = "Översvämmad väg (rapporterat)"
ROUTE_SOURCE_LABEL = "lokala medier"
ROUTE_ATTRIBUTION = "SVT Sörmland"
ROUTE_IMPACTS = [
    {"time_utc": "2021-05-26T10:22:00Z", "kind": "alert", "approximate_time": True, "source_label": "SVT",
     "text": "Stora regnmängder över länet; räddningstjänsten i Nyköping får flera larm om översvämningar"},
    {"time_utc": "2021-05-27T04:41:00Z", "kind": "road", "approximate_time": True, "site": "Väg 53 vid Skälby",
     "latitude": 58.98322, "longitude": 16.84002, "source_label": "SVT",
     "text": "Väg 53 översvämmad söder om Sparreholm; Trafikverket räknar med att den är framkomlig vid 21-tiden"},
]
# No ROUTE_EXPOSURE_FILE, as for flenkommun2024.

# MCF's (formerly MSB's) overview flood maps: Nyköpingsån (2015) from Högsjö to the sea, which in
# the municipality reaches only Forssjön, Yngaren and Långhalsen's north shore; Flen's town, Båven
# and Sparreholm are not mapped. Only the climate-adapted 100-year flow (WMS layer 12, REST 3) and
# the highest calculated flow (WMS 9, REST 5), checked 2026-10-21.
FLOOD_HAZARD_WMS = {
    "url": "https://gis-tjanster.mcf.se/arcgis/services/Oversvamningskarteringar/karteringar/MapServer/WMSServer",
    "layers": {"12": "100-årsflöde, klimatanpassat (slutet av seklet)", "9": "Beräknat högsta flöde"},
    "attribution": "Översvämningskartering © MCF (tidigare MSB)",
    "visible": ["12"],
}
# The same layers for PostGIS (tools/fetch_mcf_flood_maps.py): REST id, title and label.
MCF_LAYERS = {
    "100ar": (3, "100-årsflöde (Klimatanpassat flöde för slutet av seklet)", "MCF, klimatanpassat"),
    "bhf": (5, "Beräknat högsta flöde", "MCF"),
}
FLOOD_AREA_WORD = "det klimatanpassade 100-årsflödet"
FLOOD_MODELS = "MCF:s modell för slutet av seklet"
# Synthetic level sensors where larger roads cross MCF's climate-adapted 100-year flow of
# Nyköpingsån (tools/derive_level_sensor_points.py), each following the nearest of Hebylund Kvarnsjön
# (upstream, on no mapped stretch), Sibro 2 and Hallbosjön. Only Hebylund passed its record (1.57 m³/s,
# December 2019, measured since 2018), at 02 UTC on 27 May, so only the sensor that follows it alarms.
LEVEL_SENSOR_FILE = DATA / "sensors" / "level-points.geojson"
LEVEL_SENSOR_RIVERS = {"Nyköpingsån": ["2614:2", "2587:2", "1273:2"]}
SENSOR_WORDS = {"sensors": "nivågivare", "the_sensors": "nivågivarna", "alarming": "larmande"}

FORECAST_WEATHER_FILES: list = []
FORECAST_METHOD = ""
FORECAST_REPORT = ""
SPATIAL_SOURCE = ("PostGIS (lokal databas): OSM-mål © OpenStreetMap contributors, klimatanpassade 100-årsflöden "
                  "© MCF (tidigare MSB)")

ATTRIBUTION = {
    "osm": "© OpenStreetMap contributors (ODbL)",
    "lantmateriet": "© Lantmäteriet",
    "smhi": "SMHI öppna data (CC BY 4.0 SE): nederbörd vid Floda A, väderradar, vattenföring",
    "sentinel": "Innehåller bearbetade Copernicus Sentinel-data 2021",
    "era5_land": "Innehåller bearbetad information från Copernicus Climate Change Service (ERA5-Land), CC BY 4.0",
    "mcf": "Översvämningskartering © MCF (tidigare MSB)",
    "copernicus_dem": (
        "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 "
        "provided under COPERNICUS by the European Union and ESA; all rights reserved"
    ),
}
