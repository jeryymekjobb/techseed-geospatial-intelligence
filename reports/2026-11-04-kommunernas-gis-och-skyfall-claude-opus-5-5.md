# Kommunernas GIS och skyfallskarteringar

Datum: 2026-11-04
Författare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code, på uppdrag av
Techseed. Rapporten inventerar de publika GIS-tjänsterna hos de sju kommuner i den
kontinuerliga övervakningen som i dag tar skyddsvärda objekt och byggnader från
OpenStreetMap: Sundsvall, Kramfors, Ljusdal, Sala, Västerås stad, Höör och Vellinge. Den
inventerar också skyfallskarteringar för de kommuner som saknar en sådan i övervakningen.
Den bygger inget och ändrar inget i koden. Användaren har beslutat att lagar, regler och
säkerhet ska utredas innan något implementeras.

**Rapporten är inte juridisk rådgivning.** Bedömningarna mot regelverksregistret
(`docs/mvp/regelverksregister.md`) är förslag. Enligt repots regel (`AGENTS.md`) är
tolkningar av regelverk olösta tills de har kontrollerats mot auktoritativa källor och av
kvalificerad granskning. Frågorna om personuppgifter ska till beställarens
dataskyddsombud. Inget i rapporten säger att data får användas.

## Sammanfattning

- **Alla sju kommunerna utom Kramfors och Ljusdal har publika tjänster med geometri** för
  förskolor och skolor: Sundsvall (GeoServer, WFS), Västerås (ArcGIS FeatureServer),
  Sala, Höör och Vellinge (ArcGIS REST). Byggnader finns publikt hos Sundsvall, Västerås,
  Höör och Vellinge, inte hos Sala.
- **Vårdcentraler finns bara hos Sundsvall** (`SundsvallsKommun:Vardcentraler_punkt`, 13
  punkter). Ingen av de andra har ett publikt lager för vårdcentral, distriktssköterska
  eller folktandvård. Regionerna driver vården, så OSM blir kvar som källa för vård.
- **Samma tjänster innehåller lager som Flens regler utesluter.** Gruppboenden,
  individstöd, serviceboenden och hemtjänstlokaler (Sundsvall), *Boende för skadligt bruk
  och beroende*, *Daglig verksamhet enligt LSS* och *Korttidsvistelse* (Västerås, i
  samma punktlager som förskolorna), demensboenden med enhetschefens namn och telefon
  (Höör), äldreboenden (Vellinge, Sala saknar), VA och el. De ska inte hämtas.
- **Adress- och fastighetsfält finns i nästan alla lager** och ska väljas bort per fält.
  Byggnadslagren (Sundsvall, Höör, Vellinge, Västerås) har fastighetskopplingar,
  husnummer och signaturer för den som ändrat posten. Bara geometrin behövs.
- **Sundsvalls villkor** säger att data får användas bara av fem kommuner om inget annat
  avtalas. Användaren har godkänt kommunens lager för demon (2026-10-06), men villkoret
  gäller fortfarande.
- **Skyfall.** Kramfors: Länsstyrelsen Västernorrlands lågpunktskartering och rinnvägar,
  WMS, CC0. Sala: Länsstyrelsen Västmanlands och SMHI:s skyfallskartering 2017, WMS, CC BY
  4.0, och samma data i kommunens egen tjänst. Höör: ingen kartering hittad; Geoinfo
  Mittskånes *Skyfall 2024* ligger över Hörby och bara en liten del av Höör. Ljusdal och
  Vellinge: ingen publicerad skyfallskartering hittad, varken hos kommunen eller
  länsstyrelsen.

## Metod

Den 2026-11-04 lästes, med GET och små anrop:

- ArcGIS REST-katalogerna hos Vellinge (`karta.vellinge.se`), Sala (`geodata.sala.se`),
  Västerås (`kartor.vasteras.se`) och Geoinfo Mittskåne (`karta.geoinfomittskane.se`,
  Höörs och Hörbys gemensamma GIS), mappar utan token. För varje relevant lager:
  lagerbeskrivning (`?f=json`), antal (`returnCountOnly`) och en enda post med
  `returnGeometry=true&outSR=4326&resultRecordCount=1`.
- Höörs offentliga objekt i ArcGIS Online (`sharing/rest/search?q=orgid:XcHB8YVJHmlQKJsZ`)
  och tjänsterna på `services2.arcgis.com/XcHB8YVJHmlQKJsZ`.
- GetCapabilities för WFS och WMS hos Sundsvall (`karta.sundsvall.se/geoserver`) och
  Västerås (`kartserver.vasteras.se/geoserver`), DescribeFeatureType och
  `resultType=hits` för de relevanta lagren.
- Västerås samhällskarta (Origo, `kartor.vasteras.se/sam/vas.json`).
- Länsstyrelsernas geodatakatalog (CSW, `AnyText = 'skyfallskartering'`, 265 poster) och
  metadataposterna för Kramfors och Västmanland, samt länsstyrelsernas WMS med en
  GetMap på 256 × 256 px över Kramfors och Sala.
- Kramfors (`map.kramfors.se`) och Ljusdals (`kommunkarta.ljusdal.se`) Sokigo-kartor.
- Webbsökningar efter skyfallskarteringar och öppna data för kommunerna.

Inga data har sparats i repot. Exempelvärden nedan är namn på verksamheter, inte
uppgifter om personer.

Märkning: **V** = verifierat med anrop 2026-11-04. **O** = inte verifierat (från
webbsökning, metadata eller slutsats).

## Utgångspunkt: Flens urval

Enligt `app/monitoring/areas/flenkommun.py`, `app/monitoring/gis.py`, registret
(R-DP-01, R-CS-06, R-CS-07, R-GEO-02, R-GEO-05) och CONTEXT.md (2026-11-03):

- **Med:** förskolor, grundskolor, gymnasier, vårdcentraler, distriktssköterskor,
  folktandvård och byggnader som punkter. Bara namnfält hämtas.
- **Inte med:** boenden för personer med funktionsnedsättning (till säkerhet och
  dataskydd är genomlysta), socialtjänstens lokaler, adresser, fastighetsbeteckningar, VA,
  el och sådant som kan vara skyddsobjekt.
- **Väntar:** särskilda boenden för äldre (roadmap-punkt 3, utredning pågår).
- **Användning:** bara intern, i det oversionerade `data/monitoring/<area>/gis/`.

## Per kommun

### Sundsvalls kommun

**Tjänst (V):** `https://karta.sundsvall.se/geoserver/wfs` (GeoServer, WFS 1.1.0/2.0.0,
874 lagertyper i WFS, 21 namnrymder). GetFeature med `outputFormat=application/json` och
`srsName=EPSG:4326` ger punktgeometri.

| Lager (WFS)                            | Antal  | Fält                                                                                                                                                        | Not                                                                           |
| -------------------------------------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `SundsvallsKommun:Forskolor_punkt`     | 72     | Namn, **Adress, Postnr, Ort**, Ansvar, ID                                                                                                                   | Punkt                                                                         |
| `SundsvallsKommun:Skolor_punkt`        | 56     | Enhetsnamn, **Adress**, Ort, Typ, Ansvar, Skola, ID                                                                                                         | Punkt. Dessutom ett lager per skola (`*_punkt`, `*_linje`, skolskjutsområden) |
| `SundsvallsKommun:Vardcentraler_punkt` | 13     | X, Y, Namn, **Adress**                                                                                                                                      | Punkt, t.ex. "Hälsocentralen Liden"                                           |
| `SundsvallsKommun:bal_byggnad_yta`     | 85 530 | 60 fält, bland dem **bal_husnummer, bal_ligger_pa_fastighet, bal_tillhor_fastighet, bal_berors_av_fastighet, td_skapad_av, td_andrad_av, td_bygg_arendeid** | Yta (byggnader, BAL-modellen)                                                 |

**Ska uteslutas enligt Flens regler (V, finns i samma tjänst):**
`Gruppboende_punkt` (39; namn, **adress**, typ), `Individstod_punkt`,
`Serviceboenden_punkt`, `BistandsbedomdaTrygghetsboenden_punkt`, `Hemtjanstlokaler_punkt`,
`Aldreboende_punkt` (19; väntar som Flens särskilda boenden), `FastighetBeteckningFullstandig_punkt`,
MSVAB:s VA-lager, `Reningsverk_punkt`, SEAB:s elnätsområden, `td_kraftledning_linje`,
`Skyddsrum_punkt`, `MRF:Brandstationer_punkt`. Lager från MSVAB, SEAB, Länsstyrelsen,
Lantmäteriet, Ånge kommun och Kommunförbundet Västernorrland har andra ägare.

**Villkor (V):** WMS-tjänstens beskrivning: "Use of data delivered by this WMS-server is
under copyright of Sundsvalls kommun, Timrå kommun, Härnösands kommun, Kramfors kommun or
Örnsköldsviks kommun. No use is permitted to users outside of these five organisations, if
not explicitly agreed." `Fees` och `AccessConstraints` är `NONE` i både WMS och WFS.
Användaren bekräftade 2026-10-06 att kommunens lager får användas i demon (CONTEXT.md).
Om det godkännandet täcker punktlager i övervakningen är **O**.

**Skyfall:** finns redan i övervakningen (`SundsvallsKommun:{30,100,500}-ar_maxvattendjup`).
Länsstyrelsen Västernorrlands lågpunkter och rinnvägar för Sundsvall finns också (se
Kramfors).

### Kramfors kommun

**Tjänst:** `https://map.kramfors.se/` är Sokigo Spatial Map. `/wms` svarar men kräver en
parameter `servicename`; åtta gissade namn gav fel (V). Ingen ArcGIS REST eller GeoServer
på värden (404, V). Inga publika lager för förskolor, skolor, vård eller byggnader hittade.

**Andra källor (V):** Sundsvalls GeoServer har `KommunforbundetVn:SolayByggnaderKramfors_yta`
(33 080 byggnader med solinstrålning, ägare Kommunförbundet Västernorrland). Det ligger
under Sundsvalls villkor om fem organisationer; Kramfors kommun är en av dem, Techseed
inte. Användning kräver avtal (**O**).

**Skyfall (V):** Länsstyrelsen Västernorrland (LstY) har en lågpunktskartering och
rinnvägar per kommun, gjorda med Länsstyrelsen Jönköpings metod.

- WMS: `https://ext-geodata-lokala-visning.lansstyrelsen.se/arcgis/services/LSTY/LstY_Skyfall_ext/MapServer/WMSServer`,
  lager `12` *LstY Skyfallskartering Kramfors lågpunkter djupvärden(m)* och `5` *… Kramfors
  rinnvägar* (WMS-numreringen skiljer sig från REST, där de är 2 och 3). En GetMap över
  Kramfors tätort gav lågpunkterna i magenta.
- Nedladdning: `https://ext-dokument.lansstyrelsen.se/Vasternorrland/Geodata/LstY_Skyfallskartering_Kramfors_lagpunkter.zip`
  och `…_rinnvagar.zip`.
- Villkor i metadata (V): "inga tillämpliga villkor", "Creative commons CC0 1.0
  Universiell". Säkerhetsklassning K1 ("Ingen eller försumbar skada") för
  konfidentialitet.
- Abstract: materialet "är en indikator för potentiella riskområden ... som en vägledning
  och inte som en absolut sanning". Det är en topografisk analys, inte en hydraulisk
  skyfallsmodell som Sundsvalls eller Västerås.

### Ljusdals kommun

**Tjänst:** `https://kommunkarta.ljusdal.se/` är Sokigo Spatial Map, med samma `/wms` som
kräver `servicename` (V). Ingen ArcGIS REST eller GeoServer (404, V). Inga publika lager
hittade.

**Skyfall:** ingen publicerad skyfallskartering hittad, varken hos kommunen eller
Länsstyrelsen Gävleborg (LstX). Geodatakatalogens 265 poster med "skyfallskartering" har
ingen från LstX (V). Webbsökning gav en översvämningsutredning för Stavsätter (WSP, 2024)
och kommunens vattenplan, men ingen kartering (O). Länsstyrelsen Gävleborg har en rapport
om skyfallen i augusti 2021, för andra kommuner i länet (O).

### Sala kommun

**Tjänst (V):** `https://geodata.sala.se/arcgis/rest/services` (ArcGIS). Mapparna
Fastighetsenheten, GaidaGaturummet, Geodataenheten, GVS och Hosted kräver token.

| Tjänst och lager                                                     | Antal | Fält                                                | Not                                                                                     |
| -------------------------------------------------------------------- | ----- | --------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `vard_skola_omsorg/Skola_utbildning/MapServer/0` *Utbildning skolor* | 35    | Namn, Kommentar, Kategori                           | Punkt. Kategori: Förskola (kommunal, fristående), Grundskola, Gymnasie. Inga adressfält |
| `Intressepunkter/MapServer/0`                                        | 19    | Namn, Typ, Beskrivning, **Adress, Telefon, E_post** | Bara motionsspår och anslagstavlor; inte relevant                                       |

Ingen vård och inga byggnader i de öppna mapparna (V). `GaidaSBI/SBI_Topografi10`
("Tjänsteansvarig: Sokigo AB") är Lantmäteriets Topografi 10 och har *Militärt område*,
*Transformatorområde* och *Ledningslinje*.

**Ska uteslutas (V):** `vard_skola_omsorg/hemtjnst_team` (hemtjänstområden),
`vard_skola_omsorg/Mtesplatser` (med **adress**), `Ledning_VA/*`, `OP2050/Teknisk_forsorjning`
(kraftledning) och militärt område, transformator och ledning i Topografi 10.
`Sala_kommun/Krishantering` ("Tillfällig information i händelse av kris": vägskada,
vattennivå, översvämmad yta) är inte en del av urvalet men kan vara intressant som
händelsedata.

**Skyfall (V):**

- Kommunens `OP2050/Miljo_och_riskfaktorer/MapServer`, grupplager 21 *Skyfallskartering
  2017* med 22 *Potentiellt riskområde, djup över 1 m* (3 419 ytor) och 23 *… djup över
  0,2 m* (34 501 ytor), copyright "LstU, SMHI". Ingen WMS (400), bara ArcGIS REST.
- Länsstyrelsen Västmanlands WMS `https://ext-geodata-lokala-visning.lansstyrelsen.se/arcgis/services/LSTU/LSTU_SMHI_Skyfallskartering_ext/MapServer/WMSServer`,
  lager 0–3 (riskområde > 0,2 m och > 1 m, flödeslinjer mindre och större). En query över
  Sala tätort gav 1 322 träffar i flödeslinjerna; en GetMap visade riskområdena.
- Villkor i metadata (V): "Creative Commons Erkännande 4.0 Internationell (CC BY 4.0)" och
  "Ingen begränsning". Skyfallskartering av SMHI 2017 på uppdrag av Länsstyrelsen, "lågt
  liggande områden och potentiella flödesvägar för de centrala delarna av respektive
  tätort".

### Västerås stad

**Tjänster (V):** `https://kartor.vasteras.se/arcgis/rest/services/ext/…` (ArcGIS) och
`https://kartserver.vasteras.se/geoserver` (WFS-lagren där är bygglovsnämndens ärenden,
bostadsprognoser och transportplan, inga skyddsvärda objekt).

| Tjänst och lager                                         | Antal  | Fält                                                                    | Not                                                                                          |
| -------------------------------------------------------- | ------ | ----------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `ext/webbobjekt_dyn/FeatureServer/0` *WEBBOBJEKT_PKT*    | 1 244  | NAME, CATEGORY, PAGEID, ORGANIZATION, PROVIDER m.fl.                    | Punkt. Samhällskartans källa. Förskola 132, Grundskola 63, Gymnasieskola 18. Inga adressfält |
| `ext/buf_upptagningsomraden_skolor/MapServer/2`, `/3`    | 19, 43 | NAME, CATEGORY …                                                        | Fristående och kommunala grundskolor                                                         |
| `ext/sbf_gronskan_allt_dyn/MapServer/1` *Förskolor*      | 141    | NAME, CATEGORY …                                                        | Punkt                                                                                        |
| `ext/kommunkarta_farg_dyn/MapServer/11` *Byggnadsyta_ny* | 33 679 | 31 fält, bland dem **TAXERINGSID, TAXERINGSKOD, TAXERINGSTYP**, ANDAMAL | Yta                                                                                          |
| `ext/Matinstrument/FeatureServer/63` *Byggnader*         | 1 578  | ID, TYP, TYPKOD                                                         | Yta, bara en del av staden                                                                   |

Ingen vårdcentral (V).

**Ska uteslutas (V):** i `webbobjekt_dyn` samma punktlager, med filtret på CATEGORY:
*Boende för missbrukare* (8; samhällskartan kallar det "Boende för skadligt bruk och
beroende"), *Daglig verksamhet enligt LSS* (47), *Korttidsvistelse utanför det egna
hemmet*, *Vård- och omsorgsboende* (34; väntar som Flens särskilda boenden),
*Mötesplats-omsorg*, *Mötesplats för anhöriga* och *Pedagogisk omsorg* (dagbarnvårdare,
kan vara i ett privat hem). `ext/vof_lov_dyn` (hemsjukvård, boendestöd, daglig
verksamhet, personlig assistans, avlösare: utförarnas områden enligt LOV),
`ext/crowdsourcing_kris` (invånarnas anmälningar, se `reports/2026-10-28-forstudie-vasteras-claude-opus-5-5.md`),
`ext/sk_VMA_skyddsrum_dyn`, kraftledningar, elstolpar och transmissionsnätet i
översiktsplanerna.

**Villkor:** inga copyright- eller licenstexter i tjänsterna (V). GeoServerns WFS anger
`Fees NONE` och `AccessConstraints NONE` (V). Användaren meddelade 2026-10-28 att Techseed
får använda stadens data internt (R-GEO-05).

**Skyfall:** finns redan i övervakningen (`ext/sk_skyfall_wms`, *Maximalt vattendjup, 100
års regn*).

### Höörs kommun

**Tjänster (V):** Höör använder både ArcGIS Online (org `XcHB8YVJHmlQKJsZ`,
`https://services2.arcgis.com/XcHB8YVJHmlQKJsZ/arcgis/rest/services`) och Geoinfo
Mittskånes server (`https://karta.geoinfomittskane.se/arcgis/rest/services`, gemensam med
Hörby).

| Tjänst och lager                                                        | Antal  | Fält                                                                                                 | Not                                                   |
| ----------------------------------------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| AGOL `Skolor_i_Höörs_kommun/FeatureServer/0`                            | 36     | Namn, Skoltyp, Huvudman, **Adress, Postnr, Kontakt (telefon)**, **Creator, Editor**                  | Punkt, förskolor och skolor                           |
| AGOL `Skolor_WFL/FeatureServer/0`–`4`                                   | 36     | Som ovan                                                                                             | Samma data, uppdelad på fritids, inriktning, huvudman |
| AGOL `Byggnader_PK/FeatureServer/0`                                     | 10 770 | **ADDRESS, HOUSENUMBE, BELONGSTO, LIESON, AFFECTEDBY**, **REGSIGN, MODIFICA_1** (användarnamn) m.fl. | Yta, från primärkartan                                |
| Mittskåne `OpenData/Baskarta_Hoor_OpenData/MapServer/10` *Byggnad, yta* | 20 877 | Som ovan, bland dem **ADDRESS, HOUSENUMBER, MODIFICATIONSIGN**                                       | Yta. Copyright "(C) Höörs kommun och Lantmäteriet"    |

Ingen vård (V). Höörs del av översiktsplanen 2026 (`OP2026/…_Hr_OP2026`) ger ingen
servicepunkt för vård. Hörbys översiktsplan (`OP2035antagande/Omsorg_antagande_hby`) har
*Omsorgsverksamheter* och *Vårdcentral*, men för Hörby.

**Ska uteslutas (V):** AGOL `Särskilda_boenden_Vy/FeatureServer/0` (17 punkter: typ
som *Demensboende*, namn, **adress**, **namn och telefon till enhetschefen**; väntar som
Flens särskilda boenden, och har personuppgifter om anställda),
`OP2026/AN_Forsvar_och_beredskap_Hr_OP2026` (*Riksintresse för totalförsvaret, civil
anläggning*), `OP2026/AN_Infrastruktur_vatten_och_avlopp_Hr_OP2026`,
`OP2026/AN_Infrastruktur_energi_och_kommunikation_Hr_OP2026`, Mittskånes mappar
`MittskaneVatten`, `Gaida_VA`, `Ovrigt_VA`, `Ledningskollen`, `Adresser`,
`Fastighetskartan` och `SektorOmtanke` (namnet tyder på omsorg; innehållet inte läst).
`AGOL Fastighetslinjer_HbyHr` är fastighetsgränser.

**Villkor:** inga licenstexter i AGOL-tjänsterna (V). Mittskånes mapp `OpenData` och
appen "Öppen data i Höör" finns (V), men någon licens (t.ex. CC0) har inte hittats (O).

**Skyfall:**

- Ingen skyfallskartering för Höör hittad (V för katalogerna, O för webben).
  `OP2026/AN_Klimatrisker_Hr_OP2026` har *Ytavrinning*, *Risk för översvämning* och
  *Risk för översvämning och erosion*; innehållet är inte undersökt.
- `Skyfall2024/max_depth_combined` och `max_flux_combined` på Mittskånes server
  (maxdjup i meter och maxflöde, 2024) har utbredningen 13,56–13,89 °E, 55,75–55,94 °N
  (V, omräknat från SWEREF 99 13 30). Det är Hörby kommun; Höörs tätort (13,54 °E) ligger
  utanför. Ingen WMS (400), bara ArcGIS REST. Ingen licens angiven (V).
- Länsstyrelsen Skåne (LstM) har ingen post om skyfallskartering i geodatakatalogen (V).

### Vellinge kommun

**Tjänst (V):** `https://karta.vellinge.se/arcgis/rest/services` (ArcGIS Server 11.3).
Elva mappar kräver token, bland dem Skola, Trygghet och VELLINGE.

| Tjänst och lager                                         | Antal  | Fält                                                                                            | Not                                         |
| -------------------------------------------------------- | ------ | ----------------------------------------------------------------------------------------------- | ------------------------------------------- |
| `Extern_karta/Huvudkarta_extern/MapServer/14` *Förskola* | 24     | Namn, WIFI, URL, TYP                                                                            | Punkt, inga adressfält                      |
| `Extern_karta/Huvudkarta_extern/MapServer/13` *Skolor*   | 16     | Namn, Nivå, WIFI, URL                                                                           | Punkt                                       |
| `Emma_Extern_Översiktsplan_MIL1/MapServer/4` *Byggnader* | 49 970 | 51 fält, bland dem **ADDRESS, HOUSENUMBER, BELONGSTO, LIESON, AFFECTEDBY, NONFREEHOLDPROPERTY** | Yta                                         |
| `Emma_Extern_Översiktsplan_MIL1/MapServer/22` *Vård*     | 17     | Bara ID och area                                                                                | Ytor i översiktsplanen, utan namn eller typ |

`Huvudkarta_extern_MIL1` har samma lager som `Extern_karta/Huvudkarta_extern`. Ingen
vårdcentral (V).

**Ska uteslutas (V):** `Huvudkarta_extern/MapServer/12` *Äldreboende* (6; typ t.ex.
"vård- och omsorgsboende"; väntar som Flens särskilda boenden),
`Intern/Samhällsfunktioner` (öppen utan token trots namnet "Intern"; samma kategorier med
äldreboenden; bör inte användas eftersom namnet tyder på att den inte är avsedd för
allmänheten), `Extern_karta/Skolkarta_extern` (skolskjutsens hållplatser och linjer),
`Gaida/*Locator_Real_Estate*` (geokodning av fastigheter), *El och belysning* och
*Kabelanordning* i baskartorna.

**Villkor:** ingen copyright- eller villkorstext i tjänsterna (V). Kommunens bakgrundskarta
används redan internt efter användarens beslut 2026-11-04 (`vellingekommun.py`).

**Skyfall:** ingen skyfallskartering i de öppna tjänsterna (V). Lagren
`Skyddsvallar/MapServer/7` och `/8` (*Översvämning efter/innan skyddsvallar*) gäller
havet, inte skyfall. Kommunen har en skyfallsplan (antagen 2017, enligt sökresultat en
version 2022) med en teoretisk skyfallskartering (O); den länkade PDF:en gav 404.
Länsstyrelsen Skåne har ingen post (V).

## Bedömning mot registret

Förslag, inte beslut. Allt nedan är olöst tills kvalificerad granskning och beställarens
dataskyddsombud har sett det.

**R-DP-01 (GDPR).** Förskolor, skolor och vårdcentraler är verksamheter, inte personer. Med
bara namn och plats (som i Flen) bedöms risken som låg, men frågan är öppen. Tre saker är
nya jämfört med Flen:

- Västerås har *Boende för skadligt bruk och beroende* och LSS-verksamheter i samma lager
  som förskolorna. Plats och typ kan avslöja uppgifter om hälsa (artikel 9) om de
  kombineras med vem som bor eller vistas där. Ett filter på CATEGORY räcker tekniskt, men
  ett fel i filtret hämtar dem. Ett förslag är att filtrera på tillåtna kategorier
  (vitlista), inte på uteslutna.
- *Anpassad grundskola/gymnasieskola* (Västerås) och *Pedagogisk omsorg* (dagbarnvårdare,
  möjligen i ett privat hem) är inte prövade i Flen.
- Byggnads- och skollager har användarnamn (Höör, Sundsvall) och kontaktuppgifter (Höör).
  Med bara geometri och namnfält hämtas de inte.

**R-CS-06 och R-CS-07 (säkerhetsskydd och skyddsobjekt).** Ingen av de föreslagna
kategorierna är en sådan anläggning som 4 och 5 §§ skyddslagen räknar upp. Uteslutna:
VA, el, reningsverk, skyddsrum, brandstationer, totalförsvarets riksintresse (Höör) och
militärt område (Topografi 10, Sala). Sammanställningsrisken (förskolor, skolor och
byggnader i flera kommuner i ett system) är inte bedömd och beror på B-KUND och B-ANV.

**R-GEO-02 (lag 2016:319).** Kommunernas punktlager och byggnader är inte inhämtade från
luftfartyg i sig, men byggnadsytor i primärkartor kan vara karterade från flygbilder (O).
Intern användning är inte spridning enligt 9 §. Gäller om något visas utåt.

**R-GEO-05 (villkor per källa).**

| Källa                                       | Villkor funnet                                                         |
| ------------------------------------------- | ---------------------------------------------------------------------- |
| Sundsvall, GeoServer                        | Bara fem kommuner om inget annat avtalas (V)                           |
| Västerås                                    | Inget i tjänsterna; internt ok enligt användaren 2026-10-28            |
| Sala                                        | Inget i tjänsterna                                                     |
| Höör, AGOL och Mittskåne                    | "(C) Höörs kommun och Lantmäteriet" i OpenData-baskartan; annars inget |
| Vellinge                                    | Inget i tjänsterna                                                     |
| Kramfors, Ljusdal                           | Ingen publik tjänst                                                    |
| Länsstyrelsen Västernorrland, skyfall       | CC0 1.0 (V)                                                            |
| Länsstyrelsen Västmanland och SMHI, skyfall | CC BY 4.0 (V)                                                          |
| Mittskåne Skyfall 2024 (Hörby)              | Inget angivet                                                          |

Ingen kommun hade en hittad förklaring om öppna data enligt lag (2022:818) för just
dessa lager (O; kort sökning). SKR:s PM säger att kommuner får ta ut avgift för geodata
de lämnar ut på eget initiativ. Att en tjänst är öppen utan token är inte samma sak som en
licens.

## Förslag till beslut

Förslag, inte beslut. "Efter DSO" = efter beställarens dataskyddsombud och kvalificerad
granskning.

| Kommun    | Förskolor och skolor från GIS                                   | Vård från GIS                               | Byggnader från GIS              | Skyfallslager                                                                       |
| --------- | --------------------------------------------------------------- | ------------------------------------------- | ------------------------------- | ----------------------------------------------------------------------------------- |
| Sundsvall | Efter DSO och efter att villkoret om fem organisationer är löst | Efter DSO (vårdcentraler)                   | Efter DSO, bara geometri        | Finns redan                                                                         |
| Kramfors  | Nej, ingen publik tjänst                                        | Nej                                         | Nej (Solay-lagret kräver avtal) | Ja, LstY:s lågpunkter och rinnvägar (CC0), märkt som indikator                      |
| Ljusdal   | Nej, ingen publik tjänst                                        | Nej                                         | Nej                             | Nej, inget hittat                                                                   |
| Sala      | Efter DSO                                                       | Nej, inget lager                            | Nej, inget öppet lager          | Ja, LstU:s och SMHI:s WMS (CC BY 4.0)                                               |
| Västerås  | Efter DSO, med vitlista på CATEGORY                             | Nej, inget lager                            | Efter DSO, bara geometri        | Finns redan                                                                         |
| Höör      | Efter DSO, utan adress- och kontaktfält                         | Nej, inget lager                            | Efter DSO, bara geometri        | Nej för Höör; Hörbys *Skyfall 2024* bara om användaren vill visa grannkommunens del |
| Vellinge  | Efter DSO                                                       | Nej (översiktsplanens vårdytor saknar namn) | Efter DSO, bara geometri        | Nej, inget publicerat                                                               |

Frågor till användaren:

1. Ska Länsstyrelsens lågpunktskarteringar (Kramfors, Sala) visas, fast de är
   topografiska analyser och inte skyfallsmodeller som Sundsvalls och Västerås?
2. Ska Sundsvall frågas om ett avtal, eller räcker godkännandet 2026-10-06 för
   övervakningen? Samma fråga gäller Solay-lagret för Kramfors.
3. Ska frågan till dataskyddsombudet omfatta alla sju kommunerna på en gång, med listan
   över kategorier som ska uteslutas?
4. Ska kommunerna själva tillfrågas om villkor där tjänsterna inte anger några (Sala,
   Höör, Vellinge)?

## Inte bekräftat

- Om Sundsvalls godkännande 2026-10-06 täcker punktlagren i övervakningen.
- Kramfors och Ljusdals Sokigo-tjänstnamn för `/wms`; det kan finnas lager som inte
  hittades.
- Om Vellinges skyfallskartering finns som karta eller tjänst; skyfallsplanens PDF gav 404.
- Om Ljusdal eller Länsstyrelsen Gävleborg har en kartering som inte står i
  geodatakatalogen.
- Innehållet i Höörs `AN_Klimatrisker_Hr_OP2026` (*Ytavrinning*) och i Mittskånes mapp
  `SektorOmtanke`.
- Om byggnadsytorna i kommunernas primärkartor bygger på flygbilder (R-GEO-02).
- Om någon kommun har en licens för öppna data för lagren ovan.
- Hur aktuella lagren är; flera Västerås-poster har AKTUALITETSDATUM i maj 2024.

## Källor

- Sundsvall, WMS och WFS: https://karta.sundsvall.se/geoserver/wms?service=WMS&version=1.3.0&request=GetCapabilities,
  https://karta.sundsvall.se/geoserver/ows?service=WFS&version=1.1.0&request=GetCapabilities
- Västerås, ArcGIS: https://kartor.vasteras.se/arcgis/rest/services/ext?f=json,
  https://kartor.vasteras.se/arcgis/rest/services/ext/webbobjekt_dyn/FeatureServer/0
- Västerås, samhällskartan: https://kartor.vasteras.se/sam/vas.json
- Västerås, GeoServer: https://kartserver.vasteras.se/geoserver/ows?service=WFS&version=2.0.0&request=GetCapabilities
- Sala, ArcGIS: https://geodata.sala.se/arcgis/rest/services?f=json,
  https://geodata.sala.se/arcgis/rest/services/vard_skola_omsorg/Skola_utbildning/MapServer/0,
  https://geodata.sala.se/arcgis/rest/services/OP2050/Miljo_och_riskfaktorer/MapServer
- Vellinge, ArcGIS: https://karta.vellinge.se/arcgis/rest/services?f=json,
  https://karta.vellinge.se/arcgis/rest/services/Extern_karta/Huvudkarta_extern/MapServer
- Höör, ArcGIS Online: https://www.arcgis.com/sharing/rest/search?q=orgid:XcHB8YVJHmlQKJsZ&num=100&f=json,
  https://services2.arcgis.com/XcHB8YVJHmlQKJsZ/arcgis/rest/services
- Höör, Galleriet: https://galleriet-hoor.hub.arcgis.com
- Geoinfo Mittskåne: https://karta.geoinfomittskane.se/arcgis/rest/services?f=json,
  https://karta.geoinfomittskane.se/arcgis/rest/services/Skyfall2024/max_depth_combined/MapServer
- Kramfors: https://map.kramfors.se/ ; Ljusdal: https://kommunkarta.ljusdal.se/
- Länsstyrelsernas geodatakatalog (CSW): https://ext-geodatakatalog.lansstyrelsen.se/GeodataKatalogen/srv/swe/csw
- LstY Skyfallskartering Kramfors lågpunkter, metadata: https://ext-geodatakatalog.lansstyrelsen.se/GeodataKatalogen/srv/api/records/4c5b0141-1074-408f-b976-e837a34321a1
- LstY Skyfall, WMS: https://ext-geodata-lokala-visning.lansstyrelsen.se/arcgis/services/LSTY/LstY_Skyfall_ext/MapServer/WMSServer?service=WMS&request=GetCapabilities
- LstY, dokumentation: http://ext-dokument.lansstyrelsen.se/Vasternorrland/Dokumentarkiv/Skyfallskartering/Skyfallskartering_dokumentation_vasternorrland.pdf
- LstU Skyfallskartering WMS, metadata: https://ext-geodatakatalog.lansstyrelsen.se/GeodataKatalogen/srv/api/records/0694543a-890a-46dc-9976-8509df835c2c
- LstU och SMHI, WMS: https://ext-geodata-lokala-visning.lansstyrelsen.se/arcgis/services/LSTU/LSTU_SMHI_Skyfallskartering_ext/MapServer/WMSServer?service=WMS&request=GetCapabilities
- LstU, rapport om lokal ytavrinning: https://ext-dokument.lansstyrelsen.se//Vastmanland/Dokumentarkiv/klimatanpassning/Rapport_Lokal_ytavrinning_V%C3%A4stmanland_v1_1.pdf
- Länsstyrelsen Gävleborg, utredning om skyfallen i augusti 2021: https://www.lansstyrelsen.se/download/18.74b418a31817ff11b11152a4/1656404563637/Utredning%20av%20skyfall%20och%20%C3%B6versv%C3%A4mningar%20i%20G%C3%A4vleborgs%20l%C3%A4n,%20augusti%202021.pdf
- Ljusdal, översvämningsutredning Stavsätter: https://ljusdal.se/download/18.146d4cbb193c612dd1fc07cb/1734514982808/%C3%96versv%C3%A4mningsutredning%20Stavs%C3%A4tter_Bilaga%20C.pdf
- Vellinge, skyfallsplan (404 vid kontroll): https://vellinge.se/siteassets/kommun-och-politik/pdf/styrdokument/pdf/skyfallsplan.pdf
- Vellinge, PM dagvatten 2023 som hänvisar till skyfallskarteringen: https://www.vellinge.se/siteassets/planer-och-projekt-i-vellinge-kommun/dokument/kampinge-9-26-mfl/samrad/pm-dagvatten-2023-03-02.pdf
- Länsstyrelsen Skåne, öppna data: https://www.lansstyrelsen.se/skane/om-oss/vara-tjanster/oppna-data.html
- SKR, kommunernas geodata och öppna data-lagstiftningen: https://skr.se/download/18.50f9e076199f78d209552db5/1761056353219/kommunernasgeodata-och-oppna-datalagstiftningen.pdf
- Repo: `app/monitoring/areas/*.py`, `app/monitoring/gis.py`, `docs/mvp/regelverksregister.md`,
  `CONTEXT.md`, `reports/2026-10-06-datakallor-oversvamning-sundsvall-claude-opus-5-5.md`,
  `reports/2026-10-28-forstudie-vasteras-claude-opus-5-5.md`
