# Project Context

Project: TechSeed Geospatial Intelligence

## Purpose

Develop the concept for a short, repeatable exhibition demonstrator showing how space-derived observations, geospatial information, IoT sensors, connectivity and AI could combine into an operational situation picture.

## Current Direction

- Focus the initial demonstrator on a clear 2–3 minute scenario rather than a complete operations-room product.
- Use the IoTDagen concept in `onepager.md` as the current user-provided starting point.
- Keep real, simulated and proposed data sources distinguishable in the demonstrator and its explanations.
- Prioritize a stable, repeatable operator-controlled scenario and evidence-linked AI assessment over breadth of integrations.
- Treat implementation choices and estimates in the one-pager as proposals, not approved architecture or verified commitments.
- A working prototype exists in `app/`: the Västmanland 2014 wildfire replayed from NASA FIRMS archive data on a 2D map and a CesiumJS globe, with mission control, simulated SATCOM outage, IoT, a traceable assessment and PostGIS questions. Västmanland 2014 is the prototype's scenario; it has not been recorded as a formal MVP decision.
- The 3D globe shows the 2014 satellites (Terra, Aqua, Suomi NPP, Landsat 8, ISS) at the scenario clock from Space-Track element sets; the positions are computed, not observed, and are checked against the FIRMS detection times.
- Decided 2026-10-04: for the exhibition demo the booth IoT nodes run simulated (`tools/mqtt_node_sim.py`) and are shown as simulated. Questions that only concern a real implementation are deferred to the backlog.
- Decided 2026-10-06: a second demo, flooding in Sundsvall 2026, uses the Västmanland fire demo as its template (same screens and parts; the scenario is chosen at start, the two demos need not run at the same time). It is a scenario built on the real rain of 16–19 August 2026 and the municipality's cloudburst models, clearly marked as a scenario rather than a replayed event; a flood in Sundsvall that day is not confirmed in open sources. See `reports/2026-10-06-datakallor-oversvamning-sundsvall-claude-opus-5-5.md`.
- Decided 2026-10-06: the user confirmed that the municipality's layers in its geoserver (bxkarta), among them the cloudburst models, may be used in the Sundsvall demo, although the service's terms limit use to five municipalities unless agreed. Only Sundsvall municipality's own layers are used; those of MSVAB, the county board and Lantmäteriet in the same service have other owners.
- A working Sundsvall flood scenario exists in `app/` (`--scenario sundsvall2026`): the municipality's rain gauges, its cloudburst models and MCF's flood maps, synthetic overflow sensors, a flood assessment, a detection sequence from real Sentinel-1 acquisitions and PostGIS questions; see Del 5 of the operator guide.
- Decided 2026-10-09: each Mission Control page load sends one shared scenario reset after the page, config and first scenario sync are ready. The reset restores the saved incident display profile. The demo launcher starts scenarios at their `PLAYBACK_START`; an explicit non-default `--at` remains an intentional seek after reset.
- Decided 2026-10-12: the demo's start and stop are set from Mission Control and saved in the display profile, and the profile is saved per scenario instead of per kind of incident. RESET does not change the start and stop; the saved ones apply when a demo starts.

## Current Work Handoff (2026-10-12)

- The latest code change on `main` is `3a6697a` (`Run each demo from the start and stop in its profile`), followed by this handoff update. When the handoff was written, `origin/main` was at `7344cb0`.
- Plan status (`reports/2026-10-02-plan-saknade-delar-claude-opus-5-5.md`, Status 2026-10-12): phases 0–5 are done in the prototype and phase 6 is partly done. Remaining in phase 6: kiosk with automatic restart, the closing view, the load test (8 hours and network outages) and performance measurements on the exhibition PC.
- Every repository's `AGENTS.md` and the workspace `AGENTS.md` now let a GO for staging, given after the scope and complete commit message were shown, also cover the commit.
- Mission Control has **Start** and **Stopp** fields (Swedish time) for the demo's playback window within the scenario's data period; **ANVÄND TIDER** applies them at once. RESET and PLAY after the stop go to the start, playback stops at the stop, and seeks stay inside the window. RESET, including the reset on each Mission Control page load, keeps the start and stop in use.
- The screens run from the profile's start and stop: `/api/config` gives them as `playback.start_utc` and `end_utc` (the saved profile's when the backend starts) and the scenario's period as `data_start_utc` and `data_end_utc`. The panel's rain, river-flow and fire-timeline charts span the demo and follow ANVÄND TIDER without a reload; "Sedan start" counts rain from the demo's start, and the rain chart's dates are in Swedish time. Mission Control's Start and Stopp fields are still limited to the data period. The tests read a profile file of their own, so the exhibition PC's saved profiles cannot change their results.
- **SPARA PROFIL FÖR SCENARIOT** saves image types, base maps, effective map-layer visibility and the playback window under the scenario's name in `data/display-profiles.json`. It is red while those settings differ from the profile the demo starts with. A scenario without its own profile falls back to the older per-incident profile (`wildfire`, `flood`). The exhibition PC now has its own Sundsvall profile with start and stop.
- Mission Control's left column holds the playback controls, the demo's start and stop, SATELLITE DETECTION and NÄSTA, KARTA and SENASTE SATELLITBILD, the image list and SPARA PROFIL. The middle column, **Kartan**, holds the map layers, image types, base maps and panel choices. Weather filtering controls wind, stations and SMHI radar while preserving individual layer choices.
- The scenario had started on 16 August because a long-running demo launcher still passed `CHECK_START_UTC` as `--at`. The user now runs `tools.start_demo` from a terminal again; restart it to load `3a6697a`.
- Verification: 340 tests passed and `git diff --check` passed. With a copy of the exhibition PC's profile, the panel started at 15 Aug 00:00 Swedish time with 0 mm rain since start, the rain chart spanned 08-15 to 08-18, and it was redrawn for a changed start and stop without a reload (Playwright, headless). Mission Control's layout and the red SPARA PROFIL were checked in headless Chrome against a test backend with a copy of the profile file. The headless Sundsvall check (`tools/check_demo.py`) was run twice against its own backend, simulated nodes and a temporary Mosquitto broker on port 18830. All nine steps passed in the second run (RESET 2.71 s); in the first only RESET failed, at 5.72 s. SwiftShader rendered the 3D view at 0.2 frames per second, so these times do not represent the exhibition PC; the 5-second RESET requirement still needs a `--headed` run there. With the shared broker on port 1883 the check had stopped at step 4 because of an extra live `test-node`; its source has not been investigated.
- Mission Control sends one reset after each page load, once the document, config and first scenario sync are ready. The demo launcher opens the screens at the start saved in the scenario's profile, else at its `PLAYBACK_START`; an explicit non-default `--at` remains an intentional seek after reset.
- The local, Git-ignored per-incident flood profile, now the fallback for flood scenarios without their own profile, selects offline OSM, the Sentinel-1 `radarwater` image type, and hides the SMHI precipitation-radar overlay. The five Sundsvall Sentinel-1 water-mask images are red and are rendered above municipal flood-map WMS layers in both maps. The mask is a simple radar threshold, not a verified flood extent; generated images and `SOURCE.json` remain in unversioned `data/`.
- No suitable 2026 measured river-flow series was found for Sundsvall: Skallböle KRV (Ljungan) observations end 2024-10-07, Bergeforsens KRV (Indalsälven) observations end 2015-12-31, and Selångersån has no SMHI flow station. The accessible Vattenwebb S-HYPE analysis ends 2024-12-31. No 2026 river-flow overlay has been implemented; a valid measurement source and local class thresholds are still needed.
- The Löderup–Ystad imagery investigation is parked. The ESA SPOT 1–5 access request is pending validation; no coastal imagery has been downloaded.

## Backlog

- Firmware for the booth nodes: nRF91 board, nRF Connect SDK version, Wi-Fi fallback.
- Exposing and securing the MQTT broker for real nodes (network, passwords or certificates).
- A real 1 h forecast horizon for +60 MIN (the forecast has 3, 6, 12 and 24 h).
- GOD VIEW in 2D needs a wider offline base map; the 3D globe works.
- Check Space-Track's user agreement for showing positions computed from its element sets in public at the exhibition.

## Boundaries

- This repository contains professional TechSeed work; apply the confidentiality and data-handling rules in `AGENTS.md`.
- Do not imply that illustrative event data or simulated integrations are live feeds.
- Record material assumptions and data-source limitations before relying on them in design or demonstrations.

## Open Questions

- Which scenario, geographic area and audience interaction should be the MVP baseline?
- Which data sources are approved for the demonstration? (Physical IoT devices are not needed for the demo; see the decision above.)
- Decision B3: may the OSM power grid be shown, and may partner names (Dacreo, BruhnBruhn) be used? Until then there is no power grid and the texts are generic.
- Which layers can be sourced live, and which should be explicitly simulated?
- What are the accepted data licensing, attribution, update, and network requirements?
- Which AI assessments and spatial queries must be demonstrably traceable to source observations?
- Combined sewer overflow data from MSVA for ten days around 16 August 2026: format, positions and whether it may be shown publicly.
