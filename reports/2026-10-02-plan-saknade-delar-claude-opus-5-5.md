# Plan: det som saknas mot one-pagern

Datum: 2026-10-02
Författare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code.
Underlag: `onepager.md` och
`reviews/2026-10-02-jamforelse-implementation-onepager-claude-opus-5-5.md`.
Status: Förslag. Besluten B1–B5 är öppna, och ingenting i planen är beslutat
eller påbörjat.

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
| B5 | **Visualiseringsmotor** | Byt till CesiumJS utan Cesium ion: OSM-kartbilder, höjddata från Copernicus DEM och satellitbanor beräknade lokalt. Leaflet behålls som reserv. |

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
