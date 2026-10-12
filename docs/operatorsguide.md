# Operatörsguide – brandkartan på IoTDagen

Den här guiden tar dig från en dator utan något installerat till en demo som går i
montern. Varje steg säger vad du gör, varför, och vad du ska se när det har fungerat.
Läs gärna igenom hela guiden en gång innan du börjar.

Teknisk bakgrund för utvecklare finns i `app/README.md`.

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

- **Linux**, till exempel Ubuntu. Guiden är skriven för Ubuntu.
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

Två konton behövs bara i särskilda fall och kan hoppas över för demon:

| Vad | När det behövs |
|---|---|
| Copernicus CDS | Bara om vinddatan från ERA5-Land ska hämtas om. Den finns redan i repot. |
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

Demon behöver två tillägg till Python: ett för sensorerna och ett för
generalrepetitionen. De installeras i en egen mapp, `.venv`, så att resten av datorn inte
påverkas:

```bash
python3 -m venv .venv
.venv/bin/pip install -r app/requirements-iot.txt -r app/requirements-orbits.txt -r tools/requirements-record.txt
```

Det tar någon minut. Sista raden ska börja med `Successfully installed`.

## 5. Hämta och bygga data

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

Låt terminalen stå öppen hela dagen. **BYT DEMO** överst i mission control avslutar demon,
stänger satellitmonitorn och huvudskärmen och visar menyn i mission control igen; Ctrl+C i terminalen stoppar backend och sensorerna. Står det att något redan
svarar på port 8765 går en backend redan; stoppa den först. Sensorernas rader hamnar i
`data/node-sim.log`. Skärmarna öppnas på 4 augusti 2014 kl. 11:30 svensk tid; avsnitt 8 beskriver
dem.

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
Varje satellits bana är svag där den redan har flugit och stark där den är på väg. Terra och
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
| *PostGIS* | Hotad bebyggelse vid översvämningen: hur många byggnader som ligger inom 200 m från en sensor när den börjar larma, ur kartdata i PostGIS |
| *simulerat* | Från mission control: upptäcktssekvensen startar, SATCOM nere och SATCOM åter, SENSOR FAILURE, IoT av och på, och en sensor som placeras på kartan |

Loggen räknas fram ur scenarioklockan och stämmer därför också efter **RESET** eller ett hopp
i tiden. En sensorrad visas så fort scenarioklockan når ändringen; sensorernas ändringar är
beräknade ur deras modeller i steg om 10 minuter. Efter **SENSOR FAILURE** visas inga fler rader
för den sensorn, och medan IoT är avstängt visas inga sensorrader eller byggnadsrader. Är PostGIS
inte igång blir det inga byggnadsrader; ladda om satellitbevakningen när PostGIS är igång.

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
  Lantmäteriets topowebb när den är aktiverad (bara 2D). Varje karta visar den första
  ikryssade som den har; utan ikryssad baskarta visar 3D-globen bara Natural Earth II.
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
surfplattan. **BYT DEMO** fungerar bara när demon är startad med `tools.start_demo`; med
backend startad så här svarar den att det inte går. Datorns IP-adress visas med kommandot `hostname -I`. Även huvudskärmens adress
behöver `&token=din-token` i slutet.

---

# Del 3 – Köra demon

## 10. Manuset, cirka tre minuter

Knapparna i **fetstil** finns i mission control. Hastigheten väljer du i listan **Hastighet**
under PLAY, PAUSE och RESET – 1 minut/s, 10 minuter/s, 30 minuter/s, 1 timme/s eller 3
timmar/s – och tar i bruk med **ANVÄND** till vänster om listan. Listan visar den hastighet som
gäller. **RESET** ändrar inte hastigheten. Spara den med **SPARA PROFIL FÖR SCENARIOT** så
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
| **Riktiga data** | Satelliternas upptäckter av branden (NASA FIRMS), också passagen och detektionerna i upptäcktssekvensen, Landsat-bilderna (USGS), väderobservationer från SMHI, satelliternas banor (Space-Track), kartdata från OpenStreetMap (dagens läge, inte 2014) | "Riktiga data från 2014, uppspelade. Det är inte live." |
| **Beräknat** | Satelliternas positioner, vinden (ERA5-Land, en modell), brandprognosen, bedömningens poäng, reglerna i sekvensens korreleringssteg | "Beräknat ur data. Poängen är en regelbaserad poäng, inte en sannolikhet." |
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
| GOD VIEW blir tom på 2D-kartan | Känd begränsning: den sparade kartan täcker bara brandområdet. | Använd 3D-vyn (`3d.html`). |
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

- **Regn (SMHI)** i panelen: timmar och dygn vid den mätare du väljer, och ett stapeldiagram med
  en röd linje för scenarioklockan. Varje mätare på kartan visar regnet den senaste timmen, och
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
  kan också visas som **vatten i radarbilden utanför sjöar och hav**, en beräknad mask.

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

**Enklast:** tryck **BYT DEMO** överst i mission control och bekräfta. Demon avslutas,
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

- **Vattenföring och vattenstånd (SMHI)** i panelen: vattenföringen vid Heåkra, Ellinge,
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
  jämförelse), med falska färger i kortvågig IR där bränd skog är rödbrun och aktiv brand orange.
  Landsat är för molnig över branden de veckorna och är inte med.
- **Brandområdet enligt Copernicus EMS** (aktivering EMSR298, området Enskogen) som en lila
  streckad linje, kartlagt ur SPOT-6/7- och Sentinel-2-bilder: från 2 125 hektar på bilden 17
  juli till 17 936 hektar 7 augusti. Varje karta visas från slutet av bildens dag, eftersom
  bilderna saknar klockslag. Förklaringen under "Prognos (modell)" säger vilken bild och yta som
  visas. Jämför med brandfronten ur FIRMS, som är skalet runt alla detektioner och därför större.

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
.venv/bin/python -m tools.load_postgis    # databasen ljusdal2018, för frågorna
```
