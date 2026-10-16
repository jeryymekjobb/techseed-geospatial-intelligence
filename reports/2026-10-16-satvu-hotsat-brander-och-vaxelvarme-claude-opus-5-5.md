# Satellite Vu (HotSat): bränderna 2014 och 2018, och växelvärme

Datum: 2026-10-16. Sammanställt av Claude Opus 5.5 ur två utredningar i öppna källor. Inga
konton är skapade och inga data beställda. Siffrorna om satelliterna kommer från SatVu, UP42 och
fackpress; beräkningarna i del 3 är egna överslag, inte mätningar.

## Sammanfattning

- **Bränderna i Västmanland 2014 och vid Kårböle 2018:** HotSat-satelliterna kan inte tillföra
  verkliga data. Den första sköts upp i juni 2023, fem till nio år efter bränderna.
- **Växelvärme:** löpande övervakning av enskilda växlar går inte. En kontroll några gånger per vinterhalvår, som projektet tänker sig, är möjlig som ögonblicksbild av en hel bangård en
  klar, kall natt med snötäcke kan möjligen visa en växel som är kall bland varma. Löpande
  övervakning sker redan på marken: Trafikverkets system ÖVV styr och övervakar cirka 7 200
  uppvärmda växlar.

## 1. Satelliterna (läget 2026-10-16)

| Satellit | Status | Källa |
|---|---|---|
| HotSat-1 | Uppskjuten juni 2023, kameran slutade fungera december 2023 | <https://imveurope.com/article/hotsat-1-thermal-imaging-satellite-fails-orbit> |
| HotSat-2 | Uppskjuten 2026-03-30, kommersiell drift sedan 2026-06-29 | <https://satnews.com/2026/06/29/satvu-initiates-commercial-operations-for-hotsat-2-thermal-satellite/> |
| HotSat-3 | Uppskjuten cirka 2026-10-01, tas i drift | <https://itbrief.co.uk/story/satvu-launches-hotsat-3-to-double-thermal-imaging-capacity> |

Mellanvågs-IR (natt 3,7–4,95 µm), 3,5 m upplösning, scener på cirka 4,5 × 3,5 km, med två
satelliter en bild per dygn och plats. Ser inte genom moln. Katalogen kräver konto och kontrakt
(en sökning utan konto gav HTTP 401); SatVu tar på eget initiativ bara bilder av "key global
locations". Pris hos UP42 cirka 57 000 credits per arkivscen och 114 000 per beställd scen
(<https://docs.up42.com/data/satvu>). SatVu är Copernicus Contributing Mission sedan juni 2025; inget
deltagande i International Charter hittades.

## 2. Ljusdal 2018 och Västmanland 2014

Det finns inga HotSat-bilder av bränderna, och kommer inte att finnas. Scenarierna har redan
FIRMS (MODIS, VIIRS), Landsat och Sentinel-2 från tiden. En illustration av vad HotSat skulle ha
sett vore simulerad och strider mot projektets regel att inte hitta på satellitobservationer,
om den inte märks mycket tydligt. Rekommendation: lägg inte till HotSat i dessa scenarier.

I ett framtida scenario, efter juni 2026, kan HotSat-2 och -3 vara relevanta för bränder: 3,5 m
nattliga värmebilder av en brandfront, i scener som måste beställas i förväg för rätt plats.

## 3. Växelvärme i spårväxlar

### Prejudikat

Inget belagt exempel hittades där satellit-IR (SatVu, Landsat, ECOSTRESS, Hydrosat, OroraTech,
constellr) används för växelvärme eller snösmältning på spår. SatVu nämner järnväg bara i sin
första bild 2023 (lok och tåg i Chicago, enligt bolaget) och "transport networks" i allmänhet.
Det som finns är markbaserat, till exempel LWIR-kameror på mast som ser växlar på upp till cirka
600 m (<https://www.exosens.com/news/dual-band-monitoring-keeps-trains-running-winter>).

### Fysik (överslag)

- En svensk växel har cirka 300 W/m och 10–30 kW, värme främst i tungpartiet, cirka 15–25 m långt
  och 2,5 m brett (<https://link.springer.com/chapter/10.1007/978-3-032-04774-8_41>,
  <https://www.globalrailwayreview.com/swedish-study-proposes-smarter-switch-heating-to-cut-winter-rail-disruptions/1367740.article>).
- Börvärde cirka +8 °C (KTH), 20–30 °C enligt Trafikverket Stockholm 2025; oklart om element
  eller räl.
- Fyra rälhuvuden på 72 mm ger cirka 0,4 m varmt stål tvärs spåret, **cirka 11 % av en bildpunkt**.
- Överslag i MWIR vid −15 °C omgivning och +8 °C räl: blankt rälhuvud (emissivitet cirka 0,3)
  speglar kall himmel och ger **cirka 0 K** kontrast; rostigt stål **+2 till +3 K**; med snötäcke
  där 30–50 % av bildpunkten smält till cirka 0 °C **+5 till +8 K**.
- SatVu anger känsligheten "< 2°"; vid −15 °C är signalen bara cirka 18 % av den vid +27 °C, så
  bruset blir sannolikt flera grader. Till det kommer utsmetning och lägesfel på flera meter.
- Följd: en helt kall växel bland varma kan i bästa fall synas vid snötäcke. Ett trasigt element
  eller en enda skena syns inte.

### Väder

Klar himmel cirka 26–27 % av tiden i Stockholm november–januari
(<https://weatherspark.com/y/84156/Average-Weather-in-Stockholm-Sweden-Year-Round>); grovt 4–8
användbara nätter per månad. Snöfallen, då värmen behövs mest, är molniga.

### Övervakning som finns

- Trafikverket styr och övervakar cirka 7 200 uppvärmda växlar centralt i ÖVV (IMSE WebMasterPro;
  TRVINFRA-00141, TRVINFRA-00017, TDOK 2021:0284):
  <https://bransch.trafikverket.se/for-dig-i-branschen/teknik/anlaggningsteknik/vaxelvarmestyrning/>
- Vossloh har avtal om tillståndsövervakning av 1 000 växlar; VTI har en förstudie om prognosstyrd
  växelvärme (<https://projektdatabas.vti.se/bib/4092>).
- Jernhusen äger och förvaltar depåer, till exempel Hagalund. Vem som äger och underhåller
  depåväxlarna och deras värme är inte belagt och bör frågas direkt.

### Kontroll några gånger per vinterhalvår

Projektet tänker sig en kontroll några få gånger per vinterhalvår, inte löpande övervakning. Det
passar satelliten bättre:

- En scen på cirka 4,5 × 3,5 km täcker en hel depå eller bangård, till exempel Hagalund, i en bild.
- Kontrollen behöver inte ske en viss natt. En beställning med ett fönster på några dagar till en
  vecka, villkorad på klar himmel, räcker; med 4–8 användbara nätter per månad bör det gå att få
  tre till fem bilder per vinter.
- Det som kan avgöras är grovt: att en växel är helt kall bland varma, och bäst när det ligger snö.
  Delfel (ett element, en skena) och växlar i tunnel, under tak eller i skugga av byggnader avgörs
  inte. Bilden visar dessutom bara läget den natten, inte vid nästa snöfall.
- Kostnaden blir cirka 114 000 UP42-credits per beställd scen och kontroll, alltså några hundra
  tusen credits per vinter och depå, om priset gäller (omräkningen till euro är inte kontrollerad).
- Kontrollens värde jämfört med ÖVV är att den ser resultatet på spåret (snö smält eller inte),
  inte bara att styrningen är på. Den ersätter inte ÖVV:s larm.

Rekommendation: pröva först en pilot (nedan) för att se om en kall växel alls syns. Faller den
väl ut kan samma beställning upprepas några gånger per vinter.

### Om man vill pröva

En engångsstudie, inte övervakning: två eller tre beställda scener över en depå, till exempel
Hagalund, en klar och kall natt med snötäcke. Samtidigt markmätning med handhållen IR-kamera,
loggar ur ÖVV eller växelns styrskåp och en avsiktligt avstängd växel som referens. För
löpande övervakning är ström- och temperaturmätning i styrskåpet eller en kamera på mast billigare
och fungerar i alla väder; det passar också demonstratorns IoT-del.
