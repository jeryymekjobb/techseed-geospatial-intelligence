# TechSeed Geospatial Intelligence

A repeatable geospatial-intelligence demonstrator, built for IoTDagen 2026 and now used internally, with 16 replayed wildfire, flood and coastal-erosion scenarios. The concept combines space-derived observations, GIS, weather, IoT and infrastructure data into an operational common picture.

## Contents

- `onepager.md` — user-provided concept for the exhibition demonstrator. Its LLM/AI agent was not built; the questions are prepared and the assessments rule-based.
- `CONTEXT.md` — project purpose, boundaries and current direction.
- `AGENTS.md` — repository working and review rules.
- `docs/operatorsguide.md` — operator guide (Swedish) for running the demo: preparation, start, the two-minute script, what is real or simulated, troubleshooting.
- `docs/mvp/` — groundwork for an MVP: the inventory of today's functions, the register of regulations and the requirements template.
- `app/` — the demonstrator: backend with one module per scenario, 2D map and 3D globe, mission control, satellite monitor, IoT, assessment and spatial questions; see `app/README.md`.
- `data/` — the scenarios' fetched data (not versioned; fetch with `tools.fetch_scenario`).
- `satellite_data/firms/` — NASA FIRMS archive extracts for summer 2014.
- `weather_data/smhi/` — SMHI hourly station observations for the fire period.
- `weather_data/era5-land/` — ERA5-Land hourly reanalysis (wind, temperature, humidity, precipitation) over the map area.
- `tools/` — data extraction scripts (FIRMS detections, OSM terrain, SMHI weather, ERA5-Land), the spread analysis, offline tiles, PostGIS loading, video recording and the simulator for the IoT nodes (`mqtt_node_sim.py`).
- `docker-compose.yml` — local PostGIS, offline map-tile and MQTT (Mosquitto) services; `mosquitto/` holds the broker configuration.
- `reports/` and `reviews/` — dated analyses, plans and reviews.

The one-pager is concept material. Proposed integrations, data, performance and scenario behavior have not been independently verified. The one-pager itself identifies some demo layers as simulated; keep that distinction visible in future materials and implementation.
