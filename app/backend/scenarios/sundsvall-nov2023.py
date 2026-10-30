"""Local rain in Sundsvall on 3-4 November 2023.

Decided 2026-10-28 after a meeting the user reported, where people who built embankments then
described one flood from rain in the mountains (ljungan-aug2023) and one from local rain: this is
the local one (reports/2026-10-28-forstudie-sundsvall-2020-2021-claude-opus-5-5.md). In SMHI's data
Sidsjö D had 27.0 mm on 3 November and 50.7 mm on 4 November, the wettest day of 2023, while the
sea stood low at Spikarna. On 4 November the rescue service put out barriers on Östermovägen in
Skönsmon to lead off water running down from Södra berget (ST), and cellars were flooded in
Sundsvall, Timrå and Härnösand (Sveriges Radio P4, SVT). The scenario replays these data; it is
not live.

It shares sundsvall2026's map area, so its offline map, DEM, terrain, OSM layers, municipal
base map and flood areas are those in data/sundsvall2026/; its own data live in the unversioned
data/sundsvall-nov2023/.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.backend.scenarios import REPO_ROOT

DATA = REPO_ROOT / "data" / "sundsvall-nov2023"
# The map, terrain and OSM layers of sundsvall2026, over the same MAP_BBOX.
SHARED = REPO_ROOT / "data" / "sundsvall2026"

INCIDENT = "flood"
INCIDENT_PLACE = "Sundsvall"
INCIDENT_AREA = "Sundsvall"

TITLE = "Regnet i Sundsvall, november 2023"
DATA_LABEL = "Historiska data november 2023 – uppspelning, inte live"
CONTROL_LABEL = "Scenario: FLOOD – Sundsvall november 2023, historiska data"
# The summary the main screen shows, and the satellite monitor reads aloud, when the scenario
# comes to its start (satlog.js summaryState): what the demo shows and what is real.
SUMMARY = [
    "Det kraftiga regnet i Sundsvall den 3 och 4 november 2023. Det här är uppmätta data, inte i realtid.",
    "Vid Sidsjön föll 51 millimeter regn den 4 november, årets regnigaste dygn. Havet stod lågt.",
    "Räddningstjänsten satte ut barriärer på Östermovägen i Skönsmon, och det kom vatten i källare.",
    "Regn och flöden från SMHI, SMHI:s väderradar och havsvattenståndet vid Spikarna. Flödena i Selångersån och Sidsjöbäcken är beräknade i SMHI:s modell, inte uppmätta.",
    "Radarbilder från Sentinel-1, som ser genom moln. Det var för molnigt för bilder i synligt ljus.",
    "Bräddgivarna DV1–DV8 är simulerade och beräknade ur det verkliga regnet. Nivågivaren vid Himlabadet är simulerad och följer Sidsjöbäckens beräknade flöde.",
]

FIRMS_FILES: list = []
TERRAIN_FILE = SHARED / "osm" / "terrain-sundsvall.geojson"
TARGETS_FILE = SHARED / "osm" / "targets-sundsvall.geojson"
WEATHER_DIR = DATA / "smhi"
WIND_FILE = DATA / "era5-land" / "era5-land-sundsvall-nov2023.csv"
# ERA5 over the sea, where ERA5-Land has no values (tools/fetch_era5_sea.py).
WIND_SEA_FILE = DATA / "era5-land" / "era5-sea-sundsvall-nov2023.csv"
# SMHI's measured flows (tools/fetch_smhi_hydro.py).
HYDRO_DIR = DATA / "hydro"
# SMHI's weather radar as rain images (tools/fetch_smhi_radar.py).
RADAR_DIR = DATA / "radar"
DEM_DIR = SHARED / "dem"
TERRAIN_DIR = SHARED / "terrain"
LANDSAT_DIR = DATA / "landsat"
# MET Norway's archived weather forecasts, as issued (tools/fetch_met_forecasts.py, met_forecast.py).
MET_FORECAST_DIR = DATA / "met-forecast"
# SMHI's observed lightning (tools/fetch_smhi_lightning.py).
LIGHTNING_DIR = DATA / "lightning"
SENTINEL2_DIR = DATA / "sentinel2"
# The Sentinel-1 radar images of the acquisitions (tools/fetch_sentinel1_scene.py).
SENTINEL1_DIR = DATA / "sentinel1"
# The municipality's critical stormwater points and flood areas, and MCF's (shared). The synthetic
# overflow sensors DV1-DV8 of sundsvall2026 stand at the same points (flood_sensors.py), filled by 2023's rain.
MUNICIPAL_DIR = SHARED / "municipal"
MCF_DIR = SHARED / "mcf"
# Meteosat's cloud top height every 15 minutes and cloud mask every hour (MSG; MTG's lightning
# and instability start in 2024).
METEOSAT_CTH_FILE = DATA / "meteosat-cth" / "cth.json"
METEOSAT_CLM_FILE = DATA / "meteosat-clm" / "clm.json"
TLE_DIR = DATA / "tle"
TLE_FILE_NAME = "tle-2023.json"

# SMHI's sea level at Spikarna (2061) outside Sundsvall, hourly in RH2000 (tools/fetch_smhi_sea_level.py).
SEA_LEVEL_DIR = DATA / "sea-level"
SEA_LEVEL_STATIONS = {"2061": "Spikarna"}
# The sea stood low (about 20 cm RH2000), so no storm lines.
SEA_LEVEL_STORM_CM = 100.0
# Six days: the sea level by the hour, and, as in ljungan-aug2023, the 72 hours after the clock marked
# as measured afterwards, not a forecast (no forecast as issued in 2023 is archived).
SEA_LEVEL_HOURLY = True
SEA_LEVEL_AHEAD_HOURS = 72

# Sundsvall's centre, between Östermovägen in Skönsmon and Sidsjöbäcken.
FIRE_CENTRE = (62.385, 17.31)
FIRE_BBOX = (62.28, 62.47, 17.0, 17.55)  # min_lat, max_lat, min_lon, max_lon
# Map view: the town, the Selånger valley and lower Ljungan with Skallböle.
VIEW_BBOX = (62.28, 62.47, 16.9, 17.55)
# sundsvall2026's map area (lon/lat, west, south, east, north), which reaches Skallböle in the west.
MAP_BBOX = (16.9, 62.15, 17.8, 62.62)
PERIOD_START = date(2023, 10, 29)
PERIOD_END = date(2023, 11, 9)
# From before the rain to after Sentinel-1's passes on 6 November.
PLAYBACK_START = datetime(2023, 11, 1, 0, 0, tzinfo=timezone.utc)
PLAYBACK_END = datetime(2023, 11, 7, 0, 0, tzinfo=timezone.utc)
# Six days at half an hour a second, slowing at the satellites' passes.
PLAYBACK_SPEED = 1800.0
# The heaviest rain, on 4 November.
CHECK_START_UTC = "2023-11-04T06:00:00Z"
# The demo check: at noon on 4 November 4 of the 9 sensors confirm (DV1, DV2, DV4 and NG1 Himlabadet) and the
# assessment says "Flood probable". Its SATCOM outage starts in the evening before Sentinel-1's pass at 05:14 UTC on 6 November.
CHECK_PEAK_UTC = "2023-11-04T12:00:00Z"
CHECK_SENSORS = "4/9"
CHECK_OUTCOME = "Flood probable"
CHECK_SATCOM_UTC = "2023-11-05T21:00:00Z"
# The detection sequence at noon on 4 November uses Sentinel-1A's pass of 6 November, whose radar shows no new
# water, so fewer than two of its rules hold.
CHECK_DETECTION_OUTCOME = "Okänd"

DATABASE = "sundsvall-nov2023"
TILES_FILE = "sundsvall.mbtiles"

CAMERA_ROUTE = [
    {"lon": 12, "lat": 52, "height": 16_000_000, "pitch": -90, "seconds": 1.8},  # Earth over Europe
    {"lon": 15, "lat": 60, "height": 3_500_000, "pitch": -90, "seconds": 2.0},   # Europe
    {"lon": 16.5, "lat": 62.5, "height": 900_000, "pitch": -75, "seconds": 2.0},  # Norrland's coast
    {"lon": 17.2, "lat": 62.2, "height": 160_000, "pitch": -60, "seconds": 2.2},  # Medelpad
]

FOCUS_LAND = "stans land"
RAIN_GAUGES = "kommunens mätare"
# The rain gauges (SMHI parameter 7, hourly precipitation): the municipality's own, as in ljungan-aug2023,
# and SMHI's Brämön A. Söråker (22228110) gives implausible values; Heffners has no value from 29 October
# to 9 November 2023 (checked 2026-10-28). The municipality's gauges list only the hours with rain.
RAIN_STATIONS = {
    "2222813": "Fillan", "2222818": "Bredsand", "2222811": "Essvik",
    "2222812": "Bällsta", "2222819": "Stångom", "127130": "Brämön A",
}
# SMHI's stations that report the rain by the day (parameter 5, 06-06 UTC) by the town; the flood's
# assessment counts them, so the mountains' stations are not among them. Sidsjö D lies by the dam.
DAILY_RAIN_STATIONS = {"127220": "Sidsjö D", "127320": "Stordalen-Midlanda D"}
DAILY_RAIN_DIR = DATA / "smhi-daily"
# SMHI's flow station on Ljungan by Sundsvall ("station:parameter", every 15 minutes); the rain was
# local, so the mountains' stations are left out.
HYDRO_STATIONS = {"1650:2": "Skallböle"}

# SMHI's modelled daily flows (S-HYPE) by SUBID, from Vattenwebb's files downloaded by hand into
# MODEL_FLOW_DIR/raw/ (tools/read_vattenwebb.py; the files of ljungan-aug2023 cover 1991-2024): the
# Selånger river at its outlet in the sea (449 km²) and Sidsjöbäcken (27 km²), which have no SMHI station.
MODEL_FLOW_DIR = DATA / "s-hype"
MODEL_FLOW_STATIONS = {"12849": "Selångersån", "12794": "Sidsjöbäcken"}

# What the media reported on 4-5 November 2023, with approximate times; the barriers on Östermovägen
# have OSM's road as their place and no level sensor, as the water ran off Södra berget, not out of a stream.
ROUTE_REPORT = "ST 4 november, Sveriges Radio P4 4 november och SVT 5 november 2023"
ROUTE_IMPACT_LABEL = "Översvämmat enligt medierna"
ROUTE_SOURCE_LABEL = "lokala medier"
ROUTE_ATTRIBUTION = "Sundsvalls Tidning, Sveriges Radio och SVT"
ROUTE_IMPACTS = [
    {"time_utc": "2023-11-04T11:00:00Z", "kind": "road", "approximate_time": True,
     "latitude": 62.3737, "longitude": 17.3450, "source_label": "Sundsvalls Tidning",
     "text": "Räddningstjänsten sätter ut barriärer på Östermovägen i Skönsmon mot vatten från Södra berget"},
    {"time_utc": "2023-11-04T14:00:00Z", "kind": "alert", "approximate_time": True, "source_label": "Sveriges Radio P4",
     "text": "Vatten i källare i Sundsvall, Timrå och Härnösand"},
]
# One synthetic level sensor at Himlabadet by Sidsjöbäcken (OSM's building; tools/derive_impact_sensor_points.py),
# following Sidsjöbäcken's computed flow; it alarms when that flow is twice its flow at the playback's start,
# as in ljungan-aug2023.
LEVEL_SENSOR_SITES = [
    {"site": "Himlabadet, Sidsjöbäcken", "latitude": 62.39404, "longitude": 17.28916, "source_label": "Syntetisk plats vid Sidsjöbäcken"},
]
LEVEL_SENSOR_FILE = DATA / "sensors" / "level-points.geojson"
LEVEL_ALARM_RISE = 2.0
# The overflow sensors DV1-DV8 stay beside the level sensor (level_sensors.BothSensors).
OVERFLOW_WITH_LEVEL_SENSORS = True
SENSOR_WORDS = {"sensors": "givare", "the_sensors": "givarna", "alarming": "larmande"}

# Sidsjödammen as a marked "if", as the user chose on 2026-10-28: no open dam-break mapping exists and
# one may be classified. When NG1 Himlabadet alarms (Sidsjöbäcken's flow doubled), the log
# says how many buildings lie within 100 m of Sidsjöbäcken below the dam (OSM's dam line, waterway=dam)
# and marks the dam and Himlabadet, where the user's meeting reported water, about 360 m from the
# stream (tools/derive_dam_exposure.py). The municipality's cloudburst plan (2018) names a dam failure
# there "katastrofala konsekvenser för nedströms bebyggelse".
DAM = {
    "name": "Sidsjödammen", "latitude": 62.3796, "longitude": 17.2823, "stream": "Sidsjöbäcken", "distance_m": 100,
    "places": [{"name": "Himlabadet", "latitude": 62.39404, "longitude": 17.28916}],
    "trigger_sensor": "ng-01", "osm_extract": REPO_ROOT / "data" / "osm" / "sundsvall2026-area.osm.pbf",
}
DAM_FILE = DATA / "dam" / "dam.json"

# The satellites that imaged Sundsvall in the period (Planetary Computer catalogue, checked
# 2026-10-28; Sentinel-1B ended in December 2021) and the ISS, by NORAD number; element sets
# a few days around the playback.
TLE_SATELLITES = {
    "39634": "Sentinel-1A", "40697": "Sentinel-2A", "42063": "Sentinel-2B",
    "39084": "Landsat 8", "49260": "Landsat 9", "25544": "ISS", "38552": "Meteosat-10", "40732": "Meteosat-11",
}
TLE_START, TLE_END = "2023-10-29", "2023-11-09"
SATELLITE_ROLES = {
    "39634": {"firms": None, "instrument": "SAR", "role": "Radar, ser genom moln", "half_swath_km": None},
    "40697": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "42063": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "39084": {"firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "49260": {"firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "25544": {"firms": None, "instrument": None, "role": "Rymdstationen", "half_swath_km": None},
    # The MSG satellite at 0 degrees whose cloud mask and cloud tops the demo shows (meteosat_clm.py, meteosat_cth.py).
    "38552": {"firms": None, "instrument": "SEVIRI", "role": "Geostationär, ser området hela tiden", "half_swath_km": None, "geostationary": True},
    "40732": {"firms": None, "instrument": "SEVIRI", "role": "Geostationär, ser området hela tiden", "half_swath_km": None, "geostationary": True},
}
SATELLITE_LABEL = "Position 2023, beräknad ur banelement (SGP4) – inte en observation"

# No clear optical image in the period (checked 2026-10-28 in the Planetary Computer catalogue): Sentinel-2
# has 85-95 % cloud on 31 October and 2, 5 and 7 November, and Landsat has no scene.
LANDSAT_SCENES: dict = {}
LANDSAT_ROLES = {"before": "Före regnet", "during": "Under regnet", "after": "Efter regnet"}
# The town and the lower Selånger valley, for the coverage and cloud of each scene.
LANDSAT_FOCUS_AREA = (17.15, 62.33, 17.45, 62.45)
# About 30 m over MAP_BBOX: 0.9 degrees of longitude and 0.47 of latitude at 62.4 N.
LANDSAT_SIZE = (1546, 1742)
# Sentinel-1A's passes in the playback (Planetary Computer catalogue, sentinel-1-grd, checked 2026-10-28;
# the start of each pass's product), after the rain. The image of 1 November 05:06 covers only 58 % of
# the town, with land and water poorly separated, and is left out, as in ljungan-aug2023.
SENTINEL1_ACQUISITIONS = [
    {"time_utc": "2023-11-06T05:14:52Z", "satellite": "Sentinel-1A", "norad": "39634"},
    {"time_utc": "2023-11-06T16:30:52Z", "satellite": "Sentinel-1A", "norad": "39634"},
]
SENTINEL2_SCENES: dict = {}
# About 20 m over MAP_BBOX.
SENTINEL2_SIZE = (2320, 2613)

# MCF's overview flood maps: the 100-year and the highest calculated flow for Ljungan and
# Indalsälven, as in sundsvall2026; name MCF as the source.
FLOOD_HAZARD_WMS = {
    "url": "https://gis-tjanster.mcf.se/arcgis/services/Oversvamningskarteringar/karteringar/MapServer/WMSServer",
    "layers": {"13": "100-årsflöde", "9": "Beräknat högsta flöde"},
    "attribution": "Översvämningskartering © MCF (tidigare MSB)",
}

# Sundsvall municipality's geoserver, which the user confirmed on 2026-10-06 the demo may use.
MUNICIPAL_WMS = {
    "url": "https://karta.sundsvall.se/geoserver/wms",
    "layers": {
        "SundsvallsKommun:Skyfallsmodell100_tiff": "Skyfallsmodell, 100-årsregn",
        "SundsvallsKommun:100-ar_maxvattendjup": "Största vattendjup, 100-årsregn",
        "SundsvallsKommun:Selangersan100ArsFlode2009_yta": "Selångersån, 100-årsflöde (2009)",
        "SundsvallsKommun:GATA_KritiskDagvatten_punkt": "Kritiska punkter för dagvatten",
    },
    "attribution": "© Sundsvalls kommun",
    "visible": [],
}

# The municipality's own map, kept locally for sundsvall2026 (the user confirmed on 2026-10-14).
MUNICIPAL_BASEMAP = {
    "url": "https://karta.sundsvall.se/geoserver/wms",
    "layer": "Kartan",
    "label": "Sundsvalls kommun (Kartan)",
    "attribution": "Karta © Sundsvalls kommun, Lantmäteriet, Trafikverket",
}
MUNICIPAL_BASEMAP_DIR = SHARED / "municipal-basemap"

FORECAST_WEATHER_FILES: list = []
FORECAST_METHOD = ""
FORECAST_REPORT = ""
SPATIAL_SOURCE = ("PostGIS (lokal databas): OSM-mål © OpenStreetMap contributors, 100-årsflöden © Sundsvalls kommun "
                  "och MCF (tidigare MSB)")

ATTRIBUTION = {
    "osm": "© OpenStreetMap contributors (ODbL)",
    "lantmateriet": "© Lantmäteriet",
    "smhi": ("SMHI öppna data (CC BY 4.0 SE): nederbörd vid kommunens mätare, Brämön A, Sidsjö D och Stordalen-Midlanda D, "
             "väderradar, vattenföring vid Skallböle och havsvattenstånd vid Spikarna; modellerad vattenföring (S-HYPE) i Vattenwebb"),
    "sentinel": "Innehåller bearbetade Copernicus Sentinel-data 2023",
    "era5_land": "Innehåller bearbetad information från Copernicus Climate Change Service (ERA5-Land och ERA5 över havet), CC BY 4.0",
    "mcf": "Översvämningskartering © MCF (tidigare MSB)",
    "sundsvall": "Skyfallsmodeller och kartlager © Sundsvalls kommun",
    "copernicus_dem": (
        "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 "
        "provided under COPERNICUS by the European Union and ESA; all rights reserved"
    ),
}
