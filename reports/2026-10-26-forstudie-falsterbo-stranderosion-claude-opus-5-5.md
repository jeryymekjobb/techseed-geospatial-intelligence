# Förstudie: scenario om stranderosion på Falsterbonäset

Datum: 2026-10-26
Författare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code, på uppdrag av
Techseed. Förstudien granskar underlaget för ett nytt scenario om stranderosion vid
Falsterbo. Den bygger inget och hämtar inga data till repot. Den är inte juridisk
rådgivning.

## Uppdrag

Demon ska få ett scenario om stranderosionen vid Falsterbo. Ingen händelse eller
period var bestämd. Förstudien söker därför kandidathändelser, datakällor och
deras villkor, och vad som måste simuleras.

## Sammanfattning

- **Stormen Babet, 19–21 oktober 2023**, är den bäst förankrade kandidaten. SMHI:s
  station Skanör (30488) mätte 149,5 cm i RH2000 kl. 00 UTC den 21 oktober, ett
  oktoberrekord. Dynerna vid Falsterbo, Ljunghusen och Kämpinge fick branta
  erosionsbranter. Det är dokumenterat med fältmätningar före och efter stormen och
  med foton dagen efter.
- **Stormen Axel, 4 januari 2017**, gav ett högre vattenstånd vid Skanör, 168,6 cm i
  RH2000. Enligt en studie som LU-uppsatsen återger blev skadorna ändå mindre än vid
  Babet, eftersom vågorna var lägre. Det finns bara en klar optisk satellitbild under
  vintern. Axel passar som jämförelse men inte som huvudscenario.
- **Satelliterna ser stormen men knappt erosionen.** Sentinel-1 passerade före,
  under och efter Babet. Klara Sentinel-2-bilder finns den 16 oktober och den 30
  december 2023. Med 10 m pixlar räcker det inte för att mäta dynfotens
  tillbakagång på några meter. Den långsiktiga strandförändringen syns bäst i
  ortofoton med 0,08–0,5 m upplösning.
- **Geodata finns och är avgiftsfria att visa.** SGU:s WMS *Stranderosion och
  geologi, kust* har bland annat dynfot, erosionskänslighet, stranddynamik och
  skyddsåtgärder (`Fees` och `AccessConstraints` är `NONE`). Lantmäteriets
  ortofoton över näset finns för varannat år 2012–2024 under CC BY 4.0, men
  nedladdningen kräver ett Geotorget-konto (se [Datakontroll](#datakontroll-2026-10-26)).
- **Det är en ny sorts händelse.** Demon har idag bara brand och översvämning.
  Erosion behöver en egen bedömning och egna sensorer. Översvämningsscenariernas
  vattenstånd, radar och PostGIS-frågor kan delvis återanvändas.
- Rekommendation, att beslutas: **Babet 2023** som scenario, med ett kort
  stormförlopp och en efterbild. Se [Beslut som behövs](#beslut-som-behövs).

## Kandidathändelser

### Babet, 19–21 oktober 2023 (rekommenderas)

Förloppet enligt SMHI: vattenståndet steg på morgonen den 19 oktober, låg högt i
ungefär två dygn och sjönk under morgonen den 21 oktober. Vid Skanör låg det över
120 cm över medelvattenstånd i nio timmar under kvällen och natten 20–21 oktober.
Högsta värdet var 135 cm över medelvattenstånd, med en återkomsttid på 15–25 år.
Vinden var som starkast 19 m/s vid Skanör/Falsterbo och 26 m/s vid Hanö. SMHI
beskriver svår stranderosion längs sydkusten, underminerade vägar och båthus och
bryggor som spolades ut. SMHI:s sida beskriver inte skadorna på Falsterbonäset
specifikt.

Enligt en LU-uppsats från 2026 (Sennmark, se källor) gäller följande för
Falsterbonäset:

- Stormen gav tydliga erosionsbranter i dynerna vid Ljunghusen och Falsterbo. Det
  finns foton från dagen efter.
- Det finns GNSS-profiler från 2023-03-28 (före), 2023-10-22 och 2023-10-24
  (efter), 2024-09-30, 2025-01-28, 2025-04-22, 2025-10-14 och mars 2026.
- Alla nio profiler med mätning före stormen förlorade mer än 10 m³/m dynsand.
- I mars 2026 hade i genomsnitt 53 % återkommit. Återhämtningen var bäst vid
  Falsterbo i väster och sämst vid Kämpinge i öster. Profil F09 återhämtade sig
  helt (17,6 m³/m), F05 bara till 12 %.
- Vegetationslinjen har flyttat ut mot havet sedan 1939. Den stannade omkring 2012
  och backade kraftigt efter Babet.
- Uppsatsen återger att erosionen i Skåne under Babet var nästan 1,3 miljoner m³
  (Bokhari Irminger m.fl., 2024). Den uppgiften är inte kontrollerad i
  originalkällan.

Uppsatsen är ett studentarbete. Siffrorna bör citeras som dess resultat, inte som
myndighetsuppgifter. LUP märker den som Open Access men anger ingen licens. Vi kan
hänvisa till den, men vi bör inte kopiera figurer eller foton utan tillstånd.

### Axel, 4 januari 2017 (jämförelse)

Skanör mätte 168,6 cm i RH2000 kl. 17 UTC den 4 januari 2017. Det är seriens
högsta timvärde sedan 1992. Enligt Bokhari Irminger m.fl. (2024), som LU-uppsatsen
återger, blev kustskadorna mindre än vid Babet eftersom vågorna var lägre. Mellan
december 2016 och februari 2017 finns bara en klar Sentinel-2-bild (27 januari) och
en klar Landsat-bild (24 februari). Sentinel-1 har 82 passager i perioden.

### Långsiktig trend 1939–2024 (alternativ)

Ortofoton från 14 år mellan 1939 och 2024 visar vegetationslinjens rörelse enligt
uppsatsen. En sådan demo blir en bildserie snarare än ett händelseförlopp. Den
passar dåligt med demons klocka, satellitpassager och larm, men kan bli en efterbild
till Babet.

## Mätdata

### Havsvattenstånd (SMHI, öppna data)

Hämtat 2026-10-26 från SMHI:s API `opendata-download-ocobs` (parameter 6,
timvärden, `corrected-archive`):

| Station | Nr | Läge | Serie |
|---|---|---|---|
| Skanör | 30488 | 55,4168 N, 12,8296 O | 1992-02-17 – 2026-10-22, RH2000 |
| Klagshamn | 2095 | 55,5222 N, 12,8936 O | sedan 1929 |
| Flinten 16 | 35136 | Öresund | sedan 2009 |

- Skanörs högsta timvärden under Babet: 144,9 cm (20 okt 22 UTC), 146,5 (23 UTC),
  149,5 (21 okt 00 UTC) och 145,5 (01 UTC). 16 timvärden låg över 120 cm i RH2000
  mellan den 19 och 21 oktober.
- SMHI:s artikel anger 135 cm över medelvattenstånd. Våra 149,5 cm är i RH2000.
  Skillnaden bör vara stationens medelvattenstånd i RH2000. Det är inte
  kontrollerat.
- Minutvärden finns också (parameter 13).
- Licens: SMHI:s öppna data, CC BY 4.0, som i de andra scenarierna.

### Vind (SMHI)

Falsterbo A (52240, 55,3837 N, 12,8166 O) är aktiv och ligger på näset. Den äldre
stationen Falsterbo (52230) är nedlagd. Data för oktober 2023 är inte hämtade.

### Vågor

SMHI har ingen vågboj i södra Östersjön. Oskarsgrundets boj i Öresund slutade mäta
1999. SMHI:s egna våguppgifter för Babet kommer från en modell. Möjliga källor, som
inte är kontrollerade:

- ERA5:s signifikanta våghöjd (0,5°, timvärden, CDS-kontot som redan används).
  Upplösningen är grov för ett näs.
- Copernicus Marines vågåterberäkning för Östersjön. Den har högre upplösning men
  kräver ett eget konto.

## Satellitdata

Sökningen gjordes i Planetary Computer i rutan 12,78–12,99° O, 55,37–55,45° N.
Optiska bilder räknas som klara vid mindre än 40 % moln i hela scenen, vilket inte
garanterar att näset är molnfritt.

| Period | Sentinel-1 | Klar Sentinel-2 | Klar Landsat |
|---|---|---|---|
| 15 sep – 30 nov 2023 | 29 passager, bl.a. 18 okt 05:25, 21 okt 17:01, 23 okt 05:33 | 21 sep, 16 okt (15 %), 25 nov (17 %) | 21 sep, 8 okt, 16 okt (L8/L9) |
| 21 okt 2023 – apr 2024, under 20 % moln | – | 30 dec (3 %), 19 jan, 8 feb, 16 mar, 8 apr | 28 jan 2024 (L9) |
| dec 2016 – feb 2017 | 82 passager (S1A och S1B) | 27 jan 2017 | 24 feb 2017 |

- Sentinel-1 den 21 oktober kl. 17:01 UTC är den första passagen efter toppen.
  Radarn kan visa översvämmad mark. Den visar inte erosionen.
- Den 16 oktober och den 30 december ger ett par före och efter för Sentinel-2.
  Med 10 m pixlar kan det synas att stranden blev smalare, men inte dynfotens läge.
  Det är inte kontrollerat i bilderna.
- **Meteosat:** Babet ligger före MTG:s Lightning Imager (från juli 2024) och
  instabilitetsindex (från januari 2025). Scenariot kan få MSG:s molnmask och
  molntoppar som de andra, men inte blixtar eller K-index.

## Geodata

### SGU: Stranderosion och geologi, kust

- WMS 1.3.0: `https://resource.sgu.se/service/wms/130/stranderosion-kust-v2`.
  Svarade på GetCapabilities 2026-10-26.
- Lagren omfattar dynfot (`STRANDEROSION_Dynfot`), erosionskänslighet,
  stranddynamik, strandmaterial, bottendynamik, bottenmaterial, kustparallell
  sedimenttransport, gränser mellan sedimentsystem, en erosionsprognos och
  prognoser vid 1, 1,5, 2 och 3 m havsnivåhöjning. Grupplagret Skyddsåtgärder finns
  enligt tjänstebeskrivningen.
- Skala 1:25 000, nominell noggrannhet ungefär 25 m. Bedömningen bygger på
  fältarbeten 2012–2014, och produktbladet uppdaterades senast 2022-11-30.
  Stränderna kan ha ändrats sedan dess.
- `Fees` och `AccessConstraints` är `NONE`. Produktbladet anger ingen licens. Om
  lagren ska visas på mässan och sparas lokalt behöver det kontrolleras med SGU
  (kundservice@sgu.se), eller i SGU:s allmänna villkor för öppna data.

### SGI: Kustens sårbarhet – erosion

- Kartvisaren `https://gis.swedgeo.se/ksi_erosion/` täcker Skånes kustkommuner och
  är gjord tillsammans med SGU.
- SGI beskriver resultatet som en indikation, inte en sanning, och ber om
  källangivelsen "SGI och SGU". Ingen WMS-adress och ingen licens är kontrollerade.

### Lantmäteriet

- Lantmäteriets sida om öppna data anger CC0. Lantmäteriets STAC-katalog för
  ortofoton anger däremot CC BY 4.0 och särskilda användningsvillkor. Vilka
  ortofoton som finns över näset står i [Datakontroll](#datakontroll-2026-10-26).
- LU-uppsatsen använde Lantmäteriets ortofoton från 1939, 1960, 2004, 2007, 2009,
  2012, 2014, 2016, 2018 och 2024 (0,16–1,0 m).

### Vellinge kommun

- Kommunen har egna ortofoton från 1973, 1999, 2017, 2020 och 2022 (0,08–1,0 m)
  enligt uppsatsen. Villkoren är inte kända.
- Skyddsvallen: kommunen har tillstånd för en vall och mur på omkring 21 km runt
  Falsterbonäset, dimensionerad för år 2065. Mark- och miljööverdomstolen
  fastställde tillståndet med skärpta villkor. Hur långt bygget har kommit 2026 är
  inte kontrollerat.
- Kommunen söker nya tillstånd för skötseln av kusten på Falsterbohalvön, bland
  annat tångrensning (Sweco, 2025).
- Enligt kommunen ligger ungefär 95 % av bebyggelsen på näset lägre än 3 m över
  havet.

## Vad som blir simulerat

Det som skulle vara syntetiskt och märkt som det:

- **Nivå- och vågsensorer** vid stränderna i Falsterbo, Ljunghusen och Kämpinge. De
  följer Skanörs uppmätta vattenstånd och, om det beslutas, ERA5:s eller Copernicus
  Marines vågor.
- **Dynfotssensorer** (till exempel ett simulerat avstånd från en fast punkt till
  dynfoten). De får inte ges uppsatsens profilnamn som om de vore verkliga
  instrument.
- Själva bedömningen, till exempel "risk för dynerosion" när vattenståndet och
  vågorna passerar trösklar. Trösklarna är antaganden och måste märkas så.

## Beslut som behövs

1. **Händelse:** Babet 2023 (rekommenderas), Axel 2017, eller en långsiktig trend.
2. **Uppspelning:** till exempel 18–22 oktober 2023 för stormen. Bilderna efter
   (30 december, eller ortofoton 2024) kan visas i en avslutande "efter"-vy, eftersom
   de ligger långt utanför stormveckan.
3. **Kartområde:** bara Falsterbonäset (ungefär 12,78–12,99° O, 55,37–55,45° N),
   eller hela sydvästra Skåne för att jämföra med Klagshamn och Ystad.
4. **Vågor:** ERA5 med det befintliga kontot, eller Copernicus Marine med ett nytt
   konto.
5. **Geodata som får visas:** SGU:s erosionslager och Lantmäteriets ortofoton, efter
   att villkoren har kontrollerats. Kontakt med SGU, SGI och Vellinge kommun om deras
   material ska användas.
6. **Händelsetyp i demon:** en ny typ "erosion" med en egen bedömning, eller ett
   översvämningsscenario med erosionslager. Det första är tydligare men kräver mer
   arbete.

## Beslut 2026-10-26

Användaren valde följande efter förstudien:

| Fråga | Val |
|---|---|
| Händelse | Långsiktig trend, inte Babet ensam |
| Period | 2012–2026, med Axel 2017 och Babet 2023 som händelser |
| Kartområde | Bara Falsterbonäset, ungefär 12,78–12,99° O, 55,37–55,45° N |
| Vågor | Copernicus Marine, Östersjöns vågåterberäkning (`BALTICSEA_MULTIYEAR_WAV_003_015`) |
| Händelsetyp | Översvämningsscenario med erosionslager, ingen ny typ |
| Geodata | SGU:s erosionslager visas först när villkoren är klarlagda |

Vågåterberäkningen och Lantmäteriets ortofoton är kontrollerade i
[Datakontroll](#datakontroll-2026-10-26).

**Tidsskalan.** Motorn går som snabbast 4 dygn per sekund (`MAX_SPEED` i
`scenario_engine.py`). Då tar 2012–2026 ungefär 21 minuter. Demon ska vara 2–3
minuter, så scenariot behöver snabbare uppspelning, och det får inte bromsas vid
satellitpassager.

### Plan

Varje steg får en egen commit och ett eget GO.

1. Dokumentera besluten (den här ändringen).
2. Kontrollera datan, utan att bygga något: Lantmäteriets ortofoton över näset
   2012–2024, klara Sentinel-2-bilder per år 2015–2026, stormarna med högst
   vattenstånd vid Skanör sedan 2012, och Copernicus Marines vågdata för näset.
3. Snabbare uppspelning i motorn: högre `MAX_SPEED`, hastigheter som "1 månad/s"
   och "1 år/s", och en inställning per scenario som stänger av inbromsningen vid
   passager. Med tester.
4. Grunden för scenariot: en scenariomodul av typen översvämning med kartområdet och
   en offlinekarta, Skanörs vattenstånd som diagram och de största stormarna i
   loggen.
5. En bildserie över tid: ortofoton och Sentinel-2 efter datum.
6. SGU:s erosionslager, när villkoren är klarlagda.
7. Vågor från Copernicus Marine.
8. Syntetiska sensorer vid Falsterbo, Ljunghusen och Kämpinge som följer vattenstånd
   och vågor, märkta som syntetiska.

Användaren skaffar ett konto hos Copernicus Marine, som förvaras utanför repot, och
frågar SGU (kundservice@sgu.se) om erosionslagren får visas på mässan och sparas
lokalt.

## Datakontroll 2026-10-26

Steg 2 i planen. Bara metadata och öppna mätserier lästes. Ingenting hämtades till
repot.

### Vattenstånd vid Skanör sedan 2012

SMHI:s timvärden för Skanör (30488, RH2000), 2012-01-01 till 2026-10-22: 128 957
timvärden, varav 127 232 med kvalitetskod G och 1 725 med O. Toppar över 100 cm,
minst tre dygn isär:

| Tid (UTC) | cm, RH2000 |
|---|---|
| 2012-01-06 06:00 | 109,6 |
| 2012-01-14 09:00 | 123,8 |
| 2013-12-02 03:00 | 130,9 |
| 2017-01-04 17:00 | 168,6 (Axel) |
| 2018-10-29 08:00 | 101,1 |
| 2019-01-02 08:00 | 124,1 |
| 2022-01-30 17:00 | 122,6 |
| 2022-02-22 07:00 | 102,3 |
| 2023-10-21 00:00 | 149,5 (Babet) |
| 2024-01-03 10:00 | 114,8 |
| 2024-02-09 18:00 | 106,8 |
| 2025-01-12 07:00 | 106,2 |
| 2025-12-28 04:00 | 104,0 |

Åren 2014–2016, 2020, 2021 och 2026 hittills nådde inte 100 cm. Stormarnas namn,
utom Axel och Babet, är inte kontrollerade.

### Lantmäteriets ortofoton

Lantmäteriets STAC-katalog (`https://api.lantmateriet.se/stac-bild/v1`) har 735
samlingar. Följande täcker rutan 12,78–12,99° O, 55,37–55,45° N:

| Samling | Datum (första rutan) | Upplösning | Rutor |
|---|---|---|---|
| `orto-a2-2012` | 2012-05-01 | 0,25 m | 44 |
| `orto-a2-2014` | 2014-04-27 | 0,25 m | 44 |
| `orto-a2-2016` | 2016-05-09 | 0,25 m | 44 |
| `orto-a2-2018` | 2018-04-12 | 0,25 m | 44 |
| `orto-a2-2020` | 2020-06-02 | 0,16 m | 22 |
| `orto-a2-2022` | 2022-04-16 | 0,16 m | 22 |
| `orto-a2-2024` | 2024-05-21 | 0,16 m | 22 |

Upplösningen är läst ur filsökvägarna (`se0_25`, `se0_16`). Det finns också äldre
samlingar: `orto-skanor-falsterbo-hollviken-2009`, `orto-a-2007`, `orto-a-2010`
och historiska ortofoton från 1940–1959, 1960–1969, 1970–1979, 1990–1999 och
2000–2004. Laserdata och Markhöjdmodell finns i `https://api.lantmateriet.se/stac-hojd/v1`.

- **Licens:** katalogen och varje samling anger CC BY 4.0. Katalogen säger också att
  användningen prövas enligt GDPR och att särskilda användningsvillkor måste
  godkännas. Det stämmer inte med Lantmäteriets sida om öppna data, som anger CC0.
  Vi bör följa det som gäller för nedladdningen, alltså CC BY 4.0 och villkoren.
- **Åtkomst:** filerna på `dl1.lantmateriet.se` svarar 401 utan inloggning (HTTP
  Basic). Det behövs ett Geotorget-konto. Repot har redan stöd för Geotorget-
  inloggning med `LM_USERNAME` och `LM_PASSWORD` (`app/backend/lantmateriet.py`),
  men inte för nedladdning av ortofoton.
- Varje ortofoto är ett vårfoto. Babet (oktober 2023) syns först i 2024 års bild.

### Klara Sentinel-2- och Landsat-bilder per år

Planetary Computer, samma ruta, mindre än 10 % moln i hela scenen. Molnen över
just näset är inte kontrollerade.

| År | Antal | Exempel |
|---|---|---|
| 2012 | 3 (bara Landsat 7) | 2 maj, 25 maj, 13 aug |
| 2013 | 12 (Landsat 7/8) | 1 apr, 7 jul, 23 jul |
| 2014 | 8 (Landsat 8, en Landsat 7) | 13 mar, 29 mar, 19 jul |
| 2015 | 4 Sentinel-2, 12 Landsat | S2: 9 aug, 19 aug, 8 sep, 28 sep |
| 2016 | 10 | 12 maj, 4 jun, 12 sep |
| 2017 | 9 | 11 mar, 27 maj, 9 okt |
| 2018 | 26 | 20 apr, 4 jul, 14 okt |
| 2019 | 18 | 2 apr, 29 jun, 25 aug |
| 2020 | 15 | 9 apr, 15 jun, 23 sep |
| 2021 | 15 | 30 mar, 8 jun, 3 sep |
| 2022 | 13 | 7 mar, 12 aug, 16 okt |
| 2023 | 8 | 19 apr, 13 jun, 21 sep, 30 dec |
| 2024 | 10 | 18 maj, 5 sep, 17 okt, 4 dec |
| 2025 | 24 | 21 mar, 20 maj, 18 aug |
| 2026 | 17 | 6 mar, 25 maj, 22 sep |

Landsat 7 har haft luckor i bilden sedan 2003 (SLC-off), så 2012 års bilder har
ränder. Från 2013 finns Landsat 8. Sentinel-2 finns från 2015.

### Copernicus Marines vågåterberäkning

Lästes ur Copernicus Marines öppna STAC-metadata, utan konto:

- Produkt `BALTICSEA_MULTIYEAR_WAV_003_015`, dataset
  `cmems_mod_bal_wav_my_PT1H-i_202411`, från FMI (`FMI-WAM_CMEMS`).
- Timvärden 1980-01-01 01:00 – 2026-08-01 00:00 UTC. Datasetet släpptes 2024-11-26,
  har inget datum för när det dras tillbaka, och data uppdaterades senast 2026-10-15.
  Uppgiften om att produkten är arkiverad gäller alltså inte detta dataset.
- Rutnät 0,0278° × 0,0167° (1 nautisk mil). Över näsets ruta blir det ungefär 8 × 5
  celler, varav en del på land.
- Variablerna omfattar bland annat signifikant våghöjd (`VHM0`), största våghöjd
  (`VCMX`), medelriktning (`VMDR`) och toppperiod (`VTPK`).
- Licensen anges som `proprietary` med en länk till Copernicus Marines
  licensvillkor. Data är avgiftsfria med konto. Villkoren för att visa och spara dem
  lokalt är inte lästa.
- Datan slutar 2026-08-01, före uppspelningens slut i oktober 2026.

### Följder för planen

- **Steg 5 (bildserien):** ortofotona kräver ett Geotorget-konto och att
  Lantmäteriets villkor för nedladdningen godkänns. Utan konto blir bildserien bara
  Sentinel-2 och Landsat, och de visar inte dynfoten.
- **Steg 7 (vågorna):** vågdatan slutar i augusti 2026.
- **Steg 4:** de 13 topparna ovan räcker för att visa stormarna i loggen.

## Strandlinjekontroll 2026-10-27

Användaren beslutade 2026-10-27 att inte blanda erosion och översvämning (alternativ A):
scenariot behåller grunden av typen översvämning, men visar bara erosionen. Stormarna,
vattenståndet och de syntetiska strandgivarna står kvar som orsak. Inget lager för
översvämmad mark läggs till. Erosionen ska visas som strandlinjens förändring år för år,
med linjer. Kontrollen nedan prövar om Sentinel-2 räcker för det. Inget är byggt.

### Metod

- De råa banden B03, B04, B08 och SCL i alla 13 Sentinel-2-bilder 2015–2026 hämtades i
  bildernas eget UTM-rutnät (zon 33N, 10 m), utan omsampling.
- Sydkusten delades i 209 tvärprofiler, ungefär var 50:e meter, vinkelräta mot
  OpenStreetMaps strandlinje.
- Längs varje profil söktes två linjer:
  - **Vattenlinjen:** där NDWI, (B03 − B08)/(B03 + B08), korsar ett tröskelvärde enligt
    Otsu, med minst 40 m land innanför, så att sandrevlar utanför hoppas över.
  - **Vegetationskanten:** där NDVI, (B08 − B04)/(B08 + B04), når 0,3 innanför vattenlinjen.
    Den motsvarar ungefär dynfoten.
- Vattenståndet vid Skanör i bildögonblicket var −9 till +50 cm (RH2000).
- Skripten låg utanför repot. Banden sparades i den oversionerade
  `data/falsterbo/shoreline-check/`.

### Resultat

- 197–206 av 209 profiler gav en linje i varje bild.
- Linjerna följer stranden vid Falsterbo, Kämpinge och Ljunghusens östra strand.
- Vid Ljunghusens västra del följer de lagunen och våtmarken bakom stranden, inte havet.
- Kämpinges östligaste profiler är oanvändbara.

Vegetationskantens median, i meter innanför OSM:s strandlinje:

| Bild | Falsterbo | Kämpinge |
|---|---|---|
| 2015–2022 | 21–38 | 15–33 |
| Före Babet (21 sep 2023) | 18 | −1 |
| Efter Babet (30 dec 2023) | 43 | 36 |
| 2024–2026 | 43–52 | 34–41 |

- **Vegetationskanten** ligger 10–20 m längre inåt land efter Babet och förblir där 2024–2026.
  Det är 1–2 pixlar, ungefär lika mycket som skillnaden mellan åren före Babet.
  - Bilden efter Babet är en vinterbild, och vissnad vegetation flyttar i sig kanten
    inåt land.
  - Majbilderna 2024–2026 visar ändå samma läge.
- **Vattenlinjen** ändras inte tydligt (5–10 m). Det ligger inom vad vattenståndet och
  pixelstorleken ensamma ger. Bilden före Babet lägger vattenlinjen vid Kämpinge 55 m ut i
  havet, troligen på grund av klart grunt vatten över sandrevlar.
- **Jämfört med Sennmark (2026):**
  - Riktningen stämmer: dynerna backade efter Babet.
  - Återhämtningen vid Falsterbo syns inte. Uppsatsen mäter sandvolym i ortofoton, och
    vegetationen växer tillbaka långsammare. Sentinel-2 kan därför inte bekräfta
    återhämtningen.

### Följder för planen

- Vegetationskanten ur Sentinel-2 kan visas som linjer år för år, om de märks som härledda
  ur Sentinel-2 med osäkerheten ±10–20 m och bara visas vid Falsterbo, Kämpinge och
  Ljunghusens östra strand.
- Vattenlinjen bör inte visas, eftersom den mer speglar vattenståndet än erosionen.
- Ortofotona (0,16–0,25 m) gör förändringen till 50–100 pixlar. Med samma metod kan de
  ersätta satellitlinjerna när ett Geotorget-konto finns (steg 5c).

## Källor

Kontrollerade 2026-10-26.

- SMHI, *Stormflod under Babet oktober 2023*:
  https://www.smhi.se/kunskapsbanken/oceanografi/hogvattenhandelser-i-sverige/stormflod-under-babet-oktober-2023
- SMHI, öppna data för havsvattenstånd: https://www.smhi.se/data/hav-och-havsmiljo/havsvattenstand
  och API:t `https://opendata-download-ocobs.smhi.se/api/version/latest/parameter/6/station/30488.json`
- SMHI, stationslista för vattenstånd:
  https://www.smhi.se/kunskapsbanken/oceanografi/matningar-i-havet/stationslista-vattenstand
- Sennmark, M. (2026), *Post storm dune recovery at the Falsterbo peninsula*, LTH,
  TVVR26/5021: https://lup.lub.lu.se/student-papers/record/9243662
- Bokhari Irminger, S. m.fl. (2024), *Impact and response of storm Babet from a
  Swedish perspective*, https://doi.org/10.18171/1.094115 (inte läst, återgiven
  enligt Sennmark)
- SGU, produktblad *Stranderosion och geologi, kust*:
  https://resource.sgu.se/dokument/produkter/produktblad/stranderosion-kust.pdf
- SGU, tjänstebeskrivning för WMS:
  https://resource.sgu.se/dokument/produkter/stranderosion-kust-wms-beskrivning.pdf
- SGI, *Kustens sårbarhet – erosion*:
  https://www.sgi.se/tjanster-och-verktyg/kartor-och-verktyg/kustens-sarbarhet---erosion
- Lantmäteriet, öppna data:
  https://www.lantmateriet.se/sv/geodata/vara-produkter/oppna-data/
- Vellinge kommun, kustprogram (antaget 2020-09-28):
  https://vellinge.se/siteassets/planer-och-projekt-i-vellinge-kommun/dokument/kustprogrammet/kustprogram_antagen-kf20200928.pdf
- Vellinge kommun, MKB för vattenverksamheter på Falsterbohalvön (Sweco):
  https://vellinge.se/siteassets/boende-miljo-och-trafik/pdf/bilaga-b-mkb-och-tb.pdf
- SVT, om domen för skyddsvallen: https://www.svt.se/nyheter/lokalt/skane/dom-idag
- SVT, om Babet i Skanör–Falsterbo:
  https://www.svt.se/nyheter/lokalt/skane/stormen-babet-har-annu-inte-natt-kulmen
- Copernicus Marine, *Baltic Sea Wave Hindcast*:
  https://data.marine.copernicus.eu/product/BALTICSEA_MULTIYEAR_WAV_003_015/description
- Copernicus Marine, STAC-metadata för datasetet:
  https://stac.marine.copernicus.eu/metadata/BALTICSEA_MULTIYEAR_WAV_003_015/cmems_mod_bal_wav_my_PT1H-i_202411/dataset.stac.json
- Lantmäteriet, STAC-katalog för ortofoton: https://api.lantmateriet.se/stac-bild/v1/
- Lantmäteriet, historiska ortofoton:
  https://lantmateriet.se/en/geodata/geodata-products/product-list/historical-orthophotos
- Microsoft Planetary Computer, STAC-sökning (Sentinel-1 GRD, Sentinel-2 L2A,
  Landsat C2 L2).
