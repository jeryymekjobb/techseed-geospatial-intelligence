# Satellitdata om branden i Västmanland 2014

Arkivdatum: 2026-10-01 (Europe/Stockholm).
Samtalet inleddes 2026-09-30. Källhänvisningar har gjorts om till vanliga länkar för att fungera utanför chatten.

## Användarens fråga

Hur kan jag hämta satelitdata från https://earthexplorer.usgs.gov/ om branden i Västmanland 2014?

## Assistentens svar

**Börja med Landsat 8 och sök efter den 4 augusti 2014.** Det finns en bekräftad satellitbild från den dagen där branden och rökplymerna syns. För att undersöka brandskadorna behöver du även bilder före och efter branden. [NASA](https://science.nasa.gov/earth/earth-observatory/wildfire-in-sweden-84155/)

Gör så här i [USGS EarthExplorer](https://earthexplorer.usgs.gov/):

1. **Logga in eller skapa ett konto.**
   Landsat-data är gratis, men du behöver vara inloggad för att ladda ner bilderna. [Landsat Data Access](https://www.usgs.gov/landsat-missions/landsat-data-access), [EarthExplorer](https://earthexplorer.usgs.gov/)

2. **Ange området under `Search Criteria`.**
   Välj decimalgrader och använd följande som ungefärlig sökpunkt i brandområdet:

   | Fält | Värde |
   |---|---:|
   | Latitude | `59.9` |
   | Longitude | `16.2` |

   Använd punkt som decimaltecken. Du kan också markera en polygon på kartan kring området mellan **Ramnäs, Virsbo, Ängelsberg och Salbohed**. Sökpunkten är till för att hitta överlappande satellitbilder; den beskriver inte brandens gräns. EarthExplorer stöder både koordinater och kartmarkerade sökområden. [EarthExplorer](https://earthexplorer.usgs.gov/)

3. **Ange datum under `Date Range`.**
   Mitt förslag är att börja med hela perioden **1 juni–30 september 2014**, eller göra tre separata sökningar:

   | Syfte | Från – till | Inmatning om formatet är `mm/dd/yyyy` |
   |---|---|---|
   | Före branden | 1 juni–30 juli 2014 | `06/01/2014`–`07/30/2014` |
   | Pågående brand | 31 juli–11 augusti 2014 | `07/31/2014`–`08/11/2014` |
   | Brandens efterverkningar | 12 augusti–30 september 2014 | `08/12/2014`–`09/30/2014` |

   För den kända bilden: ange **`08/04/2014` i båda datumfälten**. NASA bekräftar att Landsat 8 fotograferade branden den dagen. [NASA](https://science.nasa.gov/earth/earth-observatory/wildfire-in-sweden-84155/)

4. **Välj dataset under `Data Sets`.**
   Öppna följande:

   ```text
   Landsat
     → Landsat Collection 2 Level-2
       → Landsat 8-9 OLI/TIRS C2 L2
   ```

   Det gemensamma datasetet innehåller Landsat 8-data från 2014. Level-2 innehåller bland annat atmosfärskorrigerad ytreflektans, vilket passar för jämförelser av mark och vegetation mellan olika datum. [USGS Surface Reflectance](https://www.usgs.gov/landsat-missions/landsat-collection-2-surface-reflectance)

5. **Visa `Results` och granska bilderna.**
   Börja gärna utan strikt molnfilter. Kontrollera bildens **Footprint** och förhandsvisning, **Browse**, så att själva brandområdet täcks och är synligt. För före- och efterbilder: prioritera fri sikt över brandområdet. För bilden under branden är röken en del av det du vill se.

6. **Ladda ner satellitdata via `Download Options`.**
   Välj **Level-2 Product Bundle** om du vill ha hela datapaketet. Det går också att hämta enskilda band. Välj själva dataprodukten för analys; förhandsvisningen är främst till för att bedöma bilden. Landsat Collection 2 levereras som georefererade GeoTIFF-filer, med möjlighet att ladda ner hela paket eller valda band. [USGS Collection 2 faktablad](https://pubs.usgs.gov/fs/2021/3002/fs20213002.pdf)

**Om du vill analysera hur mycket som brann:** spara framför allt band **5 och 7**, kvalitetsbanden och metadata från en bild före och en efter branden. Band 5 och 7 används till brandindexet **NBR**:

```text
NBR = (B5 - B7) / (B5 + B7)
```

Beräkningen ska använda ytreflektans efter att produktens skalfaktor och offset tillämpats, och moln samt molnskuggor behöver maskeras. USGS beskriver NBR som ett index för att identifiera brända områden och bedöma brandpåverkan. [USGS NBR](https://www.usgs.gov/landsat-missions/landsat-normalized-burn-ratio)

Du kan först se hur bilden från **4 augusti** ser ut på [NASA:s sida om branden](https://science.nasa.gov/earth/earth-observatory/wildfire-in-sweden-84155/).

## Användarens begäran om arkiv, 2026-10-01

Skapa ett daterat och gzippat arkiv för nedladdning.
