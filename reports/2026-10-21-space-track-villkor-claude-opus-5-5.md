# Space-Tracks villkor för att visa satellitpositioner i publik

Datum: 2026-10-21
Författare: Claude Opus 5.5 (`claude-opus-5-5`), via Claude Code, på uppdrag av
Techseed. Undersökningen gäller backlogposten om Space-Tracks användaravtal. Den är inte
juridisk rådgivning.

## Fråga

Får demon visa satellitpositioner beräknade ur Space-Tracks banelement offentligt på en
utställning, och får banelementen följa med demon, till exempel på en USB-sticka?

## Vad demon använder

`tools/fetch_tle_history.py` hämtar GP-banelement (TLE) ur `gp_history` för scenariernas
satelliter. Skärmarna räknar fram positioner och banor ur dem med SGP4 (satellite.js).
Banelementfilerna ligger i ej versionerade `data/…/tle/` och följer med när demon kopieras.

## Vad villkoren säger

Ur https://www.space-track.org/documentation, läst 2026-10-21:

- **Användaravtalet** ("Current as of 1 August 2019"): "The User agrees not to transfer any
  data or technical information received from this website, or other U.S. Government source,
  including the analysis of data, to any other entity without prior express approval."
- **Redistribution of Basic SSA Information**: basic SSA data är "Two-Line Elements (TLEs)
  and Orbital Mean-element Messages (OMMs); SATCAT; and Satellite Decay and Reentry Data", och
  "USSPACECOM has provided express blanket approval for transfer/redistribution of basic SSA
  data and services accessed via www.Space-Track.org conditioned on appropriate citation."
  Vidare: "Publications of analysis based on USSPACECOM data also require appropriate
  citations."
- För annan data hänvisar sidan till en Orbital Data Request. Villkoren kan ändras utan
  förvarning.

## Bedömning

- Demons banelement är basic SSA data (TLE/GP) och omfattas av det generella godkännandet.
  De får föras vidare, till exempel på en USB-sticka, med källhänvisning.
- Positioner och banor beräknade ur dem och visade på utställningen är en publicering av
  analys av USSPACECOM:s data; det kräver också källhänvisning.
- Vad "appropriate citation" ska innehålla anges inte. Data är USSPACECOM:s, så hänvisningen
  bör nämna både USSPACECOM och Space-Track.org.
- Ingen Orbital Data Request behövs för det demon gör i dag.

## Ändrat i demon

Källtexten under satellitlistan och i satellitmonitorn är nu "USSPACECOM via Space-Track.org
(banelement, gp_history), hämtad …", och kartornas källhänvisning har "Banelement: USSPACECOM
via Space-Track.org" (`satellites.py`, `panel.js`).

## Källor

- Space-Track.org, Documentation (User Agreement; Redistribution of Basic SSA Information):
  https://www.space-track.org/documentation
- Spaceflight Now (2005), om avtalets tidigare villkor:
  https://spaceflightnow.com/news/n0503/02observing/index2.html
- Libre Space Foundation, avtal med US Space Command (Orbital Data Request):
  https://community.libre.space/t/libre-space-signs-agreement-with-us-space-command/8175
