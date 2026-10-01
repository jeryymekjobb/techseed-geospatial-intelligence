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
  weather panel (SMHI station observations) that follows the playback clock.

All fire data is **historical (2014) and replayed, not live**; the GUI says so.

## Run

From the repository root:

```bash
python3 -m app.backend.server
```

Open <http://127.0.0.1:8765/>. Options: `--host`, `--port`. In the browser,
`?autoplay=1` starts the playback, `?show=all` shows every detection and
`?at=2014-08-04T12:00:00Z` shows the state at that UTC time (the playback
continues from there).

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
