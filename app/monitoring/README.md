# Continuous monitoring (first version)

A first implementation of the MVP one-pager's operational chain (`docs/mvp/onepager-mvp.md`) for
**Flens kommun**: events in, live sources, detection, alarms the operator confirms or dismisses, a
sourced briefing and contact lists by role. It is a service of its own beside the demo and does
not touch the scenario playback. Its data are **live**; events from the inbox are marked as
simulated unless they say otherwise.

## Run

From the start page, as the demos (`docs/operatorsguide.md`, section 7):

```bash
.venv/bin/python -m tools.start_demo      # Övervakning → Flens kommun
```

`start_demo` starts the tiles service with the area's offline map (`TILES_FILE`), the monitoring on
the demos' port 8765 and the three screens in the demos' places: the satellite monitor
(`/monitor.html`), the 3D globe (`/3d.html`) and mission control with the alarms (`/control.html`).
BYT in mission control returns to the start page.

On its own:

```bash
.venv/bin/python -m app.monitoring --area flenkommun            # http://127.0.0.1:8770/
.venv/bin/python -m app.monitoring --area flenkommun --once     # one poll, a summary, exit
```

`--port` sets the port, `--data-dir` keeps the state, inbox and log elsewhere (for a trial). The
service polls every 5 minutes (`POLL_SECONDS`) and runs as long as the process runs; it is not a
24/7 operated service. It needs no packages beyond the standard library.

The base map is the municipality's own, as the one-pager makes GIS the default: Flens kommun's
Bakgrundskarta, fetched once and kept locally for internal use, as the user decided on 2026-11-03
(the same solution as Sundsvall's and Västerås's):

```bash
.venv/bin/python -m tools.fetch_municipal_basemap --area flenkommun
```

Outside the municipality, where the municipal map is transparent, OpenStreetMap's standard map lies
under it, online: it has land cover at every zoom and no edge, which the demos' offline map
(`data/tiles/flenkommun.mbtiles`) lacks at low zooms and at its area's edges. The offline map takes
its place only when OpenStreetMap cannot be fetched. The offline map's road numbers and railway
tunnels, which the municipal map lacks, lie over it, clipped by the backend to the municipality's
border (`service.clip_to_border`), since OpenStreetMap's own map has them outside.

The satellites are those whose data the monitoring uses, NASA FIRMS's Suomi NPP, NOAA-20, NOAA-21,
Terra and Aqua. Their current element sets come from Space-Track (class `gp`) with the account in
`~/.spacetrackrc`, kept in `data/monitoring/tle/current.json` and fetched again at most once a day
(`satellites.py`). The screens compute where they are now with satellite.js; the positions are
computed, not observed.

NASA FIRMS needs a free MAP_KEY (https://firms.modaps.eosdis.nasa.gov/api/map_key/), kept outside
the repository:

```bash
printf '%s\n' 'YOUR_MAP_KEY' > ~/.firms_map_key
chmod 600 ~/.firms_map_key
```

or in `FIRMS_MAP_KEY`. Without it the source shows "nyckel saknas" and the others go on. The key
is never logged or shown.

## What it does

- **Events in** (`events.py`): files dropped in `data/monitoring/flenkommun/inbox/` (TSV, CSV or
  JSON) in the one-pager's format,
  `<datum> <klockslag> <händelse> <koordinat 1> <koordinat 2> <koordinatsystem> <källa> [<simulerad>]`,
  in UTC, with EPSG:4326 (lat, lon) or EPSG:3006 (N, E). A line without a source, or with another
  fault, is logged before it is refused, and shown on the operator page. Files read are moved to
  `inbox/processed/`.
- **Live sources** (`sources.py`, `radar.py`): SMHI's flows (Hebylund Kvarnsjön, Sibro 2,
  Hallbosjön) and the statistics of their corrected archives, SMHI's hourly rain at Floda A, SMHI's
  weather radar every 5 minutes over the municipality (the scenarios' conversion,
  `tools/fetch_smhi_radar.py`), SMHI's fire risk forecast (FWI) and point forecast, SMHI's warnings
  for the county or over the municipality, Krisinformation's VMA and news, MCF's fire ban for Flen and
  municipal border, and NASA FIRMS's near-real-time fire detections. A failing source is shown;
  the others go on.
- **Detection** (`rules.py`), by the kinds of events of the scenarios: a high flow above the 99th
  percentile of the station's daily flows at two readings in a row, a record above the archive's
  highest (the high flows of the Flen, Västerås and Ljungan scenarios); a cloudburst when the radar
  estimates at least 20 mm/h in the municipality, confirmed by 10 mm in the last hour at Floda A or a
  warning (Sundsvall 2026, Kramfors 2026); raised fire risk at SMHI's class 5 or 6 today or tomorrow,
  and the fire risk with every fire (Västmanland 2014, Kårböle 2018); SMHI's yellow, orange and red
  warnings for flood and fire; VMA; FIRMS fires in the municipality, clustered within 1 km; events
  from the inbox in the municipality. Fewer false alarms: a second source confirms (rain, a
  warning, several passes or satellites, a report near a detection), known heat sources are left
  out (none entered yet), Walpurgis Night and the fire ban are given as context. The limits are
  proposals.
- **Alarms** (`alarms.py`): new until the operator confirms or dismisses them; every action is
  logged. Nothing is sent onward.
- **Briefing** (`briefing.py`): `/briefing/<id>`, a printable page with the facts, their sources
  and times, what is uncertain, the context and the contacts by role.
- **Layers:** SMHI's radar image and MCF's climate-adapted 100-year flow of Nyköpingsån (WMS) on
  the 2D map and the globe, as in the Flen scenarios; the wind arrows over the area and the weather
  chart over Scandinavia (isobars every 2 hPa with highs and lows, the hour's rain, thunder), from
  SMHI's forecast grid snow1g for the next whole hour (`weather.py`, with the scenarios'
  `tools/isobars.py` and `wind_barbs.js`), fetched again for a new run or hour and marked as a
  forecast; mission control's VINDPILAR and VÄDERKARTA show them on the main screen (the arrows
  start on, the chart off, as in the scenarios); mission control's Läget nu gives the radar, the
  fire risk, the forecast and the flows.
- **Screens** (`web/`): mission control (`control.*`) with the map, the alarms, the sources, the
  events in and BYT; the 3D globe (`globe.*`) with the border, stations, detections, events, current
  alarms and the satellites with their orbits; the satellite monitor (`satellites.*`, with the demos'
  `orbits.js` and `satmonitor.js`) with the passes over the area and a log of passes, detections and
  alarms.

## Limits

- The contact roles in `areas/flenkommun.py` are an example, not agreed with the municipality or
  the rescue service; names and numbers stay out of the repository.
- The flow limits compare 15-minute values with daily means of SMHI's archive.
- SMHI's warning codes were mapped from the warnings active on 2026-11-03.
- The terms of Krisinformation's API and MCF's services are not checked
  (`reports/2026-11-03-mcf-data-och-tjanster-claude-opus-5-5.md`).
- Flens kommun's map is for internal use; ask the municipality before it is shown publicly.
- Landslides have no live rule: Flens kommun's stability mapping (1992-1996, map 1A) is not
  published by MCF as zones, and SGI's quick-clay and landslide layers answer only SGI's own viewer.
  SMHI's lightning comes a day late, and there is no coast for erosion.
- Not included: terrain on the globe, Sentinel images and passes, drones, reading the log aloud,
  kiosk mode, forwarding of alarms, fire models.
