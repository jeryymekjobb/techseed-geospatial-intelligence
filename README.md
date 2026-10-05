# TechSeed Geospatial Intelligence

Concept work for a repeatable geospatial-intelligence demonstrator for IoTDagen. The initial concept combines space-derived observations, GIS, weather, IoT and infrastructure data into an operational common picture.

## Contents

- `onepager.md` — user-provided concept for the exhibition demonstrator.
- `CONTEXT.md` — project purpose, boundaries and current direction.
- `AGENTS.md` — repository working and review rules.
- `docs/operatorsguide.md` — operator guide (Swedish) for running the demo in the booth: preparation, start, the two-minute script, what is real or simulated, troubleshooting.
- `app/` — fire-map prototype for the Västmanland 2014 scenario: backend, 2D map and 3D globe, mission control, IoT, assessment and spatial questions; see `app/README.md`.
- `satellite_data/firms/` — NASA FIRMS archive extracts for summer 2014.
- `weather_data/smhi/` — SMHI hourly station observations for the fire period.
- `weather_data/era5-land/` — ERA5-Land hourly reanalysis (wind, temperature, humidity, precipitation) over the map area.
- `tools/` — data extraction scripts (FIRMS detections, OSM terrain, SMHI weather, ERA5-Land), the spread analysis, offline tiles, PostGIS loading, video recording and the simulator for the booth IoT nodes (`mqtt_node_sim.py`).
- `docker-compose.yml` — local PostGIS, offline map-tile and MQTT (Mosquitto) services; `mosquitto/` holds the broker configuration.
- `reports/` and `reviews/` — dated analyses, plans and reviews.

The one-pager is concept material. Proposed integrations, data, performance and scenario behavior have not been independently verified. The one-pager itself identifies some demo layers as simulated; keep that distinction visible in future materials and implementation.
