# Förstudie: översvämningsscenarier för Flens kommun

Datum: 2026-10-21
Författare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code, på uppdrag av
Techseed. Förstudien underlagsgranskar två planerade scenarier, ett för Flens tätort
och ett för hela kommunen. Den bygger inget. Den är inte juridisk rådgivning.

## Uppdrag

Flens kommun vill bland annat mäta vattenflöden. Demon ska därför få ett
översvämningsscenario byggt på en verklig händelse. Det ska finnas i två varianter: ett
för Flens tätort och ett för hela kommunen. Flödessensorerna är simulerade. Förstudien
utgick från vintern 2024 som huvudkandidat och stormen Hans i augusti 2023 som reserv.

## Sammanfattning

- **Vintern 2024** har de bästa mätdata. Hallbosjön nådde 41,0 m³/s den 8 mars, det
  nionde högsta flödet på 94 år, och det finns klara satellitbilder. Men de
  konsekvenser som är dokumenterade inträffade nästan alla **utanför Flens kommun**. I
  Flen finns bara en bildtext om "översvämning vid Bolmängen vintern 2024".
- **Hans 2023** gav Flen svagt underlag och inga dokumenterade konsekvenser. Den
  kandidaten avskrivs.
- Sökningen gav två bättre förankrade kandidater:
  - **December 2019 (tätorten).** Kommunen varnade för höga flöden, Åpromenaden
    stängdes och vägen vid Orrhammarbron stod under vatten. Det finns ingen klar optisk
    satellitbild nära toppen, bara radar.
  - **Maj–juni 2021 (kommunen).** Väg 53 översvämmades söder om Sparreholm. Det finns
    klara Sentinel-2- och Landsat-bilder från den 28 maj, dagen efter.
- **Ingen myndighet har kartlagt översvämning från sjöar och vattendrag i tätorten.**
  MCF:s kartering av Nyköpingsån når bara kommunens södra del. För tätorten finns
  Länsstyrelsens skyfallsscreening, som är fri att använda (CC0), och kommunens egen
  skyfallskartering, som kräver tillstånd.
- Rekommendation, att beslutas: **tätorten → december 2019** och **kommunen → maj–juni
  2021**. Vintern 2024 kan behållas för kommunen om större flöden och en längre
  berättelse väger tyngre än lokal förankring. Se [Beslut](#beslut-som-behövs).

## Mätdata

### Vattenflöde (SMHI, öppna data, CC BY 4.0)

Stationer nära Flen, med avstånd från tätorten:

| Station | Nr | Avstånd | Anmärkning |
|---|---|---|---|
| Hebylund Kvarnsjön | 2614 | 15 km | liten, närmast |
| Sibro 2 | 2587 | 21 km | |
| Hallbosjön | 1273 | 23 km | Nyköpingsån, sedan 1933 |
| Övre Hyndevad | 138 | 30 km | Eskilstunaån |

Det finns också regleringsdammar och kraftverksstationer i närheten: Christineholms
regleringsdamm (2020), Kila övre (2595) och Åkers krutbruk (2249).

Högsta dygnsflöde per period, ur SMHI:s kontrollerade arkiv, kontrollerat 2026-10-21:

| Station | Dec 2019 – 10 jan 2020 | 15 maj – 15 jun 2021 | 20 jan – 20 mar 2024 |
|---|---|---|---|
| Hebylund | 1,51 (19 dec) | 1,93 (28 maj) | 1,93 (17 feb) |
| Sibro 2 | 5,28 (24 dec) | 13,8 (1 jun) | 17,2 (27 feb), högsta sedan 2012 |
| Hallbosjön | 23,4 (10 jan, fortfarande stigande) | 24,1 (11 jun) | 41,0 (8 mar), 9:e högsta på 94 år |
| Övre Hyndevad | 90,0 (16 dec) | 101 (2 jun) | 97,4 (28 feb) |

Enhet: m³/s. Hans 2023 gav 105 m³/s vid Övre Hyndevad den 16 augusti. Ingen av
stationerna ligger i Flens tätort, och sjöarna och ån genom tätorten saknar egen station
hos SMHI.

### Väder (SMHI)

- Timnederbörd finns från Floda A (96040, 11 km) och Eskilstuna A. Dygnsvärden finns
  bland annat från Granhed D (96060), Sköldinge (96050) och Hälleforsnäs D (96090).
- Vintern 2024 vid Floda A: 38,6 mm i januari, 46,6 mm i februari (varav 17,4 mm den 16
  februari) och 13,0 mm i mars. Snödjupet vid Granhed sjönk från 24 cm den 18 januari
  till 6 cm den 30 januari, och från 10 cm den 15 februari till 0 den 19 februari. Det
  tyder på regn på snö och snösmältning. Det är en tolkning, inte något SMHI anger.
- Hans 2023: 41 mm vid Hälleforsnäs.
- Nederbörden för december 2019 och maj 2021 är inte hämtad än.

## Satellitdata

Sökningen gjordes i Planetary Computer, i rutan 16,2–17,0° O, 58,9–59,25° N. Optiska
bilder räknas som klara vid mindre än 30 % moln i hela scenen, vilket inte garanterar
att Flen är molnfritt.

| Period | Sentinel-1 (radar) | Klar Sentinel-2 | Klar Landsat |
|---|---|---|---|
| Dec 2019 | 46 passager | 10 dec, 31 dec, 4 jan | inga |
| Maj–jun 2021 | 34 passager | 28 maj (2 %), 2 jun, 5 jun m.fl. | 28 maj (L8), 29 maj (L7, 0 %) |
| 22 jan – 17 mar 2024 | 27 passager | 5 feb, 17 feb | 8 mar (L8, Hallbosjöns topp), 17 mar delvis |

**Meteosat:** alla tre perioderna ligger före Meteosat-12:s Lightning Imager (från juli
2024) och instabilitetsindex (från januari 2025). Scenarierna kan få molnmask och
molntoppar från Meteosat-10/11 (MSG), men inte blixtar eller K-index. FCI-bilderna är
fortfarande blockerade i väntan på EUMETSAT-licensen.

## Kommunens geodata

Det här kommer från underagentens genomgång av gis.flen.se (ArcGIS Server 11.3):

- **`Skyfallskartering`** (MapServer) innehåller vattendjup, flödeshastighet och
  flödesriktning för 100- och 500-årsregn. Den är i EPSG:3010 och täcker Flens tätort,
  ungefär 16,549–16,669° O och 59,026–59,091° N. Tjänsten har ingen WMS, men export och
  query fungerar.
- WMS-tjänsterna `Primarkarta_Flen_SVAAB` och `Primärkarta_Flen` är verifierade.
- **Ingen licens anges.** Innan något visas offentligt måste vi fråga kommunen
  (samhallsbyggnad@flen.se).
- Skyfallskarteringen gäller kraftigt regn, inte höga flöden i sjöar och vattendrag.
  Den kan visa var vatten samlas i tätorten, men den är inte en bild av någon av
  händelserna ovan.

**Vattentjänstplanen (2025-02-03):** 17 VA-anläggningar har skyfallsrisk och 7 behöver
åtgärdas. Deras namn är sekretessbelagda. De simulerade sensorerna får därför **inte**
placeras eller namnges som om de vore verkliga pumpstationer eller VA-anläggningar.
Huvudman är Flen Vatten och Avfall AB med Sörmland Vatten och Avfall AB. Reningsverken
ligger i Flen, Sparreholm, Bettna och Vadsbro.

## MCF:s och Länsstyrelsens översvämningskarteringar

Det här kommer från underagentens kontroll av de öppna tjänsterna, rapporterna och
metadata, gjord 2026-10-21. Täckningen inom kommunen är bedömd mot en förenklad
kommungräns från OpenStreetMap, så kanterna är ungefärliga.

**MCF (före detta MSB):**
- Det finns en **"Översvämningskartering utmed Nyköpingsån"** från 2015 (MSB dnr
  2014-3378, rapport https://rib.msb.se/filer/pdf/31231.pdf). Den sträcker sig från
  Högsjö till mynningen. Inom Flens kommun når den bara den södra delen: **Yngaren,
  Forssjön och Långhalsens norra strand**. Den täcker **inte** Flens tätort, Båven,
  Valdemaren, Skiren, Sparren, Orrhammarsjön, Sparreholm eller Malmköping.
- **I WMS:en finns Nyköpingsån inte i det vanliga lagret för 100-årsflöde**, med
  WMS-namnet "13". Den finns i det klimatanpassade 100-årsflödet ("12") och i beräknat
  högsta flöde ("9"). WMS:en är
  `https://gis-tjanster.mcf.se/arcgis/services/Oversvamningskarteringar/karteringar/MapServer/WMSServer`
  och kräver ingen inloggning. WMS och REST numrerar lagren olika.
- **Licens:** enligt metadata finns "inga begränsningar" och "inga tillämpliga villkor".
  Ingen CC-licens anges.
- **Skyfall:** MCF har ingen egen skyfallskartering för Flen. MCF:s översiktslager
  markerar ändå Flen som "Skyfallskartering genomförd", men utan att säga vilken
  studie det gäller.

**Länsstyrelsen Södermanland:**
- **Riskbild 2 Södermanland (Rapport 2013:24), avsnitt 8.2.2, beskriver Flens tätort.**
  Där finns lågpunkter vid Sveaparken och norr om järnvägen, och vattnet rinner av mot
  Gårdssjön, Bjuren och Flensån.
- Länsstyrelsen har en skyfallsscreening med **"Skyfall – Flödesvägar"** och
  **"Skyfall – Låga områden"**. Den har licensen **CC0 1.0** och täcker hela länet. Den
  finns som ArcGIS REST
  (`ext-geodata-lokala-visning.lansstyrelsen.se/arcgis/rest/services/LSTD/LstD_Klimat_EXT/MapServer`,
  lager 0 och 1) och som shapefil. WMS:en svarar med HTTP 400.
- Det finns ingen kartering av höga flöden och inga högvattenlinjer för Flens sjöar.
  Det finns heller ingen riskhanteringsplan för Flen.

**SMHI:**
- I SVAR 2022 ligger Flens tätort i delavrinningsområdet "Båven" inom
  Nyköpingsåns huvudavrinningsområde. Det finns som WFS och zip under CC BY 4.0.
- Vattenwebb har S-HYPE-modellerade flöden per delområde. Där finns också en zip för
  hela Flens kommun, men vilken version av S-HYPE som används anges inte.
- Det finns en nedlagd station, **2252 Varbro**, vid 59,03° N, 16,52° O, nära
  tätorten. Jag har inte kontrollerat vilka år den har data för.
- SMHI:s station Hallbosjön (1273) ligger vid 58,859° N, 16,699° O, mellan Yngaren och
  Långhalsen. Den ligger alltså nedströms Yngaren och inte vid Sparreholm.

**Följder för scenarierna:**
- **Tätorten:** ingen myndighet har kartlagt översvämning från sjöar och vattendrag där.
  Det som finns för att visa var vattnet tar vägen är Länsstyrelsens CC0-screening, som
  kan visas utan att fråga, kommunens skyfallskartering, som kräver tillstånd, och
  beskrivningen i Riskbild 2.
- **Kommunen:** MCF:s klimatanpassade 100-årslager och lagret för högsta flöde kan visas
  i söder, vid Yngaren och Forssjön. Händelserna i maj 2021 vid väg 53 och i december
  2019 i tätorten ligger däremot utanför det karterade området.

## Dokumenterade händelser (media och kommunen)

| Datum | Plats | Vad | Inom kommunen |
|---|---|---|---|
| 18 dec 2019 | Flens tätort | Kommunen varnade för höga flöden. Åpromenaden stängdes, gångvägen vid Lasarettssjön översvämmades delvis, vägen före och efter Orrhammarbron stod under vatten och ett körfält vid Orrestaö stängdes. | ja |
| 27 maj 2021 | väg 53 söder om Sparreholm | Vägen översvämmades på cirka 100 m. | ja |
| 22 jul 2022 | Götgatan, Flen | En butik översvämmades (skyfall). | ja |
| 28 aug 2022 | Flen | Ett gruppboende drabbades (skyfall). | ja |
| 2 feb 2024 | Kilaån, Trosaån, Eskilstunaån | Gul varning (SVT). | delvis, Eskilstunaån |
| 19–20 feb 2024 | Sörmland | Stängda vägar. | nej |
| 25–27 feb 2024 | Nyköpingsån vid Hallbosjön | Orange varning; TGOJ-banan Sala–Oxelösund hotades (SN). | troligen nej, nedströms Yngaren |
| vintern 2024 | Bolmängen | En bildtext på flen.se; sidan svarar 404. | ja, oklart vad |
| dec 2025 | väg 686 | Översvämning. | ja |

De här uppgifterna är inte kontrollerade mot originalkällorna utöver underagentens
genomgång. Innan något citeras i demon ska varje källa läsas och anges.

## Vad som blir simulerat

- Alla flödessensorer i Flens tätort och i kommunen, med nivå och flöde. De ska märkas
  som simulerade. Kurvorna kan förankras i SMHI-stationernas uppmätta förlopp, skalade
  och tidsförskjutna, och det ska stå i källtexten.
- Inga sensorer får placeras på eller namnges efter verkliga VA-anläggningar (se ovan).
- Utbredningen av översvämningen i tätorten saknar karta för december 2019. Det som
  kan visas är platserna ur kommunens varning, satellitradar (Sentinel-1) och, med
  kommunens tillstånd, skyfallskarteringen som en "så här kan det se ut".

## Beslut som behövs

1. **Händelse för tätorten:** december 2019 (rekommenderas: bäst lokal förankring) eller
   vintern 2024.
2. **Händelse för kommunen:** maj–juni 2021 (rekommenderas: konsekvens inom kommunen
   och klara optiska bilder) eller vintern 2024 (större flöden, men konsekvenserna låg
   utanför kommunen).
3. **Kartor över var vattnet tar vägen:** räcker Länsstyrelsens CC0-screening och MCF:s
   karteringar, eller ska vi också fråga Flens kommun om skyfallskarteringen och
   primärkartan får visas på utställningen?

## Källor

- SMHI Hydrologiska observationer och Meteorologiska observationer, öppna data, hämtade
  2026-10-21.
- Microsoft Planetary Computer STAC (sentinel-1-grd, sentinel-2-l2a, landsat-c2-l2),
  sökt 2026-10-21.
- gis.flen.se (ArcGIS REST), läst 2026-10-21.
- MCF, Översvämningskartering utmed Nyköpingsån (2015), och MCF:s WMS/REST för
  översvämningskarteringar, kontrollerade 2026-10-21.
- Länsstyrelsen Södermanland, Riskbild 2 Södermanland (Rapport 2013:24), och
  LstD_Klimat_EXT (CC0 1.0), kontrollerade 2026-10-21.
- SMHI SVAR 2022 och Vattenwebb, kontrollerade 2026-10-21.
- Flens kommun, vattentjänstplan (2025-02-03).
- SVT och Södermanlands Nyheter (SN), enligt underagentens sökning 2026-10-21.
