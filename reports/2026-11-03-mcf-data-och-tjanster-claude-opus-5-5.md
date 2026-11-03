# MCF:s data och tjänster

Datum: 2026-11-03
Författare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code, på uppdrag av
Techseed. Rapporten inventerar vad Myndigheten för civilt försvar (MCF, tidigare MSB)
tillhandahåller för data och tjänster, som underlag till MVP:n. Den bygger inget. Den är
inte juridisk rådgivning, och inget i den säger att data får användas.

## Sammanfattning

- MCF har en öppen ArcGIS Server, `https://gis-tjanster.mcf.se/arcgis/rest/services`
  (version 11.5), med 13 mappar. Demon använder i dag bara
  `Oversvamningskarteringar/karteringar`, både som WMS och som REST-fråga
  (`tools/fetch_mcf_flood_maps.py`).
- Flera lager fyller luckor i one-pagern (`docs/mvp/onepager-mvp.md`):
  stabilitetskarteringar för skred och erosion, brandbränsleklassificering för
  brandprognoser, eldningsförbud mot falsklarm, och brandstationer och responstider för
  briefingen.
- Krisinformation.se har ett API med nyheter och VMA i JSON.
- Villkoren för användning är inte bekräftade. Nästan alla tjänster saknar
  upphovsrättstext.

## Metod

Katalogen och varje tjänsts metadata lästes direkt från ArcGIS REST (`?f=json`) den
2026-11-03. Webbsökningar gav övriga tjänster. Ingen tjänst har provats för skrivning.

## Kartserverns tjänster

Alla tjänster är i SWEREF 99 TM (EPSG:3006). Bas-URL:
`https://gis-tjanster.mcf.se/arcgis/rest/services/`. MapServer har normalt även en
WMS-ändpunkt (`.../MapServer/WMSServer`), vilket demon redan använder för karteringarna.

| Mapp | Tjänster (urval) | Innehåll | Möjlig användning i MVP:n |
|---|---|---|---|
| `Oversvamningskarteringar` | `karteringar`, `kustoversvamning`, `malaren`, `Vänern`, `hotkartor`, `hotkartor_2026`, `Hotkartor_2026_op2`, `riskkartor`, `riskkartor_2026`, `Skyfallskarteringar`, `Skyfallskartering_Oversikt` | Översvämningskartering längs vattendrag och kust, hot- och riskkartor, skyfallskarteringar för vissa orter (till exempel Karlstad och Uddevalla) | Översvämning; skyddsvärda objekt inom riskzon |
| `Stabilitetskarteringar` | `Oversiktlig_stabilitetskartering`, `Stabilitetskart_Finkorniga`, `Stabilitetskart_Moran`, `Moränkartering`, `Oversiktliga_stabilitetskarteringar_i_finkorniga_jordarter` | Genomförda översiktliga stabilitetskarteringar per kommun, i finkorniga jordar och morän | Underlag för skred och erosion |
| `Brandbransleklassificering` | `Skogsmark`, `Oppen_mark` | Klassning av brandbränsle | Underlag för brandspridning |
| `Eldningsforbud` | `Eldningsforbud` | Eldningsförbud i kommuner, speglat från länsstyrelsernas karttjänst | Filter mot falsklarm; lägesbild |
| `Raddningstjanst` | `Brandstationer`, `Stationsomraden`, `Stationsomraden_dag`, `Stationsomraden_natt`, `Räddningstjänstgränser`, `Grunddata_responstid_2024`, `Kortidsanalys`, `Kommun_statistik_2024` m.fl. | Brandstationer, stationsområden, gränser, responstider och körtidsanalyser, statistik | Briefing: närmaste resurs och tid till plats |
| `Befolkningsskydd` | `Skyddsrum_kontrollanter` | Skyddsrum som punkter, i två skalintervall | Skyddsvärda objekt |
| `Varmekarteringar` | `Maxtemperatur_2017_2019` … `Maxtemperatur_2023_2025`, `Maxtemperatur_2017_2025`, `Maxtemperatur_vektor_2017_2025` | Maxtemperatur i treårsperioder | Värmebölja |
| `Basdata` | `Kommuner`, `Sveriges_lan`, `Civilområden`, `Polisregioner`, `Militärregioner`, `tatorter_ytor` | Administrativ indelning och tätorter | Ansvarsområden för kontaktlistor |
| `NMD` | `Objekthojd_intervall_5_45`, `Objekttackning_hojdintervall_5_45` | Objekthöjd och täckning från Nationella Marktäckedata, 10 m | Terräng och vegetation |
| `RiksintressenTfC` | `RiksintresseTfC` | Riksintressen för totalförsvarets civila anläggningar och påverkansområden | Försiktighet: se R-CS-06 i `docs/mvp/regelverksregister.md` |
| `Krisinfo` | `VMA_statistik_krisinfo` | VMA-statistik 2017–2023 | Historik |
| `Statsbidrag` | `statsbidragNaturolyckorPunkterExtern` | Punkter för statsbidrag till förebyggande åtgärder mot naturolyckor | Historik |
| `Utilities` | `RasterUtilities`, `Symbols` | Hjälptjänster | Ingen |

## Övriga tjänster

- **Krisinformation.se API**, `https://api.krisinformation.se/v3`. Ändpunkterna
  `/v3/news` och `/v3/vmas` svarade 2026-11-03 med JSON. Möjlig källa i nära realtid för
  händelser in och briefing. Licens inte kontrollerad.
- **Statistik om räddningstjänstens insatser.** Finns i IDA och i statistikdatabasen
  `https://statistik.mcf.se/PXWeb/`. Enligt MCF går den på övergripande nivå tillbaka
  till 1998, och IDA är märkt som öppna data i INSPIRE-geoportalen. Möjligt underlag om
  brandorsaker och falsklarm.
- **Copernicus EMS.** MCF (då MSB) har aktiverat satellitkartering, till exempel vid
  översvämningarna i Dalarna 2018 och i sydvästra Sverige 2020.
- **INSPIRE.** En äldre WMS för översvämningskarteringen, `inspire.msb.se/oversvamning/ows`,
  finns i INSPIRE-geoportalen. Om den finns kvar är inte kontrollerat.

## Inte bekräftat

- **Villkor.** Fältet `copyrightText` är tomt i alla granskade tjänster utom
  skyddsrummen, där det står "MSB". Villkoren för användning och vidarespridning behöver
  kontrolleras på mcf.se eller med MCF (R-GEO-05).
- **Skrivbehörighet.** Flera publika FeatureServers (`Eldningsforbud`,
  `Skyddsrum_kontrollanter`, `Brandstationer`) anger `Create,Update,Delete,Editing` i sin
  metadata. Det kan vara en konfigurationsfråga. Det är inte provat och ska inte provas.
- **Inte undersökt:** RIB och WIS, och om skyddsrumsdata finns som nedladdning utanför
  kartservern.
- **Aktualitet.** Om lagren är aktuella, och hur ofta eldningsförbuden uppdateras, är
  inte kontrollerat.

## Källor

- MCF:s ArcGIS REST-katalog: https://gis-tjanster.mcf.se/arcgis/rest/services
- Krisinformation API v3: https://api.krisinformation.se/v3
- MCF:s statistikdatabas: https://statistik.mcf.se/PXWeb/pxweb/sv/PxData/START__B__B1/B12/
- INSPIRE-geoportalen, IDA: https://inspire-geoportal.ec.europa.eu/srv/api/records/d8ce90cc-6102-42be-b6b3-265a0f70e81a
- INSPIRE-geoportalen, Översvämningskartering visningstjänst: https://inspire-geoportal.ec.europa.eu/srv/api/records/19ea119f-bc3c-404a-b2ef-38badc7e44ea
- Copernicus, EMS i Sverige: https://www.copernicus.eu/en/node/1018
- MCF:s pressmeddelande om insatsstatistik: https://mcf.mynewsdesk.com/pressreleases/statistik-visar-faerre-utryckningar-foer-kommunal-raeddningstjaenst-3437640.pdf
