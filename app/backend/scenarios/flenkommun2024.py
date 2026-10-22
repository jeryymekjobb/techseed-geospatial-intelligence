"""The high flows of winter 2024 in Flens kommun and Nyköpingsån below it.

Chosen 2026-10-21 from the feasibility study reports/2026-10-21-forstudie-flen-claude-opus-
5-5.md; the user asked for both Flen's town and the whole municipality, each for winter 2024
and for a second event. After a wet January, rain on snow on 16 February (Floda A 17.4 mm;
the snow at Granhed went from 10 cm on 15 February to none on 19 February) raised the flows
of Nyköpingsån's catchment: Hebylund Kvarnsjön peaked on 17 February, Sibro 2 on 27 February
(its highest since 2012) and Hallbosjön, just south of the municipality, on 8 March (41.0 m³/s,
the ninth highest in 94 years). On 7 February the municipality switched off the lights along
the Åpromenaden by Flensån for the high water (flen.se); on 25 February SMHI warned (orange)
for Nyköpingsån at Hallbosjön, where the railway Sala-Oxelösund was threatened (SN 27
February). No flooding inside the municipality is documented beyond that. Like Skåne 2024
this is a replayed event with real data, not a scenario.

Its data live in the unversioned data/flenkommun2024/.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.backend.scenarios import REPO_ROOT

DATA = REPO_ROOT / "data" / "flenkommun2024"

INCIDENT = "flood"
INCIDENT_PLACE = "Nyköpingsån"
INCIDENT_AREA = "Flens kommun"

TITLE = "Höga flöden i Flens kommun 2024"
DATA_LABEL = "Historiska data vintern 2024 – uppspelning, inte live"
CONTROL_LABEL = "Scenario: FLOOD – Flens kommun vintern 2024, historiska data"
# The summary the main screen shows, and the satellite monitor reads aloud, when the scenario
# comes to its start (satlog.js summaryState): what the demo shows and what is real.
SUMMARY = [
    "Vinterns höga flöden 2024 i Flens kommun och Nyköpingsån. De återges med verkliga data, inte i realtid.",
    "Regn på snö i mitten av februari höjde flödena. Hallbosjön, söder om kommunen, nådde den 8 mars sitt nionde högsta flöde på 94 år.",
    "SMHI:s vattenföring, nederbörd och väderradar, och MCF:s 100-årsflöde för Nyköpingsån, beräknat för ett framtida klimat.",
    "Radarbilder från Sentinel-1 och bilder från Sentinel-2 och Landsat 8 före, under och efter.",
    "Nivågivarna är simulerade och följer SMHI:s stationer.",
]

FIRMS_FILES: list = []
TERRAIN_FILE = DATA / "osm" / "terrain-flenkommun.geojson"
TARGETS_FILE = DATA / "osm" / "targets-flenkommun.geojson"
WEATHER_DIR = DATA / "smhi"
# SMHI's measured flows (tools/fetch_smhi_hydro.py).
HYDRO_DIR = DATA / "hydro"
WIND_FILE = DATA / "era5-land" / "era5-land-flenkommun-2024.csv"
RADAR_DIR = DATA / "radar"
DEM_DIR = DATA / "dem"
TERRAIN_DIR = DATA / "terrain"
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
TLE_FILE_NAME = "tle-2024.json"

# Sparreholm, between Flen and Hallbosjön.
FIRE_CENTRE = (58.98, 16.68)
FIRE_BBOX = (58.85, 59.24, 16.4, 17.05)  # min_lat, max_lat, min_lon, max_lon
# Map view: the municipality, from Hälleforsnäs in the north to Hallbosjön just south of it.
VIEW_BBOX = (58.85, 59.24, 16.4, 17.05)
# The offline map, the DEM and the satellite images (west, south, east, north): the municipality
# (16.42-17.04 E, 58.87-59.24 N in OpenStreetMap) with Hebylund Kvarnsjön and Floda A in the west
# and Hallbosjön in the south.
MAP_BBOX = (16.3, 58.8, 17.1, 59.28)
PERIOD_START = date(2024, 1, 29)
PERIOD_END = date(2024, 3, 12)
PLAYBACK_START = datetime(2024, 2, 1, 0, 0, tzinfo=timezone.utc)
PLAYBACK_END = datetime(2024, 3, 11, 0, 0, tzinfo=timezone.utc)
# Sentinel-1A passes at 05:15 UTC on 22 February, after Sibro 2 passed its record (15.2 m³/s,
# 2018) at 21 UTC on 18 February.
CHECK_START_UTC = "2024-02-22T05:00:00Z"
# The demo check: just after that pass the level sensor that follows Sibro 2 alarms; Hallbosjön
# stays below its record (51.5 m³/s, 2001), so the others do not, and the assessment reaches
# "Possible flood". Its SATCOM outage starts in the evening before the next radar acquisition at
# 05:07 UTC on 29 February.
CHECK_PEAK_UTC = "2024-02-22T05:30:00Z"
CHECK_SENSORS = "1/8"
CHECK_OUTCOME = "Possible flood"
CHECK_SATCOM_UTC = "2024-02-28T21:00:00Z"

DATABASE = "flenkommun2024"
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
# 2026-10-21) and the ISS, by NORAD number. In 2024 only Sentinel-1A was in orbit.
TLE_SATELLITES = {
    "39634": "Sentinel-1A", "40697": "Sentinel-2A", "42063": "Sentinel-2B",
    "39084": "Landsat 8", "49260": "Landsat 9", "25544": "ISS",
    "38552": "Meteosat-10",
}
TLE_START, TLE_END = "2024-01-26", "2024-03-14"
SATELLITE_ROLES = {
    "39634": {"firms": None, "instrument": "SAR", "role": "Radar, ser genom moln", "half_swath_km": None},
    "40697": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "42063": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "39084": {"firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "49260": {"firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "25544": {"firms": None, "instrument": None, "role": "Rymdstationen", "half_swath_km": None},
    # Meteosat-10 (MSG-3) at 0 degrees, whose cloud mask the demo shows (meteosat_clm.py).
    "38552": {"firms": None, "instrument": "SEVIRI", "role": "Geostationär, ser området hela tiden", "half_swath_km": None, "geostationary": True},
}
SATELLITE_LABEL = "Position 2024, beräknad ur banelement (SGP4) – inte en observation"

# Landsat 8 on 8 March, the day Hallbosjön peaked (catalogue cloud 0 %, checked 2026-10-21). The
# scene covers 74 % of the focus area (row 18 covers 35 %, and 17 March is 45 % cloud over it);
# Sentinel-2 the same day covers it all.
LANDSAT_SCENES = {"after": "LC08_L2SP_194019_20240308_02_T1"}
LANDSAT_ROLES = {"before": "Före de höga flödena", "during": "Under de höga flödena", "after": "Vid Hallbosjöns topp"}
LANDSAT_FOCUS_AREA = (16.45, 58.88, 16.95, 59.12)  # Flen, Sparreholm, Båven and Yngaren
# About 30 m over MAP_BBOX: 0.8 degrees of longitude and 0.48 of latitude at 59.0 N.
LANDSAT_SIZE = (1530, 1780)
# Sentinel-1A acquisitions that cover the focus area whole (Planetary Computer catalogue,
# sentinel-1-grd, checked 2026-10-21; the start of the pass's product): before, as the flows
# rose and at their peak.
SENTINEL1_ACQUISITIONS = [
    {"time_utc": "2024-01-29T05:15:51Z", "satellite": "Sentinel-1A", "norad": "39634"},
    {"time_utc": "2024-02-05T05:07:39Z", "satellite": "Sentinel-1A", "norad": "39634"},
    {"time_utc": "2024-02-22T05:15:50Z", "satellite": "Sentinel-1A", "norad": "39634"},
    {"time_utc": "2024-02-29T05:07:39Z", "satellite": "Sentinel-1A", "norad": "39634"},
    {"time_utc": "2024-03-05T05:15:51Z", "satellite": "Sentinel-1A", "norad": "39634"},
]
# Sentinel-2 (tools/fetch_sentinel2_scene.py): the clearest datatakes before, during and after, by
# product name up to the relative orbit (catalogue tile cloud 0-40 %; the tool measures the focus
# area's own). In winter the sun is low and snow can lie on the fields.
SENTINEL2_SCENES = {
    "before": "S2B_MSIL2A_20240205T102129_R065",
    "during": "S2A_MSIL2A_20240217T101101_R022",
    "after": "S2A_MSIL2A_20240308T100841_R022",
}
# The natural colour of the snow-free February scenes stretched over 0-0.12 rather than 0-0.25, as the
# low sun leaves the forest nearly black; the ice on the lakes is then white throughout. The snowy and
# the March scenes keep 0-0.25 (checked on the images 2026-10-21).
SENTINEL2_NATURAL_REFLECTANCE = {"S2B_MSIL2A_20240205T102129_R065": (0.0, 0.12), "S2A_MSIL2A_20240217T101101_R022": (0.0, 0.12)}
# About 20 m over MAP_BBOX.
SENTINEL2_SIZE = (2295, 2670)

# What the municipality and local media reported, each read 2026-10-21. The publication times stand
# for the events, which have no times of their own, and are marked approximate; the Åpromenaden's
# place is the stretch of Flensån between Kyrkvägen and Frändestavägen in OSM. The railway has no
# reported damage and no place, so it shows in the log only.
ROUTE_REPORT = "Flens kommun (driftstörningar) och Södermanlands Nyheter"
ROUTE_IMPACT_LABEL = "Rapporterat högt vatten"
ROUTE_SOURCE_LABEL = "kommunen och lokala medier"
ROUTE_ATTRIBUTION = "Flens kommun, Södermanlands Nyheter (SN)"
ROUTE_IMPACTS = [
    {"time_utc": "2024-02-07T09:00:00Z", "kind": "road", "approximate_time": True, "site": "Åpromenaden, Flen",
     "latitude": 59.0545, "longitude": 16.5975, "source_label": "Flens kommun",
     "text": "Belysningen längs Åpromenaden vid Flensån släcks kvällstid på grund av högt vattenstånd"},
    {"time_utc": "2024-02-27T05:43:00Z", "kind": "alert", "approximate_time": True, "source_label": "SN",
     "text": "Nyköpingsån svämmar över igen vid Hallbosjön, som har orange varning"},
    {"time_utc": "2024-02-27T16:43:00Z", "kind": "rail", "approximate_time": True, "source_label": "SN",
     "text": "Godståg kan påverkas av översvämningen vid Hallbosjön"},
]
# No ROUTE_EXPOSURE_FILE: over the playback's 39 days nearly every road gathers 50 mm of radar rain,
# which says nothing of this flood (as for Skåne 2024).

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
# Nyköpingsån (tools/derive_level_sensor_points.py), each following the nearer of Sibro 2 and
# Hallbosjön; Hebylund lies on no mapped stretch.
LEVEL_SENSOR_FILE = DATA / "sensors" / "level-points.geojson"
LEVEL_SENSOR_RIVERS = {"Nyköpingsån": ["2587:2", "1273:2"]}
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
    "sentinel": "Innehåller bearbetade Copernicus Sentinel-data 2024",
    "era5_land": "Innehåller bearbetad information från Copernicus Climate Change Service (ERA5-Land), CC BY 4.0",
    "mcf": "Översvämningskartering © MCF (tidigare MSB)",
    "copernicus_dem": (
        "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 "
        "provided under COPERNICUS by the European Union and ESA; all rights reserved"
    ),
}
