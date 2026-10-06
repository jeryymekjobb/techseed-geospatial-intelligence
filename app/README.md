# Fire map: Västmanland 2014

Exhibition prototype in two parts:

- **Backend** (`app/backend/`, Python standard library; paho-mqtt only for the
  IoT nodes): reads the FIRMS archive
  extracts in `satellite_data/firms/`, keeps the detections of the 2014 fire
  (same filters as `tools/firms_extract.py`) and sends them to the GUI as a
  playback stream in compressed time (Server-Sent Events). It also serves the
  terrain layer and proxies Lantmäteriet services, so credentials stay on the
  server.
- **GUI** (`app/frontend/`, Leaflet 1.9.4 vendored): OpenStreetMap base map over
  the fire area with a margin, a terrain layer, FIRMS hotspots coloured by age and
  sized by fire radiative power, a daily timeline, playback controls and a
  weather panel (SMHI station observations) and thin wind arrows with speed
  barbs (ERA5-Land model wind) that follow the playback clock, and a fire-spread
  forecast (model, large uncertainty) for the latest satellite pass.
- **Mission control** (`control.html`): a touch screen for the operator that
  drives the scenario on every screen – events, GOD VIEW and its filter, and a
  simulated SATCOM outage.
- **IoT, assessment and questions**: simulated booth nodes over MQTT, synthetic
  sensors in the fire area, a traceable fire assessment and prepared spatial
  questions answered with PostGIS.

All fire data is **historical (2014) and replayed, not live**; the GUI says so.

To run the demo in the booth, see the operator guide `docs/operatorsguide.md` (Swedish).

The 2D map (`index.html`, `map2d.js`) and the 3D globe (`3d.html`, `map3d.js`,
CesiumJS without Cesium ion) share the panel logic in `panel.js`; each map file is
an adapter with the same interface.

## Run

From the repository root, with the local services and the IoT client:

```bash
docker compose up -d tiles postgis mosquitto
.venv/bin/pip install -r app/requirements-iot.txt   # once
.venv/bin/python -m app.backend.server
.venv/bin/python -m tools.mqtt_node_sim             # in a second terminal: the booth nodes, simulated
```

`python3 -m app.backend.server` also works; without paho-mqtt the IoT nodes are
then shown as unavailable, and without PostGIS the questions say so.

Open <http://127.0.0.1:8765/> (2D), <http://127.0.0.1:8765/3d.html> (3D globe)
and <http://127.0.0.1:8765/control.html> (mission control). Options: `--host`,
`--port`, `--mqtt host:port|off` (default `IOT_MQTT_BROKER` or `127.0.0.1:1883`). In the browser,
`?autoplay=1` starts the playback, `?show=all` shows every detection and
`?at=2014-08-04T12:00:00Z` shows the state at that UTC time (the playback
continues from there).

### Scenarios

Everything that belongs to one demo - area, period, titles, data files, database,
map tiles, camera route, satellites and Landsat scenes - is in a module of its own in
`app/backend/scenarios/`; `app/backend/scenario.py` loads the chosen one:
`vastmanland2014`, the default, and `sundsvall2026`, a flood scenario built on the real
rain of August 2026, whose data the tools fetch but whose screens are not built yet.
Choose with `--scenario` or the environment variable `TECHSEED_SCENARIO`; the tools in
`tools/` read the same variable:

```bash
.venv/bin/python -m app.backend.server --scenario vastmanland2014
TECHSEED_SCENARIO=vastmanland2014 .venv/bin/python -m tools.load_postgis
TILES_FILE=vastmanland.mbtiles docker compose up -d tiles   # the scenario's TILES_FILE
```

The Sundsvall data go to the unversioned `data/sundsvall2026/` (the rain gauges are the
municipality's and SMHI's Brämön A; the last months may not be quality-controlled yet, and
the municipality's gauges list only hours with rain):

```bash
export TECHSEED_SCENARIO=sundsvall2026
.venv/bin/python -m tools.fetch_copernicus_dem && .venv/bin/python -m tools.build_terrain
.venv/bin/python -m tools.build_offline_tiles      # data/tiles/sundsvall.mbtiles
.venv/bin/python -m tools.fetch_tle_history         # Sentinel-1C/1D, Sentinel-2A/2B/2C, Landsat 8/9, ISS
.venv/bin/python -m tools.fetch_smhi_weather 2222813 2222814 2222818 2222811 2222812 2222819 127130 \
  --period latest-months --parameters 7 --start 2026-08-14 --end 2026-08-22 --out data/sundsvall2026/smhi
.venv/bin/python -m tools.fetch_osm_terrain --bbox 62.15,16.9,62.62,17.8 --out data/sundsvall2026/osm/terrain-sundsvall.geojson
.venv/bin/python -m tools.fetch_osm_targets --bbox 62.15,16.9,62.62,17.8 --out data/sundsvall2026/osm/targets-sundsvall.geojson
.venv/bin/python -m tools.fetch_landsat_scene       # Landsat 8 before and after the rain
.venv/bin/python -m tools.fetch_sentinel2_scene     # Sentinel-2 natural colour and NDWI water
```

`?speed=10800` sets the playback speed in simulated seconds per second and
`?horizon=6` the forecast horizon (3, 6, 12 or 24 hours).

### 3D globe

The 3D globe needs CesiumJS and satellite.js, which are not versioned. Fetch them
once (and before an exhibition, so the page works offline):

```bash
python3 -m tools.fetch_web_vendor
```

The script downloads pinned npm packages, checks their SHA-512 and unpacks them
into `app/frontend/vendor/`. Open <http://127.0.0.1:8765/3d.html>; the button
"Flyg till branden" (or `?fly=1`) flies the camera from space to the fire in about
five seconds. The world imagery is Natural Earth II, shipped with Cesium; the fire
area uses the offline map when the `tiles` service runs. The globe draws the same
layers as the 2D map (hotspots, OSM terrain, place and lake names, wind arrows and
the forecast) and has its own layer panel; click an object for its details.

The terrain comes from Copernicus DEM GLO-30 (30 m), built for the map area:

```bash
python3 -m tools.fetch_copernicus_dem   # four 1x1 degree tiles, about 100 MB, into data/dem/
python3 -m tools.build_terrain          # cesium-terrain-builder in Docker -> data/terrain/ (about 12 MB)
```

The backend serves the terrain at `/terrain/` and the globe places the hotspots
and stations on it. Without it the globe is flat. The tiles come from the public
AWS open-data bucket without an account. The GUI shows the attribution required by
the Copernicus DEM licence.

### Shared scenario and several screens

The backend holds one scenario clock (`app/backend/scenario_engine.py`); every
open GUI follows it through `/api/scenario/stream`, and the buttons send
commands to `POST /api/scenario/command` (`play`, `pause`, `reset`, `seek` with
`at`, `speed` with `speed`). A second screen on the network, for example a
mission-control tablet, therefore shows the same moment. When the backend
listens on the network (`--host 0.0.0.0`), set `SCENARIO_CONTROL_TOKEN` and open
the GUI with `?token=<the token>` on screens that may control the scenario;
others can only watch.

### Mission control

`control.html` sends commands to the shared scenario, and every screen follows:

| Button | Command | On the main screens |
|---|---|---|
| PLAY, PAUSE, RESET | `play`, `pause`, `reset` | RESET also clears every event and filter |
| SATELLITE DETECTION | `satellite_detection` | Banner (synthetic event) |
| SENSOR FAILURE | `sensor_failure` with `target` `sensor-17` | The synthetic sensor drops out of the IoT count |
| SATCOM FAILURE (again: restore) | `satcom_failure`, `satcom_restore` | See below |
| ROAD CLOSED, POWER FAILURE | `road_closed`, `power_failure` | Status text only, marked synthetic; no road closure or power-grid data |
| +60 MIN | `plus60` (toggle) | The shortest forecast horizon (3 h; the forecast has no 1 h horizon) |
| GOD VIEW | `god_view` (toggle) | Camera out to Europe and back; the filter list on the map |
| SPACE VIEW (again: RETURN TO INCIDENT) | `space_view` (toggle) | The 3D camera out to the satellites' orbits and back to the fire |
| Filter SPACE, IOT, INFRASTRUCTURE, WEATHER | `filter` with `target` | Hides or shows hotspots, synthetic sensors, the last answer, wind and SMHI stations |

Maritime, aviation and emergency are greyed out and marked as not part of the
demo. Every event is stored with its scenario time; the stream sends each new
one once (`scenario_event`) and the status they add up to in every state.

**SATCOM outage.** While it lasts, detections after its start are held back:
the main screen shows SATELLITE DATA UNAVAILABLE and how many detections are
queued (`satcom_queue`), the assessment uses only earlier satellite data, and IoT
carries on. When the link is back, `satcom_sync` lists the satellite passes
during the outage and how much the front grew, from the 2014 data, and the
queued detections follow on the map.

### Satellites 2014

The 3D globe shows Terra and Aqua (MODIS), Suomi NPP (VIIRS) – the satellites
whose detections are in the FIRMS data – and Landsat 8 and the ISS where they
were at the scenario clock in 2014, with their orbits 50 minutes back and ahead.
The positions are **computed** with SGP4 (satellite.js, `app/frontend/orbits.js`)
from the 2014 element sets, not observed. Sentinel-1A was still in commissioning
in August 2014 and Sentinel-2A was launched in 2015, so neither is shown.

The element sets come from Space-Track (class `gp_history`) and need an account:

```bash
# ~/.spacetrackrc, readable only by you (chmod 600):
#   identity=<the e-mail address you log in with>
#   password=<your password>
python3 -m tools.fetch_tle_history      # one login and one query -> data/tle/
```

The login is never printed or stored. `data/tle/` is not versioned, so the
element sets are not redistributed through the repository; check Space-Track's
terms before showing the positions in public. Without `data/tle/` the globe shows
no satellites. `GET /api/satellites` gives the element sets.

When a detection arrives, the satellite that made it is enlarged with a line
down to the detection ("VIIRS-detektion 11:28 UTC (Suomi NPP)"). The panel lists
each satellite's height, speed and next pass over the fire (the fire inside half
the instrument's swath: MODIS 1165 km, VIIRS 1520 km, Landsat 8 OLI 92.5 km).
SPACE VIEW from mission control zooms out to the orbits; at 1 hour/s the
satellites jump far between ticks, so choose **1 minut/s** there.

`tests/test_satellite_passes.py` checks the chain: every one of the 1,727 FIRMS
detections lies within the swath of the satellite that made it during its
granule (farthest: Terra 947 km, Aqua 1151 km, Suomi NPP 1428 km), the check
fails for a time 45 minutes off, and the next pass found is the one that made the
detections. It needs Node.js, satellite.js and `data/tle/`.

### Landsat 8 images before, during and after the fire

Three Landsat 8 scenes (Collection 2 Level-2 surface reflectance), all clear and
covering the whole fire area:

| Role | Scene | Taken (UTC) |
|---|---|---|
| Before | `LC08_L2SP_193018_20140610_02_T1` | 2014-06-10 10:00 |
| During | `LC08_L2SP_194018_20140804_02_T1` | 2014-08-04 10:06, as the fire spread fastest |
| After | `LC08_L2SP_193018_20140914_02_T1` | 2014-09-14 10:00, the whole burnt area |

Cut the map area out of them once (needs Docker, no account; numpy and Pillow from
the `.venv`):

```bash
.venv/bin/python -m tools.fetch_landsat_scene    # Planetary Computer -> data/landsat/ (nine PNGs, about 105 MB)
```

The tool reads the scenes from Microsoft Planetary Computer's open STAC catalogue
with the anonymous access token its API hands out; GDAL in the
`tumgis/ctb-quantized-mesh` image (as for the terrain) reads only the map area and
warps it to WGS 84. Per scene it writes a **false-colour** image (bands 7-5-4:
burnt area dark, active fire orange), a **natural-colour** image (bands 4-3-2; the
atmospheric correction leaves a greenish tint around smoke) and **NDMI**, the
moisture index (B5 - B6) / (B5 + B6) of the vegetation, brown dry to blue moist,
with clouds, cloud shadows and water from the QA_PIXEL mask left transparent. It
reports the share of the fire area each scene covers and the cloud over it, and
warns below 95 % coverage: scenes from path 195 (for example 26 July and 27 August)
only graze the fire at the scene's edge. TLS is verified with the host's
certificates, and brief catalogue outages are tried again. `data/landsat/SOURCE.json`
records the scenes, bands, stretch, coverage and cloud; `data/` is not versioned.

The panel's "Satellitbild" chooses the date - by default the latest scene taken up
to the scenario clock - and the image: false colour, natural colour, NDMI (with its
colour scale) or none. A chosen scene before or during the fire appears once the
clock has reached it; the scene after the fire is shown whenever it is chosen and
is marked as a comparison taken after the fire, not the state at the scenario
clock. The Space filter hides the images. In 2D the WGS 84 images are stretched to
their bounds (about 1 % distortion over this area). USGS Landsat data are public
domain; the maps cite "Landsat 8-9 OLI/TIRS Collection 2 Level-2 Science Products,
courtesy of the U.S. Geological Survey, doi:10.5066/P9OGBGM6".

### IoT

The four booth nodes (TEMP, WATER, AIR, NTN) publish JSON to
`techseed/<node>/<kind>`, for example `{"value": 24.7, "time_utc": "…"}`, to the
local Mosquitto broker (`docker compose up -d mosquitto`, 127.0.0.1:1883,
anonymous). For the exhibition demo they run **simulated** with
`tools/mqtt_node_sim.py` (`--interval`, `--drop <node>` to try a silent node);
their messages carry `"simulated": true` and the screens show them as
"simulerad", not live. A node silent for 60 s is shown as offline.
`GET /api/sensors` gives the latest readings.

Three **synthetic sensors** in the fire area (`app/backend/sensor_sim.py`,
invented positions) show the ERA5-Land air temperature plus a heat term that
grows towards the front, and smoke near or downwind of it; they are computed from
the scenario, not measured, and always marked synthetic.
`GET /api/sensors/synthetic`.

### Assessment and questions

`app/backend/assessment.py` assesses the fire at the scenario clock with an
evidence list – FIRMS detections in the last 24 h, repeats within 1 km, high
FIRMS confidence, each synthetic sensor, wind and forecast as context, and the
missing camera – each pointing at an object on the map (click a line). The
lines that hold are combined with fixed weights (0.50, 0.30, 0.20, 0.25 per
sensor) as 1 − ∏(1 − weight): a **rule-based score, not a calibrated
probability**. `GET /api/assessment`.

Four prepared questions (`app/backend/spatial.py`, `GET /api/questions`,
`GET /api/ask?q=<id>`): why there is a fire (from the assessment), infrastructure
within 5 km of the front (`ST_DWithin`), places inside the 6 h forecast
(`ST_Intersects`) and the nearest village (`ST_Distance`). Only the scenario
clock goes into the SQL; the answer shows the SQL that ran, its run time and the
sources, and is drawn on the map. They need PostGIS loaded with
`tools/load_postgis.py`; the backend keeps one `psql` open in the `postgis`
service. The power grid is not in the data.

### Offline map and PostGIS

`docker-compose.yml` has two local services (127.0.0.1 only):

```bash
python3 -m tools.build_offline_tiles      # OSM extract -> data/tiles/vastmanland.mbtiles (needs data/osm/sweden-latest.osm.pbf)
docker compose up -d tiles postgis
python3 -m tools.load_postgis             # targets, terrain, detections, fronts and forecasts into PostGIS
```

With the `tiles` service running the GUI uses the offline map
(`/tiles/{z}/{x}/{y}.png` through the backend) and draws place and lake names
itself; without it, it falls back to OpenStreetMap online. The country extract
comes from <https://download.openstreetmap.fr/extracts/europe/sweden-latest.osm.pbf>
(about 930 MB, kept in the unversioned `data/osm/`); `data/tiles/SOURCE.json`
records its SHA-256. PostGIS listens on 127.0.0.1:5433 (database and user
`firemap`, local password `firemap-local` unless `FIREMAP_DB_PASSWORD` is set).

### Check the demo end to end

`tools/check_demo.py` runs the two-minute demo from mission control in Chrome –
the flight, SPACE VIEW, detections with Landsat and IoT, the assessment and
questions, +60 MIN, a SATCOM outage with SYNC, GOD VIEW – and checks that RESET
brings both screens back within 5 s. It writes `report.txt`, `report.json` and a
screenshot per step, and exits with 1 if a step fails. Run it on the exhibition
PC with `--headed` (real graphics card); headless Chrome renders WebGL in
software (about 0.3 frames per second here), so only the steps, not the times,
mean anything there:

```bash
.venv/bin/python -m tools.check_demo --headed --out ~/demo-check                          # starts backend and booth nodes
.venv/bin/python -m tools.check_demo --headed --base-url http://127.0.0.1:8765 --out ~/demo-check   # a backend that runs
```

### Record a video

`tools/record_demo.py` starts the backend itself, plays the GUI in a headless
Google Chrome and saves a video (needs `.venv/bin/pip install -r
tools/requirements-record.txt`):

```bash
.venv/bin/python -m tools.record_demo --start 2014-08-04T06:00:00Z --speed 10800 --horizon 6 --size 1920x1080 --out ~/Videos/brandkarta.webm
```

Without `--duration` it records until the playback ends. The WebM starts with the
few seconds in which the page loads; with ffmpeg installed an MP4 is also written
that starts with the playback.

With the `tiles` service running the recording uses the offline map; without
it the browser loads the OSM base map from `tile.openstreetmap.org`.

## Data and layers

| Layer | Source | Licence / terms | Notes |
|---|---|---|---|
| Hotspots | NASA FIRMS archive, MODIS C6.1 (816007) and VIIRS S-NPP C2 (816008) | NASA open data; acknowledge FIRMS | 1,727 detections, 2014-07-31 – 2014-08-10 UTC, type 0, MODIS confidence ≥ 30, VIIRS `n`/`h` |
| Base map | OpenStreetMap standard tiles | © OpenStreetMap contributors, ODbL; OSM tile usage policy | Place names, lakes, roads |
| Terrain | OSM land use and natural areas via Overpass, `app/layers/terrain-vastmanland.geojson` | ODbL | **Current** OSM state, not 2014; fetched 2026-10-01, simplified about 10 m; regenerate with `tools/fetch_osm_terrain.py` |
| Weather | SMHI Sala A (96560) and Kloten A (95540), hourly, `weather_data/smhi/` | CC BY 4.0 SE; name SMHI | Station measurements 29 and 52 km from the fire, not at the fire |
| Wind arrows | ERA5-Land hourly 10 m wind, 0.1° grid, `weather_data/era5-land/` | CC BY 4.0; "Contains modified Copernicus Climate Change Service information" | Model reanalysis, 40 grid points; arrows point where the wind blows; barbs 2.5/5/25 m/s |
| Forecast (model) | `app/backend/forecast.py`, `tools/fire_spread.py` | – | At each FIRMS pass: estimated front (hull of detections so far), observed spread between passes, FBP C-2 forecast with FWI from SMHI Sala A, weather held from the pass, calibrated against observed spread; band half to double the rate for 3/6/12/24 h; places inside the double-rate area within 24 h with a span, no exact times. Hindcast skill: `reports/2026-10-01-brandspridningsanalys-vastmanland-2014-claude-opus-5-5.md` |
| Synthetic sensors | `app/backend/sensor_sim.py` | – | **Synthetic**: invented positions; values computed from the front and ERA5-Land, not measured |
| Booth IoT nodes | `tools/mqtt_node_sim.py` over MQTT | – | **Simulated** for the demo; real nRF91 nodes are deferred |
| Assessment score | `app/backend/assessment.py` | – | Rule-based score with fixed weights, not a probability |
| Landsat 8 images | USGS Collection 2 Level-2 scenes of 2014-06-10, 2014-08-04 and 2014-09-14 via Planetary Computer, `data/landsat/` (not versioned) | Public domain; cite USGS, doi:10.5066/P9OGBGM6 | Real satellite images, 30 m: false colour, natural colour and NDMI (vegetation moisture); the image after the fire is a comparison |
| Satellite positions | Space-Track `gp_history` element sets, `data/tle/` (not versioned) | Space-Track user agreement | **Computed** with SGP4 for the scenario clock; checked against the FIRMS detection times |
| Infrastructure (questions) | OSM targets in PostGIS | ODbL | Places, major roads, railways, industrial buildings; no power grid |
| Topowebb (optional) | Lantmäteriet Topografisk webbkarta Visning | CC0; access via Geotorget | Off until configured |
| Property boundaries (optional) | Lantmäteriet Fastighetsindelning Visning (WMS) | Open data via Geotorget | Off until configured; choose the layers to show |

Hotspot pixels are about 375 m (VIIRS) and 1 km (MODIS); a detection is a thermal
anomaly, not a mapped fire perimeter. Times are UTC in the data and Swedish time
in the GUI.

## Lantmäteriet (optional)

Set these environment variables before starting the backend; never commit them:

| Variable | Meaning |
|---|---|
| `LM_USERNAME`, `LM_PASSWORD` | Geotorget credentials (HTTP Basic) |
| `LM_TOPOWEBB_URL` | Tile URL template with `{z}`, `{x}`, `{y}` for a Web Mercator (EPSG:3857) tile matrix set |
| `LM_FASTIGHET_WMS_URL` | Base URL of the Fastighetsindelning Visning WMS |
| `LM_FASTIGHET_LAYERS` | Comma-separated WMS layer names, for example boundaries only |

The exact URLs and layer names come with the Geotorget order. The proxy forwards
only WMS `GetMap` requests and never sends the credentials to the browser.

## Tests

```bash
python3 -m pytest -q tests
```
