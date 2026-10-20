# Meteosats branddata för Västmanland 2014 och Kårböle 2018

Datum: 2026-10-20
Författare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code, på uppdrag av
Techseed. Undersökningen gäller om geostationära satelliter kan komplettera demons
polarsatelliter (FIRMS) i de två brandscenarierna. Den är inte juridisk rådgivning om
datarättigheter.

## Fråga

Har Meteosat branddetektioner, som går att hämta i dag, för skogsbranden i Västmanland
2014 och skogsbranden vid Kårböle 2018?

| Händelse | Period (UTC) | Område |
|---|---|---|
| Skogsbranden i Västmanland 2014 | 31 juli–14 augusti 2014 | 59,75–60,08 N, 15,85–16,45 E |
| Skogsbranden vid Kårböle 2018 | 12 juli–8 augusti 2018 | 61,75–62,2 N, 14,9–15,8 E |

## Metod

Sökningar efter EUMETSAT:s och LSA SAF:s brandprodukter, genomgång av LSA SAF:s
produktsida och listning av LSA SAF:s dataserver den 2026-10-20. Det som är
**verifierat** har prövats mot servern. Det som bara bygger på dokumentation är
markerat *(dok.)*. Samma dag hämtades och lästes filerna med användarens LSA SAF-konto
(se Resultat).

## Sammanfattning

- LSA SAF:s **MSG FRP-Pixel** har varje brandpixel som Meteosats SEVIRI ser, med läge, tid
  och strålningseffekt (FRP), var 15:e minut över hela jordskivan, för båda perioderna.
- **Västmanland 2014: ja, men bara den 4 augusti.** Sex pixlar i fem kvartar 12:00–13:45
  UTC, upp till 2 605 MW i en pixel.
- **Kårböle 2018: nej.** Ingen pixel i kartområdet under hela perioden, men 98 pixlar vid
  andra bränder cirka 50 km västerut 14–18 juli.
- Pixlarna är grova över Sverige, cirka 26 km², så bara de intensivaste timmarna syns.
- EUMETSAT:s egen produkt Active Fire Monitoring och nya Meteosat (MTG) täcker inte
  åren.

## Produkter

| Produkt | Innehåll | Period | 2014 | 2018 |
|---|---|---|---|---|
| MSG FRP-Pixel (LSA-502; arkivet 2004–2015 som FRPPixel-R, LSA-550) | Brandpixlar med FRP, SEVIRI, ca 3 km rakt under satelliten, var 15:e minut | 2004– | ja | ja |
| MSG FREM (LSA-507) | Brandutsläpp per 0,1°-ruta, per timme och dygn | 2004– *(dok.)* | sannolikt | sannolikt |
| MSG FRP-Grid (LSA-503) | FRP per 5°-ruta och timme | 2016–, uppehåll *(dok.)* | – | grovt |
| MSG FD&M (LSA-501) | Brandrisk, inte detektioner | 2010–2024, nedlagd *(dok.)* | – | – |
| EUMETSAT Active Fire Monitoring, MSG 0° (`EO:EUM:DAT:MSG:FIR`) | Brand eller möjlig brand i CAP-format, ±67,5° | från 1 september 2020 *(dok.)* | nej | nej |
| MTG FRP-Pixel (LSA-509) | FCI, ca 1 km, var 10:e minut | 2025– *(dok.)* | nej | nej |

## Verifierat på dataservern

- `https://datalsasaf.lsasvcs.ipma.pt/PRODUCTS/MSG/FRP-PIXEL/HDF5/` har årsmappar från
  2004, och 2014 och 2018 har alla tolv månader.
- `…/HDF5/2014/08/04/` och `…/HDF5/2018/07/17/` listar filer för hela jordskivan var 15:e
  minut, till exempel `HDF5_LSASAF_MSG_FRP-PIXEL-ListProduct_MSG-Disk_201408040000` och
  `…_201807170000`. Det finns inga separata Europafiler; Europa ligger i
  jordskivefilen.
- Serverns `Readme.md`: nedladdning kräver registrering
  (`https://mokey.lsasvcs.ipma.pt/auth/signup`), med wget eller WebDAV.

## Villkor

- Licens: LSA SAF:s produkter är licensierade av EUMETSAT under CC BY 4.0, med LSA SAF:s
  regler för hänvisning *(dok.)*. Hänvisa till Wooster m.fl. 2015 och Roberts m.fl. 2015
  för FRP.
- Kontot är personligt. Användarnamn och lösenord hör inte hemma i repot.

## Begränsningar

- **Synvinkel och pixelstorlek.** Meteosat står över ekvatorn på 0° longitud. Egna
  överslag, inte uppmätta värden: Västmanland ses ca 21° över horisonten och Kårböle ca
  19°, på ca 39 500 km avstånd. En pixel på 3 km rakt under satelliten blir då ca 3 km
  öst–väst och upp mot ca 9–10 km nord–syd. (Svaret i chatten 2026-10-20 angav 5–7 km;
  överslaget här är grövre åt det hållet.)
- **Missade bränder.** Roberts m.fl. 2015 anger att SEVIRI över Europa missar fler
  bränder och underskattar FRP än över Afrika, på grund av de större pixlarna *(dok.)*.
  Små bränder och svaga brandfronter bör inte väntas synas. Västmanlands snabba spridning
  den 4 augusti 2014 och Kårbölebrandens största dagar är rimliga kandidater, men det är
  en bedömning, inte ett resultat.
- **Inga tidigare studier hittade.** Ingen studie av SEVIRI-detektioner för de svenska
  bränderna 2014 eller 2018 hittades. NASA:s bilder av bränderna 2018 är från MODIS.
- **Satellit.** Vilken Meteosat som stod på 0° vid varje tillfälle följer av filernas
  metadata och är inte kontrollerat här.

## Resultat (hämtat 2026-10-20)

Alla FRP-Pixel-filer för 31 juli–14 augusti 2014 och 12 juli–8 augusti 2018 hämtades med
användarens LSA SAF-konto: 4 117 av 4 128 kvartar. 11 kvartar fanns inte på servern även
efter nya försök (7 under 2014 och 4 under 2018, bland annat 12 juli 2018 13:30–14:00
UTC). Pixlarna inom varje scenarios kartområde (`MAP_BBOX`) sparades i ej versionerade
`data/vastmanland2014/meteosat-frp/` och `data/ljusdal2018/meteosat-frp/` med
`SOURCE.json`; satelliten var MSG3 (Meteosat-10) 2014. Produkten tar med pixlar upp till
cirka 72° synvinkel (största värde i filerna 71,98°).

**Västmanland 2014: 6 pixlar, bara den 4 augusti.** Meteosat såg branden i fem kvartar
den 4 augusti 12:00–13:45 UTC, under den snabba spridningen, med upp till 2 605 MW i en
pixel och 3 903 MW sammanlagt i en kvart. Pixlarnas yta anges till cirka 26 km² och
synvinkeln till cirka 70°. Inga andra dagar gav någon pixel, fast FIRMS hade 85–820
detektioner om dagen 1–5 augusti.

| Datum 2014 | Meteosat-kvartar | Meteosat-pixlar | Max MW per pixel | FIRMS detektioner | FIRMS max MW |
|---|---|---|---|---|---|
| 31 juli | 0 | 0 | – | 19 | 156,9 |
| 1 augusti | 0 | 0 | – | 85 | 137,8 |
| 2 augusti | 0 | 0 | – | 186 | 314,0 |
| 3 augusti | 0 | 0 | – | 132 | 63,5 |
| 4 augusti | 5 | 6 | 2 604,8 | 560 | 450,9 |
| 5 augusti | 0 | 0 | – | 820 | 78,1 |

FIRMS-värdena är per detektion från MODIS och VIIRS, med betydligt mindre pixlar, och kan
inte jämföras direkt med Meteosats per pixel.

**Kårböle 2018: inga pixlar i kartområdet.** Meteosat såg ingen brand inom 14,9–15,8° E,
61,75–62,2° N under hela perioden, fast FIRMS hade upp till 571 detektioner om dagen
15–28 juli. Synvinkeln vid Kårböle är cirka 71°, inom produktens gräns. Däremot såg
Meteosat 98 pixlar i Sverige 14–18 juli 2018, de flesta och starkaste kring 61,7–61,9° N,
14,3–14,6° E, cirka 50 km väster om Kårböle (upp till 3 116 MW i en pixel den 16 juli
17:45 UTC). Vilken brand det var har inte kontrollerats mot andra källor.

Slutsatsen är att Meteosat bara fångar de mest intensiva timmarna så här långt norrut:
en eftermiddag i Västmanland och ingen gång i Kårböle.

## Vad det skulle ge demon

I Västmanland kan Meteosats sex pixlar den 4 augusti visas som ett exempel på vad en
geostationär satellit ser så här långt norrut: grova pixlar på cirka 26 km² under de
intensivaste timmarna, mellan polarsatelliternas passager. Det ska märkas med Meteosat,
pixelstorlek och att det är arkivdata, inte realtid. I Kårböle finns inget att visa.
Inget av detta är byggt.

## Nästa steg

Besluta om Västmanlands Meteosat-pixlar ska visas i demon, och i så fall hur.

## Källor

- LSA SAF, Fire Detection & Emissions: https://lsa-saf.eumetsat.int/data/products/fire-products/
- LSA SAF dataserver, MSG FRP-PIXEL: https://datalsasaf.lsasvcs.ipma.pt/PRODUCTS/MSG/FRP-PIXEL/
- FEDEO, Active Fire Monitoring, MSG 0°: https://fedeo.ceos.org/series/concepts/instruments/c1bba609-e816-52c5-b9ed-9b22c0da820f/EO:EUM:DAT:MSG:FIR
- Wooster m.fl. 2015, LSA SAF Meteosat FRP products – Part 1: https://acp.copernicus.org/articles/15/13217/2015/
- Roberts m.fl. 2015, LSA SAF Meteosat FRP products – Part 2: https://acp.copernicus.org/articles/15/13241/2015/
- NASA Earth Observatory, Scarcely Seen Scandinavian Fires: https://earthobservatory.nasa.gov/images/92454/scarcely-seen-scandinavian-fires
