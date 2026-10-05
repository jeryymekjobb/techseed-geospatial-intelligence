# Kan AI förbättra brandprognosen? Bedömning för demonstratorn

Datum: 2026-10-05
Författare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code, på uppdrag av
Techseed. Bedömningen gäller brandspridningsprognosen i demonstratorn för
Västmanland 2014. Den är inte ett beslutsunderlag för räddningstjänst.

## Fråga

Kan prognosen för brandens spridning (`app/backend/forecast.py`,
`tools/fire_spread.py`) förbättras med AI, och i så fall på vilket sätt?

## Kort svar

Ja, men den största vinsten finns i **bättre indata** och i att låta
**satellitdetektionerna rätta modellen löpande**, inte i att ersätta fysikmodellen
med en AI-modell. En ren AI-modell för spridningen kan inte tränas och prövas
trovärdigt med en enda brand. Rekommendationen är datassimilering med ett
ensemble-Kalmanfilter (väg 1), eventuellt kompletterad med bättre fysik för
kronbrand (väg 3). Varje förbättring ska prövas med samma efterhandstest som den
nuvarande prognosen, så att förbättringen kan visas och inte bara påstås.

## Dagens prognos

- **Spridningshastighet:** det kanadensiska Fire Behavior Prediction System, FBP
  (Forestry Canada 1992), bränsletyp C-2 (boreal granskog).
- **Bränslets torrhet och vindens effekt:** det kanadensiska Fire Weather
  Index-systemet, FWI (Van Wagner 1987), med väder från SMHI Sala A. Vädret vid
  satellitpassagen antas gälla framåt.
- **Form:** varje punkt på brandfronten (skalet runt alla FIRMS-detektioner
  hittills) växer som en ellips i vindriktningen, med längd mot bredd enligt FBP.
- **Kalibrering:** spridningshastigheten skalas med medianen av kvoten observerad
  mot modellerad spridning de senaste 24 timmarna. Spannet är halva till dubbla
  den kalibrerade hastigheten.

## Var felen finns

Ur efterhandstestet
(`reports/2026-10-01-brandspridningsanalys-vastmanland-2014-claude-opus-5-5.md`):

1. **Vädret som går in i modellen är den största osäkerheten.** SMHI:s mätningar
   gav extrem torka (BUI 78–97, FWI 28 den 4 augusti). ERA5-Land gav måttlig torka
   (BUI 31–43, FWI 12), eftersom modellen gav regn som stationen inte uppmätte. Med
   ERA5-Land underskattades hastigheten upp till 50 gånger.
2. **Skiftet till kronbrand fångas inte.** Den 4 augusti flyttade sig fronten
   1–2 km i timmen. Modellen gav en halv till en sjundedel av det. Den förenklade
   FBP-beräkningen använder inte FBP:s regler för när en markbrand blir kronbrand.
3. **Bränslet antas vara barrskog överallt.** Myrar, sjöar och åker bromsar inte
   branden i modellen.
4. **Spannet är fast och för brett.** Prognosytan blev två till fyra gånger större
   än den yta som brann. En hög träffandel betyder därför delvis bara att ytan är
   stor.

Riktningen är däremot bra när branden drivs av vinden: medianfelet mot vindens
riktning var 10° vid de nio intervall där fronten flyttade sig minst 1 km.

## Fyra vägar

| Väg | Innehåll | Angriper | Bedömning |
|---|---|---|---|
| **1. Datassimilering** | Ett ensemble-Kalmanfilter kör många varianter av prognosen med olika hastighet, riktning och väder. Vid varje satellitpassage vägs varianterna mot var branden faktiskt syns, och osäkerheten krymper eller växer efter hur väl modellen träffar. | Fel 4, och delvis 1 och 2, eftersom systematiska fel rättas löpande | **Rekommenderas först.** Förklarbart, beprövat för bränder i forskningen och möjligt att pröva mot efterhandstestet. Ersätter den enkla kalibreringen och det fasta spannet. |
| **2. AI för bättre indata** | Bränslekarta ur Landsat- eller Sentinel-bilder (maskininlärd klassning av skogstyp och täthet), fuktindex för vegetationen (NDMI) och väderdata nedskalad med AI. | Fel 1 och 3 | Angriper de största felkällorna. NDMI ur Landsat är en första byggsten och planerad i demonstratorn. En bränslekarta kräver mer arbete och data. |
| **3. Bättre fysik för kronbrand** | FBP:s regler för kronbrand (kritisk intensitet och andel bränd krona) i stället för bara markbrandens hastighet. | Fel 2 | Inte AI, men troligen den mest direkta åtgärden för den 4 augusti. Kan kombineras med väg 1. |
| **4. En ren AI-modell för spridningen** | Ett neuralt nät som förutsäger nästa dags brandyta ur väder, bränsle, terräng och tidigare detektioner. Sådana modeller finns i forskningen, tränade på tusentals bränder från bland annat Nordamerika. | Allt, i teorin | **Inte trovärdigt med den data som finns.** Västmanland 2014 är en enda brand och måste vara testfallet. En modell som tränas på den ser bra ut i demon men bevisar ingenting. Kräver en stor träningsmängd från andra bränder och är ett eget projekt. |

**Språkmodeller** är inte rätt verktyg för själva prognosen. De passar till att
förklara prognosen och evidensen i text, i linje med demonstratorns spårbara
bedömning.

## Rekommendation

1. **Väg 1, datassimilering**, prövad med efterhandstestet mot dagens kalibrering.
   Upplägget beskrivs i
   `reports/2026-10-05-plan-datassimilering-brandprognos-claude-opus-5-5.md`.
2. **Väg 3, kronbrand**, som nästa steg om felet den 4 augusti kvarstår efter väg 1.
3. **Väg 2** stegvis: först NDMI ur Landsat, sedan bränsle ur marktäckesdata
   (myrar, sjöar, åker) innan en maskininlärd bränslekarta.
4. **Väg 4** bara som ett separat forskningsprojekt med träningsdata från många
   bränder.

## Begränsningar

- Bedömningen bygger på efterhandstestet för en enda brand. Hur mycket varje väg
  förbättrar prognosen är inte prövat.
- Uppgifterna om AI-modeller och datassimilering för bränder i forskningen är
  allmänna. De har inte granskats i detalj för den här rapporten.
