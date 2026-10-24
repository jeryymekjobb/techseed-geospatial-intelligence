# Datahämtning per scenario – inventering för installation från Git

Datum: 2026-10-22
Författare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code, på uppdrag av Techseed. Steg 1 i
planen för lokal installation från Git (backloggen i `CONTEXT.md`). Underlag: koden i `tools/`,
scenariomodulerna i `app/backend/scenarios/`, `tools/startup_check.py`, operatörsguiden och de
befintliga `SOURCE.json`-filerna under `data/`. Licens- och attributionsuppgifter är citerade ur
dem; rapporten är ingen juridisk bedömning av vad som får spridas.

## Sammanfattning

Varje scenarios data hämtas och byggs av de befintliga verktygen i `tools/`. `tools.fetch_scenario
<scenario>` kör dem i rätt ordning med argument ur scenariomodulen; `--list` visar planen med
konton, paket, storlek och vad som redan finns, utan att hämta något. Användarens egna konton
behövs för satellitbanor (Space-Track), vind (Copernicus CDS) och Meteosat (EUMETSAT, LSA SAF);
övriga källor är öppna. Kontofilerna ligger utanför repot och läses bara av respektive verktyg.

## Konton och paket

| Konto | Fil | Används av |
|---|---|---|
| Space-Track | `~/.spacetrackrc` | `fetch_tle_history` |
| Copernicus CDS | `~/.cdsapirc` | `fetch_era5_land`, `fetch_era5_sea` |
| EUMETSAT Data Store | `~/.eumdac/credentials` | `fetch_meteosat_cth`, `_clm`, `_li`, `_gii` |
| LSA SAF | `~/.netrc` | `fetch_meteosat_frp`, `_frm` |

Extra Python-paket: `tools/requirements-era5.txt` (cdsapi, netCDF4), `tools/requirements-meteosat.txt`
(h5py, eumdac, eccodes), `tools/requirements-terrain.txt` (terrängen utan Docker). MET Norways
prognoser behöver netCDF4.

## Källor, licenser och attribution

| Data | Verktyg | Källa | Licens/attribution enligt koden eller SOURCE.json |
|---|---|---|---|
| Webbibliotek | `fetch_web_vendor` | npm, SHA-512 | Cesium Apache-2.0, satellite.js MIT |
| Röster | `fetch_piper_voices` | Hugging Face, SHA-256 | nst CC0, alma CC BY 4.0 |
| Höjddata | `fetch_copernicus_dem` | Copernicus DEM GLO-30 (AWS) | "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA" |
| Offlinekarta, marktäcke, byggnader | `build_offline_tiles`, `fetch_osm_*` | OpenStreetMap (Sverigeutdrag, Overpass) | "© OpenStreetMap contributors, ODbL" |
| Satellitbanor | `fetch_tle_history` | Space-Track | användaravtalet; "Fetched with a personal Space-Track account; not versioned or redistributed" (se också `reports/2026-10-21-space-track-villkor-claude-opus-5-5.md`) |
| Väder, regn, flöden, radar, blixtar | `fetch_smhi_*` | SMHI öppna data | CC BY 4.0 SE med attribution per produkt |
| Vind | `fetch_era5_land`, `fetch_era5_sea` | Copernicus CDS | "Contains modified Copernicus Climate Change Service information (ERA5-Land …), CC BY 4.0" |
| Landsat | `fetch_landsat_scene` | Planetary Computer | USGS, public domain; doi:10.5066/P9OGBGM6 |
| Sentinel-1 och -2 | `fetch_sentinel*_scene` | Planetary Computer | "Contains modified Copernicus Sentinel data <år>" |
| EMS-ytor | `fetch_ems_perimeters` | Copernicus EMS | "© European Union, Copernicus Emergency Management Service (EMSR298)" |
| Översvämningskarteringar | `fetch_mcf_flood_maps` | MCF:s karttjänst | "Översvämningskartering © MCF (tidigare MSB)" |
| Kommunens lager och karta | `fetch_municipal_*` | Sundsvalls kommuns geoserver | "© Sundsvalls kommun"; användningen bekräftad av användaren (`CONTEXT.md`) |
| Prognoser | `fetch_met_forecasts` | MET Norways arkiv | NLOD 2.0 och CC BY 4.0 |
| Meteosat | `fetch_meteosat_*` | EUMETSAT, LSA SAF | CC BY 4.0 (Core, EUMETSAT data policy 5.1; LSA SAF data policy) |

## Vad scenarierna kräver

`tools/startup_check.py` kräver allt som scenariot pekar ut med ett `*_FILE`-attribut och
kataloger med en markörfil, däribland Meteosat-data, blixtar och kommunens karta där scenariot
har dem. Bara MET Norways prognoser är valfria. `fetch_scenario --list <scenario>` visar varje
scenarios steg; de skiljer sig så här:

- **Brand (Västmanland 2014, Kårböle 2018):** Landsat (Västmanland), Sentinel-2 och EMS (Kårböle),
  LSA SAF:s brandpixlar och brandrisk. Västmanlands väder, vind, OSM-lager och FIRMS ligger i git.
  Kårböles väderstationer och period före branden står bara i guiden och är inlagda i verktyget.
- **Översvämning:** SMHI:s regnmätare, radar, flöden och dygnsregn där scenariot har dem,
  MCF:s karteringar, Sentinel-1, databasen och därefter de syntetiska givarna.
- **Delade data:** `flen2019` använder `flen2024`:s och `flenkommun2021` `flenkommun2024`:s höjddata,
  terräng och OSM-lager; offlinekartorna ligger gemensamt i `data/tiles/`.

Ordningen följer beroendena: Sentinel-1 efter OSM-terrängen och höjddatan, Meteosats molnmask efter
satellitbilderna, ERA5 över hav efter ERA5-Land, de härledda givarna efter databasen. Två verktyg
skriver samma givarfil: `derive_level_sensor_points` där scenariot har `LEVEL_SENSOR_RIVERS`,
annars `derive_impact_sensor_points`.

## Luckor och osäkerheter

- ERA5-filerna får ingen `SOURCE.json` av verktygen; attributionen finns i koden (och för Sundsvall
  i en handskriven fil).
- Givarfilerna från `derive_impact_sensor_points` saknar käll- och attributionsfält.
- Meteosat-filernas `SOURCE.json` har källa och licens men inte attribution; den står i
  `app/backend/meteosat*.py`, där året är fast satt till 2026.
- MCF:s och kommunens GeoJSON saknar licensfält.
- MET Norways arkiv är inte provat för 2020–2023, vilket gäller `flenkommun2021`.
- Argumenten för de scenarier som saknar avsnitt i guiden (Kramfors, Flen) är härledda ur deras
  data och moduler: SMHI:s nyare data ur `latest-months`, radarn över uppspelningen med 30 minuters
  steg för perioder över två veckor.
- Storlekarna i `--list` är uppskattningar från tidigare hämtningar.

## Inte gjort

Ingen ny hämtning är gjord för den här inventeringen. Ett helt prov från en ren klon (planens steg 6)
återstår, först på Ubuntu och sedan på Windows.

## Uppföljning (2026-10-24)

Inventeringen ovan beskriver läget den 2026-10-22. Senare verifierat och genomfört:

- En ren Windows-klon av `main` (`92d8f1d`) hämtade och byggde `flen2019` med native verktyg, laddade PostGIS och skapade syntetiska givare. `fetch_scenario` avslutades med kod 0 med `--services native`, Edge och de uttryckliga runtime-sökvägarna; MET Norway-prognoserna, som är valfria, hämtades inte. PostGIS laddades med 5 304 targets, 1 201 terrain features och 166 flood areas.
- Källmetadata är implementerad på den lokala grenen `record-source-metadata` (ännu inte mergad/pushad) för framtida ERA5-Land/ERA5 sea CSV-sidecars, impact-baserade syntetiska nivågivare och Meteosats `SOURCE.json`-attribueringar. Befintliga oversionerade data skrivs inte om automatiskt.

Fortfarande olöst: licensvillkoren för MCF:s och kommunens GeoJSON, MET Norway-arkivet för 2020–2023, scenarioargumenten som härletts för Kramfors/Flen och storleksuppskattningarna.
