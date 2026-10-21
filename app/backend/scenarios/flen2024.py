"""High water in Flen's town in winter 2024.

Chosen 2026-10-21 from the feasibility study reports/2026-10-21-forstudie-flen-claude-opus-5-5.md,
with flenkommun2024 for the whole municipality and flen2019 for the town's flood of December 2019.
A thaw in late January and rain on snow in mid-February raised Flen's small watercourses: SMHI's
Hebylund Kvarnsjön, 15 km west of the town and the only flow station near it, went from 0.31 m³/s
on 20 January to 1.83 on 1 February and 1.93 on 17 February (daily means). On 7 February the
municipality switched off the lights along the Åpromenaden by Flensån in the evenings for the high
water (flen.se). Nothing else in the town is documented for the winter, so the synthetic level
sensors also stand where the town flooded in December 2019 (Kommunen varnar för höga vattenflöden,
Katrineholms-Kuriren 18 December 2019). Like Skåne 2024 this is a replayed event with real data,
not a scenario.

Its data live in the unversioned data/flen2024/.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.backend.scenarios import REPO_ROOT

DATA = REPO_ROOT / "data" / "flen2024"

INCIDENT = "flood"
INCIDENT_PLACE = "Flen"
INCIDENT_AREA = "Flens tätort"

TITLE = "Högt vatten i Flen 2024"
DATA_LABEL = "Historiska data vintern 2024 – uppspelning, inte live"
CONTROL_LABEL = "Scenario: FLOOD – Flens tätort vintern 2024, historiska data"
# The summary the main screen shows, and the satellite monitor reads aloud, when the scenario
# comes to its start (satlog.js summaryState): what the demo shows and what is real.
SUMMARY = [
    "Högt vatten i Flen vintern 2024. Det återges med verkliga data, inte i realtid.",
    "Töväder i slutet av januari och regn på snö i mitten av februari höjde flödena i Flens små vattendrag.",
    "Den 7 februari släckte kommunen belysningen längs Åpromenaden vid Flensån på grund av högt vattenstånd.",
    "SMHI:s vattenföring vid Hebylund, nederbörd och väderradar, och bilder från Sentinel-1 och Sentinel-2.",
    "Nivågivarna är simulerade. De står där tätorten svämmade över i december 2019 och följer SMHI:s station vid Hebylund.",
]

FIRMS_FILES: list = []
TERRAIN_FILE = DATA / "osm" / "terrain-flen.geojson"
TARGETS_FILE = DATA / "osm" / "targets-flen.geojson"
WEATHER_DIR = DATA / "smhi"
# SMHI's measured flows (tools/fetch_smhi_hydro.py).
HYDRO_DIR = DATA / "hydro"
WIND_FILE = DATA / "era5-land" / "era5-land-flen-2024.csv"
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

# The Åpromenaden by Flensån, in the town's centre.
FIRE_CENTRE = (59.0545, 16.5975)
FIRE_BBOX = (59.02, 59.10, 16.52, 16.68)  # min_lat, max_lat, min_lon, max_lon
# Map view: the town, from Orrhammar and Orrestaö in the north to Bjuren and Igelsjön in the south.
VIEW_BBOX = (59.02, 59.10, 16.52, 16.68)
# The offline map, the DEM and the satellite images (west, south, east, north): the town with
# Hebylund Kvarnsjön, Floda A, Sköldinge and Granhed D to the west and north-west.
MAP_BBOX = (16.35, 58.95, 16.75, 59.13)
PERIOD_START = date(2024, 1, 18)
PERIOD_END = date(2024, 2, 23)
PLAYBACK_START = datetime(2024, 1, 20, 0, 0, tzinfo=timezone.utc)
PLAYBACK_END = datetime(2024, 2, 23, 0, 0, tzinfo=timezone.utc)
# Sentinel-1A passes at 05:15 UTC on 29 January, after the thaw had more than tripled Hebylund's flow.
CHECK_START_UTC = "2024-01-29T05:00:00Z"
# The demo check: just after that pass all three level sensors alarm and the assessment reaches
# "Possible flood". Its SATCOM outage starts in the evening before the radar acquisition at 05:07 UTC
# on 5 February.
CHECK_PEAK_UTC = "2024-01-29T05:30:00Z"
CHECK_SENSORS = "3/3"
CHECK_OUTCOME = "Possible flood"
CHECK_SATCOM_UTC = "2024-02-04T21:00:00Z"

DATABASE = "flen2024"
TILES_FILE = "flen.mbtiles"

CAMERA_ROUTE = [
    {"lon": 12, "lat": 52, "height": 16_000_000, "pitch": -90, "seconds": 1.8},  # Earth over Europe
    {"lon": 15, "lat": 59, "height": 3_000_000, "pitch": -90, "seconds": 2.0},   # Southern Scandinavia
    {"lon": 16.6, "lat": 59.05, "height": 400_000, "pitch": -80, "seconds": 2.0},  # Södermanland
    {"lon": 16.6, "lat": 58.99, "height": 25_000, "pitch": -60, "seconds": 2.2},  # Flen
]

# The flood's words for the land the radar's water is counted on and for the gauges.
FOCUS_LAND = "marken runt Flen"
RAIN_GAUGES = "SMHI:s mätare"
# SMHI's hourly rain (parameter 7) in the area, checked 2026-10-21: only Floda A, 11 km west of Flen.
RAIN_STATIONS = {"96040": "Floda A"}
# SMHI's stations that report the rain by the day (parameter 5, 06-06 UTC) in the map area,
# checked 2026-10-21 (tools/fetch_smhi_daily.py, daily_rain.py).
DAILY_RAIN_STATIONS = {"96060": "Granhed D", "96050": "Sköldinge"}
DAILY_RAIN_DIR = DATA / "smhi-daily"
# SMHI's hydrological stations with the flow every 15 minutes (parameter 2) near the town, checked
# 2026-10-21: only Hebylund Kvarnsjön (58 km², Nyköpingsån's catchment); Varbro by the town measured
# 1979-1995 only.
HYDRO_STATIONS = {"2614:2": "Hebylund Kvarnsjön"}

# The satellites that imaged the area in the period (Planetary Computer catalogue, checked
# 2026-10-21) and the ISS, by NORAD number. In 2024 only Sentinel-1A was in orbit.
TLE_SATELLITES = {
    "39634": "Sentinel-1A", "40697": "Sentinel-2A", "42063": "Sentinel-2B",
    "39084": "Landsat 8", "49260": "Landsat 9", "25544": "ISS",
    "38552": "Meteosat-10",
}
TLE_START, TLE_END = "2024-01-15", "2024-02-26"
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

# Landsat 8 on 5 February, two days before the lights were switched off (catalogue cloud 34 %,
# checked 2026-10-21; the tool measures the focus area's own).
LANDSAT_SCENES = {"during": "LC08_L2SP_194019_20240205_02_T1"}
LANDSAT_ROLES = {"before": "Före det höga vattnet", "during": "Under det höga vattnet", "after": "Efter det höga vattnet"}
LANDSAT_FOCUS_AREA = (16.55, 59.03, 16.67, 59.09)  # Flen's town
# About 30 m over MAP_BBOX: 0.4 degrees of longitude and 0.18 of latitude at 59.04 N.
LANDSAT_SIZE = (765, 666)
# Sentinel-1A acquisitions that cover the town whole (Planetary Computer catalogue, sentinel-1-grd,
# checked 2026-10-21; the start of the pass's product), from the thaw to after the February peak.
# The passes of relative orbit 168 (22 January, 3 and 15 February) have data over only a quarter of
# the town and are left out.
SENTINEL1_ACQUISITIONS = [
    {"time_utc": "2024-01-24T05:07:39Z", "satellite": "Sentinel-1A", "norad": "39634"},
    {"time_utc": "2024-01-29T05:15:51Z", "satellite": "Sentinel-1A", "norad": "39634"},
    {"time_utc": "2024-02-05T05:07:39Z", "satellite": "Sentinel-1A", "norad": "39634"},
    {"time_utc": "2024-02-22T05:15:50Z", "satellite": "Sentinel-1A", "norad": "39634"},
]
# Sentinel-2 (tools/fetch_sentinel2_scene.py): the clearest datatakes before, during and after, by
# product name up to the relative orbit (catalogue tile cloud 0-9 %; the tool measures the focus
# area's own). In winter the sun is low and snow can lie on the fields.
SENTINEL2_SCENES = {
    "before": "S2A_MSIL2A_20240118T101331_R022",
    "during": "S2B_MSIL2A_20240205T102129_R065",
    "after": "S2A_MSIL2A_20240217T101101_R022",
}
# The natural colour of the snow-free February scenes stretched over 0-0.12 rather than 0-0.25, as the
# low sun leaves the forest nearly black; the ice on the lakes is then white throughout. The snowy and
# the March scenes keep 0-0.25 (checked on the images 2026-10-21).
SENTINEL2_NATURAL_REFLECTANCE = {"S2B_MSIL2A_20240205T102129_R065": (0.0, 0.12), "S2A_MSIL2A_20240217T101101_R022": (0.0, 0.12)}
# About 20 m over MAP_BBOX.
SENTINEL2_SIZE = (1148, 1000)

# What the municipality reported, read 2026-10-21. The notice has no time of its own, so the time is
# approximate; the place is the stretch of Flensån between Kyrkvägen and Frändestavägen in OSM.
ROUTE_REPORT = "Flens kommun (driftstörningar)"
ROUTE_IMPACT_LABEL = "Rapporterat högt vatten"
ROUTE_SOURCE_LABEL = "kommunen"
ROUTE_ATTRIBUTION = "Flens kommun"
ROUTE_IMPACTS = [
    {"time_utc": "2024-02-07T09:00:00Z", "kind": "road", "approximate_time": True, "site": "Åpromenaden",
     "latitude": 59.0545, "longitude": 16.5975, "source_label": "Flens kommun",
     "text": "Belysningen längs Åpromenaden vid Flensån släcks kvällstid på grund av högt vattenstånd"},
]
# Where the town flooded in December 2019 (Katrineholms-Kuriren 18 December 2019), as further places
# for the synthetic level sensors (tools/derive_impact_sensor_points.py). The points are approximate:
# the road by the bridge towards Orrhammar and the road to Orrestaö in OSM. The path by
# Lasarettssjön is left out, as the lake could not be placed.
LEVEL_SENSOR_SITES = [
    {"site": "Bron mot Orrhammar", "latitude": 59.08386, "longitude": 16.5733},
    {"site": "Vägen till Orrestaö", "latitude": 59.0725, "longitude": 16.5865},
]
# Synthetic level sensors (level_sensors.py), each following Hebylund Kvarnsjön. Its flow stayed below
# its record (2.19 m³/s, May 2021), so they alarm when it has risen LEVEL_ALARM_RISE times above its
# flow at the playback's start (0.32 m³/s): from 12 UTC on 25 January to the end, at most 6.7 times.
LEVEL_SENSOR_FILE = DATA / "sensors" / "level-points.geojson"
LEVEL_ALARM_RISE = 3.0
SENSOR_WORDS = {"sensors": "nivågivare", "the_sensors": "nivågivarna", "alarming": "larmande"}

# MCF has no flood mapping of the town's lakes and watercourses (checked 2026-10-21); only
# Nyköpingsån's (2015) reaches the map area, at its southern edge.
FLOOD_HAZARD_WMS = {
    "url": "https://gis-tjanster.mcf.se/arcgis/services/Oversvamningskarteringar/karteringar/MapServer/WMSServer",
    "layers": {"12": "100-årsflöde, klimatanpassat (slutet av seklet)", "9": "Beräknat högsta flöde"},
    "attribution": "Översvämningskartering © MCF (tidigare MSB)",
    "visible": [],
}
# The same layers for PostGIS (tools/fetch_mcf_flood_maps.py): REST id, title and label.
MCF_LAYERS = {
    "100ar": (3, "100-årsflöde (Klimatanpassat flöde för slutet av seklet)", "MCF, klimatanpassat"),
    "bhf": (5, "Beräknat högsta flöde", "MCF"),
}
FLOOD_AREA_WORD = "det klimatanpassade 100-årsflödet"
FLOOD_MODELS = "MCF:s modell för slutet av seklet"

FORECAST_WEATHER_FILES: list = []
FORECAST_METHOD = ""
FORECAST_REPORT = ""
SPATIAL_SOURCE = "PostGIS (lokal databas): OSM-mål © OpenStreetMap contributors"

ATTRIBUTION = {
    "osm": "© OpenStreetMap contributors (ODbL)",
    "lantmateriet": "© Lantmäteriet",
    "smhi": "SMHI öppna data (CC BY 4.0 SE): nederbörd vid Floda A, väderradar, vattenföring",
    "sentinel": "Innehåller bearbetade Copernicus Sentinel-data 2024",
    "era5_land": "Innehåller bearbetad information från Copernicus Climate Change Service (ERA5-Land), CC BY 4.0",
    "copernicus_dem": (
        "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 "
        "provided under COPERNICUS by the European Union and ESA; all rights reserved"
    ),
}
