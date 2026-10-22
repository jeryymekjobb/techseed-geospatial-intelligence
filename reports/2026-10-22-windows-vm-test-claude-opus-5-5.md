# Windows-test av demon utan Docker i en VirtualBox-VM

Datum: 2026-10-22
Författare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code, på uppdrag av Techseed.
Användaren körde stegen i VM:en; Claude förberedde data och checklista, följde VM:en från
värddatorn och felsökte. Det användaren rapporterade och det Claude själv kontrollerade
hålls isär nedan.

## Syfte

Backloggens nästa steg för Windows-stödet: att prova guidens väg utan Docker eller WSL
(`docs/operatorsguide.md`, avsnitt A–C och G) från en ren Git-klon i en Windows-VM.

## Miljö

| Del | Värde |
|---|---|
| Värddator | Ubuntu, Intel Core i7-14700HX (28 trådar), 31 GB minne, VirtualBox 7.0.16 |
| VM | "Windows 11", Windows 11 Business 10.0.26200, 64-bit, EFI, 16 GB minne, VBoxSVGA 128 MB, Guest Additions 7.0.16, NAT |
| Processorer och 3D i VM:en | först 4 och utan 3D, sedan 8 och med 3D, till sist 8 och utan 3D (se Förlopp) |
| Skärm | en virtuell skärm, 2270 × 1323 |
| Kod | ren klon av `577f400` (`main`), via den befintliga, läsbara VirtualBox-delningen `techseed_root` |
| Python | 3.12.10, `py -3.12 -m venv .venv` |
| Node.js | 24.17.0 (guiden anger 22.x; användaren valde att prova 24) |
| TileServer GL | 5.6.0 med `@maplibre/maplibre-gl-native` 6.4.1 och `sharp` 0.34.5, redan installerad i `techseed-runtime` från ett tidigare prov |
| PostgreSQL / PostGIS | 16.15 som Windows-tjänst / 3.6 |
| Mosquitto | Windows x64-installationen, startad av demon |
| Webbläsare | Microsoft Edge (`TECHSEED_BROWSER=edge`); Chrome är inte installerat i VM:en |
| Scenario och data | `flen2019`; ett datapaket (`tools.package_data`) med 1 445 filer, 72 MB, ur `data/flen2019/` och den del av `data/flen2024/` som scenariot delar (DEM, terräng, OSM), `flen.mbtiles` |

Innan något ändrades togs ögonblicksbilden `fore-techseed-windows-test-2026-10-22` av VM:en,
som också används för COPA-DATA zenon. Datapaketet delades med VM:en i en läsbar delad mapp.

## Förlopp och resultat

Kontrollerat av Claude ur utdata som användaren klistrade in:

- Klon, Python-miljö och alla Pythonpaket, också `piper-tts` 1.8.0 och `onnxruntime` 1.31.0.
- `tools.install_data`: förhandskontroll och installation av alla 1 445 filer.
- `tools.fetch_web_vendor` (Cesium 1.146.0, satellite.js 7.1.0) och `tools.fetch_piper_voices`.
- Databasen `flen2019` med PostGIS 3.6, och `tools.load_postgis`: `Loaded into flen2019:
  targets=5304 terrain=1201 flood_areas=166 stormwater_points=0`.
- `start_native_tiles --dry-run`, `start_native_mqtt --dry-run` och `startup_check` med
  `--services native`: allt OK utom Chrome (inte installerat; Edge hittades) och MET Norways
  prognoser för `flen2019` (fynd 3).

Rapporterat av användaren, med demon igång i VM:en (8 processorer, utan 3D-acceleration):
fönstren, 2D och 3D, karta, satellitbilder, MCF:s översvämningsytor, IoT, PostGIS-frågor,
Almas uppläsning, slutbilden, STARTA OM DEMO, BYT SCENARIO och kioskläget fungerade, "även
ljudet".

VM:en hängde sig två gånger innan dess; Claude följde båda från värddatorn:

1. **4 processorer, utan 3D-acceleration:** tre av fyra virtuella processorer låg på 100 %
   medan Edge renderade 3D-globen och kartan i mjukvara och kartservern renderade
   rasterbitar. VM:en svarade inte. Den mjuka och den hårda avstängningen fastnade i
   "stopping"; VM-processen avslutades på värddatorn (VM:en "aborted").
2. **8 processorer, med 3D-acceleration:** VM:en stod still med låg processorbelastning. Dess
   logg slutade med upprepade varningar från grafikdrivrutinen (`VBoxMP::DxgkDdiQueryAdapterInfo:
   WARNING! :unsupported Type (25)`) när Edge började använda 3D. Avslutad på samma sätt.

Med 8 processorer och 3D-accelerationen avstängd igen gick demon, också 3D-globen. Hur fort
den renderade mättes inte; en VM utan grafikkort säger inget om utställningsdatorn.

## Fynd

1. **MQTT-porten går inte att ändra i native-läget.** `tools/native_services.py` startar
   Mosquitto på 1883 och ger backend `127.0.0.1:1883`, och `start_demo` startar de simulerade
   noderna utan `--broker`. I VM:en lyssnade tjänsten **zenon Data Hub** (COPA-DATA, med en egen
   Mosquitto) på 1883, och demon vägrade starta, som den ska. Den stoppades tillfälligt för
   testet. Åtgärdat samma dag (`7d8a601`): `--mqtt-port` i `start_demo` och `startup_check`
   flyttar demons broker, och backend och noderna följer med. Provat i VM:en med zenon Data Hub
   igång: `startup_check` visade `MISSING/FAILED Native MQTT port 1883: in use by another
   program`, med `--mqtt-port 18830` var porten ledig, demon startade (`IoT: Ansluter till
   127.0.0.1:18830`) och `/api/sensors` gav de fyra simulerade noderna med värden.
2. **Guiden behöver kompletteras:** de fyra Flen-scenarierna saknas i tabellen över
   databaser (G2) och i scenariolistan i D; att `TECHSEED_BROWSER=edge` kan sättas för hela
   fönstret; att Windows-tjänster stoppas i ett administratörsfönster; att provet gick med Node
   24.17.0; och för VirtualBox-VM:ar minst 8 processorer och ingen 3D-acceleration (7.0.16).
   Åtgärdat samma dag i `docs/operatorsguide.md` (avsnitt D och G).
3. **`startup_check` kräver MET Norways prognoser**, som scenarierna klarar sig utan (panelen
   blir tom). För `flen2019` har prognoserna aldrig hämtats, inte heller på Ubuntu.
   Åtgärdat samma dag: `startup_check` visar dem som `OPTIONAL/MISSING` och godkänns ändå.
   Prognoserna för `flen2019` är fortfarande inte hämtade.
4. **Menyn listar alla scenarier, också de som inte är installerade.** Ett val av Sundsvall gav
   `Missing or empty scenario map: …\data\tiles\sundsvall.mbtiles`. Guiden säger det, men
   menyn skulle kunna visa vilka scenarier som har data.
5. **`start_demo` slutar när ett scenario saknar data**, i stället för att visa menyn igen; i
   kioskläge borde den hellre gå tillbaka till menyn.

Övrigt: `npm install` rapporterade 12 kända sårbarheter i TileServer GL:s beroenden; `npm audit
fix` kördes inte, eftersom den byter de fastlåsta versionerna. Kartservern lyssnar bara på
localhost. psql varnade för konsolens teckentabell (437 mot 1252); frågorna i demon visade å, ä
och ö rätt enligt användaren.

## Inte provat

- Chrome på Windows (bara Edge), flera skärmar och olika skalning.
- Offlinekörning efter installationen.
- Den automatiska demokontrollen (`tools.check_demo`) mot den körande demon.
- Andra scenarier än `flen2019`, och hämtning och bygge av data på Windows.
- Riktig Windows-hårdvara med grafikkort; 3D-prestandan där.

## Återställning i VM:en

zenon Data Hub stoppades för testet men står kvar på automatisk start; den startar igen när
Windows startar, eller med `Start-Service zenon_Data_Hub` i ett administratörsfönster.
Windows-tjänsten Mosquitto (installerad för testet) står på manuell start. VM:en har nu 8
processorer och 3D-accelerationen avstängd. Ögonblicksbilden och den delade mappen
`techseed-test` finns kvar.
