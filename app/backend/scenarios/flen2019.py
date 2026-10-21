"""The high flows in Flen's town on 18 December 2019.

Chosen 2026-10-21 from the feasibility study reports/2026-10-21-forstudie-flen-claude-opus-5-5.md
as the second event for the town, beside winter 2024 (flen2024). On 18 December 2019 the
municipality warned of high flows (Kommunen varnar för höga vattenflöden, Katrineholms-Kuriren
18 December 2019, 15.00): the Åpromenaden between Kyrkvägen and Frändestavägen was closed to
walkers and cyclists and its lights switched off, the path by Lasarettssjön was partly flooded,
the road before and after the bridge towards Orrhammar was under water and one lane of the road
to Orrestaö was closed. SMHI's Hebylund Kvarnsjön, 15 km west of the town, went from 0.37 m³/s on
3 December to 1.26 on 18 December and 1.36 on 21 December (daily means). Like Skåne 2024 this is a
replayed event with real data, not a scenario.

Its data live in the unversioned data/flen2019/; the offline map, DEM, terrain and OSM layers are
flen2024's (the same area, OSM as fetched in 2026).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.backend.scenarios import REPO_ROOT

DATA = REPO_ROOT / "data" / "flen2019"
# The map area's offline map, DEM, terrain and OSM layers, shared with flen2024.
SHARED = REPO_ROOT / "data" / "flen2024"

INCIDENT = "flood"
INCIDENT_PLACE = "Flen"
INCIDENT_AREA = "Flens tätort"

TITLE = "Höga flöden i Flen 2019"
DATA_LABEL = "Historiska data december 2019 – uppspelning, inte live"
CONTROL_LABEL = "Scenario: FLOOD – Flens tätort december 2019, historiska data"
# The summary the main screen shows, and the satellite monitor reads aloud, when the scenario
# comes to its start (satlog.js summaryState): what the demo shows and what is real.
SUMMARY = [
    "De höga flödena i Flen i december 2019. De återges med verkliga data, inte i realtid.",
    "Den 18 december varnade kommunen för höga flöden. Åpromenaden stängdes och vägen vid bron mot Orrhammar stod under vatten.",
    "SMHI:s vattenföring vid Hebylund, nederbörd och väderradar, och radarbilder från Sentinel-1 före och efter.",
    "Nivågivarna är simulerade. De står där tätorten svämmade över och följer SMHI:s station vid Hebylund.",
]

FIRMS_FILES: list = []
TERRAIN_FILE = SHARED / "osm" / "terrain-flen.geojson"
TARGETS_FILE = SHARED / "osm" / "targets-flen.geojson"
WEATHER_DIR = DATA / "smhi"
# SMHI's measured flows (tools/fetch_smhi_hydro.py).
HYDRO_DIR = DATA / "hydro"
WIND_FILE = DATA / "era5-land" / "era5-land-flen-2019.csv"
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
TLE_FILE_NAME = "tle-2019.json"

# The Åpromenaden by Flensån, in the town's centre.
FIRE_CENTRE = (59.0545, 16.5975)
FIRE_BBOX = (59.02, 59.10, 16.52, 16.68)  # min_lat, max_lat, min_lon, max_lon
# Map view: the town, from Orrhammar and Orrestaö in the north to Bjuren and Igelsjön in the south.
VIEW_BBOX = (59.02, 59.10, 16.52, 16.68)
# The offline map, the DEM and the satellite images (west, south, east, north): the town with
# Hebylund Kvarnsjön, Floda A, Sköldinge and Granhed D to the west and north-west.
MAP_BBOX = (16.35, 58.95, 16.75, 59.13)
PERIOD_START = date(2019, 12, 5)
PERIOD_END = date(2019, 12, 30)
PLAYBACK_START = datetime(2019, 12, 7, 0, 0, tzinfo=timezone.utc)
PLAYBACK_END = datetime(2019, 12, 29, 0, 0, tzinfo=timezone.utc)
# Sentinel-1A passes at 05:15 UTC on 21 December, three days after the warning.
CHECK_START_UTC = "2019-12-21T05:00:00Z"
# The demo check: just after that pass all three level sensors alarm (Hebylund above its record) and
# the assessment reaches "Possible flood". Its SATCOM outage starts in the evening before the radar
# acquisition at 05:07 UTC on 28 December.
CHECK_PEAK_UTC = "2019-12-21T05:30:00Z"
CHECK_SENSORS = "3/3"
CHECK_OUTCOME = "Possible flood"
CHECK_SATCOM_UTC = "2019-12-27T21:00:00Z"

DATABASE = "flen2019"
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
# 2026-10-21) and the ISS, by NORAD number. Landsat has no clear scene in the period.
TLE_SATELLITES = {
    "39634": "Sentinel-1A", "41456": "Sentinel-1B", "40697": "Sentinel-2A", "42063": "Sentinel-2B",
    "39084": "Landsat 8", "25544": "ISS", "40732": "Meteosat-11",
}
TLE_START, TLE_END = "2019-12-02", "2020-01-02"
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
SATELLITE_LABEL = "Position 2019, beräknad ur banelement (SGP4) – inte en observation"

# Landsat has no clear scene over the town in December 2019 (checked 2026-10-21).
LANDSAT_SCENES: dict = {}
LANDSAT_ROLES = {"before": "Före de höga flödena", "during": "Under de höga flödena", "after": "Efter de höga flödena"}
LANDSAT_FOCUS_AREA = (16.55, 59.03, 16.67, 59.09)  # Flen's town
# About 30 m over MAP_BBOX: 0.4 degrees of longitude and 0.18 of latitude at 59.04 N.
LANDSAT_SIZE = (765, 666)
# Sentinel-1 acquisitions on the descending tracks that cover the town whole (Planetary Computer
# catalogue, sentinel-1-grd, checked 2026-10-21; the start of the pass's first product): before the
# flows rose, two days before the warning, three days after it and as the flows fell. Sentinel-1B's
# passes (22 and 27 December) have no VV product in the catalogue.
SENTINEL1_ACQUISITIONS = [
    {"time_utc": "2019-12-09T05:15:31Z", "satellite": "Sentinel-1A", "norad": "39634"},
    {"time_utc": "2019-12-16T05:07:19Z", "satellite": "Sentinel-1A", "norad": "39634"},
    {"time_utc": "2019-12-21T05:15:30Z", "satellite": "Sentinel-1A", "norad": "39634"},
    {"time_utc": "2019-12-28T05:07:18Z", "satellite": "Sentinel-1A", "norad": "39634"},
]
# Sentinel-2 (tools/fetch_sentinel2_scene.py): the only clear datatake, before the flows rose (catalogue
# tile cloud 9 %; the tool measures the focus area's own). The sun is very low in December.
SENTINEL2_SCENES = {"before": "S2A_MSIL2A_20191210T101411_R022"}
# About 20 m over MAP_BBOX.
SENTINEL2_SIZE = (1148, 1000)

# What the municipality told Katrineholms-Kuriren, read 2026-10-21. The article's time (15.00 Swedish
# time) stands for the flooding, which has no time of its own, and is marked approximate. The places
# are approximate: the stretch of Flensån between Kyrkvägen and Frändestavägen, the road by the bridge
# towards Orrhammar and the road to Orrestaö in OSM; the path by Lasarettssjön has no place, as the
# lake could not be placed, and shows in the log only.
ROUTE_REPORT = "Katrineholms-Kuriren 18 december 2019, uppgifter från Flens kommun"
ROUTE_IMPACT_LABEL = "Översvämmat enligt kommunen"
ROUTE_SOURCE_LABEL = "kommunen, via lokala medier"
ROUTE_ATTRIBUTION = "Flens kommun via Katrineholms-Kuriren"
ROUTE_IMPACTS = [
    {"time_utc": "2019-12-18T14:00:00Z", "kind": "alert", "approximate_time": True, "source_label": "Katrineholms-Kuriren",
     "text": "Flens kommun varnar för höga vattenflöden"},
    {"time_utc": "2019-12-18T14:00:00Z", "kind": "road", "approximate_time": True, "site": "Åpromenaden",
     "latitude": 59.0545, "longitude": 16.5975, "source_label": "Katrineholms-Kuriren",
     "text": "Åpromenaden mellan Kyrkvägen och Frändestavägen stängd för gång- och cykeltrafik"},
    {"time_utc": "2019-12-18T14:00:00Z", "kind": "road", "approximate_time": True, "source_label": "Katrineholms-Kuriren",
     "text": "Gångvägen längs Lasarettssjön delvis översvämmad"},
    {"time_utc": "2019-12-18T14:00:00Z", "kind": "road", "approximate_time": True, "site": "Bron mot Orrhammar",
     "latitude": 59.08386, "longitude": 16.5733, "source_label": "Katrineholms-Kuriren",
     "text": "Vägen före och efter bron mot Orrhammar under vatten"},
    {"time_utc": "2019-12-18T14:00:00Z", "kind": "road", "approximate_time": True, "site": "Vägen till Orrestaö",
     "latitude": 59.0725, "longitude": 16.5865, "source_label": "Katrineholms-Kuriren",
     "text": "Ett körfält på vägen till Orrestaö avstängt"},
]
# Synthetic level sensors at the places above (tools/derive_impact_sensor_points.py, level_sensors.py),
# each following Hebylund Kvarnsjön. They alarm when its flow is above its record (1.17 m³/s, March 2019,
# measured since 2018), as it was from 07 UTC on 18 December, the day of the warning (1.57 at most).
LEVEL_SENSOR_FILE = DATA / "sensors" / "level-points.geojson"
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
    "sentinel": "Innehåller bearbetade Copernicus Sentinel-data 2019",
    "era5_land": "Innehåller bearbetad information från Copernicus Climate Change Service (ERA5-Land), CC BY 4.0",
    "copernicus_dem": (
        "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 "
        "provided under COPERNICUS by the European Union and ESA; all rights reserved"
    ),
}
