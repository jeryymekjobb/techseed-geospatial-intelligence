# Operatörsguide – brandkartan på IoTDagen

Den här guiden tar dig från en dator utan något installerat till en demo som går i
montern. Varje steg säger vad du gör, varför, och vad du ska se när det har fungerat.
Läs gärna igenom hela guiden en gång innan du börjar.

Teknisk bakgrund för utvecklare finns i `app/README.md`.

## Installation från Git utan USB – Ubuntu och Windows

Den här installationsvägen använder en Git-klon och ett separat, lokalt datapaket.
USB3-stickan ingår inte i kedjan. Git-klonen innehåller inte alla kördata, röster eller
webbibliotek. Ett datapaket måste först tas fram från en uttryckligen granskad fillista;
den här guiden innebär inte att ett komplett eller distributionsgodkänt paket finns.
Be projektansvarig om paketet och den kodrevision som ska användas. Paketets manifest
anger en kodrevision, men importören kontrollerar inte att den är kompatibel med koden.
Kontrollsummor verifierar filernas integritet, inte vem som har publicerat dem.

**Verifieringsläge:** Ubuntu är projektets befintliga körmiljö. De nya verktygen har
enhetstestats där med syntetiska paket och ersättningar för plattformsanrop. Windows-vägen
utan Docker (G) provades som helhet i en Windows 11-VM 2026-10-22 med `flen2019`: installation,
lokala tjänster, Edge-fönster, 2D och 3D, ljud och kioskläge fungerade. Chrome på Windows,
flera skärmar, offlinekörning och riktig Windows-hårdvara är inte provade. macOS har kod
för Chrome-sökning och WAV-uppspelning, men är inte verifierat och saknar automatisk
placering och stängning av demofönster. Det är ännu inte en färdig macOS-installation.

**Välj installationsväg:** Ubuntu fortsätter använda Docker enligt A–F nedan.
Windows utan Docker/WSL använder gemensamma steg A–C för Git, Python och data, och
går därefter till **G. Windows med lokala tjänster – utan Docker eller WSL**.
Hoppa över Docker-kraven i A och Docker-kommandona i D–E för denna Windows-väg.
Utan `--services native` använder startverktyget fortfarande Docker.

Resten av guiden innehåller äldre Ubuntu-kommandon och instruktioner för att hämta
data från grunden. På Windows följer du denna sektion, inte de äldre Bash-kommandona.

### A. Förutsättningar och ren klon

Installera Git, Python med `venv`, Google Chrome samt Docker med Compose enligt
respektive programs installationsanvisningar. Python måste vara minst 3.10;
välj samma Python-version vid jämförande tester och anteckna den i testrapporten.
Ubuntu behöver X11 och `xrandr`, `xprop`, `wmctrl`, `pkill` för automatisk placering,
och `pw-play` för Piper-ljud. Wayland är inte verifierat för fönsterhanteringen.
Windows använder Windows-API:er och `powershell.exe` för demofönstren, inte dessa
Linuxverktyg. WAV spelas där med Pythons `winsound` i en separat process.

Om Docker-vägen väljs på Windows behövs en fungerande miljö för **Linuxcontainrar**, exempelvis
Docker Desktop med dess angivna systemkrav uppfyllda. I en Windows-VM måste även
värddatorn och VM-konfigurationen medge den virtualisering Docker behöver. Kontrollera
detta innan data installeras; Windows-stöd i koden garanterar inte att Docker kan köras
i den aktuella VM:n. Ingen del av guiden kräver att tjänster exponeras på nätverket.

För Docker-vägen: starta Docker och kör `docker compose version` och `docker info`.
För båda vägarna: kontrollera `git --version`. Alla relevanta kontroller måste lyckas.
Ordna Git-åtkomst separat; dela inte SSH-nycklar eller
dataleverantörernas kontouppgifter. Klona till en lokal, skrivbar mapp:

Ubuntu/Bash:

```bash
cd ~
git clone git@github.com:jeryymekjobb/techseed-geospatial-intelligence.git
cd techseed-geospatial-intelligence
git status --short --branch
git rev-parse HEAD
python3 --version
```

Windows/PowerShell:

```powershell
Set-Location $HOME
git clone git@github.com:jeryymekjobb/techseed-geospatial-intelligence.git
Set-Location techseed-geospatial-intelligence
git status --short --branch
git rev-parse HEAD
py -3 --version
```

Kommandona nedan förutsätter att klonen innehåller de nya verktygen
`tools/startup_check.py`, `tools/install_data.py` och `tools/package_data.py`.
Arbetet ligger på `cross-platform-installation` tills det publiceras eller integreras;
en vanlig klon av `main` ger inte nödvändigtvis dessa ändringar. Använd endast en
publicerad revision som projektansvarig har angett. Guiden är inte en uppmaning att
pusha eller byta branch i ett repo med pågående arbete.

### B. Pythonberoenden

Kör från klonens rot. Ingen aktivering av Pythonmiljön eller ändring av PowerShells
exekveringspolicy behövs:

Ubuntu/Bash:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r app/requirements-iot.txt -r app/requirements-orbits.txt -r app/requirements-speech.txt -r tools/requirements-record.txt
```

Windows/PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r app/requirements-iot.txt -r app/requirements-orbits.txt -r app/requirements-speech.txt -r tools/requirements-record.txt
```

Avbryt vid installationsfel. Tillgängligheten av Piper och dess beroenden på vald
Windows/Python/processor-kombination återstår att verifiera. Guiden förutsätter inte
att Linuxmiljön `.venv` kopieras till Windows. Kravfiler för att hämta och bygga data
från grunden behövs inte för en komplett paketbaserad installation.

### C. Installera ett granskat lokalt datapaket

Hämta paketet via en av projektansvarig godkänd överföringsväg, utan USB-beroende.
Lägg det exempelvis som `demo-data.zip` i hemmappen. Paketet ska innehålla nödvändiga
filer för de scenarier som ska köras, tillsammans med käll- och licensuppgifter.
Lokala visningsprofiler, loggar och inloggningsuppgifter ska inte följa med.
Paketskaparen måste granska även innehållet: filtrering på filnamn bevisar inte att
filerna saknar hemligheter eller att distribution är tillåten.

Verifiera först hela paketet utan att skriva filer. Installera därefter, endast om
kontrollen lyckas och paketets innehåll är godkänt:

Ubuntu/Bash:

```bash
.venv/bin/python -m tools.install_data "$HOME/demo-data.zip" --dry-run
.venv/bin/python -m tools.install_data "$HOME/demo-data.zip"
```

Windows/PowerShell:

```powershell
.\.venv\Scripts\python.exe -m tools.install_data "$HOME\demo-data.zip" --dry-run
.\.venv\Scripts\python.exe -m tools.install_data "$HOME\demo-data.zip"
```

Importören lämnar identiska befintliga filer orörda och avbryter om en fil skiljer sig.
Den skriver inte över `data/display-profiles.json`. Den laddar inte databasen och
garanterar inte att paketet är komplett. Ändra inte paketet eller målmappen under
importen. Ett avbrott under själva skrivningen kan lämna en delvis installerad uppsättning;
undersök felet i stället för att radera eller skriva över befintliga data automatiskt.
Utrymme behövs både för ZIP-filen, tillfälligt uppackade filer, installerade data och
programberoenden (eller Dockerbilder för Docker-vägen). Fastställ storleken från det
verkliga paketet, inte äldre storleksuppgifter.

Om webbibliotek eller röster inte ingår i det godkända paketet kan de hämtas separat
med internetanslutning. Kör bara de hämtningar som behövs:

Ubuntu/Bash:

```bash
.venv/bin/python -m tools.fetch_web_vendor
.venv/bin/python -m tools.fetch_piper_voices
```

Windows/PowerShell:

```powershell
.\.venv\Scripts\python.exe -m tools.fetch_web_vendor
.\.venv\Scripts\python.exe -m tools.fetch_piper_voices
```

Verktygen verifierar bibliotek och röstmodeller mot fastställda kontrollsummor.
Hämtningen av webbibliotek ersätter deras befintliga versionsmappar. Gör den inte mot
en pågående demo. På Windows krävs fungerande Piper och röstmodell för uppläsning;
ingen annan systemröst väljs automatiskt. Saknat eller felande ljud loggas i backend.

### D. Kontrollera data och fyll PostGIS för valda scenarier

Exemplet väljer enbart Västmanland. Byt namnet till ett scenario som paketet faktiskt
omfattar: `vastmanland2014`, `sundsvall2026`, `skane2024`, `ljusdal2018`,
`vasternorrland2025`, `kramfors2026`, `flenkommun2024`, `flen2024`, `flenkommun2021`
eller `flen2019`.

Ubuntu/Bash:

```bash
SCENARIO=vastmanland2014
.venv/bin/python -m tools.startup_check "$SCENARIO"
```

Windows/PowerShell:

```powershell
$Scenario = "vastmanland2014"
.\.venv\Scripts\python.exe -m tools.startup_check $Scenario
```

Kontrollen är skrivskyddad och ska avslutas med kod 0. Den kontrollerar Python-version,
Chrome, Docker och vissa konfigurerade datafiler/metadata. MET Norways prognoser är
valfria: saknas de visas `OPTIONAL/MISSING`, kontrollen godkänns ändå och demons panel
**Väderprognos** blir tom. Den verifierar **inte**
alla bildfiler eller tidstäckning, Pythonpaket, databasens innehåll, ljud eller
fönsterplacering. Utred varje `MISSING/FAILED`; ett lyckat resultat är inte ett
godkännande av hela installationen.

**Följande kommandon ändrar databasen.** Kör bara vid avsedd installation eller
omladdning av det valda scenariot, med demon stoppad. `load_postgis` skapar databasen
vid behov och ersätter scenariots demotabeller. Den befintliga Docker-volymen ska
inte raderas. Starta tjänsterna och vänta tills PostGIS är friskt:

```text
docker compose up -d tiles postgis mosquitto
docker compose ps
```

När PostGIS visar `healthy`, ladda det valda scenariot:

Ubuntu/Bash:

```bash
TECHSEED_SCENARIO="$SCENARIO" .venv/bin/python -m tools.load_postgis
```

Windows/PowerShell:

```powershell
$env:TECHSEED_SCENARIO = $Scenario
.\.venv\Scripts\python.exe -m tools.load_postgis
Remove-Item Env:TECHSEED_SCENARIO
```

Kontrollera att kommandot lyckas och rapporterar `Loaded into ...`. Upprepa endast för
övriga valda scenarier, med respektive namn. Startverktyget väljer scenariots egen
kartfil när demon startas; kartan som visas av den första Compose-starten kan vara standardkartan.

### E. Start och verifiering på måldatorn

Ubuntu/Bash:

```bash
.venv/bin/python -m tools.start_demo vastmanland2014
```

Windows/PowerShell:

```powershell
.\.venv\Scripts\python.exe -m tools.start_demo vastmanland2014
```

Utelämna scenarionamnet för menyn. Menyn listar alla scenarier i koden; de som saknar
installerade data är gråa med texten "Data saknas" och går inte att välja. Ctrl+C stoppar backend
och simulerade noder, men lämnar webbläsarfönster och Docker-tjänster igång.

Checklista för Windows-VM, ännu inte genomförd:

- Anteckna Windows-, Python-, Chrome-, Docker- och VM-version, processorarkitektur,
  grafikinställningar, skärmantal och skalningsfaktorer.
- Kontrollera att Docker faktiskt kör Linuxcontainrar och att tjänsterna svarar.
- Prova start och stopp, meny, scenariobyte och STARTA OM DEMO. Kontrollera att din
  vanliga Chrome inte stängs när demofönstren stängs.
- Prova fönsterplacering med en skärm och med flera skärmar om VM:n medger det,
  inklusive olika skalning och en skärm till vänster om primärskärmen.
- Kontrollera 2D/3D, karta, satellitbilder, simulerade MQTT-noder och PostGIS-frågor.
- Prova Alma-uppläsning, UPPLÄSNING av/på och stopp under pågående tal.
- Prova avsedd offlinekörning efter att alla data och Dockerbilder installerats.
  Valbara nätkartor och andra nätberoende lager blir inte offline genom dataimporten.

Stoppa startverktyget innan den automatiska demokontrollen körs; den startar egen
backend och simulerade noder. Använd valt scenario och en ny rapportmapp:

Ubuntu/Bash:

```bash
TECHSEED_SCENARIO="$SCENARIO" .venv/bin/python -m tools.check_demo --headed --out "$HOME/demo-check-installation"
```

Windows/PowerShell:

```powershell
$env:TECHSEED_SCENARIO = $Scenario
.\.venv\Scripts\python.exe -m tools.check_demo --headed --out "$HOME\demo-check-installation"
Remove-Item Env:TECHSEED_SCENARIO
```

Kontrollen startar inte Docker-tjänsterna; de måste redan köra med rätt scenariokarta.
Spara rapporten och notera scenariofel separat från plattformsfel. En VM kan verifiera
funktion, men dess WebGL-bildfrekvens är inte ett prestandagodkännande av mässdatorn.
Demokontrollen ersätter inte manuella prov av ljud och fönstrens livscykel.

### F. Skapa paketet – endast för den som ansvarar för data

Granska filinnehåll, källhänvisningar och distributionsrättigheter först. Skapa sedan
en lokal JSON-fillista med paketversion, avsedd kodrevision, scenarionamn och varje
enskild godkänd fil. Exemplet visar bara formatet och är **inte ett körbart datapaket**:

```json
{
  "package_version": "example-only",
  "code_revision": "replace-with-approved-commit",
  "scenarios": ["vastmanland2014"],
  "files": ["data/example/approved-input.json"]
}
```

Spara listan lokalt, exempelvis som `selection.json` utanför repot. Verktyget skannar
inte kataloger och avgör inte om listan ger en komplett demo. Det samlar inte
automatiskt in hemligheter, visningsprofiler eller Docker-volymer. Källmetadata och
licensfiler måste också listas uttryckligen där de behövs. Outputfilen får inte finnas.

Ubuntu/Bash:

```bash
.venv/bin/python -m tools.package_data "$HOME/selection.json" "$HOME/demo-data.zip" --dry-run
.venv/bin/python -m tools.package_data "$HOME/selection.json" "$HOME/demo-data.zip"
```

Windows/PowerShell:

```powershell
.\.venv\Scripts\python.exe -m tools.package_data "$HOME\selection.json" "$HOME\demo-data.zip" --dry-run
.\.venv\Scripts\python.exe -m tools.package_data "$HOME\selection.json" "$HOME\demo-data.zip"
```

Pröva paketet i en separat ren klon och genomför kontrollerna ovan innan det lämnas
vidare via godkänd överföringsväg. En lyckad kontrollsumma ersätter inte det provet.

### G. Windows med lokala tjänster – utan Docker eller WSL

Denna väg är ett uttryckligt alternativ. **Ubuntus Docker-installation, startkommando
och konfigurationsfiler ändras inte.** På Windows behövs ingen fungerande WSL-miljö
eller nästlad virtualisering för de lokala tjänsterna. Vägen provades i en Windows-VM
2026-10-22; vad som provades och inte står i rapporten som nämns nedan.

Gör först A–C ovan för en ren, lokal Windows-klon, Pythonberoenden och ett godkänt
datapaket. Hoppa över Docker-installation och steg D–E. Använd Python 3.12 x64 för
det planerade Windows-provet; byt då miljökommandot i B till `py -3.12 -m venv .venv`.
Kör inte från en delad VirtualBox-mapp: klonen, Pythonmiljön och programmens runtime
ska ligga på Windows egen lokala disk. Verifiera att den valda Git-revisionen även
innehåller `tools/native_services.py` och de två `tools/start_native_*.py`-verktygen.

**Prova i en VirtualBox-VM.** Vägen provades 2026-10-22 i en Windows 11-VM i VirtualBox
7.0.16 (`reports/2026-10-22-windows-vm-test-claude-opus-5-5.md`). Med 4 virtuella
processorer blev VM:en överbelastad när 3D-globen ritades i mjukvara, och med VirtualBox
3D-acceleration påslagen låste den sig. Det fungerade med **minst 8 processorer och
3D-accelerationen avstängd**. En VM utan grafikkort säger inget om prestandan på
utställningsdatorn. Ta en ögonblicksbild av VM:en innan du installerar något.

**Administratörsfönster.** Programmen installeras som vanligt, men att stoppa en
Windows-tjänst eller ändra hur den startar kräver ett PowerShell-fönster som öppnats med
högerklick och **Kör som administratör** (Run as administrator); i ett vanligt fönster
svarar Windows "Cannot open … service". Gör allt annat i ett vanligt fönster.

#### G1. Installera programmen separat

Installera från respektive projekts angivna källor:

| Program | Val för första Windows-provet | Källa/anvisning |
|---|---|---|
| Node.js | 22.x eller 24.x, Windows x64 (24.17.0 provat 2026-10-22) | [Node.js](https://nodejs.org/en/download); öppna ny PowerShell efter installation |
| Microsoft Visual C++ Redistributable | x64 | Krävs enligt [TileServer GL:s Windows-anvisning](https://tileserver.readthedocs.io/en/latest/installation.html) |
| PostgreSQL | 16, Windows x64 | [PostgreSQLs Windows-sida](https://www.postgresql.org/download/windows/) länkar till EDB-installationen |
| PostGIS | En släppt Windows-version kompatibel med vald PostgreSQL 16-installation | [PostGIS för Windows](https://postgis.net/documentation/getting_started/install_windows/), via StackBuilder eller angiven installerare |
| Mosquitto | Officiell Windows x64-installation | [Mosquitto](https://mosquitto.org/download/); anteckna version och installationssökväg |

Windows-provet 2026-10-22 använde Node.js 24.17.0, PostgreSQL 16.15 med PostGIS 3.6
och Microsoft Edge; övriga kombinationer är inte provade. Installera
inte ett godtyckligt senare PostgreSQL/PostGIS-par utan att kontrollera kompatibiliteten.
Välj lokal åtkomst för PostgreSQL och behåll autentisering; ändra inte till `trust`.
Spara administratörslösenordet säkert utanför repo och kommandon. Exemplet nedan
använder port 5432, men en befintlig installation kan behöva en annan port.

Mosquitto ska inte samtidigt köras som automatisk Windows-tjänst på port 1883 när
startverktyget ska äga processen. Windows-installationen av Mosquitto skapar en sådan
tjänst. Ställ den på manuell start i ett administratörsfönster:

```powershell
Stop-Service mosquitto
Set-Service mosquitto -StartupType Manual
```
 Om en tjänst redan använder porten: identifiera den och besluta separat hur
den ska hanteras; stoppa inte okända tjänster eller ändra deras konfiguration.
Startverktyget vägrar ersätta en process på port 1883 eller kartport 8081.
Används 1883 av ett annat program som ska fortsätta gå – i Windows-provet 2026-10-22 var det
zenon Data Hub (COPA-DATA), som har en egen Mosquitto – kan demons egen broker i stället köras
på en annan port med `--mqtt-port`, till exempel `--mqtt-port 18830`, både i `startup_check`
och i `start_demo`. Backend och de simulerade noderna följer med till samma port.

Installera fullständiga TileServer GL i en separat runtime-mapp. `tileserver-gl-light`
saknar den rasterrendering som demon använder. Följande hämtar npm-paket och kan köra
deras installationsskript; kör bara mot betrodda källor och med nätåtkomst:

```powershell
node --version
npm.cmd --version
$Runtime = Join-Path $HOME "techseed-runtime"
New-Item -ItemType Directory -Path $Runtime -Force
npm.cmd install --prefix "$Runtime" --save-exact tileserver-gl@5.6.0
```

Node-versionen ska vara 22.x eller 24.x; Windows-provet använde 24.17.0. Vid npm-/DLL-/renderingsfel: stanna och
spara feltexten. Kringgå inte kontrollsummor eller ersätt servern med light-versionen.
Spara skapad `package-lock.json` för spårbarhet vid jämförande installationer; en
fast toppnivåversion ensam låser inte alla transitiva beroenden mellan installationer.
Denna runtime behöver inte checkas in eller installeras i `data/`.

#### G2. Förbered lokal PostGIS med rätt behörighet

PostgreSQL ska köras som sin installerade Windows-tjänst; demon startar eller stoppar
inte databastjänsten. Administratören behöver skapa demots egen roll och databas samt
aktivera PostGIS. Ge inte demots normala roll superuser-rättighet bara för att få
installationen att fungera.

Exemplet avser **en ny lokal installation** och bara Västmanland. Om rollen eller
databasen redan finns: granska dem först och kör inte skapandekommandona blint.
Kör följande i PowerShell och använd installationssökvägen som faktiskt gäller:

```powershell
$Psql = "C:\Program Files\PostgreSQL\16\bin\psql.exe"
& $Psql --host=127.0.0.1 --port=5432 --username=postgres --dbname=postgres -W
```

`-W` frågar efter administratörens lösenord interaktivt. Skriv sedan följande **inne
i psql**, inte i PowerShell. `\password` frågar efter demots lösenord utan att lägga
det som klartext i SQL-kommandot:

```sql
CREATE ROLE firemap LOGIN;
\password firemap
CREATE DATABASE firemap OWNER firemap;
\connect firemap
CREATE EXTENSION IF NOT EXISTS postgis;
SELECT PostGIS_Version();
\q
```

Rollnamnet är `firemap`, medan databasnamnet beror på scenariot:

| Scenario | Databas |
|---|---|
| `vastmanland2014` | `firemap` |
| `sundsvall2026` | `sundsvall2026` |
| `skane2024` | `skane2024` |
| `ljusdal2018` | `ljusdal2018` |
| `vasternorrland2025` | `vasternorrland2025` |
| `kramfors2026` | `kramfors2026` |
| `flenkommun2024` | `flenkommun2024` |
| `flen2024` | `flen2024` |
| `flenkommun2021` | `flenkommun2021` |
| `flen2019` | `flen2019` |

För övriga installerade scenarier skapar administratören respektive databas med
`OWNER firemap` och aktiverar PostGIS där på samma sätt. Rollen skapas bara en gång.
Föraktiveringen behövs eftersom `load_postgis` annars kan behöva större behörighet
för att skapa databasen eller PostGIS-tillägget. Laddaren ersätter senare demotabeller,
men ska inte användas som generell administratör av andra databaser.

#### G3. Lösenordsfil och anslutningsinställningar

Skapa PostgreSQLs lösenordsfil **utanför repot** med en textredigerare. Följande öppnar
en lokal fil; om filen redan finns ska befintliga poster bevaras:

```powershell
$PassDir = Join-Path $env:APPDATA "postgresql"
New-Item -ItemType Directory -Path $PassDir -Force
$PassFile = Join-Path $PassDir "pgpass.conf"
notepad.exe "$PassFile"
```

Lägg till en post enligt libpq-formatet, med demorollens verkliga lösenord i stället
för platshållaren. Spara som UTF-8 utan BOM. Det här är **filinnehåll, inte ett kommando**:

```text
127.0.0.1:5432:*:firemap:ERSÄTT_MED_DEMOROLLENS_LÖSENORD
```

`*` tillåter denna lokala demoroll i flera scenariodatabaser och i `postgres`, som
laddaren frågar för att kontrollera vilka databaser som finns. Kolon och backslash
i lösenordet måste skyddas enligt [libpq:s lösenordsfilsformat](https://www.postgresql.org/docs/16/libpq-pgpass.html).
Begränsa Windows-filens åtkomst till avsedda konton via filens säkerhetsinställningar.
Checka aldrig in filen och dela inte dess innehåll i loggar eller felsökningssvar.

Ange anslutning och runtime i PowerShell-fönstret som ska användas. Följande innehåller
inga lösenord och gäller bara detta fönster och dess underprocesser:

```powershell
$Scenario = "vastmanland2014"
$Runtime = Join-Path $HOME "techseed-runtime"
$NodeModules = Join-Path $Runtime "node_modules"
$Mosquitto = "C:\Program Files\mosquitto\mosquitto.exe"
$env:TECHSEED_DB_MODE = "native"
$env:TECHSEED_PSQL_PATH = "C:\Program Files\PostgreSQL\16\bin\psql.exe"
$env:TECHSEED_DB_HOST = "127.0.0.1"
$env:TECHSEED_DB_PORT = "5432"
$env:TECHSEED_DB_USER = "firemap"
$env:TECHSEED_DB_PASSFILE = Join-Path $env:APPDATA "postgresql\pgpass.conf"
```

Anpassa sökvägar och port till installationen. Native-anslutningen använder UTF-8,
anslutningstimeout och `psql -w`: den frågar inte efter lösenord om filen saknas eller
inte matchar. `PGPASSWORD` används inte av native-klienten. Startflaggan nedan väljer
native-läge i backend, men fristående dataladdning behöver miljövariabeln ovan.

Saknar datorn Chrome, välj Edge för hela fönstret, så att alla verktyg och deras
underprocesser använder det utan `--browser edge` i varje kommando:

```powershell
$env:TECHSEED_BROWSER = "edge"
```

#### G4. Kontrollera filer och ladda valt scenario

Kör från klonens rot. Förhandskontrollerna nedan startar inga tjänster:

```powershell
.\.venv\Scripts\python.exe -m tools.start_native_tiles $Scenario --node-modules "$NodeModules" --dry-run
.\.venv\Scripts\python.exe -m tools.start_native_mqtt --dry-run
.\.venv\Scripts\python.exe -m tools.startup_check $Scenario --services native --node-modules "$NodeModules" --mosquitto "$Mosquitto"
```

Den sista kontrollen kör Node för versionskontroll och ansluter till scenariots databas
med den skrivskyddade frågan `SELECT PostGIS_Version()`. Den startar inte kartserver,
broker eller PostgreSQL och använder inte Docker. Den kontrollerar inte att alla
demotabeller eller rasterbilder finns. Kontrollera kod 0 efter varje steg; vid fel
ska nästa steg inte köras. `$LASTEXITCODE` visar det senaste programmets resultat.

**Nästa kommando ändrar databasen och ersätter scenariots demotabeller.** Kör endast
efter godkänd installation/omladdning, med demon stoppad och rätt scenario valt:

```powershell
$env:TECHSEED_SCENARIO = $Scenario
.\.venv\Scripts\python.exe -m tools.load_postgis
Remove-Item Env:TECHSEED_SCENARIO
```

Kräv lyckat resultat och `Loaded into ...`. Vid behörighetsfel: kontrollera G2; byt inte
slentrianmässigt till administratörsrollen. Upprepa endast för andra scenarier vars
data har installerats och vars databaser förberetts. Ingen Docker-volym ska kopieras.

#### G5. Start, stopp och verifiering

I samma PowerShell-fönster, från klonens rot:

```powershell
.\.venv\Scripts\python.exe -m tools.start_demo $Scenario --services native --node-modules "$NodeModules" --mosquitto "$Mosquitto"
```

Utelämna `$Scenario` för menyn. Native-läget startar en egen Node-kartserver och en
egen Mosquitto, båda på localhost, och använder redan körande PostgreSQL. Vid avslut,
scenariobyte och STARTA OM DEMO städas de egna tjänsteprocesserna. Ctrl+C stoppar även
backend och simulerade noder men lämnar PostgreSQL och Chrome-fönstren kvar.
Om en port redan är upptagen avbryts starten utan att den befintliga tjänsten stoppas;
`startup_check` visar då vilken port det gäller. Lägg till `--mqtt-port 18830` (eller en
annan ledig port) om det är 1883.

Utför checklistan i E, men ersätt Docker-kontrollerna med kontroller av lokal
PostgreSQL/PostGIS, TileServer GL och Mosquitto. Anteckna deras och Nodes versioner.
Verifiera särskilt baskartan, vägnummer/järnvägstunnlar ovanpå bilder, båda vyerna,
svenska ortnamn i databasfrågor, MQTT, Alma-ljud och städning efter omstart/scenariobyte.
Verifiera också offlinekörning när program och data väl är installerade.

Automatisk demokontroll kan köras **mot den native-demo som redan går**, från ett
andra PowerShell-fönster. Använd `--base-url` så att kontrollen inte startar egen
backend med fel inställningar. I detta andra fönster, från samma klon:

```powershell
$env:TECHSEED_SCENARIO = "vastmanland2014"
.\.venv\Scripts\python.exe -m tools.check_demo --headed --base-url http://127.0.0.1:8765 --out "$HOME\demo-check-native"
Remove-Item Env:TECHSEED_SCENARIO
```

Byt scenarionamnet till det som faktiskt körs och välj en ny rapportmapp. Testet styr
och återställer den körande demon: använd det inte samtidigt som någon demonstrerar.
Det verifierar inte alla plattformsfunktioner; de manuella ljud- och fönsterproven
behövs fortfarande. Windows utan Docker är inte godkänt förrän dessa prov genomförts.

#### G6. Hämta och bygga data utan Docker

Den vanliga Windows-vägen tar data ur ett datapaket (C). Den som i stället hämtar och bygger
data själv kan köra GDAL- och osmium-stegen utan Docker med `--tools native`, eller
`$env:TECHSEED_TOOLS = "native"` för hela fönstret. Det gäller:

| Verktyg | Steg utan Docker |
|---|---|
| `tools.fetch_landsat_scene`, `tools.fetch_sentinel2_scene` | GDAL: utsnitt, kompositbilder och råa band |
| `tools.fetch_sentinel1_scene` | GDAL: radarbilderna och höjddatan för havet |
| `tools.fetch_ems_perimeters` | GDAL (`ogr2ogr`): EMS-ytorna |
| `tools.build_offline_tiles` | osmium och tilemaker, se nedan |

Programmen ska finnas på PATH, till exempel från en conda-forge-miljö med paketen `gdal` och
`osmium-tool`; installera dem enligt respektive projekts anvisningar och anteckna versionerna.
Saknas ett program avbryts verktyget med ett meddelande om det. Docker är fortfarande standard,
och Ubuntus kommandon ändras inte.

Två begränsningar:

- **Offlinekartan** byggs med tilemaker, som saknar färdig Windows-version. `build_offline_tiles
  --tools native` kräver tilemaker på PATH och `--tilemaker-resources` med tilemakers
  `resources`-mapp. På Windows tas kartan i stället ur scenariots datapaket.
- **3D-terrängen** (`tools.build_terrain`) kräver fortfarande Docker och tas på Windows ur
  datapaketet.

Provat 2026-10-22 på Ubuntu med GDAL 3.13.3 och osmium 1.19.1 från conda-forge, mot Docker-vägen
med samma indata: osmium-utdraget, EMS-konverteringen och kompositbilderna blev desamma. Höjddata
som medelvärdesbildas (`-r average`, Sentinel-1:s havsmask) skiljer sig något, i Flens område i
medel 0,9 m och som mest 10 m, eftersom containern har GDAL 2.4 och metoden ändrades i GDAL 3.
Hämtning från Planetary Computer med native GDAL och körning på Windows är inte provade.

## Vad demon är

Demon spelar upp skogsbranden i Västmanland sommaren 2014 med riktiga satellitdata. Den
visar hur satelliter upptäcker branden, hur sensorer på marken bekräftar den och hur en
spårbar bedömning byggs upp. En genomkörning tar ungefär två minuter.

Demon har två skärmar:

- **Huvudskärmen** är den stora skärmen som besökarna ser: en 3D-jordglob med branden.
- **Mission control** är en mindre skärm för dig som operatör, med knappar som styr
  demon. Besökarna ser den inte.

Båda skärmarna är sidor i webbläsaren. De hämtar allt från ett program på datorn,
**backend**, som måste vara igång så länge demon körs.

Samma skärmar kan också köra en andra demo: **översvämningen i Sundsvall 2026**, ett
scenario byggt på det verkliga regnet i augusti 2026. Den beskrivs i Del 5. Del 1–4 gäller
branddemon, och det mesta i dem gäller också översvämningen.

## Ord som används i guiden

| Ord | Betydelse |
|---|---|
| Terminal | Ett fönster där du skriver kommandon. I Ubuntu öppnas den med Ctrl+Alt+T. |
| Kommando | En rad text som du klistrar in i terminalen och kör med Enter. |
| Repot | Mappen `techseed-geospatial-intelligence` med all kod. Kommandona körs från den mappen. |
| Docker | Ett program som kör färdiga tjänster, till exempel databasen, utan att de behöver installeras en och en. |
| Backend | Programmet som skärmarna hämtar data från. Startas i avsnitt 7. |
| Scenarioklockan | Tiden i demon, alltså en tidpunkt i augusti 2014. Den är gemensam för alla skärmar. |

Kopiera kommandona från kodblocken i guiden. En rad som börjar med `#` är en förklaring
och gör ingenting om den råkar komma med.

---

# Del 1 – Förbered datorn

Del 1 görs en gång per dator, helst några dagar före mässan. Den kräver internet. Efteråt
fungerar demon utan internet.

## 1. Program som behövs

Datorn behöver:

- **Linux**, till exempel Ubuntu, för denna äldre installationsväg. Windows beskrivs
  separat i sektionen **Installation från Git utan USB** ovan.
- **Git**, för att hämta koden, och **curl**, för att hämta kartutdraget.
- **Python 3** med `venv`, som demon är skriven i.
- **Docker** med `docker compose`, för databasen, kartan och meddelandetjänsten.
- **Google Chrome**, för skärmarna.
- **wmctrl**, så att skärmarna kan öppnas på sina platser (avsnitt 8). Installeras med
  `sudo apt install wmctrl`.
- **Ett grafikkort** som klarar 3D i webbläsaren. De flesta datorer från de senaste åren
  gör det.
- **Cirka 10 GB ledigt diskutrymme.**

Kontrollera vad som redan finns genom att köra de här raderna i terminalen. Varje rad ska
svara med ett versionsnummer:

```bash
git --version
curl --version
python3 --version
docker --version
docker compose version
google-chrome --version
wmctrl --version
```

Om en rad svarar `command not found` saknas programmet. Installera det enligt programmets
egen installationsanvisning, eller be den som sköter datorn om hjälp. För Docker behöver
ditt konto dessutom få köra Docker utan `sudo`. Det ingår i Dockers anvisning för Linux
("post-installation steps"), och kräver att du loggar ut och in igen.

## 2. Åtkomster och konton

Det mesta som demon använder är öppet och kräver inget konto. Två saker kräver inloggning:

| Vad | Varför | Vad du behöver |
|---|---|---|
| **GitHub-repot** `jeryymekjobb/techseed-geospatial-intelligence` | För att hämta koden. | Åtkomst till repot och en SSH-nyckel på GitHub. Fråga ägaren av repot om åtkomst. |
| **Space-Track** (space-track.org) | För satelliternas banor 2014. | Ett eget, gratis konto. Registrera dig på space-track.org och godkänn villkoren. Använd ett eget konto i stället för att dela någon annans inloggning. |

Fyra konton behövs bara i särskilda fall och kan hoppas över för demon:

| Vad | När det behövs |
|---|---|
| Copernicus CDS | Bara om vinddatan från ERA5-Land ska hämtas om. Den finns redan i repot. |
| LSA SAF (EUMETSAT) | Bara för att hämta Meteosats brandpixlar och brandrisken (avsnitt 5, steg 5.10). Ett gratis konto på mokey.lsasvcs.ipma.pt, sparat i `~/.netrc` som `machine datalsasaf.lsasvcs.ipma.pt login … password …`, aldrig i repot. |
| EUMETSAT Data Store | Bara för att hämta Meteosats molntoppar (Del 9). Ett gratis konto på user.eumetsat.int; API-nyckeln från api.eumetsat.int/api-key sparas med `eumdac set-credentials` i `~/.eumdac/credentials`, aldrig i repot. |
| Lantmäteriet Geotorget | Bara för Lantmäteriets kartor och fastighetsgränser. De är avstängda i demon. |

Det här behöver **inget konto**: Landsat-bilden (Microsoft Planetary Computer), höjddata
(Copernicus på AWS), webbiblioteken (npm), Docker-tjänsterna (Docker Hub) och kartutdraget
från OpenStreetMap. Brandens satellitdetektioner, väderdata och kartdata över orter och
terräng ligger redan i repot.

### Spara inloggningen till Space-Track

Programmet som hämtar satellitbanorna läser din inloggning från en fil i din hemmapp,
`~/.spacetrackrc`. Filen ligger utanför repot, så inloggningen hamnar aldrig i koden.

Skapa filen med ett textredigeringsprogram, till exempel:

```bash
nano ~/.spacetrackrc
```

Skriv två rader, med din egen e-postadress och ditt eget lösenord:

```
identity=din.adress@example.com
password=ditt-lösenord
```

Spara med Ctrl+O och Enter, och stäng med Ctrl+X. Gör sedan filen läsbar bara för dig:

```bash
chmod 600 ~/.spacetrackrc
```

Prova gärna att logga in på space-track.org i webbläsaren med samma uppgifter först. Ett
lösenord som inte fungerar där fungerar inte heller i programmet, och för många
misslyckade försök kan spärra kontot.

## 3. Hämta koden

Hämta repot till din hemmapp och gå in i det:

```bash
cd ~
git clone git@github.com:jeryymekjobb/techseed-geospatial-intelligence.git
cd techseed-geospatial-intelligence
```

**Alla kommandon i resten av guiden körs från den här mappen.** Öppnar du en ny terminal
senare, gå först in i mappen igen:

```bash
cd ~/techseed-geospatial-intelligence
```

## 4. Installera demons Python-delar

Demon behöver några tillägg till Python: för sensorerna, satelliternas banor,
uppläsningen och generalrepetitionen. De installeras i en egen mapp, `.venv`, så att resten
av datorn inte påverkas:

```bash
python3 -m venv .venv
.venv/bin/pip install -r app/requirements-iot.txt -r app/requirements-orbits.txt \
  -r app/requirements-speech.txt -r tools/requirements-record.txt
```

Det tar någon minut. Sista raden ska börja med `Successfully installed`.

## 5. Hämta och bygga data

### Installera färdiga data utan USB

Använd den nya sektionen **Installation från Git utan USB**, steg C–E, för ett granskat
lokalt paket, data- och tjänstekontroll, laddning av valda scenariers PostGIS och start.
Kopiera inte hela `data/` okontrollerat: mappen innehåller även lokala profiler och loggar.
Databasen ligger i Docker och följer inte med datapaketet. Resterande steg nedan behövs
bara om data ska hämtas och byggas från grunden på Ubuntu; den vägen är inte portad till Windows.

### Hämta datan från början

Kör stegen i tur och ordning. Vissa tar några minuter. Varje steg skriver ut vad det gör,
och om något går fel visas ett felmeddelande. Läs det och se avsnitt 13, eller be om hjälp
innan du går vidare.

```bash
# 5.1 Webbiblioteken för 3D-globen och satelliterna
python3 -m tools.fetch_web_vendor

# 5.2 Höjddata (cirka 100 MB) och 3D-terrängen som byggs av den
python3 -m tools.fetch_copernicus_dem
python3 -m tools.build_terrain

# 5.3 Kartutdraget för Sverige (cirka 930 MB) och offline-kartan som byggs av det
mkdir -p data/osm
curl -L -o data/osm/sweden-latest.osm.pbf https://download.openstreetmap.fr/extracts/europe/sweden-latest.osm.pbf
python3 -m tools.build_offline_tiles

# 5.4 Starta tjänsterna: databasen, kartan och meddelandetjänsten för sensorerna
docker compose up -d tiles postgis mosquitto

# 5.5 Fyll databasen
python3 -m tools.load_postgis

# 5.6 Satelliternas banor 2014 (använder ~/.spacetrackrc)
python3 -m tools.fetch_tle_history

# 5.7 Landsat-bilderna före, under och efter branden (10 juni, 4 augusti och 14 september 2014)
.venv/bin/python -m tools.fetch_landsat_scene

# 5.8 MET Norways väderprognoser som de utfärdades, och SMHI:s observerade blixtar
TECHSEED_SCENARIO=vastmanland2014 .venv/bin/python -m tools.fetch_met_forecasts
TECHSEED_SCENARIO=vastmanland2014 .venv/bin/python -m tools.fetch_smhi_lightning

# 5.9 Rösterna för uppläsningen (alla demona använder dem)
.venv/bin/python -m tools.fetch_piper_voices

# 5.10 Meteosats brandpixlar och brandrisken från LSA SAF (kräver LSA SAF-kontot i ~/.netrc, avsnitt 2)
.venv/bin/pip install -r tools/requirements-meteosat.txt
TECHSEED_SCENARIO=vastmanland2014 .venv/bin/python -m tools.fetch_meteosat_frp
TECHSEED_SCENARIO=vastmanland2014 .venv/bin/python -m tools.fetch_meteosat_frm
```

Första gången du kör 5.4 hämtar Docker tjänsterna, cirka 2,5 GB. Det sker bara en gång.

När 5.6 är klar skriver den hur många "element sets" den hämtade för varje satellit, till
exempel `Suomi NPP: 18 element sets`. När 5.7 är klar skriver den en rad per bild, till exempel
`before: … – data över 100.0 % av brandområdet, moln över 0.0 %`.

## 6. Generalrepetition – på varje dator

Det här steget ingår i installationen på **varje dator** där demon ska köras. Det visar
att allt fungerar och mäter hur jämnt 3D-vyn rör sig på just den datorn. Kör det med
skärmarna inkopplade som de ska vara i montern.

Stäng först en demo som redan är igång (Ctrl+C i terminal 1 och 2 från avsnitt 7).
Kontrollen startar en egen.

```bash
.venv/bin/python -m tools.check_demo --headed --out ~/demo-check-$(hostname)
```

Tre webbläsarfönster öppnas och demon körs av sig själv i några minuter. Rör inte
fönstren under tiden. När den är klar skriver den en rapport, som också sparas i
`~/demo-check-<datorns namn>/report.txt` tillsammans med en skärmdump per steg. Skicka
mappen till den som ansvarar för demon, så att datorerna kan jämföras.

Så här läser du rapporten:

- **Grafik** visar vilket grafikkort Chrome använde.
- Alla tio steg ska stå som **GODKÄND**, och sista raden ska vara `RESULTAT: GODKÄND`.
- **Bilder per sekund i 3D** säger hur jämnt 3D-vyn rör sig. Under 20 skriver rapporten en
  **VARNING**: kameran och satelliterna kommer att kännas ryckiga. Gränsen är en tumregel.

Står något steg som **UNDERKÄND**, se avsnitt 13. Skärmdumparna visar hur det såg ut.

### Datorer med två grafikkort

Många bärbara datorer har ett inbyggt grafikkort (ofta Intel) och ett kraftfullare (ofta
NVIDIA). Chrome använder oftast det inbyggda, och det står under **Grafik** i rapporten.
Att tvinga Chrome till NVIDIA-kortet fungerade inte på den dator där demon provades,
varken via PRIME offload eller via Vulkan: 3D-vyn startade inte alls. Skicka därför rapporten vidare om den visar en varning, i stället för
att försöka byta grafikkort själv.

---

# Del 2 – På mässdagen

## 7. Starta demon

**Enklast:** ett kommando startar allt – tjänsterna, backend, sensorerna i montern och de tre
skärmarna på sina platser. Öppna en terminal, gå in i repot (`cd ~/techseed-geospatial-intelligence`)
och kör:

```bash
.venv/bin/python -m tools.start_demo
```

Först öppnas bara mission control, med menyn **Techseed Geospatial Intelligence Demos** och en
knapp per demo. Klicka på **Skogsbranden i Västmanland 2014**. Kommandot skriver steg 1/4 till
4/4 och sedan "Demon går", och då öppnas alla tre skärmarna i demon. Med demons namn,
`.venv/bin/python -m tools.start_demo vastmanland2014`, hoppar det över menyn.

Låt terminalen stå öppen hela dagen. **BYT SCENARIO** längst ned i mission controls vänstra kolumn
avslutar demon, stänger satellitmonitorn och huvudskärmen och visar menyn i mission control igen.
**STARTA OM DEMO** bredvid den stänger alla skärmarna, startar om backend och sensorerna och öppnar
skärmarna igen med samma scenario från dess sparade start, till exempel om något har hängt sig.
Båda frågar först. Ctrl+C i terminalen stoppar backend och sensorerna. Står det att något redan
svarar på port 8765 går en backend redan; stoppa den först. Sensorernas rader hamnar i
`data/node-sim.log`. Skärmarna öppnas på 4 augusti 2014 kl. 11:30 svensk tid; avsnitt 8 beskriver
dem.

**Slutbilden.** När uppspelningen når demons stopp visar huvudskärmen slutbilden: "TECHSEED
GEOSPATIAL INTELLIGENCE – Physical world. Space. Data. Intelligence. – From Orbit to Decision." och
under det scenariots namn och att datan inte är i realtid. Den står kvar tills du trycker RESET,
PLAY eller hoppar i tiden.

**Kioskläge, när ingen står vid demon.** Tryck **KIOSKLÄGE AV** överst i menyn så att det står
**KIOSKLÄGE PÅ**, och välj sedan demo (eller starta med `--kiosk`). Då sköter demon sig själv:

- Sammanfattningen visas i 20 sekunder ("Startar av sig själv om … s"), sedan spelas demon upp.
- Vid stoppet står slutbilden i 30 sekunder ("Demon börjar om om … s"), sedan börjar demon om från
  start.
- Var tionde sekund kontrollerar `start_demo` att sensorerna i montern och de tre skärmarna går, och
  startar det som har stannat. Öppnas mission control igen återställs demon och börjar från start.
- Stannar backend av sig själv, eller startar demon inte, försöker `start_demo` igen efter 10 sekunder.

Knappen **AUTOSLINGA** bredvid UPPLÄSNING i mission control slår av slingan för demon som går, till
exempel medan du visar något för en besökare, och slår på den igen. Den sparas inte i profilen;
kioskläget i menyn avgör om demon startar med slingan på. Kioskläget gäller tills `start_demo`
avslutas, också efter BYT SCENARIO och STARTA OM DEMO. Ctrl+C avslutar som vanligt. En paus med
PAUSE står kvar tills någon trycker PLAY, också i kioskläge.

**Steg för steg**, om du hellre startar delarna själv: demon behöver två program som är igång
hela dagen. Öppna **två terminaler** och gå in i repot i båda (`cd ~/techseed-geospatial-intelligence`).

Kontrollera först att tjänsterna från avsnitt 5.4 är igång. Om datorn har startats om
sedan dess, starta dem igen:

```bash
docker compose up -d tiles postgis mosquitto
```

**I terminal 1**, starta backend:

```bash
.venv/bin/python -m app.backend.server
```

Efter några sekunder ska du se raden `PostGIS: questions on`. Då är backend klar.

**I terminal 2**, starta sensorerna i montern. De är simulerade i demon, se avsnitt 11:

```bash
.venv/bin/python -m tools.mqtt_node_sim --interval 5
```

Den skriver en rad var femte sekund, till exempel `round 3: 4 nodes published`.

**Låt båda terminalerna stå öppna hela dagen.** Stänger du terminal 1 slutar skärmarna att
fungera.

## 8. Öppna skärmarna

Enklast är att låta ett kommando öppna de tre skärmarna, var och en på sin plats:

```bash
.venv/bin/python -m tools.open_screens
```

Med två skärmar hamnar satellitbevakningen på vänstra tredjedelen av den största skärmen,
huvudskärmen på resten av den och mission control på den andra skärmen. Med en skärm hamnar de
sida vid sida. Varje skärm är ett eget Chrome-fönster utan adressfält. Din vanliga Chrome
påverkas inte. När Mission Control har laddat återställs scenariot till den sparade profilen och
dess starttid. Kör kommandot igen om ett fönster har hamnat fel eller stängts: det öppnar
skärmarna på nytt på sina platser.

Vill du hellre öppna fönstren själv, öppna tre fönster i Chrome:

| Skärm | Adress | Var |
|---|---|---|
| Huvudskärmen | <http://127.0.0.1:8765/3d.html?at=2014-08-04T09:30:00Z> | Stora skärmen. Tryck F11 för helskärm. |
| Satellitbevakningen | <http://127.0.0.1:8765/monitor.html> | Bredvid huvudskärmen, så att besökarna ser båda. |
| Mission control | <http://127.0.0.1:8765/control.html> | Din skärm bredvid. |

Satellitbevakningen visar hela tiden var satelliterna är och när de passerar över branden.
Varje satellits bana är svag där den redan har flugit och stark där den är på väg. Banor ritas,
här och på 3D-globen, bara för satelliter som levererar data till marken i scenariot:
FIRMS-detektioner, Sentinel-1:s radarbilder eller någon av scenariots satellitbilder. Övriga
satelliter, som ISS, visas som en punkt med namn utan bana. Terra och
Aqua har var sin nyans av orange, och färgprickarna i listan längst ned visar vilken färg
som hör till vilken satellit.

Under världskartan och tidslinjen finns **Satellit- och IoT-händelser**, en logg över allt som
hänt sedan demons start, med den senaste händelsen överst och i gult. Loggen går att skrolla
ned till den första händelsen. Har du skrollat ned ligger vyn kvar medan nya händelser kommer
in överst; skrolla upp igen för att följa de senaste. Varje rad är märkt med var uppgiften
kommer från:

| Märkning | Händelser |
|---|---|
| *beräknat* | En satellit går in över eller lämnar branden, beräknat ur banorna |
| *FIRMS 2014* | Detektionerna från en passage: hur många och den starkaste |
| *Landsat 2014* | Landsat 8 tar en bild över branden |
| *syntetiskt* | En syntetisk IoT-sensor börjar eller slutar bekräfta händelsen: känner rök eller värme vid branden, en bräddgivare bräddar, eller en nivåsensor går över tidigare högsta nivå |
| *modell* | Hotad bebyggelse vid branden: orter som prognosen vid en satellitpassage för första gången når inom 24 h, med tidsspannet från hög till låg spridningshastighet |
| *PostGIS* | Hotad bebyggelse vid översvämningen: hur många byggnader som ligger inom 200 m från en sensor när den börjar larma och den närmaste namngivna orten, ur kartdata i PostGIS |
| *simulerat* | Från mission control: upptäcktssekvensen startar, SATCOM nere och SATCOM åter, SENSOR FAILURE, IoT av och på, och en sensor som placeras på kartan |

Loggen skriver enheterna med hela ord, till exempel "starkast 27,9 megawatt", "inom 200 meter"
och "16 till mer än 24 timmar", eftersom den läses upp. Rösten säger mätvärden avrundade till
närmaste heltal, med 5 uppåt: "starkast 28 megawatt". Förkortningar inom parentes, som (MODIS),
(VIIRS) och (NDMI), läses inte upp; skärmarna visar dem som förut. Före uppläsningen skrivs texten
om så att den uttalas rätt: decimalkomma läses "komma", ett tankstreck mellan tal "till", datum
som ordningstal ("fjortonde juli") och förkortningar med versaler bokstav för bokstav ("S M H I"),
utom de som sägs som ord (NASA, FIRMS, NOAA, SATCOM). Ord som får fel vokallängd läggs in i
uttalsordlistan `LEXICON` i `app/backend/speech.py`. Rösterna talar lite långsammare än Pipers
standard. Starta om backend efter en ändring i ordlistan. När fler än en ort hotas säger rösten
bara hur många och tidsspannet från den tidigaste till den senaste ankomsten, till exempel
"5 orter hotas inom 2 till mer än 24 timmar"; namnen står i loggen och på kartan.

Loggen räknas fram ur scenarioklockan och stämmer därför också efter **RESET** eller ett hopp
i tiden. En sensorrad visas så fort scenarioklockan når ändringen; sensorernas ändringar är
beräknade ur deras modeller i steg om 10 minuter. Efter **SENSOR FAILURE** visas inga fler rader
för den sensorn, och medan IoT är avstängt visas inga sensorrader eller byggnadsrader. Är PostGIS
inte igång blir det inga byggnadsrader; ladda om satellitbevakningen när PostGIS är igång.

**Hotad bebyggelse på kartan.** När en rad om hotad bebyggelse kommer i loggen, och läses upp,
visar huvudskärmens karta (2D och 3D) platsen med en stor röd varningstriangel och namnet i ett
rött textfält: vid branden orterna som prognosen pekar ut, vid översvämningen byggnaderna inom
200 m från givaren, i mitten av dem och med namnet på den närmaste namngivna orten i OSM (inom
2 km, annars givarens namn). Markeringen syns i 8 sekunder och släcks sedan helt, triangeln
tillsammans med namnet; hotet står kvar i loggen. Bara hot som kommer in medan klockan går
markeras; när sidan laddas, vid **RESET** och vid hopp i tiden visas inga trianglar. Markeringarna räknas ur scenarioklockan som
loggen och syns även när uppläsningen är av. Lagret heter **Hotad bebyggelse** och kan släckas i mission control.
Huvudskärmen hämtar hoten när den laddas; ladda om den om PostGIS startade senare.

**Meteosat.** Meteosat, en geostationär satellit, står över ekvatorn och ser Sverige snett. I
Västmanland såg den branden bara den 4 augusti 2014, 14:00–15:45 svensk tid: lagret **Meteosat
(geostationär, LSA SAF)** visar varje pixel som en lila rektangel på cirka 26 km², och loggen har en
rad per kvart, till exempel "Meteosat-10 (geostationär) ser branden: 2 pixlar, starkast 2592,4
megawatt". Pixlarnas läge och form är ungefärliga; de ligger några kilometer norr om FIRMS-punkterna.
Satellitbevakningen visar Meteosat-10 som en punkt över ekvatorn vid 0° längd, där den står still, och
listan säger "geostationär, ser branden hela tiden"; den har inga passager. På 3D-globen ligger den
35 800 km ut; SPACE VIEW zoomar då ut så att både jorden och Meteosat-10 syns, och jorden blir cirka en
fjärdedel av skärmens höjd.
Raden **Brandrisk enligt LSA SAF** i panelen, under demons egen brandrisk, visar dagens riskklass
(låg till extrem) och FWI vid branden, giltig från kl. 12 UTC (14:00 svensk tid). Den räknas ur
ERA5:s väder och kalibreras mot satelliternas brandobservationer, så säg "Meteosat och ERA5", inte
"uppmätt av Meteosat". Kryssa **Brandrisk (LSA SAF)** i mission control för rutor i riskklassens färg
över kartan; loggen säger när riskklassen ändras, till exempel "Brandrisken vid branden stiger till
hög enligt LSA SAF (FWI 25)". Brandrisken finns också i Kårböle 2018.

I Kårböle 2018 visar demon i stället vad Meteosat missar: Meteosat-11 såg aldrig branden vid Kårböle,
men väl branden vid Strandåsmyrvallen cirka 50 km västerut (Copernicus EMS, EMSR298). Raden
**Meteosat (geostationär)** i panelen räknar pixlarna vid Kårböle (0) och vid Strandåsmyrvallen upp
till klockan, loggen har en rad per dygn, till exempel "Meteosat-11 (geostationär) ser branden vid
Strandåsmyrvallen, 50 kilometer väster om Kårböle: 1 pixel, starkast 1021,3 megawatt – men ingen vid
Kårböle", och de lila rektanglarna syns på 3D-globen (utanför offlinekartan i 2D).

**Diagrammen under Uppspelning.** Tidsdiagrammen med scenarioklockan ligger i panelen direkt
under **Uppspelning**, i 2D och 3D: **Detektioner per dygn (UTC)** vid branden, **Regn (SMHI)** vid
översvämningen och i Skåne också **Vattenföring och vattenstånd (SMHI)**. De är kompakta, med
mätaren eller stationen på rubrikens rad, så att båda översvämningsdiagrammen syns utan att panelen
behöver rullas.

**Sammanfattning vid start.** När scenariot står vid sin start, alltså när skärmarna laddas
och efter **RESET**, visar huvudskärmen ett kort med vad demon visar och vad som är verkligt,
beräknat och simulerat, till exempel att Landsat är för molnig över Kårböle och inte är med. Sista raden säger hur lång tid uppspelningen tar med vald hastighet
och demons start och stopp, med inbromsningen vid satellitpassager inräknad, till exempel "Uppspelningen
tar cirka 21 minuter med 3 timmar per sekund"; den följer en ändrad hastighet.
Kortet ligger kvar tills du trycker **PLAY** i mission control eller knappen **▶ STARTA
SCENARIOT** längst ned i kortet, som startar uppspelningen på samma sätt. Med uppläsningen på läser
satellitbevakningen upp kortet, en rad i taget med rösterna omväxlande. Texten står i
scenariots fil (`SUMMARY` i `app/backend/scenarios/`).

**Uppläsning.** Med **UPPLÄSNING** i mission control (under FLYG TILL och ÖVERSIKT) läser
satellitbevakningen upp nya rader i loggen på svenska genom datorns högtalare, så fort
scenarioklockan når dem, med rösten alma. Av satelliterna läses bara det upp när en satellit
skickar data till marken, alltså FIRMS-detektioner och satellitbilder; att en satellit går in
över eller lämnar området syns i loggen men läses inte upp.
Inga loggrader läses upp när sidan laddas, vid **RESET** eller vid ett hopp i tiden. I Skåne läses
dessutom nivågivarnas läge upp en gång per scenariodygn så länge någon larmar, alltså ligger över
det högsta flöde eller den högsta nivå som uppmätts tidigare vid dess SMHI-station, till exempel
"Nivålarm från 5 nivågivare: Ringsjödammen övre 12 centimeter över tidigare högsta nivå".
Givare med SENSOR FAILURE eller när IoT är avstängt räknas inte med. Kommer fler än tre rader på en gång läses de tre senaste upp och sedan hur många fler det
var. Uppläsningen är på i alla scenarier om du inte stänger av den; sparar du den avstängd med
**SPARA PROFIL FÖR SCENARIOT** startar demon tyst. Backend läser upp med Piper, en svensk talsyntes som fungerar utan
nät, med rösten alma, så ljudet kommer ur den dator som kör
backend. Rösterna installeras en gång med `.venv/bin/pip install -r app/requirements-speech.txt`
och `.venv/bin/python -m tools.fetch_piper_voices`; saknas de läser datorns enklare röst
(espeak-ng) i stället. Källan till rösterna står längst ned i satellitbevakningen, som licensen
för alma kräver. Prova ljudet innan besökarna kommer: slå på uppläsningen och tryck **PLAY**.

Har du bara en stor skärm, lägg fönstren sida vid sida: satellitbevakningen till vänster,
huvudskärmen i mitten och mission control till höger. Öppna huvudskärmen först.

Slutet av huvudskärmens adress, `?at=2014-08-04T09:30:00Z`, ställer scenarioklockan på den
4 augusti 2014 kl. 11:30 svensk tid. Då hinner du visa en satellitpassage och
Landsat-bilden inom en minut.

Huvudskärmen ska visa kartan över brandområdet, och i panelen till höger ska det stå "4 aug.
2014 11:30 svensk tid".

Överst på huvudskärmen, efter den gula märkningen, står vad kartan visar under sina lager, med
datum: till exempel "Visas: Satellitbild – Landsat 8, falska färger, kortvågig IR, tagen 4 aug.
2014 12:06 svensk tid", eller "Visas: Karta – OpenStreetMap, data från …" med datumet då kartans
OpenStreetMap-data hämtades. Du väljer i gruppen **Satellitbilder** i mission controls vänstra
kolumn, under uppspelningsknapparna: knapparna
**KARTA** och **SENASTE SATELLITBILD**, eller en bild i listan **Bild** som du sedan visar med
**VISA VALD BILD**. Senaste satellitbild är
den senaste bilden av de ikryssade bildtyperna som är tagen fram till scenariotiden (se nedan).
Valet gäller alla skärmar, och **RESET** ställer tillbaka det på senaste satellitbild. Under upptäcktssekvensen i branden
nämner raden först passagens detektioner och sedan underlaget, till exempel
"Visas: VIIRS-detektioner 5 aug. 2014 03:17 svensk tid · underlag: Satellitbild – Landsat 8, …,
tagen 4 aug. 2014 12:06 svensk tid".

**Huvudskärmen visar bara.** Alla knappar, listor och kryssrutor finns i mission control och
gäller alla skärmar: uppspelningen, **VISA ALLA**, **FLYG TILL …** och **ÖVERSIKT**,
prognoshorisonten och vilken station panelen visar, kartans lager, frågorna och **RENSA
SVARET**. Huvudskärmens listor står kvar som text, så att besökarna ser vad som visas. På
kartan kan du fortfarande zooma, dra och högerklicka. Lägg till `?controls=1` i adressen för
att få tillbaka huvudskärmens egna knappar och lagerlistor vid felsökning. Uppspelningsknapparna
där styr alla skärmar, medan lagerlistan och stationslistorna bara gäller den skärmen.

**VISA 2D / VISA 3D.** Knappen bredvid **UPPLÄSNING** i mission control byter huvudskärmen mellan
3D-globen och 2D-kartan; den heter efter den vy du byter till. Klockan, lagren och händelserna följer
med, och RESET behåller vyn. STARTA OM DEMO och BYT SCENARIO börjar i 3D. Innan någon har tryckt
på knappen stannar varje skärm där den öppnades, till exempel ett eget fönster med 2D-kartan; efter ett
val följer huvudskärmen det, också när den laddas om. Ett fönster med `?controls=1` byter inte. GOD VIEW är tom utanför området runt händelsen i 2D, så använd 3D för den.

**Kartans lager.** Rutan **Kartans lager**, överst i gruppen **Kartan** i mittkolumnen, har en
kryssruta per lager och de fyra kategorierna för GOD VIEW: **Space** (detektioner och
satelliter), **IoT** (syntetiska sensorer), **Infrastructure** (svar på fråga) och **Weather**
(vind, SMHI:s nederbördsradar och väderstationer). En kategori döljer eller visar alla sina
lager, med en banner och i GOD VIEW:s lista på huvudskärmen; dess lager står indragna under den
och går inte att ändra medan kategorin är dold. Maritime, Aviation och Emergency är gråa: de
ingår inte i demon.

**Bildtyper och baskartor.** Under Kartans lager listar mission control demons bildtyper och
baskartor med kryssrutor. Vilka typer som är mest användbara beror på händelsen och på vilka
satelliter som tog bilder.

- **Bildtyperna** styr vad **SENASTE SATELLITBILD** följer. Exempel på typer är radar, beräknat
  vatten, naturliga färger, NDWI, kortvågig IR och NDMI. Skärmarna visar den nyaste bilden
  bland de ikryssade typerna och byter automatiskt när en ny blir tagen vid scenariotiden.
  Varje rad visar hur många bilder av typen som är tagna, till exempel "radar 5 av 8 tagna".
  Listan **Bild** visar bara de ikryssade typerna. Utan ikryssad typ visas kartan.
- **Baskartorna** är offline-kartan (OSM), OpenStreetMap online (kräver internet) och
  Lantmäteriets topowebb när den är aktiverad (bara 2D). I översvämningen i Sundsvall finns
  också **Sundsvalls kommun (Kartan)**, kommunens egen karta sparad på datorn, när den är
  hämtad (avsnitt 15). Den fungerar utan internet och är vit med ortnamn utanför kommunen,
  till exempel i Timrå. Varje karta visar den första ikryssade som den har; utan ikryssad
  baskarta visar 3D-globen bara Natural Earth II.
- **SPARA PROFIL FÖR SCENARIOT**, längst ned i vänstra kolumnen, sparar kryssen, demons
  start och stopp och hastigheten (avsnitt 10) för den demo som körs. Knappen är röd så länge
  kryssen, tiderna eller hastigheten skiljer sig från profilen som demon startar med, och blir
  som vanligt igen när du har sparat. Demon startar med profilen, och **RESET** återgår till
  kryssen i den men behåller start, stopp och hastighet som de är. Ett scenario
  utan egen profil använder den äldre profilen för sin typ av händelse (skogsbrand eller
  översvämning), om en sådan sparades innan profilerna blev per scenario; texten under knappen
  säger vilken profil som gäller. Utan sparad profil gäller standardvalet: kortvågig IR i
  bränderna, radar i översvämningarna, offline-kartan och scenariots hela period. Profilerna
  sparas i `data/display-profiles.json` på utställningsdatorn och följer inte med repot. Ta
  bort filen för att gå tillbaka till standardvalet.

## 9. Mission control på en surfplatta (valfritt)

Hoppa över det här avsnittet om mission control körs på samma dator som huvudskärmen.

Ska en surfplatta styra demon över nätverket behöver backend vara nåbar från nätverket och
kräva ett lösenord, en så kallad **token**, så att ingen annan kan styra den. Välj själv en
token, till exempel en fras utan mellanslag, och starta backend i terminal 1 så här i
stället:

```bash
SCENARIO_CONTROL_TOKEN=din-token .venv/bin/python -m app.backend.server --host 0.0.0.0
```

Öppna sedan `http://<datorns-ip-adress>:8765/control.html?token=din-token` på
surfplattan. **BYT SCENARIO** och **STARTA OM DEMO** fungerar bara när demon är startad med `tools.start_demo`; med
backend startad så här svarar den att det inte går. Datorns IP-adress visas med kommandot `hostname -I`. Även huvudskärmens adress
behöver `&token=din-token` i slutet.

---

# Del 3 – Köra demon

## 10. Manuset, cirka tre minuter

Knapparna i **fetstil** finns i mission control. Hastigheten väljer du i listan **Hastighet**
under PLAY, PAUSE och RESET – 1 minut/s, 10 minuter/s, 30 minuter/s, 1 timme/s eller 3
timmar/s – och tar i bruk med **ANVÄND** till vänster om listan. Listan visar den hastighet som
gäller. Knapparna som tar ett val i bruk – **ANVÄND**, **ANVÄND TIDER** och **VISA VALD BILD** –
är röda så länge du har valt något som ännu inte gäller på skärmarna. **RESET** ändrar inte hastigheten. Spara den med **SPARA PROFIL FÖR SCENARIOT** så
startar demon med den; utan sparad hastighet startar den på 10 minuter/s.

**Demons start och stopp.** Under hastigheten anger du i **Start** och **Stopp** när demon
börjar och slutar, i svensk tid och inom scenariots data (raden under fälten visar hela
perioden). **ANVÄND TIDER** tar dem i bruk direkt: **RESET** och **PLAY** efter slutet går till
start, uppspelningen stannar vid stopp och **VISA ALLA** går till stopp. **RESET** ändrar inte
tiderna, inte heller när mission control laddas om; de gäller tills du anger nya eller demon
startas om. Spara dem med **SPARA PROFIL FÖR SCENARIOT** (avsnitt 8) så används de varje gång
demon startar: skärmarna öppnas på starttiden, och panelens diagram (regn, vattenföring och
brandens tidslinje) spänner från start till stopp. "Sedan start" i regnet räknas från demons
start.

Texten i kolumnen "Säg" är förslag. Använd dina egna ord.

| Tid | Gör | Säg |
|---|---|---|
| 0:00 | Tryck **FLYG TILL BRANDEN** i mission control. Kameran åker ut till jorden och flyger in till branden. | "Det här är skogsbranden i Västmanland sommaren 2014, återuppspelad med riktiga satellitdata." |
| 0:10 | Tryck **SPACE VIEW**, välj 1 minut/s och tryck **ANVÄND** och **PLAY**. Peka på satellitbevakningen. | "Det här är satelliterna som såg branden, Aqua, Terra och Suomi NPP, där de var den dagen. Tidslinjen visar när de passerar över branden." |
| 0:25 | Tryck **SPACE VIEW** igen. Kameran flyger tillbaka. | |
| 0:30 | Tryck **SATELLITE DETECTION**. Uppspelningen stannar, och ett kort med sex steg visas nere till höger på huvudskärmen. Steg 1, **Bild tagen**: kameran går ut så att satelliten syns, med en lila linje ner till branden. | "Här passerar Suomi NPP över branden. Det är den verkliga passagen från 2014." |
| 0:40 | Tryck **NÄSTA ▸**. Steg 2, **Anomali upptäckt ombord**, märkt SYNTETISKT. | "I framtiden kan satelliten själv se värmen och slå larm. 2014 gjordes det på marken, därför står det syntetiskt." |
| 0:50 | Tryck **NÄSTA ▸**. Steg 3, **Nedlänk till markstation**, märkt SYNTETISKT. | "Larmet skickas ner till en markstation och vidare till lägescentralen." |
| 0:55 | Tryck **NÄSTA ▸**. Steg 4, **Zoom till branden**: kameran flyger in och passagens detektioner visas. | "Det här är vad satelliten faktiskt såg. Antalet står på kortet." |
| 1:05 | Tryck **NÄSTA ▸**. Steg 5, **IoT på marken**, märkt SYNTETISKT. | "Sensorer på marken kontrollerar larmet. I demon är de simulerade." |
| 1:15 | Tryck **NÄSTA ▸**. Steg 6, **Korrelering**: kortet visar utfallet och fem regler med ✓ eller ✗. | "Reglerna jämför med kartan: brinner det i skog eller vid en industri? Det är regler som håller eller inte, ingen sannolikhet." |
| 1:30 | Tryck **NÄSTA ▸** en sista gång. Kortet försvinner. Tryck **PLAY**. Kl. 12:06 svensk tid kommer Landsat-bilden. | "Landsat 8 fotograferade branden tjugo minuter senare. Det mörka är bränd skog, det orange är brandfronten." |
| 1:45 | Välj 1 timme/s och tryck **ANVÄND**. | "Nu går tiden fortare, och branden växer." |
| 1:55 | Peka på AI ASSESSMENT på huvudskärmen. Tryck "Why do you believe there is a fire?" under **Frågor** i mission control. | "Bedömningen visar varför den tror att det brinner. Varje rad pekar på sitt objekt på kartan." |
| 2:10 | Tryck "Show infrastructure within 5 km of the incident". Klicka på "SQL som kördes" på huvudskärmen. | "Det här är en riktig fråga mot en kartdatabas. Frågan syns här." |
| 2:20 | Tryck **+60 MIN**, och tryck igen för att stänga. | "Prognosen är en enkel modell med stor osäkerhet." |
| 2:30 | Tryck **SATCOM FAILURE**. Vänta några sekunder. | "Satellitlänken bryts. Sensorerna fortsätter, och satellitdatan köas." |
| 2:45 | Tryck **SATCOM FAILURE** igen. | "Länken är tillbaka, och här är det som hände under avbrottet." |
| 2:55 | Tryck **GOD VIEW**, och prova kategorierna Space, IoT, Infrastructure och Weather i rutan **Kartans lager** om det finns tid. | "From Orbit to Decision." |
| Efteråt | Tryck **RESET**. | Inom ungefär fem sekunder är demon tillbaka i början och klar för nästa besökare. |

**Om upptäcktssekvensen.** SATELLITE DETECTION tar alltid nästa verkliga satellitpassage
efter scenarioklockan. Trycker du före kl. 11:35 svensk tid blir det Terra kl. 11:35, annars
Suomi NPP kl. 11:48. Båda fungerar, och kortet säger vilken satellit det är. Knapparna
**SATELLITE DETECTION** och **NÄSTA ▸** står överst i gruppen **Satellitbilder** i mission
control, som visar vilket steg du är på, till exempel "Steg 2/6". **NÄSTA ▸** går bara att trycka på
medan en sekvens pågår. Uppspelningen står still under hela sekvensen tills du trycker
**PLAY**.

Efter **RESET** står klockan på demons startpunkt, den 31 juli. Ladda om huvudskärmen med
adressen i avsnitt 8 för att börja kl. 11:30 den 4 augusti igen.

**Före och efter branden.** Listan **Bild** i mission control har varje bild som är tagen fram
till scenariotiden, den senaste överst, och fylls på när klockan går. Ett val i listan syns på
skärmarna först när du trycker **VISA VALD BILD**, så du kan förbereda nästa bild i lugn och ro. Längst ner står bilden
från 14 september, **jämförelse – tagen senare**, med hela det brända området ovanpå dagens
brandfront; den går alltid att välja. Välj en bild med **fukt i vegetationen (NDMI)** för att
visa hur torrt det var: brunt är torrt, blått är fuktigt. Säg att bilden efter branden är en jämförelse,
inte läget vid scenariotiden – det står också på skärmen.

**Prognospilarna.** Mitt i branden pekar två pilar. Den **streckade orange** pilen är modellens
spridningsriktning, med vind och brandväder från SMHI Sala A; den syns så snart det finns en
prognos. Den **heldragna orange** pilen är den observerade spridningen, riktningen brandfronten
har flyttat sig mellan de två senaste satellitpassagerna; den syns först när fronten har
flyttat sig mätbart. Pekar de åt samma håll stämmer modellen med vad satelliterna har sett.

Fler knappar om besökarna frågar:

- **SENSOR FAILURE**: en sensor slutar fungera och räknas inte längre.
- **IOT PÅ/AV**: stänger av alla sensorer, både de i montern och de i brandområdet. Bedömningen
  räknas då bara på satellitdata. Tryck igen för att slå på dem.
- **Placera IoT-sensor**: högerklicka på kartan på huvudskärmen och välj **Placera IoT-sensor**
  i menyn. En syntetisk sensor placeras där du klickade. Den heter Sensor P1, P2 och så vidare,
  visas i listan över syntetiska sensorer och räknas med i "IoT bekräftar" och i AI ASSESSMENT.
  Säg att sensorn är simulerad: värdena räknas ut ur brandfronten och vinden. Högst tio sensorer
  kan placeras, och **RESET** tar bort dem alla.
- **ROAD CLOSED** och **POWER FAILURE** visar bara en text, märkt syntetisk. Det finns inga
  väg- eller elnätsdata kopplade till dem.

## 11. Riktigt, beräknat och simulerat

Besökare frågar ofta vad som är på riktigt. Skärmarna märker varje del, och det är viktigt
att det du säger stämmer med märkningen.

| Kategori | Vad | Säg |
|---|---|---|
| **Riktiga data** | Meteosats brandpixlar (LSA SAF), satelliternas upptäckter av branden (NASA FIRMS), också passagen och detektionerna i upptäcktssekvensen, Landsat-bilderna (USGS), väderobservationer från SMHI, satelliternas banor (Space-Track), kartdata från OpenStreetMap (dagens läge, inte 2014) | "Riktiga data från 2014, uppspelade. Det är inte live." |
| **Beräknat** | Satelliternas positioner, brandrisken från LSA SAF (ur ERA5:s väder), vinden (ERA5-Land, en modell), brandprognosen, bedömningens poäng, reglerna i sekvensens korreleringssteg | "Beräknat ur data. Poängen är en regelbaserad poäng, inte en sannolikhet." |
| **Simulerat** | Sensorerna i montern (TEMP, WATER, AIR, NTN), sensorerna i brandområdet, satellitavbrottet, händelserna från mission control och sekvensens steg märkta SYNTETISKT: anomali ombord, nedlänk och IoT på marken | "Simulerat för demon. Det står på skärmen." |

Säg inte att något är live, att sensorerna fanns i skogen 2014 eller att poängen är en
träffsäkerhet. Nämn inte partnernamn som Dacreo eller BruhnBruhn förrän det finns ett
skriftligt godkännande.

## 12. Avsluta för dagen

Tryck Ctrl+C i terminal 1 och i terminal 2. Docker-tjänsterna kan stå kvar till nästa dag,
eller stoppas med:

```bash
docker compose stop
```

---

# Del 4 – Om något går fel

## 13. Felsökning

Hitta det du ser i vänstra kolumnen. Åtgärderna A–F står i kodblocket under tabellen.

| Det här ser du | Orsak | Gör så här |
|---|---|---|
| "This site can't be reached" eller `ERR_CONNECTION_REFUSED` | Backend är inte igång. | A, och ladda om sidorna. |
| Sensorerna visar "Ansluter …" eller "IoT unavailable" | Meddelandetjänsten är inte igång, eller backend startades med `python3` i stället för `.venv/bin/python`. | B, sedan A. |
| Sensorerna i montern visas som OFFLINE | Programmet i terminal 2 har stannat. | C. Sensorerna kommer tillbaka inom några sekunder. |
| Frågorna svarar "PostGIS svarar inte" | Databasen är inte igång. | D, sedan A. |
| Inga satelliter, eller ingen satellitbild | Steg 5.6 eller 5.7 är inte gjort. | E. Före 12:06 svensk tid den 4 augusti visas bilden från 10 juni; bilden från 4 augusti tar över när scenariot når dit. |
| Kartan runt brandområdet är tom eller ljus | Kartjänsten är inte igång. | F. |
| 3D-vyn rör sig ryckigt | För hög hastighet eller för svagt grafikkort. | Välj 1 minut/s och tryck **ANVÄND** i SPACE VIEW. Kör generalrepetitionen i avsnitt 6. |
| Mission control säger "fel eller saknad token" | Backend kräver token. | Lägg till `?token=din-token` i adressen, se avsnitt 9. |
| GOD VIEW blir tom på 2D-kartan | Känd begränsning: den sparade kartan täcker bara brandområdet. | Tryck **VISA 3D** i mission control. |
| En röd ruta på huvudskärmen: "An error occurred while rendering. Rendering has stopped." | 3D-vyn har slutat rita, oftast på grund av grafikkortet. Panelen till höger fungerar fortfarande. | Ladda om huvudskärmen med adressen i avsnitt 8. Kommer rutan igen, starta om Chrome på vanligt sätt och kör generalrepetitionen i avsnitt 6. |
| Något annat ser konstigt ut | – | Tryck **RESET**. Hjälper det inte, ladda om huvudskärmen med adressen i avsnitt 8. |

Åtgärderna körs från repots mapp:

```bash
# A – starta backend (i terminal 1)
.venv/bin/python -m app.backend.server

# B – starta meddelandetjänsten för sensorerna
docker compose up -d mosquitto

# C – starta sensorerna i montern (i terminal 2)
.venv/bin/python -m tools.mqtt_node_sim --interval 5

# D – starta databasen
docker compose up -d postgis

# E – hämta satellitbanorna och Landsat-bilden
python3 -m tools.fetch_tle_history
.venv/bin/python -m tools.fetch_landsat_scene

# F – starta kartjänsten
docker compose up -d tiles
```

Om ett kommando skriver ett felmeddelande du inte förstår, spara det, till exempel som en
skärmdump. Det gör det mycket lättare för någon annan att hjälpa till.

---

# Del 5 – Översvämningsdemon i Sundsvall

## 14. Vad översvämningsdemon är

Demon visar Sundsvall den 14–22 augusti 2026. Regnet är verkligt: det kommer från kommunens
egna regnmätare och SMHI:s station Brämön A. Den 16 augusti föll som mest 10,6 mm på en timme
(Fillan) och 29 mm på ett dygn, och den 19 augusti kom ett andra regn.

Det är ett **scenario**, inte en återgiven händelse. Att Sundsvall översvämmades de dagarna är
inte bekräftat i öppna källor. Det står överst på huvudskärmen: "Scenario byggt på verkligt
regn augusti 2026 – inte en återgiven händelse". Säg det också till besökarna.

Demon använder samma skärmar och knappar som branddemon. I stället för brandens delar visar den:

- **Regn (SMHI)** i panelen under Uppspelning: timmar och dygn vid den mätare du väljer,
  och ett stapeldiagram med en röd linje för scenarioklockan. Klasserna står i panelen under **Regn
  på kartan (SMHI)**. Varje mätare på kartan visar regnet den senaste timmen, och
  markeringens storlek och färg följer SMHI:s klasser för regn: lätt (högst 0,5 mm på en timme),
  måttligt (0,5–4 mm), kraftigt (mer än 4 mm) och skyfall (minst 50 mm). En timsumma skiljer inte
  skurar från ihållande regn, så klasserna för regn används.
- **Vind (ERA5-Land, modell)**: vindpilar över kartan, som i branddemon, timme för timme. Över
  havet, där ERA5-Land saknar värden, kommer pilarna från ERA5 (0,25°, interpolerad); det står
  när man håller musen över en pil.
- **Nederbörd (SMHI radar)**: SMHI:s väderradar var 10:e minut, även över havet, omräknad till
  regn (Z = 200·R^1,6) och färgad i samma klasser som mätarna. Det är en uppskattning från radarn,
  inte en mätning på marken. Slå av och på lagret i kartans lagerlista.
- **Översvämningskartor (modell)**: kommunens skyfallsmodeller för 30-, 100- och 500-årsregn,
  Selångersåns 100-årsflöde och MCF:s (tidigare MSB:s) karteringar av Ljungan och Indalsälven.
  Välj dem i kartans lagerlista. Största vattendjup vid 100-årsregn är påslaget från början.
  När ett lager med största vattendjup är påslaget visar panelen kommunens färger: grönt
  0,1–0,2 m, ljusgrönt 0,2–0,3 m, gult 0,3–0,4 m, ljusorange 0,4–0,5 m, orange 0,5–1 m, rött
  1–2 m och mörkrött mer än 2 m. Det är modellens största djup vid ett sådant regn, inte vad som
  hände i augusti 2026.
- **Syntetiska bräddgivare DV1–DV8** vid kommunens kritiska dagvattenpunkter. Röd betyder att
  den bräddar. Deras värden räknas ut ur det verkliga regnet och kommunens modell.
- **Satellitbilder**: Sentinel-1:s radarbilder, som ser genom moln, och Landsat 8 och
  Sentinel-2, vars augustibilder är molniga. Från början visas den senaste radarbilden fram
  till scenariotiden. Välj karta eller en annan bild i gruppen **Satellitbilder** i mission
  control; raden överst på huvudskärmen säger vad som visas och när bilden togs. En radarbild
  kan också visas som **vatten i radarbilden utanför sjöar och hav**, en beräknad mask i rött;
  panelen förklarar då färgen under **Satellitbild**.

Kommunens och MCF:s kartor hämtas från deras karttjänster medan demon körs. Datorn behöver
därför internet för dem. Allt annat fungerar utan.

## 15. Förbered översvämningsdemon

Gör Del 1 först. Hämta sedan Sundsvalls data, en gång per dator. Alla kommandon körs från
repots mapp och skriver till `data/sundsvall2026/`.

```bash
# 15.1 Välj scenariot för kommandona i den här terminalen
export TECHSEED_SCENARIO=sundsvall2026

# 15.2 Höjddata och 3D-terräng, offline-kartan (använder Sverigeutdraget från 5.3) och satellitbanorna 2026
.venv/bin/python -m tools.fetch_copernicus_dem && .venv/bin/python -m tools.build_terrain
.venv/bin/python -m tools.build_offline_tiles
.venv/bin/python -m tools.fetch_tle_history

# 15.3 Regnet från kommunens mätare och Brämön A
.venv/bin/python -m tools.fetch_smhi_weather 2222813 2222814 2222818 2222811 2222812 2222819 127130 \
  --period latest-months --parameters 7 --start 2026-08-14 --end 2026-08-22 --out data/sundsvall2026/smhi

# 15.3b Vinden för pilarna (ERA5-Land; behöver ett konto hos Copernicus CDS med nyckeln i ~/.cdsapirc)
.venv/bin/python tools/fetch_era5_land.py --area 62.6,16.9,62.2,17.8 --start 2026-08-14 --end 2026-08-22 \
  --raw-dir /tmp/era5-land-sundsvall --out data/sundsvall2026/era5-land/era5-land-sundsvall-2026.csv
# och vinden över havet, där ERA5-Land saknar värden (ERA5, samma CDS-konto)
.venv/bin/python -m tools.fetch_era5_sea --area 62.6,16.9,62.2,17.8 --start 2026-08-14 --end 2026-08-22 \
  --land data/sundsvall2026/era5-land/era5-land-sundsvall-2026.csv --raw-dir /tmp/era5-sea \
  --out data/sundsvall2026/era5-land/era5-sea-sundsvall-2026.csv

# 15.3c SMHI:s väderradar som regnbilder, var 10:e minut (cirka 1 300 små bilder)
.venv/bin/python -m tools.fetch_smhi_radar --start 2026-08-14 --end 2026-08-22 --out data/sundsvall2026/radar

# 15.4 Kartdata från OpenStreetMap
.venv/bin/python -m tools.fetch_osm_terrain --bbox 62.15,16.9,62.62,17.8 --out data/sundsvall2026/osm/terrain-sundsvall.geojson
.venv/bin/python -m tools.fetch_osm_targets --bbox 62.15,16.9,62.62,17.8 --out data/sundsvall2026/osm/targets-sundsvall.geojson

# 15.5 Satellitbilderna, kommunens dagvattenpunkter och flödesytor, och MCF:s flödesytor
.venv/bin/python -m tools.fetch_landsat_scene
.venv/bin/python -m tools.fetch_sentinel2_scene
.venv/bin/python -m tools.fetch_municipal_features
.venv/bin/python -m tools.fetch_mcf_flood_maps
.venv/bin/python -m tools.fetch_sentinel1_scene

# 15.5a Kommunens karta (Kartan) som baskarta, sparad på datorn: cirka 41 000 kartbitar,
# 1,1 GB och två till tre timmar; avbryts den, kör samma kommando igen
.venv/bin/python -m tools.fetch_municipal_basemap

# 15.5b MET Norways väderprognoser som de utfärdades, och SMHI:s observerade blixtar
.venv/bin/python -m tools.fetch_met_forecasts
.venv/bin/python -m tools.fetch_smhi_lightning

# 15.6 Databasen sundsvall2026 (skapas bredvid branddemons databas, som inte påverkas)
.venv/bin/python -m tools.load_postgis
```

**Generalrepetition.** Kontrollen fungerar som i avsnitt 6. Byt först till Sundsvalls karta,
se avsnitt 16, och kör sedan:

```bash
TECHSEED_SCENARIO=sundsvall2026 .venv/bin/python -m tools.check_demo --headed --out ~/demo-check-sundsvall-$(hostname)
```

Den kör översvämningens nio steg och ska sluta med `RESULTAT: GODKÄND`.

## 16. Byta mellan demona

**Enklast:** tryck **BYT SCENARIO** längst ned i mission controls vänstra kolumn och bekräfta. Demon avslutas,
satellitmonitorn och huvudskärmen stängs, och menyn visas i mission control. Klicka på **Översvämning i Sundsvall 2026 – scenario**, eller
på branden för att byta tillbaka. Är demon startad med ett namn går det likadant; utan
`tools.start_demo` stoppar du med Ctrl+C och kör `.venv/bin/python -m tools.start_demo`.

Valet byter karta i kartjänsten, startar backend och sensorerna och återställer scenariot till
dess start den 14 augusti kl. 02:00 svensk tid. Spela upp scenariot för att komma fram till
radarbilden den 16 augusti och regnets topp.

**Steg för steg:** det finns en kartjänst, och den visar en demos karta i taget. Byt så här.

**Till översvämningen:**

1. Tryck Ctrl+C i terminal 1 så att branddemons backend stannar.
2. Kör, i terminal 1:

```bash
TILES_FILE=sundsvall.mbtiles docker compose up -d tiles
.venv/bin/python -m app.backend.server --scenario sundsvall2026
```

3. Öppna skärmarna på nytt, i terminal 2 eller en ny terminal:

```bash
.venv/bin/python -m tools.open_screens
```

   När Mission Control har laddat är klockan 14 augusti kl. 02:00 svensk tid. Öppnar du
   fönstren själv är adresserna desamma som i avsnitt 8, med <http://127.0.0.1:8765/3d.html>
   för huvudskärmen.

Huvudskärmen ska ha rubriken "Översvämning i Sundsvall 2026 – scenario", och mission control
"Scenario: FLOOD – Sundsvall 2026".

**Tillbaka till branden:** stoppa backend med Ctrl+C och kör:

```bash
docker compose up -d tiles
.venv/bin/python -m app.backend.server
```

Sensorerna i montern, terminal 2, behöver inte startas om. De visas i båda demona.

## 17. Manuset, cirka tre minuter

Börja med huvudskärmen på adressen i avsnitt 16 och hastigheten 10 minuter/s. Gå lugnt fram,
så att besökarna hinner se vad som händer.

| Tid | Gör | Säg |
|---|---|---|
| 0:00 | Tryck **FLYG TILL SUNDSVALL** i mission control. | "Det här är Sundsvall i augusti 2026. Det är ett scenario byggt på det verkliga regnet, inte en återgiven händelse." |
| 0:15 | Peka på "Regn (SMHI)" i panelen och på mätarna på kartan. | "Kommunen har egna regnmätare. Staplarna visar regnet timme för timme, och den röda linjen är tiden i scenariot." |
| 0:30 | Peka på de färgade fälten på kartan. | "Det här är kommunens skyfallsmodell: hur djupt vattnet kan bli vid ett 100-årsregn. Det är en modell, inte en observation." |
| 0:45 | Tryck **SPACE VIEW**, välj 1 minut/s och tryck **ANVÄND** och **PLAY**. Peka på satellitbevakningen. Tryck **SPACE VIEW** igen efter en stund. | "Sentinel-1 har radar som ser genom moln. Sentinel-2 och Landsat ser som en kamera, och de bilderna var molniga." |
| 1:00 | Tryck **SATELLITE DETECTION**. Steg 1, **Bild tagen**: Sentinel-1C kl. 07:21 svensk tid. | "Det här är en verklig radarbild från Sentinel-1, tagen över Sundsvall den morgonen." |
| 1:10 | Tryck **NÄSTA ▸** två gånger: **Anomali upptäckt ombord** och **Nedlänk**, båda SYNTETISKT. | "I framtiden kan satelliten själv hitta vatten i bilden och slå larm. Här är det illustrerat." |
| 1:25 | Tryck **NÄSTA ▸**. Steg 4, **Zoom till Sundsvall**: kartan visar radarbilden i grått. | "Radarn ser genom molnen. Släta vattenytor är mörka, och stan är ljus." |
| 1:35 | Tryck **NÄSTA ▸**. Steg 5, **IoT på marken**, SYNTETISKT. Rött på kartan är vatten i radarbilden utanför sjöar och hav. | "Det röda är en enkel beräkning, inte en kartlagd översvämning. Bräddgivarna i dagvattnet är simulerade, men har samma format som kommunens sensorplattform." |
| 1:45 | Tryck **NÄSTA ▸**. Steg 6, **Korrelering**: fyra regler med ✓ eller ✗. | "Reglerna väger regn, bräddning, modellen och radarbilden. Just den här morgonen skiljer radarn dåligt mellan vatten och land, och det säger regeln." |
| 2:00 | Tryck **NÄSTA ▸**, välj 10 minuter/s och tryck **ANVÄND** och **PLAY**. Runt kl. 10 svensk tid kommer regnets topp, och bräddgivarna blir röda. | "Nu kommer det kraftigaste regnet. Fyra av åtta bräddgivare bräddar." |
| 2:15 | Tryck **PAUSE**. Peka på AI ASSESSMENT och tryck "Why do you believe there is a flood?" under **Frågor** i mission control. | "Bedömningen visar varför: regnet och bräddningen. Varje rad pekar på sitt ställe på kartan." |
| 2:30 | Tryck "Vilka byggnader ligger inom 100-årsflödet?" och klicka sedan på "SQL som kördes" på huvudskärmen. | "Det här är en riktig fråga mot en kartdatabas, med kommunens och MCF:s flödeskartor." |
| 2:45 | Tryck "Vad finns inom 200 m från de bräddande punkterna?". | "Här är det som ligger nära de bräddande punkterna. Underlaget är syntetiskt." |
| 2:55 | Tryck **GOD VIEW**. | "From Orbit to Decision." |
| Efteråt | Tryck **RESET** och ladda om huvudskärmen med adressen i avsnitt 16. | Demon är klar för nästa besökare. |

**Om upptäcktssekvensen.** SATELLITE DETECTION tar alltid nästa verkliga Sentinel-1-bild över
stan efter scenarioklockan. Det finns fem i perioden: den 16 augusti kl. 07:21, den 17 augusti
kl. 07:13 och 18:29, den 18 augusti kl. 18:21 och den 22 augusti kl. 07:21, svensk tid. Trycker
du efter kl. 07:21 den 16 augusti blir det bilden nästa morgon. Varje radarbild visas på
kartan under sekvensen. Bilden den 16 augusti är tagen mitt i regnet och vinden, och där
skiljer radarn dåligt mellan vatten och land; bilderna efter den är tydligare.

**SATCOM FAILURE** fungerar som i branddemon, men det som köas är satellitbilder. Med
1 timme/s kommer nästa radarbild inom ungefär en halv minut, och efter **SATCOM FAILURE**
igen listar SYNC den.

**SENSOR FAILURE** slår ut bräddgivaren DV1. **Placera IoT-sensor** med högerklick fungerar
också. En placerad sensor räknas ut ur regnet vid närmaste mätare, men har inget modelldjup.

## 18. Riktigt, beräknat, modell och syntetiskt i översvämningen

| Kategori | Vad | Säg |
|---|---|---|
| **Riktiga data** | Regnet från kommunens mätare och SMHI:s Brämön A, Sentinel-1:s radarbilder (inte terrängkorrigerade), Landsat 8- och Sentinel-2-bilderna, satelliternas banor (Space-Track), kommunens kritiska dagvattenpunkter, kartdata från OpenStreetMap (dagens läge) | "Riktiga data från augusti 2026, uppspelade. Det är inte live." |
| **Modell** | Vinden (ERA5-Land, en väderanalys från Copernicus, inte SMHI:s mätningar), kommunens skyfallsmodeller, vattendjup och strömhastighet, Selångersåns 100-årsflöde, MCF:s karteringar av Ljungan och Indalsälven | "Modeller av vad som kan översvämmas. De visar inte vad som hände." |
| **Beräknat** | Satelliternas positioner och passager, vattenmasken i Sentinel-2-bilden, vattnet i radarbilden utanför sjöar och hav (en enkel tröskel), bedömningens poäng och reglerna | "Beräknat ur data. Poängen är en regelbaserad poäng, inte en sannolikhet." |
| **Syntetiskt och simulerat** | Bräddgivarna DV1–DV8 och placerade sensorer, sensorerna i montern, händelserna från mission control och sekvensens steg märkta SYNTETISKT | "Simulerat för demon. Det står på skärmen." |

Säg inte att Sundsvall översvämmades den 16 augusti, att det röda i radarbilden är en kartlagd
översvämning eller att bräddgivarna är MSVA:s eller kommunens mätningar. Regnet från kommunens mätare är de senaste
månaderna inte alltid kvalitetsgranskat, och en timme utan värde räknas som torr.

## 19. Felsökning för översvämningen

| Det här ser du | Orsak | Gör så här |
|---|---|---|
| Kartan runt Sundsvall är tom, eller visar Västmanland | Kartjänsten visar brandens karta. | Kör `TILES_FILE=sundsvall.mbtiles docker compose up -d tiles` och ladda om. |
| Rubriken säger "Skogsbranden i Västmanland 2014" | Backend kör branddemon. | Starta om backend med `--scenario sundsvall2026`, se avsnitt 16. |
| Frågorna svarar "PostGIS svarar inte" eller att en tabell saknas | Databasen är inte igång eller inte fylld. | D i avsnitt 13, sedan `TECHSEED_SCENARIO=sundsvall2026 .venv/bin/python -m tools.load_postgis`. |
| Översvämningskartorna syns inte, eller panelen säger att en karttjänst inte svarar | Datorn saknar internet, eller kommunens eller MCF:s karttjänst svarar inte. Backend frågar tjänsterna var 30:e sekund och lämnar en tyst tjänst utanför, så resten av demon fungerar ändå. | Kontrollera nätverket. Ladda om huvudskärmen när tjänsten svarar igen. |
| Fönstren hamnar fel på skärmarna | Chrome öppnar nya fönster där det vill. | Öppna skärmarna med `tools.open_screens`, se avsnitt 8 och 16. |
| Inga bräddgivare | Kommunens dagvattenpunkter är inte hämtade. | Kör 15.5 och starta om backend. |

---

# Del 6 – Översvämningarna i Skåne 2024

## 20. Vad demon visar

Vintern 2024 svämmade Ringsjöarna, Hörbyån, Kävlingeån och Vombsjön över. Det här är en
**återgiven händelse med verkliga data**, inte ett scenario som i Sundsvall. Enligt SMHI:s
mätningar satte vattenföringen nya rekord 24–27 januari, till exempel 30,3 m³/s vid Heåkra i
Hörbyån mot tidigare högsta 25,8 m³/s (2005), och Ringsjöarna nådde 54,94 m den 10 februari,
det högsta sedan mätningarna började 1974.

Välj **Översvämningarna i Skåne 2024** i menyn (avsnitt 7). Demon visar:

- **Vattenföring och vattenstånd (SMHI)** i panelen under regnet: vattenföringen vid Heåkra, Ellinge,
  Högsmölla och Eggelstad och vattenståndet i Ringsjöarna och Vombsjön, med ett diagram över
  perioden, en streckad linje för det tidigare högsta värdet och "rekord" vid stationen på
  kartan när värdet är högre än allt som mätts där tidigare. Ett par stationer är ännu inte
  kvalitetsgranskade av SMHI; det står i panelen.
- **Regn (SMHI)** vid Hörby A och VA-huvudmännens mätare, **SMHI:s väderradar**, **vind
  (ERA5-Land)** och **MCF:s översvämningskartering** av Kävlingeån.
- **Satellitbilder**: åtta Sentinel-1-radarbilder som täcker Ringsjöarna, från 20 januari till
  22 februari, och Sentinel-2 före (16 januari), under (3 februari) och efter (4 mars, en
  jämförelse). Landsat har ingen användbar bild under perioden. Radarbilden kan visas som
  beräknat vatten utanför sjöar och hav; det är störst 27 januari och 3 februari, med 2–3 % av
  marken runt Ringsjöarna. Det är en enkel beräknad mask, inte en kartlagd översvämning.
- **SATELLITE DETECTION** tar nästa Sentinel-1-bild efter klockan. Kontrollen och skärmarna
  börjar 27 januari kl. 17:30 svensk tid, strax före passagen 17:45 när flödena satte rekord.
  Korreleringen har fyra regler: regn minst 30 mm de fem dygnen före bilden, vattenföring
  över tidigare högsta vid någon station, vattenstånd över tidigare högsta och radarbildens
  vatten. Vid passagen 27 januari håller alla fyra: "Översvämning trolig".
- **Bedömningen** väger samma regn, flöden och nivåer och de syntetiska nivågivarna. En
  översvämning från vattendrag och sjöar stiger under dagar, så timregnet räknas inte här.
  Gränsen 30 mm är en demoregel, inte SMHI:s varningsklasser.
- **Syntetiska nivågivare (NG1–NG8)** där större vägar korsar MCF:s 100-årsyta vid Kävlingeån
  och Rönne å, som avvattnar Ringsjöarna. Det fanns inga sensorer där 2024. Varje givare
  följer en SMHI-station (Ellinge, Högsmölla eller Ringsjödammen övre) och **larmar** när den
  stationen ligger över sitt tidigare högsta. Den visar stationens flöde i procent av rekordet
  eller nivån i centimeter från det. Flera givare följer samma station, så samma mätning kan
  räknas mer än en gång i bedömningen. Allt märks syntetiskt. Hörbyån och själva Ringsjöarna
  har ingen MCF-kartering och därför inga givare.
- **Frågorna** gäller **MCF:s klimatanpassade 100-årsflöde för slutet av seklet**: MCF har
  karterat Kävlingeån (2020) och Höje å (2025) bara med klimatanpassade flöden, så det
  vanliga 100-årsflödet finns inte här. Kartlagret visar samma yta; beräknat högsta flöde kan
  väljas till. Svaren är modellens, inte observationer.

I generalrepetitionen (`check_demo`) bekräftar 5 av 8 givare kl. 17:50 svensk tid 27 januari
och bedömningen blir "Flood probable".

## 21. Förbered demon

Gör Del 1 först. Kommandona körs från repots mapp och skriver till `data/skane2024/`.

```bash
export TECHSEED_SCENARIO=skane2024
.venv/bin/python -m tools.fetch_copernicus_dem && .venv/bin/python -m tools.build_terrain
.venv/bin/python -m tools.build_offline_tiles
.venv/bin/python -m tools.fetch_tle_history
.venv/bin/python -m tools.fetch_smhi_hydro
.venv/bin/python -m tools.fetch_smhi_weather 53530 22128523 22128522 22128520 22128524 22128144 \
  --parameters 7 --start 2024-01-20 --end 2024-02-25 --out data/skane2024/smhi
.venv/bin/python tools/fetch_era5_land.py --area 56.0,13.0,55.6,13.9 --start 2024-01-20 --end 2024-02-25 \
  --raw-dir /tmp/era5-skane --out data/skane2024/era5-land/era5-land-skane-2024.csv
.venv/bin/python -m tools.fetch_smhi_radar --start 2024-01-20 --end 2024-02-25 --step 30 --out data/skane2024/radar
.venv/bin/python -m tools.fetch_osm_terrain --bbox 55.6,13.0,55.98,13.9 --out data/skane2024/osm/terrain-skane.geojson
.venv/bin/python -m tools.fetch_osm_targets --bbox 55.6,13.0,55.98,13.9 --out data/skane2024/osm/targets-skane.geojson
.venv/bin/python -m tools.fetch_met_forecasts   # MET Norways väderprognoser som de utfärdades
.venv/bin/python -m tools.fetch_smhi_lightning  # SMHI:s observerade blixtar
```

Radarbilderna tas var 30:e minut, eftersom perioden är fem veckor lång. Satellitbilderna:

```bash
.venv/bin/python -m tools.fetch_sentinel1_scene
.venv/bin/python -m tools.fetch_sentinel2_scene
```

MCF:s kartor, databasen för frågorna och nivågivarnas punkter (som väljs ur databasen, så i
den ordningen):

```bash
.venv/bin/python -m tools.fetch_mcf_flood_maps
.venv/bin/python -m tools.load_postgis
.venv/bin/python -m tools.derive_level_sensor_points
```

Generalrepetitionen, med kartjänsten på Skånes karta:

```bash
TILES_FILE=skane.mbtiles docker compose up -d tiles
.venv/bin/python -m tools.check_demo --headed --out ~/demo-check-skane
```

---

# Del 7 – Skogsbranden vid Kårböle 2018 (under uppbyggnad)

## 22. Vad demon visar

Blixten tände skogen nära Kårböle i Ljusdals kommun den 14 juli 2018. Branden växte snabbt
kring 17–18 juli; räddningstjänsten bedömde den till omkring 8 500 hektar, 70–90 personer i
Kårböle evakuerades och 7–8 byggnader brann. Det är en **återgiven händelse med verkliga
data**, som Västmanland 2014, och demon fungerar på samma sätt: FIRMS-detektioner,
upptäcktssekvensen, prognosen, vinden och de syntetiska sensorerna.

Välj **Skogsbranden vid Kårböle 2018** i menyn (avsnitt 7). Skillnader mot Västmanland:

- FIRMS-detektionerna kommer från **fyra satelliter**: Terra och Aqua (MODIS) och Suomi NPP och
  **NOAA-20** (VIIRS), 2 540 detektioner 14–28 juli.
- Prognosens brandväder kommer från **SMHI Hamra A**, 39 km från branden; i juli 2018 var
  brandfaran extrem (FWI över 40 den 17 juli).
- Skärmarna börjar 17 juli kl. 11:15 svensk tid, strax före NOAA-20 kl. 11:34; **SATELLITE
  DETECTION** tar nästa verkliga passage efter klockan.
- **Satellitbilder från Sentinel-2**: före (4 juli), under (27 juli) och efter (2 september, en
  jämförelse), med falska färger i kortvågig IR där bränd skog är rödbrun och aktiv brand orange,
  och med **fukt i vegetationen (NDMI)** ur Sentinel-2:s band B8A och B11, i samma färger som
  Västmanlands Landsat-bilder: brunt är torrt, blått är fuktigt. Moln, molnskuggor och vatten är
  genomskinliga. NDMI visar fukten i växterna, inte i marken. Landsat är för molnig över branden
  de veckorna och är inte med.
- **Brandområdet enligt Copernicus EMS** (aktivering EMSR298, området Enskogen) som en lila
  streckad linje, kartlagt ur SPOT-6/7- och Sentinel-2-bilder: från 2 125 hektar på bilden 17
  juli till 17 936 hektar 7 augusti. Varje karta visas från slutet av bildens dag, eftersom
  bilderna saknar klockslag. Förklaringen under "Prognos (modell)" säger vilken bild och yta som
  visas. Jämför med brandfronten ur FIRMS, som är skalet runt alla detektioner och därför större.
- **Väderprognos (MET Norway)** i panelen under detektionsdiagrammet: den prognos från MET
  Norways nordiska modell MEPS (samma samarbete som SMHI är med i) som hade utfärdats och
  publicerats vid scenariotiden, alltså så som räddningstjänsten kunde ha sett den, inte facit.
  Diagrammet visar vind, byvind och regn vid branden 0–66 timmar framåt med en röd linje för
  klockan; raderna under sammanfattar 6, 12 och 24 timmar. Korta punkter säger vad som spelar
  roll för insatsen: vindvridning, byvind på minst 10 m/s, regn eller inget regn, luftfuktighet
  ned mot 30 % och risk för åska (nya bränder kan tändas). Brandrisken (FWI) de närmaste dygnen
  är **beräknad** av demon ur SMHI:s observationer fram till prognosen och prognosen därefter, inte
  MET Norways. En ny prognos kommer var sjätte timme (cirka tre timmar efter körningen); har den
  något nytt står det i satellitbevakningens logg och läses upp, till exempel "Ny väderprognos:
  Vind från sydost, 3 meter per sekund. Byvind upp till 12 meter per sekund från sydost om 8 timmar".
  Raden börjar alltid med medelvinden de närmaste sex timmarna, eller "Nästan vindstilla" under
  1 meter per sekund. Kryssa **Prognosvind (MET Norway)** i
  mission controls lagerlista för orange vindpilar sex timmar framåt; de blå pilarna är vinden
  just nu (ERA5-Land).
- **Blixtar (SMHI, observerade):** blixtsymboler för nedslagen den senaste timmen före scenarioklockan,
  ur SMHI:s öppna blixtarkiv, gula när de är nya och orange när de är äldre. Nedslag inom 30 km från
  händelsen ligger kvar som **röda blixtar** hela scenariot, med datum och klockslag när du håller
  musen över dem (i 3D: klicka). Lagret är påslaget från början i alla scenarier. Överst på kartan står hur många det var och hur många inom 30 km, och i
  satellitbevakningens logg och uppläsning sägs varje timme med nedslag nära händelsen, till exempel
  "29 blixtnedslag inom 30 kilometer från branden den senaste timmen". Det är observationer, inte
  prognoser. I Kårböle syns blixtarna som tände branden den 14 juli. MEPS blixtindex från 2024–2026
  används inte i Skåne och Sundsvall, eftersom dess skala inte är känd.
- **Väderkarta:** kryssa **Väderkarta (MET Norway)** i mission controls lagerlista (kolumnen
  Kartan, under Väder). Kartan blir platt och visar Skandinavien med lufttrycket som isobarer var
  hPa (var fjärde kraftigare och med sitt värde) med H och L, regnet de tre timmarna fram till kartans tid (blått till lila: från 0,3, 1, 3
  och 10 mm) och ⚡ där MEPS åskindex är högt. Kartan gäller **nästa** av 00Z, 03Z, 06Z … efter
  scenarioklockan, ur den senast publicerade prognosen: klockan 01 svensk tid (23Z i juli) visas
  prognosen för 00Z. Överst på kartan står vilken tid som visas och när prognosen utfärdades, till
  exempel "Väderkarta 15 juli 00Z"; för **Prognosvind** står dess tid på samma sätt. Kryssa ur
  lagret för att komma tillbaka till exakt den vy du hade. I 2D finns offlinekartan bara kring
  branden; välj baskartan OpenStreetMap online för kustlinjerna.

Generalrepetition:

```bash
TECHSEED_SCENARIO=ljusdal2018 .venv/bin/python -m tools.check_demo --headed --out ~/demo-check-ljusdal-$(hostname)
```

Bedömningen kl. 14:00 den 17 juli är "Possible fire": ingen av de syntetiska sensorerna
bekräftar branden då, och kontrollen väntar sig det.

## 23. Förbered demon

FIRMS-uttagen för 2018 finns i repot under `satellite_data/firms/`. Övriga data hämtas till
`data/ljusdal2018/`:

```bash
export TECHSEED_SCENARIO=ljusdal2018
.venv/bin/python -m tools.fetch_copernicus_dem && .venv/bin/python -m tools.build_terrain
.venv/bin/python -m tools.build_offline_tiles
.venv/bin/python -m tools.fetch_tle_history
.venv/bin/python -m tools.fetch_smhi_weather 114410 124030 --start 2018-07-12 --end 2018-08-08 --out data/ljusdal2018/smhi
.venv/bin/python -m tools.fetch_smhi_weather 114410 --start 2018-05-01 --end 2018-07-11 --out data/ljusdal2018/smhi/spinup
.venv/bin/python tools/fetch_era5_land.py --area 62.2,14.9,61.75,15.8 --start 2018-07-12 --end 2018-08-08 \
  --raw-dir /tmp/era5-ljusdal --out data/ljusdal2018/era5-land/era5-land-ljusdal-2018.csv
.venv/bin/python -m tools.fetch_osm_terrain --bbox 61.75,14.9,62.2,15.8 --out data/ljusdal2018/osm/terrain-ljusdal.geojson
.venv/bin/python -m tools.fetch_osm_targets --bbox 61.75,14.9,62.2,15.8 --out data/ljusdal2018/osm/targets-ljusdal.geojson
.venv/bin/python -m tools.fetch_sentinel2_scene
.venv/bin/python -m tools.fetch_ems_perimeters
.venv/bin/python -m tools.fetch_met_forecasts   # MET Norways väderprognoser som de utfärdades, ca 20 min
.venv/bin/python -m tools.fetch_smhi_lightning  # SMHI:s observerade blixtar
.venv/bin/python -m tools.fetch_meteosat_frm    # brandrisken från LSA SAF (avsnitt 5, steg 5.10)
.venv/bin/python -m tools.fetch_meteosat_frp    # Meteosats brandpixlar, också vid Strandåsmyrvallen
.venv/bin/python -m tools.load_postgis    # databasen ljusdal2018, för frågorna
```

---

# Del 8 – Regnet i Västernorrland 2025

## 24. Vad demon visar

Demon återger det kraftiga regnet i Västernorrland 6–7 september 2025 med verkliga data, inte i
realtid. Ett regnband drog in strax söder om Härnösand på lördagskvällen och flyttade sig norrut
under natten. Kramfors fick 123,5 mm och Myckelgensjö 140 mm på ett dygn. Vägar spolades bort,
en person omkom när väg 738 vid Judeby spolats bort, och två tåg spårade ur på söndagsmorgonen:
ett godståg på Stambanan vid Stugusjön väster om Skorped och ett timmertåg på Ådalsbanan norr om
Prästmon. Uppspelningen går från 6 september kl. 14 till 8 september kl. 14 svensk tid.

Källan för skadorna är Länsstyrelsen Västernorrlands utredning *Utredning av konsekvenser av
kraftig nederbörd 6–7 september 2025* (2026:12). Statens haverikommissions utredning av
urspårningarna är inte klar. Säg därför inget om orsakerna.

Utöver flodens delar (avsnitt 14 och 20) visar demon:

- **Skadade vägar och järnvägar (Länsstyrelsen)**: när scenarioklockan når en händelse ur
  utredningen visas en röd rund markering (väg) eller en svart fyrkantig (järnväg) på kartan.
  Händelsen blir också en rad i satellitmonitorns logg som läses upp. Platserna är ungefärliga,
  eftersom utredningen beskriver dem i text. Tider som utredningen bara anger som "strax innan
  8-tiden" eller "förmiddagen" är märkta "tid ungefärlig".
- **Vägar och järnvägar i kraftigt regn (beräknat ur radar)**: OSM:s större vägar och
  järnvägarna i bitar om cirka 1 km. En bit blir gul när radarns regn sedan uppspelningens start
  passerar 50 mm, och röd över 80 mm. Det är beräknat regn, inte observerade skador. De röda
  sträckorna sammanfaller ändå med flera av de dokumenterade skadorna.
- **Dygnsregn (SMHI)**: SMHI mäter regnets kärna bara per dygn, kl. 06–06 UTC. Varje station
  visar sitt senaste avslutade dygn, till exempel "Kramfors: 123,5 mm" från kl. 08 svensk tid den
  7 september. Klicka för dygnets tider.
- **Nivågivarna NG1–NG6** står vid de dokumenterade skadorna och är syntetiska. Varje givare följer
  närmaste SMHI-station för vattenföring: Risnäs för Judeby, Stugusjön för de övriga. Ingen
  station gick över sitt tidigare högsta flöde. Givarna larmar i stället när flödet har
  femdubblats sedan uppspelningens start, vid Stugusjön kl. 07 och vid Risnäs kl. 10 svensk tid.

| Del | Riktigt, beräknat eller syntetiskt |
|---|---|
| Regn per timme och dygn, väderradar, vattenföring, blixtar (SMHI) | Riktigt, observerat |
| Sentinel-1 (2, 7 och 8 september), Sentinel-2 och Landsat 8 | Riktigt. Vattnet i radarbilden är beräknat. |
| Skador på vägar och järnvägar, tider och VMA | Ur Länsstyrelsens utredning, platser ungefärliga |
| Regn längs vägar och järnvägar | Beräknat ur radarn |
| MET Norways prognoser, ERA5-vind | Modell |
| MCF:s karteringar (Ångermanälven, Indalsälven, Moälven, Nätraån) | Modell. De små vattendrag som gjorde skadorna är inte karterade. |
| Nivågivarna NG1–NG6 | Syntetiska |

Ha **Terräng (OSM)** avslaget i 3D. Ytorna draperade på terrängen gav cirka 13 bilder per sekund
i stället för drygt 70. Scenariots sparade profil har lagret avslaget. Spara om profilen i mission
control om du ändrar något.

## 25. Förbered demon

Gör Del 1 först. Kommandona körs från repots mapp och skriver till `data/vasternorrland2025/`.

```bash
export TECHSEED_SCENARIO=vasternorrland2025
.venv/bin/python -m tools.fetch_copernicus_dem && .venv/bin/python -m tools.build_terrain
.venv/bin/python -m tools.build_offline_tiles
.venv/bin/python -m tools.fetch_tle_history
.venv/bin/python -m tools.fetch_smhi_weather 128390 138070 138390 --period corrected-archive \
  --parameters 7 --start 2025-09-04 --end 2025-09-10 --out data/vasternorrland2025/smhi
.venv/bin/python -m tools.fetch_smhi_daily       # dygnsregnet i kärnan
.venv/bin/python -m tools.fetch_smhi_hydro --start 2025-09-04 --end 2025-09-10
.venv/bin/python -m tools.fetch_smhi_radar --start 2025-09-04 --end 2025-09-10 --out data/vasternorrland2025/radar
.venv/bin/python -m tools.fetch_smhi_lightning
.venv/bin/python tools/fetch_era5_land.py --area 63.7,17.2,62.5,18.9 --start 2025-09-04 --end 2025-09-10 \
  --raw-dir /tmp/era5-land-vn --out data/vasternorrland2025/era5-land/era5-land-vasternorrland-2025.csv
.venv/bin/python -m tools.fetch_era5_sea --area 63.7,17.2,62.5,18.9 --start 2025-09-04 --end 2025-09-10 \
  --land data/vasternorrland2025/era5-land/era5-land-vasternorrland-2025.csv --raw-dir /tmp/era5-sea-vn \
  --out data/vasternorrland2025/era5-land/era5-sea-vasternorrland-2025.csv
.venv/bin/python -m tools.fetch_osm_targets --bbox 62.5,17.2,63.7,18.9 --out data/vasternorrland2025/osm/targets-vasternorrland.geojson
.venv/bin/python -m tools.fetch_osm_terrain --bbox 62.5,17.2,63.7,18.9 --out data/vasternorrland2025/osm/terrain-vasternorrland.geojson
.venv/bin/python -m tools.fetch_met_forecasts    # ca 30 min
```

Overpass svarade 502 på terrängfrågan för hela området den 15 oktober 2026. Den hämtades då i fyra
delar som slogs ihop och konverterades med `fetch_osm_terrain --from-raw`. Upprepa kommandot
om det misslyckas.

Satellitbilderna. Sentinel-2 tar längst tid. Om nedladdningen står still i över tio minuter,
stoppa GDAL-containern (`docker ps`, sedan `docker kill <namn>`) och kör igen:

```bash
.venv/bin/python -m tools.fetch_landsat_scene
.venv/bin/python -m tools.fetch_sentinel2_scene
.venv/bin/python -m tools.fetch_sentinel1_scene   # behöver OSM-terrängen för sjöarna
```

MCF:s kartor och databasen, regnet längs vägarna och nivågivarnas punkter, i den ordningen:

```bash
.venv/bin/python -m tools.fetch_mcf_flood_maps
.venv/bin/python -m tools.load_postgis
.venv/bin/python -m tools.derive_route_exposure        # radarns regn längs vägar och järnvägar
.venv/bin/python -m tools.derive_impact_sensor_points  # givarna vid skadorna, efter fetch_smhi_hydro
```

Generalrepetitionen, med kartjänsten på Västernorrlands karta. Kl. 11 svensk tid den 7 september
larmar 6 av 6 givare och bedömningen blir "Flood probable":

```bash
TILES_FILE=vasternorrland.mbtiles docker compose up -d tiles
.venv/bin/python -m tools.check_demo --headed --out ~/demo-check-vasternorrland-$(hostname)
```

---

# Del 9 – Meteosat i översvämningarna: molntoppar, moln och åska

Kramfors 2026, Sundsvall 2026 och Västernorrland 2025 visar, utöver SMHI:s radar och sensorerna,
hur högt molntopparna nådde enligt Meteosat var 15:e minut. Stigande toppar visar åskmoln som växer, ofta innan regnet
når marken: den 15 augusti steg medelhöjden över kartområdet från cirka 5–6 km till 9 km mellan
17:00 och 18:00 svensk tid, före bräddgivarnas larm.

- **Panelen:** **Molntoppar (Meteosat)** under regnet, en kurva över medelhöjden med 8 och 10 km
  streckade och raden **Nu** med höjd och molnandel.
- **Loggen:** en rad som läses upp när topparna når 8 och 10 km och när de sjunker under 7 km igen
  (en tröskel räknas som lämnad först en kilometer under den, så att en medelhöjd som pendlar inte
  ger en rad varje kvart; Sundsvall får 16 rader på nio dygn),
  till exempel "Molntopparna över Kramfors når 8 kilometer enligt Meteosat – åskmolnen växer".
- **Kartan:** kryssa **Molntoppar (Meteosat)** i mission control (väder) för rutor färgade efter
  höjd, ljust för låga toppar och mörklila över 10 km. Rutorna är grova så här långt norrut, cirka
  tio över kartområdet, så de visar ovädret i stort, inte enskilda celler.

Satellitbevakningen visar Meteosat-10, som sände molntopparna, som en punkt över ekvatorn vid 0° längd
med "geostationär, ser … hela tiden" i listan, och SPACE VIEW zoomar ut så att den syns på 3D-globen.

Det är Meteosats produkt, inte en prognos. Data hämtas med EUMETSAT-kontot (avsnitt 2):

```bash
.venv/bin/pip install -r tools/requirements-meteosat.txt
TECHSEED_SCENARIO=kramfors2026 .venv/bin/python -m tools.fetch_meteosat_cth
TECHSEED_SCENARIO=sundsvall2026 .venv/bin/python -m tools.fetch_meteosat_cth       # nio dygn, cirka 350 MB
TECHSEED_SCENARIO=vasternorrland2025 .venv/bin/python -m tools.fetch_meteosat_cth
```

**Moln (Meteosat), alla scenarier.** Panelen har kurvan **Moln (Meteosat)**: andelen moln över
kartområdet varje timme, ur Meteosats molnmask. Varje satellitbild får sin molnandel i bildtexten, i
mission controls bildlista och i loggen, till exempel "Sentinel-1C tar bild över Kramfors – Meteosat:
100 procent moln". Det förklarar varför en optisk bild är molnig eller saknas; radarn ser genom moln.

**Åska (Meteosat-12), Kramfors, Sundsvall och Västernorrland.** Meteosat-12 (MTG) har en
blixtkamera och räknar ut åskpotentialen ur molnfria rutor:

- Kartlagret **Blixtar från rymden (Meteosat)** visar blixtarna den senaste timmen som små cyanfärgade
  punkter, också blixtar inne i molnen, bredvid SMHI:s gula blixtar. Zooma ut för att se hela området.
- Panelens **Åska (Meteosat-12)** räknar blixtarna i kartområdet den senaste timmen och visar K-index
  (åskpotential: under 20 låg, 20–30 måttlig, 30–35 hög, över 35 mycket hög – en tumregel) från de
  senaste molnfria rutorna.
- Loggen säger när en åskepisod börjar och slutar, till exempel "Meteosat ser åska över Kramfors: 87
  blixtar den senaste timmen", och första gången per dygn K-index är högt.

Norden ligger i kanten av blixtkamerans synfält. Data hämtas med EUMETSAT-kontot (avsnitt 2):

```bash
TECHSEED_SCENARIO=<scenario> .venv/bin/python -m tools.fetch_meteosat_clm   # molnmasken, alla scenarier
TECHSEED_SCENARIO=<scenario> .venv/bin/python -m tools.fetch_meteosat_li    # blixtarna, 2025–2026
TECHSEED_SCENARIO=<scenario> .venv/bin/python -m tools.fetch_meteosat_gii   # åskpotentialen, 2025–2026
```
