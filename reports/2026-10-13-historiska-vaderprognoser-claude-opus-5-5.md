# Historiska väderprognoser för demons scenarier

Datum: 2026-10-13
Författare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code, på uppdrag av
Techseed. Undersökningen är steg 1 inför att visa väderprognoser under scenariot, som
stöd för räddningstjänsten och andra aktörer. Den är inte juridisk rådgivning om
datarättigheter.

## Fråga

Vilka väderprognoser och hydrologiska prognoser finns arkiverade **som de utfärdades då**,
inte omanalyser eller observationer, för demons fyra händelser, och på vilka villkor?

| Händelse | Period (UTC) | Område |
|---|---|---|
| Skogsbranden i Västmanland 2014 | 31 juli–14 augusti 2014 | 59,75–60,08 N, 15,85–16,45 E |
| Skogsbranden vid Kårböle 2018 | 12 juli–8 augusti 2018 | 61,75–62,2 N, 14,9–15,8 E |
| Översvämningarna i Skåne 2024 | 20 januari–25 februari 2024 | 55,6–55,98 N, 13,0–13,9 E |
| Regnet i Sundsvall 2026 | 14–22 augusti 2026 | 62,15–62,62 N, 16,9–17,8 E |

## Metod

Tre parallella genomgångar den 2026-10-13: MET Norways THREDDS-arkiv; ECMWF och
Copernicus; NOAA, Open-Meteo och SMHI. Det som är **verifierat** har prövats med
anrop (katalogfiler, OPeNDAP, API-svar, listningar av öppna lagringsplatser). Det som
bara bygger på dokumentation är markerat *(dok.)*. Allt som inte prövats är en öppen
fråga, inte ett faktum.

## Sammanfattning

| Källa | Västmanland 2014 | Kårböle 2018 | Skåne 2024 | Sundsvall 2026 | Villkor |
|---|---|---|---|---|---|
| **MET Norway, AROME-MetCoOp / MEPS** (2,5 km) | **Ja**, verifierat | **Ja**, verifierat | **Ja**, verifierat | **Ja**, verifierat | NLOD / CC BY 4.0, kommersiellt tillåtet |
| MET Nordic efterbehandlad (1 km) | Nej | Bara temperatur | Ja, verifierat | Ja, verifierat | NLOD / CC BY 4.0 |
| ECMWF öppna data (0,25°/0,4°) | Nej | Nej | Ja, verifierat | Ja, verifierat | CC BY 4.0 |
| ECMWF operativt arkiv (MARS) | Ja *(dok.)* | Ja *(dok.)* | Ja *(dok.)* | Ja *(dok.)* | Kommersiellt: avtal, ca 3 000 EUR/år *(dok.)* |
| ECMWF TIGGE | Ja *(dok.)* | Ja *(dok.)* | Ja *(dok.)* | Ja *(dok.)* | CC BY-NC 4.0, **inte kommersiellt** |
| NOAA GFS (AWS, 0,25°) | Nej | Nej | Ja, verifierat | Ja, verifierat | Fri (amerikansk statlig) |
| NOAA GEFS-ensemble (AWS) | Nej | Ja (v11), verifierat | Ja, verifierat | Ja, verifierat | Fri |
| Open-Meteo, arkiverade prognoser | Nej | I praktiken nej | Ja, verifierat | Ja, verifierat | Data CC BY 4.0; kommersiell API-användning kräver betald plan |
| Copernicus brandriskprognos (FWI) | Nej | Nej (bara säsong) | – | – | CC BY 4.0 |
| **EFAS** flödesprognos (1,5–5 km) | Nej | Nej | **Ja**, verifierat | **Ja**, verifierat | CEMS-floods: fri, kommersiellt tillåtet, konto krävs |
| GloFAS flödesprognos | Nej | Nej | Ja, verifierat | Ja, verifierat | CEMS-floods |
| SMHI | Nej | Nej | Nej | Nej | Inga arkiverade prognoser, varningar eller brandriskprognoser som öppna data |

**Slutsats:** MET Norways arkiv är den enda öppna källan som täcker alla fyra
händelserna med prognoser som de utfärdades, i hög upplösning och med villkor som
tillåter kommersiell användning. Det är samma nordiska modellsamarbete (MetCoOp) som
SMHI deltar i. För översvämningarna i Skåne och Sundsvall kompletterar EFAS med
flödesprognoser. Inget öppet arkiv har SMHI:s egna varningar, brandriskprognoser eller
flödesprognoser för händelserna.

## MET Norway (thredds.met.no)

Verifierat med katalogfiler och OPeNDAP-anrop; gittren täcker alla fyra områdena.

| Händelse | Arkiv | Körningar | Prognoslängd | Upplösning |
|---|---|---|---|---|
| Västmanland 2014 | `aromemetcoopstarc` (AROME-MetCoOp, deterministisk; MEPS fanns inte än) | 00/06/12/18 UTC | 0–66 h, varje timme | 2,5 km |
| Kårböle 2018 | `meps25epsarchive` (MEPS, 10 medlemmar, och en efterbehandlad kontrollkörning) | 00/06/12/18 UTC | 0–66 h (medlem 0–1), 0–48 h övriga *(dok.)* | 2,5 km |
| Skåne 2024 | `meps25epsarchive` (deterministisk som NcML-aggregering; medlemmar i timvis förskjutna körningar) | 00/06/12/18 UTC | 0–66 h | 2,5 km |
| Sundsvall 2026 | `meps25epsarchive` | var 3:e timme | 0–66 h | 2,5 km |

- Variabler i alla: temperatur och relativ fuktighet på 2 m, vind på 10 m, byvind och
  ackumulerad nederbörd. Det räcker för brandväder (och ett eget FWI) och för regn.
- Exempel: `https://thredds.met.no/thredds/dodsC/aromemetcoopstarc/2014/07/31/AROME_MetCoOp_00_fp.nc_20140731`,
  `https://thredds.met.no/thredds/catalog/meps25epsarchive/2018/07/12/catalog.xml`.
- MET Nordic (`metpparchive`, 1 km, MEPS plus observationer) finns från 2018-03, men
  2018 bara med temperatur; 2024 och 2026 med vind, byvind och nederbörd, 0–58 h.
- Licens: NLOD och CC BY 4.0 med erkännande av MET Norway,
  <https://www.met.no/en/free-meteorological-data/Licensing-and-crediting>. Filerna från
  2014 saknar licensattribut; erkännandet gäller ändå.
- Förbehåll: körningslistorna är kontrollerade för stickprovsdagar; för övriga dagar är
  bara dagmapparna sedda. OPeNDAP kräver hakparenteser kodade som `%5B`/`%5D`.

## ECMWF och Copernicus

- **Öppna data** (`ecmwf-forecasts` på AWS, verifierat): från 2023-01-18. Skåne 2024
  har 20–31 januari bara i 0,4° (beta), 0,25° från 1 februari. Sundsvall 2026 har IFS
  0,25°, ensemble och AI-modellerna AIFS, fyra körningar per dygn, upp till 15 dygn.
  CC BY 4.0, ingen registrering.
- **Operativt arkiv (MARS)** täcker alla fyra *(dok.)*, men kommersiell åtkomst kräver
  avtal och en avgift på ca 3 000 EUR per år, som kan efterges för forskning eller
  samhällsnytta *(dok.)*. Om arkivet omfattas av ECMWF:s CC BY-beslut från oktober 2025
  behöver bekräftas med ECMWF.
- **TIGGE** täcker alla fyra men är CC BY-NC 4.0: bara icke-kommersiell forskning och
  utbildning. Inte användbart för Techseeds demo.
- **Brandriskprognos (CEMS/EFFIS):** ingen arkiverad prognos som utfärdad för 2014 eller
  2018 i de öppna datalagren (verifierat); operativa prognoser arkiveras i MARS först
  från 2022-08-08 *(dok.)*. Brandrisken kan i stället räknas själv ur arkiverade
  prognoser (MET Norway).
- **EFAS** (`efas-forecast`, verifierat): från 2018-10-11 till ca 30 dagar före idag
  (katalogen når 2026-09-07). Flöde, markfukt och snö, ensembler, 00/12 UTC, upp till
  15 dygn. Skåne 2024 har alla dagar i januari och februari. Licens CEMS-floods: fri,
  kommersiell användning tillåten, konto hos ECMWF, erkännande krävs; "inte en
  översvämningsvarning".
- **GloFAS** (`cems-glofas-forecast`, verifierat): från 2019-11-05, upp till 30 dygn,
  troligen för grov för Skånes små vattendrag.

## NOAA och Open-Meteo

- **GFS** på AWS (`noaa-gfs-bdp-pds`) från 2021-01-01 (verifierat): Skåne 2024 och
  Sundsvall 2026, 0,25°, upp till 16 dygn. Äldre GFS hos NCEI finns bara med 0–6 h
  (verifierat) och är alltså i praktiken analyser.
- **GEFS** på AWS från 2017 (verifierat): Kårböle 2018 (v11, 21 medlemmar), Skåne och
  Sundsvall. **GEFSv12-omprognoser** täcker 2000–2019, alltså Västmanland och Kårböle,
  men är körda i efterhand med en nyare modell, inte utfärdade då.
- **Open-Meteo**: arkiverade prognoser för Skåne 2024 och Sundsvall 2026 med flera
  modeller (bland andra MET Nordic, ICON och GFS), och "Previous Runs" som visar vad som
  prognostiserades 1–7 dygn i förväg (verifierat). Västmanland ger fel om datumintervall;
  Kårböle ger bara data som i praktiken är analys. Datan är CC BY 4.0, men det fria API:t
  är bara för icke-kommersiell användning; Techseed behöver i så fall en betald plan.

## SMHI

Verifierat: SMHI:s öppna data har bara aktuella punktprognoser (`snow1g`; `pmp3g` är
nedlagd), aktuella varningar och aktuella brandriskprognoser. Gridarkivet har AROME
bara som analys (+0 h) och MESAN-analyser. Inga arkiverade flödesprognoser. Historiska
prognoser, varningar eller HYPE-körningar kan troligen beställas via SMHI:s
kundtjänst, sannolikt mot avgift; det är inte kontrollerat.

## Rekommendation

1. **Väderprognoser för alla fyra händelser från MET Norway** (AROME-MetCoOp 2014, MEPS
   2018–2026): vind, byvind, nederbörd, temperatur och fuktighet, 0–66 h, som de
   utfärdades. Märks "Historisk prognos från MET Norway (MetCoOp), utfärdad <tid> –
   inte live".
2. **Brandrisk:** räkna FWI framåt ur samma prognoser, med den brandväderkod demon
   redan har, och märk det som beräknat ur prognosen.
3. **Översvämningar:** EFAS-flödesprognoser för Skåne 2024 och Sundsvall 2026, efter
   kontroll av att vattendragen är stora nog för EFAS rutnät; kräver konto hos ECMWF.
4. **Ensembler** (MEPS 2018–2026, ECMWF öppna data 2024–2026) kan visa osäkerheten.
5. **Fråga SMHI** om historiska varningar och brandriskprognoser för händelserna, om
   demon ska kunna visa vad räddningstjänsten faktiskt fick.

## Öppna frågor

- Om ECMWF:s arkiv (MARS) numera är CC BY för kommersiell återanvändning.
- Om Skånes vattendrag (Hörbyån, Kävlingeån, Rönne å) är stora nog i EFAS.
- MEPS-körningarnas fullständighet för varje dag i perioderna (bara stickprov kontrollerade).
- Om SMHI kan lämna ut arkiverade varningar och brandriskprognoser, och till vilken kostnad.
