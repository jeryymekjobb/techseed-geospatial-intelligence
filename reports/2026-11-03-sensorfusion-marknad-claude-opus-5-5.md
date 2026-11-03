# Sensorfusion: finns det redan tillämpningar?

Datum: 2026-11-03
Författare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code, på uppdrag av
Techseed. Genomgången svarar på frågan om någon organisation har en tillämpning som gör
sensorfusion på data från satelliter, väderstationer, IoT-sensorer, SMHI:s mätstationer och
liknande. Den bygger på fem webbsökningar samma dag, kompletterade med nio till om priser,
utvärderingar, MCF:s system och nordiska leverantörer. Den är inte uttömmande. Uppgifterna om
produkterna är i huvudsak leverantörernas egna och inte oberoende utvärderade.

## Sammanfattning

- Det finns flera internationella plattformar som väger samman satellit-, väder- och
  marksensordata, främst för skogsbrand och översvämning.
- Ingen hittad lösning gör allt för svenska kommuner: satellit, SMHI:s stationer, IoT och
  räddningstjänstens behov i en lägesbild med larm.
- De närmaste svenska exemplen är Forest Fires Sweden (SMHI och MSB, numera MCF), som bygger på
  satellitdata, och Visual Water (Linköpings universitet och SMHI), som är för planering.
- MCF:s WIS och RIB är system för informationsdelning och beslutsstöd, inte sensorfusion. De
  kompletterar snarare än konkurrerar.
- De nordiska leverantörerna DHI och 7Analytics gör prognoser och varningar för översvämning
  med modeller; ingen av dem verkar väga samman egna marksensorer med satellitdata för kommuner.
- Inga listpriser publiceras. Den enda oberoende utvärderingen som hittades gällde AI-sensorer för
  skogsbrand och visade många falsklarm, vilket stöder one-pagerns vikt vid färre falsklarm.
- Det tycks vara den luckan som övervakningen av Flens kommun (`app/monitoring/`) riktar sig mot.
  En noggrannare marknadsgenomgång behövs innan det används i one-pagern.

## Plattformar som väger samman flera sensortyper

| Organisation och produkt | Vad den gör enligt källan | Relevans för MVP:n |
|---|---|---|
| Genasys Protect (USA) | Väger samman flera sensorer i realtid för att bekräfta hot och minska falsklarm; kopplar in befintliga IoT-system, NOAA:s väderstationer, vattenstånds- och regnmätare. | Mest lik one-pagerns sensorfusion och minskade falsklarm. |
| Juvare, Unified Command Platform och Crisis Track (USA) | Krisledningsplattform med ICEYE:s radarbilder vid översvämning och brand, och SenseNets marksensorer för skogsbrand. | Satellit och marksensorer i en krisledningsmiljö. |
| PyroSense (Panorama Solutions) | IoT-sensorer, drönare och AI tillsammans med meteorologiska satellitdata för brandrisk. | Bara skogsbrand. |
| RSS-Hydro (Luxemburg) | Platsvisa "pins" vid viktiga objekt som väger samman satellitobservationer med lokalt väder och IoT. | Översvämning, på objektnivå. |
| Esri ArcGIS Velocity | Tar in IoT-flöden i realtid (MQTT, Kafka, LoRaWAN, fordon) och analyserar dem i en gemensam lägesbild; kan köras i egen drift (ArcGIS Enterprise). | En plattform att bygga på snarare än en färdig tillämpning; ligger i linje med beslutet om ArcGIS-stöd (D-2026-11-02). |
| TAHMO (Afrika) | Varning för översvämning med markstationer, mobilnätets mikrovågslänkar och satellitdata. | Visar en ovanlig regnkälla. |

## Satellit eller marksensor, men inte sammanvägda

- **OroraTech** (Tyskland) upptäcker brand med egna värmesatelliter. Grekland har ett avtal på
  20 miljoner euro om tidig varning.
- **Dryad Silvanet** (Tyskland) upptäcker brand tidigt med gassensorer på marken i ett IoT-nät;
  den senaste modellen skickar data via satellit.
- Inget hittat visar att de två kombineras. De är konkurrenter.

## I Sverige

- **Forest Fires Sweden** (SMHI och MSB, numera MCF) upptäcker skogsbrand ur satellitdata med
  öppen kod (`activefires-pp`). Det är satellit, inte en sammanvägning med marksensorer.
- **Visual Water** (Linköpings universitet och SMHI) är en interaktiv visualiseringsplattform för
  dagvatten och översvämningsplanering tillsammans med kommuner och länsstyrelser. Den är för
  planering, inte för övervakning i realtid.
- **LoV-IoT** (IoT Sverige) undersökte IoT för miljöövervakning av luft och vatten, inte
  lägesbilder vid brand eller översvämning.

## Priser, drift och oberoende utvärderingar

- **Esri ArcGIS Velocity** säljs som årlig prenumeration i nivåerna Standard, Advanced och
  Dedicated, som främst skiljer sig i hur mycket data de klarar. Esri publicerar inga listpriser i
  det som hittades. En myndighet i Oregon uppskattade 2024 på en e-postlista kostnaden för att
  införa produkten till 90 000 USD per år; det är en enskild uppskattning, inte Esris pris.
- **Genasys Protect** säljs utan offentliga priser. Avtal finns med flera amerikanska counties,
  bland annat ett femårsavtal för evakuering med Los Angeles County (2024) och avtal med Davidson
  County i North Carolina och Ada County i Idaho (2026). Genasys har i en kvartalsrapport nämnt en
  lösning på 60–70 miljoner USD med programvara, sensorer och kommunikation, men den kan inte
  knytas till ett visst county.
- **Juvare WebEOC** säljs som prenumeration efter antal användare, behörigheter och tillval, med
  årliga avgifter för underhåll och support (enligt Gartners produktsida).
- **Oberoende utvärderingar:** ingen hittades av Genasys sensorfunktioner. Felaktiga
  evakueringslarm i Los Angeles i januari 2025 granskades av en ledamot av den amerikanska
  kongressen, men det gällde utskicket av larm, inte sensorernas träffsäkerhet. En granskning av
  DHS generalinspektör fann att AI-sensorer för skogsbrand från N5 Sensors (ett kontrakt på cirka
  3 miljoner USD) inte upptäckte bränder pålitligt: en partner fick nio falsklarm av 13 larm mellan
  maj 2024 och april 2025. Det gäller ett annat företag än de i tabellen ovan.

## MCF:s och räddningstjänstens egna system

- **WIS** (webbaserat informationssystem) är MCF:s portal för Sveriges civila beredskap. Aktörer
  delar information före, under och efter samhällsstörningar för en samlad lägesbild, med begäran
  och lägesrapportering och driftinformation om Rakel. MCF ger support och länsstyrelserna kurser.
  Informationen läggs in av aktörerna; det är inte sensorfusion. Om WIS har ett gränssnitt för
  att ta emot larm från en tjänst som Flen-övervakningen är inte undersökt.
- **RIB** är MCF:s beslutsstöd för räddningstjänsten, en prenumeration på svenska. Delen
  **Farliga ämnen** har omkring 5 000 ämnen med fysikaliska data, gränsvärden, transport- och
  märkningsregler och råd till räddningspersonal; den finns fritt på `rib.msb.se/kem` och som
  appen "Farliga ämnen". RIB kan också installeras lokalt i Windows. Ett äldre pris är 900 kr per
  år utan moms för en organisation; det kan vara inaktuellt.
- **Slutsats:** WIS och RIB kompletterar en övervakning som Flens: WIS som mottagare av en
  bekräftad lägesbild, RIB som underlag i briefingen. Ingen av dem väger samman mätdata.

## Nordiska leverantörer

- **7Analytics** (Bergen) säljer programvara och modeller: FloodCube Planning för dagvatten,
  FloodCube Realtime för varningar i realtid, InzureFlood för försäkring samt GeoCube och
  RiskCube. Företaget uppger att det kan förutse översvämningar upp till sju dagar framåt utifrån
  väderprognoser, och Bergens kommun nämns som kund. Inget tyder på egna sensorer. Det tog in
  4 miljoner euro i maj 2024 (Scale Capital); uppgifterna om grundår och antal anställda skiljer
  sig mellan källorna.
- **DHI** (Danmark) har MIKE OPERATIONS, en plattform för att bygga egna system för prognoser och
  styrning i realtid med varningar. Exempel är ett system för staden Elbląg i Polen och för två
  kommuner på Guadeloupe. DHI:s Local Flash Flood Warning System kombinerar radarprognoser för
  nederbörd med hydrologi och larm, som i Aarhus med en egen X-bandsradar. Ingen användning hos en
  svensk kommun hittades.
- **SMHI** gör de nationella flödesprognoserna med modellen HYPE, som körs varje timme.

## Fortfarande inte undersökt

- Faktiska avtalspriser, som kräver upphandlingsdatabaser eller begäran om allmänna handlingar.
- Om WIS kan ta emot information maskinellt.
- Svenska kommuner som använder MIKE OPERATIONS eller liknande för varning i realtid.

## Källor

Första genomgången:


- Genasys Protect, integrationer: https://genasys.com/genasys-protect/external-integrations/
- Juvare, Unified Command Platform vid skogsbrand: https://docs.juvare.com/ucp-onuniu/juvare-events/wildfire-preparedness-and-evacuation-coordination.htm
- SenseNet och Juvare: https://www.iotevolutionworld.com/iot/articles/461355-burning-crisis-sensenet-juvare-enhance-wildfire-detection-response.htm/amp
- PyroSense: https://panorama.solutions/en/solution/pyrosense
- Innovation News Network om RSS-Hydro: https://www.innovationnewsnetwork.com/tailoring-wildfire-intelligence-for-the-frontlines-parks-and-portfolios/74361/
- Esri ArcGIS Velocity: https://www.esri.com/en-us/arcgis/products/arcgis-velocity/overview
- ArcGIS Velocity, nyheter juni 2026: https://www.esri.com/arcgis-blog/products/arcgis-velocity/real-time/whats-new-in-arcgis-velocity-june-2026
- GSMA och TAHMO, fallstudie: https://www.gsma.com/solutions-and-impact/connectivity-for-good/mobile-for-development/wp-content/uploads/2025/12/GSMA-TAHMO_CaseStudy_Leveraging-commercial-microwave-link-data-to-develop-flood-early-warning-systems_2025.pdf
- Insurance Journal om OroraTech och Dryad: https://www.insurancejournal.com/news/national/2024/12/27/805973.htm
- Dryad Gen 4 Pro: https://www.businesswire.com/news/home/20260510819235/en/Dryad-Launches-Gen-4-Pro-Silvanet-Wildfire-Sensor-Setting-New-Standard-in-Ultra-Early-Fire-Detection
- Forest Fires Sweden (EU Mission Adaptation): https://mission-adaptation-portal.ec.europa.eu/stories-0/real-time-end-end-satellite-based-forest-fire-detection-system-sweden_en
- Visual Water (Linköpings universitet): https://liu.se/forskning/visual-water
- AI-baserad varning för översvämning (Enterprise Europe Network): https://een.ec.europa.eu/partnering-opportunities/ai-based-flood-early-warning-platform-small-rivers-and-catchments
- LoV-IoT, dataplattform: https://diffusivesampling.ivl.se/download/18.5bcd43b91781d2f501c213d/1617286937668/2020-20%20The%20LoV-IoT%20project%20-%20Air%20and%20water%20monitoring%20with%20Internet%20of%20Things%20-%20Data%20platform.pdf

Kompletteringen:

- Esri, licensiering av ArcGIS Velocity: https://doc.arcgis.com/en/velocity/reference/licensing.htm
- Oregon, e-postlista om Velocity (2024): https://omls.oregon.gov/pipermail/gpl_list/2024-August/001756.html
- Los Angeles County, femårsavtal med Genasys: https://markets.financialcontent.com/firstheritage/article/gnwcq-2024-1-18-los-angeles-county-awards-5-year-contract-to-genasys-for-evacuation-management-solution
- Davidson County väljer Genasys: https://www.genasys.com/resources/davidson-county-nc-selects-genasys-to-provide-protective-communications-and-evacuation-management
- Ada County väljer Genasys: https://www.genasys.com/resources/genasys-new-emergency-alert-provider-for-ada-county-idaho
- Gartner om WebEOC: https://www.gartner.com/reviews/product/webeoc
- CBS om Genasys och larmen i Los Angeles: https://www.cbsnews.com/amp/news/los-angeles-wildfires-evacuation-alerts-genasys
- DHS OIG, sensorer för skogsbrand: https://www.oversight.gov/reports/audit/dhs-wildfire-sensors-did-not-consistently-detect-fires-and-provide-early-warning
- MCF om WIS: https://www.mcf.se/sv/amnesomraden/samhallsviktiga-kommunikationstjanster/wis/
- Länsstyrelsen Uppsala, kurs i WIS: https://www.lansstyrelsen.se/uppsala/om-oss/kalender/kalenderhandelser---uppsala/2025-12-19-wis---webbaserat-informationssystem.html
- MCF om RIB: https://www.mcf.se/en/services--tools/rib/
- MCF om appen Farliga ämnen: https://www.mynewsdesk.com/se/mcf/news/ny-app-ska-tillgaengliggoera-information-om-farliga-aemnen-411233
- Socialstyrelsen om RIB (äldre pris): https://www.socialstyrelsen.se/contentassets/31fbd01281054030ad9942dfa56937c6/2017-9-14.pdf
- 7Analytics, Business Norway: https://businessnorway.com/companies/7analytics-as
- 7Analytics, finansiering: https://siliconcanals.com/norway-based-7analytics-bags-2-5m/
- Human Progress om 7Analytics: https://humanprogress.org/we-want-to-let-people-know-before-floods-hit-them
- DHI, MIKE OPERATIONS: https://www.mikepoweredbydhi.com/products/mike-operations
- DHI, Elbląg: https://www.dhigroup.com/-/media/shared%20content/global/references/emea/case%20stories/protecting%20elblag%20city%20from%20floods%20-%20dhi%20case%20story.pdf
- DHI, Guadeloupe: https://mikepoweredbydhi.com/global/references/emea/overview/forecasting-urban-flooding-in-guadeloupe
- DHI, Flash Flood Solution: https://dhigroup.com/upload/publications/misc/DHI%20Flash%20Flood%20Solution%20SF%20v2.1.pdf
- WMO, högupplösta flödesprognoser (SMHI): https://old.wmo.int/extranet/pages/prog/hwrp/RA6/documents/2016/session3/High-resolution-flood-forecasting-Olsson.pdf
