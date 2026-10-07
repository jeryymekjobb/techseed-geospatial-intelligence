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
.venv/bin/python -m tools.start_demo vastmanland2014
```

Det skriver steg 1/4 till 4/4 och sedan "Demon går". Låt terminalen stå öppen hela dagen: demon
går tills du trycker Ctrl+C i den, som stoppar backend och sensorerna. Står det att något redan
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
.venv/bin/python -m tools.open_screens --at 2014-08-04T09:30:00Z
```

Med två skärmar hamnar satellitbevakningen på vänstra tredjedelen av den största skärmen,
huvudskärmen på resten av den och mission control på den andra skärmen. Med en skärm hamnar de
sida vid sida. Varje skärm är ett eget Chrome-fönster utan adressfält. Din vanliga Chrome
påverkas inte. Kör kommandot igen om ett fönster har hamnat fel eller stängts: det öppnar
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

Under världskartan och tidslinjen finns **Satellithändelser**, en logg över det senaste
dygnet i scenariot med den senaste händelsen överst och i gult. Loggen fyller utrymmet ned
till listan, och varje rad är märkt med var uppgiften kommer från:

| Märkning | Händelser |
|---|---|
| *beräknat* | En satellit går in över eller lämnar branden, beräknat ur banorna |
| *FIRMS 2014* | Detektionerna från en passage: hur många och den starkaste |
| *Landsat 2014* | Landsat 8 tar en bild över branden |
| *simulerat* | Från mission control: upptäcktssekvensen startar, SATCOM nere och SATCOM åter |

Loggen räknas fram ur scenarioklockan och stämmer därför också efter **RESET** eller ett hopp
i tiden.

Har du bara en stor skärm, lägg fönstren sida vid sida: satellitbevakningen till vänster,
huvudskärmen i mitten och mission control till höger. Öppna huvudskärmen först.

Slutet av huvudskärmens adress, `?at=2014-08-04T09:30:00Z`, ställer scenarioklockan på den
4 augusti 2014 kl. 11:30 svensk tid. Då hinner du visa en satellitpassage och
Landsat-bilden inom en minut.

Huvudskärmen ska visa kartan över brandområdet, och i panelen till höger ska det stå "4 aug.
2014 11:30 svensk tid".

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
surfplattan. Datorns IP-adress visas med kommandot `hostname -I`. Även huvudskärmens adress
behöver `&token=din-token` i slutet.

---

# Del 3 – Köra demon

## 10. Manuset, cirka tre minuter

Knapparna i **fetstil** finns i mission control, också hastigheten: **1 MIN/S**, **10 MIN/S**
och **1 TIMME/S** under PLAY, PAUSE och RESET. Den hastighet som gäller lyser.

Texten i kolumnen "Säg" är förslag. Använd dina egna ord.

| Tid | Gör | Säg |
|---|---|---|
| 0:00 | Klicka "Flyg till branden" på huvudskärmen. Kameran åker ut till jorden och flyger in till branden. | "Det här är skogsbranden i Västmanland sommaren 2014, återuppspelad med riktiga satellitdata." |
| 0:10 | Tryck **SPACE VIEW**, **1 MIN/S** och **PLAY**. Peka på satellitbevakningen. | "Det här är satelliterna som såg branden, Aqua, Terra och Suomi NPP, där de var den dagen. Tidslinjen visar när de passerar över branden." |
| 0:25 | Tryck **SPACE VIEW** igen. Kameran flyger tillbaka. | |
| 0:30 | Tryck **SATELLITE DETECTION**. Uppspelningen stannar, och ett kort med sex steg visas nere till höger på huvudskärmen. Steg 1, **Bild tagen**: kameran går ut så att satelliten syns, med en lila linje ner till branden. | "Här passerar Suomi NPP över branden. Det är den verkliga passagen från 2014." |
| 0:40 | Tryck **NÄSTA ▸**. Steg 2, **Anomali upptäckt ombord**, märkt SYNTETISKT. | "I framtiden kan satelliten själv se värmen och slå larm. 2014 gjordes det på marken, därför står det syntetiskt." |
| 0:50 | Tryck **NÄSTA ▸**. Steg 3, **Nedlänk till markstation**, märkt SYNTETISKT. | "Larmet skickas ner till en markstation och vidare till lägescentralen." |
| 0:55 | Tryck **NÄSTA ▸**. Steg 4, **Zoom till branden**: kameran flyger in och passagens detektioner visas. | "Det här är vad satelliten faktiskt såg. Antalet står på kortet." |
| 1:05 | Tryck **NÄSTA ▸**. Steg 5, **IoT på marken**, märkt SYNTETISKT. | "Sensorer på marken kontrollerar larmet. I demon är de simulerade." |
| 1:15 | Tryck **NÄSTA ▸**. Steg 6, **Korrelering**: kortet visar utfallet och fem regler med ✓ eller ✗. | "Reglerna jämför med kartan: brinner det i skog eller vid en industri? Det är regler som håller eller inte, ingen sannolikhet." |
| 1:30 | Tryck **NÄSTA ▸** en sista gång. Kortet försvinner. Tryck **PLAY**. Kl. 12:06 svensk tid kommer Landsat-bilden. | "Landsat 8 fotograferade branden tjugo minuter senare. Det mörka är bränd skog, det orange är brandfronten." |
| 1:45 | Tryck **1 TIMME/S**. | "Nu går tiden fortare, och branden växer." |
| 1:55 | Peka på AI ASSESSMENT till höger. Klicka "Why do you believe there is a fire?". | "Bedömningen visar varför den tror att det brinner. Varje rad pekar på sitt objekt på kartan." |
| 2:10 | Klicka "Show infrastructure within 5 km of the incident". Klicka på "SQL som kördes". | "Det här är en riktig fråga mot en kartdatabas. Frågan syns här." |
| 2:20 | Tryck **+60 MIN**, och tryck igen för att stänga. | "Prognosen är en enkel modell med stor osäkerhet." |
| 2:30 | Tryck **SATCOM FAILURE**. Vänta några sekunder. | "Satellitlänken bryts. Sensorerna fortsätter, och satellitdatan köas." |
| 2:45 | Tryck **SATCOM FAILURE** igen. | "Länken är tillbaka, och här är det som hände under avbrottet." |
| 2:55 | Tryck **GOD VIEW**, och prova filterknapparna om det finns tid. | "From Orbit to Decision." |
| Efteråt | Tryck **RESET**. | Inom ungefär fem sekunder är demon tillbaka i början och klar för nästa besökare. |

**Om upptäcktssekvensen.** SATELLITE DETECTION tar alltid nästa verkliga satellitpassage
efter scenarioklockan. Trycker du före kl. 11:35 svensk tid blir det Terra kl. 11:35, annars
Suomi NPP kl. 11:48. Båda fungerar, och kortet säger vilken satellit det är. Mission control
visar vilket steg du är på, till exempel "Steg 2/6". **NÄSTA ▸** går bara att trycka på
medan en sekvens pågår. Uppspelningen står still under hela sekvensen tills du trycker
**PLAY**.

Efter **RESET** står klockan på demons startpunkt, den 31 juli. Ladda om huvudskärmen med
adressen i avsnitt 8 för att börja kl. 11:30 den 4 augusti igen.

**Före och efter branden.** Under "Satellitbild" i panelen kan du välja datum. Med
**efter branden (jämförelse)** visas bilden från 14 september med hela det brända området,
ovanpå dagens brandfront. Välj bilden **fukt i vegetationen (NDMI)** för att visa hur torrt
det var: brunt är torrt, blått är fuktigt. Säg att bilden efter branden är en jämförelse,
inte läget vid scenariotiden – det står också på skärmen.

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
| 3D-vyn rör sig ryckigt | För hög hastighet eller för svagt grafikkort. | Tryck **1 MIN/S** i SPACE VIEW. Kör generalrepetitionen i avsnitt 6. |
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
  en röd linje för scenarioklockan. Varje mätare på kartan visar regnet den senaste timmen.
- **Översvämningskartor (modell)**: kommunens skyfallsmodeller för 30-, 100- och 500-årsregn,
  Selångersåns 100-årsflöde och MCF:s (tidigare MSB:s) karteringar av Ljungan och Indalsälven.
  Välj dem i kartans lagerlista. Största vattendjup vid 100-årsregn är påslaget från början.
- **Syntetiska bräddgivare DV1–DV8** vid kommunens kritiska dagvattenpunkter. Röd betyder att
  den bräddar. Deras värden räknas ut ur det verkliga regnet och kommunens modell.
- **Satellitbilder** under "Satellitbild": Sentinel-1:s radarbilder, som ser genom moln, och
  Landsat 8 och Sentinel-2, vars augustibilder är molniga. Från början visas den senaste
  radarbilden fram till scenariotiden. Radarbilden kan också visas som **vatten i radarbilden
  utanför sjöar och hav**, en beräknad mask.

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

**Enklast:** stoppa den demo som går med Ctrl+C i dess terminal och starta den andra:

```bash
.venv/bin/python -m tools.start_demo sundsvall2026     # tillbaka: tools.start_demo vastmanland2014
```

Kommandot byter karta i kartjänsten, startar backend och sensorerna och öppnar skärmarna på
16 augusti kl. 07:00 svensk tid, strax före den första radarbilden och regnets topp.

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
.venv/bin/python -m tools.open_screens --at 2026-08-16T05:00:00Z
```

   Klockan blir då 16 augusti kl. 07:00 svensk tid, strax före den första radarbilden och
   regnets topp. Öppnar du fönstren själv är adresserna desamma som i avsnitt 8, med
   <http://127.0.0.1:8765/3d.html?at=2026-08-16T05:00:00Z> för huvudskärmen.

Huvudskärmen ska ha rubriken "Översvämning i Sundsvall 2026 – scenario", och mission control
"Scenario: FLOOD – Sundsvall 2026".

**Tillbaka till branden:** stoppa backend med Ctrl+C och kör:

```bash
docker compose up -d tiles
.venv/bin/python -m app.backend.server
```

Sensorerna i montern, terminal 2, behöver inte startas om. De visas i båda demona.

## 17. Manuset, cirka tre minuter

Börja med huvudskärmen på adressen i avsnitt 16 och hastigheten **10 MIN/S**. Gå lugnt fram,
så att besökarna hinner se vad som händer.

| Tid | Gör | Säg |
|---|---|---|
| 0:00 | Klicka "Flyg till Sundsvall" på huvudskärmen. | "Det här är Sundsvall i augusti 2026. Det är ett scenario byggt på det verkliga regnet, inte en återgiven händelse." |
| 0:15 | Peka på "Regn (SMHI)" i panelen och på mätarna på kartan. | "Kommunen har egna regnmätare. Staplarna visar regnet timme för timme, och den röda linjen är tiden i scenariot." |
| 0:30 | Peka på de färgade fälten på kartan. | "Det här är kommunens skyfallsmodell: hur djupt vattnet kan bli vid ett 100-årsregn. Det är en modell, inte en observation." |
| 0:45 | Tryck **SPACE VIEW**, **1 MIN/S** och **PLAY**. Peka på satellitbevakningen. Tryck **SPACE VIEW** igen efter en stund. | "Sentinel-1 har radar som ser genom moln. Sentinel-2 och Landsat ser som en kamera, och de bilderna var molniga." |
| 1:00 | Tryck **SATELLITE DETECTION**. Steg 1, **Bild tagen**: Sentinel-1C kl. 07:21 svensk tid. | "Det här är en verklig radarbild från Sentinel-1, tagen över Sundsvall den morgonen." |
| 1:10 | Tryck **NÄSTA ▸** två gånger: **Anomali upptäckt ombord** och **Nedlänk**, båda SYNTETISKT. | "I framtiden kan satelliten själv hitta vatten i bilden och slå larm. Här är det illustrerat." |
| 1:25 | Tryck **NÄSTA ▸**. Steg 4, **Zoom till Sundsvall**: kartan visar radarbilden i grått. | "Radarn ser genom molnen. Släta vattenytor är mörka, och stan är ljus." |
| 1:35 | Tryck **NÄSTA ▸**. Steg 5, **IoT på marken**, SYNTETISKT. Blått på kartan är vatten i radarbilden utanför sjöar och hav. | "Det blå är en enkel beräkning, inte en kartlagd översvämning. Bräddgivarna i dagvattnet är simulerade, men har samma format som kommunens sensorplattform." |
| 1:45 | Tryck **NÄSTA ▸**. Steg 6, **Korrelering**: fyra regler med ✓ eller ✗. | "Reglerna väger regn, bräddning, modellen och radarbilden. Just den här morgonen skiljer radarn dåligt mellan vatten och land, och det säger regeln." |
| 2:00 | Tryck **NÄSTA ▸**, **10 MIN/S** och **PLAY**. Runt kl. 10 svensk tid kommer regnets topp, och bräddgivarna blir röda. | "Nu kommer det kraftigaste regnet. Fyra av åtta bräddgivare bräddar." |
| 2:15 | Tryck **PAUSE**. Peka på AI ASSESSMENT och klicka "Why do you believe there is a flood?". | "Bedömningen visar varför: regnet och bräddningen. Varje rad pekar på sitt ställe på kartan." |
| 2:30 | Klicka "Vilka byggnader ligger inom 100-årsflödet?" och sedan "SQL som kördes". | "Det här är en riktig fråga mot en kartdatabas, med kommunens och MCF:s flödeskartor." |
| 2:45 | Klicka "Vad finns inom 200 m från de bräddande punkterna?". | "Här är det som ligger nära de bräddande punkterna. Underlaget är syntetiskt." |
| 2:55 | Tryck **GOD VIEW**. | "From Orbit to Decision." |
| Efteråt | Tryck **RESET** och ladda om huvudskärmen med adressen i avsnitt 16. | Demon är klar för nästa besökare. |

**Om upptäcktssekvensen.** SATELLITE DETECTION tar alltid nästa verkliga Sentinel-1-bild över
stan efter scenarioklockan. Det finns fem i perioden: den 16 augusti kl. 07:21, den 17 augusti
kl. 07:13 och 18:29, den 18 augusti kl. 18:21 och den 22 augusti kl. 07:21, svensk tid. Trycker
du efter kl. 07:21 den 16 augusti blir det bilden nästa morgon. Varje radarbild visas på
kartan under sekvensen. Bilden den 16 augusti är tagen mitt i regnet och vinden, och där
skiljer radarn dåligt mellan vatten och land; bilderna efter den är tydligare.

**SATCOM FAILURE** fungerar som i branddemon, men det som köas är satellitbilder. Med
**1 TIMME/S** kommer nästa radarbild inom ungefär en halv minut, och efter **SATCOM FAILURE**
igen listar SYNC den.

**SENSOR FAILURE** slår ut bräddgivaren DV1. **Placera IoT-sensor** med högerklick fungerar
också. En placerad sensor räknas ut ur regnet vid närmaste mätare, men har inget modelldjup.

## 18. Riktigt, beräknat, modell och syntetiskt i översvämningen

| Kategori | Vad | Säg |
|---|---|---|
| **Riktiga data** | Regnet från kommunens mätare och SMHI:s Brämön A, Sentinel-1:s radarbilder (inte terrängkorrigerade), Landsat 8- och Sentinel-2-bilderna, satelliternas banor (Space-Track), kommunens kritiska dagvattenpunkter, kartdata från OpenStreetMap (dagens läge) | "Riktiga data från augusti 2026, uppspelade. Det är inte live." |
| **Modell** | Kommunens skyfallsmodeller, vattendjup och strömhastighet, Selångersåns 100-årsflöde, MCF:s karteringar av Ljungan och Indalsälven | "Modeller av vad som kan översvämmas. De visar inte vad som hände." |
| **Beräknat** | Satelliternas positioner och passager, vattenmasken i Sentinel-2-bilden, vattnet i radarbilden utanför sjöar och hav (en enkel tröskel), bedömningens poäng och reglerna | "Beräknat ur data. Poängen är en regelbaserad poäng, inte en sannolikhet." |
| **Syntetiskt och simulerat** | Bräddgivarna DV1–DV8 och placerade sensorer, sensorerna i montern, händelserna från mission control och sekvensens steg märkta SYNTETISKT | "Simulerat för demon. Det står på skärmen." |

Säg inte att Sundsvall översvämmades den 16 augusti, att det blå i radarbilden är en kartlagd
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
