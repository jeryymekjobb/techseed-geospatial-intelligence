# IoTDagen – TechSeed Geospatial Intelligence

## Ofiltrerad konceptutveckling för mässdemonstrator

Jag skulle skala ner visionen men göra upplevelsen mycket mer övertygande. Målet bör inte vara att bygga ett komplett War Room, utan en 2–3 minuters demo där besökaren upplever hur rymddata + GIS + IoT + AI blir en operativ lägesbild.

## TECHSEED GEOSPATIAL INTELLIGENCE

### Koncept: En samhällskris upptäcks från rymden och verifieras på marken

Exempelvis en skogsbrand eller översvämning i Mälardalen. Skogsbrand är sannolikt visuellt bäst.

Besökaren ser initialt en lugn 3D-vy:

Europa → Sverige → Mälardalen → Västeråsregionen

Sedan startar scenariot.

```text
🛰 SATELLITE
          │
     DACREO AI
          │
  EVENT DETECTED
          │
          ▼
┌──────────────── TECHSEED ────────────────┐
│                                          │
│ Satellite ─┐                             │
│ Weather ───┤                             │
│ GIS ───────┼──► GEOSPATIAL FUSION       │
│ IoT ───────┤            │                │
│ Traffic ───┤            ▼                │
│ Infra ─────┘       AI COPILOT            │
│                           │               │
└───────────────────────────┼───────────────┘
                            ▼
                   OPERATIONS ROOM
```

## DET HÄR SKULLE JAG FAKTISKT BYGGA

Inte 25 integrationer. Fem fungerande datalager räcker.

1. Satellite – Sentinel/Copernicus-data + simulerad Dacreo-event
2. GIS – Vägar, byggnader, vatten, skog, terräng
3. Weather – Vindriktning, temperatur, nederbörd
4. IoT – 3–5 riktiga TechSeed-sensorer
5. Infrastructure – Elstationer, vägar och annan kritisk infrastruktur

AIS, ADS-B, NATO, räddningstjänst osv kan finnas i arkitekturen, men jag skulle inte försöka integrera allt till första mässversionen. Det riskerar bara att göra projektet stort och demon svår att förstå.

## 1. HUVUDSKÄRMEN

Jag skulle göra UI:t ungefär så här:

```text
┌───────────────────────────────────────────────────────────────┐
│ TECHSEED GEOSPATIAL INTELLIGENCE            14:32:17 LIVE ●  │
├──────────────────────────────────────────┬────────────────────┤
│                                          │ SITUATION          │
│                                          │                    │
│             3D GIS                       │ 🔴 FIRE DETECTED   │
│                                          │                    │
│       🔥                                 │ Confidence 94%     │
│                                          │                    │
│        ○ IoT                             │ Wind NE 11 m/s     │
│                                          │                    │
│    ───── Road                            │ IoT confirms 2/3   │
│                                          │                    │
│        ⚡ Power                           │                    │
│                                          │ AI ASSESSMENT      │
│                                          │                    │
│                                          │ 2 assets at risk   │
│                                          │                    │
├──────────────────────────────────────────┴────────────────────┤
│ 13:30 ───── 14:00 ───── 14:30 ───── 15:00 ───── +60 min       │
└───────────────────────────────────────────────────────────────┘
```

70–80 % av skärmen ska vara kartan.

Undvik klassiskt Power BI-dashboardutseende.

Det ska kännas:

Command Center + Google Earth + AI.

## 2. CESIUM ÄR SANNOLIKT RÄTT VISUALISERINGSMOTOR

Jag skulle starkt överväga CesiumJS.

Det ger direkt:

- 3D-glob
- terräng
- satellitpositioner
- GeoJSON
- 3D Tiles
- rasterlager
- kameraanimationer
- tidsbaserade objekt

Det gör också en väldigt snygg sekvens möjlig:

Earth → Europe → Sweden → Mälardalen → Incident

på kanske fem sekunder.

Det ger omedelbart rymdkänslan.

## 3. DACREO SKA VARA EN LITEN MEN VIKTIG DEL

Jag skulle inte göra Dacreo till huvudpersonen.

Istället:

```text
🛰 EO SATELLITE

IMAGE ACQUIRED
      ↓
DACREO
ONBOARD AI

🔥 ANOMALY DETECTED

confidence 87 %

↓

DOWNLINK EVENT
```

Sedan händer resten hos TechSeed.

Storyn blir:

**BruhnBruhn:** See and compute from space.

**TechSeed:** Fuse and understand on Earth.

## 4. LÄGG TILL RIKTIG SATELLITPOSITION

Det här är billigt men väldigt effektfullt.

Visa riktiga satelliter som rör sig runt jorden.

Exempel:

- Sentinel-1
- Sentinel-2
- Landsat
- ISS

Besökaren kan klicka på SPACE VIEW och kartan zoomar ut.

Sedan visas exempelvis:

```text
SENTINEL-2
Altitude 786 km
Velocity 7.4 km/s
NEXT OBSERVATION
Mälardalen
T - 18:42
```

Sedan RETURN TO INCIDENT och kameran flyger tillbaka.

Det kommer se betydligt dyrare ut än det faktiskt är att bygga.

## 5. RIKTIGA IoT-SENSORER ÄR VIKTIGA

Här får TechSeed Things verkligen visa vad vi kan.

Jag skulle ha fyra fysiska boxar:

- TECHSEED TEMP – 24.7 °C
- TECHSEED WATER – 42 cm
- TECHSEED AIR – NORMAL
- TECHSEED NTN – ONLINE

Nordic nRF91 passar perfekt för storyn. MQTT räcker gott bakom.

## 6. BESÖKAREN SKA KUNNA ORSAKA EN INCIDENT

Ge besökaren en fysisk knapp:

TRIGGER EVENT

- T+0 – Satelliten upptäcker något.
- T+5 s – ANOMALY DETECTED.
- T+10 s – Dacreo analyserar.
- T+15 s – Kartan zoomar in och brand visas.
- T+20 s – IoT-data kommer in.
- T+25 s – AI korrelerar informationen.

Klassificering:

- Wildfire 94 %
- Industrial 4 %
- Unknown 2 %

Sensor 17:

- Temperature 24°C → 31°C → 46°C
- Smoke DETECTED

## 7. AI SKA INTE BARA VARA EN CHATBOT

AI-panelen ska fungera som ett spårbart analyslager.

```text
ASSESSMENT
Wildfire probable
Confidence: 94 %

Evidence:
✓ Satellite anomaly
✓ IoT temperature
✓ Smoke sensor
✓ Wind model
⚠ Camera unavailable
```

Besökaren ska kunna fråga:

“Why do you believe there is a fire?”

AI:n visar satellitobservation + IoT-observationer + weather och pekar på respektive objekt i kartan.

Det blir Explainable Geospatial AI.

Det är ett mycket bättre budskap än “vi har kopplat en LLM till GIS”.

## 8. LÄGG IN PROGNOSEN

Tryck:

+60 MIN

Kartan visar ett transparent område med predicted fire propagation.

AT RISK:

- ⚡ Substation 17 – 42 min
- 🛣 Road 66 – 31 min
- 🏭 Industrial site – 54 min

Det behöver inte vara avancerad AI.

Till mässan kan detta vara en enkel modell baserad på:

- vind
- vegetation
- terräng
- avstånd

Poängen är demonstrationen av geospatial reasoning.

## 9. KOMMUNIKATIONSAVBROTT

Besökaren trycker:

DISRUPT COMMS

SATCOM faller stegvis från bra signal till CONNECTION LOST.

Dacreo fortsätter bearbeta data.

```text
DACREO
EDGE PROCESSING
3 EVENTS QUEUED
```

Markstationen visar:

SATELLITE DATA UNAVAILABLE

men IoT fortsätter.

När kommunikationen kommer tillbaka:

SYNC

```text
3 NEW EVENTS
13:42 hotspot detected
13:44 area increased 17 %
13:46 new hotspot detected
```

AI:n säger:

“Three significant events occurred while satellite communication was unavailable.”

Det är en bra demonstration av resilience.

## 10. GOD MODE

Operatören trycker:

GOD VIEW

Kameran zoomar ut.

Nu ser man satelliter, flyg, fartyg, vädersystem, incident, IoT och infrastruktur på samma karta.

FILTER:

- ☑ Space
- ☑ IoT
- ☑ Infrastructure
- ☑ Weather
- ☐ Maritime
- ☐ Aviation
- ☐ Emergency

Då börjar det kännas som ett riktigt Geospatial Operations System.

## VAD JAG SKULLE BYGGA PÅ RIKTIGT RESPEKTIVE SIMULERA

RIKTIGT:

- Cesium 3D GIS
- PostGIS
- MQTT
- 3–5 IoT-noder
- riktig satellitposition
- Copernicus/Sentinel-data
- väderdata
- LLM/AI-agent
- GIS-query från AI

Exempel:

“Show infrastructure within 5 km of the incident.”

AI:n gör faktiskt en spatial query med ST_DWithin och kartan visar resultatet.

Det är tekniskt imponerande på riktigt.

SIMULERAT:

- Dacreo-event
- NATO-data
- räddningstjänstens operativa data
- kommunikationsavbrott
- framtida satellitobservation
- brandförlopp
- klassificeringsresultat

Var tydliga med att sådana lager är syntetiska i demon.

## MISSION CONTROL

På en liten touchskärm bredvid stora skärmen:

TECHSEED MISSION CONTROL

**SCENARIO:** [ WILDFIRE ]

EVENTS

- [ SATELLITE DETECTION ]
- [ SENSOR FAILURE ]
- [ SATCOM FAILURE ]
- [ ROAD CLOSED ]
- [ POWER FAILURE ]
- [ +60 MIN ]
- [ RESET ]

Personen från TechSeed som demonstrerar systemet styr hela scenariot därifrån.

Besökaren ser bara den stora Operations Room-skärmen.

Det gör demon repeterbar, vilket är extremt viktigt på mässa.

## RIMLIG MVP

Målet bör vara ungefär 6–8 veckor för 2–3 personer snarare än att försöka bygga en produkt.

Ungefär:

- 1–2 veckor: Cesium + GIS + UI
- 1 vecka: IoT/MQTT
- 1 vecka: satellit + väder
- 1–2 veckor: AI + PostGIS tools
- 1 vecka: scenariosystem
- 1 vecka: UX, animationer och mässhärdning

Det viktiga är att sista veckan går till show control och stabilitet, inte fler features.

## TVÅ MINUTERS DEMO

- 0:00 Earth view
- 0:10 Satellit passerar Sverige
- 0:20 Dacreo upptäcker incident
- 0:30 Zoom → Mälardalen
- 0:40 IoT verifierar
- 0:50 AI fusionerar informationen
- 1:05 Visa evidence/confidence
- 1:20 Visa +60 min prediction
- 1:35 SATCOM failure
- 1:45 Dacreo fortsätter edge processing
- 1:55 Link restored
- 2:00 COP uppdateras

Slutbild:

```text
TECHSEED GEOSPATIAL INTELLIGENCE

Physical world. Space. Data. Intelligence.

From Orbit to Decision.
```

Den här demon säger inte bara “TechSeed kan IoT”. Den visar embedded, connectivity, edge, cloud, GIS, satellit, data fusion, AI och UX som ett sammanhängande system.
