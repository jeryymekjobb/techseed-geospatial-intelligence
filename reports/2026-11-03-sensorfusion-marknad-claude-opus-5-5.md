# Sensorfusion: finns det redan tillämpningar?

Datum: 2026-11-03
Författare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code, på uppdrag av
Techseed. Genomgången svarar på frågan om någon organisation har en tillämpning som gör
sensorfusion på data från satelliter, väderstationer, IoT-sensorer, SMHI:s mätstationer och
liknande. Den bygger på fem webbsökningar samma dag och är inte uttömmande. Uppgifterna om
produkterna är i huvudsak leverantörernas egna och inte oberoende utvärderade.

## Sammanfattning

- Det finns flera internationella plattformar som väger samman satellit-, väder- och
  marksensordata, främst för skogsbrand och översvämning.
- Ingen hittad lösning gör allt för svenska kommuner: satellit, SMHI:s stationer, IoT och
  räddningstjänstens behov i en lägesbild med larm.
- De närmaste svenska exemplen är Forest Fires Sweden (SMHI och MSB, numera MCF), som bygger på
  satellitdata, och Visual Water (Linköpings universitet och SMHI), som är för planering.
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

## Inte undersökt

- Priser, driftstatus och oberoende utvärderingar av produkterna.
- MCF:s och räddningstjänsternas egna lägesbildssystem (till exempel RIB och WIS).
- Nordiska leverantörer som DHI och 7Analytics; sökningen gav inga träffar på dem.

## Källor

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
