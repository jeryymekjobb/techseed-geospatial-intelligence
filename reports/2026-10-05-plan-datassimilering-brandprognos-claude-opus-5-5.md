# Plan: datassimilering för brandprognosen (väg 1)

Datum: 2026-10-05
Författare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code.
Underlag: `reports/2026-10-05-ai-forbattring-brandprognos-claude-opus-5-5.md` och
`reports/2026-10-01-brandspridningsanalys-vastmanland-2014-claude-opus-5-5.md`.
Status: Förslag. Inget är byggt.

## Mål

Ersätta dagens enkla kalibrering (median av observerad mot modellerad hastighet de
senaste 24 timmarna) och det fasta spannet halva–dubbla hastigheten med ett
**ensemble-Kalmanfilter** som rättar prognosen vid varje satellitpassage och ger
ett osäkerhetsband som växer eller krymper efter hur väl modellen träffar.

Målet är uppnått om efterhandstestet visar att den nya prognosen är **minst lika
träffsäker med en mindre prognosyta**, eller **mer träffsäker med samma yta**, än
dagens. Om den inte är det dokumenteras resultatet och dagens prognos behålls.

## Upplägg

### Ensemble

- **Medlemmar:** 50 varianter av prognosen (antalet prövas i känslighetsanalysen).
- **Det som skattas** för varje medlem:
  - en **hastighetsfaktor** `k` (logaritmerad) som multiplicerar FBP-hastigheten,
  - en **riktningsförskjutning** `δ` i grader mot vindens riktning.
- **Startfördelning,** bestämd i förväg: `log k` normalfördelad med medelvärde 0
  och standardavvikelse 0,7 (ungefär en faktor två), `δ` normalfördelad med
  medelvärde 0° och standardavvikelse 20°.
- **Modellsteget** är dagens: FBP C-2 och FWI med SMHI-väder, ellipsformad
  tillväxt timme för timme från fronten. Varje medlem använder sina egna `k` och
  `δ`.
- **Processbrus:** `log k` och `δ` får ett litet extra brus mellan passagerna, så
  att ensemblen kan följa när branden ändrar beteende, till exempel övergången
  till kronbrand den 4 augusti.

### Uppdatering vid varje passage

- **Observation:** den observerade framflyttningen (meter) och riktningen (grader)
  mellan passagerna, beräknade som i efterhandstestet (`observed_intervals`).
  Riktningen används bara när fronten flyttat sig minst 1 km.
- **Observationsfel,** bestämda i förväg: framflyttning 500 m eller 30 %, det
  största, och riktning 20°. FIRMS-pixlarna är 375 m (VIIRS) och 1 km (MODIS).
- **Uppdatering:** standardformeln för ensemble-Kalmanfiltret med störda
  observationer, på parametrarna `log k` och `δ`.

### Prognosen som visas

- Varje medlem ger en front för 3, 6, 12 och 24 timmar.
- I stället för låg, trolig och hög visas **andelen medlemmar som når en punkt**,
  som konturer för 10 %, 50 % och 90 %. De märks "andel modellvarianter", inte
  "sannolikhet", tills efterhandstestet visar att andelarna stämmer.

## Utvärdering

Samma efterhandstest som för dagens prognos, med data fram till varje passage och
facit från senare detektioner:

| Mått | Dagens prognos | Ny prognos |
|---|---|---|
| Andel nya detektioner inom ytan, per horisont | ur rapporten 2026-10-01 | 10 %, 50 % och 90 %-konturen |
| Prognostiserad mot observerad yta | 1,9–4,1 (trolig) | per kontur |
| Ankomst: intervallet överlappar observationsfönstret | 60–66 % | samma mått |
| Riktningsfel vid framflyttning över 1 km | median 10° | samma mått |
| Tillförlitlighet | – | stämmer andelen nya detektioner inom 90 %-konturen med ungefär 90 %? |

**Inga parametrar justeras mot resultatet.** Startfördelning, observationsfel,
processbrus och antal medlemmar bestäms enligt ovan innan testet körs. En separat
känslighetsanalys visar hur resultatet beror på dem, men används inte för att
välja de värden som redovisas.

## Steg

Varje steg får ett eget GO och en egen commit.

1. **Filtret** i ett nytt verktyg, `tools/fire_ensemble.py`, med tester på en
   påhittad brand där det rätta svaret är känt: filtret ska hitta en känd
   hastighetsfaktor och riktning.
2. **Efterhandstestet** för Västmanland 2014, jämfört med dagens prognos, och en
   daterad rapport med resultatet, även om det blir sämre.
3. **Beslut:** om den nya prognosen är bättre byggs den in i `forecast.py`, i
   kartorna och i bedömningen, med uppdaterad dokumentation. Annars behålls
   dagens prognos och rapporten förklarar varför.

Grov uppskattning av arbetet: steg 1 en dag, steg 2 en halv dag, steg 3 en dag.

## Risker och begränsningar

- **En enda brand.** Även ett gott resultat visar bara att metoden fungerar här,
  inte att den fungerar generellt.
- **Glesa observationer.** Passagerna kommer ofta med 6–8 timmars mellanrum, så
  filtret har få tillfällen att rätta sig.
- **Grov front.** Fronten är skalet runt alla detektioner och följer inte bukter
  i brandgränsen.
- **Beräkningstid.** 50 medlemmar gånger 24 timsteg för 38 passager räknas i
  förväg, som dagens prognos. Tiden mäts i steg 1.
- **Vädret rättas inte direkt.** Filtret kompenserar systematiska fel genom `k`,
  men ett väderfel som ändras snabbt fångas först vid nästa passage.
