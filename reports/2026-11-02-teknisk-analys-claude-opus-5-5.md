# Teknisk analys av demonstratorn: brister, motsägelser och luckor

Claude Opus 5.5, 2026-11-02. Användaren bad om en analys av den nuvarande implementationen
med avseende på tekniska brister, motsägelser och luckor, och om samma analys av
dokumentationen och testerna. Analysen gjordes mot `main` på `aee7ce0` av fem granskare med
läsbehörighet. Var och en hade ett område: backend, frontend, tools och drift, dokumentation
mot kod, och tester. Inga filer ändrades. Fem av de allvarligaste fynden har kontrollerats
en andra gång direkt i koden: B-01, B-02, F-01, T-01 och `/api/speak` i B-02. Övriga fynd
bygger på granskarnas läsning av koden och är inte omprövade. Radnumren kan avvika med någon
rad.

Kända begränsningar i `docs/mvp/funktionskatalog.md` ("Begränsningar som redan är kända")
tas inte upp igen, utom där koden motsäger dem.

Varje fynd har ett ID för vidare spårning. Prefixet anger området: `B` för backend, `F` för
frontend, `T` för tools och drift, `D` för dokumentation och `Q` för tester. Allvarlighet:
**Hög**, **Medel** eller **Låg**. Typ: **brist**, **motsägelse** eller **lucka**.

## Sammanfattning

- **Testsviten är grön:** 802 tester passerade, 0 misslyckades och 3 hoppades över, på
  139 sekunder.
- **Skyddet mot vanliga angrepp är gott.** Det gäller sökvägar, SQL och WMS-proxyn (SSRF),
  liksom inloggningsuppgifterna.
- **Det finns en säkerhetslucka via webbläsaren på demodatorn** (B-02). Dessutom sätter
  2D-kartan in texter från OSM och PostGIS som rå HTML (F-01).
- **Händelselistans tak på 100 händelser kan ändra demons läge** (B-01).
- **IoT-mätvärden visas som "live" om flaggan `simulated` saknas** (B-03). Det strider mot
  projektregeln om märkning.
- **Hämtning av data kan ge trasiga filer som räknas som klara** (T-01–T-04).
- **Två tester kan påverka en demo som körs:** ett tömmer den riktiga databasen och ett
  startar en egen container (Q-01, Q-02).
- **Dokumentationen har halkat efter koden:** antal scenarier, borttagna grenar, mässan och
  gjort arbete som står som ogjort (D-01–D-12).

**Under analysen:** testgranskaren körde hela sviten. Testet `tests/test_iot.py` startade då
en egen Mosquitto-container. Granskaren stoppade den och körde om utan Docker. Efteråt körde
inga containrar. De delade tjänsterna var redan stoppade och berördes inte.

## Översikt

| ID | Allvarlighet | Typ | Kort |
|---|---|---|---|
| B-01 | Medel | brist | Läget räknas ur de senaste 100 händelserna |
| B-02 | Medel | brist | Kommandon kan skickas från vilken webbsida som helst i demodatorns webbläsare |
| B-03 | Medel | motsägelse | IoT-mätvärden räknas som verkliga om flaggan saknas |
| F-01 | Medel | motsägelse | 2D sätter in texter från OSM och PostGIS som rå HTML, 3D escapar dem |
| T-01 | Hög | brist | Återupptagen nedladdning kan skarva två filversioner eller acceptera en avkortad fil |
| Q-01 | Hög | brist | `test_load_postgis` tömmer och laddar om demons databas |
| Q-02 | Hög | brist | `test_iot` startar en Docker-container vid en vanlig testkörning |
| Övriga | Medel–Låg | | Se avsnitten nedan |

## Backend (`app/backend/`)

**B-01 · Medel · brist · `scenario_engine.py:384`, `307`, `393`**
- **Vad:** motorn behåller bara de senaste 100 händelserna (`del self.events[:-MAX_EVENTS]`),
  men `_status()` räknar fram läget ur listan. Läget omfattar SATCOM, växlarna GOD VIEW,
  +60 MIN och SPACE VIEW, IoT av och på, trasiga sensorer och placerade sensorer. Även
  gränsen på 10 placerade sensorer räknas ur listan.
- **Felscenario:** operatören trycker SATCOM FAILURE och gör sedan ungefär 100 andra
  kommandon utan RESET. Då blir SATCOM uppe igen, trasiga sensorer blir hela och en växel
  kan slå om. Placerade sensorer försvinner, gränsen slutar gälla och id:n `placed-N`
  återanvänds.

**B-02 · Medel · brist (säkerhet) · `server.py:896–908`, `974–986`**
- **Vad:** `POST` läser JSON oavsett Content-Type och kontrollerar varken Origin eller Host.
  Kommandotoken är valfri. `/api/speak` kontrollerar bara att anropet kommer från
  127.0.0.1, vilket en webbläsare på samma dator alltid gör.
- **Felscenario:** en sida som öppnas i webbläsaren på demodatorn kan skicka
  `fetch('http://127.0.0.1:8765/api/demo/menu', {method: 'POST', mode: 'no-cors', body: '{}'})`.
  Den kan på samma sätt stoppa backend, återställa demon eller få högtalarna att läsa upp
  valfri text.
- **Skillnad mot den kända begränsningen:** den gäller inloggning över nätverk. Det här är en
  väg in via den lokala webbläsaren.

**B-03 · Medel · motsägelse · `iot.py:108`, `app/frontend/sensors.js:24`**
- **Vad:** `"real": not simulated`, där `simulated` som standard är falsk. Ett meddelande
  utan flaggan visas som en verklig nod, märkt "live".
- **Felscenario:** ett testskript eller en äldre simulator som publicerar på
  `techseed/<nod>/<typ>` utan flaggan visas som en verklig mätning på skärmarna. Det strider
  mot regeln att simulerade data aldrig visas som live. Sedan beslutet 2026-10-04 är alla
  noder simulerade.

**B-04 · Låg · brist · `server.py:382–383`, död kod vid `772` och `806`, `scenario_engine.parse_utc`**
- **Vad:** `fromisoformat(...).astimezone(timezone.utc)` tolkar en tid utan tidszon som
  datorns lokala tid. Grenen som ska sätta UTC kan aldrig nås.
- **Felscenario:** `/api/lightning?at=2018-07-15T12:00:00` ger blixtarna från två timmar
  tidigare med svensk sommartid. Samma sak gäller `seek` och uppspelningsfönstret.

**B-05 · Låg · motsägelse · `lantmateriet.py:88–95`**
- **Vad:** proxyn begränsar inte `LAYERS` till `LM_FASTIGHET_LAYERS`. `wms.get_map`
  (`wms.py:110`) gör det. Topowebbens z/x/y kontrolleras inte heller mot sina gränser.
- **Felscenario:** en skärm i nätet kan hämta vilket lager som helst i tjänsten med
  serverns inloggning.

**B-06 · Låg · brist · `lantmateriet.py:78`**
- **Vad:** proxyn fångar bara `URLError` och `TimeoutError`, inte `OSError` som
  `wms.py:62` gör.
- **Felscenario:** om anslutningen bryts under läsningen får webbläsaren inget svar.

**B-07 · Låg · brist · `spatial.py:222–223`**
- **Vad:** `Psql.query` väntar på `readline()` utan timeout och håller samtidigt ett lås.
- **Felscenario:** om PostGIS eller `docker exec` hänger sig blir alla senare anrop till
  `/api/ask` och `/api/threats` stående, och var och en håller en servertråd.

**B-08 · Låg · brist · `profiles.py:35–40`, `101`**
- **Vad:** en oläsbar `display-profiles.json` läses som `{}` och skrivs sedan tillbaka med
  bara det aktuella scenariot.
- **Felscenario:** SPARA PROFIL raderar tyst de andra 15 scenariernas profiler.

**B-09 · Låg · lucka · `scenario.py:53–58`, `scenarios/falsterbo.py`**
- **Vad:** Falsterbo saknar `CHECK_*` och `SENTINEL1_ACQUISITIONS`. Scenariot ärver därför
  `CHECK_OUTCOME = "Wildfire probable"`, och `flood_rain_and_sensors` gör `seek` utan tid.
- **Felscenario:** `check_demo` för Falsterbo misslyckas. `CONTEXT.md` säger att kontrollen
  gäller alla scenarier.

**B-10 · Låg · lucka · `server.py:874–894`**
- **Vad:** `/api/stream` används bara av tester och går förbi den gemensamma motorn.
  Parametern `from` saknar nedre gräns.
- **Felscenario:** `from=1900-01-01T00:00:00Z` håller en tråd strömmande i praktiken utan
  slut. Modulens docstring beskriver den fortfarande som gränssnittets ström.

**B-11 · Låg · motsägelse · `scenario.py:171`, `199`, `212–213`**
- **Vad:** kommentarer säger "only Kårböle 2018", "only Sundsvall 2026" och "only
  Västernorrland 2025". Fjorton, fem respektive nio scenarier använder nu funktionerna. Fem
  valfria nycklar används inte av något scenario: `UPSTREAM_RAIN_NOTICE_MM`,
  `SWOT_BASELINE_DAYS`, `RADAR_ANALYSIS_BBOX`, `ROAD_OVERLAY` och `MUNICIPAL_BASEMAP_BBOX`.

**B-12 · Låg · brist · `speech.py:206–215`**
- **Vad:** listan `spoken`, som finns för testernas skull, växer för varje uppläst rad.
  Rader med `keep=True` går förbi taket `MAX_QUEUED`.
- **Felscenario:** minnet växer under lång kioskdrift.

**Kontrollerat och OK:**
- Sökvägar (`resolve()` och `is_relative_to`), z/x/y för kommunkartan och offline-tiles.
- WMS-proxyn: fast uppströmsadress, bara GetMap och listade lager.
- SQL: frågor väljs efter id, och sensornamn citeras.
- Validering av kommandon.
- Märkning av syntetiska sensorer, bedömningen och SATCOM-avbrottet.
- Inloggningsuppgifter från miljön.
- Att alla 16 scenarier har de obligatoriska nycklarna.
- Händelsernas sekvensnummer över RESET.
- Mosquitto bunden till 127.0.0.1.

## Frontend (`app/frontend/`)

**F-01 · Medel · motsägelse (XSS) · `map2d.js:190–191`, `716`, `807`**
- **Vad:** 2D sätter in OSM:s `name` och `osm_tag`, ortsnamnen i prognosen och
  frågeetiketter med PostGIS-namn som rå HTML via Leaflets `bindPopup` och `bindTooltip`.
  3D escapar samma fält (`map3d.js:1310–1311`, `870`, `972`).
- **Felscenario:** ett OSM-objekt som heter `<img src=x onerror=...>` och kommer med i en
  hämtning kör skript på huvudskärmen i 2D.

**F-02 · Medel · brist · `panel.js:55`, `1386–1388`**
- **Vad:** `state.flashedPasses` töms aldrig.
- **Felscenario:** efter RESET, ett hopp bakåt eller ett varv i kiosken visas linjen och
  etiketten från satelliten till branden i 3D aldrig igen.

**F-03 · Medel · brist · `panel.js:1870–1885`, `1709–1716`**
- **Vad:** `askQuestion` saknar kontroll av om svaret fortfarande gäller, till skillnad från
  prognos, blixtar och Meteosat.
- **Felscenario:** operatören trycker RENSA SVARET medan PostGIS arbetar. Det sena svaret
  ritas ändå, och 2D-kartan flyger till det. Två snabba frågor kan också visas i fel ordning.

**F-04 · Låg · lucka · `monitor.js:40`, `228`**
- **Vad:** vid ett avbrott ersätts källkrediteringen, som också innehåller rösten alma
  (CC BY 4.0), med "Anslutningen till backend bröts". Krediteringen skrivs aldrig tillbaka.
- **Felscenario:** efter en kort omstart av backend saknar satellitmonitorn kreditering
  resten av körningen.

**F-05 · Låg · brist · `control.js:626–658`**
- **Vad:** `fetch("/api/config")` slutar i `.catch(() => {})` och försöker aldrig igen.
- **Felscenario:** listorna i mission control blir tomma, start-RESET körs aldrig och
  operatören ser inget fel.

**F-06 · Låg · brist · `panel.js:1544–1563`**
- **Vad:** `detectionKey` sätts före anropet till `/api/detection`.
- **Felscenario:** om anropet misslyckas en gång döljs detektionskortet för det steget tills
  operatören trycker NÄSTA.

B-03 gäller också frontend (`sensors.js:24`).

**Kontrollerat och OK:**
- 2D och 3D har samma metoder.
- Händelsenamnen stämmer mot backend.
- Fälten i `/api/met-forecast`, `/api/lightning` och `/api/ask` stämmer.
- Inaktuella svar kastas för prognos, blixtar och Meteosat.
- Alla datalager krediteras i båda vyerna.
- Syntetiska data är märkta i båda vyerna.
- Sammanfattning, slutbild och bedömning sätts med `textContent`.
- Inga läckande timers.
- `lang="sv"`, `aria-live` och `aria-pressed` finns.

## Tools och drift (`tools/`, `docker-compose.yml`)

**T-01 · Hög · brist · `fetch_scenario.py:357–369`**
- **Vad:** nedladdningen av OSM-extraktet och vattenpolygonerna återupptas med
  `Range: bytes=N-` utan `If-Range` eller ETag. Den kontrollerar varken Content-Length eller
  hash före `replace`. `HTTPResponse.read(amt)` ger tomt svar vid avbrott i stället för ett
  fel.
- **Felscenario:** `sweden-latest.osm.pbf` (930 MB) byggs om varje dag. En nedladdning som
  avbryts en dag och återupptas nästa skarvar två versioner. Ett tappat nätverk ger en
  avkortad fil. I båda fallen räknas steget som klart, `build_offline_tiles` misslyckas eller
  bygger en trasig karta, och nya körningar hoppar över steget utan `--force`.

**T-02 · Medel · brist · `fetch_copernicus_dem.py:59–68`**
- **Vad:** samma avkortning utan kontroll som i T-01. SHA-256 räknas på det som kom fram.
- **Felscenario:** källinformationen intygar en avkortad GeoTIFF som giltig.

**T-03 · Medel · brist · `fetch_municipal_basemap.py:158`, `168–170`**
- **Vad:** tiles skrivs direkt till sin slutliga plats, och återupptagningen hoppar över
  filer som finns. Samma fil skriver atomiskt på ett annat ställe (`124–126`).
- **Felscenario:** Ctrl+C under den två–tre timmar långa hämtningen lämnar en avkortad PNG
  som aldrig hämtas igen.

**T-04 · Medel · brist · `fetch_scenario.py:137–140`, `fetch_web_vendor.py:52–66`, `fetch_piper_voices.py:54–58`**
- **Vad:** filen som markerar att ett steg är klart bevisar inte att steget blev klart. För
  webbiblioteken är markören `Cesium.js`, men satellite.js packas upp efter den. Rösten
  skrivs inte atomiskt, och hashen kontrolleras i minnet, inte på disk.
- **Felscenario:** ett avbrott lämnar ett ofullständigt bibliotek eller en ofullständig
  `.onnx`, och `fetch_scenario` säger "klart, hoppas över".

**T-05 · Medel · lucka · `docker-compose.yml:31`, `build_offline_tiles.py:50`, `53`, `76`, `build_terrain.py:34`, `fetch_landsat_scene.py:63`**
- **Vad:** imagarna har rörliga taggar: `tileserver-gl:latest`, `tilemaker:master`,
  `ctb-quantized-mesh:latest` och `debian:stable-slim` med `apt-get install` vid varje
  bygge. Python-paketen är däremot exakt låsta. SOURCE.json sparar taggen, inte digesten.
- **Felscenario:** en ny `master` ändrar tile-schemat och bryter `techseed.json` vid nästa
  rena installation, och det tidigare resultatet går inte att återskapa.

**T-06 · Låg · motsägelse · `fetch_scenario.py:254–255`, `requirements-era5.txt:1`**
- **Vad:** stegen för Sentinel-1-vind deklarerar inga paket men importerar numpy.
  `requirements-era5.txt` säger att den bara gäller ERA5-Land, men `netCDF4` behövs också av
  `fetch_era5_sea` och `fetch_met_forecasts`.
- **Felscenario:** kontrollen före start visar att inget saknas, och steget kraschar med
  ImportError.

**T-07 · Låg · motsägelse · `build_offline_tiles.py:71`, `build_terrain.py:39`**
- **Vad:** `os.getuid()` anropas utan skydd. `derive_dam_exposure.py:42` skyddar anropet.
- **Felscenario:** `--tools docker` på Windows ger AttributeError.

**T-08 · Låg · lucka · `package_data.py`, `fetch_municipal_features.py:89–95`**
- **Vad:** villkoret att Västerås data bara får användas internt (`permission` i
  SOURCE.json) läses inte vid paketering. Kommunens objekt har inget sådant fält.
- **Felscenario:** ett paket med Västerås tiles kan installeras någon annanstans utan
  varning.

**T-09 · Låg · lucka:** `fetch_mcf_flood_maps.py` och `fetch_municipal_features.py` saknar
tester. Se också Q-08.

**T-10 · Låg · brist · `tools/start_demo.py:152–170`** (upptäckt under AP2)
- **Vad:** scenariomenyns server (`/api/demo/start`) läser JSON oavsett Content-Type och
  kontrollerar inte Origin, alltså samma lucka som B-02 hade.
- **Felscenario:** medan menyn visas kan en annan webbsida i webbläsaren på demodatorn välja
  och starta ett scenario.

**Kontrollerat och OK:**
- `install_data` och `package_data`: sökvägar, manifest, storlek och SHA-256 före skrivning,
  ingen överskrivning. En kopiering som avbryts halvvägs måste dock städas för hand.
- Uppackning av arkiv.
- Inget `shell=True`.
- Inloggningsuppgifter utanför repot, aldrig loggade. Landsat-token tas bort ur felmeddelanden.
- Inga hårdkodade hemkataloger.
- Portar och databasnamn stämmer mellan compose och kod.
- Flaggorna i dokumentationen stämmer mot argparse.
- Alla nätverksanrop har timeout.
- Python-paketen är exakt låsta, och röster och webbibliotek har låsta hashar.

## Dokumentation

**D-01 · Hög · motsägelse · `app/README.md:1–3`, `61–66`**
- **Vad:** rubriken lyder "Fire map: Västmanland 2014" och texten "Exhibition prototype". Där
  står att scenarierna är `vastmanland2014` och `sundsvall2026`, och att Sundsvalls skärmar
  inte är byggda.
- **Hur det faktiskt är:** `scenarios/__init__.py:16` har 16 scenarier, och Sundsvall är
  byggt.

**D-02 · Hög · inaktuell · `docs/operatorsguide.md:79–82`**
- **Vad:** guiden säger att arbetet ligger på `cross-platform-installation`, och att en klon
  av `main` inte nödvändigtvis har det.
- **Hur det faktiskt är:** grenen finns inte. Den är mergad i `0e5a125`, och verktygen finns
  på `main`.

**D-03 · Medel · lucka · `docs/operatorsguide.md:248–250`, `514–525`, `527`**
- **Vad:** scenariolistan och databastabellen nämner 10 av 16 scenarier. Sex scenarier
  saknar eget avsnitt: `kramfors2026`, de fyra Flen-scenarierna och `sundsvall-nov2023`.
  `sundsvall-nov2023` nämns inte alls, fast startmenyn visar det. Databasnamn som avviker,
  till exempel `sundsvall-dec2020`, som använder `sundsvall-nov2023`, står inte i guiden.

**D-04 · Medel · inaktuell · `CONTEXT.md:32`, `45`, `47–48`**
- **Vad:** `fix-windows-meteosat-dependencies` och `record-source-metadata` beskrivs som
  omergade eller pågående. Båda är mergade i `main`. Handoffens rubrik säger
  "(2026-10-24)".

**D-05 · Medel · inaktuell · `CONTEXT.md`, Backlog**
- **Vad:** "Planned 2026-10-21, not implemented: scenario-selective data acquisition".
- **Hur det faktiskt är:** `tools/fetch_scenario.py` finns och används 14 gånger i guiden.
  Vilka steg i planen som återstår står inte.

**D-06 · Medel · inaktuell · `docs/operatorsguide.md:1–4`, `953`, `957`**
- **Vad:** titeln lyder "brandkartan på IoTDagen", och texten talar om "montern" och "På
  mässdagen".
- **Hur det faktiskt är:** mässan är över, demon används internt, och 13 av 16 scenarier är
  översvämningar.

**D-07 · Medel · motsägelse · `docs/mvp/funktionskatalog.md`, kända begränsningar**
- **Vad:** katalogen säger att Sundsvalls och Kramfors kommuners lager används med
  medgivande.
- **Hur det faktiskt är:** Kramfors kommun hade inga egna lager i tjänsten (`CONTEXT.md:25`),
  och `kramfors2026.py` använder bara MCF:s WMS.

**D-08 · Låg · motsägelse · `app/README.md:145`**
- **Vad:** README säger att rösterna är "nst" och "alma".
- **Hur det faktiskt är:** `speech.py:5` och katalogen säger bara "alma".

**D-09 · Låg · lucka · `app/README.md:140–155`**
- **Vad:** tabellen över mission control saknar BYT SCENARIO, STARTA OM DEMO, AUTOSLINGA,
  VISA 2D, IOT PÅ/AV, NÄSTA och RENSA SVARET. Filtren beskrivs som knappar men är kryssrutor
  under "Kartans lager".

**D-10 · Låg · lucka · `README.md:3`, `11`**
- **Vad:** README beskriver projektet som konceptarbete för IoTDagen och `app/` som en
  brandkarta för Västmanland. Innehållslistan saknar `docs/mvp/` och `data/`.

**D-11 · Låg · lucka · `onepager.md`**
- **Vad:** one-pagern beskriver en LLM/AI-agent och "GIS-query från AI" som något som ska
  byggas på riktigt. Det byggda systemet har förberedda frågor som väljs efter id och ingen
  språkmodell. Avvikelsen står bara indirekt i `regelverksregister.md`.

**D-12 · Låg · inaktuell · `docs/mvp/regelverksregister.md:3`, `32`**
- **Vad:** dokumentet säger att utkastet ligger på grenen `mvp-regelverksregister`, som är
  borttagen. Det skriver "Sex poster" men räknar upp sju, inklusive R-AI-01.

**Kontrollerat och stämmer:**
- Alla `python -m tools.*` med flaggor i guiden och README.
- Alla `/api/...` i dokumentationen.
- Serverns flaggor och miljövariabler, och portarna.
- Katalogens 16 scenarier och 709 testfunktioner i 92 filer.
- Alla F-id i kravmallen och registret.
- Scenariotitlar och starttider i guiden.
- Knappnamnen i guiden.
- Märkningen V/M/B/S i katalogen och guiden.

## Tester (`tests/`)

**Körning:**
- **Med data:** `.venv/bin/python -m pytest -q -p no:cacheprovider` gav 802 passerade,
  0 misslyckade, 3 överhoppade och 3 varningar om att Pillows `getdata` är föråldrad.
  Överhoppade var `test_load_postgis.py:35` och `test_spatial.py:147`, där PostGIS inte
  körde, och `test_iot.py:230`, där brokern blockerades, se Q-02. Inget test behöver
  internet, utom att `docker run` kan hämta imagen.
- **Utan data:** en körning på en kopia från `git archive` gav 794 passerade,
  9 överhoppade och 2 misslyckade, se Q-03.

**Q-01 · Hög · brist · `test_load_postgis.py:35–41`**
- **Vad:** om den delade PostGIS-tjänsten körs, kör testet `load_postgis.main([])`. Det tar
  bort och laddar om tabellerna i databasen `firemap`, som är demons databas för
  Västmanland. Testet förväntar sig dessutom antal som beror på oversionerade data.
- **Felscenario:** en demo som körs tappar sina tabeller mitt i en fråga.

**Q-02 · Hög · brist · `test_iot.py:207`**
- **Vad:** fixturen `own_broker` kör `docker run -d --rm … eclipse-mosquitto:2` när
  `docker` finns i PATH, utan att någon har valt det.
- **Felscenario:** en vanlig testkörning startar en container, och kanske en
  image-hämtning. Det inträffade under analysen.

**Q-03 · Medel · brist · `test_passes.py:27–33`, `test_natural_earth.py:51–52`**
- **Vad:** testerna läser webbibliotek som inte är versionerade, utan `skipif`.
  `test_satellite_passes.py:143` gör rätt.
- **Felscenario:** på en ny klon misslyckas de med `FileNotFoundError` och `assert 0 == 32`.

**Q-04 · Medel · kvalitet · `test_flood.py:224`, `227`, `295`, `test_basemaps.py:116–117`**
- **Vad:** när `data/` saknas passerar testerna, men kontrollerna som beror på data hoppas
  tyst över. Det sker med `if exists:` eller genom att testet godtar båda utfallen.
  `test_flood.py:227` godtar fyra historiska värden.

**Q-05 · Medel · lucka · `panel.js`, `map2d.js`, `control.js`, `app.js`, `app3d.js`**
- **Vad:** filerna körs aldrig i något test. Ett 70-tal kontroller söker bara efter
  textsträngar i källkoden, till exempel `test_scenario.py:229` och
  `test_chart_clock.py:33–40`. Övrig JS körs i Node.

**Q-06 · Medel · lucka/motsägelse · `server.py:904`, katalogens F-MC-03**
- **Vad:** kontrollen av `SCENARIO_CONTROL_TOKEN` testas inte. Katalogen anger
  `test_mission_control.py`, som aldrig nämner token, och alla serverfixturer sätter
  `"control_token": None`.
- **Rättat 2026-11-02:** fyndet var fel om testet. Fixturen i `test_scenario_engine.py` sätter
  `"control_token": "secret"`, och `test_commands_need_the_token_and_change_the_shared_state`
  kontrollerar att ett kommando utan token ger 403. Det som stämmer är att katalogens F-MC-03
  pekar på fel testfil. Det rättas i AP8.

**Q-07 · Medel · lucka · `scenario_engine.py:394`, katalogens F-IOT-05**
- **Vad:** gränsen på 10 placerade sensorer testas inte. `test_scenario_engine.py:408`
  placerar två.
- **Rättat 2026-11-02:** fyndet var fel. Gränsen testas i
  `test_placed_sensors_are_numbered_inside_the_area_and_cleared_by_reset`.

**Q-08 · Låg · lucka:** `fetch_mcf_flood_maps.py` och `fetch_municipal_features.py` har inga
tester. Katalogen täcker dem bara med mönstret `test_fetch_*.py`.

**Q-09 · Låg · lucka · `docs/mvp/funktionskatalog.md`**
- **Vad:** sex testfiler saknar koppling till någon funktion: `test_browsers`,
  `test_cancelled_requests`, `test_derive_impact_sensor_points`, `test_geo_tools`,
  `test_osm_waterways` och `test_read_vattenwebb`. Alla filnamn i katalogen finns.

**Q-10 · Låg · kvalitet · `test_cancelled_requests.py:45`**
- **Vad:** testet gör `time.sleep(1.0)` och sedan `assert errors == []`. Ett fel som kommer
  senare än så märks inte på en långsam dator.

**Q-11 · Låg · kvalitet · `test_derive_impact_sensor_points.py:37`**
- **Vad:** testet kontrollerar bara att `derived_utc <= now()`. En fast tid skulle också
  passera.

**Q-12 · Låg · kvalitet**
- **Dubbletter:** `postgis_running()` finns i två versioner med olika innebörd
  (`test_load_postgis.py:17`, `test_spatial.py:140`). Fixturerna `node()` och `base_url` är
  kopierade i ett tiotal filer.
- **Inaktuellt:** `CONTEXT.md` säger fortfarande "360 tests passed".
- **Delvis rättat 2026-11-02:** "360 tests passed" är daterade verifieringar, inte inaktuella
  uppgifter.

**Bra:**
- Sviten är grön och snabb.
- Alla tester har kontroller.
- `conftest.py` skyddar den sparade visningsprofilen.
- Scenarierna körs i egna processer, så ordningen spelar ingen roll.
- Hämtverktygen testas mot stubbar, också hanteringen av inloggningsuppgifter.
- JS testas i Node i stället för som kopior i Python.
- Kanterna i paketeringen är väl testade.
- Alla 16 scenarier körs minst en gång.

## Förslag till ordning

Detta är förslag. Inget är beslutat.

1. **Det som kan skada en körande demo eller data:** Q-01, Q-02, T-01–T-04, B-08.
2. **Säkerhet och märkning:** B-02 (Origin/Content-Type och token för `/api/speak`), F-01
   (escape i 2D som i 3D), B-03 (simulerat som standard).
3. **Demons läge:** B-01 (läget hålls separat från den begränsade händelselistan), F-02,
   F-03.
4. **Dokumentationen:** D-01–D-07 i en genomgång, sedan D-08–D-12.
5. **Testluckor:** Q-03–Q-07.
6. **Resten av fynden med låg allvarlighet**, när de berörda filerna ändå ändras.

Om MVP:n bygger vidare på koden kan fynden föras in som krav av typen `K-CS` och `K-OPS`,
eller som verifiering i `docs/mvp/kravmall.md`.

## Åtgärdsplan

Användaren godkände planen 2026-11-02 ("Vi kör enligt din plan"). Den ersätter förslaget
till ordning ovan.

**Arbetssätt:**
- Varje arbetspaket görs på en egen gren från `main`, och varje logisk ändring blir en egen
  commit.
- För en bugg skrivs först ett test som visar felet, sedan rättningen.
- Paketet visas fungera innan något stagas.
- Handoffen i `CONTEXT.md` uppdateras i samma commit.

### Arbetspaket

| Paket | Fynd | Vad som görs | Verifiering |
|---|---|---|---|
| **AP0 Tester som kan skada en demo** | Q-01, Q-02 | Klart 2026-11-02 (`2249662`). Testerna körs bara med `TECHSEED_TEST_POSTGIS=1` respektive `TECHSEED_TEST_DOCKER=1`. | Sviten är grön: 802 passerade, 3 överhoppade |
| **AP1 Robust datahämtning** | T-01–T-04 | `If-Range` med ETag eller Last-Modified, annars börjar nedladdningen om. Content-Length kontrolleras före `replace`. Skrivningarna blir atomiska (`.part` och `os.replace`) för kommunkartans tiles, webbiblioteken och rösten. Markören för ett klart steg skrivs sist, och rösten hashkontrolleras på disk. | Tester med en stub-server som bryter mitt i och byter fil mellan försöken |
| **AP2 Säkerhet** | B-02, F-01, B-05, B-06 | `POST` kräver `Content-Type: application/json` och samma Origin eller ingen Origin, också för `/api/speak`. 2D escapar samma fält som 3D. Lantmäteriets proxy tar bara listade lager och kontrollerar z/x/y. `OSError` fångas. | Tester för fel Content-Type, främmande Origin och ett OSM-namn med HTML |
| **AP3 Märkning** | B-03, F-04 | IoT-värden räknas som simulerade om inte `"simulated": false` står uttryckligen. Monitorn skriver tillbaka sin kreditering efter ett avbrott. | Test av IoT-flaggan och kontroll i webbläsaren |
| **AP4 Demons läge** | B-01, F-02, F-03, F-05, F-06, B-08 | Läget hålls separat från listan med de 100 senaste händelserna. `flashedPasses` töms vid sync. Frågesvar får ett löpnummer så att inaktuella svar kastas. Mission control försöker igen och visar fel. `detectionKey` sätts först när svaret har kommit. En korrupt profilfil sparas undan och skrivs inte över. | Test med 150 händelser, profiltest och demokontroll i webbläsaren |
| **AP8 Dokumentation** | D-01–D-12, B-11, Q-06 (katalogen) | README och `app/README.md` uppdateras. Operatörsguiden: den borttagna grenen, alla 16 scenarier, databasnamnen och mässformuleringarna. Inaktuella punkter i `CONTEXT.md` rättas. Kramfors i katalogen, avvikelsen från one-pagern om LLM, registrets grenhänvisning och antal, och kommentarerna i `scenario.py`. | Granskning mot koden |
| **AP5 Backend i övrigt** | B-04, B-07, B-10, B-12, B-09 | Tid utan tidszon räknas som UTC. PostGIS-frågor får timeout. Talkön och listan `spoken` får tak. `/api/stream` får en nedre gräns för `from`. Falsterbo får inställningar för demokontrollen. | Enhetstester och `check_demo` för Falsterbo |
| **AP7 Testluckor** | Q-03, Q-04, Q-08–Q-12, T-09 | `skipif` när data eller bibliotek saknas, i stället för att kontroller tyst hoppas över. Tester för de två hämtverktygen. Katalogen kompletteras. Fast tid i stället för `sleep` och `now()`. Gemensamma fixturer i `conftest.py`. | Sviten med och utan `data/` |
| **AP6 Drift** | T-05–T-08, T-10 | Docker-imagarna låses till de digests som finns lokalt, och digesten sparas i SOURCE.json. Paketlistorna rättas. `getuid` får skydd. `package_data` varnar för data med `permission` som bara tillåter intern användning. | Tester och en kontroll att tiles och terräng byggs |

Paketen görs i den ordning som tabellen visar.

### Beslut 2026-11-02

Användaren godkände förslagen:
- **B-10:** `/api/stream` behålls, men med en nedre gräns för `from`. Den tas inte bort.
- **T-05:** Docker-imagarna låses till de digests som finns lokalt nu, så att dagens kartor
  och terräng kan byggas om likadant.
- **D-06:** operatörsguiden behåller sin struktur. Bara mässformuleringarna och "brandkartan"
  tas bort. Ingen omskrivning till en guide för intern demo nu.
- **Ordning:** AP0, AP1, AP2, AP3, AP4, AP8, AP5, AP7, AP6.

### Parkerat

- **Q-05:** att köra `panel.js`, `map2d.js` och `control.js` i Node. Det kräver
  omstrukturering av stora filer och väntar tills MVP:ns arkitektur är bestämd.
