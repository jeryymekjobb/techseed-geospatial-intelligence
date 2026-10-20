# Fler data från Meteosat för demons scenarier

Datum: 2026-10-20
Författare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code, på uppdrag av
Techseed. Undersökningen följer upp `2026-10-20-meteosat-branddata-claude-opus-5-5.md`
och gäller vad Meteosat kan bidra med utöver brandpixlarna. Den är inte juridisk
rådgivning om datarättigheter.

## Fråga

Finns de tre Meteosat-produkter som bedömdes tillföra mest, för demons datum och
områden, och på vilka villkor?

1. Molnmasken, som kan förklara varför satellitbilder saknas vissa dagar.
2. Nya Meteosats (MTG) FCI-bilder av skyfallet över Kramfors 15–16 augusti 2026.
3. LSA SAF:s brandrisk för Västmanland 2014 och Kårböle 2018.

## Metod

Den 2026-10-20: listning av LSA SAF:s dataserver och nedladdning av brandriskfiler med
användarens LSA SAF-konto (`~/.netrc`), och sökning i EUMETSAT:s Data Store
(`api.eumetsat.int/data`, katalog och produktsökning, som inte kräver konto). Det som
är **verifierat** har prövats så. Det som bara bygger på dokumentation eller min
kännedom är markerat *(dok.)*. Inga EUMETSAT-produkter har hämtats, eftersom
nedladdning från Data Store kräver ett eget EUMETSAT-konto.

## Sammanfattning

| Produkt | Finns för | Storlek | Konto | Bedömning |
|---|---|---|---|---|
| Molnmask, MSG 0° (`EO:EUM:DAT:MSG:CLM`) | 2004– , var 15:e minut; prövat 3 aug 2014 och 15 aug 2026 | ca 550 kB per kvart, hela jordskivan | EUMETSAT | Lätt att använda i alla scenarier |
| FCI Level 1c, MTG 0° (`EO:EUM:DAT:0662` normal, `0665` hög upplösning) | 24 sep 2024– , var 10:e minut; prövat 15 aug 2026 | ca 930–960 MB per tiominutersbild, hela jordskivan | EUMETSAT | Täcker Kramfors, Sundsvall och Västernorrland 2025, men tungt |
| Brandrisk FRM v3 (LSA SAF) | 2000–2026, dagligen; hämtat för båda bränderna | ca 4,5 MB per dag, Europa | LSA SAF (finns) | Fungerar redan; bygger delvis på ERA5 |

## 1. Molnmasken

**Verifierat:** samlingen *Cloud Mask – MSG – 0 degree* finns från 29 januari 2004. En
sökning gav produkter den 3 augusti 2014 kl. 12:15 UTC (MSG3) och den 15 augusti 2026
kl. 15:15 UTC. Varje produkt är cirka 554 kB och gäller hela jordskivan. Samlingens
beskrivning: varje pixel klassas som klar himmel, moln eller annat.

*(dok.)* Upplösningen är SEVIRI:s, alltså ungefär 5–10 km i nord–sydlig riktning över
Sverige (se förra rapporten). Det räcker för att säga hur molnigt det var över ett
scenarios kartområde när Landsat eller Sentinel-2 passerade, men inte för enskilda
moln. Det finns också en snabbskanningsversion över Europa (`EO:EUM:DAT:MSG:RSS-CLM`).

**I demon:** en rad i loggen eller panelen vid varje bildpassage om hur stor del av
kartområdet Meteosat såg som molnigt, till exempel när Sentinel-2:s bild över Kramfors
den 16 augusti 2026 blev 99 % moln, och eventuellt ett molnlager på kartan. Det gäller
alla scenarier.

## 2. FCI-bilder av skyfallet över Kramfors

**Verifierat:** samlingarna *FCI Level 1c Normal Resolution Image Data – MTG – 0
degree* (FDHSI) och *High Resolution Image Data* (HRFI) finns från 24 september 2024.
Båda gav produkter den 15 augusti 2026 kl. 15:10–15:19 UTC från MTG-I1 (MTI1). En
produkt för hela jordskivan är cirka 930 MB (FDHSI) respektive 960 MB (HRFI).

*(dok.)* FCI har 16 kanaler, cirka 1–2 km upplösning rakt under satelliten (HRFI ner
till 0,5–1 km i några kanaler) och tar en bild var 10:e minut. Produkterna är delade i
remsor, så det bör gå att hämta bara de remsor som täcker Norden; EUMETSAT:s Data
Tailor kan också klippa ut ett område. Inget av detta är prövat. Över Kramfors blir
pixlarna utdragna nord–syd på samma sätt som SEVIRI:s.

**I demon:** en bildserie som visar hur åskmolnen växer över Kramfors före regnet den
15 augusti 2026, som komplement till SMHI:s radar. Det gäller också Sundsvall 2026 och
Västernorrland 2025. Med cirka 6 GB per timme för hela jordskivan behöver utklippet
göras innan något hämtas.

## 3. LSA SAF:s brandrisk

**Verifierat:** `/PRODUCTS/MSG/FRMv3/NETCDF/` har år 2000–2026, en fil per dag
(`NETCDF4_LSASAF_MSG_FRMv3-ERA5_MSG-Disk_<datum>0000.nc`, cirka 4,5 MB), över
34,5–70° N och 10° W–45,5° E med 0,05° rutor. Filerna har FWI och dess delindex (FFMC,
DMC, DC, ISI, BUI), riskklass (1 låg – 5 extrem) och en sannolikhet. Licens enligt
filerna: CC BY 4.0, EUMETSAT. Närmaste ruta till varje brand:

| Datum | FWI | Riskklass | FFMC | DC |
|---|---|---|---|---|
| 31 juli 2014, Västmanland | 19,7 | hög | 88,4 | 367 |
| 2 augusti 2014 | 18,3 | hög | 90,1 | 382 |
| 3 augusti 2014 | 3,2 | låg | 68,3 | 372 |
| 4 augusti 2014 | 25,4 | hög | 91,2 | 381 |
| 5 augusti 2014 | 1,8 | låg | 73,9 | 388 |
| 14 juli 2018, Kårböle | 8,8 | låg | 81,6 | 435 |
| 16 juli 2018 | 38,1 | mycket hög | 92,5 | 453 |
| 17 juli 2018 | 38,2 | mycket hög | 92,6 | 462 |
| 18 juli 2018 | 44,1 | mycket hög | 92,6 | 471 |

Filnamnet anger att versionen bygger på ERA5, så brandrisken räknas till stor del ur
ERA5:s väder och inte bara ur Meteosats observationer *(dok., inte kontrollerat i
produktens dokumentation)*. De låga värdena den 3 och 5 augusti 2014 följer ett fall i
FFMC, som tyder på regn eller hög fuktighet i ERA5 de dagarna; det är inte jämfört med
SMHI Sala A. Demons egen FWI, beräknad ur MET Norways prognos, gav 30 för den 4 augusti.

**I demon:** en karta eller en panelrad med brandrisken för dagen, som komplement till
demons egen FWI. Den kan hämtas med det konto som redan finns.

## Översvämningarna: molntoppar, molnmask, blixtar och FCI

Undersökt 2026-10-20 på användarens fråga om hur Meteosat kan förbättra övervakningen i
översvämningsscenarierna. Sökt i EUMETSAT:s katalog och produktsökning (utan konto) en
tjugominutersperiod per scenario: Skåne 27 januari 2024 kl. 12, Västernorrland 6
september 2025 kl. 12, Sundsvall 17 augusti 2026 kl. 12 och Kramfors 15 augusti 2026 kl.
16 UTC. Inga produkter har hämtats eller öppnats.

| Samling | Startar | Skåne 2024 | Västernorrland 2025 | Sundsvall 2026 | Kramfors 2026 | Storlek |
|---|---|---|---|---|---|---|
| Molnmask, MSG (`MSG:CLM`) | 2004 | ✓ | ✓ | ✓ | ✓ | ca 550 kB per kvart |
| Molntoppens höjd, MSG (`MSG:CTH`) | 21 jun 2005 | ✓ | ✓ | ✓ | ✓ | ca 400 kB per kvart |
| Molnmask, MTG (`0678`) | 27 jan 2025 | – | ✓ | ✓ | ✓ | ca 5–6 MB per tio minuter |
| Molntoppens temperatur och höjd, MTG (`0681`) | 10 dec 2025 | – | – | ✓ | ✓ | ca 70 MB per tio minuter |
| Instabilitetsindex, MTG (`0683`) | 27 jan 2025 | – | ✓ | ✓ | ✓ | ca 14 MB per tio minuter |
| Lightning Imager, blixtar, MTG (`0691`) | 4 jul 2024 | – | ✓ | ✓ | ✓ | ca 0,2–0,5 MB per tio minuter |
| FCI-bilder, MTG (`0662`) | 24 sep 2024 | – | ✓ | ✓ | ✓ | ca 0,9–1 GB per tio minuter |
| Nederbörd FCI och mikrovåg, MTG (`1086`) | 14 aug 2025 | – | ingen kl. 12 | ✓ | ✓ | ca 3 MB |

Alla är härledda produkter eller nivå 1-data och därmed Core enligt datapolicyn, utom
FCI-bilder tätare än en i timmen (se Villkor).

**1. Molntopparna och FCI-bilderna över Kramfors.** Molntoppens höjd finns för alla fyra
översvämningarna från MSG, var 15:e minut och cirka 400 kB per produkt, så en serie över
skyfallet den 15 augusti 2026 blir liten. MTG:s produkt med både temperatur och höjd
finns först från 10 december 2025, så den täcker Sundsvall och Kramfors men inte
Västernorrland. MTG:s instabilitetsindex (från 27 januari 2025) visar hur gynnsamt läget
var för åska timmarna innan cellerna byggs, och täcker alla tre scenarier från 2025–2026.
FCI-bilderna är cirka 1 GB per bild av hela jordskivan. Enligt EUMETSAT är de uppdelade
i remsor som kan hämtas var för sig, och Data Tailor kan klippa ut ett område *(dok.,
inte prövat utan konto)*; för en serie över Kramfors behövs bara de nordligaste remsorna.

**2. Molnmasken.** Finns för alla fyra översvämningarna från MSG (cirka 550 kB per kvart)
och för 2025–2026 också från MTG med högre upplösning (cirka 5–6 MB per tio minuter).

**3. Lightning Imager.** Blixtprodukten (`LI Lightning Flashes`) finns från 4 juli 2024 i
filer per tio minuter på cirka 0,2–0,5 MB och täcker alltså Västernorrland, Sundsvall och
Kramfors. Katalogen anger ingen täckning för produkterna. ESA beskriver synfältet som
Europa och Afrika, cirka 84 % av jordskivan, och anger att den norra kameran ser norra
Skandinavien; enligt en studie från Finlands meteorologiska institut (2025) ligger Norden
i kanten av synfältet med en starkt lutande synvinkel, men instrumentet presterar
förvånansvärt bra även norr om 70° N *(dok.)*. Om den såg cellerna över Kramfors är inte
kontrollerat; det kräver att filerna hämtas.

**Bedömning för demon.** Mest nytta för minst data: molntoppens höjd från MSG över
skyfallet i Kramfors, kompletterad med MTG:s instabilitetsindex och Lightning Imagers
blixtar, som tillsammans kan visa att ovädret byggdes upp innan bräddgivarna larmade.
FCI-bilderna ger den tydligaste bilden men är tyngst. Allt kräver ett EUMETSAT-konto.

## Villkor

Kontrollerat 2026-10-20 i EUMETSAT:s datapolicy, senast ändrad 25 november 2025
(https://www-cdn.eumetsat.int/files/2026-01/45173%20-%20Data_Policy.pdf). Det här är en
läsning av policyn, inte juridisk rådgivning.

- **Core** (artikel 5.1, 6.1 och tabellen över kategorier): nivå 1-data från SEVIRI och
  FCI en gång i timmen ("Hourly Data", den bild som hör till varje hel timme UTC), alla
  härledda produkter från EUMETSAT:s marksegment och från SAF:arna ("All SAF products are
  categorised as Core") och färdiga bildprodukter (RGB). De är fria för all användning
  och får spridas vidare, under CC BY 4.0.
- **Recommended** (artikel 5.2, 6.2, 12 och 14): nivå 1-data från SEVIRI och FCI oftare
  än en gång i timmen. Data med minst en timmes fördröjning, vilket gäller allt arkiv, är
  gratis för all användning, även för företag (artikel 14.1), men kräver EUMETSAT:s
  licens, och de ursprungliga siffervärdena får inte spridas till andra (artikel 6.2).
- **Kreditering** (artikel 6.3): "[Contains modified] EUMETSAT [Meteosat/Metop]
  [data/product] [år för publicering eller spridning]".

För demons produkter betyder det:

| Produkt | Kategori | Villkor för demon |
|---|---|---|
| Molnmask, MSG 0° | Core (härledd produkt) | CC BY 4.0; får visas och spridas |
| LSA SAF:s brandpixlar och brandrisk | Core (SAF-produkt) | CC BY 4.0; får visas och spridas |
| FCI, en bild i timmen | Core | CC BY 4.0; får visas och spridas |
| FCI, var 10:e minut | Recommended | Gratis för arkivdata efter godkänd licens; egna renderade bilder får visas, FCI-filerna själva får inte lämnas till andra |

Nedladdning från EUMETSAT:s Data Store kräver ett gratis EUMETSAT-konto och en
API-nyckel *(dok.)*; LSA SAF-kontot finns redan. Demons kreditering av Meteosats
brandpixlar följer sedan 2026-10-20 artikel 6.3: "Contains modified EUMETSAT Meteosat
product 2026 (LSA SAF MSG FRP-Pixel, CC BY 4.0)".

## Nästa steg

1. Om molnmasken eller FCI-bilderna ska användas: användaren registrerar ett
   EUMETSAT-konto; för FCI-bilder oftare än en gång i timmen godkänns också licensen.
2. Besluta vilken av de tre som ska byggas först; brandrisken kan byggas direkt.

## Källor

- LSA SAF, Fire Risk Map v3: https://datalsasaf.lsasvcs.ipma.pt/PRODUCTS/MSG/FRMv3/NETCDF/
- ESA, MTG Lightning Imager, norra kamerans synfält: https://esa.int/esatv/Videos/2023/09/MTG_Lightning_Imager_animations_-_July_2023/North_camera_full_field_of_view
- Finlands meteorologiska institut m.fl., ECSS2025-104: https://meetingorganizer.copernicus.org/ECSS2025/ECSS2025-104.html
- EUMETSAT Data Policy (senast ändrad 25 november 2025): https://www-cdn.eumetsat.int/files/2026-01/45173%20-%20Data_Policy.pdf
- EUMETSAT Data Store, katalog: https://api.eumetsat.int/data/browse/collections
- EUMETSAT Data Store, produktsökning: https://api.eumetsat.int/data/search-products/1.0.0/os
- Samlingar: `EO:EUM:DAT:MSG:CLM`, `EO:EUM:DAT:MSG:RSS-CLM`, `EO:EUM:DAT:MSG:CTH`, `EO:EUM:DAT:0662`, `EO:EUM:DAT:0665`, `EO:EUM:DAT:0678`, `EO:EUM:DAT:0681`, `EO:EUM:DAT:0683`, `EO:EUM:DAT:0691`, `EO:EUM:DAT:1086`
