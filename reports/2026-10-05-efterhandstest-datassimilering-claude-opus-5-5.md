# Efterhandstest: datassimilering mot dagens prognos, Västmanland 2014

Datum: 2026-10-05
Författare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code, på uppdrag av
Techseed. Steg 2 i
`reports/2026-10-05-plan-datassimilering-brandprognos-claude-opus-5-5.md`.

## Kort svar

**Ensemble-Kalmanfiltret blev sämre än dagens prognos** och ska inte ersätta den.
Dess prognosytor är mindre och närmare den yta som faktiskt brann, men de missar
fler av de senare detektionerna, och ankomstintervallen träffar mer sällan.
Resultatet är detsamma med tre olika slumpfrön.

Orsaken är ett konstruktionsfel i filtret, inte i metoden: filtret räknar
passager **utan nya detektioner** som att branden stod still och sänker då
hastigheten. Dagens kalibrering hoppar över sådana intervall. Med
konstruktionsfelet når filtret en hastighetsfaktor på 1,4–1,7 den 4 augusti,
där dagens kalibrering ger 2,8–4,7.

## Upplägg

- **Samma körning för båda:** `tools/fire_ensemble_hindcast.py` gör dagens
  prognos och filtrets prognos vid varje satellitpassage, med data fram till
  passagen och facit från senare detektioner.
- **Väder:** SMHI Sala A, samma filer som demonstratorn (`app/backend/forecast.py`).
  Vädret vid passagen hålls framåt, som i dagens prognos.
- **Filtret:** `tools/fire_ensemble.py` med 50 medlemmar och inställningarna i
  planen, fastställda innan testet kördes. Under arbetet med steg 1 tillkom
  lokalisering: framflyttningen uppdaterar bara hastighetsfaktorn och riktningen
  bara vridningen.
- **Jämförbara ytor:** dagens band låg, trolig och hög (halva, en och två gånger
  den kalibrerade hastigheten) jämförs med de ytor som minst 90 %, 50 % respektive
  10 % av filtrets medlemmar når.
- **Kontroll av baslinjen:** dagens prognos gav exakt samma värden som i
  efterhandstestet från 2026-10-01 (SMHI, rådande väder). Jämförelsen räknas
  alltså likadant.

## Resultat

### Andel nya detektioner inom prognosytan (median)

| Horisont | Antal prognoser | Dagens låg / trolig / hög | Filtret 90 % / 50 % / 10 % |
|---|---:|---|---|
| 3 h | 5 | 12 % / 62 % / 100 % | 0 % / 0 % / 0 % |
| 6 h | 6 | 60 % / 92 % / 100 % | 14 % / 34 % / 62 % |
| 12 h | 16 | 59 % / 88 % / 100 % | 34 % / 56 % / 72 % |
| 24 h | 30 | 78 % / 98 % / 100 % | 74 % / 90 % / 100 % |

### Prognostiserad mot observerad tillväxt i yta (median, trolig respektive 50 %)

| Horisont | Dagens | Filtret |
|---|---:|---:|
| 3 h | 1,85 | 0,55 |
| 6 h | 2,81 | 0,87 |
| 12 h | 2,91 | 1,08 |
| 24 h | 4,13 | 3,88 |

### Ankomst till mål som nåddes inom 24 timmar (1 454 fall)

| | Dagens | Filtret |
|---|---:|---:|
| Intervallet överlappar observationsfönstret | 55 % | 19 % |
| Trolig ankomst inom observationsfönstret | 170 fall | 82 fall |
| Trolig ankomst förutsagd men målet nåddes inte | 26 541 fall | 11 777 fall |

### Tre slumpfrön (filtret, 50 %-ytan)

| Frö | Träff 6 / 12 / 24 h | Yta 6 / 12 / 24 h | Ankomst | Faktor 4 aug 13:09 |
|---|---|---|---:|---:|
| 2014 | 34 / 56 / 90 % | 0,87 / 1,08 / 3,88 | 19 % | 1,46 |
| 1 | 35 / 51 / 78 % | 0,86 / 0,99 / 3,22 | 20 % | 1,72 |
| 2 | 26 / 47 / 74 % | 0,70 / 0,87 / 2,72 | 21 % | 1,36 |

Dagens kalibreringsfaktor den 4 augusti: 4,71 (01:36), 3,47 (09:35), 3,16 (11:13),
2,84 (13:09) och 2,83 (19:13 och 20:51).

## Varför filtret blev sämre

1. **Mätningen är inte skev.** Med faktor 1 förutsäger filtrets modell nästan
   samma framflyttning som kalibreringens mått (huvudhastighet gånger timmar).
   Över de nio intervall där fronten flyttade sig minst 1 km var medianen av
   kvoten observerad mot modell 2,52 för filtrets mått och 2,46 för
   kalibreringens.
2. **Intervall utan nya detektioner drar ner hastigheten.** 10 av filtrets 26
   uppdateringar gällde intervall där ingen ny detektion låg utanför fronten,
   alltså framflyttning 0 m. Filtret tolkar det som att branden stod still. Att
   satelliten inte ser något nytt kan bero på moln, en nattpassage eller att
   branden ligger i kanten av svepet. Dagens kalibrering hoppar över sådana
   intervall.
3. **Följden** är att filtrets hastighetsfaktor ligger kring 1 i stället för kring
   3 när branden tar fart den 4 augusti. Ytorna blir små, och de missar
   spridningen.

Att filtrets ytor är mindre och närmare den yta som brann (faktor 0,9–1,1 vid 6 och
12 timmar mot dagens 2,8–2,9) är därför ingen vinst i sig. Ytorna är små för att
hastigheten är för låg.

## Beslut enligt planen

**Dagens prognos behålls.** Filtret byggs inte in i demonstratorn.

## Möjligt nästa försök

En rättad version av filtret skulle hoppa över intervall utan nya detektioner,
som dagens kalibrering gör. Det är en ändring som görs **efter** att resultatet
är känt. Ett nytt efterhandstest på samma brand skulle därför ha svagare
bevisvärde och måste redovisas som efterhandsjusterat. Ett trovärdigt prov kräver
en annan brand, till exempel bränderna i Ljusdal och Älvdalen 2018, med FIRMS-data
och väder hämtade på samma sätt.

## Begränsningar

- En enda brand, och få prognoser vid 3 och 6 timmar (5 och 6 stycken).
- Fronten är skalet runt alla detektioner hittills.
- Filtrets 50 %-yta mäts längs 72 strålar från frontens mitt. Träffandelen räknas
  exakt för varje detektion.

## Reproducera

```bash
python3 -m tools.fire_ensemble_hindcast --seed 2014 --out data/fire-ensemble-hindcast.json
python3 -m tools.fire_ensemble_hindcast --seed 1 --out data/fire-ensemble-hindcast-seed1.json
python3 -m tools.fire_ensemble_hindcast --seed 2 --out data/fire-ensemble-hindcast-seed2.json
```

En körning tar ungefär två minuter. Resultatfilerna i `data/` versionshanteras inte.
