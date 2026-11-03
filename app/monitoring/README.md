# Continuous monitoring (first version)

A first implementation of the MVP one-pager's operational chain (`docs/mvp/onepager-mvp.md`) for
**Flens kommun**: events in, live sources, detection, alarms the operator confirms or dismisses, a
sourced briefing and contact lists by role. It is a service of its own beside the demo and does
not touch the scenario playback. Its data are **live**; events from the inbox are marked as
simulated unless they say otherwise.

## Run

```bash
.venv/bin/python -m app.monitoring --area flenkommun            # http://127.0.0.1:8770/
.venv/bin/python -m app.monitoring --area flenkommun --once     # one poll, a summary, exit
```

`--port` sets the port, `--data-dir` keeps the state, inbox and log elsewhere (for a trial). The
service polls every 5 minutes (`POLL_SECONDS`) and runs as long as the process runs; it is not a
24/7 operated service. It needs no packages beyond the standard library.

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
- **Live sources** (`sources.py`): SMHI's flows (Hebylund Kvarnsjön, Sibro 2, Hallbosjön) and the
  statistics of their corrected archives, SMHI's hourly rain at Floda A, SMHI's warnings for the
  county or over the municipality, Krisinformation's VMA and news, MCF's fire ban for Flen and
  municipal border, and NASA FIRMS's near-real-time fire detections. A failing source is shown;
  the others go on.
- **Detection** (`rules.py`): a high flow above the 99th percentile of the station's daily flows
  at two readings in a row, a record above the archive's highest; SMHI's yellow, orange and red
  warnings for flood and fire; VMA; FIRMS fires in the municipality, clustered within 1 km; events
  from the inbox in the municipality. Fewer false alarms: a second source confirms (rain, a
  warning, several passes or satellites, a report near a detection), known heat sources are left
  out (none entered yet), Walpurgis Night and the fire ban are given as context. The limits are
  proposals.
- **Alarms** (`alarms.py`): new until the operator confirms or dismisses them; every action is
  logged. Nothing is sent onward.
- **Briefing** (`briefing.py`): `/briefing/<id>`, a printable page with the facts, their sources
  and times, what is uncertain, the context and the contacts by role.
- **Operator page** (`web/`): OpenStreetMap as the fallback, since Flens kommun's own maps are not
  used until the municipality allows it, with the border, stations, detections and alarms.

## Limits

- The contact roles in `areas/flenkommun.py` are an example, not agreed with the municipality or
  the rescue service; names and numbers stay out of the repository.
- The flow limits compare 15-minute values with daily means of SMHI's archive.
- SMHI's warning codes were mapped from the warnings active on 2026-11-03.
- The terms of Krisinformation's API and MCF's services are not checked
  (`reports/2026-11-03-mcf-data-och-tjanster-claude-opus-5-5.md`).
- Not included: Flens kommun's GIS, Sentinel images and passes, drones, forwarding of alarms, fire
  models.
