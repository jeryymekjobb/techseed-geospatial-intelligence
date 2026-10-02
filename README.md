# TechSeed Geospatial Intelligence

Concept work for a repeatable geospatial-intelligence demonstrator for IoTDagen. The initial concept combines space-derived observations, GIS, weather, IoT and infrastructure data into an operational common picture.

## Contents

- `onepager.md` — user-provided concept for the exhibition demonstrator.
- `CONTEXT.md` — project purpose, boundaries and current direction.
- `AGENTS.md` — repository working and review rules.
- `app/` — fire-map prototype (backend and browser GUI) for the Västmanland 2014 scenario; see `app/README.md`.
- `satellite_data/firms/` — NASA FIRMS archive extracts for summer 2014.
- `weather_data/smhi/` — SMHI hourly station observations for the fire period.
- `weather_data/era5-land/` — ERA5-Land hourly reanalysis (wind, temperature, humidity, precipitation) over the map area.
- `tools/` — data extraction scripts (FIRMS detections, OSM terrain, SMHI weather, ERA5-Land), the spread analysis, offline tiles, PostGIS loading and video recording.
- `docker-compose.yml` — local PostGIS and offline map-tile services.

The one-pager is concept material. Proposed integrations, data, performance and scenario behavior have not been independently verified. The one-pager itself identifies some demo layers as simulated; keep that distinction visible in future materials and implementation.
