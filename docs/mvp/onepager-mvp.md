# Techseed Geospatial Intelligence – MVP

Utkast 2026-11-02. Bygger på användarens stolpar (`new-one-pager.md`) och besluten samma dag.
Det som är märkt **Förslag** är inte beslutat.

## Syfte

1. **Rädda liv och skydda egendom och kritisk infrastruktur.** Detta är det viktigaste syftet.
   Geospatial Intelligence övervakar dygnet runt och upptäcker tidigt brand, översvämning, erosion
   och skred som hotar människor, bebyggelse och kritisk infrastruktur. Med kritisk infrastruktur
   menas till exempel elnät, vatten och avlopp, vägar, järnvägar, telekommunikation och anläggningar
   för vård och räddning. Tjänsten larmar ansvarig operatör och ger räddningsledaren och den som
   ansvarar för infrastrukturen en lägesbild med fakta.
2. **Visa vad som går att åstadkomma.** Demonstratorn spelar upp verkliga, historiska händelser
   med satellit-, väder- och kartdata, så att beslutsfattare ser vad som är möjligt. Den har
   16 scenarier i dag.

Bakgrund: det finns ett nationellt intresse av att kommuner och regioner använder mer satellitdata.

## Målbild

- **Kartor.** Kommunens eller kundens GIS-kartor är standard. OpenStreetMap används bara som
  reserv när GIS-data saknas. Olika slags GIS-data ska stödjas: ArcGIS, WMS och WFS, GeoPackage,
  Shapefile och GeoJSON. Lösningen från scenariot Sundsvall 2026 används genomgående där den behövs:
  kommunens karta hämtas via WMS och sparas lokalt, med OSM:s vägnummer och järnvägstunnlar ovanpå.
- **Händelser in**, som JSON eller CSV/TSV. En händelse kan upptäckas genom en mätning eller på
  annat sätt, till exempel en satellitdetektion, en observation eller en rapport. Varje rad är:

  `<datum> <klockslag> <händelse> <koordinat 1> <koordinat 2> <koordinatsystem> <källa>`

  - Datum och klockslag anges i UTC.
  - Händelse är brand, översvämning, erosion eller skred.
  - Koordinatsystemet är antingen WGS 84 (EPSG:4326), där koordinat 1 är latitud och koordinat 2
    longitud, eller SWEREF 99 TM (EPSG:3006), där koordinat 1 är norr och koordinat 2 öst, i meter.
  - Källan anges alltid, liksom om data är simulerade.
- **Källor.**
  - IoT-sensorer i terrängen, på strategiskt valda platser.
  - Satellitdata, färdigbearbetade ombord eller rådata som bearbetas på marken.
  - Drönare, övervakningsflyg och helikoptrar.
  - Värmekameror och vanliga bilder.
  - Väderstationer.
  - Sensorer i fordon i området.
- **Sensorfusion.** Flera källor används tillsammans för att bygga upp en bild av vad som händer på
  marken.
- **Prognoser.**
  - Befintliga prognosmodeller för hur till exempel en brand utvecklas.
  - Väderprognoser från SMHI som standard, kompletterat med NOAA, MET Norway (Yr), Klart och andra
    europeiska vädertjänster, till exempel ECMWF, DMI och FMI.
  - Riskprognoser, till exempel SMHI:s om förhöjd brandrisk i skog och mark och om höga flöden i
    vattendrag.
  - Prognoser för erosion och risk för skred. Exempel att komplettera: Säve–Tuve 1977, Småröd i
    Munkedal 2006, ett nyare skred och flera i Göta älvdalen. Trolig källa är SGI.
- **Övervakning dygnet runt, året om,** med omedelbart larm till ansvarig operatör vid en anomali.
  Larm i onödan ska undvikas. Exempel: en brand i naturen ska kunna skiljas från en majbrasa.
- **Briefing till räddningsledaren:** vad som sker just nu, omfattningen och relevanta fakta.
- **Kontaktlistor** för vem som ska kontaktas vid varje typ av händelse.

## Förslag: MVP:n är den första operativa kedjan

**Ingår**

- Kommunens GIS-lager in, med OSM som reserv och skyddsvärda objekt som eget lager. Exempel på
  skyddsvärda objekt: skolor, äldreboenden, vattenverk, vägar, järnvägar och elanläggningar.
- Händelser in i formatet ovan, och ett urval aktuella källor i nära realtid, till exempel SMHI:s
  varningar och observationer, NASA FIRMS brandpunkter och Sentinel-bilder.
- Upptäckt och **larm som operatören bekräftar** innan något skickas vidare. Ingen åtgärd sker
  automatiskt.
- Minskade falsklarm genom flera källor:
  - samma punkt vid flera satellitpassager eller i flera sensorer,
  - kända värmekällor,
  - kalender, som valborg, och anmälda eldningar där sådana finns,
  - bekräftelse från en andra källa.
- **Briefing** som en sida eller utskrift, där varje påstående har sin källa och det som är osäkert
  är markerat. Dagens spårbara bedömning är grunden.
- **Kontaktlistor per händelsetyp och roll.** Roller i stället för namn håller personuppgifterna få.
- Demonstratorns historiska scenarier finns kvar för syfte 2.

**Utanför MVP:n, men med i målbilden och i händelseformatet**

- Drönare, flyg, helikoptrar, fordon och bearbetning ombord på satelliter.
- Full drift dygnet runt med avtalad tillgänglighet. MVP:n kan i stället köras kontinuerligt under
  en provperiod.
- En egen brandspridningsmodell. Den utreds, och dagens prognos finns som grund.

## Förslag: framgångsmått

- Tid från satellitpassage eller mätning till larm hos operatören.
- Andel larm som operatören avfärdar som falska.
- Tid från larm till färdig briefing.
- Antal kommuner och regioner som använder satellitdata genom tjänsten.
- Vilka satellitkällor som bidrog till varje larm och briefing.

## Att utreda

- Hur konton och åtkomst till alla data sätts upp, och på vilka villkor data får användas.
- Hur brandmodellerna fungerar.
- Utbudet av satelliter.
- Vilka europeiska vädertjänster som tas med, och varifrån Klart får sina data.

## Risker och regelverk

Underlaget finns i `docs/mvp/regelverksregister.md`.

- **Datarättigheter per källa:** R-GEO-05.
- **Personuppgifter i kontaktlistor:** R-DP-01.
- **AI-förordningen**, om bedömning eller briefing räknas som AI-system. För högrisksystem som är
  avsedda för myndigheter gäller kraven senast 2 augusti 2030: R-AI-01–03.
- **Cybersäkerhet**, om drift hos kommun eller region: R-CS-02 och R-CS-03.
- **Säkerhetsskydd:** sammanställda lägesbilder över kritisk infrastruktur kan bli
  säkerhetsskyddsklassificerade (R-CS-06). För den som äger infrastrukturen kan även NIS2 och
  cybersäkerhetslagen bli aktuella (R-CS-02 och R-CS-03).

## Öppna frågor

- Vem som är beställare och användare, och om beställaren får nämnas.
- Vilken händelsetyp och vilket område MVP:n börjar med.
- Om MVP:n levereras till kommuner och regioner eller körs av Techseed.
- Om elnätet från OSM får visas (beslut B3 i `CONTEXT.md`), och vilka data om kritisk
  infrastruktur som får användas.
