# Får källkrediteringen flyttas från kartbilden?

Claude Opus 5.5, 2026-10-30. Användaren frågade om copyrighttexterna måste stå i kartbilden,
eller om de kan listas i scenariots startpanel eller i slutbilden. Rapporten går igenom
villkoren för varje källa som demon krediterar i dag (`ATTRIBUTION` i scenarierna och
modulernas egna texter). Det är en läsning av villkoren, inte en juridisk bedömning.

## Sammanfattning

- Inget av de kontrollerade villkoren kräver att krediten står i själva kartbilden.
  OpenStreetMap har de mest detaljerade reglerna. En startskärm räcker där, och krediten får
  sedan fällas ihop till en "(i)"-knapp, om den går att hitta.
- CC BY 4.0-källorna får krediteras "in any reasonable manner based on the medium". Det
  gäller SMHI, EUMETSAT, LSA SAF, Copernicus klimatdata (ERA5) och MET Norway. Föreskriven
  ordalydelse måste dock behållas, till exempel "Contains modified EUMETSAT …" och
  "Contains modified Copernicus Sentinel data [år]".
- Lantmäteriets öppna data, Natural Earth och USGS (Landsat) kräver ingen kredit. NASA FIRMS
  ber om en.
- Inte klarlagt: Sundsvalls kommuns geoserver. Användningen bygger på ett eget medgivande,
  och tjänstens text säger inget om krediten. Hur kommunen vill bli krediterad behöver
  kontrolleras mot det medgivandet.
- Västerås stads data får bara användas internt, enligt användaren 2026-10-28. Det gäller
  oavsett var krediten står och berör scenariot `vasteras-sep2023` vid offentlig visning.

## Källa för källa

| Källa | Villkor | Krav på krediten | I kartbilden? |
|---|---|---|---|
| OpenStreetMap (offline-kartan, OSM online, OSM-lager) | ODbL; OSMF Attribution Guidelines | Interaktiva kartor: "should typically appear in a corner of the map", men också intill kartan eller på en startskärm. Får fällas ihop efter fem sekunder, vid panorering eller när man stänger den, men "the user must still be able to find the licence information", till exempel via "(i)". Tittaren ska inte behöva göra något för att se den. Texten ska vara läsbar och synas tillräckligt länge. | Nej. Startskärm plus "(i)" räcker. |
| SMHI (nederbörd, radar, flöden, vattenstånd, blixtar) | CC BY 4.0 SE | "Du ska ange SMHI som källa och även ange om du har ändrat i licensmaterialet." Ingen placering anges. | Nej |
| EUMETSAT (Meteosat: molnmask, molntoppar, MTG LI, GII) | Datapolicyn, Core Data under CC BY 4.0 | Artikel 6.3: "[Contains modified] EUMETSAT [Meteosat/Metop] [data/product] [Year]". Ingen placering anges. | Nej |
| LSA SAF (FRP-Pixel, FRM) | CC BY 4.0 | Kort form för figurer: "EUMETSAT LSA SAF [akronym, id]"; DOI om den finns. Ingen placering anges. | Nej, men den korta formen för figurer bör stå i listan |
| Copernicus Sentinel och radarvattnet | EU:s rättsliga meddelande (förordning 1159/2013) | "Contains modified Copernicus Sentinel data [Year]" när datan har bearbetats. Mottagarna ska informeras; ingen placering anges. | Nej |
| Copernicus EMS (EFAS) | Samma meddelande | "Contains modified Copernicus Service information [Year]". | Nej |
| ERA5 och ERA5-Land (C3S) | CC BY 4.0 | Enligt CC BY 4.0. | Nej |
| Copernicus DEM GLO-30 (3D-terrängen) | ESA:s licens för Copernicus Contributing Missions | Vid bearbetning: "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved". Allmänheten ska informeras; ingen placering anges. | Nej |
| MET Norway (prognoser) | NLOD och CC BY 4.0 | Ange MET Norway som källa, till exempel "Based on data from MET Norway". Ingen placering anges. | Nej |
| MCF:s översvämningskarteringar | INSPIRE-posten: inga begränsningar och inga villkor (kontrollerat tidigare, se `sundsvall2026.py`) | Ange MCF som källa. | Nej |
| Lantmäteriet (öppna data) | CC0 | "Ange gärna Lantmäteriet som källa … men det är inget krav." | Nej |
| Trafikverket (i kommunens karta) | Krediteras tillsammans med kommunens karta | Följer kommunens karta. | Se Sundsvall |
| Sundsvalls kommun (Kartan, skyfallsmodeller, WMS) | Tjänstens text: "No use is permitted to users outside of these five organisations, if not explicitly agreed." Användaren bekräftade 2026-10-06 och 2026-10-14 att demon får använda den. | Tjänsten anger inget om krediten. | Okänt. Kontrollera mot medgivandet. |
| Västerås stad (bakgrundskartor, flygfoto, skyfallskartering) | Användaren 2026-10-28: endast intern användning, inga offentliga visningar | Tjänsten anger inget (AccessConstraints "none"). | Okänt; scenariot ska inte visas offentligt |
| NASA FIRMS (Kårböle, Västmanland) | Öppna data | FAQ: bildtexter ska ange "NASA FIRMS". Ingen placering anges. | Nej |
| USGS Landsat | Allmän egendom | "we ask that proper credit be given"; en textrad räcker. | Nej |
| Natural Earth II (världskartan) | Allmän egendom | "Crediting the authors is unnecessary." | Nej |
| Space-Track (banelement) | Se `reports/2026-10-21-space-track-villkor-claude-opus-5-5.md` | Lämplig citering; står redan under satellitlistorna. | Påverkas inte |
| Länsstyrelsen, kommunen och nyheter (vägskador) | Källhänvisning till fakta, inte en licens | Källan ska framgå. | Nej |

## Förslag till steg 2

1. På kartan i 2D och 3D en kort rad: "© OpenStreetMap-bidragsgivare · (i) Källor". Ett
   klick på "(i)" visar hela listan i en ruta på kartan, med samma texter som i dag.
2. Hela listan visas i startpanelen ("… – det här visas"), som står kvar till PLAY, och i
   slutbilden. Där räknas den som startskärm enligt OSMF.
3. En kommunal karta krediteras kvar på kartan när den visas, med kort text ("© Sundsvalls
   kommun"), tills det är klart hur kommunen vill bli krediterad.
4. Texterna ändras inte, bara var de står.

## Källor

- OSMF, [Licence/Attribution Guidelines](https://osmfoundation.org/wiki/Licence/Attribution_Guidelines)
- Creative Commons, [CC BY 4.0 legal code](https://creativecommons.org/licenses/by/4.0/legalcode.en), avsnitt 3(a)(1) och 3(a)(2)
- SMHI, [Villkor för användning](https://www.smhi.se/data/om-smhis-data/villkor-for-anvandning)
- Lantmäteriet, [Öppna data](https://www.lantmateriet.se/sv/geodata/vara-produkter/oppna-data/)
- EUMETSAT, [Data Policy](https://www-cdn.eumetsat.int/files/2026-01/45173%20-%20Data_Policy.pdf), ändrad 25 november 2025, artikel 5 och 6
- LSA SAF, [Data access](https://lsa-saf.eumetsat.int/data/data-access/)
- Europeiska kommissionen, [Legal notice on the use of Copernicus Sentinel Data and Service Information](https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice)
- Copernicus Data Space, [COP-DEM](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM)
- Climate Data Store, [CC-BY-licensen](https://cds.climate.copernicus.eu/licences/cc-by)
- MET Norway, [Licensing and crediting](https://www.met.no/en/free-meteorological-data/Licensing-and-crediting)
- NASA Earthdata, [FIRMS FAQ](https://www.earthdata.nasa.gov/data/tools/firms/faq)
- USGS, [Crediting USGS](https://www.usgs.gov/information-policies-and-instructions/crediting-usgs)
- Natural Earth, [Terms of use](https://www.naturalearthdata.com/about/terms-of-use/)
- Sundsvalls kommun, GetCapabilities för `karta.sundsvall.se/geoserver/wms`, hämtad 2026-10-30
