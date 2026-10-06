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
.venv/bin/pip install -r app/requirements-iot.txt -r tools/requirements-record.txt
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

Demon behöver två program som är igång hela dagen. Öppna **två terminaler** och gå in i
repot i båda (`cd ~/techseed-geospatial-intelligence`).

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

Öppna tre fönster i Chrome:

| Skärm | Adress | Var |
|---|---|---|
| Huvudskärmen | <http://127.0.0.1:8765/3d.html?at=2014-08-04T09:30:00Z> | Stora skärmen. Tryck F11 för helskärm. |
| Satellitbevakningen | <http://127.0.0.1:8765/monitor.html> | Bredvid huvudskärmen, så att besökarna ser båda. |
| Mission control | <http://127.0.0.1:8765/control.html> | Din skärm bredvid. |

Satellitbevakningen visar hela tiden var satelliterna är och när de passerar över branden.
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
