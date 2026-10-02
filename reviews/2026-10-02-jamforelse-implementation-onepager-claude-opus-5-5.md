# Jämförelse: implementationen mot one-pagern

Datum: 2026-10-02
Granskare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code.
Underlag: `onepager.md` och implementationen i repot vid commit `1219d67`
(`app/`, `tools/`, datakatalogerna, `reports/`).
Typ: Ren jämförelse. One-pagern har inte ändrats.

## Sammanfattning

Implementationen täcker **kartan, väder och prognos**, och går där längre än
one-pagern. **Rymd- och IoT-delen**, som bär one-pagerns berättelse, saknas:
Dacreo, satellitpositioner, IoT-sensorer, AI-panelen, kommunikationsavbrott och
3D/Cesium. Två skillnader är medvetna val:

- historisk uppspelning i stället för "LIVE", enligt granskningens G-01
  (`reviews/2026-09-30-granskning-onepager-claude-opus-5-5.md`);
- tidsspann i stället för exakta ankomsttider, enligt efterhandstestet
  (`reports/2026-10-01-brandspridningsanalys-vastmanland-2014-claude-opus-5-5.md`).

## De fem datalagren

| Lager i one-pagern | Implementationen | Status |
|---|---|---|
| 1. Satellit: Sentinel/Copernicus plus simulerad Dacreo-händelse | NASA FIRMS MODIS och VIIRS (1 727 verkliga detektioner). Copernicus används bara för väder (ERA5-Land). Inga Sentinel-bilder, och Sentinel-2 fanns inte 2014. Ingen Dacreo. | Delvis, med annan källa |
| 2. GIS: vägar, byggnader, vatten, skog, terräng | OSM-karta och terränglager (skog, myr, vatten, åker). Vägar och byggnader från OSM används i analysen. Ingen höjdmodell och ingen 3D-terräng. | Delvis |
| 3. Väder: vind, temperatur, nederbörd | SMHI Sala A och Kloten A varje timme, vindfält från ERA5-Land med vindpilar, och brandväder (FWI). | Implementerat, mer än planerat |
| 4. IoT: 3–5 riktiga TechSeed-sensorer | Finns inte. | Saknas |
| 5. Infrastruktur: elstationer, vägar, kritisk infrastruktur | Orter i prognosen. Vägar och järnväg bara i analysen. Elnätet är medvetet uteslutet (G-10, inget beslut ännu). | Delvis |

## One-pagerns tio punkter

| Punkt | Implementationen | Status |
|---|---|---|
| 1. Huvudskärm: 70–80 % karta, situationspanel, tidslinje | Kartan tar cirka 75 % av bredden och panelen ligger till höger. Tidslinjen visar staplar per dygn i panelen, inte längs nederkanten. "LIVE ●" är ersatt med "Historiska data 2014 – uppspelning". | Delvis, medvetet annorlunda |
| 2. CesiumJS, 3D-glob, kameraresa Jorden → incidenten | Leaflet i 2D. Ingen glob och ingen kameraresa. | Avviker |
| 3. Dacreo, analys ombord på satelliten | Finns inte. | Saknas |
| 4. Riktiga satellitpositioner, SPACE VIEW | Finns inte. Tiden för senaste FIRMS-passage visas i prognospanelen. | Saknas |
| 5. Riktiga IoT-sensorer (nRF91, MQTT) | Finns inte. | Saknas |
| 6. Besökaren utlöser en incident, klassificering 94/4/2 % | Spela, Paus, Återställ och kioskläge (`?at=`, `?autoplay=1`). Ingen fysisk knapp och ingen klassificering. | Delvis |
| 7. Spårbar AI-panel ("Why do you believe…?") | Ingen LLM och ingen AI-agent. Prognosens underlag (observerad spridning, kalibrering, FWI) visas spårbart, men utan konfidens eller frågefunktion. | Saknas, delvis underlag |
| 8. Prognos +60 min med "AT RISK"-lista i minuter | Fysikalisk modell (FWI, FBP C-2) för 3, 6, 12 och 24 timmar med spannet halva–dubbla farten. Orter listas med tidsspann. Efterhandstestet visar att exakta minuter inte går att ge med säkerhet. | Mer än planerat, medvetet annorlunda |
| 9. Kommunikationsavbrott (DISRUPT COMMS, SYNC) | Finns inte. | Saknas |
| 10. God mode med filter | Lagerkontroll för hotspots, terräng, vind, prognos och FIRMS-urval. Inga lager för rymd, sjöfart eller flyg. | Delvis |

## "Riktigt" och "simulerat" enligt one-pagern

- **Riktigt i one-pagern:**
  - Finns: väderdata.
  - Delvis: Copernicus-data, men bara väder, inte Sentinel.
  - Saknas: Cesium, PostGIS, MQTT, IoT-noder, satellitpositioner, LLM eller
    AI-agent, och spatiala frågor från AI:n (ST_DWithin). Geometrin räknas i
    Python, inte i PostGIS.
- **Simulerat i one-pagern:** brandförloppet skulle simuleras. Implementationen
  använder i stället verkliga historiska detektioner, vilket är ärligare men ger
  ett fast scenario. Dacreo, kommunikationsavbrott och klassificering, som skulle
  simuleras, finns inte alls.

## Styrning och mässan

- **Mission control:** ingen separat operatörsskärm. Händelseknapparna saknas
  (SENSOR FAILURE, SATCOM FAILURE, ROAD CLOSED, POWER FAILURE, +60 MIN).
  Uppspelningen är däremot repeterbar, med kioskläge och inspelning till video,
  vilket one-pagern betonar.
- **Tvåminutersdemon:** uppspelningen kan ta två minuter med 3 timmar/s. Bara
  stegen 0:30 (zoom till Mälardalen) och 1:20 (prognosen) har motsvarigheter.
- **Mässhärdning:** kartrutorna hämtas från internet. Offlineläge och
  Lantmäteriets kartor är inte på plats.

## Skillnader och risker

1. **"LIVE" mot historiskt:** one-pagerns huvudskärm visar "LIVE ●", medan
   implementationen märker allt som historiskt (G-01).
2. **Exakta ankomsttider:** one-pagern visar "Substation 17 – 42 min".
   Efterhandstestet visar att det troliga värdet bara träffade
   observationsfönstret i 13–15 % av fallen.
3. **Plats:** one-pagern nämner Västeråsregionen. Branden låg cirka 30–40 km
   norr om Västerås, i Mälardalens utkant, vilket fortfarande passar
   beskrivningen.
4. **Satellitkälla:** one-pagern nämner Sentinel. För 2014 finns bara FIRMS,
   Landsat 8 och Sentinel-1 (radar).
5. **Berättelsen:** "See and compute from space / Fuse and understand on Earth"
   bärs i dag bara av FIRMS och vädret. Dacreo, IoT och AI, som enligt one-pagern
   gör demon unik för TechSeed, finns inte.

## Implementerat men inte nämnt i one-pagern

- FIRMS-uttag och dataverktyg med källor och kontrollsummor.
- SMHI- och ERA5-Land-väder med vindpilar.
- Brandväder enligt FWI och efterhandstest med daterad rapport.
- Kioskläge och inspelning till video.
- Förberedd proxy för Lantmäteriet.
- Presentationen `reports/2026-10-01-brandkartan-presentation.pptx`.
