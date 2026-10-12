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

## Current Work Handoff (2026-10-10)

- `main` is at `e4a1e7d` (`Reset demos to their saved startup view`), pushed to `origin/main`; the worktree was clean after the push.
- Mission Control groups GOD VIEW categories and map layers in **Kartans lager**. Weather filtering controls wind, stations and SMHI radar while preserving individual layer choices. Profiles now persist image types, base maps and effective map-layer visibility.
- Verification: 330 tests passed and `git diff --check` passed. The latest headless Sundsvall check reaches step 4, then stops because a shared MQTT broker reports an extra live `test-node` in addition to the four simulated booth nodes. Steps 1–3 pass. SwiftShader frame-rate results do not represent the exhibition PC.
- Mission Control sends one reset after each page load, once the document, config and first scenario sync are ready. The demo launcher defaults every scenario to its `PLAYBACK_START`; an explicit non-default `--at` remains an intentional seek after reset.
- The local, Git-ignored flood profile selects offline OSM, the Sentinel-1 `radarwater` image type, and hides the SMHI precipitation-radar overlay. The five Sundsvall Sentinel-1 water-mask images are red and are rendered above municipal flood-map WMS layers in both maps. The mask is a simple radar threshold, not a verified flood extent; generated images and `SOURCE.json` remain in unversioned `data/`.
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
