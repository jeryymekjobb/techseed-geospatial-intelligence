# Operatörsguide – brandkartan på IoTDagen

Guide för den som kör demonstratorn i montern: förberedelser, start, tvåminutersmanuset,
vad som är riktigt och simulerat, felsökning och avslutning. Teknisk bakgrund finns i
`app/README.md`.

Kommandona körs från repots rot, `techseed-geospatial-intelligence/`.

> **Inte provat ännu:** flytet i 3D-vyn på mässans dator. Proven hittills har körts i
> headless Chrome utan grafikkort. Kör kontrollen i avsnitt 1.3 på mässans dator innan
> mässan.

## 1. Förberedelser dagen före

### 1.1 Engångshämtningar

Allt nedan behövs en gång per dator och sparas i `data/` och `app/frontend/vendor/`, som
inte versioneras. Efteråt behövs inget internet för demon. Kör kommandona i tur och ordning:

```bash
# Lokala tjänster: PostGIS, offline-karta och MQTT (kräver Docker)
docker compose up -d tiles postgis mosquitto

# Python-miljö med IoT-klient och provverktyg (kräver internet)
python3 -m venv .venv
.venv/bin/pip install -r app/requirements-iot.txt -r tools/requirements-record.txt

# Webbibliotek: Cesium och satellite.js (kräver internet)
python3 -m tools.fetch_web_vendor

# Höjddata och 3D-terräng (kräver internet och Docker)
python3 -m tools.fetch_copernicus_dem
python3 -m tools.build_terrain

# Offline-karta (kräver data/osm/sweden-latest.osm.pbf, cirka 930 MB, se app/README.md)
python3 -m tools.build_offline_tiles

# Data i PostGIS (kräver att tjänsten postgis kör)
python3 -m tools.load_postgis

# Satellitbanor 2014 (kräver Space-Track-konto i ~/.spacetrackrc)
python3 -m tools.fetch_tle_history

# Landsat-bilden 4 aug 2014 (kräver internet och Docker)
python3 -m tools.fetch_landsat_scene
```

`~/.spacetrackrc` innehåller två rader, `identity=<e-postadressen du loggar in med>` och
`password=<lösenord>`, och ska bara kunna läsas av dig (`chmod 600 ~/.spacetrackrc`).

### 1.2 Data som visas offentligt

Kontrollera Space-Tracks användarvillkor för att visa satellitpositioner beräknade ur
deras banelement på en mässa. Det är inte granskat ännu (se `CONTEXT.md`, backlogg).

### 1.3 Generalrepetition med kontrollen

Kör på mässans dator, med skärmarna inkopplade:

```bash
docker compose up -d tiles postgis mosquitto
.venv/bin/python -m tools.check_demo --headed --out ~/demo-check
```

Verktyget kör hela demon i två fönster och skriver `~/demo-check/report.txt`. Allt ska
vara **GODKÄND**. Notera raden "Bilder per sekund i 3D". Som tumregel (inte uppmätt på
mässans dator) känns satelliterna och kameraresan hackiga under cirka 20.

## 2. Start på mässan

### 2.1 Starta

```bash
docker compose up -d tiles postgis mosquitto     # om de inte redan körs
.venv/bin/python -m app.backend.server             # terminal 1 – vänta på "PostGIS: questions on"
.venv/bin/python -m tools.mqtt_node_sim --interval 5   # terminal 2 – monternoderna (simulerade)
```

Låt båda terminalerna stå öppna under hela mässdagen. Stängs terminal 1 slutar demon att
svara.

### 2.2 Öppna skärmarna

| Skärm | Adress | Placering |
|---|---|---|
| Huvudskärm (besökarna) | <http://127.0.0.1:8765/3d.html?at=2014-08-04T09:30:00Z> | stora skärmen, helskärm med F11 |
| Mission control (operatören) | <http://127.0.0.1:8765/control.html> | liten skärm eller surfplatta bredvid |

`?at=2014-08-04T09:30:00Z` ställer scenarioklockan för alla skärmar strax före en
satellitpassage. Besökarna ser bara huvudskärmen.

### 2.3 Mission control på en annan enhet

Ska en surfplatta styra över nätverket måste backend lyssna på nätverket och kräva en
token:

```bash
SCENARIO_CONTROL_TOKEN=<valfri hemlig sträng> .venv/bin/python -m app.backend.server --host 0.0.0.0
```

Öppna då `http://<datorns-ip>:8765/control.html?token=<strängen>` på surfplattan. Även
huvudskärmen behöver `&token=<strängen>` i adressen om den ska ställa klockan med `?at=`.
Skärmar utan token kan bara titta.

## 3. Tvåminutersmanuset

Knappar i **fetstil** finns i mission control. Hastigheten väljs under "Uppspelning" på
huvudskärmen – mission control har inget hastighetsval ännu.

| Tid | Gör | Säg (förslag) |
|---|---|---|
| 0:00 | Klicka "Flyg till branden" på huvudskärmen – kameran går ut till jorden och flyger in till branden. | "Det här är skogsbranden i Västmanland sommaren 2014 – återuppspelad med riktiga satellitdata." |
| 0:10 | **SPACE VIEW**. Välj **1 minut/s**. **PLAY**. | "Det här är satelliterna som faktiskt såg branden – Aqua, Terra och Suomi NPP – där de var den dagen." |
| 0:30 | Suomi NPP passerar kl. 11:48 svensk tid och blinkar med en linje ner till branden. | "Här upptäcker Suomi NPP:s VIIRS-instrument värmen från branden." |
| 0:40 | **SPACE VIEW** igen (RETURN TO INCIDENT). Kl. 12:06 svensk tid kommer Landsat-bilden. | "Landsat 8 fotograferade branden tjugo minuter senare – det mörka är bränd skog, det orange är brandfronten." |
| 0:50 | Välj **1 timme/s**. | "Sensorer på marken bekräftar – de här är simulerade i demon." |
| 1:00 | Peka på AI ASSESSMENT. Klicka "Why do you believe there is a fire?". | "Bedömningen visar varför: varje rad pekar på sitt objekt på kartan." |
| 1:15 | Klicka "Show infrastructure within 5 km of the incident". Fäll ut "SQL som kördes". | "Det här är en riktig rumslig fråga mot databasen – frågan syns här." |
| 1:25 | **+60 MIN** (och igen för att stänga). | "Prognosen är en enkel modell med stor osäkerhet." |
| 1:35 | **SATCOM FAILURE**. Vänta några sekunder. | "Satellitlänken bryts – IoT fortsätter, satellitdatan köas." |
| 1:50 | **SATCOM FAILURE** igen. | "Länken är tillbaka – här är det som hände under avbrottet." |
| 2:00 | **GOD VIEW**, och filterknapparna om tid finns. | Slutbild: "From Orbit to Decision." |
| efter | **RESET**. | Klart för nästa besökare inom cirka 5 sekunder. |

Fler knappar vid frågor: **SENSOR FAILURE** (en sensor faller bort och räknas inte),
**SATELLITE DETECTION**, **ROAD CLOSED** och **POWER FAILURE** (bara text, märkta
syntetiska – det finns inga väg- eller elnätsdata kopplade till dem).

## 4. Riktigt, beräknat och simulerat

Var tydlig med skillnaden – skärmarna märker varje del.

| Kategori | Vad | Säg |
|---|---|---|
| **Riktiga data** | Brandens FIRMS-detektioner (NASA), Landsat 8-bilden (USGS), väderobservationer från SMHI, satelliternas banelement (Space-Track), terräng och orter från OSM (dagens läge, inte 2014) | "Riktiga data från 2014, uppspelade – inte live." |
| **Beräknat** | Satellitpositionerna (ur banelementen), vinden (ERA5-Land, en modell), brandprognosen, bedömningspoängen | "Beräknat ur data. Poängen är en regelbaserad poäng, ingen sannolikhet." |
| **Simulerat/syntetiskt** | Monternoderna (TEMP, WATER, AIR, NTN), sensorerna i brandområdet, kommunikationsavbrottet, händelserna från mission control | "Simulerat för demon – märkt på skärmen." |

Säg inte att något är live, att sensorerna fanns i skogen 2014 eller att poängen är en
träffsäkerhet. Partnernamn (Dacreo, BruhnBruhn) används inte förrän det finns ett
skriftligt godkännande.

## 5. Felsökning

| Problem | Orsak | Åtgärd |
|---|---|---|
| "This site can't be reached" / `ERR_CONNECTION_REFUSED` | Backend kör inte. | A, ladda sedan om sidorna. |
| "Ansluter …" eller IoT unavailable | Brokern kör inte, eller backend startades med `python3` i stället för `.venv/bin/python`. | B, sedan A. |
| Monternoderna visas som OFFLINE | Simulatorn i terminal 2 har stannat. | C – noderna blir live inom några sekunder. |
| Frågorna svarar "PostGIS svarar inte" | PostGIS kör inte. | D, sedan A. |
| Inga satelliter eller ingen satellitbild | `data/tle/` eller `data/landsat/` saknas. | E. Landsat-bilden visas först från 12:06 svensk tid den 4 augusti. |
| Tom eller ljus karta runt brandområdet | Offline-kartan kör inte. | F. |
| Hackig 3D-vy | För hög hastighet eller svag grafik. | Välj 1 minut/s i SPACE VIEW. Mät med kontrollen i avsnitt 1.3. |
| Knapparna i mission control ger "fel eller saknad token" | Backend kräver token. | Lägg till `?token=<strängen>` i adressen (avsnitt 2.3). |
| GOD VIEW på 2D-kartan blir tom | Känd begränsning: offline-kartan täcker bara brandområdet. | Använd 3D-vyn. |
| Allt annat | – | **RESET** i mission control. Hjälper det inte: ladda om huvudskärmen med adressen i 2.2. |

Åtgärderna (från repots rot):

```bash
# A – starta backend (terminal 1)
.venv/bin/python -m app.backend.server

# B – starta MQTT-brokern
docker compose up -d mosquitto

# C – starta de simulerade monternoderna (terminal 2)
.venv/bin/python -m tools.mqtt_node_sim --interval 5

# D – starta PostGIS
docker compose up -d postgis

# E – hämta satellitbanor och Landsat-bilden
python3 -m tools.fetch_tle_history
python3 -m tools.fetch_landsat_scene

# F – starta offline-kartan
docker compose up -d tiles
```

## 6. Avslutning

Tryck Ctrl-C i terminal 1 och 2. Docker-tjänsterna kan få stå kvar, eller stoppas med
`docker compose stop`.
