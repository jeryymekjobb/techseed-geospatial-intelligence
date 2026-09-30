# Granskning av onepager.md

Datum: 2026-09-30
Granskat dokument: `onepager.md`, "IoTDagen – TechSeed Geospatial Intelligence"
(commit `0cb96ce`)
Jämförelseunderlag: `AGENTS.md` och `CONTEXT.md` i samma repo, erfarenheter från
`instant-ai-design` (lokala LLM-körningar) och `techseed-ai-framework` (evidensmodell)
Granskare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code
Typ: Ren granskning. One-pagern har inte ändrats.

## Sammanfattning

Konceptet är välavgränsat och säljande. Fem datalager i stället för 25 integrationer,
en demo på 2–3 minuter, operatörsstyrd repeterbarhet och en förklarbar AI i stället för
en chatbot är bra val för en mässa. One-pagern säger också själv att simulerade lager
ska redovisas som syntetiska (rad 355).

De viktigaste bristerna:

1. **Gränsen mellan riktigt och simulerat är otydlig där det betyder mest.**
   Skärmen visar "LIVE ●", och IoT-sensorerna i mässhallen presenteras som att de
   verifierar en brand i Västeråsregionen. Klassificeringen är simulerad men förklaras
   av AI:n som om den vore beräknad (G-01–G-03).
2. **Interaktionsmodellen motsäger sig själv.** Besökaren ska både trycka på en knapp
   och ställa frågor till AI:n, men samtidigt bara se storskärmen medan en
   TechSeed-person styr allt (G-04).
3. **Siffror, tider och antal stämmer inte mellan avsnitten** (G-05–G-08).
4. **Datarättigheter, känsliga infrastrukturdata, partnernamn och mässans nätverk
   saknas som frågor** (G-09–G-13).
5. **Lokal LLM-latens är en verklig risk för live-frågor.** Mätningar i
   instant-ai-design visar 4–7 tokens/s för en 27B-modell på en laptop (G-14).

Allvarlighetsgrad: **Hög** = kan vilseleda publiken eller få demon att fallera,
**Medel** = väsentlig otydlighet eller lucka, **Låg** = konsistens och presentation.

## Riktigt, simulerat och trovärdighet

### G-01 "LIVE ●" över simulerade händelser (Hög)

Huvudskärmen (rad 59) visar "14:32:17 LIVE ●". Samtidigt är Dacreo-eventet,
brandförloppet, klassificeringen och kommunikationsavbrottet simulerade (rad
345–353). Rad 355 kräver att de syntetiska lagren redovisas som syntetiska, och
`AGENTS.md` och `CONTEXT.md` kräver att simulerade data inte framställs som live.
Skisserna visar ingen märkning av vad som är simulerat. Varje lager behöver en
synlig status, till exempel LIVE, REPLAY eller SIMULATED.

### G-02 Sensorer i mässhallen kan inte verifiera en brand i Västerås (Hög)

Konceptet bygger på att en händelse "upptäcks från rymden och verifieras på marken"
(rad 9), där IoT-data "verifierar" (rad 403) och "IoT confirms 2/3" (rad 69). De
fysiska boxarna står dock i mässhallen och mäter rumstemperatur ("24.7 °C", rad
179). Förloppet 24 °C → 31 °C → 46 °C och "Smoke DETECTED" för "Sensor 17" (rad
205–208) måste därför vara simulerat eller framkallat fysiskt, till exempel med en
värmekälla. One-pagern säger inte vilket.

Om sensorvärdena för branden är simulerade är påståendet att "riktiga
IoT-sensorer" verifierar branden vilseledande. Det behövs ett uttryckligt val:

- **Riktiga sensorer, riktigt stimulus:** värme eller rök i en kontrollerad box vid
  montern, där sensorn kartan visar är den fysiska boxen, tydligt märkt.
- **Simulerade sensorer:** märkta som simulerade, medan de fysiska boxarna visar sina
  egna riktiga värden separat.

### G-03 Förklarbar AI över simulerade resultat (Hög)

Klassificeringsresultatet ("Wildfire 94 %, Industrial 4 %, Unknown 2 %", rad 201–203)
är simulerat (rad 353). Ändå ska AI:n förklara "Why do you believe there is a fire?"
genom att peka på observationer i kartan (rad 227–231), och budskapet är "Explainable
Geospatial AI" (rad 233). Om siffrorna är förskrivna förklarar AI:n ett manus, inte
en egen slutsats.

Det behöver framgå vad AI:n faktiskt beräknar, till exempel att den sammanställer
evidens och gör spatiala frågor (rad 339–341), och vad som är förskrivet. Förklaringen
ska bygga på de faktiska evidensobjekten i demon, med källa, tid och status, inte på
fri text. En sådan evidenslista passar också väl mot Evidence Object i
techseed-ai-framework.

## Interaktion och körbarhet

### G-04 Vem styr demon? (Hög)

- Rad 186–190: "Ge besökaren en fysisk knapp: TRIGGER EVENT".
- Rad 227: "Besökaren ska kunna fråga".
- Rad 375–377: "Personen från TechSeed … styr hela scenariot därifrån. Besökaren ser
  bara den stora Operations Room-skärmen."

De tre påståendena går inte ihop. Välj en modell. Förslaget är att operatören styr
scenariot från Mission Control, och att besökaren får en enda säker interaktion, till
exempel knappen, utan att scenariot kan hamna i ett tillstånd som kräver RESET mitt i
en visning. Frågor till AI:n bör i så fall väljas från förberedda alternativ. I en
mässhall är fri röst- eller textinmatning svår att hantera, både på grund av buller
och oförutsägbara frågor.

### G-05 Tidslinjerna stämmer inte (Medel)

- Sekvensen efter TRIGGER EVENT (rad 192–197) når AI-korrelationen efter 25 s.
- Tvåminutersdemon (rad 398–409) når AI-fusionen efter 50 s och startar med 20 s
  jordvy och satellitpassage.
- Zoomen "Earth → … → Incident" tar "kanske fem sekunder" (rad 106–108), men 30 s i
  demomanuset.
- CONTEXT.md talar om 2–3 minuter, manuset om 2:00.

En av tidslinjerna bör vara den gällande, och den andra härledas från den.

### G-06 Klockslagen motsäger varandra (Medel)

Skärmen visar 14:32:17, tidslinjen 13:30–15:00 (rad 77). Händelserna under
kommunikationsavbrottet är tidsstämplade 13:42–13:46 (rad 290–292), alltså cirka 50
minuter före "nu". Avbrottet i demon varar bara cirka 20 s (rad 406–408). Scenarioklockan
och demotiden behöver en gemensam modell, till exempel att scenariot går i accelererad
tid och att det visas.

### G-07 Konfidens och antal skiljer sig (Medel)

- Dacreo anger "confidence 87 %" (rad 128), huvudskärmen och bedömningen "94 %" (rad
  65, 201, 217). Det framgår inte att 87 % är Dacreos detektion ombord och 94 % den
  fuserade bedömningen hos TechSeed.
- Antalet sensorer varierar: "3–5 riktiga" (rad 48, 330), "fyra fysiska boxar" (rad
  177), "IoT confirms 2/3" (rad 69) och "Sensor 17" (rad 205).
- Huvudskärmen säger "2 assets at risk" (rad 74), prognosen räknar upp tre (rad
  247–249).

### G-08 Kommunikationsavbrottet och NTN-sensorn (Medel)

Vid "DISRUPT COMMS" faller SATCOM, men "IoT fortsätter" (rad 280–282). Samtidigt
finns boxen "TECHSEED NTN – ONLINE" (rad 182). NTN betyder non-terrestrial network,
alltså satellitansluten IoT. Om NTN-boxen går via satellit borde den påverkas av
avbrottet. Det behöver framgå vilka länkar som faller: nedlänk från jordobservation,
SATCOM till markstationen eller satellit-IoT. Det avgör också vad resilience-budskapet
visar.

## Data, rättigheter och känslighet

### G-09 Datarättigheter och villkor saknas (Hög)

Varje källa har egna villkor för licens, attribution och kommersiell visning, och
inget av det nämns:

- Copernicus/Sentinel-data.
- Vägar, byggnader, vatten och skog, till exempel OpenStreetMap under ODbL eller
  Lantmäteriets data.
- Väderdata, till exempel SMHI.
- Satellitpositioner, till exempel TLE-data.
- CesiumJS och Cesium ion, och eventuella 3D Tiles från tredje part.

`CONTEXT.md` listar licenser och attribution som en öppen fråga. One-pagern bör inte
gå vidare till en byggplan förrän varje lager har en känd källa, licens och
attributionsrad. Villkoren behöver kontrolleras mot källa.

### G-10 Riktig kritisk infrastruktur i ett brandscenario (Hög)

Lagret "Infrastructure – Elstationer, vägar och annan kritisk infrastruktur" (rad 49)
och exemplen "Substation 17", "Road 66" och "Industrial site" (rad 247–249) pekar på
verkliga objekt. Riksväg 66 går genom Västerås. Att visa verkliga elstationer i ett
scenario om hot kan beröra informationssäkerhet och säkerhetsskydd för samhällsviktig
verksamhet, även om enstaka uppgifter finns öppet. Detta behöver bedömas mot källa och
av behörig person innan riktiga objekt visas. Ett säkert alternativ är fiktiva eller
anonymiserade infrastrukturobjekt i ett verkligt landskap, tydligt märkta.

### G-11 Är en brand från Sentinel realistisk? (Medel, kräver kontroll mot källa)

Sentinel-2 har en återbesökstid på flera dagar, och data blir inte tillgänglig i
realtid. En brand som "upptäcks från rymden" inom minuter är därför inte ett
realistiskt Copernicus-flöde idag. Det flödet är just det som Dacreo ombord ska
illustrera, och det är simulerat. One-pagern bör skilja på tre saker:

- vad Copernicus faktiskt kan leverera i demon, till exempel historiska eller nyliga
  bilder av området;
- vad som är den simulerade framtidsförmågan (detektion ombord med Dacreo);
- vilka befintliga tjänster som ger nära realtid, till exempel värmeanomalier från
  MODIS eller VIIRS via FIRMS, eller Copernicus EMS. Deras tillgänglighet och villkor
  behöver kontrolleras mot källa.

Påståendet "NEXT OBSERVATION Mälardalen T - 18:42" (rad 164–166) visar nästa
överflygning. Det är inte en garanterad bildtagning. Detta bör framgå, och "framtida
satellitobservation" står redan som simulerad (rad 351).

### G-12 Partnernamn och tredjepartsnamn (Medel)

- "Dacreo" och "BruhnBruhn" (rad 112–141) används med slogans ("See and compute from
  space"). Relationen mellan dem, Dacreos faktiska förmåga och tillstånd att använda
  namn och logotyper på mässan framgår inte.
- "NATO-data" står som simulerat lager (rad 348). Att visa NATO-namnet i en kommersiell
  demo kan antyda en koppling som inte finns.

`AGENTS.md` förbjuder att hitta på sensorförmågor och kundåtaganden. Partnerns
förmågor bör därför beskrivas som simulerade eller avtalade, när det är klarlagt.

### G-13 Prognosen ser mer precis ut än den är (Medel)

"+60 MIN" visar "predicted fire propagation" och minutprecisa ankomsttider ("42 min",
"31 min", "54 min", rad 247–249). Samtidigt beskrivs modellen som en enkel modell
baserad på vind, vegetation, terräng och avstånd (rad 253–258), och brandförloppet
står som simulerat (rad 352). Minutprecisa värden utan osäkerhet ger intryck av en
validerad modell. Märk prognosen som illustrativ och visa ett intervall eller en
osäkerhet i stället för exakta minuter.

## Genomförande

### G-14 Svarstider för LLM-frågor live (Hög)

"LLM/AI-agent" och "GIS-query från AI" står som riktiga (rad 334–341). Körningar i
instant-ai-design på den här datorn gav 4–7 tokens/s för `qwen3.8:27b`. Ett svar på
100–150 ord tar då ungefär 30–60 s. Det är för långt i en demo på två minuter. Med en
extern modell kräver det nätverk och godkänd extern behandling. One-pagern behöver
bestämma:

- vilken modell som körs och var;
- vilken latens som accepteras;
- att frågor och spatiala anrop kan förberedas eller cachas, men att de ändå körs på
  riktigt när de visas.

### G-15 Mässans nätverk och offlineläge (Medel)

Flera riktiga lager kräver nätverk: satellitpositioner, väderdata, Copernicus-data,
Cesium ion och en eventuell extern LLM. Mässnätverk är ofta instabila. "Mässhärdning"
nämns (rad 392), men inte vad som krävs:

- lokal cache av terräng, tiles och bilder;
- lokal MQTT-broker;
- lokal PostGIS;
- ett offlineläge som behåller den riktiga satellitpositionen via lokalt
  propagerade TLE-data;
- vad som visas när en källa saknas. Rad 224 visar "⚠ Camera unavailable" som ett
  bra mönster för det.

### G-16 MVP-uppskattningen saknar risker och förutsättningar (Medel)

6–8 veckor för 2–3 personer (rad 383–392) är en uppskattning. Den omfattar inte:

- avtal och klarlägganden med Dacreo och BruhnBruhn;
- licensbeslut;
- hårdvara och uppkoppling för nRF91 (SIM, täckning och eventuell NTN, vars stöd i
  den aktuella nRF91-varianten behöver kontrolleras mot källa);
- montrens hårdvara: skärmar, touchskärm och fysisk knapp;
- testmiljö och tid för att öva demon.

Ansvar, budget och tidpunkten för IoTDagen saknas också.

### G-17 Framgångskriterier och målgrupp saknas (Medel)

Det framgår inte vem publiken är, till exempel kommuner, räddningstjänst, försvar
eller industri, eller vad demon ska leda till: leads, möten, partnerskap. Det saknas
också kriterier för när demon är klar att visas. Exempel på sådana kriterier är
körningar utan fel i rad, tid till RESET och beteendet vid avbrott i en källa.

## Övrigt

### G-18 Namn och tonläge (Låg)

- "GOD MODE" och "GOD VIEW" (rad 301–305) och "War Room" kan uppfattas som informellt
  för en professionell publik, till exempel myndigheter eller försvar.
- "COP" (rad 409) används utan förklaring (common operational picture).

### G-19 Språk och dokumentets status (Låg)

- One-pagern blandar svenska och engelska, även i UI-texter. Det bör beslutas vilket
  språk demon visar.
- Rubriken "Ofiltrerad konceptutveckling" och formuleringarna i jagform, som "Jag
  skulle…", visar att dokumentet är ett idéunderlag. `CONTEXT.md` säger redan att
  valen är förslag. En beslutad version bör skilja förslag från beslut.

### G-20 Faktauppgifter att kontrollera (Låg)

"SENTINEL-2 Altitude 786 km, Velocity 7.4 km/s" (rad 161–163) stämmer i storleksordning
med Sentinel-2:s bana, men värdena bör hämtas från banberäkningen i demon och inte
skrivas in fast. ISS och Landsat (rad 153–154) har andra banor. "Sentinel-1" är
radar, inte optisk, och bör presenteras därefter.

## Tidigare observationer

- Repot är korrekt uppsatt med gate-reglerna i `AGENTS.md`, `CLAUDE.md` som länk och
  en `CONTEXT.md` med öppna frågor som stämmer med flera av fynden ovan: scenario,
  källor, live eller simulerat, licenser och spårbarhet.
- Remoten `origin` använder `git@github.com:…`, inte SSH-aliaset
  `github.com-jeryymekjobb` som de andra Techseed-repona använder.
- Projektet är inte registrerat i GUI:t för instant-ai-design
  (`config/workspace-context.md`).
- Idén om en förklarbar AI med en evidenslista (rad 214–225) ligger nära Evidence
  Object i techseed-ai-framework och kan använda dess fält: källa, tid, status och
  integritet.

## Rekommenderad prioritering

1. G-01, G-02, G-03: bestäm och märk vad som är riktigt och simulerat, lager för lager.
2. G-04, G-14: bestäm interaktionsmodell och AI-latens, eftersom de avgör om demon
   fungerar live.
3. G-09, G-10, G-12: datarättigheter, infrastrukturdata och partnernamn innan något
   visas offentligt.
4. G-05–G-08, G-13: en gemensam tidslinje och konsistenta siffror.
5. G-15–G-17: mässhärdning, uppskattning och framgångskriterier.
