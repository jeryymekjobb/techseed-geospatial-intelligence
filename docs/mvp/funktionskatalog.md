# Funktionskatalog – dagens demonstrator

Underlag för MVP:n, fas 0a. Inventering av vad demonstratorn gör i dag, gjord 2026-11-01
mot `main` på `42fd050` ur koden i `app/` och `tools/`, testerna i `tests/` och
`docs/operatorsguide.md`. Katalogen beskriver funktioner som finns. Den är inte en
kravspecifikation och inte ett beslut om vad MVP:n ska innehålla.

Varje funktion har ett ID (`F-xx-nn`) som kravspecifikationen kan spåra till senare.
Kolumnen **Tester** anger testfiler i `tests/` som täcker funktionen. Att en fil nämns betyder
inte att funktionen är fullständigt verifierad.

## Märkning av data

| Märkning | Betydelse |
|---|---|
| **V** | Verkliga observationer, uppspelade i efterhand. Inget är live. |
| **M** | Modell eller analys från en extern källa, till exempel en skyfallsmodell eller ERA5. |
| **B** | Beräknat i demonstratorn ur data, till exempel satellitpositioner, poäng och vattenmasker. |
| **S** | Syntetiskt eller simulerat för demon, till exempel sensorer och operatörens händelser. |
| **–** | Funktion utan egna data, till exempel styrning eller drift. |

## Omfattning i dag

- **Två händelsetyper:** skogsbrand (`wildfire`) och översvämning (`flood`).
- **16 scenarier** i `app/backend/scenarios/`:
  - Brand: Västmanland 2014 och Kårböle 2018.
  - Översvämning: Sundsvall 2026, november 2023, februari 2020 och december 2020, Ljungan
    augusti 2023, Västernorrland 2025, Kramfors 2026, Skåne 2024, Västerås september 2023,
    Flen 2019 och 2024 och Flens kommun 2021 och 2024.
  - Stranderosion: Falsterbonäset 2012–2026, byggt som ett översvämningsscenario.
- **Ett scenario i taget:** det väljs när backend startar (`TECHSEED_SCENARIO`).
- **Skärmar:** huvudskärm (2D-karta eller 3D-glob), mission control, satellitmonitor och
  kioskläge. Alla är webbsidor som hämtar från en backend på samma dator.
- **Tester:** 709 testfunktioner i 92 testfiler (räknat 2026-11-01).

## A. Scenarier och uppspelning

| ID | Funktion | Märkning | Moduler | Tester |
|---|---|---|---|---|
| F-SC-01 | Scenariodefinition: område, period, datakällor, texter, kontrollpunkter och kreditering per scenario | – | `app/backend/scenario.py`, `app/backend/scenarios/*.py` | `test_scenario.py`, `test_sundsvall_feb2020.py`, `test_sundsvall_dec2020.py` |
| F-SC-02 | Gemensam scenarioklocka för alla skärmar: play, paus, reset, hastighet, hopp i tid, ström till skärmarna (SSE) | – | `scenario_engine.py`, `/api/scenario`, `/api/scenario/stream` | `test_scenario_engine.py` |
| F-SC-03 | Visningsprofil per scenario: bildtyper, baskartor, lager, uppläsning, start, stopp och hastighet | – | `profiles.py` | `test_profiles.py` |
| F-SC-04 | Sammanfattning vid start och slutbild: vad scenariot visar och vad som är verkligt, beräknat eller simulerat | – | `SUMMARY` i scenarierna, `panel.js`, `satlog.js` | `test_satlog.py`, `test_scenario.py` |
| F-SC-05 | Tidsdiagram i panelen med en klocklinje som kan dras fram och tillbaka | V/B | `panel.js`, `chart_clock.js` | `test_chart_clock.py` |
| F-SC-06 | Kioskalternativ i URL:en: visa allt, starttid, autoplay, hastighet, prognoshorisont | – | `kiosk.js` | `test_scenario_engine.py`, `test_record_demo.py` |

## B. Lägesbild i 2D och 3D

| ID | Funktion | Märkning | Moduler | Tester |
|---|---|---|---|---|
| F-MAP-01 | 2D-karta (Leaflet) och 3D-glob (CesiumJS utan Cesium ion) med samma gränssnitt | – | `map2d.js`, `map3d.js`, `panel.js` | `test_map_adapters.py` |
| F-MAP-02 | Offline-baskarta från OpenStreetMap via egen tileserver, med etiketter och vägöverlägg | V | `offline_tiles.py`, `tools/build_offline_tiles.py` | `test_offline_and_labels.py`, `test_basemaps.py` |
| F-MAP-03 | Val av baskarta: offline-OSM, OSM online, Lantmäteriets topowebb (via proxy med inloggning på servern), kommunens kartor sparade lokalt | V | `basemaps.js`, `lantmateriet.py`, `municipal_basemap.py` | `test_basemaps.py`, `test_municipal_basemap.py` |
| F-MAP-04 | Världskarta utanför scenarioområdet (Natural Earth II) i 2D och 3D | V | `natural_earth.js` | `test_natural_earth.py` |
| F-MAP-05 | 3D-terräng från Copernicus DEM GLO-30 | V | `tools/build_terrain.py`, `tools/quantized_terrain.py` | `test_terrain.py`, `test_quantized_terrain.py` |
| F-MAP-06 | WMS-proxy för kommunens och MCF:s översvämningskartor, bara listade lager, med skydd mot för stora rutor och döda tjänster | M | `wms.py` | `test_scenario.py`, `test_app_backend.py` |
| F-MAP-07 | Källkreditering: kort rad i kartan, hela listan bakom "(i) Källor", i sammanfattningen och i slutbilden | – | `credits.js` | `test_credits.py` |
| F-MAP-08 | Vyer: GOD VIEW, rymdvy, kameraflygning från rymden, växling 2D/3D från mission control | – | `map2d.js`, `map3d.js`, `kiosk.js` | `test_mission_control.py`, `test_view_caption.py` |
| F-MAP-09 | Filter per kategori: rymd, IoT, infrastruktur, väder | – | `scenario_engine.py` (`FILTERS`) | `test_mission_control.py` |
| F-MAP-10 | Terränglager och mål från OpenStreetMap (byggnader, vägar, orter) | V | `/api/layers/terrain`, `tools/fetch_osm_terrain.py`, `tools/fetch_osm_targets.py` | `test_fetch_osm_terrain.py`, `test_fetch_osm_targets.py` |

## C. Satellitdata

| ID | Funktion | Märkning | Moduler | Tester |
|---|---|---|---|---|
| F-SAT-01 | Brandpunkter från NASA FIRMS (MODIS, VIIRS), uppspelade efter scenarioklockan | V | `/api/hotspots`, `/api/stream`, `tools/firms_extract.py` | `test_firms_extract.py`, `test_app_backend.py` |
| F-SAT-02 | Meteosats brandpixlar (LSA SAF FRP-Pixel), med jämförelseområde | V | `meteosat.py`, `meteosat.js` | `test_meteosat.py` |
| F-SAT-03 | Brandrisk från LSA SAF (FRM v3), en karta per dag | M | `meteosat_frm.py`, `meteosat_frm.js` | `test_meteosat_frm.py` |
| F-SAT-04 | Meteosats molnmask, molntoppshöjd, MTG:s Lightning Imager och instabilitetsindex | V | `meteosat_clm.py`, `meteosat_cth.py`, `meteosat_li.py`, `meteosat_gii.py` | `test_meteosat_clm.py`, `test_meteosat_cth.py`, `test_meteosat_mtg.py` |
| F-SAT-05 | Satellitbilder före, under och efter: Landsat, Sentinel-2 (naturlig färg, falsk färg, NDMI, vattenmask) och Sentinel-1 (radar och enkel vattentröskel) | V/B | `landsat.py`, `landsat.js`, `tools/fetch_*_scene.py` | `test_landsat.py`, `test_sentinel1.py`, `test_sentinel2.py` |
| F-SAT-06 | Sentinel-1:s vind över havet vid varje passage | V | `sentinel1_wind.py` | `test_sentinel1_wind.py` |
| F-SAT-07 | SWOT:s vattenytehöjder för sjöar och vattendrag, med osäkra mätningar markerade | V | `swot.py`, `swot.js` | `test_swot.py` |
| F-SAT-08 | Copernicus EMS:s kartlagda brandperimetrar | V | `ems.py`, `ems.js` | `test_ems.py` |
| F-SAT-09 | Satellitbanor och positioner (SGP4 ur Space-Track-banelement), passager över händelsen, satellitens position vid varje bild | B | `satellites.py`, `passes.py`, `scene_satellites.py`, `orbits.js` | `test_passes.py`, `test_satellite_passes.py`, `test_scene_satellites.py` |
| F-SAT-10 | Satellitmonitor: världskarta med banor och tidslinje över passager | B | `satmonitor.js`, `monitor.js` | `test_satmonitor.py` |
| F-SAT-11 | Strandlinjer år för år ur Sentinel-2 (Falsterbo) | B | `shorelines.py`, `shorelines.js`, `tools/derive_shorelines.py` | `test_shorelines.py` |

## D. Väder och hydrologi

| ID | Funktion | Märkning | Moduler | Tester |
|---|---|---|---|---|
| F-WX-01 | Timnederbörd från SMHI och kommunala mätare, omräknad till UTC där stationen anger lokal tid | V | `/api/weather`, `rain.js`, `tools/fetch_smhi_weather.py` | `test_rain.py`, `test_fetch_smhi_weather.py`, `test_weather_chart.py` |
| F-WX-02 | Dygnsnederbörd från SMHI | V | `daily_rain.py` | `test_daily_rain.py` |
| F-WX-03 | SMHI:s väderradar som regnbilder | V | `radar.py` | `test_radar.py` |
| F-WX-04 | SMHI:s observerade blixtar | V | `lightning.py` | `test_lightning.py` |
| F-WX-05 | Vindpilar från ERA5-Land och ERA5 över havet | M | `/api/wind`, `wind_barbs.js` | `test_wind_barbs.py`, `test_fetch_era5_land.py`, `test_sea_wind.py` |
| F-WX-06 | MET Norways prognoser som de utfärdades vid scenarioklockan | M | `met_forecast.py`, `met_forecast.js` | `test_met_forecast.py`, `test_met_forecast_screens.py` |
| F-WX-07 | SMHI:s uppmätta flöden och sjönivåer, med jämförelse mot högsta uppmätta | V | `hydro.py`, `hydro.js` | `test_hydro.py` |
| F-WX-08 | EFAS flödesprognoser som de utfärdades | M | `efas.py` | `test_efas.py` |
| F-WX-09 | Havsvattenstånd från SMHI | V | `tools/fetch_smhi_sea_level.py` | `test_fetch_smhi_sea_level.py` |
| F-WX-10 | Isobarer och väderdiagram | M | `tools/isobars.py`, `tools/weather_chart.py` | `test_isobars.py`, `test_weather_chart.py` |

## E. IoT och sensorer

| ID | Funktion | Märkning | Moduler | Tester |
|---|---|---|---|---|
| F-IOT-01 | Mottagning av IoT-noder över MQTT (TEMP, WATER, AIR, NTN), med status för noder som tystnat | S i dag | `iot.py`, `tools/mqtt_node_sim.py` | `test_iot.py`, `test_mqtt_node_sim.py` |
| F-IOT-02 | Syntetiska sensorer i brandområdet, beräknade ur branden och vädret | S | `sensor_sim.py` | `test_sensor_sim.py` |
| F-IOT-03 | Syntetiska bräddgivare vid kommunens kritiska dagvattenpunkter, i formen av diwise `Sewer` | S | `flood_sensors.py` | `test_flood.py` |
| F-IOT-04 | Syntetiska nivåsensorer där vägar korsar ett vattendrags 100-årsflöde, drivna av SMHI:s mätningar | S | `level_sensors.py` | `test_flood.py` |
| F-IOT-05 | Sensorer som operatören placerar på kartan (högst 10) | S | `scenario_engine.py` (`place_sensor`) | `test_mission_control.py`, `test_scenario_engine.py` |

## F. Analys och bedömning

| ID | Funktion | Märkning | Moduler | Tester |
|---|---|---|---|---|
| F-AN-01 | Spårbar brandbedömning: en lista med belägg, var och en kopplad till ett objekt på kartan, och en regelbaserad poäng med fasta, påhittade vikter | B | `assessment.py` | `test_assessment.py` |
| F-AN-02 | Spårbar översvämningsbedömning i samma format: regn, syntetiska sensorer, skyfallsmodell och satellitbilder | B | `flood_assessment.py` | `test_flood.py`, `test_upstream_rain.py` |
| F-AN-03 | Upptäcktssekvens från rymden: verklig passage och detektioner, regelbaserad klassning, syntetiska steg märkta SYNTETISKT | V/B/S | `detection.py`, `flood_assessment.py` | `test_detection.py` |
| F-AN-04 | Brandspridningsprognos per satellitpassage (FWI, FBP C-2), med ensemble och efterhandsprövning | B | `forecast.py`, `tools/fire_spread*.py`, `tools/fire_ensemble*.py` | `test_forecast.py`, `test_fire_spread.py`, `test_fire_ensemble.py`, `test_fire_ensemble_hindcast.py`, `test_fire_spread_analysis.py` |
| F-AN-05 | Hotad bebyggelse: orter som hotas inom prognosens horisont, markerade på kartan | B | `/api/threats`, `spatial.py`, `satlog.js` | `test_spatial.py`, `test_satlog.py` |
| F-AN-06 | Damm som ett markerat "om": byggnader längs vattendraget nedströms, ingen dammbrottsmodell | B | `dam.py` | `test_dam.py` |
| F-AN-07 | Vägar och järnvägar: rapporterade skador (dokumenterade) och sträckor under kraftigt regn (beräknade) | V/B | `routes.py`, `routes.js` | `test_routes.py` |
| F-AN-08 | Färdiga rumsliga frågor mot PostGIS, bara valbara efter ID, aldrig fri SQL. Till exempel "Varför tror du att det brinner?", infrastruktur inom 5 km, närmaste by, byggnader och vägar inom översvämningsytan | B | `spatial.py`, `/api/questions`, `/api/ask`, `tools/load_postgis.py` | `test_spatial.py`, `test_load_postgis.py`, `test_postgres.py` |

## G. Uppdragsstyrning och händelser

| ID | Funktion | Märkning | Moduler | Tester |
|---|---|---|---|---|
| F-MC-01 | Mission control: styr klockan, bilder, baskartor, lager, vyer, profil och händelser för alla skärmar | – | `control.js`, `/api/scenario/command` | `test_mission_control.py` |
| F-MC-02 | Operatörens händelser: satellitdetektion, sensorfel, satellitavbrott och återställning, stängd väg, strömavbrott, +60 MIN, IoT | S | `scenario_engine.py` (`EVENT_KINDS`), `scenario_events.js` | `test_mission_control.py`, `test_satcom_outage.py` |
| F-MC-03 | Valfri token för kommandon när mission control körs över nätverk (`SCENARIO_CONTROL_TOKEN`) | – | `server.py` | `test_mission_control.py` |

## H. Kommunikation till publik och operatör

| ID | Funktion | Märkning | Moduler | Tester |
|---|---|---|---|---|
| F-COM-01 | Logg över satellit- och IoT-händelser, byggd ur klockan så att den blir densamma efter reset eller hopp | V/B/S | `satlog.js` | `test_satlog.py` |
| F-COM-02 | Uppläsning av nya logglinjer på svenska med Piper offline (rösten "alma"), med uttalsregler för tal, förkortningar och ord | – | `speech.py`, `wav_player.py` | `test_speech.py` |
| F-COM-03 | Bildtexter och märkning av verkligt, beräknat och simulerat på skärmarna | – | `panel.js`, `sensors.js`, `scenario_events.js` | `test_view_caption.py`, `test_satlog.py` |

## I. Drift och installation

| ID | Funktion | Märkning | Moduler | Tester |
|---|---|---|---|---|
| F-OPS-01 | Start med scenariomeny, kontroll före start och öppning av skärmar på rätt bildskärm | – | `tools/start_demo.py`, `tools/startup_check.py`, `tools/open_screens.py`, `tools/windows_screens.py` | `test_start_demo.py`, `test_startup_check.py`, `test_open_screens.py` |
| F-OPS-02 | Automatisk kontroll av ett scenario i webbläsare (`check_demo`) och inspelning av demon | – | `tools/check_demo.py`, `tools/record_demo.py` | `test_check_demo.py`, `test_record_demo.py` |
| F-OPS-03 | Tjänster i Docker (PostGIS, tileserver, Mosquitto) eller lokalt installerade på Windows | – | `docker-compose.yml`, `tools/native_services.py`, `tools/start_native_*.py`, `postgres.py` | `test_native_services.py`, `test_start_native_mqtt.py`, `test_start_native_tiles.py` |
| F-OPS-04 | Datapaket med kontrollsummor, installation från paket, hämtning per scenario | – | `tools/package_data.py`, `tools/install_data.py`, `tools/fetch_scenario.py` | `test_package_data.py`, `test_install_data.py`, `test_fetch_scenario.py` |
| F-OPS-05 | Datainhämtning från respektive källa, med inloggningar utanför repot | – | `tools/fetch_*.py` (omkring 30 verktyg) | `test_fetch_*.py` |

## Begränsningar som redan är kända

Underlag för MVP-beskrivningens kapitel om begränsningar. Varje punkt har stöd i koden,
operatörsguiden eller `CONTEXT.md`.

- **Inget är live.** Alla data spelas upp i efterhand. Ingen funktion tar emot
  realtidsdata från satelliter eller väder.
- **Poängen är inte en sannolikhet.** Bedömningarna (F-AN-01, F-AN-02) använder fasta vikter
  som är påhittade för demon. Ingen modellprestanda är validerad.
- **Sensorerna är syntetiska.** IoT-noderna körs simulerade sedan beslutet 2026-10-04. Det
  finns ingen firmware och ingen skyddad MQTT-exponering för riktiga noder.
- **Vattenmasker och vattentröskel är enkla.** Sentinel-1:s tröskel är inte en kartlagd
  översvämning och missar översvämning i bebyggelse och skog (Västerås 2023).
- **Modeller visar vad som kan hända, inte vad som hände.** Det gäller skyfallsmodeller,
  MCF:s karteringar, ERA5 och EFAS.
- **En användare och en dator.** Det finns ingen inloggning eller behörighetsstyrning. Det
  enda skyddet är en valfri token för kommandon, och backend kör ett scenario i taget.
- **Plattformar.** Ubuntu är verifierat. Windows utan Docker är provat i en VM men delvis
  oåtgärdat. macOS stöds inte.
- **Datarättigheter.** Sundsvalls och Kramfors kommuners lager används med medgivande.
  Västerås stads data får bara användas internt. Hur Sundsvalls kommun vill bli krediterad är
  oklart. Se `reports/2026-10-30-kreditering-utanfor-kartbilden-claude-opus-5-5.md`.
- **Partnernamn och elnät.** Dacreo och BruhnBruhn nämns inte, och elnätet från OSM visas
  inte, förrän beslut B3 är fattat.

## Öppet inför MVP-beslutet

- Vilken händelsetyp och vilket scenario MVP:n utgår ifrån. Det är en öppen fråga i
  `CONTEXT.md` och avgörs efter beställarens nya one-pager.
- Vilka funktioner ovan som är kärna, vilka som är stöd och vilka som stryks.
- Vilka källor som får användas utanför intern visning.
