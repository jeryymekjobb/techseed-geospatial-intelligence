# Förstudie: fyra nya översvämningsscenarier

Datum: 2026-10-15. Underlag sammanställt av Claude Opus 5.5 från fyra parallella
utredningar. Kandidaterna och beskrivningarna av dem kommer från ChatGPT, vidarebefordrade
av användaren, och är kontrollerade här. Allt är läst i öppna källor och API:er den här
dagen; inget är hämtat till `data/` och ingen kod är ändrad.

## Sammanfattning

| Kandidat | Bedömning | Insats | Starkast | Svagast |
|---|---|---|---|---|
| Västernorrland 6–7 sep 2025 | Genomförbar | 5–8 dagar | Länsstyrelsens utredning (2026), Sentinel-1 mitt i förloppet, radar och blixtar, Härnösand och Kramfors | Regnkärnan saknar timstationer, inga MCF-kartor för de små vattendragen, SHK:s utredning är inte klar |
| Boden 16–20 aug 2026 | Delvis, nära genomförbar | 5–8 dagar | Rekordflöden, Sentinel-1 nästan dagligen, länsstyrelsens färdförbud | Ingen SMHI-mätning i Ljusån eller sjöarna, MCF saknar platserna |
| Bohuslän 8 okt 2026 | Genomförbar | 3–5 dagar | Bekräftad av krisinformation.se, Sentinel-1 under larmen, MCF-karta för Örekilsälven | Dagvatten och små vattendrag, molnigt, data ännu inte granskade av SMHI |
| Sundsvall 29 jun 2026 | Delvis | 2–3 dagar | Återanvänder nästan allt från sundsvall2026, radar och blixtar | Mätarna missade skuren (3 mm mot 12–24 mm i radarn), översvämningen bara belagd i en bildtext |

**Rekommenderad ordning:** 1. Västernorrland 2025, 2. Boden 2026, 3. Bohuslän 2026,
4. Sundsvall juni 2026. Västernorrland är bäst dokumenterad, ligger där användaren vill
se Härnösand och Kramfors och har en radarbild mitt i händelsen. Boden har den tydligaste
översvämningen att visa från satellit. Bohuslän är billig men svår att visa från rymden.
Sundsvall i juni är billigast men har minst att visa.

## Avvikelser från ChatGPT:s uppgifter

- Utredningen om Västernorrland 2025 som publicerades 2026 är gjord av Länsstyrelsen
  Västernorrland, inte av SMHI; den bygger på SMHI:s öppna data.
- Det största skyfallet den 29 juni 2026 låg enligt SMHI:s junisammanfattning i Sadiliden i
  Lappland (72,2 mm), inte i Sundsvall; Sundsvall fick ett kortare skyfall.

## Sidofynd att kontrollera i den befintliga demon

Kommunens regnmätare i Sundsvall toppar den 29 juni cirka två timmar efter radarn,
blixtarna, SVT:s "16-tiden" och SMHI:s Brämön A. Kommunens tidsstämplar kan vara i
svensk tid i stället för UTC. Det kan i så fall också förskjuta regnet i
`sundsvall2026` (augusti) med två timmar och bör kontrolleras separat.

## 1. Västernorrland 6–7 september 2025

- **Händelse:** ett regnband från strax söder om Härnösand norrut kvällen 6/9 och morgonen
  7/9, "extrem arealnederbörd". Ett godståg spårade ur på Stambanan genom övre Norrland vid
  Stugusjön väster om Skorped strax före kl. 08, ett timmertåg på övre Ådalsbanan norr om
  Prästmon (Kramfors) på förmiddagen. En person omkom kl. 07 i en trafikolycka i Härnösands
  kommun där vägen spolats bort. Kostnader minst 263 Mkr.
- **Källor:** Länsstyrelsen Västernorrland, *Utredning av konsekvenser av kraftig nederbörd
  6–7 september 2025* (2026:12, 28 aug 2026)
  <https://www.lansstyrelsen.se/download/18.6dcddd7d1a042196bfb8d77/1787894588141/Utredning%20av%20konsekvenser%20av%20kraftig%20nederb%C3%B6rd%206-7%20september%202025.pdf>;
  Mittuniversitetet (RCR) juni 2026; SHK O-7/25, utan slutrapport
  <https://shk.se/engelska/the-swedish-accident-investigation-authority/search-investigation/other-incidents/2025-09-23-incidents-related-to-a-rainstorm-in-vasternorrland-on-7-september-2025>;
  Copernicus EMS EMSR841 (Gottne, Bjästa i Örnsköldsvik).
- **SMHI, dygnet 6/9:** Myckelgensjö 140,0 mm, Kramfors 123,5, Gåltjärn 87,0, Aspeå 72,0
  (septemberrekord), Härnösand 68,7. Timvärden bara utanför kärnan (Lungö A max 10,7 mm/h).
  Flöden höga men inga rekord vid SMHI:s stationer (Stugusjön 21,9 m³/s mot 24,5);
  kraftverksmätare i mindre vattendrag nådde enligt utredningen 75–100+-årsflöden.
  Trafikverkets mätare (Okenberget 146 mm) finns bara i utredningen.
- **Radar och blixtar:** fullständigt radararkiv 4–9/9; 1 268 blixtar 7/9.
- **Satellit:** Sentinel-1 2/9 och 7/9 05:21 UTC (mitt i förloppet), 8/9 med flera; Sentinel-2
  molnigt (32–53 % 5/9 och 10/9, 99–100 % 7/9); Landsat 10/9 58 % moln.
- **Modeller:** MEPS 3–10/9 och ERA5 finns.
- **Kartor:** MCF har Ångermanälven och Indalsälven (100-årsflöde), Moälven och Nätraån
  (högsta flöde), inget vid Härnösand. Trafikverkets Lastkajen kräver ett (gratis) konto;
  annars OSM-järnvägar. Sundsvalls geoserver har inga lager för Kramfors.
- **Verkligt:** SMHI:s regn, flöden, radar och blixtar, satellitbilderna, MEPS, ERA5,
  MCF-ytor och utredningens tidslinje. **Beräknat:** radarns regnsummor per kommun, vatten i
  radarbilden 7/9 mot 2/9. **Simulerat:** nivågivare i småvattendrag och banvallsgivare.
- **Risker:** urspårningsplatserna måste ritas in ur utredningens text, orsaker får inte
  påstås innan SHK är klar, dödsolyckan måste hanteras med respekt.

## 2. Boden och östra Norrbotten 16–20 augusti 2026

- **Källor:** SMHI:s augustisammanfattning, som nämner Buddbyträsket, Bodträsket,
  Svartbyträsket och Ljusån
  <https://www.smhi.se/klimat/klimatet-da-och-nu/manadens-vader-och-vatten-i-sverige/manadens-vader-och-vatten-i-sverige/2026-09-04-augusti-2026---vattenbrist--i-soder-oversvamning-i-norr>;
  Länsstyrelsen Norrbotten, förbud mot färd på vattnet 26–31 aug p.g.a. "extrem
  vattenföring"
  <https://www.lansstyrelsen.se/norrbotten/om-oss/nyheter-och-press/nyheter---norrbotten/2026-08-26-tillfallig-lagstiftning-for-oversvammade-omraden-i-boden.html>.
  SMHI:s orangea varning och Sveriges Radios uppgifter (över 20 vägar) är bara
  andrahandsuppgifter.
- **SMHI:** Boden 147,3 mm 12–24 aug (50,0 mm 17 aug), Brännberg 145,4, Lakaträsk 152,9.
  Timvärdena är luckiga; dygnsvärden plus radarns timprofil bör styra. Nytt rekord i
  Stupforsen (101 m³/s), högsta flöde utanför vårfloden i Råneälven och Kalixälven.
  Bodens station i Luleälven saknar data efter februari 2026; ingen vattenståndsstation
  inom 90 km.
- **Satellit:** Sentinel-1 nästan dagligen, samma bana 12 aug (före) och 18 och 24 aug;
  Sentinel-2 13 aug (13–15 % moln) och 23 aug (6–7 %); Landsat 23 aug 26 %.
- **Kartor:** MCF:s Luleälven-kartering visas inte längre; Ljusån och sjöarna är inte
  karterade. Bodens WebGIS har ingen öppen WMS.
- **Verkligt:** regn, radar, flöden, satellitbilder, MEPS, ERA5, länsstyrelsens förbud.
  **Beräknat:** vattenutbredning ur Sentinel-1 (12 mot 18 aug). **Simulerat:** nivågivarna
  vid sjöarna och Ljusån, utan SMHI-station att följa.

## 3. Bohuslän 8 oktober 2026

- **Källor:** krisinformation.se
  <https://www.krisinformation.se/en/latest/news/oversvamningar-i-vastsverige/>,
  Lysekilsposten (larm från kl. 06, skred vid Väggabacken, vattenskador i Kungshamn,
  Bohus-Malmön, Brastad, Dingle; väg 171 och 900 översvämmade)
  <https://www.lysekilsposten.se/artikel/kraftiga-oversvamningar-vagar-blockerade-och-vatten-i-flera-byggnader/>,
  SVT Väst, Sejfer. Gul varning kom först efteråt enligt Bohusläningen.
- **SMHI (ej granskat):** dygnet 7/10 Heden (Munkedal) 60,4 mm, Grebbestad 41,6, Holane
  38,0; timvärden bara utanför de fyra kommunerna. Örekilsälven i Munkedal steg från 8,9 till
  104 m³/s, under medelhögflödet; små vattendrag steg tiofalt.
- **Satellit:** Sentinel-1 8/10 05:31 under larmen; Sentinel-2 3/10 (29 % moln) och 12/10
  (13–14 %); Landsat 6/10 (6 %).
- **Kartor:** MCF:s Örekils- och Munkedalsälven (2026); inget längs den drabbade kusten.
- **Verkligt:** regn, radar, flöden, satellitbilder, MEPS, ERA5 (hämtbar redan), MCF-ytor,
  tidslinjen. **Beräknat:** radarsummor, återkomsttider. **Simulerat:** givare i dagvatten,
  vägtrummor och källare.
- **Risker:** okontrollerade data kan ändras, dagvatten syns inte från satellit, händelsen
  är färsk.

## 4. Sundsvall 29 juni 2026

- **Källor:** ST 30 juni (skyfall, översvämning i en korsning på Norrmalmsgatan, betalvägg)
  <https://www.st.nu/sundsvall/brander-oversvamningar-och-elavbrott-sa-slog-ovadret-mot-sundsvall/>;
  SVT (blixtnedslag och brand i Gudmundsbyn, strömavbrott i Birsta); SMHI:s
  junisammanfattning (5 989 blixtar 29 juni, största skyfallet i Lappland, inte Sundsvall).
- **Mätningar:** kommunens mätare 1,4–3,0 mm under dagen, radarn 12–15 mm under timmen 14 UTC
  och upp till 24 mm i en pixel; 159 blixtar till marken i kartrutan 13–14 UTC.
- **Satellit:** Sentinel-2 samma morgon (23–27 % moln), Landsat 27 juni (8 %) och 4 juli
  (19 %), Sentinel-1 före och efter. En gatuöversvämning under en timme syns inte.
- **Återanvänds:** nästan allt i `sundsvall2026`: kartor, kommunens skyfallsmodeller och
  dagvattenpunkter, bräddgivarnas simulering och verktygen.
- **Risker:** regnet måste tas från radarn, översvämningen är svagt belagd, skuren är kort.

## Gemensamt för alla

- Den nya tydliga offlinekartan (`tiles/styles/techseed.json`) används; kommunens karta finns
  bara för Sundsvall.
- Offlinekartans hav kräver kustlinjefilen (`coastline/water_polygons.shp`) i kartbygget,
  annars blir öppet hav beige.
- Varje scenario byggs med eget GO och egna commits, med `skane2024` eller `sundsvall2026`
  som mall.
