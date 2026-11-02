# Kravmall och spårbarhetsmodell – utkast

Underlag för MVP:n, fas 0c. Utkast gjort 2026-11-02, nu på `main`.
Dokumentet beskriver hur kraven i kravspecifikationen (fas 1) ska skrivas och spåras. Det
innehåller inga beslutade krav. Exemplen i slutet är märkta som exempel och är inte
godkända.

Dokumentet bygger på:

- `docs/mvp/funktionskatalog.md` (fas 0a) med funktions-ID:n `F-xx-nn`.
- `docs/mvp/regelverksregister.md` (fas 0b) med regelverks-ID:n `R-xx-nn` och de öppna
  besluten `B-KUND`, `B-ANV`, `B-MARK`, `B-IOT` och `B-DATA`.

## Spårbarhetskedjan

```
Källa till kravet            Krav          Funktion        Verifiering
R-xx-nn  (regelverk)  ─┐
N-xx-nn  (behov)      ─┼──>  K-xx-nn  ──>  F-xx-nn   ──>   test, inspektion,
D-ÅÅÅÅ-MM-DD (beslut) ─┘                                   analys eller demonstration
```

- **Bakåt:** varje krav har minst en källa. Kravet är skälet till att en funktion finns.
  Källan är skälet till att kravet finns.
- **Framåt:** varje krav pekar på de funktioner som uppfyller det, och på hur det
  verifieras.
- **Funktioner utan krav:** en funktion i katalogen som inget krav pekar på är en kandidat
  att strykas eller att flytta utanför MVP:n. Den stryks inte automatiskt.
  Det beslutet fattas av användaren (se `CONTEXT.md`).

### Typer av källor

| Prefix | Källa | Var den finns |
|---|---|---|
| `R-xx-nn` | Regelverk, villkor eller standard | `docs/mvp/regelverksregister.md` |
| `N-xx-nn` | Behov hos beställaren eller användarna | Ska föras in ur beställarens one-pager när den finns. Om one-pagern är konfidentiell förs bara en neutral sammanfattning in, och referensen pekar på en plats utanför repot. |
| `D-ÅÅÅÅ-MM-DD` | Beslut av användaren, registrerat i `CONTEXT.md` | `CONTEXT.md`, Current Direction och handoffen |

## Krav-ID

Formatet är `K-<område>-<nummer>`, med två siffror. Ett ID återanvänds aldrig, inte heller
när ett krav avförs.

| Område | Betydelse |
|---|---|
| `K-FN` | Funktion: vad MVP:n gör |
| `K-DA` | Data: källor, märkning, kreditering, rättigheter, tid och koordinater |
| `K-AN` | Analys och bedömning: spårbarhet, belägg, begränsningar |
| `K-CS` | Cybersäkerhet och behörighet |
| `K-AI` | AI-specifika krav: öppenhet, mänsklig kontroll, dokumentation |
| `K-PD` | Personuppgifter |
| `K-ACC` | Tillgänglighet |
| `K-OPS` | Drift, installation och plattform |
| `K-DOC` | Dokumentation och leverans |

## Kravmall

Varje krav skrivs med fälten nedan. Fält som saknar värde anges med "–", inte utelämnas.

| Fält | Innehåll |
|---|---|
| **ID** | `K-xx-nn` |
| **Krav** | En mening med "ska", som går att verifiera. Ett krav per post. |
| **Motivering** | Kort varför. Skiljer verifierade fakta, antaganden och beslut åt. |
| **Källa** | En eller flera `R-`, `N-` eller `D-` referenser. |
| **Villkor** | Det öppna beslut kravet beror på, till exempel `B-MARK`, eller "–". |
| **Funktioner** | `F-xx-nn` som uppfyller kravet. "Saknas" om ingen funktion finns i dag. |
| **Verifiering** | Metod: **T** test, **I** inspektion, **A** analys, **D** demonstration. Ange var: testfil, dokument eller procedur. |
| **Prioritet** | **Måste**, **Bör**, **Kan** eller **Inte nu** (MoSCoW). Sätts av användaren. |
| **Status** | Se nedan. |
| **Uppfyllt i dag** | **Ja**, **Delvis**, **Nej** eller **Okänt**, med en kort förklaring. |

### Status

| Status | Betydelse |
|---|---|
| **Förslag** | Skrivet men inte granskat. Alla krav börjar här. |
| **Granskat** | Granskat mot källan. För krav från regelverk betyder det att källan är kontrollerad mot primärkälla (märkningen **P** i registret) och granskad av en behörig person. |
| **Godkänt** | Godkänt av användaren eller beställaren för MVP:n. |
| **Verifierat** | Verifieringen är genomförd och dokumenterad mot en bestämd commit. |
| **Avfört** | Ska inte gälla. Skälet anges. ID:t behålls. |

Ett krav vars källa är ett regelverk får inte gå längre än **Förslag** så länge regelverket
saknar märkningen **P** i registret, eller så länge villkoret är obesvarat.

## Regler för spårbarheten

1. Varje krav har minst en källa.
2. Varje krav med prioriteten **Måste** har minst en verifiering.
3. Varje funktion i katalogen pekar minst ett krav på, eller så står den i listan över
   funktioner utan krav.
4. Ett krav med status **Verifierat** anger commit och datum för verifieringen.
5. När en funktion, ett regelverk eller ett beslut ändras, granskas de krav som pekar på
   dem igen.

## Spårbarhetsmatris

Matrisen sammanställs ur kraven. En rad per par av krav och funktion:

| Krav | Källa | Funktion | Verifiering | Status |
|---|---|---|---|---|
| `K-xx-nn` | `R-xx-nn` | `F-xx-nn` | T: `tests/...` | Förslag |

I fas 1 skrivs kraven och matrisen som Markdown-tabeller i `docs/mvp/`. Om kraven blir
många kan de flyttas till en maskinläsbar fil, till exempel YAML eller CSV, med ett test
som kontrollerar reglerna ovan. Det är inte beslutat.

## Exempel (inte godkända krav)

Exemplen visar formatet. De bygger på funktioner som finns, men prioritet och status är
inte satta av användaren.

### Exempel 1

| Fält | Värde |
|---|---|
| **ID** | K-DA-01 (exempel) |
| **Krav** | Varje datakälla vars data visas ska krediteras på skärmen i den form källans villkor anger. |
| **Motivering** | Copernicus villkor kräver att källan anges (kontrollerat mot sekundärkälla 2026-11-02). Övriga källors villkor är delvis kontrollerade i tidigare rapporter. |
| **Källa** | R-GEO-01, R-GEO-05 |
| **Villkor** | – |
| **Funktioner** | F-MAP-07 |
| **Verifiering** | T: `tests/test_credits.py`. I: genomgång av villkoren per källa mot krediteringstexterna. |
| **Prioritet** | Inte satt |
| **Status** | Förslag |
| **Uppfyllt i dag** | Delvis. Krediteringen finns. Hur Sundsvalls kommun vill bli krediterad är inte känt. |

### Exempel 2

| Fält | Värde |
|---|---|
| **ID** | K-DA-02 (exempel) |
| **Krav** | Syntetiska och simulerade data ska vara märkta som syntetiska eller simulerade överallt där de visas eller läses upp. |
| **Motivering** | Beslutet att sensorerna körs simulerade och visas som simulerade, och projektregeln att inte presentera simulerade data som live. |
| **Källa** | D-2026-10-04 |
| **Villkor** | – |
| **Funktioner** | F-COM-03, F-SC-04, F-IOT-02, F-IOT-03, F-IOT-04 |
| **Verifiering** | T: `tests/test_view_caption.py`, `tests/test_satlog.py`. D: genomgång av varje scenario på skärmarna. |
| **Prioritet** | Inte satt |
| **Status** | Förslag |
| **Uppfyllt i dag** | Okänt. Märkningen finns, men ingen genomgång av alla scenarier mot kravet är gjord. |

### Exempel 3

| Fält | Värde |
|---|---|
| **ID** | K-CS-01 (exempel) |
| **Krav** | Kommandon till scenariot ska bara tas emot från autentiserade användare när mission control nås över nätverk. |
| **Motivering** | En levererad MVP kan omfattas av CRA:s krav på skydd mot obehörig åtkomst. Det är inte granskat. |
| **Källa** | R-CS-01 |
| **Villkor** | B-MARK |
| **Funktioner** | F-MC-03 |
| **Verifiering** | T: `tests/test_mission_control.py`. A: hotanalys för nätverksåtkomst. |
| **Prioritet** | Inte satt |
| **Status** | Förslag |
| **Uppfyllt i dag** | Delvis. Det finns en valfri token för kommandon, men inga användarkonton och ingen behörighetsstyrning. |

## Öppet

- Var kraven och matrisen slutligen ska ligga: i repot, i ett dokumentsystem eller båda.
  Det hänger ihop med den öppna frågan om var dokumenten och presentationen ska ligga.
- Hur kundbehov (`N-xx-nn`) hanteras om beställarens one-pager är konfidentiell.
- Vem som får sätta prioritet och godkänna krav: användaren, beställaren eller båda.
