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
markerat *(dok.)*. Inga datafiler har hämtats eller öppnats, eftersom nedladdning
kräver ett konto.

## Sammanfattning

- **Ja, sannolikt för båda.** LSA SAF:s **MSG FRP-Pixel** finns för båda perioderna:
  varje brandpixel som Meteosats SEVIRI ser, med läge, tid och strålningseffekt (FRP),
  var 15:e minut över hela jordskivan. Om Västmanlands och Kårböles bränder faktiskt
  finns i filerna är **inte kontrollerat**; det kräver att filerna öppnas.
- Pixlarna är grova över Sverige, så bara stora och intensiva brandfaser kan väntas
  synas.
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

## Vad det skulle ge demon

En kurva över brandeffekten var 15:e minut från en stillastående satellit, mellan
polarsatelliternas passager, och grova pixlar på kartan. Båda ska märkas med Meteosat,
pixelstorlek och att det är arkivdata, inte realtid. Inget av detta är byggt.

## Nästa steg

1. Användaren registrerar ett konto hos LSA SAF.
2. Hämta FRP-Pixel-filerna för perioderna, behåll bara pixlarna inom scenariernas
   kartområden och jämför tider och FRP med FIRMS.
3. Besluta därefter om och hur det ska visas i demon.

## Källor

- LSA SAF, Fire Detection & Emissions: https://lsa-saf.eumetsat.int/data/products/fire-products/
- LSA SAF dataserver, MSG FRP-PIXEL: https://datalsasaf.lsasvcs.ipma.pt/PRODUCTS/MSG/FRP-PIXEL/
- FEDEO, Active Fire Monitoring, MSG 0°: https://fedeo.ceos.org/series/concepts/instruments/c1bba609-e816-52c5-b9ed-9b22c0da820f/EO:EUM:DAT:MSG:FIR
- Wooster m.fl. 2015, LSA SAF Meteosat FRP products – Part 1: https://acp.copernicus.org/articles/15/13217/2015/
- Roberts m.fl. 2015, LSA SAF Meteosat FRP products – Part 2: https://acp.copernicus.org/articles/15/13241/2015/
- NASA Earth Observatory, Scarcely Seen Scandinavian Fires: https://earthobservatory.nasa.gov/images/92454/scarcely-seen-scandinavian-fires
