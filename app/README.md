# Fire map: Västmanland 2014

Exhibition prototype in two parts:

- **Backend** (`app/backend/`, Python standard library): reads the FIRMS archive
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

All fire data is **historical (2014) and replayed, not live**; the GUI says so.

The 2D map (`index.html`, `map2d.js`) and the 3D globe (`3d.html`, `map3d.js`,
CesiumJS without Cesium ion) share the panel logic in `panel.js`; each map file is
an adapter with the same interface.

## Run

From the repository root:

```bash
python3 -m app.backend.server
```

Open <http://127.0.0.1:8765/>. Options: `--host`, `--port`. In the browser,
`?autoplay=1` starts the playback, `?show=all` shows every detection and
`?at=2014-08-04T12:00:00Z` shows the state at that UTC time (the playback
continues from there).

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
area uses the offline map when the `tiles` service runs. Forecast, wind arrows and
place names are not yet drawn in 3D.

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

The OSM base map is loaded by the browser from `tile.openstreetmap.org`, so it
needs internet access; offline tiles for the exhibition are not part of this
version.

## Data and layers

| Layer | Source | Licence / terms | Notes |
|---|---|---|---|
| Hotspots | NASA FIRMS archive, MODIS C6.1 (816007) and VIIRS S-NPP C2 (816008) | NASA open data; acknowledge FIRMS | 1,727 detections, 2014-07-31 – 2014-08-10 UTC, type 0, MODIS confidence ≥ 30, VIIRS `n`/`h` |
| Base map | OpenStreetMap standard tiles | © OpenStreetMap contributors, ODbL; OSM tile usage policy | Place names, lakes, roads |
| Terrain | OSM land use and natural areas via Overpass, `app/layers/terrain-vastmanland.geojson` | ODbL | **Current** OSM state, not 2014; fetched 2026-10-01, simplified about 10 m; regenerate with `tools/fetch_osm_terrain.py` |
| Weather | SMHI Sala A (96560) and Kloten A (95540), hourly, `weather_data/smhi/` | CC BY 4.0 SE; name SMHI | Station measurements 29 and 52 km from the fire, not at the fire |
| Wind arrows | ERA5-Land hourly 10 m wind, 0.1° grid, `weather_data/era5-land/` | CC BY 4.0; "Contains modified Copernicus Climate Change Service information" | Model reanalysis, 40 grid points; arrows point where the wind blows; barbs 2.5/5/25 m/s |
| Forecast (model) | `app/backend/forecast.py`, `tools/fire_spread.py` | – | At each FIRMS pass: estimated front (hull of detections so far), observed spread between passes, FBP C-2 forecast with FWI from SMHI Sala A, weather held from the pass, calibrated against observed spread; band half to double the rate for 3/6/12/24 h; places inside the double-rate area within 24 h with a span, no exact times. Hindcast skill: `reports/2026-10-01-brandspridningsanalys-vastmanland-2014-claude-opus-5-5.md` |
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
