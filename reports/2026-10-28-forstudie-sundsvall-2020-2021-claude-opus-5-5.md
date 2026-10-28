# Förstudie: översvämningar i Sundsvall 2020–2021 med havsvattenstånd och sjöväder

Datum: 2026-10-28
Författare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code, på uppdrag av
Techseed. Förstudien granskar underlaget för ett Sundsvallsscenario där regn, vattendrag,
havsvattenstånd och vind från havet möts. Den bygger inget och lägger inga data i repot.
Mätdata hämtades till en tillfällig katalog utanför repot. Den är inte juridisk rådgivning
och inte en bedömning av dammsäkerhet.

## Uppdrag

Användaren beskrev scenariot så här (2026-10-28, i sammandrag):

- Översvämningar i Sundsvall 2020 och 2021: Ljungan, Selångersån och Sidsjöbäcken. 2020
  ska vattnet ha kommit runt Himlabadet och idrottshallen. Om dammen hade brustit hade det
  blivit kritiskt.
- Vid ett läge vill man veta hur mycket regn som kommer det närmaste dygnet.
- Man vill veta havets vattenstånd, eftersom ett högt hav kan dämma upp vattendragen så att
  vattnet inte kommer ut från land. Användarens exempel var en höjning på 1 m som i
  Göteborg och att vind från Polen höjer vattenståndet.
- Vinden: hur stark den är från havet.
- Sjöväder och havsnivå ska in i Sundsvallsscenariot, med vattenstånd tre dagar framåt.
- Hur vattenstånd och vind mäts vid lotsstationerna, som man kommer åt på kartor.

Uppgifterna om 2020, 2021, Himlabadet och dammen är **användarens** och har inte gått att
bekräfta i öppna källor (se [Händelserna](#händelserna-2020-och-2021)).

## Sammanfattning

- **Tillägg efter användarens möte 2026-10-28: händelserna är troligen 2023.** På mötet
  beskrev deltagare, bland dem några som byggde vallarna, en översvämning driven av regn i
  fjällen och en av regn lokalt vid Sundsvall, och att man behövt veta hur flödet skulle bli
  för att veta hur höga vallarna skulle vara. Att händelserna inträffat är inte ifrågasatt,
  bara när. Mätdata sätter tidpunkterna: **augusti 2023** (lågtrycket Hans) har både
  fjällflödet i Ljungan och lokalt regn och högt hav, och **3–4 november 2023** har det
  kraftigaste lokala regnet 2023 och räddningstjänstens barriärer. EFAS sparar sina
  flödesprognoser (se [Två typer av händelser](#två-typer-av-händelser-vallar-och-flödesprognoser)).
- **Händelserna 2020 och 2021 är inte bekräftade i öppna källor.** Sökningar i SVT, Sveriges
  Radio, ST, SMHI och MSB gav dokumenterade översvämningar i Sundsvall 2001 (då Sidsjödammen
  hotade att brista), 2015 (skyfall i centrum), 2018 (vårflod i Selångersån) och 2023, men
  inget om Himlabadet eller Sidsjöbäcken 2020–2021. Användaren behöver ange datum eller en
  källa. SMHI:s mätningar ger kandidatdagar (nedan).
- **Riktade sökningar i pressen gav en händelse 2020: 20–23 februari.** ST skrev den 22
  februari 2020 om "spöregn, snöväder och ovanligt högt vattenstånd" med SMHI:s klass
  1-varning för högt vattenstånd i norra Bottenhavet och bilder från Selångersån. Spikarna
  nådde 97,7 cm kl. 15 UTC den dagen, det högsta 2020, och Sentinel-1 passerade 16:05. För
  december 2020 och augusti 2021 hittades inga notiser (se
  [Pressen](#pressen-riktade-sökningar-2026-10-28)).
- **Platsen stämmer.** Enligt OSM ligger Himlabadet och Sporthallen (62,394 N, 17,289 E)
  cirka 1,7 km nedströms Sidsjödammen (62,379 N, 17,281 E) längs Sidsjöbäcken. Kommunens
  skyfallsplan (2018) säger att "ett dammbrott vid Sidsjön kan få katastrofala konsekvenser
  för nedströms bebyggelse" och att Sidsjöverket med dricksvattenfunktioner ligger direkt
  nedströms.
- **Bästa kandidaten i mätdata är 27–28 december 2020.** Sidsjö D mätte 30,0 och 25,0 mm
  två dygn i rad, temperaturen vid Sundsvall-Timrå flygplats låg på +3–4 °C, Brämön hade
  sydostlig vind 12–15 m/s, alltså från havet, och havet vid Spikarna nådde 58,7 cm i
  RH2000. Det är just den kombination användaren beskriver, men det är inte bekräftat att
  något översvämmades då.
- **Flöden:** Ljungan hade inga höga flöden 2020–2021. De höga åren är 2001, 2018 och
  2023. Selångersån och Sidsjöbäcken saknar mätningar, men SMHI:s modell S-HYPE ger dygnsflöden
  från 2010. Där är **30 december 2020 årets högsta flöde** i båda, över
  medelhögvattenföringen, och vårfloden 2018 den högsta sedan 2010 (se
  [Flöden](#flöden-i-ljungan-selångersån-och-sidsjöbäcken)).
- **Havsvattenståndet mäts och finns öppet.** SMHI:s station Spikarna (2061) utanför
  Sundsvall har timvärden i RH2000 från 1968 till idag (CC BY 4.0). Det högsta är 155 cm
  (14 januari 1984). Demon har redan verktyget för det från Falsterbo
  (`tools/fetch_smhi_sea_level.py`, `SEA_LEVEL_STATIONS`).
- **"Lotsstationerna" är Sjöfartsverkets ViVa.** ViVa visar realtidsvärden från 185
  stationer. Runt Sundsvall finns vind vid Gubben, Sundsvalls hamn, Brämön och Lungö, och
  vattenstånd vid Spikarna. ViVa:s vattenstånd vid Spikarna är SMHI:s mätning, så historiken
  finns hos SMHI. ViVa:s eget gränssnitt ger bara senaste värdet. Någon dokumenterad licens
  eller historik har inte hittats.
- **Prognoser av vattenståndet som de såg ut 2020–2021 finns inte att hämta.** SMHI:s
  vattenståndsprognos (NEMO-Nordic, 60 timmar, var 6:e timme) finns bara i realtid. Arkivet
  är analysdata, inte gamla prognoser. Copernicus Marines Östersjöprognos (upp till 10 dygn)
  har arkiv från november 2021, också det analyser. En "prognos tre dagar framåt" i ett
  historiskt scenario måste därför antingen vara uppmätt i efterhand och sägas vara det,
  eller vara en ny modellkörning. Det senare är inte rimligt här.
- **Regnet närmaste dygnet finns som prognos.** MET Norways arkiv med MEPS-körningar täcker
  2020 och 2021, och demon hämtar och visar dem redan (`tools/fetch_met_forecasts.py`).
- **Satellitdata, alla sensorer:** decemberstormen 2020 har Sentinel-1-radar över land
  två gånger om dygnet och Sentinel-1:s vind över havet vid samma passager, som visar
  sydoststormen. Den har också Sentinel-3:s termiska bilder och MODIS snötäcke. Det är
  för mörkt för synligt ljus. Augusti 2021, vårfloden 2018 och augusti 2023 har dessutom
  klara optiska bilder. 2001 har Landsat och MODIS (se [Satellitdata](#satellitdata)).
- **Dammbrott kan bara visas som ett tydligt märkt "om".** Det finns inget öppet underlag
  för hur vattnet skulle gå vid ett dammbrott. Dammbrottskarteringar kan omfattas av
  sekretess. Det måste kontrolleras.
- Rekommendation, att beslutas: ett **nytt scenario** kring augusti 2023, efter mötet (se
  första punkten), annars kring 20–23 februari eller 27–28 december 2020, med Spikarnas vattenstånd, vind från
  Brämön, MEPS regnprognos och Sidsjö D. Se [Beslut som behövs](#beslut-som-behövs).

## Händelserna 2020 och 2021

### Det som hittades i öppna källor

| År | Händelse | Källa |
|---|---|---|
| 1919 | Vårflod. Banvallen vid Sidsjöbäcken underminerades. | Sundsvallsminnen, SMHI |
| 2001 | 146,5 mm på tio timmar den 27 augusti. Sidsjödammen hotade att brista. Bron över Sidsjöbäcken förstördes 11 september. Selångersån hade ett hundraårsflöde, 90 m³/s. | SMHI, ST |
| 2015 | Skyfall och hagel i centrum. Parkgatan stod en halv meter under vatten. | SVT |
| 2018 | Vårflod i Selångersån och Sättnaån. Ånäsparken i Kovland delvis översvämmad. | SVT, SR |
| 2020 | 22 februari: spöregn, snöväder och ovanligt högt vattenstånd. SMHI:s klass 1-varning för högt vattenstånd i norra Bottenhavet, 80–100 cm över medelvattenståndet. Bilder från Selångersån. | ST (22 februari 2020) |
| 2020 | Parkgatans viadukt översvämmades igen en måndag i början av november. | ST (2 november 2020) |
| 2023 | Ihållande regn den 4 november och källaröversvämningar i Sundsvall, Timrå och Härnösand. | SR |

Inget av detta nämner Himlabadet eller idrottshallen, och inget beskriver ett dammhot 2020
eller 2021. Händelserna kan ändå ha inträffat. Lokala nyheter ligger delvis bakom betalvägg
och räddningstjänstens insatsrapporter är inte öppna.

### Pressen, riktade sökningar 2026-10-28

Efter att kandidatdagarna hittats i mätdata söktes pressen för just de perioderna (SVT,
Sveriges Radio, ST, GP, SMHI:s månads- och årssammanfattningar):

- **20–23 februari 2020:** [ST 22 februari 2020](https://www.st.nu/2020-02-22/bildextra-sporegn-snovader-och-ovanligt-hogt-vattenstand-se-bilderna-fran-den-gra-lordagen/)
  beskriver "spöregn följt av snöväder" i Medelpad och att SMHI:s klass 1-varning för
  högt vattenstånd i norra Bottenhavet uppdaterades på morgonen, med 80–100 cm över årets
  medelvattenstånd. Bildtexten nämner Selångersån. Himlabadet, dammen och skador nämns inte.
- **27–30 december 2020:** ingen notis om Sundsvall. SMHI:s sammanfattning av
  havsvattenståndet 2020 säger att december saknade extrema vattenstånd, och SVT:s
  december-krönika nämner översvämningar och höga flöden bara i södra Sverige.
- **Augusti 2021:** ingen notis om Sundsvall, Sidsjön eller Himlabadet. SMHI:s
  månadssammanfattning nämner andra orter.
- **November 2023:** [SVT 5 november 2023](https://www.svt.se/nyheter/lokalt/vasternorrland/manga-oversvamningar-efter-regnet-over-vasternorrland--5yucih)
  bekräftar vatten i källare i Sundsvall och Härnösand efter helgens regn.

ST ligger delvis bakom betalvägg och sökmotorerna når inte hela lokalpressens arkiv. Att
inget hittats om Himlabadet betyder inte att inget hänt. ST:s arkiv och Räddningstjänsten
Medelpad är de säkraste källorna.

### Kandidatdagar i SMHI:s mätningar

Sidsjö D (127220) är SMHI:s nederbördsstation vid Sidsjön, dygnsvärden. Spikarna (2061)
är vattenståndet i RH2000, dygnets högsta timvärde. Vinden är Brämön A (127130), där en
riktning runt 90–180° kommer från havet.

| Dygn | Regn Sidsjö D | Hav Spikarna (dag före, dag, dag efter) | Vind Brämön | Kommentar |
|---|---|---|---|---|
| 2020-02-22 | 12,9 mm | 83, 98, 83 cm | syd 11–12 m/s 20–21 feb | Plus 5,0 mm 20 feb. +3–6 °C, regn på snö. **Högsta havet 2020, i pressen.** |
| 2020-09-26 | 48,3 mm | 12, 12, 6 cm | nordlig 10–11 m/s | Mest regn 2020, lågt hav |
| 2020-12-28 | 30,0 mm | 57, 59, 28 cm | **sydost 12–15 m/s** | Plus 25,0 mm 29 dec. +3–4 °C. **Regn, hav och vind från havet samtidigt.** |
| 2021-01-11 | 62,8 mm | −0, 51, 63 cm | sydost upp till 18 m/s | −13 till 0 °C, alltså troligen mest snö |
| 2021-08-07 | 45,0 mm | 7, 8, 9 cm | svag | Sommarregn, lågt hav |
| 2021-08-17 | 39,0 mm | 17, 21, 41 cm | nordnordost 10–12 m/s | Plus 27,0 mm 16 aug |

Årets högsta vattenstånd vid Spikarna var 97,7 cm den 22 februari 2020 och 62,9 cm den
12 januari 2021. Ljungan vid Skallböle hade inga höga flöden dessa år: 224 m³/s som mest
2020 och 234 m³/s 2021, mot 593 m³/s 2018 och 449 m³/s 2023.

Selångersån har ingen SMHI-station för flöde, och det har inte heller Sidsjöbäcken.

### Platser

| Plats | Läge (OSM) | Not |
|---|---|---|
| Sidsjödammen | 62,3789 N, 17,2808 E | Utredning för 500-årsregn planerad till 2022 i skyfallsplanen |
| Himlabadet | 62,3940 N, 17,2892 E | Cirka 1,7 km nedströms dammen |
| Sporthallen, Sporthallsbadet | 62,3943 N, 17,2901 E | Intill Himlabadet |
| Sidsjö D (regn) | 62,3808 N, 17,2852 E | Vid dammen |
| Spikarna (vattenstånd) | 62,3633 N, 17,5311 E | Utanför Sundsvallsfjärden |

## Två typer av händelser, vallar och flödesprognoser

Användaren återgav 2026-10-28 ett möte där deltagare, bland dem några som byggde vallarna,
beskrev två översvämningar: en där mycket nederbörd i fjällen ökade flödet i vattendragen
vid Sundsvall, och en där mycket nederbörd lokalt gjorde det. I det ena fallet hade man
velat veta hur flödet skulle bli för att veta hur höga vallarna skulle byggas. Användaren
tvivlar inte på att det hänt, men på när. Tidpunkterna nedan kommer ur mätdata.

### Regn i fjällen: augusti 2023

Ljungan börjar i Härjedalens fjäll. Flödestoppen vandrade nedför älven:

| Station | Topp | Datum | Rang |
|---|---|---|---|
| Lännässjön (20035), fjällen | 208 m³/s (144 % av MHQ) | 9 aug | 10:e högsta sedan 1973 |
| Östavallselet (20036) | 308 m³/s (161 %) | 13 aug | 10:e högsta sedan 1976 |
| Skallböle KRV (1650), nära Sundsvall | 449 m³/s (133 %) | 14 aug | 16:e högsta sedan 1956 |

- Från fjällen till kusten tog det cirka fem dygn, den tid då vallar hinner byggas om man
  vet vad som kommer.
- Vid mynningen gick cirka 500 m³/s ut i havet den 15 augusti, mot normalt 138 m³/s, och
  vattnet ställde till problem vid Öhns camping i Matfors (SVT). SMHI hade gul varning för
  höga flöden i Ljungan från Holmsjön till Kvissleby 2–16 augusti (ST, SR). SMHI räknar
  Ljungan till vattendragen med flöden av lång återkomsttid i augusti 2023.
- Samtidigt **lokalt**: Sidsjö D mätte 22,4 mm den 6 augusti och 48,0 mm den 10 augusti,
  och **havet stod 76,7 cm vid Spikarna den 8 augusti**. Augusti 2023 har alltså högt hav,
  lokalt regn och fjällflödet efter varandra.
- Indalsälven var inte särskilt hög (Bergeforsen 80 % av MHQ). Vårfloden 2018 var högre i
  Ljungan, men den var snösmältning.
- Inget om vallbygge längs Ljungan 2023 hittades i pressen. SMHI skriver att militären
  byggde vallar där biflödena mynnar i nedre Ljungan **2001**.

### Regn lokalt: 3–4 november 2023

- Sidsjö D mätte 27,0 mm den 3 november och **50,7 mm den 4 november**, det högsta dygnet
  2023. Havet var lågt, cirka 20 cm vid Spikarna.
- [ST 4 november 2023](https://www.st.nu/2023-11-04/hart-regn-har-orsakat-manga-oversvamningar-i-medelpad):
  räddningstjänsten "satt ut barriärer" på Östermovägen i Skönsmon för att leda om vatten
  som strömmade från Södra bergets sluttningar och prioriterade viktig infrastruktur. SR och
  SVT rapporterade vatten i källare i Sundsvall, Timrå och Härnösand.
- Sidsjöbäcken hade 3,3 m³/s den 6 november enligt S-HYPE, 133 % av MHQ. Himlabadet,
  Sporthallen och Sidsjöbäcken nämns inte i pressen. Skönsmon ligger på andra sidan centrum.

Vilken plats vallarna stod på kan mötets deltagare avgöra.

### Flödesprognoser som de såg ut

- **EFAS** (Copernicus översvämningsvarning för Europa, modellen LISFLOOD, cirka 1,5 km
  rutor) sparar sina operativa prognoser för vattenföring. Data äldre än 30 dagar är fritt
  tillgängliga i Copernicus Early Warning Data Store (`efas-forecast`), som kräver ett
  konto. Från vilket datum arkivet börjar och hur väl Ljungan och Selångersån följs i
  modellen är inte kontrollerat.
- Demon skulle då kunna visa vad prognosen sa till exempel den 9 augusti 2023 om flödet vid
  Skallböle den 14 augusti, jämfört med vad som kom.
- SMHI:s egna flödesprognoser (HYPE) har inget öppet arkiv.
- En vallhöjd kräver en vattennivå, inte ett flöde. Kopplingen kan göras med kommunens och
  MSB:s karteringar av 100-årsflöden i Ljungan och Selångersån, som visar hur långt vattnet
  når vid ett givet flöde. Det är en tolkning och ska sägas vara det.

## Mätdata

### Havsvattenstånd (SMHI, öppna data)

- Spikarna (2061): timvärden i RH2000 från 1968-09-24 till idag, aktiv. Det högsta uppmätta
  är 155 cm den 14 januari 1984. Över 90 cm sedan 2015: 99,2 cm (januari 2015), 104,8 cm
  (januari 2017) och 97,7 cm (februari 2020).
- Draghällan (2062) längre söderut är nedlagd. Lunde (35209) vid Ådalen och Skagsudde 2
  (35138) är aktiva men längre bort.
- Licens: CC BY 4.0, som i Falsterbo.

### Vind och sjöväder (SMHI och Sjöfartsverket)

- SMHI:s stationer med vindens riktning och styrka per timme: Brämön A (127130, ute i havet,
  bäst för vind från havet), Sundsvall-Timrå flygplats (127310) och Lungö A (128390).
- Sjöfartsverkets **ViVa** har realtidsvärden från 185 stationer. Svaret från ViVa:s
  tjänst 2026-10-28 visade:
  - Gubben (153): medelvind S 5,8 m/s, byvind 6,7 m/s.
  - Sundsvalls hamn (191): vind.
  - Brämön (SMHI, 208) och Lungö (SMHI, 202): vind.
  - Spikarna (SMHI, 109): vattenstånd 23 cm, referens "MVY" (medelvattenytan, inte RH2000).
- ViVa:s tjänst (`services.viva.sjofartsverket.se`) ger bara senaste värdet. Den nya
  webbappen från november 2024 visar historik, men hur långt bakåt och om den får laddas ner
  är inte klarlagt. Villkoren för att använda ViVa i en demo har inte hittats. Det behöver
  frågas Sjöfartsverket om ViVa ska användas.
- Slutsats: för en historisk händelse räcker SMHI:s data. ViVa passar för ett framtida
  läge med realtidsdata.

### Vattendrag och regn

- Ljungan: Skallböle KRV (1650) har dygnsflöden även 2020–2021. Ljungan mynnar söder om
  Sundsvall i Njurunda och var inte hög dessa år.
- Selångersån och Sidsjöbäcken: inga SMHI-stationer, men SMHI:s modell S-HYPE ger
  dygnsflöden för båda från 2010 till i går (se [Flöden](#flöden-i-ljungan-selångersån-och-sidsjöbäcken)).
  Kommunens 100-årsflöde för Selångersån finns redan i
  `data/sundsvall2026/municipal/selangersan-100ar.geojson`.
- Regn: Sidsjö D (dygn) och kommunens mätare med timvärden hos SMHI (Bällsta, Essvik,
  Fillan, Heffners) samt Brämön A. Kommunens mätare går en timme efter (backlog).

## Flöden i Ljungan, Selångersån och Sidsjöbäcken

### Ljungan, uppmätt (SMHI)

Ljungan är reglerad. Flödena vid kraftverken är det som släpps fram, inte naturliga
flöden. MHQ är medelvärdet av årens högsta dygnsflöde.

| Station | Serie | MQ | MHQ | Högsta |
|---|---|---|---|---|
| Skallböle KRV (1650), närmast Sundsvall | 1956 – feb 2026 | 126 m³/s | 355 m³/s | 1 050 m³/s (2000) |
| Torpshammar KRV (1471), längre upp | 1943 – feb 2026 | 38 m³/s | 110 m³/s | 314 m³/s (2000) |

Högsta flöde i varje period:

| Period | Skallböle | Torpshammar |
|---|---|---|
| Aug–sep 2001 | **825 m³/s, 14 sep** (232 % av MHQ, tredje högsta året sedan 1956) | **220 m³/s** (200 %) |
| Sep 2015 | 105 m³/s (30 %) | 42 m³/s |
| Vårfloden 2018 | **593 m³/s, 11 maj** (167 %, sjätte högsta året) | **188 m³/s** (171 %) |
| Sep 2020 | 91 m³/s (26 %) | 49 m³/s |
| Nov 2020 | 196 m³/s (55 %) | 53 m³/s |
| Dec 2020 – jan 2021 | 205–226 m³/s (58–64 %) | 64–73 m³/s |
| Vår 2021 | 234 m³/s (66 %) | 59 m³/s |
| Aug 2021 | 123 m³/s (35 %) | 44 m³/s |
| Aug 2023 | **449 m³/s, 14 aug** (126 %) | 93 m³/s (85 %) |
| Nov 2023 | 214 m³/s (60 %) | 79 m³/s |

**Ljungan hade inga höga flöden 2020 eller 2021.** De höga åren i perioden är 2001, 2018
och 2023.

### Selångersån och Sidsjöbäcken, modellerat (SMHI S-HYPE)

SMHI:s Vattenwebb ger dygnsflöden från modellen S-HYPE för varje delavrinningsområde från
2010 till i går. Hämtat 2026-10-28 för Selångersåns utlopp i havet (SUBID 12849, 449 km²)
och Sidsjöbäcken (SUBID 12794). Det är **modellvärden, inte mätningar**. SMHI anger en
modellosäkerhet på 0,28 för Selångersån. Utan station i ån är värdena inte korrigerade mot
någon mätning. MHQ är här medel för 2010–2025, alltså bara 16 år.

| | MQ | MHQ | Högsta 2010–2026 |
|---|---|---|---|
| Selångersån, utloppet | 4,4 m³/s | 29,0 m³/s | 64,3 m³/s, 7 maj 2018 |
| Sidsjöbäcken | 0,3 m³/s | 2,5 m³/s | 4,7 m³/s, 8 maj 2018 |

| Period | Selångersån | Sidsjöbäcken |
|---|---|---|
| Sep 2015 (skyfall i centrum) | 0,9 m³/s | 0,1 m³/s |
| Vårfloden 2018 | **64,3 m³/s, 7 maj** (221 % av MHQ, högst sedan 2010) | **4,7 m³/s** (192 %, högst sedan 2010) |
| Feb 2020 | 16,8 m³/s, 23 feb (58 %) | 1,3 m³/s (52 %) |
| Sep 2020 | 11,7 m³/s (40 %) | 1,6 m³/s (64 %) |
| Nov 2020 | 16,0 m³/s (55 %) | 1,1 m³/s (46 %) |
| **Dec 2020** | **32,0 m³/s, 30 dec** (110 %, årets högsta) | **3,0 m³/s, 30 dec** (121 %, årets högsta) |
| Jan 2021 | 26,4 m³/s 1 jan, sedan 10,6 (36 %) | 2,2 m³/s 1 jan |
| Vår 2021 | 23,6 m³/s (81 %) | 1,9 m³/s (77 %) |
| Aug 2021 | 12,4 m³/s, 18 aug (43 %) | 1,9 m³/s (77 %) |
| Aug 2023 | 25,4 m³/s (88 %) | 2,3 m³/s (92 %) |
| Nov 2023 | 29,0 m³/s, 6 nov (100 %) | **3,3 m³/s, 6 nov** (133 %) |

Vad modellen säger:

- **December 2020 gav årets högsta flöde 2020 i både Selångersån och Sidsjöbäcken**, över
  medelhögvattenföringen. Det stöder att 27–28 december 2020 var en verklig högflödeshändelse.
  Toppen i ån kom den 30 december, två dygn efter havets topp på 59 cm vid Spikarna, som
  då hade sjunkit till under 30 cm. Om uppdämning från havet spelade roll beror alltså på
  timmarna 28–29 december.
- **2021** nådde Selångersån som mest 26,4 m³/s, den 1 januari, som en fortsättning på
  december 2020. Augusti 2021 gav 43 % av MHQ i ån och 77 % i bäcken.
- **2018** är högst i hela serien. Det stämmer med den dokumenterade vårfloden.
- **Skyfall i staden syns inte.** Modellen ger 0,9 m³/s för september 2015. Ett skyfall på
  en halvtimme över gator och dagvatten ligger utanför vad en dygnsmodell för hela
  avrinningsområdet visar. Det gäller även en kort topp i Sidsjöbäcken.
- Som jämförelse rapporterade ST 90 m³/s i Selångersån i september 2001, ett hundraårsflöde.
  Modellserien börjar 2010 och har inte 2001.

## Prognoser

| Vad | Källa | Finns för 2020–2021? | Not |
|---|---|---|---|
| Regn närmaste dygnet | MET Norway MEPS (THREDDS) | Ja, antagligen. MEPS-arkivet täcker 2018–2026 och demon använder det redan. | Måste kontrolleras för exakt period |
| Vind och byar | MET Norway MEPS | Ja, som ovan | Demon visar redan vindskifte och byvind |
| Havsvattenstånd 60 h | SMHI NEMO-Nordic | Nej. Bara realtid, arkivet är analyser | Öppna data. Hur filerna hämtas är inte klarlagt. |
| Havsvattenstånd upp till 10 dygn | Copernicus Marine BALTICSEA_ANALYSISFORECAST_PHY_003_006 | Nej. Arkiv från november 2021, och då analyser | Kräver konto, som Falsterbo steg 7 |
| Vågor | Copernicus Marine, Östersjöns vågmodell | Återberäkning finns | Kräver konto |

Användarens krav på "vattenstånd tre dagar framåt" kan därför uppfyllas på tre sätt, att
välja mellan:

1. **Uppmätt i efterhand**: visa Spikarnas uppmätta vattenstånd 72 timmar framåt från
   klockan, märkt "uppmätt i efterhand, inte en prognos". Det är enkelt och ärligt, men
   det visar mer än man visste då.
2. **Analysdata som "facit"**: samma idé med SMHI:s eller Copernicus analyser. Det ger inget
   mer än mätningen vid en station.
3. **Realtidsläge**: i ett framtida "nu"-läge hämtas SMHI:s 60-timmarsprognos och ViVa
   direkt. Det passar inte ett historiskt scenario och kräver nätverk på mässan.

## Satellitdata

Kontrollerat 2026-10-28 i Planetary Computers STAC-katalog, samma som demons
hämtverktyg använder, för Sentinel-1 GRD, Sentinel-2 L2A och Landsat Collection 2 L2.
Sökområdet är centrala Sundsvall från Sidsjön till Selångersåns mynning (17,20–17,40 E,
62,36–62,42 N). Molnandelen är **hela scenens**. Hur molnigt det var just över staden är
inte kontrollerat. Det görs med SCL-lagret när en bild väljs, som i Falsterbo.

Allmänt gäller:

- Sentinel-1 (radar) ser genom moln och mörker. 2016–december 2021 flög både 1A och 1B, så
  det finns en passage nästan varje dag. Efter december 2021 finns bara 1A, och glesare.
- Sentinel-2 och Landsat (optiska) är oanvändbara i november–januari på 62° N, eftersom
  solen står för lågt och dagarna är korta. Det syns i tabellerna: inga bilder alls runt jul
  2020.
- Landsat 7 har randiga bilder efter maj 2003 (SLC-off). År 2001 är bilderna hela.

### 1. Användarens perioder 2020–2021 och kandidatdagarna i mätdata

| Period | Sentinel-1 | Sentinel-2, bästa | Landsat, bästa |
|---|---|---|---|
| 17–27 feb 2020 (hav 98 cm 22 feb) | 13 passager, bl.a. **22 feb 16:05** (en timme efter havets topp), 23 feb 05:30 | 24 feb 12 %, 26 feb 20 % | **L7 27 feb 0 %**, L8 26 feb 3 %, L7 25 feb 6 % |
| 19 sep – 3 okt 2020 (48 mm 26 sep) | 10 passager, bl.a. 27 sep 05:22 (dagen efter) | 23 sep 9 % (före), 3 okt 31 % | Inga under 70 % |
| 20 dec 2020 – 4 jan 2021 (regn, sydoststorm, hav 59 cm) | 17 passager, bl.a. 27 dec 05:14 och 16:30, 28 dec 05:06 och 16:21 | **Inga** (mörker) | **Inga** |
| 5–19 jan 2021 (sydoststorm, snö) | 14 passager, bl.a. 11 jan 16:05, 12 jan 05:30 | 14 jan 78 % | Inga |
| 31 jul – 14 aug 2021 (45 mm 7 aug) | 13 passager, bl.a. 7 aug 05:06 och 16:22 | 4 aug 13 % (före), **12 aug 2 %** (efter) | L7 8 aug 16 % (SLC-off) |
| 10–24 aug 2021 (66 mm 16–17 aug) | 13 passager, bl.a. 17 aug 05:23, 18 aug 05:14 och 16:30 | **12 aug 2 %** (före), 22 aug 48 % | L8 23 aug 39 % |

### 2. Händelser som hittades i källor och data

| Period | Sentinel-1 | Sentinel-2, bästa | Landsat, bästa |
|---|---|---|---|
| 20 aug – 20 sep 2001 (146,5 mm 27 aug, Sidsjödammen) | Fanns inte | Fanns inte | **L5 25 aug 21 %** (två dygn före), **L5 10 sep 12 %**, L7 24 aug 45 % |
| 29 aug – 12 sep 2015 (skyfall 5 sep) | 5 passager, bl.a. 6 sep 05:22 (dagen efter) | 8 sep 15 % | L8 30 aug 16 %, **L8 8 sep 10 %** |
| 10 apr – 25 maj 2018 (vårflod i Selångersån) | 40 passager | Många klara: **10 maj 0 %**, 30 apr 2 %, 15 maj 2 % m.fl. | L7 10 apr 0 %, 19 maj 0 % (SLC-off) |
| 26 okt – 9 nov 2020 (Parkgatan 2 nov) | 13 passager, bl.a. 2 nov 05:22, 3 nov 05:14 | 7 nov 23 % | Inga |
| 1–20 aug 2023 (Ljungan 449 m³/s 13 aug, hav 77 cm 8 aug) | 7 passager (bara 1A), bl.a. 9 aug 05:06, 14 aug 05:15 | **17 aug 1 %**, 19 aug 2 %, 14 aug 14 % | L9 14 aug 7 %, L9 5 aug 16 % |
| 28 okt – 11 nov 2023 (regn 4 nov) | 5 passager, bl.a. 6 nov 05:15 och 16:31 | Inga under 77 % | Inga |

### Andra satellitburna sensorer

Satellitdata är här alla satellitburna sensorer: radar, optiska och termiska, vind över
havet från radar och scatterometer, altimetri, mikrovåg och geostationära satelliter.
Kontrollerat 2026-10-28 i Planetary Computer och, för Sentinel-1:s vindprodukt och
Sentinel-3 OLCI 2023, i Copernicus Data Spaces katalog.

| Period | Sentinel-1 OCN, vind över havet | Sentinel-3 OLCI / SLSTR | Sentinel-3 altimetri (SRAL) | MODIS snö och yttemperatur |
|---|---|---|---|---|
| 25 aug – 12 sep 2001 | Fanns inte | Fanns inte | Fanns inte | Varje dag |
| 4–7 sep 2015 | Ingen | Fanns inte | Fanns inte | Varje dag |
| 25 apr – 15 maj 2018 | 22 passager | OLCI nästan varje dag, SLSTR flera gånger om dagen | 28 apr, 6 maj | Varje dag |
| 20–24 feb 2020 | 20 feb 05 och 16, 22 feb 16, 23 feb 05, 24 feb 05 | Varje dag | 23 feb 19:28 | Varje dag |
| 25–28 sep 2020 | 27 sep 05, 28 sep 05 och 16 | Varje dag | 26 sep 19:28 | Varje dag |
| 1–4 nov 2020 | 2 nov 05, 3 nov 05 och 16, 4 nov 05 och 16 | Varje dag | Ingen | Varje dag |
| 26–30 dec 2020 | **26 dec 05 och 16, 27 dec 05 och 16, 28 dec 05 och 16, 30 dec 16** | SLSTR (termisk) varje dag, OLCI inte (mörker) | Ingen | Varje dag |
| 10–13 jan 2021 | 11 jan 16, 12 jan 05, 13 jan 05 | SLSTR varje dag | 12 jan 19:28 | Varje dag |
| 6–9 aug 2021 | 6 aug 05 och 16, 7 aug 05 och 16 | Varje dag | 6 aug 19:27 | Varje dag |
| 15–19 aug 2021 | 18 aug 05 och 16, 19 aug 05 och 16 | Varje dag | 16 aug 19:26–19:29 | Varje dag |
| 6–15 aug 2023 | 9 aug 05 och 16, 14 aug 05 | OLCI varje dag (Copernicus Data Space), SLSTR | Ingen | Varje dag |
| 3–6 nov 2023 | 6 nov 05 | OLCI varje dag (Copernicus Data Space) | Ingen | Varje dag |

- **Sentinel-1 OCN** ger vindens styrka och riktning över havet ur radarbilden, med cirka
  1 km rutor. Den visar vinden från havet utan att vara beroende av en enda station.
  Produkten är fri i Copernicus Data Space med samma villkor som Sentinel-1 i övrigt.
- **Sentinel-3 SLSTR** är termisk och ser i mörker. Sentinel-3 OLCI och MODIS är optiska
  med 300 m respektive 250–500 m upplösning. De visar molnen och snön över avrinningsområdet
  men inte enskilda gator.
- **Sentinel-3 SRAL** mäter havsytans höjd längs ett spår. Spåren passerar Sundsvallsbukten.
  Om mätningen nära kusten går att använda är inte kontrollerat.
- **MODIS snö (10A1)** visar snötäcket varje dag sedan 2000, användbart för vårfloden 2018 och
  för att se om nederbörden i december 2020 och januari 2021 föll på snö.
- **Inte kontrollerat än:**
  - Meteosat (MSG från 2004): molnmask och molntoppar, som demon redan visar i Sundsvall 2026.
  - ASCAT på Metop: vind över havet från 2007, via Copernicus Marine eller OSI SAF. Kräver konto.
  - GPM IMERG: regn från satellit. Planetary Computers sökning gav inga träffar, och
    Sundsvall ligger norr om 60° N, där IMERG bygger på färre passager.
  - Kommersiell radar (ICEYE m.fl.): arkiv från 2018, avgiftsbelagt.
  - Om Copernicus krishanteringstjänst (EMS) kartlade någon av händelserna.

### Vad det betyder för valet av händelse

- **20–23 februari 2020** har radar över land och vind över havet den 22 februari kl. 16,
  en timme efter havets topp, ett altimeterspår den 23 februari och klara Landsat- och
  Sentinel-2-bilder 24–27 februari. Den är också den enda kandidaten 2020–2021 som pressen
  beskriver.

- **27–28 december 2020** har radar över både land och hav. Sentinel-1 passerade två gånger
  om dygnet, och dess vindprodukt visar sydoststormen över havet vid varje passage. SLSTR
  ger termiska bilder och MODIS snötäcket. Synligt ljus saknas. Radarn visar öppet vatten
  där det inte brukar finnas, men inte vatten under is eller snö. Det kräver en kontroll
  av bilderna.
- **Augusti 2021** har klara optiska bilder före (12 augusti, 2 %), radar och vind över
  havet dagen efter regnet, och ett altimeterspår 16 augusti. Havet var lågt, så
  uppdämningen från havet kan inte visas där.
- **Vårfloden 2018** är bäst täckt av alla perioder: radar och havsvind varje dag, många
  klara Sentinel-2-bilder, Sentinel-3 och MODIS snö. Det är en dokumenterad översvämning
  i Selångersån.
- **Augusti 2023** har klara bilder efter toppen i Ljungan, och havet stod 77 cm vid
  Spikarna fem dygn innan.
- **2001** har två nästan klara Landsat 5-bilder före och efter och MODIS varje dag, men
  ingen radar.

## Uppdämning från havet

Användarens resonemang är att ett högt hav hindrar vattendragen från att rinna ut.
Följande är **allmän kunskap och antaganden** som behöver kontrolleras innan demon säger
något om effekten:

- Vind från syd och sydost som ligger på länge pressar vatten norrut i Bottenhavet och höjer
  vattenståndet längs Norrlandskusten. Dagarna 27–28 december 2020 och 11–12 januari 2021
  hade sydostlig vind vid Brämön och de högsta vattenstånden de vintrarna.
- Selångersån mynnar via Selångersfjärden i Sundsvallsfjärden. Hur långt upp ett högt hav
  påverkar vattennivån i ån och i Sidsjöbäcken är inte utrett. Användarens exempel på 1 m
  avser Göteborg. Vid Spikarna har vattenståndet aldrig nått över 155 cm i RH2000.
- Demon kan visa havet och vattendragen samtidigt och säga att högt hav kan försvåra
  avrinningen. Den kan inte räkna ut uppdämningen utan en hydraulisk modell.

## Dammen

- Skyfallsplanen 2018 (kommunfullmäktige, KS-2018-00474) prioriterade en utredning av om
  Sidsjödammen klarar ett 500-årsregn till år 2022. Om den gjordes och vad den visade är
  inte känt.
- En dammbrottskartering har inte hittats öppet. Sådana underlag kan vara sekretessbelagda.
  Det ska inte antas att de får användas.
- Det som kan visas utan sådant underlag: dammen, Sidsjöbäcken och byggnaderna nedströms
  med en PostGIS-fråga, märkt "exponerat om dammen brister, illustrativt, ingen
  dammbrottsmodell". Det är en tolkning och ska sägas vara det.

## Vad som blir simulerat eller syntetiskt

- Nivågivare i Sidsjöbäcken och vid Himlabadet, eftersom det inte finns några mätningar där.
  Som i Flen kan de följa ett regn eller ett flöde, märkta syntetiska.
- Vattenståndet framåt, om val 1 ovan, märkt som uppmätt i efterhand.
- Dammens läge: bara som "om", aldrig som en beräknad flodvåg.

## Beslut som behövs

1. **Händelsen.** Efter mötet rekommenderas **augusti 2023** (fjällflödet i Ljungan, lokalt
   regn och högt hav efter varandra, EFAS-prognoser, klara satellitbilder efteråt), med
   **3–4 november 2023** som rent lokalt fall med barriärer. Som jämförelse står 2020 kvar,
   där valet stod mellan **20–23 februari 2020**, det högsta havet 2020, beskrivet i
   pressen och med radar, havsvind och klara bilder efteråt men ett måttligt flöde i ån,
   och **27–28 december 2020**, med årets högsta flöde i ån, regn och vind från havet men
   lägre hav, ingen notis i pressen och radar men inget synligt ljus. **Vårfloden 2018** har flest sensorer och klara optiska
   bilder. **Augusti 2023** är också väl täckt.
   2021-08-16–18 är ett sommaralternativ med lågt hav.
2. **Nytt scenario eller tillägg.** Rekommendation: ett nytt scenario `sundsvall2020`
   med Sundsvall 2026 som mall, eftersom karta, DEM, terräng och OSM-lager kan delas. Ett
   tillägg till `sundsvall2026` vore möjligt för havet, men händelsen 2026 var ett
   sommarskyfall med lågt hav.
3. **Vattenstånd tre dagar framåt.** Val 1, 2 eller 3 ovan. Rekommendation: val 1.
4. **ViVa.** Bara som källa till kunskap här, eller ska Sjöfartsverket tillfrågas om villkor
   och historik för ett realtidsläge?
5. **Dammen.** Visa den som ett märkt "om" med byggnader nedströms, eller inte alls tills
   kommunen tillfrågats?

## Källor

Mätdata hämtades 2026-10-28 från SMHI:s öppna data:
`opendata-download-ocobs.smhi.se` (parameter 6, station 2061),
`opendata-download-metobs.smhi.se` (parameter 5 station 127220, parameter 3 och 4 station
127130, parameter 1 station 127310) och `opendata-download-hydroobs.smhi.se` (parameter 1,
station 1650). Värdena ovan räknades ur dem.

- SMHI Vattenwebb, modelldata per område (S-HYPE, version `release_autumn_2025-2`),
  `vattenwebb.smhi.se/webservices/download/api/v1/excel/land/basin/bySubid/12849` och
  `…/12794`, hämtade 2026-10-28. Torpshammar KRV (1471) hämtades som Skallböle.
- Sjöfartsverket, ViVa, stationslista och senaste värden:
  `services.viva.sjofartsverket.se:8080/output/vivaoutputservice.svc/vivastation/`
  (hämtad 2026-10-28). Adressen kommer från det inofficiella projektet
  [sjofartsverket_viva-component](https://github.com/patrickribbing/sjofartsverket_viva-component).
- [Sjöfartsverket: Ny uppdaterad ViVa](https://sjofartsverket.se/sv/om-oss/nyheter-och-press/nyheter/uppdaterad-viva)
- [SMHI: Havsvattenstånd, datamängder](https://www.smhi.se/data/hav-och-havsmiljo/havsvattenstand)
- [SMHI: NEMO-Nordic, historiska analysdata (data.europa.eu)](https://data.europa.eu/data/datasets/7d86fb3d-a341-4aee-91bc-5ef342d958c3?locale=en)
- [Copernicus Marine: BALTICSEA_ANALYSISFORECAST_PHY_003_006](https://data.marine.copernicus.eu/product/BALTICSEA_ANALYSISFORECAST_PHY_003_006/description)
- [Sundsvalls kommun: Skyfallsplan för Sundsvalls kommun (2018)](https://sundsvall.se/download/18.235b114b198e57425bc6aaa7/1647599619414/Skyfallsplan-f%C3%B6r-Sundsvalls-kommun.pdf)
- [SMHI: 2001 – Översvämningar i Sundsvallstrakten](https://www.smhi.se/kunskapsbanken/hydrologi/historiska-oversvamningar/2001---oversvamningar-i-sundsvallstrakten)
- [ST: Detta hände 2001](https://www.st.nu/sundsvall/detta-hande-2001/)
- [Sundsvallsminnen: Översvämningen 1919](https://sundsvallsminnen.se/handelser/oversvamningen-1919/)
- [SVT: Historiskt skyfall i Sundsvall (2015)](https://www.svt.se/nyheter/lokalt/vasternorrland/askovader-slog-till)
- [SVT: Selångersån svämmar över sina bräddar](https://www.svt.se/nyheter/lokalt/vasternorrland/selangersan-svammar-over-sina-braddar)
- [ST: Femtio blöta år på Parkgatan](https://www.st.nu/sundsvall/bildextra-femtio-blota-ar-pa-parkgatan-i-sundsvall-se-bilderna-ur-sts-arkiv/)
- [ST: Höga vattenflöden i Ljungan (11 augusti 2023)](https://st.nu/2023-08-11/hoga-vattenfloden-i-ljungan)
- [SVT: Översvämningar längs Ljungan](https://www.svt.se/nyheter/lokalt/vasternorrland/oversvamningar-i-ljungan-ljusare-prognos-framat)
- [SR: Högt vattenflöde i Ljungan](https://www.sverigesradio.se/artikel/hogt-vattenflode-i-ljungan-kommunen-varnar-batagare)
- [SMHI: Augusti 2023, en blöt månad med höga flöden](https://www.smhi.se/klimat/klimatet-da-och-nu/manadens-vader-och-vatten-i-sverige/manadens-vader-och-vatten-i-sverige/2023-09-06-augusti-2023-hyd-en-blot-manad-med-hoga-floden-och-manga-oversvamningar)
- [ST: Hårt regn har orsakat många översvämningar i Medelpad (4 november 2023)](https://www.st.nu/2023-11-04/hart-regn-har-orsakat-manga-oversvamningar-i-medelpad)
- [Copernicus EWDS: EFAS forecasts](https://ewds.climate.copernicus.eu/datasets/efas-forecast)
- SMHI:s flöden för Lännässjön (20035), Östavallselet (20036), Järpströmmen (1495) och
  Bergeforsen (2185), hämtade 2026-10-28 som Skallböle.
- [ST: Spöregn, snöväder och ovanligt högt vattenstånd (22 februari 2020)](https://www.st.nu/2020-02-22/bildextra-sporegn-snovader-och-ovanligt-hogt-vattenstand-se-bilderna-fran-den-gra-lordagen/)
- [SMHI: Havsvattenstånd 2020](https://www.smhi.se/klimat/klimatet-da-och-nu/arets-vatten/vattenaret/2021-09-03-havsvattenstand-2020)
- [SVT: Många översvämningar efter regnet över Västernorrland (5 november 2023)](https://www.svt.se/nyheter/lokalt/vasternorrland/manga-oversvamningar-efter-regnet-over-vasternorrland--5yucih)
- [P4 Västernorrland: Ihållande regn orsakade översvämningar (4 november 2023)](https://www.sverigesradio.se/artikel/ihallande-regn-orsakar-oversvamningar)
- Satellitscener: Microsoft Planetary Computer STAC
  (`planetarycomputer.microsoft.com/api/stac/v1`), samlingarna `sentinel-1-grd`,
  `sentinel-2-l2a`, `landsat-c2-l2`, `sentinel-3-olci-lfr-l2-netcdf`,
  `sentinel-3-slstr-lst-l2-netcdf`, `sentinel-3-sral-wat-l2-netcdf`,
  `sentinel-3-sral-lan-l2-netcdf`, `modis-10A1-061`, `modis-11A1-061` och `gpm-imerg-hhr`,
  sökta 2026-10-28.
- Sentinel-1 OCN och Sentinel-3 OLCI 2023: Copernicus Data Space Ecosystem, OData-katalogen
  (`catalogue.dataspace.copernicus.eu/odata/v1/Products`), sökt 2026-10-28.
- Lägen ur OpenStreetMap (ODbL), ur demons lokala `data/sundsvall2026/osm/`.
