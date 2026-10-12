# Plan: det som saknas mot one-pagern

Datum: 2026-10-02
Författare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code.
Underlag: `onepager.md` och
`reviews/2026-10-02-jamforelse-implementation-onepager-claude-opus-5-5.md`.
Status: Fas 0–5 genomförda i prototypen, fas 6 delvis. B1 och B2 är genomförda,
B4 körs simulerat enligt beslut 2026-10-04 och B3 är öppen. B5 är genomförd i
prototypen men inte formellt beslutad. Se [Status 2026-10-12](#status-2026-10-12),
[Status 2026-10-04](#status-2026-10-04) och [Status 2026-10-02](#status-2026-10-02).

Planen bygger vidare på det som finns: backend, data, prognos, kioskläge och
inspelning. Den lägger till rymd-, IoT-, AI- och styrdelarna i en ordning där
varje fas ger en körbar demo. Allt simulerat märks som syntetiskt i
gränssnittet, enligt `AGENTS.md`.

## Beslut som behövs först

| # | Beslut | Förslag |
|---|---|---|
| B1 | **Interaktionsmodell** (G-04) | Operatören styr från en egen pekskärm (mission control). Besökaren ser bara huvudskärmen. |
| B2 | **AI-svar** (G-14) | Förberedda svar som visas direkt, plus spatiala frågor som körs på riktigt mot PostGIS. En lokal LLM kan läggas till som tillval. |
| B3 | **Rättigheter och namn** (G-09, G-10, G-12) | Ja till att visa elnät från OSM. Dacreo och BruhnBruhn nämns bara med skriftligt godkännande. |
| B4 | **IoT-hårdvara** | 3–4 nRF91-noder finns och kan levereras. De visas som riktiga sensorer i montern. Sensorer i brandområdet är syntetiska och märks så (G-02). |
| B5 | **Visualiseringsmotor** | Byt till CesiumJS utan Cesium ion: OSM-kartbilder, höjddata från Copernicus DEM och satellitbanor beräknade lokalt. Leaflet behålls som reserv. Genomförd i prototypen, ej formellt beslutad. |

## Status 2026-10-12

Avstämning mot koden efter commit `6043543`. Underlag: git-historiken sedan
2026-10-04, `CONTEXT.md`, `python3 -m pytest` (338 godkända) och två körningar av
`tools/check_demo.py` för Sundsvall 2026, headless med en egen MQTT-broker.

### Faser

- **Fas 2 genomförd:** upptäcktssekvensen startas med SATELLITE DETECTION på nästa
  riktiga satellitpassage efter scenarioklockan och stegas med NÄSTA. Den är
  märkt som syntetisk.
- **Fas 5 funktionellt bekräftad:** all styrning finns i mission control och
  huvudskärmen bara visar. Demokontrollen för Sundsvall gick igenom alla nio steg
  i den andra körningen (RESET 2,71 s). I den första underkändes bara RESET, med
  5,72 s. Headless Chrome renderade 3D-vyn i mjukvara med 0,2 bilder per sekund,
  så tiderna säger inget om utställningsdatorn. Kravet på RESET inom 5 s behöver
  bekräftas med `--headed` på utställningsdatorn. Med den delade brokern stoppade
  kontrollen tidigare vid steg 4 på grund av en extra nod (`test-node`); dess
  källa är inte utredd.
- **Fas 6 delvis:** manus i operatörsguiden för brand- och översvämningsdemona,
  start med en meny och ett kommando, långsammare tempo och videoinspelning
  (`tools/record_demo.py`). Kvar: kiosk med automatisk återstart, slutbild,
  belastningsprov (8 timmar och nätavbrott) och prestandamätning på
  utställningsdatorn.

### Utöver planen

- Tre demos till: översvämningen i Sundsvall 2026 (scenario, inte en återspelad
  händelse), vinteröversvämningarna i Skåne 2024 och branden vid Kårböle 2018.
  Demon väljs i en meny vid start.
- Sentinel-1 och Sentinel-2, Copernicus EMS-perimetrar, SMHI:s väderradar,
  vattenföring och sjönivåer.
- Visningsprofil per scenario med bildtyper, baskartor, kartlager och demons
  start och stopp, sparad från mission control.
- Datassimilering med ensemble-Kalmanfilter prövades
  (`reports/2026-10-05-plan-datassimilering-brandprognos-claude-opus-5-5.md`).
  Efterhandstestet visade att filtret blev sämre, så dagens prognos behålls.

### Kvar

- Beslut B3: elnät från OSM och partnernamnen.
- Öppna frågor i `CONTEXT.md`: MVP-scenario, godkända datakällor, licenser och
  attribuering, och bräddningsdata från MSVA.
- Backloggen är oförändrad (se Status 2026-10-04).

## Status 2026-10-04

Genomförandet av B1–B4, med en commit per steg. Underlag: koden, `python3 -m
pytest` (143 godkända, inklusive frågorna mot PostGIS) och webbläsarprov med
Playwright i Chrome för varje steg med gränssnitt.

### Beslut

- **B1 genomförd:** mission control på egen sida (`control.html`), huvudskärmen
  följer.
- **B2 genomförd:** förberedda svar ur bedömningen och riktiga PostGIS-frågor.
  Lokal LLM ingår inte.
- **B3 öppen:** inget elnät i data, och texterna är generiska ("edge
  processing") i stället för Dacreo och BruhnBruhn.
- **B4 ändrad 2026-10-04:** monternoderna körs simulerat för mässdemon och
  märks "simulerad". Riktig hårdvara och firmware ligger i backloggen.

### Steg

| Steg | Innehåll | Commit |
|---|---|---|
| 1 | Händelser i scenariomotorn | `9531cc4` |
| 2 | Mission control och huvudskärmens reaktioner | `a4e7adf` |
| 3 | MQTT-mottagning av monternoder | `f516d1f` |
| 4a | Syntetiska sensorer i brandområdet | `b998ff4` |
| 4b | Visning av sensorerna | `024b9ef` |
| 5a | Simulator för monternoderna | `25a81cf` |
| 6 | Spårbar bedömning med evidens | `1b08463` |
| 7 | Förberedda frågor med PostGIS | `9b6ace5` |
| 8a | Kommunikationsavbrott med kö och SYNC | `f7c7958` |
| 8b | Filter i GOD VIEW | `da84b55` |
| 1b-1 | Hämtning av 2014 års banelement från Space-Track | `d83e7dc` |
| 1b-2 | Banelementen i backend och kontroll mot FIRMS | `f9eee31` |
| 1b-3 | Satelliterna på globen, SPACE VIEW och RETURN TO INCIDENT | `9cfa8b9` |
| 1b-4 | Landsat 8-bilden från 4 augusti 2014 på båda kartorna | `f14ecec` |

Fas 1 genomfördes med satelliternas läge 2014 (alternativ B, 2026-10-05) i
stället för dagens läge från CelesTrak: Terra, Aqua och Suomi NPP – de som gjorde
detektionerna – samt Landsat 8 och ISS, beräknade ur banelement från Space-Track.
Sentinel-1A och Sentinel-2A var inte i drift i augusti 2014. Varje
FIRMS-detektion ligger inom svepbredden för satelliten som gjorde den.

### Kvar

- **Fas 2:** den syntetiska upptäcktssekvensen från rymden och klassificeringen.
- **Fas 5:** att hela tvåminutersdemon går att köra från pekskärmen och
  återställa på under 5 sekunder är inte provat från början till slut.
- **Fas 6:** manus, slutbild, kiosk med automatisk återstart och
  belastningsprov.
- **Backlogg:** firmware för nRF91, kort och SDK, wifi som reserv, att exponera
  och skydda brokern, en riktig 1-timmeshorisont för +60 MIN och en bredare
  offline-karta för GOD VIEW i 2D. Granska också Space-Tracks användarvillkor
  för att visa positionerna offentligt.

## Status 2026-10-02

Avstämning mot koden efter commit `a18700d`. Underlag: dagens commits, läsning
av koden och `python3 -m pytest` (78 godkända). Gränssnittet är inte provat i
webbläsare, och offlinedrift är inte provad från början till slut.

### Fas 0 – i stort sett klar

- **Klart:** gemensam scenarioklocka (`app/backend/scenario_engine.py`) som alla
  skärmar följer via `/api/scenario/stream`, med kommandona play, pause, reset,
  seek och speed, och token för styrning över nätverk. PostGIS i Docker med
  orter, byggnader, vägar, järnväg, terräng, detektioner, brandfronter och
  prognoser (`tools/load_postgis.py`). Offline-kartrutor via `tileserver-gl`
  med egna ort- och sjönamn, och lokal terräng i `data/terrain/`.
- **Avvikelser:** scenariomotorn är en klocka utan händelser i tidslinjen;
  händelserna behövs i fas 5. Elnät saknas i PostGIS i väntan på B3. 2D-kartan
  har kvar OSM online som valbart kartlager.

### Fas 1 – delvis klar

- **Klart:** CesiumJS utan Cesium ion, med Natural Earth II och offline-kartrutor
  över brandområdet. Kameraresan till branden på cirka 5 sekunder. Hotspots,
  terräng, vind, prognos och namn på globen. Höjddata från Copernicus GLO-30 med
  licensens källhänvisning.
- **Kvar:** satellitbanor från CelesTrak med satellite.js (biblioteket hämtas av
  `tools/fetch_web_vendor.py` men används inte än), SPACE VIEW och RETURN TO
  INCIDENT med panel för höjd, fart och nästa passage, och satellitbildslagret
  från Landsat 8 den 4 augusti 2014.

### Fas 2–6

Inte påbörjade.

## Faser

### Fas 0 – Grund och mässhärdning (1 vecka)

Tas först, eftersom allt annat bygger på det.

- **Scenariomotor i backend:** ett tillstånd med tidslinje och händelser som
  alla skärmar följer via Server-Sent Events. Den gör att alla scenarier går att
  återställa och spela upp likadant varje gång.
- **Offline:** egna kartrutor ur OSM för utsnittet, och höjddata lokalt.
- **PostGIS:** i Docker, med målen från OSM (orter, byggnader, vägar, järnväg
  och ev. elnät), brandfronten och prognosytorna.
- **Klart när:** demon går utan internet, och en ändring av scenariot syns
  direkt på alla skärmar.

### Fas 1 – 3D och rymd (2 veckor)

- **CesiumJS** med glob och kameraresan Jorden → Europa → Sverige → Mälardalen
  → branden på cirka 5 sekunder. Befintliga lager flyttas över (hotspots,
  terräng, vind, prognos).
- **Riktiga satellitpositioner:** banelement från CelesTrak, beräknade med
  satellite.js (SGP4), för Sentinel-1, Sentinel-2, Landsat 8 och ISS.
- **SPACE VIEW och RETURN TO INCIDENT,** med panel för höjd, fart och nästa
  passage över Mälardalen. Banelementen sparas lokalt för offline.
- **Satellitbildslager:** Landsat 8 den 4 augusti 2014. Tillval: radar från
  Sentinel-1.
- **Klart när:** kameraresan och SPACE VIEW fungerar offline, med verkliga
  satellitbanor.

### Fas 2 – Upptäckt från rymden (1 vecka)

Allt i den här fasen är syntetiskt.

- **Dacreo-sekvensen:** bild tagen, avvikelse upptäckt ombord med konfidens,
  nedlänk. Den triggas av den första riktiga FIRMS-detektionen.
- **Klassificering** (vegetationsbrand, industri, okänd). Den bygger på regler
  från FIRMS-fältet `type`, upprepade detektioner på samma plats och
  strålningseffekt. Den visar en uträknad sannolikhet, inte påhittade värden.
- **Klart när:** sekvensen T+0–T+25 s går att trigga från mission control och
  är märkt som syntetisk.

### Fas 3 – IoT (1–2 veckor)

- **Mosquitto (MQTT)** i backend, med en abonnent som skickar värdena vidare
  till skärmarna.
- **3–4 nRF91-noder i montern** (TEMP, WATER, AIR, NTN) med firmware som skickar
  via LTE-M/NB-IoT, och wifi som reserv.
- **Syntetiska sensorer i brandområdet,** till exempel "Sensor 17". Deras
  värden räknas fram ur brandfrontens avstånd och vädret, och de märks som
  syntetiska.
- **Sensorhälsa:** felläge och bortfall.
- **Klart när:** de riktiga noderna syns live i montern, de syntetiska följer
  uppspelningen, och "IoT bekräftar 2/3" räknas ut.

### Fas 4 – Spårbar AI (1–2 veckor)

- **Bedömningspanel** med evidenslista (satellit, IoT, vind, prognos) och
  konfidens. Konfidensen räknas ut deterministiskt ur datan, och varje rad pekar
  ut sitt objekt på kartan.
- **Frågor:** förberedda frågor, som "Why do you believe there is a fire?" och
  "Show infrastructure within 5 km". De besvaras med riktiga PostGIS-frågor
  (`ST_DWithin`), och resultatet ritas på kartan.
- **Tillval:** en lokal LLM formulerar svaren ur samma evidens, med förberett
  svar som reserv om den är för långsam.
- **Klart när:** varje påstående i panelen har en källa som går att klicka
  fram, och frågorna svarar inom 1 sekund.

### Fas 5 – Mission control och händelser (1 vecka)

- **Egen sida `/control` för pekskärm:** SATELLITE DETECTION, SENSOR FAILURE,
  SATCOM FAILURE, ROAD CLOSED, POWER FAILURE, +60 MIN, RESET och GOD VIEW.
- **Kommunikationsavbrott:** satellitdata stoppas och köas, IoT fortsätter, och
  vid SYNC visas händelserna under avbrottet som "3 NEW EVENTS". De bygger på
  verkliga FIRMS-detektioner i perioden.
- **+60 MIN** visar prognosen med tidsspann, inte exakta minuter, enligt
  efterhandstestet
  (`reports/2026-10-01-brandspridningsanalys-vastmanland-2014-claude-opus-5-5.md`).
- **GOD VIEW** med filter. Rymd, IoT, infrastruktur och väder är riktiga lager.
  Sjöfart och flyg lämnas utanför eller simuleras och märks.
- **Klart när:** hela tvåminutersdemon kan köras från pekskärmen och återställas
  på under 5 sekunder.

### Fas 6 – Manus, form och stabilitet (1 vecka)

- Tvåminutersmanus enligt one-pagern, med Västmanland 2014 som historiskt
  scenario.
- Animationer, slutbild och kiosk med automatisk återstart.
- Belastningsprov: 8 timmar utan omstart, och avbrott i nätet.
- Videoinspelning av hela demon som reserv.

## Omfattning och risker

- **Omfattning:** cirka 8–9 veckor för en person, eller 4–5 veckor för 2–3
  personer som delar på faserna. Fas 1 och fas 3 går att köra parallellt.
  One-pagern räknar med 6–8 veckor för 2–3 personer. Uppskattningen är grov.
- **Största riskerna:**
  - leverans av IoT-hårdvaran och mobiltäckning i mässhallen;
  - prestanda i Cesium på mässans dator;
  - godkännande av Dacreo och partnernamn;
  - att syntetiska delar uppfattas som verkliga, vilket motverkas med tydlig
    märkning.
- **Utanför planen:** NATO-data, räddningstjänstens operativa data, och
  live-integration av AIS och ADS-B. De kan finnas i arkitekturbilden, i linje
  med one-pagern.
