# Regelverksregister – utkast

Underlag för MVP:n, fas 0b. Utkast gjort 2026-11-02, nu på `main`.
Registret listar lagar, EU-rättsakter, föreskrifter, villkor och standarder som **kan**
beröra en MVP byggd på dagens demonstrator (`docs/mvp/funktionskatalog.md`). Det är inte
en juridisk bedömning och inte compliance-rådgivning. Om ett regelverk gäller avgörs
först när det är bestämt vem beställaren är, vilka användarna är, hur MVP:n ska användas
och om den ska säljas, och sedan efter en granskning av en behörig person mot
primärkällorna.

Varje post har ett ID (`R-xx-nn`). Kravspecifikationen (fas 1) kan spåra krav till dem.

## Märkning

**Uppgift** gäller hur säker själva uppgiften om regelverket är, till exempel beteckning
eller datum:

| Märkning | Betydelse |
|---|---|
| **P** | Kontrollerad mot primärkälla (EUR-Lex, Riksdagen, Lagrummet, utfärdande myndighet). |
| **S** | Kontrollerad 2026-11-02 mot sekundärkällor (advokatbyråer, branschsidor). Ska bekräftas mot primärkälla. |
| **A** | Antagen ur tidigare kunskap. Inte kontrollerad i detta arbete. |

**Tillämplighet** gäller om regelverket berör MVP:n:

| Märkning | Betydelse |
|---|---|
| **Trolig** | Berör MVP:n i nästan alla tänkbara upplägg, till exempel villkor för data som redan används. |
| **Beror på** | Beror på ett beslut som inte är fattat. Beslutet anges i posten. |
| **Osannolik** | Med i registret för att utesluta den uttryckligen. Skälet anges. |

Sju poster har märkningen **P** sedan 2026-11-02: R-CS-01, R-CS-03, R-GEO-02, R-EM-02 (bara
myndighetens namn), R-AI-02, R-AI-03 och R-AI-01 (bara det allmänna tillämpningsdatumet).

## Beslut som avgör tillämpligheten

Många poster beror på samma beslut, som ännu inte är fattade (se `CONTEXT.md`, Open Questions):

- **B-KUND:** Vem som är beställare och användare. Det kan vara en myndighet, en kommun,
  ett räddningstjänstförbund eller ett företag.
- **B-ANV:** Hur MVP:n används: som intern demo, som stöd i skarpa beslut eller som ett
  system i drift.
- **B-MARK:** Om MVP:n släpps ut på marknaden, säljs eller levereras som programvara eller
  tjänst, eller om den stannar hos Techseed.
- **B-IOT:** Om riktiga IoT-noder ingår eller om sensorerna förblir syntetiska. Sedan
  beslutet 2026-10-04 är de syntetiska.
- **B-DATA:** Vilka källor som får användas utanför intern visning. Det är en öppen fråga i
  funktionskatalogen.

## A. Cybersäkerhet och produktsäkerhet

| ID | Regelverk | Uppgift | Vad det gäller | Berör funktioner | Tillämplighet |
|---|---|---|---|---|---|
| R-CS-01 | Cyberresiliensförordningen (CRA), förordning (EU) 2024/2847 | P (kontrollerad 2026-11-02, artikel 71): antagen 23 oktober 2024, tillämpas från 11 december 2027. Artikel 14 (rapporteringsplikten) tillämpas från 11 september 2026 och kapitel IV (artiklarna 35–51, anmälan av organ för bedömning av överensstämmelse) från 11 juni 2026 | Krav på cybersäkerhet för produkter med digitala element som släpps ut på EU-marknaden, sårbarhetshantering och rapportering till ENISA | Hela programvaran; F-IOT-01, F-MC-03, F-OPS-03 | Beror på B-MARK. Programvara som bara används internt släpps inte ut på marknaden. En såld eller levererad MVP kan omfattas. |
| R-CS-02 | NIS2-direktivet, direktiv (EU) 2022/2555 | A | Cybersäkerhet hos väsentliga och viktiga verksamheter, bland annat offentlig förvaltning och digital infrastruktur | Drift hos kund | Beror på B-KUND. Kravet ligger på beställarens verksamhet, inte direkt på MVP:n, men kan föras över till leverantören genom avtal. |
| R-CS-03 | Cybersäkerhetslag (SFS 2025:1506) och cybersäkerhetsförordning (SFS 2025:1507) | P: båda utfärdade 11 december 2025 och i kraft 15 januari 2026. Lagen upphäver lag (2018:1174) om informationssäkerhet för samhällsviktiga och digitala tjänster (övergångsbestämmelserna) | Svensk genomförandelag för NIS2 | Som R-CS-02 | Beror på B-KUND. |
| R-CS-04 | Radioutrustningsdirektivet, direktiv 2014/53/EU, med delegerad förordning (EU) 2022/30 om cybersäkerhet | A: den delegerade förordningen gäller från 1 augusti 2025 | Väsentliga krav för radioutrustning, bland annat skydd av nätverk, personuppgifter och mot bedrägeri | Riktiga IoT-noder (nRF91, se backloggen) | Beror på B-IOT. Osannolik med syntetiska sensorer. |
| R-CS-05 | Produktansvarsdirektivet, direktiv (EU) 2024/2853 | A: ska vara genomfört senast 9 december 2026 | Strikt ansvar för skador av defekta produkter, där programvara uttryckligen räknas som produkt | Hela programvaran | Beror på B-MARK och B-ANV. |
| R-CS-06 | Säkerhetsskyddslagen (2018:585) | A | Skydd av säkerhetskänslig verksamhet och uppgifter. Sammanställda lägesbilder över infrastruktur kan bli säkerhetsskyddsklassificerade | F-AN-05, F-AN-07, F-MAP-10, F-AN-08 | Beror på B-KUND och B-ANV. Bedöms av beställaren. |

## B. AI

| ID | Regelverk | Uppgift | Vad det gäller | Berör funktioner | Tillämplighet |
|---|---|---|---|---|---|
| R-AI-01 | AI-förordningen, förordning (EU) 2024/1689 | P för att förordningen i övrigt tillämpas från 2 augusti 2026 (skälet i 2026/1744). Grundtexten i övrigt A | Krav på AI-system efter risknivå, öppenhet och AI-kunnighet | F-AN-01–F-AN-05, F-AN-08, F-COM-02 | Beror på B-ANV. Dagens bedömningar är regelbaserade, och det är öppet om de räknas som AI-system enligt förordningens definition. Säkerhetskomponenter i kritisk infrastruktur och vissa system för räddningstjänst finns i bilaga III. Om MVP:n hamnar där måste prövas. |
| R-AI-02 | Digital omnibus om AI, som ändrar R-AI-01 | P (kontrollerad 2026-11-02): förordning (EU) 2026/1744 av den 8 juli 2026, publicerad i EUT 24 juli 2026, som också ändrar (EU) 2018/1139 och (EU) 2023/1230. Den nya artikel 113 c i AI-förordningen: kapitel III avsnitt 1–3 (utom artikel 6.5) tillämpas från 2 december 2027 för system enligt artikel 6.2 och bilaga III och från 2 augusti 2028 för system enligt artikel 6.1 och bilaga I. Ny artikel 111.2: högrisksystem som släppts ut före tillämpningsdatumet för kapitel III omfattas bara vid väsentliga ändringar, men system avsedda för offentliga myndigheter ska uppfylla kraven senast 2 augusti 2030. I kraft 27 juli 2026, den tredje dagen efter publiceringen (artikel 4). Artiklarna 102–110 tillämpas från samma dag (ny artikel 113 d) | Senarelägger högriskkraven i kapitel III avsnitt 1–3 (utom artikel 6.5): system enligt artikel 6.2 och bilaga III till 2 december 2027, system enligt artikel 6.1 och bilaga I till 2 augusti 2028 | Som R-AI-01 | Beror på B-ANV och B-KUND. |
| R-AI-03 | Krav på märkning och öppenhet för syntetiskt innehåll, artikel 50 i AI-förordningen | P (kontrollerad 2026-11-02, ny artikel 111.4): märkningsplikten i artikel 50.2 tillämpas från 2 augusti 2026. Leverantörer av system som genererar syntetiskt ljud, bild, video eller text och som släppts ut före det datumet ska uppfylla den senast 2 december 2026 | Märkning av innehåll som skapats eller ändrats av AI, och information om att man interagerar med AI | F-COM-02 (syntetisk röst), F-COM-03 | Beror på B-ANV. Uppläsningen är syntetiskt tal av loggtext. Det är öppet om den omfattas. |

## C. Geodata, rymddata och öppna data

| ID | Regelverk | Uppgift | Vad det gäller | Berör funktioner | Tillämplighet |
|---|---|---|---|---|---|
| R-GEO-01 | Copernicus datapolicy: delegerad förordning (EU) 1159/2013, rymdprogramförordningen (EU) 2021/696 och Copernicus Sentinel-licensen | S | Fri, full och öppen tillgång till Sentinel-data. Källan ska anges ("Contains modified Copernicus Sentinel data [år]"). Ingen garanti för kvalitet eller lämplighet | F-SAT-04–F-SAT-06, F-SAT-08, F-SAT-11, F-MAP-05, F-WX-05, F-WX-08, F-MAP-07 | Trolig. |
| R-GEO-02 | Lag (2016:319) och förordning (2016:320) om skydd för geografisk information, med Lantmäteriets föreskrifter (LMFS) | P för lagen (kontrollerad 2026-11-02): 9 § förbjuder utan tillstånd spridning av sammanställningar av geografisk information över Sveriges sjöterritorium (utom insjöar, vattendrag och kanaler), och över övrigt territorium om informationen inhämtats från luftfartyg. 10 § 1 undantar sammanställningar som framställts endast med fjärranalys från satellit. Förordningen och LMFS är inte kontrollerade | Tillstånd för att sprida vissa sammanställningar av geografisk information, med hänsyn till totalförsvaret | F-SAT-05, F-SAT-11, F-MAP-03, F-MAP-10, eventuella flyg- eller drönarbilder och data om havsområden | Beror på B-DATA. Satellitbilder som bara bygger på fjärranalys från satellit omfattas inte. Flyg- och drönarbilder över land och information om sjöterritoriet, till exempel djupdata vid kusten, kräver en bedömning om de läggs till. |
| R-GEO-03 | INSPIRE-direktivet, direktiv 2007/2/EG, och lag (2010:1767) om geografisk miljöinformation | A | Infrastruktur, metadata och tjänster för offentlig geodata | F-MAP-06, F-SC-01 | Beror på B-KUND. Gäller offentliga dataägare. Det är relevant om MVP:n ska läsa INSPIRE-tjänster eller leverera data till en myndighet. |
| R-GEO-04 | Öppna data-direktivet, direktiv (EU) 2019/1024, genomförandeförordning (EU) 2023/138 om värdefulla dataset och lag (2022:818) om den offentliga sektorns tillhandahållande av data | A | Villkor för vidareutnyttjande av offentliga data, bland annat geodata, meteorologiska data och jordobservationsdata | F-WX-01–F-WX-04, F-WX-07, F-WX-09, F-MAP-03 | Trolig som grund för källornas villkor. Kraven ligger på dataägarna. |
| R-GEO-05 | Villkor per datakälla: NASA FIRMS, EUMETSAT och LSA SAF, Space-Track, SMHI, MET Norway, MCF, OpenStreetMap (ODbL), Lantmäteriet och kommunernas lager | Delvis kontrollerade i tidigare rapporter, till exempel `reports/2026-10-21-space-track-villkor-claude-opus-5-5.md` och `reports/2026-10-30-kreditering-utanfor-kartbilden-claude-opus-5-5.md` | Licens, kreditering och spridning. Västerås stads data får bara användas internt | F-MAP-07, F-OPS-04 och alla dataflöden | Trolig. Ska samlas i en tabell per källa i fas 1. Rätten att visa är inte samma sak som rätten att sprida (se backloggen). |
| R-GEO-06 | Rymdlagstiftning: lag (1982:963) om rymdverksamhet och föreslagen EU-rymdakt | A | Uppskjutning och drift av rymdföremål | – | Osannolik. MVP:n använder data och beräknade banor men driver inga rymdföremål. |

## D. Personuppgifter och data

| ID | Regelverk | Uppgift | Vad det gäller | Berör funktioner | Tillämplighet |
|---|---|---|---|---|---|
| R-DP-01 | Dataskyddsförordningen (GDPR), förordning (EU) 2016/679, och dataskyddslagen (2018:218) | A | Behandling av personuppgifter | F-AN-05, F-AN-06, F-MAP-10, F-OPS-05, framtida inloggning | Beror på B-KUND och B-ANV. Byggnader och adresser kan bli personuppgifter när de kopplas till fastigheter eller personer. I dag finns inga användarkonton. |
| R-DP-02 | Dataförordningen (Data Act), förordning (EU) 2023/2854 | A: gäller från 12 september 2025 | Åtkomst till data från uppkopplade produkter och byte mellan molntjänster | F-IOT-01 | Beror på B-IOT och B-MARK. |
| R-DP-03 | Offentlighets- och sekretesslagen (2009:400) och tryckfrihetsförordningens regler om allmänna handlingar | A | Allmänna handlingar och sekretess hos offentliga beställare | Loggar, lägesbilder, F-COM-01 | Beror på B-KUND. Gäller om beställaren är en myndighet eller kommun. |

## E. Krisberedskap och räddningstjänst

| ID | Regelverk | Uppgift | Vad det gäller | Berör funktioner | Tillämplighet |
|---|---|---|---|---|---|
| R-EM-01 | Lag (2003:778) om skydd mot olyckor | A | Kommunal och statlig räddningstjänst, ledning och förebyggande arbete | F-AN-01–F-AN-07, F-MC-01 | Beror på B-KUND och B-ANV. Ställer inga produktkrav, men bestämmer vilka beslut lägesbilden kan stödja och vem som fattar dem. |
| R-EM-02 | Förordning (2022:524) om statliga myndigheters beredskap, samt föreskrifter från Myndigheten för civilt försvar (MCF) | P för namnet: Myndigheten för samhällsskydd och beredskap (MSB) heter Myndigheten för civilt försvar från 1 januari 2026. Det är samma myndighet med nytt namn, genom SFS 2025:1124 som ändrar instruktionen (2008:1002). Förordningen 2022:524 är inte kontrollerad. Föreskrifter utfärdade före namnbytet heter fortfarande MSBFS | Beredskap, samverkan och informationsdelning hos myndigheter | Lägesbild och delning | Beror på B-KUND. |
| R-EM-03 | Översvämningsdirektivet, direktiv 2007/60/EG, och förordning (2009:956) om översvämningsrisker | A | Kartläggning av översvämningsrisk och riskhanteringsplaner | F-MAP-06, F-AN-02 | Beror på B-KUND. Det är källan till MCF:s karteringar. MVP:n får inte framstå som en kartering enligt förordningen. |

## F. Tillgänglighet och upphandling

| ID | Regelverk | Uppgift | Vad det gäller | Berör funktioner | Tillämplighet |
|---|---|---|---|---|---|
| R-ACC-01 | Lag (2018:1937) om tillgänglighet till digital offentlig service, med webbtillgänglighetsdirektivet (EU) 2016/2102 | A | Krav på att offentliga aktörers digitala service är tillgänglig (WCAG via EN 301 549) | Alla skärmar | Beror på B-KUND. Undantag för vissa interna system ska prövas. |
| R-ACC-02 | Tillgänglighetsdirektivet (EAA), direktiv (EU) 2019/882, och lag (2023:254) | A: gäller från 28 juni 2025 | Tillgänglighetskrav på vissa produkter och tjänster till konsumenter | – | Osannolik. MVP:n riktar sig inte till konsumenter. |
| R-PRO-01 | Lag (2016:1145) om offentlig upphandling och lag (2016:1146) om upphandling inom försörjningssektorerna | A | Hur en offentlig beställare får köpa MVP:n och vilka krav den kan ställa | Hela leveransen | Beror på B-KUND. |

## G. Standarder och specifikationer

Standarderna är inte bindande i sig. De blir krav när en lag hänvisar till dem som
harmoniserade standarder, eller när beställaren eller avtalet kräver dem. Alla poster i
denna del har märkningen **A**.

| ID | Standard | Område | Berör funktioner | Tillämplighet |
|---|---|---|---|---|
| R-STD-01 | OGC WMS, WMTS och WFS, samt ISO 19128 | Karttjänster | F-MAP-02, F-MAP-03, F-MAP-06 | Trolig. Används redan. |
| R-STD-02 | ISO 19115 och 19157 | Metadata och datakvalitet för geodata | F-SC-01, F-OPS-04, SOURCE-filer | Trolig som grund för spårbar källinformation. |
| R-STD-03 | ISO 19111 och EPSG, med SWEREF 99 och RH 2000 | Koordinatreferenssystem och höjdsystem | Alla kartlager, F-WX-09 | Trolig. |
| R-STD-04 | ISO/IEC 27001 och 27002 | Ledningssystem för informationssäkerhet | Drift och utveckling | Beror på B-KUND. |
| R-STD-05 | IEC 62443 och ETSI EN 303 645 | Säkerhet för industriella system och IoT-enheter | F-IOT-01 | Beror på B-IOT. |
| R-STD-06 | EN 18031-1, -2 och -3 | Harmoniserade standarder för cybersäkerhet under radioutrustningsdirektivet (R-CS-04) | Riktiga IoT-noder | Beror på B-IOT. |
| R-STD-07 | Harmoniserade standarder under CRA | Under framtagning. Status ska kontrolleras | Hela programvaran | Beror på B-MARK. |
| R-STD-08 | ISO/IEC 42001 och ISO/IEC 23894 | Ledningssystem och riskhantering för AI | F-AN-01–F-AN-05 | Beror på R-AI-01. |
| R-STD-09 | EN 301 549 och WCAG 2.1 eller 2.2 | Tillgänglighet | Alla skärmar | Beror på R-ACC-01. |
| R-STD-10 | MQTT 3.1.1 och 5 (OASIS) samt TLS 1.2 och 1.3 | Protokoll och transportskydd för IoT | F-IOT-01 | Beror på B-IOT. Backloggen tar redan upp ett skyddat MQTT. |
| R-STD-11 | CAP (Common Alerting Protocol, OASIS) och EDXL | Utbyte av varningar och lägesinformation | F-COM-01, F-AN-05 | Beror på B-ANV. Det är en möjlig export för delning med räddningstjänst. |
| R-STD-12 | Esris ArcGIS REST API (Map, Feature och Image Service). Det är en leverantörsspecifikation, inte en formell standard | Inläsning från ArcGIS Server, ArcGIS Online och ArcGIS Enterprise | Datainhämtningen läser MCF:s karteringar med ArcGIS REST-frågan som GeoJSON (`tools/fetch_mcf_flood_maps.py`, F-OPS-05). Skärmarna läser ArcGIS Server bara via WMS (F-MAP-06), och kundens egna ArcGIS-tjänster läses inte | Trolig, enligt beslutet D-2026-11-02. |
| R-STD-13 | OGC API – Features (del 1 också som ISO 19168-1) | Inläsning av objekt från moderna GIS-tjänster, efterföljaren till WFS | Saknas i dag. WFS används i datainhämtningen (F-OPS-05) | Trolig, enligt beslutet D-2026-11-02. |
| R-STD-14 | OGC GeoPackage | Filformat för vektor- och rasterdata, öppnas i ArcGIS och QGIS | Saknas i dag | Trolig, enligt beslutet D-2026-11-02. Även för utlämning i MVP:ns roadmap. |
| R-STD-15 | Esri Shapefile (Esris tekniska beskrivning, 1998) | Vanligt filformat för vektordata | Saknas som inläsning i MVP:n. Används i datainhämtningen för Copernicus EMS (F-SAT-08) | Trolig, enligt beslutet D-2026-11-02. |
| R-STD-16 | GeoJSON, RFC 7946 (IETF) | Filformat för vektordata i WGS 84 | Används internt, till exempel för sensorer och kommunens objekt. Saknas som inläsning av användarens filer | Trolig, enligt beslutet D-2026-11-02. |
| R-STD-17 | OpenStreetMap: datamodellen, ODbL 1.0 och OSMF:s riktlinjer för användning av data och tiles | Baskarta och källa för vägar, byggnader och orter | F-MAP-02, F-MAP-03, F-MAP-10 | Trolig, enligt beslutet D-2026-11-02. Licensen finns också under R-GEO-05. |

## Nästa steg

1. Kontrollera övriga poster med märkningen **S** och **A** mot primärkällor och lägg till
   länkar till dem.
2. Gå igenom tillämpligheten när B-KUND, B-ANV och B-MARK är besvarade efter beställarens
   one-pager.
3. Samla villkoren per datakälla (R-GEO-05) i en tabell med licens, kreditering och
   spridning.
4. Låt en behörig person granska de poster som ska bli krav, innan något presenteras som
   uppfyllt.

## Primärkällor kontrollerade 2026-11-02

- R-CS-01: [Förordning (EU) 2024/2847 (Cyber Resilience Act)](https://eur-lex.europa.eu/legal-content/SV/TXT/?uri=CELEX:32024R2847), artikel 71, EUR-Lex. Texten klistrades in av användaren.
- R-AI-01, R-AI-02 och R-AI-03: [Förordning (EU) 2026/1744 (Digital Omnibus on AI)](https://eur-lex.europa.eu/legal-content/SV/TXT/?uri=CELEX:32026R1744), rubriken, skälen om artikel 113 och artikel 50.2, de ändrade artiklarna 111 och 113 och artikel 4, EUR-Lex. Texten klistrades in av användaren.
- R-CS-03: [Cybersäkerhetslag (2025:1506)](https://data.riksdagen.se/dokument/sfs-2025-1506.html) och [cybersäkerhetsförordning (2025:1507)](https://data.riksdagen.se/dokument/sfs-2025-1507.html), Riksdagen.
- R-GEO-02: [Lag (2016:319) om skydd för geografisk information](https://data.riksdagen.se/dokument/sfs-2016-319.html), 9 och 10 §§, Riksdagen.
- R-EM-02: [SFS 2025:1124, förordning om ändring i förordningen (2008:1002) med instruktion för Myndigheten för samhällsskydd och beredskap](https://svenskforfattningssamling.se/sites/default/files/sfs/2025-11/SFS2025-1124.pdf), Svensk författningssamling.

## Källor för kontrollen 2026-11-02 (sekundärkällor)

- Cybersäkerhetslagen: [CMS: NIS2 to be implemented into Swedish law by the new Cybersecurity Act](https://cms.law/en/swe/legal-updates/nis2-to-be-implemented-into-swedish-law-by-the-new-cybersecurity-act), [MCF: konsekvensutredning MCFFS 2026:1](https://www.mcf.se/contentassets/9f0c38cd40b7485f9f006047555533bc/konsekvensutredning-mcffs-2026-1.pdf).
- Digital omnibus om AI: [Gibson Dunn: EU AI Act Omnibus Agreement](https://www.gibsondunn.com/eu-ai-act-omnibus-agreement-postponed-high-risk-deadlines-and-other-key-changes/), [Sidley: provisional agreement to delay key EU AI Act obligations](https://datamatters.sidley.com/2026/06/22/eu-lawmakers-reach-provisional-agreement-to-delay-key-eu-ai-act-obligations/).
- CRA: [Jones Day: EU Cyber Resilience Act 24-hour reporting duties start September 11, 2026](https://www.jonesday.com/en/insights/2026/07/eu-cyber-resilience-act-24hour-reporting-duties-start-september-11-2026), [Freshfields: CRA reporting obligations take effect on 11 September 2026](https://www.freshfields.com/en/our-thinking/blogs/technology-quotient/cyber-resilience-act-reporting-obligations-take-effect-on-11-september-2026-102nzmk).
- Copernicus: [Copernicus Sentinel data licence](https://ads.atmosphere.copernicus.eu/licences/ec-sentinel), [Copernicus Land: data policy](https://land.copernicus.eu/en/data-policy).
- Lag (2016:319): [Riksdagen: lagtext](https://data.riksdagen.se/dokument/sfs-2016-319.html), [Lantmäteriet: information om lag och föreskrifter för spridningstillstånd](https://www.lantmateriet.se/globalassets/temawebbar/spridningstillstand/info_lag_foreskrifter_spridningstillstand.pdf).
