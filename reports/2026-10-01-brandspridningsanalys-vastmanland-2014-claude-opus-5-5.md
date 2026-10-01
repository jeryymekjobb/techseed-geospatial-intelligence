# Går det att prognostisera brandens spridning? Efterhandstest på Västmanland 2014

Datum: 2026-10-01
Författare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code, på uppdrag av
Techseed. Analysen är en teknisk undersökning för demonstratorn. Den är inte ett
beslutsunderlag för räddningstjänst och inte en bedömning av hur branden faktiskt
hanterades.

## Fråga

Kan en prognos som uppdateras med satellitdetektioner och väder bedöma åt vilket
håll och hur fort branden sprider sig, och med vilken säkerhet kan man säga när
brandfronten når bebyggelse, vägar och järnväg?

## Kort svar

- **Riktning: ja, när branden löper med vinden.** Vid de nio intervall där fronten
  flyttade sig minst 1 km var medianfelet mellan observerad spridningsriktning och
  vindens riktning 10°. Vid svag vind, nattetid och i små förflyttningar var felet
  i median 71°. Riktningen är alltså användbar under de skeden som är farliga,
  men inte under lugna skeden.
- **Hastighet: bara grovt.** Den kanadensiska spridningsmodellen (FBP, boreal
  barrskog) gav i median ungefär halva den observerade hastigheten med SMHI:s
  väder, och under brandens värsta timmar den 4 augusti hälften till en
  sjundedel. Med ERA5-Lands modellväder var underskattningen upp till 50 gånger,
  eftersom modellens regn gav för lite torka.
- **Ankomsttid: bara som intervall, och med låg precision.** När fronten faktiskt
  nådde ett mål inom 24 timmar låg prognosens troliga värde inom satelliternas
  observationsfönster i 13–15 % av fallen. Utanför fönstret var medianfelet
  2,6 timmar. Intervallet halva–dubbla hastigheten överlappade fönstret i
  60–66 % av fallen. Samtidigt pekade prognosen ut många mål som inte nåddes inom
  24 timmar. En bedömning av typen "Ängelsberg om 10 timmar" går inte att ge med
  säkerhet. "Fronten rör sig mot nordväst, mål inom 5–10 km i den riktningen kan
  nås inom ett halvt till ett dygn" går att ge.
- **Den största enskilda osäkerheten är vädret som går in i modellen,** inte
  själva spridningsmodellen. SMHI:s mätningar från Sala A gav extrem torka
  (uppbyggnadsindex BUI 78–97, FWI 28 den 4 augusti). ERA5-Land gav måttlig torka
  (BUI 31–43, FWI 12), eftersom modellen gav regn som stationerna inte uppmätte.

## Underlag

| Data | Källa | Upplösning |
|---|---|---|
| Branddetektioner | NASA FIRMS, MODIS C6.1 och VIIRS S-NPP C2 (`satellite_data/firms/`) | 1 km respektive 375 m, 39 satellitpassager 31 juli–10 augusti |
| Väder, alternativ A | ERA5-Land, punkt 59,9° N 16,2° E, 1 maj–14 augusti (`weather_data/era5-land/`) | 0,1°, varje timme, modell |
| Väder, alternativ B | SMHI Sala A (96560), 1 maj–14 augusti (SMHI:s arkiv) | station 29 km öster om branden, varje timme, mätning |
| Mål | OpenStreetMap: orter, byggnader, vägar, järnväg (`osm_data/`) | dagens läge, inte 2014 |

## Metod

1. **Brandfronten** vid varje satellitpassage är det konvexa höljet kring alla
   detektioner dittills. Det är en förenkling. Verkliga brandområden har öar och
   flikar, och detektionerna täcker inte varje bränd pixel.
2. **Observerad spridning** mellan två passager är 90-percentilen av avståndet
   från det förra höljet till nya detektioner utanför det, delat med tiden.
   Riktningen är det avståndsviktade medelvärdet av de nya detektionernas läge.
   Intervall under 1,5 timmar räknas inte med vid kalibreringen, eftersom en
   passage strax efter en annan satellit ser det som brann under en tidigare
   lucka.
3. **Brandväder:** det kanadensiska Fire Weather Index-systemet (Van Wagner 1987)
   med timvis finbränslefukt (Van Wagner 1977), inkört från 1 maj med
   standardvärdena 85/6/15. Implementationen ger exakt referensfallet i
   Van Wagner och Pickett (1985).
4. **Spridningsmodell:** FBP C-2 (boreal granskog) för huvudbrand och bakbrand,
   elliptisk form ur vindhastigheten och tillväxt timme för timme från varje
   hörn av fronten. Modellhastigheten kalibreras vid varje prognos med medianen
   av kvoten observerad/modell för de senaste 24 timmarna (begränsad till
   0,1–10). Låg, trolig och hög prognos är halva, en och dubbla den kalibrerade
   hastigheten. Bränslet antas vara barrskog överallt.
5. **Efterhandstest:** prognoser för 3, 6, 12 och 24 timmar görs vid varje
   passage med data fram till dess, och jämförs med senare detektioner. Två
   vädersätt prövas: *rådande väder ligger kvar* (realistiskt) och *facit* (det
   väder som faktiskt kom, vilket ingen hade då).
6. **Ankomst:** målen läggs i rutor på 500 m. En ruta räknas som nådd när en
   detektion ligger inom 750 m. Observationsfönstret är tiden mellan den senaste
   passagen som inte såg branden där och den första som gjorde det.

## Resultat

### Brandväder 31 juli–5 augusti

| Dygn | DC ERA5-Land | BUI ERA5-Land | FWI ERA5-Land | Regn ERA5-Land, mm | DC SMHI | BUI SMHI | FWI SMHI | Regn SMHI, mm |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 31 juli | 323 | 35 | 11,4 | 0,7 | 418 | 78 | 7,1 | 8,6 |
| 1 aug | 330 | 39 | 13,3 | 0,4 | 425 | 81 | 16,0 | 0 |
| 2 aug | 337 | 43 | 13,0 | 0 | 433 | 86 | 17,9 | 0 |
| 3 aug | 332 | 31 | 0,7 | 5,0 | 440 | 88 | 13,6 | 0,6 |
| 4 aug | 340 | 37 | 11,8 | 0 | 450 | 94 | 28,1 | 0 |
| 5 aug | 348 | 38 | 2,0 | 1,6 | 457 | 97 | 19,3 | 0 |

Regn avser 24 timmar till kl. 11 UTC. Regnet vid Sala A den 31 juli kom den
30 juli på kvällen. Båda källorna visar mycket torr mark (DC över 300), men
ERA5-Land ger mindre torka i de övre lagren och regn den 3 augusti som stationen
inte uppmätte.

### Observerad spridning och vind (SMHI-väder)

| Intervall (UTC) | Timmar | Framflyttning, m | Observerad, m/h | Riktning | Vinden mot | Modell, m/h |
|---|---:|---:|---:|---:|---:|---:|
| 31 juli 12:44– | 6,9 | 2 582 | 375 | 49° | 58° | 154 |
| 1 aug 12:25– | 7,9 | 1 694 | 214 | 59° | 58° | 461 |
| 2 aug 12:06– | 7,3 | 3 531 | 483 | 314° | 6° | 251 |
| 3 aug 12:21– | 7,8 | 1 490 | 191 | 310° | 320° | 55 |
| 4 aug 11:13– | 1,9 | 2 180 | 1 128 | 312° | 310° | 400 |
| 4 aug 13:09– | 6,1 | 6 072 | 1 001 | 324° | 327° | 451 |
| 4 aug 19:13– | 1,6 | 3 114 | 1 906 | 330° | lugnt | 276 |

Branden gick först mot nordost (31 juli–1 augusti, sydvästlig vind) och vände
sedan mot nordväst med sydostlig vind (2–4 augusti). Den 4 augusti flyttade sig
fronten 1–2 km i timmen.

### Prognosytan jämfört med senare detektioner

Andel nya detektioner (utanför fronten vid prognosen) som låg inom prognosytan,
median över prognoserna, och kvoten prognostiserad/observerad tillväxt i yta.

| Väder | Horisont | Antal prognoser | Inom låg | Inom trolig | Inom hög | Yta trolig/observerad |
|---|---:|---:|---:|---:|---:|---:|
| SMHI, rådande väder | 3 h | 5 | 12 % | 62 % | 100 % | 1,9 |
| SMHI, rådande väder | 6 h | 6 | 60 % | 92 % | 100 % | 2,8 |
| SMHI, rådande väder | 12 h | 16 | 59 % | 88 % | 100 % | 2,9 |
| SMHI, rådande väder | 24 h | 30 | 78 % | 98 % | 100 % | 4,1 |
| ERA5-Land, rådande väder | 6 h | 6 | 20 % | 68 % | 89 % | 1,4 |
| ERA5-Land, rådande väder | 12 h | 16 | 50 % | 80 % | 100 % | 1,7 |
| ERA5-Land, rådande väder | 24 h | 30 | 76 % | 100 % | 100 % | 4,0 |

Prognoserna fångar för det mesta var branden tar vägen, men ytan blir två till
fyra gånger större än den som brann. En hög träffandel betyder därför delvis bara
att prognosen täcker ett stort område. Antalet prognoser för 3 och 6 timmar är
litet, eftersom det sällan kom en ny passage med nya detektioner så snart.

### Ankomsttider till mål

Par av prognos och målruta där fronten nådde målet inom 24 timmar efter
prognosen, rådande väder:

| Väder | Mål | Nådda inom 24 h | Trolig inom 24 h | Trolig inom fönstret | Medianfel utanför fönstret | Låg–hög överlappar fönstret | Utpekade men inte nådda |
|---|---|---:|---:|---:|---:|---:|---:|
| SMHI | orter | 171 | 130 (76 %) | 25 (15 %) | 2,6 h | 102 (60 %) | 4 197 |
| SMHI | byggnader | 258 | 199 (77 %) | 36 (14 %) | 2,6 h | 159 (62 %) | 6 800 |
| ERA5-Land | orter | 171 | 141 (82 %) | 23 (13 %) | 2,6 h | 111 (65 %) | 2 179 |
| ERA5-Land | byggnader | 258 | 216 (84 %) | 36 (14 %) | 2,9 h | 169 (66 %) | 3 630 |

Observationsfönstret var i median 1,6 timmar. Exempel: prognosen vid passagen
4 augusti 09:35 UTC. Ett 20-tal namngivna platser nordväst om fronten nåddes
mellan cirka 19 och 21 UTC samma dag (9,6–11,3 timmar senare), bland andra
Gärsjötorp, Fattasbo, Holmen, Skrampbo och Ängelsberg (detektion inom 750 m av
ortens punkt i OSM, inte nödvändigtvis bebyggelsen). Den troliga prognosen gav för de
flesta 10–18 timmar eller ingen ankomst inom ett dygn. Bara den höga prognosen
(dubbla hastigheten) kom nära. Modellen var alltså för långsam just den dag då
det gick som fortast.

## Begränsningar

- **Satelliterna ser branden några gånger per dygn.** Luckorna mellan passager
  var upp till 6 timmar på dagen den 4 augusti och över 8 timmar natt till dag.
  Ankomsten till ett mål är därför bara känd inom ett fönster. Fönstren här
  förutsätter att varje passage hade sett branden om den fanns, vilket moln, rök
  och satellitens bildbredd inte garanterar. De verkliga fönstren är bredare.
- **Detektionerna täcker inte allt som brann.** "Utpekade men inte nådda" är
  därför överskattat, och yta och ankomst bedöms mot en ofullständig bild. Ett
  bättre facit är den kartlagda brandgränsen (till exempel från EFFIS eller
  myndigheternas egna kartor) eller brandspår i Landsat-bilder.
- **Brandfronten som konvext hölje** fyller i obrända områden innanför och gör
  fronten för slät.
- **Bränsle och terräng:** all mark behandlas som barrskog. Sjöar, myrar, åker
  och vägar som bromsar branden finns inte med, och inte heller lutning.
- **Brandens eget väder, flygbränder och släckinsatser** finns inte med.
  Kraftig spridning som den 4 augusti, med kronbrand och flygbränder, underskattas
  av modellen.
- **Vädret:** en station 29 km bort eller en modell med 9 km upplösning. Med
  rådande väder framåt finns ingen förändring av vinden med. Facitläget visar
  vad en perfekt väderprognos skulle ge, och den skillnaden är liten här.
- **Målen är dagens OSM,** inte bebyggelsen 2014.

## Slutsatser för demonstratorn

1. **Visa riktning och skede, inte exakta klockslag.** En pil för observerad
   spridning mellan passager, med hastighet i km/h, och en prognosyta som visar
   spannet halva–dubbla hastigheten är försvarbart. En lista med exakta
   ankomsttider är det inte.
2. **Mät vädret där det går.** Brandvädret skilde sig mer mellan SMHI och
   ERA5-Land än mellan prognos och facit. För brandvädret är stationsmätningar
   bättre än ERA5-Land här. För vindens rumsliga fält är ERA5-Land användbart.
3. **Kalibrera kontinuerligt mot satelliterna.** Utan kalibrering missar modellen
   den 4 augusti helt. Med kalibrering och det höga spannet kommer den nära.
4. **Märk prognosen tydligt** som modellbedömning med stor osäkerhet, och visa
   observationsluckorna (tid sedan senaste passage) i gränssnittet.
5. **Nästa förbättring** vore bränsle och hinder ur marktäckesdata (myrar, sjöar,
   åker) och en brandgräns som facit, så att yta och ankomst kan bedömas
   rättvisare.

## Reproducera

```bash
python3 -m tools.fire_spread_analysis --weather weather_data/era5-land/era5-land-fwi-spinup-2014.csv weather_data/era5-land/era5-land-vastmanland-2014.csv --targets osm_data/targets-vastmanland.geojson --out data/fire-spread-analysis.json
python3 -m tools.fire_spread_analysis --weather-smhi <katalog med SMHI-arkiv> --targets osm_data/targets-vastmanland.geojson --out data/fire-spread-analysis-smhi.json
```

SMHI-arkiven hämtas med `tools/fetch_smhi_weather.py ... --raw-dir <katalog>`
(hela arkivet för Sala A, parametrarna 1, 3, 4, 6 och 7). Resultatfilerna i
`data/` versionshanteras inte.

## Källor

- Van Wagner, C. E. (1987). Development and structure of the Canadian Forest Fire
  Weather Index System. Canadian Forestry Service, Forestry Technical Report 35.
- Van Wagner, C. E. (1977). A method of computing fine fuel moisture content
  throughout the diurnal cycle. Canadian Forestry Service, Information Report
  PS-X-69.
- Van Wagner, C. E. och Pickett, T. L. (1985). Equations and FORTRAN program for
  the Canadian Forest Fire Weather Index System. Forestry Technical Report 33.
- Forestry Canada Fire Danger Group (1992). Development and structure of the
  Canadian Forest Fire Behavior Prediction System. Information Report ST-X-3.
- MSB, Olycksutredning skogsbrand Västmanland, Dnr 2014/336.
- NASA FIRMS, SMHI öppna data, Copernicus Climate Change Service (ERA5-Land),
  OpenStreetMap; se README-filerna i respektive datakatalog.
