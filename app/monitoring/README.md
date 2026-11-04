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
- **What an alarm may threaten** (`gis.py`): from Flens kommun's own GIS (`gis.flen.se`), as the
  one-pager makes GIS the default: preschools, schools, the upper secondary school, health centres,
  district nurses and dental care (Kommunala_verksamheter) and the primary map's 13 466 buildings;
  from OpenStreetMap only what the municipality's services lack, marked so: the railway station,
  churches and the roads and railways (the comprehensive plan's transport and care layers give no
  geometry). Within 1 km of a fire, cloudburst or reported event, or in MCF's 100-year flow for a high
  flow. Kept after the check of laws and rules on 2026-11-03: no addresses or property designations,
  no housing for people with disabilities (until its security and data protection are reviewed),
  no water, sewage, power or protected objects; internal use only.
- **Briefing** (`briefing.py`): `/briefing/<id>`, a printable page with the facts, their sources
  and times, what is uncertain, the context and the contacts by role.
- **Layers**, each switched in mission control: the municipal map, SMHI's radar image and MCF's climate-adapted 100-year flow of Nyköpingsån (WMS) on
  the 2D map and the globe, as in the Flen scenarios; the wind arrows over the area and the weather
  chart over Scandinavia (isobars every 2 hPa with highs and lows, the hour's rain, thunder), from
  SMHI's forecast grid snow1g for the next whole hour (`weather.py`, with the scenarios'
  `tools/isobars.py` and `wind_barbs.js`), fetched again for a new run or hour and marked as a
  forecast; the protected objects, the place names (OSM), SMHI's flow and weather stations (Floda A,
  Eskilstuna A, Kolmården-Strömsfors A, Höksta and the daily rain stations, with their latest values),
  FIRMS's detections, and the latest Sentinel-2 image (`sentinel2.py`: Planetary Computer's catalogue
  and data API, the newest datatake of 14 days with at most 60 % cloud, else the clearest of 30 days,
  in true colour as the scenarios'); the latest Sentinel-1 radar pass (`sentinel1.py`: Planetary
  Computer's terrain-corrected sentinel-1-rtc, VV), as the scenarios' radar images: the grey radar
  image, which shows wet and rough ground bright, and the water outside OpenStreetMap's lakes in red
  (darker than the median over the lakes, five of nine neighbours) – a computed mask, not a mapped
  flood; and the ground's relative wetness by change detection (each pixel now between its driest and
  wettest in the last 120 days' passes of the same relative orbit, about 100 m, brown dry to blue
  wet; computed, not measured, left out in forest, built-up land and lakes); the weather chart, the
  optical image, the grey radar image and the wetness start off;
- **Marks**, as the user asked: SMHI's stations round with a white ring, blue, and red while one of
  them alarms (a high flow or record, or heavy rain: 10 mm in an hour at a weather station); the
  protected objects and other places of interest small, round and yellow;
- **Logs**: the satellite monitor logs only what is detected (FIRMS's detections, Sentinel-1's
  water outside the lakes from 0.5 % of the land, a proposal) and every alarm with its station and
  value, not the passes that see nothing; mission control's Logg lists every alarm, confirmation
  and dismissal;
- **Charts** in mission control: each station's flow of the last day with its limits, the hour's rain
  at Floda A, the radar's highest rate in the municipality in the last hour.
- **UPPLÄSNING** in mission control reads new alarms aloud with the scenarios' voice alma
  (`app/backend/speech.py`); off at the start.
- **IoT**: the demos' MQTT nodes (`techseed/<node>/<kind>` on 127.0.0.1:1883, `app/backend/iot.py`;
  `--mqtt`), simulated unless they say otherwise, listed in mission control; `start_demo` starts
  Mosquitto with the tiles. mission control's Läget nu gives the radar, the
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
- The comprehensive plan's care units for the elderly have no position in the municipality's
  services, so they are not placed; bus stops likewise.
- Not included: terrain on the globe, Sentinel images and passes, drones, reading the log aloud,
  kiosk mode, forwarding of alarms, fire models.
