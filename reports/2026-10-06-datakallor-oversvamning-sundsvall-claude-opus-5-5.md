# Datakällor för en översvämningsdemo i Sundsvall

Datum: 2026-10-06
Författare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code, på uppdrag av
Techseed. Undersökningen gäller en andra demo i demonstratorn, med branddemon för
Västmanland 2014 som mall. Den är inte juridisk rådgivning om datarättigheter.

## Fråga

Vilka av källorna från mötet med Sundsvalls kommun, och vilka öppna källor, kan
användas för en demo om översvämningen i Sundsvall kring den 16 augusti 2026?

## Beslut (användaren, 2026-10-06)

- Sundsvallsdemon blir ett **scenario** byggt på det verkliga regnet och kommunens
  skyfallsmodeller, tydligt märkt som scenario, inte en återgiven händelse.
- Branddemon är mallen: samma skärmar och delar, scenariot väljs vid start. De två
  demona behöver inte köras samtidigt.
- Användaren tycker att det är i sin ordning att be kommunen om tillstånd för lagren
  i bxkarta. Tills ett skriftligt tillstånd finns används lagren inte.

## Verifierade fakta

### Händelsen

- SMHI:s sammanfattning av augusti 2026: särskilt stora mängder i nordöstra
  Norrland 16–20 augusti, översvämning i Boden. Sundsvall nämns inte.
  <https://www.smhi.se/klimat/klimatet-da-och-nu/manadens-vader-och-vatten-i-sverige/manadens-vader-och-vatten-i-sverige/2026-09-04-augusti-2026---vattenbrist--i-soder-oversvamning-i-norr>
- SMHI:s öppna API för meteorologiska observationer (parameter 7, timvärden, och 14,
  15-minutersvärden) har kommunens egna regnmätare (ägare "Sundsvalls kommun").
  Dygnssummor 16 augusti (UTC): Fillan 29,2 mm, Heffners 25,4, Bredsand 17,6,
  Brämön A 15,9, Essvik 11,6, Bällsta 8,6. Högsta timvärde 10,6 mm (Fillan, 08 UTC),
  högsta 15-minutersvärde 3,0 mm. Ett andra regn 19 augusti (Bällsta 28,6 mm).
  Exempel: <https://opendata-download-metobs.smhi.se/api/version/1.0/parameter/7/station/2222814.json>
- Copernicus EMS har ingen aktivering för Sverige 2026. Den senaste svenska är
  EMSR841, översvämning i Västernorrland 2025-09-06 (Gottne och Bjästa), utanför
  Sundsvall.
- Sentinel-1 (radar) har bilder 16, 17, 18 och 22 augusti 2026. Sentinel-2 är
  98,6 % molnig 16 augusti; klarast är 20 augusti, cirka 12 % moln (rutorna T33VXK
  och T34VCQ). Källa: Copernicus Data Space-katalogen.

Översvämningen i Sundsvall är alltså inte bekräftad i öppna källor. Regnet var
kraftigt men inte ett skyfall enligt mätarna ovan.

### Källorna från mötet

| Källa | Vad den är | Användning |
|---|---|---|
| [diwise/iot-transform-fiware](https://github.com/diwise/iot-transform-fiware) | Go, AGPL-3.0. Omvandlar sensordata till FIWARE/NGSI-LD-entiteter. `Sewer` har `level`, `percent`, bräddstatus (start, uppdatering, slut), `overflowObservedAt`, `overflowEndedAt` och `overflowCumulativeTime`; även `SewagePumpingStation`. | Formen för simulerade bräddnoder. Historiska data kräver tillgång till kommunens broker, som inte är publik. |
| [Sundsvallskommun/gis-origo2client](https://github.com/Sundsvallskommun/gis-origo2client) | Kommunens version av Origo (OpenLayers). Ingen licens angiven i repot; Origo är BSD-2. Innehåller inga data. | Lokalt test av hur ett eget WMS-lager ser ut i deras karta. |
| QGIS | GIS med öppen källkod; QGIS Server publicerar WMS och WFS. | Möjligt verktyg för att ta fram och publicera ett eget lager. |
| [Satellitdata](https://github.com/Satellitdata) (RECON) | Två publika repon (React, arkitekturdokument). `context-broker-prototype` svarar 404. Målarkitektur: FIWARE Orion-LD matat av diwise; Origo läser via OGC API Features eller WMS. | Integrationsmönster. Inga översvämningsdata. |
| HSOPublik (`kartatest.sundsvall.se/HSOPublik/`) | Origo-karta med cirka 28 lager (riksintressen, skyddade områden, transportplan). | Inga översvämningslager. |
| bxkarta (`karta.sundsvall.se/bxkarta/`) | Kommunens geoserver, 1 205 lager, bland annat `Skyfallsmodell30/100/500_tiff`, maxvattendjup och -hastighet, `GATA_KritiskDagvatten_punkt`, 100-årsflöden för Selångersån och Ljungan, MSB:s flödeskarteringar, Länsstyrelsens lågpunkter och rinnvägar, MSVA:s dagvattenområden och höjdkurvor med 1 m mellanrum. | Mycket relevant, men tjänstens villkor tillåter bara Sundsvall, Timrå, Härnösand, Kramfors och Örnsköldsvik om inget annat avtalas. Kräver skriftligt tillstånd. |
| Bräddningsdata från MSVA | Inte publik. Begärd för tio dagar runt 16 augusti, bara Sundsvall. | Väntar på MSVA. |

Om en egen WMS ("VMS" i anteckningen) som kommunen läser in i sin karta: deras
Origo-kartor använder EPSG:3006. Kartsidans Content-Security-Policy tillåter
externa bilder (`img-src *`), men andra anrop bara till `karta.sundsvall.se` och
`karta.timra.se`, så klick-info och WFS från vår server blockeras om de inte lägger
till den.

### Öppna nationella källor

- SMHI:s öppna hydrologiska data har ingen station i Selångersån; Ljungan
  (Skallböle) och Indalsälven (Bergeforsen) saknar data efter februari 2026.
- MSB:s översvämningskarteringar finns som visningstjänst utan begränsningar för
  allmänheten enligt INSPIRE-posten. WMS-adressen är inte framtagen än.
  Portal: <https://gisapp.msb.se/Apps/oversvamningsportal/>
- Ingen nationell öppen datamängd för dagvatten eller avlopp hittades.

## Antaganden, inte verifierade

- Lantmäteriets Markhöjdmodell grid 1+ är CC0 enligt sökresultat; sidorna gick inte
  att läsa. Copernicus DEM, som branddemon redan använder, är alternativet.
- En SMHI-varning för delar av Timrå och Sundsvall nämns i ett sökresultat, men
  källan (Sveriges Radio) gick inte att läsa.
- Stationen i Söråker (22228110) ger orimliga värden och bör uteslutas. Sidsjö D
  saknar data 14–16 augusti.
- Kommunens bräddgivare kan redan gå via diwise, eftersom `Sewer` finns där.

## Vad i branddemon som återanvänds

Skärmarna och layouten, scenarioklockan, mission control, satellitbevakningen med
loggen, IoT, den spårbara bedömningen, frågorna, 2D- och 3D-kartorna och
satellitbilderna. Det som byts är händelsemodulen:

| Brand (Västmanland 2014) | Översvämning (Sundsvall 2026, scenario) |
|---|---|
| FIRMS-detektioner | Nederbörd från kommunens mätare, vatten i Sentinel-1-bilder |
| Brandspridning och prognos | Skyfalls- och flödeskarteringar (MSB; kommunens efter tillstånd) |
| Vindpilar | Nederbördsintensitet |
| Sensorer för värme och rök | Bräddning och nivå i diwise-formen, montrens WATER-nod |
| Orter inom prognosen | Byggnader och vägar i riskområdet |

Västmanland 2014 är i dag hårdkodat i ett tjugotal filer, främst
`app/backend/scenario.py`, `server.py`, `forecast.py`, `spatial.py`,
`tools/load_postgis.py`, `docker-compose.yml`, `map3d.js` och HTML-filerna.

Föreslagen ordning: (1) scenariofil per demo och `data/<scenario>/`, med branddemon
oförändrad; (2) öppna data för Sundsvall; (3) översvämningsmodulen; (4) som tillval
en WMS för kommunens Origo-karta.

## Öppna frågor

- Skriftligt tillstånd från kommunen för lagren i bxkarta.
- Bräddningsdata från MSVA: format, positioner och om de får visas offentligt.
- Vad som faktiskt hände i Sundsvall 16 augusti: platser, tider och rapporter, om
  scenariot ska knytas närmare till händelsen.
- WMS-adressen för MSB:s karteringar och licensen för Lantmäteriets höjdmodell.
