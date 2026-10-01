# OpenStreetMap targets for the fire-spread analysis

`targets-vastmanland.geojson` holds places (547), building centre points (7,560),
roads (1,260 ways: motorway to unclassified) and railways (96 ways) inside
59.75–60.08° N, 15.85–16.45° E, fetched with `tools/fetch_osm_targets.py` from
the Overpass API on 2026-10-01.

Source and licence: © OpenStreetMap contributors, ODbL 1.0,
<https://www.openstreetmap.org/copyright>. OSM shows the current state, not 2014;
buildings and roads may have been added, removed or rebuilt since the fire.
Power lines and other critical infrastructure are not included.

Regenerate:

```bash
python3 -m tools.fetch_osm_targets --bbox 59.75,15.85,60.08,16.45 --out osm_data/targets-vastmanland.geojson
```
