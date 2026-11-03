# SGI:s data och tjänster

Datum: 2026-11-03
Författare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code, på uppdrag av
Techseed. Rapporten inventerar vad Statens geotekniska institut (SGI) tillhandahåller för
data och tjänster, som underlag till MVP:n, särskilt skred och erosion i one-pagern
(`docs/mvp/onepager-mvp.md`). Den bygger inget. Den är inte juridisk rådgivning, och
inget i den säger att data får användas.

## Sammanfattning

- SGI har en egen GeoServer, `https://mapsext.sgi.se/geoserver`, med WMS-lager för
  skred, erosion och geoteknik. Bland dem finns skreddatabasen över inträffade skred, ras
  och övriga jordrörelser i hela landet.
- SGI anger att dess öppna data är under CC BY 4.0, med SGI som källa. Om det gäller
  varje WMS-lager är inte bekräftat.
- InSAR Sverige (`insar.sgi.se`) visar långsamma markrörelser från Sentinel-1, byggt på
  Copernicus EGMS, med WMS och WMTS.
- SGI har en tjänsteman i beredskap och egna fältapplikationer för räddningstjänsten
  vid ras och skred.
- SGI har 3D-modeller och ortomosaik av skredet på E6 den 23 september 2023, en möjlig
  kandidat för "ett nyare skred" i one-pagern.

## Metod

Den 2026-11-03 lästes SGI:s GIS-startsida (`https://gis.sgi.se/`), konfigurationen till
kartvisaren för ras, skred och erosion (`https://gis.sgi.se/hajk-api/v2/config/rasskrederosion`),
SGI:s ArcGIS-katalog (`https://geodata.sgi.se/server/rest/services?f=json`) och SGI:s
webbsidor. GeoServerns GetCapabilities svarar 403, så lagernamnen är tagna ur
kartvisarens konfiguration. Inga kartbilder har hämtats.

## SGI:s lager på `mapsext.sgi.se/geoserver`

| Lager (WMS) | Innehåll | Möjlig användning i MVP:n |
|---|---|---|
| `sgi_ext:_sgi_sverige_skreddatabas` | Inträffade skred, ras och övriga jordrörelser, hela landet; ett urval, inte komplett | Historik; one-pagerns exempel |
| `lagergrupp_srk_gotaalv_inkl_detaljerad_geoteknisk_information`, `lagergrupp_srk_savean`, `sgi_ext:_sgi_norsalven_risk`, `lagergrupp_srk_angermanalven` | Skredriskkartor för Göta älv, Säveån, Norsälven och Ångermanälven | Riskzoner kring skyddsvärda objekt |
| `lagergrupp_srk_fastmark`, `lagergrupp_srk_ej_klassat_omrade`, `lagergrupp_srk_utredningsomrade`, `sgi:sgi_angermanalven_1_3_fsrk_aktsam_diss` | Fastmark, ej klassat område, utredningsområden och aktsamhetsområde till skredriskkarteringarna | Riskzoner |
| `lagergrupp_forutsattningar_kvicklera_sgu` | Finkorniga jordarter med förutsättning för kvicklera | Skredrisk |
| `sgi_ext:sgi_skane_ksi_*_2022`, `sgi_ext:sgi_halland_ksi_*_2022` | Kustsårbarhetsindex, förutsättningar för erosion och samhällsvärden, Skåne och Halland | Erosion vid kusten |
| `lagergrupp_historiska_strandlinjer_40_50_60_70_sgu` | Historiska strandlinjer, 1940- till 1970-tal | Stranders förändring |
| `sgi:oks_sverige_kommuner_2023`, `sgi:oks_sverige_lan_2023` | Rapporter om stabilitet, naturolyckor och klimat per kommun och län (2021) | Underlag |
| `bga:surveypoint_info_gis`, `bga:investigation_boundary`, `sgi_ext:geotekniska_undersokningsomr` | Branschens geotekniska arkiv: borrhål och undersökningsområden | Detaljunderlag |

Kartvisaren visar också lager från andra myndigheter, med deras egna villkor:
MCF:s stabilitets- och översvämningskarteringar (`gis-tjanster.mcf.se`), SGU:s jordarter,
stranderosion och sedimenttransport (`maps3.sgu.se`), Skogsstyrelsens instabila slänter
(`geodpags.skogsstyrelsen.se`), Trafikverkets geotekniska databas och SMHI:s
medelvattenstånd. MCF:s tjänster beskrivs i
`reports/2026-11-03-mcf-data-och-tjanster-claude-opus-5-5.md`.

## Övriga tjänster

- **InSAR Sverige**, `https://insar.sgi.se/`. Markrörelser från Sentinel-1, en svensk
  tillämpning av Copernicus EGMS, med WMS och WMTS för egna GIS. Enligt Rymdstyrelsen kan
  EGMS mätpunkter ligga förskjutna omkring tio meter.
- **Stöd till räddningstjänsten**, `https://gis.sgi.se/rtj/`. SGI har en tjänsteman i
  beredskap som ger geotekniskt stöd vid ras och skred eller misstanke om dem.
  Fältapplikationerna RTJ FÄLT, GEOSTAB och VAKASTAB finns i skarp version och
  övningsversion, med rutiner (2025) och instruktioner för drönarflygning (2026).
- **ArcGIS**, `https://geodata.sgi.se/server/rest/services`. Bland annat påverkansområden
  för skred (`paverkansomraden_skred_v2`) och historiska ortofoton över Trelleborg
  1950–2020.
- **Göta älv.** Skredriskkartering, borrhål, stabilitetsberäkningar, terrängskuggning
  och skredärr, ansvarsgränser och 3D-visualisering.
- **E6-skredet 23 september 2023.** 3D-modeller med terrängskuggning och ortomosaik
  (QGIS och ArcGIS).
- **Övrigt.** Kustdataportal, vågdataportal, stränders eroderbarhet vid sjöar, kust och
  vattendrag, kartläggning av kvicklera.

## Villkor

SGI:s sida om öppna data säger: "We make our open data available under the CC BY 4.0
licence." Villkoret är att SGI anges som källa. Geodata sägs vara tillgängliga genom
Lantmäteriets geodataportal.

## Inte bekräftat

- Om CC BY 4.0 gäller varje WMS-lager på `mapsext.sgi.se`, eller bara det som
  publiceras som öppna data i geodataportalen (R-GEO-05).
- Om skreddatabasen innehåller Säve–Tuve 1977 och Småröd 2006.
- Om tjänstemannen i beredskap nås dygnet runt, och vem som får använda
  räddningstjänstens applikationer.
- Om GeoServerns spärrade GetCapabilities betyder att tjänsterna bara är avsedda för
  SGI:s egna kartvisare.

## Källor

- SGI:s GIS-startsida: https://gis.sgi.se/
- SGI, kartor och verktyg: https://www.sgi.se/en/services-and-tools/maps-and-tools
- SGI, öppna data: https://www.sgi.se/en/about-sgi/about-sgi/policy-och-vardegrund/open-data
- SGI, InSAR: https://www.sgi.se/tjanster-och-verktyg/kartor-och-verktyg/insar
- Kort beskrivning av InSAR Sverige: https://gis.sgi.se/dokument/insar/SGI/Kort%20beskrivning%20av%20InSAR,%20Sentinel1,%20CLMS,%20EGMS,%20SGI%20till%C3%A4mpning.pdf
- Regeringen, SGI:s beredskap: https://www.regeringen.se/contentassets/50d2ce9792ba45c6b6dd3b4e3fe0cd4d/statens-geotekniska-institut.pdf
- SGI Varia 512 (skreddatabasen, 2001): https://www.sgi.se/upload/publikationer/Varia/pdf/SGI-V512.pdf
- Rymdstyrelsen, InSAR-datafusion: https://www.rymdstyrelsen.se/innovation/beviljade-bidrag/rymdtillampningsprogrammet-2025-rd1/datafusion-av-medelupplosta-satellitbaserade-insar-data/
