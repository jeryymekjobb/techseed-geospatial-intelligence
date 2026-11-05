# Continuous monitoring (first version)

A first implementation of the MVP one-pager's operational chain (`docs/mvp/onepager-mvp.md`) for
**Flens kommun** and, with it as the template, the municipalities of the other scenarios: events in, live sources, detection, alarms the operator confirms or dismisses, a
sourced briefing and contact lists by role. It is a service of its own beside the demo and does
not touch the scenario playback. Its data are **live**; events from the inbox are marked as
simulated unless they say otherwise.

## Areas

One module per municipality in `app/monitoring/areas/`, all taking the template's shared satellites,
limits, FIRMS, Meteosat and example contacts from `areas/common.py`, and their offline map, OSM
targets, terrain, MCF flood zone and level sensors from their scenarios' unversioned data:

| Area (`--area`) | Scenarios | Flows (SMHI, live) | Base map |
|---|---|---|---|
| `flenkommun` | Flen 2019, 2021, 2024 | Hebylund, Sibro 2, Hallbosjön | Flens kommun's Bakgrundskarta |
| `sundsvallkommun` | Sundsvall 2020, 2023, 2026, Ljungan 2023 | Norrsjön (Ljungan) | Sundsvalls kommun's Kartan |
| `kramforskommun` | Kramfors 2026, Västernorrland 2025 | Risnäs (Gådeån) | OpenStreetMap |
| `ljusdalkommun` | Kårböle 2018 | Saras fors, Oppli (Ljusnan) | OpenStreetMap |
| `salakommun` | Västmanland 2014 | Tärnsjö, Gränvad | OpenStreetMap |
| `vasterasstad` | Svartån 2023 | Åkesta kvarn, Berg, Gränvad | Västerås stad's karta |
| `hoorkommun` | Skåne 2024 | Heåkra, Ellinge | Höörs kommun's Baskarta (Geoinfo Mittskåne) |
| `vellingekommun` | Falsterbonäset | none; the sea level at Klagshamn | Vellinge kommun's Bakgrundskarta (full colour) |

Besides SMHI's own stations, Sundsvall shows the municipality's rain gauges that SMHI publishes
(Fillan, Heffners, Bredsand, Essvik, Bällsta, Stångom, Stöde, Indal, Söråker) and Höör the gauges
near Ringsjöarna (Kungshult VV), as the scenarios show them
(`"rain_gauge"` in `WEATHER_STATIONS`, `sources.rain_gauge`): they report only hours with rain, so a
dry gauge stays on the map with "inget regn uppmätt"; SMHI's suspect values (quality Y) and hours
above 100 mm are left out. On the 2D map the marks lie in a pane of their own over the wind arrows
and images.

Every station SMHI lists as active in the municipality or within 5 km of it is taken in, as the user
asked on 2026-11-04, even one that gives no values: it is placed from SMHI's description of it, drawn
grey on both maps and listed under "Tysta stationer" in mission control, as a hint it may be out of
order (no value for two days, three for the rain by the day). Weather stations farther off are left
out, as the user chose on 2026-11-05, except the rain stations that confirm the alarms
(`RAIN_STATIONS`); the flow, water-level and sea-level stations are kept wherever they lie, since
the alarms read them. Sibro 2 and Ringsjödammen also give the
water level (one value a day, the height system not named), with the archive's highest as the limit
for "Rekordhögt vattenstånd"; Sundsvall (Spikarna), Kramfors (Lunde) and Vellinge (Klagshamn, Skanör)
the sea level.

The stations were checked live on 2026-11-04: several of the scenarios' stations (Skallböle,
Torpshammar, Ringsjödammen, Hjälta, Sollefteå) give only SMHI's corrected archive, so the nearest
live ones are used, and the scenarios' level sensors are kept only where they follow one of them.
Only Flens kommun's own GIS (protected objects, buildings) is used, as the check of laws and rules
covered it alone; the others take their protected objects and buildings from OpenStreetMap. The
municipal maps of Sundsvall and Västerås are those fetched for their scenarios, for internal use as
the user allowed (Västerås's is fetched again over the whole municipality into the monitoring's own
folder, `fallback_dir` keeping the scenario's until then); Vellinge's (ArcGIS REST, no terms stated) is fetched with
`tools.fetch_municipal_basemap --area vellingekommun`, for internal use as the user allowed on
2026-11-04, and so is Höör's (`Baskarta_Hoor_OpenData` on Geoinfo Mittskåne's server, found by the
report of 2026-11-04). Kramfors, Ljusdal and Sala publish no background map of their own (checked
2026-11-04: Sokigo's Spatial Map with Lantmäteriet's maps, Lantmäteriet's Topowebb through a proxy),
so OpenStreetMap stays their base map.

Vellinge's sea level is read live at Klagshamn (SMHI's ocobs parameter 6, cm in RH2000), since
Skanör's gauge, which Falsterbo's scenario follows, offers SMHI's archive only; from 100 cm, the
scenario's limit and a proposal, it raises "Högt vattenstånd", and the scenario's three simulated
beach sensors follow it (`LEVEL_SENSOR_STATIONS`).

Where a municipality has no public map of its own (Kramfors, Ljusdal, Sala:
`LANTMATERIET_BASEMAP`), Lantmäteriet's Topografisk webbkarta becomes the base map through the
service (`/lm/topowebb/`, so the credentials stay on the server) once a Geotorget order's settings
are in a file outside the repository:

```bash
cat > ~/.lantmateriet <<'END'
LM_USERNAME=<användarnamn från Geotorget>
LM_PASSWORD=<lösenord från Geotorget>
LM_TOPOWEBB_URL=https://<adressen från Geotorget>/{z}/{y}/{x}.png
END
chmod 600 ~/.lantmateriet
```

The environment's `LM_*` win over the file. Without them the base map stays OpenStreetMap.

Sundsvall's cloudburst model (the greatest water depth at a 30-, 100- and 500-year rain) and
Västerås stad's (100-year rain) are laid over the maps straight from the municipalities' WMS, as
their scenarios show them, for internal use as the user allowed (layers `skyfall30`, `skyfall100`,
`skyfall500`, off at the start); Flen's are fetched tiles.

The scenarios' offline map and 3D terrain cover their map area only. An area's own, over its whole
municipality (its `BBOX`), is built with the scenarios' tools and taken once there
(`areas.common.built_terrain`, `built_tiles`):

```bash
.venv/bin/python -m tools.fetch_copernicus_dem --area sundsvallkommun   # data/monitoring/<area>/dem/
.venv/bin/python -m tools.build_terrain --area sundsvallkommun          # data/monitoring/<area>/terrain/
.venv/bin/python -m tools.build_offline_tiles --area sundsvallkommun    # data/tiles/<area>.mbtiles
```

## Run

From the start page, as the demos (`docs/operatorsguide.md`, section 7):

```bash
.venv/bin/python -m tools.start_demo      # Övervakning → a municipality
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

The same tool fetches the municipality's cloudburst mapping (Skyfallskartering, the water depth of a
100- and a 500-year rain over Flen's town, zoom 12-16) as transparent layers laid over the maps, also
for internal use only, as the user allowed on 2026-11-04:

```bash
.venv/bin/python -m tools.fetch_municipal_basemap --area flenkommun --map skyfall100
.venv/bin/python -m tools.fetch_municipal_basemap --area flenkommun --map skyfall500
```

The globe uses the Flen scenarios' 3D terrain (`data/flenkommun2024/terrain`, served at `/terrain/`)
when it is there, else the ellipsoid.

Outside the municipality, where the municipal map is transparent, OpenStreetMap's standard map lies
under it, online: it has land cover at every zoom and no edge, which the demos' offline map
(`data/tiles/flenkommun.mbtiles`) lacks at low zooms and at its area's edges. The offline map takes
its place only when OpenStreetMap cannot be fetched. The offline map's road numbers and railway
tunnels, which the municipal map lacks, lie over it, clipped by the backend to the municipality's
border (`service.clip_to_border`), since OpenStreetMap's own map has them outside.

The satellites are those whose data the monitoring uses: NASA FIRMS's Suomi NPP, NOAA-20, NOAA-21,
Terra and Aqua, Sentinel-1C and 1D (radar), Sentinel-2A, 2B and 2C, Landsat 8 and 9, and the
geostationary Meteosat-10, whose cloud mask the monitoring shows (on the satellite monitor, not the globe).
Their current element sets come from Space-Track (class `gp`) with the account in
`~/.spacetrackrc`, kept in `data/monitoring/tle/current.json` and fetched again at most once a day
(`satellites.py`). The screens compute where they are now with satellite.js; the positions are
computed, not observed.

Meteosat's cloud mask (`meteosat.py`, as the Flen scenarios' `tools/fetch_meteosat_clm.py`) gives the
cloudy share of the municipality's pixels every 15 minutes, about an hour late, kept for the last day
in `data/monitoring/flenkommun/meteosat-clm/`; it says why an optical image is old. It needs the
EUMETSAT API key in `~/.eumdac/credentials` (one line `KEY,SECRET`, `chmod 600`) and eumdac and
eccodes (`tools/requirements-meteosat.txt`); without them the source says the key is missing.

The Flen scenarios' simulated level sensors (`levels.py`, the eight points of
`data/flenkommun2024/sensors/level-points.geojson` where larger roads cross MCF's 100-year flow) each
follow the live flow of Sibro 2 or Hallbosjön and alarm, as in the scenarios, above the highest daily
flow in SMHI's archive; marked simulated on the maps (a magenta ring) and in mission control's IoT.
Mission control's Simulerade sensorer has one switch for every simulated sensor: the level sensors
on both maps and in IoT, and the MQTT nodes not marked real in IoT.

Both maps keep the credits out of the map picture, as the scenarios (`app/frontend/credits.js`):
OpenStreetMap's credit, and the municipal map's while it is shown, stay in the corner, as
OpenStreetMap's licence asks; "(i) Källor" opens the whole list of every source the map shows.
Errors and notes, such as missing orbital elements, have a line of their own under the globe.

SPARA INSTÄLLNINGAR in mission control saves the display settings in use (the map layers, the
simulated sensors, 2D or 3D and UPPLÄSNING) in `data/monitoring/<area>/settings.json`, which is not
in the repository, and the monitoring starts with them; as the scenarios' SPARA PROFIL, the button
is red while the settings differ from those it starts with.

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
  the 2D map and the globe, as in the Flen scenarios; the wind arrows over the area (about 10 km
  apart) and the weather chart over Scandinavia (its own wind arrows about 75 km apart, isobars every
  2 hPa with highs and lows sought in SMHI's whole grid within about 200 km, drawn as a large blue H
  or red L with the pressure, the hour's rain, thunder); the arrows are thinned by zoom on both maps
  so they stay about 70 px apart (each arrow's tier in `weather.py`), from
  SMHI's forecast grid snow1g for the next whole hour (`weather.py`, with the scenarios'
  `tools/isobars.py` and `wind_barbs.js`), fetched again for a new run or hour and marked as a
  forecast; the protected objects, the place names (OSM), SMHI's flow and weather stations (Floda A,
  Eskilstuna A, Kolmården-Strömsfors A, Höksta and the daily rain stations, with their latest values),
  FIRMS's detections, and the latest Sentinel-2 image (`sentinel2.py`: Planetary Computer's catalogue
  and data API, the newest datatake of 14 days with at most 60 % cloud, else the clearest of 30 days,
  in true colour as the scenarios'), and the latest Landsat 8 or 9 image chosen the same way
  (Collection 2 Level-2, true colour as the scenarios' Landsat); the latest Sentinel-1 radar pass (`sentinel1.py`: Planetary
  Computer's terrain-corrected sentinel-1-rtc, VV), as the scenarios' radar images: the grey radar
  image, which shows wet and rough ground bright, and the water outside OpenStreetMap's lakes and sea
  in red (darker than the median over them, five of nine neighbours; the sea from OSM's coastline
  water polygons, `data/osm/<area>-coastline/`, where the area's offline map was built) – a computed mask, not a mapped
  flood; and the ground's relative wetness by change detection (each pixel now between its driest and
  wettest in the last 120 days' passes of the same relative orbit, about 100 m, brown dry to blue
  wet; computed, not measured, left out in forest, built-up land, lakes and the sea); the weather chart, the
  MCF's highest computed flow (layer 9 of the flood mapping) and the municipality's cloudburst
  mapping for 100- and 500-year rain (a model, not an observation); the weather chart, the optical
  images, the grey radar image, the wetness, the highest flow and the cloudburst layers start off;
- **Marks**, as the user asked: SMHI's stations round with a white ring, blue, and red while one of
  them alarms (a high flow or record, or heavy rain: 10 mm in an hour at a weather station); the
  protected objects and other places of interest small, round and yellow;
- **Logs** in mission control: Detektioner och larm lists, for the last day, only what is detected
  (FIRMS's detections, Sentinel-1's water outside the lakes from 0.5 % of the land, a proposal) and
  every alarm with its station and value, not the passes that see nothing; Logg lists every alarm,
  confirmation and dismissal;
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
  `orbits.js` and `satmonitor.js`) with the passes over the area.

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
