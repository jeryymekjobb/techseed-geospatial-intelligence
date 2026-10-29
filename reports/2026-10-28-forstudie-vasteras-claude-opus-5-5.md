# Förstudie: scenarier för Västerås – översvämning, skogsbrand och erosion

Datum: 2026-10-28
Författare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code, på uppdrag av
Techseed. Förstudien granskar om Västerås har kartor och data som räcker för demoscenarier
om översvämning, skogsbrand och erosion, på samma sätt som Sundsvall. Den bygger inget och
lägger inga data i repot. Den är inte juridisk rådgivning. Tjänsterna kontrollerades direkt
2026-10-28.

## Uppdrag

Användaren frågade om Västerås har samma sorts karta som Sundsvall, alltså kommunens egna
kartlager som skyfallsmodeller och baskarta, och om den kan användas för scenarier om
översvämning, skogsbrand och jorderosion. Användaren bad också om ett mejlutkast till staden
om villkoren (se [Bilaga](#bilaga-mejlutkast-till-västerås-stad)).

## Sammanfattning

- **Västerås har motsvarande karttjänster som Sundsvall.** Stadens kartor bygger på samma
  ramverk, Origo, med lager från en öppen ArcGIS-server (`kartor.vasteras.se/arcgis`, 82
  tjänster i mappen `ext`) och bakgrundskartor från en GeoServer (`kartserver.vasteras.se`).
- **Skyfallskartering finns som öppen tjänst.** `ext/sk_skyfall_wms` har två lager:
  maximalt vattendjup vid 100-årsregn och maximalt ytvattenflöde (l/s/m). Djuplagret ritades i
  webbprojektionen (EPSG:3857) över centrala Västerås utan problem. Översiktsplanerna har lagret
  *Skyfallsled*.
- **Villkor anges inte.** Tjänsterna har ingen upphovsrätts- eller licenstext. Användaren
  meddelade 2026-10-28 att Techseed har ok att använda Västerås stads data för internt bruk
  och att inga offentliga visningar är planerade. Mejlutkastet i bilagan behövs bara om
  demon ska visas offentligt.
- **En väldokumenterad översvämning finns: Svartån i september 2023.** SMHI:s station Åkesta
  kvarn mätte **56,4 m³/s den 2 september 2023, det högsta sedan mätningarna började 1980**
  (tidigare 42,9 m³/s 1983). Skultuna fick 59,7 mm på ett dygn efter en augusti med 254 mm.
  SMHI gav röd varning, staden byggde vallar vid stadshuset och cirka 60 fritidshus i
  Biskopsängen översvämmades.
- **Satellitdata finns för händelsen.** Sentinel-1A passerade kl. 05:07 den 2 september,
  toppdagen, med vindprodukt över Mälaren. Klara optiska bilder finns efteråt: Sentinel-2 den
  5 september (2 % moln) och Landsat 9 den 6 september (5 %).
- **Erosion:** SGI har en översiktlig erosionskarta för Svartån (2012) och skred- och
  erosionsunderlag för Mälaren, men SGI:s GeoServer svarade "403 – access denied" utan
  inloggning. Underlaget måste fås från SGI eller Länsstyrelsens geodatakatalog.
- **Skogsbrand:** staden har inga brandlager. NASA FIRMS 2001–2025 visar ingen skogsbrand i
  Västerås kommun, bara enstaka små detektioner (se [Brandsökning](#brandsökning-2026-10-28)).
  Närmast ligger branden i Västmanland 2014, som demon redan visar, strax norr om
  kommungränsen.
- Beslutat 2026-10-28 (se [Beslut](#beslut)): första scenariot är **översvämningen i Svartån i
  september 2023** (`vasteras-sep2023`); erosion väntar.

## Västerås stads karttjänster

### Hur kartorna är byggda

[Stadens kartsida](https://www.vasteras.se/kommun-och-politik/kartor.html) länkar till ett
antal kartor på `kartor.vasteras.se`, bland dem samhällskartan (`/sam/`), näringslivskartan
och översiktsplanen (`/external/op2026origo/`). De är Origo-kartor, samma ramverk som
Sundsvalls `bxkarta`. Origo-konfigurationerna (`vas.json`, `index.json`) visar källorna:

| Källa | Adress | Innehåll |
|---|---|---|
| ArcGIS Server | `https://kartor.vasteras.se/arcgis/rest/services/ext/…` | Stadens lager, 82 tjänster |
| GeoServer, WMTS | `https://kartserver.vasteras.se/geoserver/gwc/service/wmts` | Bakgrundskartor: *Karta, färg*, *Karta, grå*, *Flygfoto* (`bakgrundskartor:topowebbkartan`, `…_nedtonad`, `…:Ortofoto_016`) |
| ArcGIS-portal | `https://gisportal.vasteras.se/portal/…` | Webbappar |

Bakgrundskartorna motsvarar Sundsvalls *Kartan*. Namnet *topowebbkartan* tyder på att de
bygger på Lantmäteriets Topografisk webbkarta, så Lantmäteriets villkor kan gälla vid sidan
av stadens. Det är inte kontrollerat.

### Lager som rör scenarierna

| Tjänst | Lager | Not |
|---|---|---|
| `ext/sk_skyfall_wms` (MapServer, WMS) | 0 *Maximalt vattendjup, 100 års regn*, 1 *Maximalt ytvattenflöde (l/s/m)* | WMS i EPSG:4326 och 3010 (SWEREF 99 16 30). ArcGIS-exporten ritar i 3857. |
| `ext/sk_op2070_lagakraft`, `ext/sk_OP2050_dyn` | *Klimatanpassning*, *Klimatanpassning – Hänsyn*, *Skyfallsled*, *Dricksvattenförsörjning*, *Vattenytor* | Översiktsplanernas underlag |
| `ext/sbf_op2026_dyn` | Skyddszoner för grund- och ytvatten | |
| `ext/crowdsourcing_kris` (FeatureServer) | *CROWDSOURCING_KRIS*, "tjänst för invånare att anmäla problem vid händelse" | Kan innehålla anmälningar från verkliga händelser; innehållet är inte undersökt och kan vara personuppgifter. |
| `ext/sk_VMA_skyddsrum_dyn` | VMA och skyddsrum | |
| `ext/Matinstrument` (FeatureServer) | Markbeläggning, byggnader och *Dagvattenbrunnar* | Trots namnet inga mätinstrument |

Skyfallskarteringens djuplager ritades 2026-10-28 över centrala Västerås (export i EPSG:3857,
800 × 800 px): Svartån, centrum, järnvägen och Mälarstranden syns, med de största djupen i
lågpunkter och underfarter.

**Tekniskt:** demons WMS-proxy begär kartbilder i EPSG:3857. Stadens WMS erbjuder inte den
projektionen, så demon behöver antingen ArcGIS-serverns `export` (som ritar i valfri
projektion) eller hämta i 3010 och projicera om. Det är en mindre anpassning av
`tools/fetch_municipal_features.py` och WMS-proxyn.

## Svartån i september 2023

### Förlopp enligt källor

- Kraftigt regn natten 1–2 september 2023 över Västmanlands och Uppsala län, efter en blöt
  sensommar då marken redan var mättad ([Länsstyrelsens utredning](https://www.lansstyrelsen.se/vastmanland/om-oss/vara-tjanster/publikationer/2024/utredning-av-oversvamningar-i-vastmanlands-och-uppsala-lan-september-2023.html)).
- SMHI gav röd varning för höga flöden i Svartån. Staden byggde vallar för att skydda
  stadshuset; vallarna sattes enligt SVT aldrig på riktigt prov, eftersom vattnet hunnit sjunka
  något ([SVT](https://www.svt.se/nyheter/inrikes/ett-60-tal-fritidshus-kan-flyta-ut-i-svartan)).
- Cirka 60 fritidshus i koloniområdet Biskopsängen översvämmades, och det varnades för ras
  längs ån (SVT).
- Norconsults utredning för staden (januari–februari 2024) bedömer toppflödet som ungefär ett
  klimatanpassat 100-årsflöde, och att Biskopsängen svämmar över när flödet når cirka 70 m³/s
  ([Utredning Biskopsängen](https://vasteras.se/download/18.2d0dc8ab18f3799c4a119110/1715070905172/Utredning%20Biskops%C3%A4ngen.pdf)).
- Länsstyrelsen kom fram till att kommunerna inte vidtagit tillräckliga åtgärder trots
  vädervarningar, och att beredskapen behöver förbättras.

### Mätdata (SMHI, öppna data)

| Station | Vad | Värde |
|---|---|---|
| Åkesta kvarn (2216, 2771, 2773), Svartån ovanför Västerås | Dygnsflöde | **56,4 m³/s 2 september 2023**, högst sedan 1980; MHQ 27 m³/s; 46,1 m³/s 3 september |
| Skultuna (96440) | Nederbörd per dygn | 59,7 mm 1 september (06–06 UTC); 254 mm i augusti |
| Västerås (96350) | Nederbörd per dygn | 37,0 mm 1 september; 203 mm i augusti |
| Hallstaberg (96390) | Nederbörd per dygn | 29,7 mm 1 september |
| Berg (2218), Kolbäcksån | Dygnsflöde | 7,4 m³/s 2 september (högsta någonsin 8,3) |
| Gränvad (2217) | Dygnsflöde | 14,0 m³/s 3 september (högsta 30,7) |

Åkesta kvarn bytte stationsnummer två gånger (2771 från november 2021, 2773 från 28 augusti
2023), alltså mitt i händelsen. Serierna behöver sättas ihop; SMHI har även 15-minutersvärden.
Norconsults 70 m³/s gäller längre ned än Åkesta, där tillflöden kommer till.

Mälarens vattenstånd finns inte bland SMHI:s öppna hydrologiska stationer i området. Det är
inte undersökt var det kan hämtas.

### Satellitdata, alla sensorer

Kontrollerat 2026-10-28 i Planetary Computers katalog och Copernicus Data Space, över
Västerås från Åkesta kvarn till Mälaren (16,40–16,65 Ö, 59,58–59,70 N).

| Sensor | Före | Under | Efter |
|---|---|---|---|
| Sentinel-1A radar | 26 aug 05:15 och 16:30, 31 aug 05:24 | **2 sep 05:07**, toppdagen | 7 sep 05:15 och 16:30 |
| Sentinel-1 vind över havet (OCN) | | 2 sep 05:07, över Mälaren | |
| Sentinel-2 | 31 aug, 28 % moln (scen) | 1 och 3 sep, 97–100 % moln | **5 sep, 2 % moln** |
| Landsat 8/9 | 29–30 aug, 59–60 % moln | | **Landsat 9 6 sep, 5 % moln** |

Molnandelen gäller hela scenen; över staden kontrolleras den när bilderna hämtas. Övriga
sensorer (Sentinel-3, MODIS, Meteosat, SWOT) är inte kontrollerade för Västerås men täcker
området på samma sätt som Sundsvall.

### Övriga översvämningskällor

- **MCF:s översvämningskarteringar:** översikten listar *Svartån Västerås*, karterad 2025, och
  i närheten Eskilstunaån (2025), Kolbäcksån (2014), Arbogaån (2013) och Kölstaån och Köpingsån
  (2024). Karteringen av Svartån är publicerad. Ytan *Svartån Västerås* (startdatum 2025) finns i
  lagren *100-årsflöde (klimatanpassat flöde för slutet av seklet)* och *Beräknat högsta flöde*
  (REST-lager 3 och 5, WMS-lager 12, 11 och 9), men inte i det vanliga lagret *100-årsflöde*.
  *Rättat 2026-10-29:* förstudien frågade först bara lager 0 och 2 och drog felaktigt slutsatsen
  att karteringen kanske inte var publicerad.
- **MET Norway:** MEPS-arkivet täcker 2023, som för Ljungan.

## Skogsbrand

Staden har inga brandlager. Ett brandscenario för Västerås bygger på samma källor som demons
brandscenarier: NASA FIRMS, Sentinel-2 och Landsat, SMHI:s väder, brandrisk från LSA SAF och
MET Norways prognoser. Branden i Västmanland 2014, som demon redan visar, låg i Sala,
Surahammar, Fagersta och Norberg, alltså inte i Västerås kommun.

### Brandsökning 2026-10-28

NASA FIRMS årsfiler för Sverige (MODIS Collection 6.1 2001–2025, VIIRS S-NPP 2012–2025)
söktes inom Västerås kommuns gräns i OpenStreetMap (relation 935588), med bara detektioner
som FIRMS antar är vegetationsbränder (`type` 0) och med minst nominell konfidens (VIIRS `n`
eller `h`, MODIS 30).

- **Ingen skogsbrand syns i kommunen.** Där finns 34 detektioner från 26 dagar, högst två
  passager samma dygn och 29 av dem under 10 MW.
- Flera ligger vid 59,61 N 16,46 Ö, där Mälarenergis kraftvärmeverk ligger. De är troligen
  värme från anläggningen trots att de räknas som vegetation; det är inte kontrollerat.
- Den största, två MODIS-detektioner på 116–128 MW kl. 02:27 UTC den 24 september 2003 vid
  59,63 N 16,58 Ö öster om staden, är inte identifierad.
- I närområdet är branden i Västmanland 2014 den enda stora; dess sydligaste detektioner
  ligger strax norr om kommungränsen. Övriga grupper inom cirka 20 km har högst 7 detektioner.
- Pressen ger bara småbränder, till exempel 10 × 25 m vid Fäbodängen nära Skultuna
  ([SVT](https://www.svt.se/nyheter/lokalt/vastmanland/raddningstjansten-har-larmats-till-flera-brander-i-lanet),
  datum inte bekräftat). MSB:s eller MCF:s insatsstatistik är inte sökt.

Ett brandscenario i Västerås har alltså ingen händelse som satelliterna sett. Alternativen är
branden 2014 sedd från Västerås eller att vänta med brand.

## Erosion

Användaren skrev *jorderosion*. Det kan betyda två saker med olika källor:

1. **Erosion och skred längs vattendrag och stränder** (Svartån, Mälaren):
   - SGI:s [översiktliga erosionskarta för Svartån](https://www.sgi.se/globalassets/kartor/erosionskartor/erosionskartor-vattendrag/svartan-vasteras.pdf),
     2012, byggd på SGU:s jordartskartor; den visar erosionskänsliga jordarter, inte uppmätt erosion.
   - SGI:s underlag om erosionsförutsättningar runt Mälaren och skredrisk längs vattendrag.
     Länsstyrelsernas geodatakatalog listar *SGI Erosionsförutsättningar* och *SGI Inträffade
     skred*. SGI:s GeoServer (`gis.swedgeo.se/geoserver`, `gis.sgi.se/geoserver`) svarade
     403 utan inloggning 2026-10-28, och kartvisaren `gis.sgi.se/hajk` visar inte sina
     tjänster öppet.
   - I september 2023 varnades för ras längs Svartån, vilket knyter erosion till
     översvämningsscenariot.
2. **Erosion på åkermark** (vatten- eller vinderosion av matjord): andra källor, till exempel
   Jordbruksverket och SLU. Inte undersökt.

## Vad som blir simulerat eller syntetiskt

Som i övriga scenarier: nivågivare där det inte finns mätningar, till exempel vid stadshuset,
i Biskopsängen och vid Svartåns mynning, märkta syntetiska; och, om användaren vill, vallarna
vid stadshuset som ett märkt objekt på kartan, inte som en modell.

## Beslut

Beslutat av användaren 2026-10-28:

1. **Stadens data.** Techseed har ok att använda Västerås stads data för internt bruk, och
   inga offentliga visningar är planerade. Mejlutkastet i bilagan används bara om demon ska
   visas offentligt.
2. **Första scenariot** är Svartån i september 2023 (`vasteras-sep2023`), med SMHI:s flöden
   och regn, stadens skyfallskartering, Sentinel-1 på toppdagen och klara bilder efteråt.
3. **Erosion** väntar: längs vattendrag och stränder (SGI) eller på åkermark är inte bestämt.
4. **Skogsbrand:** sökningen är gjord (se [Brandsökning](#brandsökning-2026-10-28)); hur brand
   ska visas för Västerås är inte bestämt.

## Källor

- Västerås stad, kartor: <https://www.vasteras.se/kommun-och-politik/kartor.html>,
  Origo-konfigurationer `https://kartor.vasteras.se/sam/vas.json` och
  `https://kartor.vasteras.se/naringsliv/index.json`, ArcGIS-katalog
  `https://kartor.vasteras.se/arcgis/rest/services/ext?f=json`, skyfallstjänsten
  `https://kartor.vasteras.se/arcgis/services/ext/sk_skyfall_wms/MapServer/WMSServer`,
  hämtade 2026-10-28.
- [Länsstyrelsen Västmanland: Utredning av översvämningar i Västmanlands och Uppsala län september 2023](https://www.lansstyrelsen.se/vastmanland/om-oss/vara-tjanster/publikationer/2024/utredning-av-oversvamningar-i-vastmanlands-och-uppsala-lan-september-2023.html)
- [SVT: Ett 60-tal fritidshus kan flyta ut i Svartån](https://www.svt.se/nyheter/inrikes/ett-60-tal-fritidshus-kan-flyta-ut-i-svartan)
- [Norconsult för Västerås stad: Utredning Biskopsängen (2024)](https://vasteras.se/download/18.2d0dc8ab18f3799c4a119110/1715070905172/Utredning%20Biskops%C3%A4ngen.pdf)
- [SMHI: 2023 – översvämningar efter ovädret Hans](https://www.smhi.se/kunskapsbanken/hydrologi/historiska-oversvamningar/2023---oversvamningar-efter-ovadret-hans)
- SMHI öppna data, hämtade 2026-10-28: vattenföring per dygn vid Åkesta kvarn (2216, 2771,
  2773), Berg (2218) och Gränvad (2217); nederbörd per dygn vid Västerås (96350), Skultuna
  (96440) och Hallstaberg (96390).
- MCF:s översvämningskarteringar, `gis-tjanster.mcf.se/arcgis/rest/services/Oversvamningskarteringar/karteringar/MapServer`, lager 0 och 2, frågade 2026-10-28; lager 3 och 5, hämtade 2026-10-28 för scenariot och kontrollerade 2026-10-29.
- [SGI: Erosionskarta Svartån, Västerås](https://www.sgi.se/globalassets/kartor/erosionskartor/erosionskartor-vattendrag/svartan-vasteras.pdf)
- [SGI: Vägledning ras, skred, erosion](https://gis.swedgeo.se/rasskrederosion/)
- [Länsstyrelsernas geodatakatalog: SGI Erosionsförutsättningar](https://ext-geodatakatalog.lansstyrelsen.se/GeodataKatalogen/srv/api/records/GetMetaDataById?id=f735c3f3-56e5-46d4-b78e-00a319357ece)
- Satellitscener: Microsoft Planetary Computer STAC (`sentinel-1-grd`, `sentinel-2-l2a`,
  `landsat-c2-l2`) och Copernicus Data Space Ecosystem (Sentinel-1 OCN), sökta 2026-10-28.
- NASA FIRMS, årsfiler per land (`https://firms.modaps.eosdis.nasa.gov/data/country/`, MODIS
  C6.1 2001–2025 och VIIRS S-NPP 2012–2025, Sverige), hämtade 2026-10-28.
- OpenStreetMap, Västerås kommuns gräns (relation 935588) via Nominatim, hämtad 2026-10-28.
- [SVT Västmanland: Räddningstjänsten har larmats till flera bränder i länet](https://www.svt.se/nyheter/lokalt/vastmanland/raddningstjansten-har-larmats-till-flera-brander-i-lanet)

## Bilaga: mejlutkast till Västerås stad

Utkastet är skrivet för att skickas av Techseed om demon ska visas offentligt; för internt
bruk har Techseed redan ok (se [Beslut](#beslut)). Mottagare: stadens GIS- eller
kartfunktion, via stadens kontaktcenter om ingen direktadress finns. Namn och kontaktuppgifter
fylls i av avsändaren.

> **Ämne:** Fråga om att använda Västerås stads kartlager i en demonstrator om klimatrisker
>
> Hej,
>
> Vi på Techseed bygger en demonstrator som visar hur satellitdata, geodata, sensorer och AI
> kan ge en gemensam lägesbild vid översvämning, skogsbrand och erosion. Vi använder den i
> dag internt och vill kunna visa den för kunder och vid möten. Den spelar upp historiska
> händelser med verkliga data och är tydligt märkt som en uppspelning, inte en levande tjänst.
>
> Vi vill gärna bygga ett scenario om Svartåns höga flöden i september 2023 och har sett att
> staden publicerar kartlager på kartor.vasteras.se. Vi undrar om vi får använda följande:
>
> 1. Skyfallskarteringen (tjänsten sk_skyfall_wms: maximalt vattendjup vid 100-årsregn och
>    maximalt ytvattenflöde).
> 2. Översiktsplanens lager om klimatanpassning och skyfallsleder (OP2050/OP2070).
> 3. Stadens bakgrundskartor (karta i färg och grått samt flygfoto) från kartserver.vasteras.se.
>
> Konkret undrar vi:
>
> - Får vi visa lagren i demonstratorn, med Västerås stad angiven som källa?
> - Får vi spara en lokal kopia av kartbilderna för det område och den tid scenariot gäller,
>   så att demonstratorn fungerar utan internet? Kopian används bara i
>   demonstratorn och lämnas inte vidare.
> - Hur vill ni att källan anges, och finns det andra villkor eller rättigheter vi ska känna
>   till, till exempel för Lantmäteriets underlag i bakgrundskartorna?
> - Finns det kartering eller underlag från händelsen i september 2023, till exempel var
>   vallar byggdes eller vilka områden som översvämmades, som ni kan dela?
>
> Vi skickar gärna en skärmbild eller visar demonstratorn innan något visas externt.
>
> Med vänliga hälsningar
> [Namn]
> Techseed
> [E-post, telefon]
