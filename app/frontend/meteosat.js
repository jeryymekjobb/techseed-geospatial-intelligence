// Meteosat's fire pixels over the incident (meteosat.py): which of them the maps draw at a moment of
// the scenario clock, and how. Pure, so it can be tested in Node.
"use strict";

// Purple, apart from FIRMS's red and orange points.
const METEOSAT_COLOUR = "#7b2cbf";

// The pixels whose quarter the clock has reached; they stay, as FIRMS's detections do.
function meteosatPixelsAt(pixels, clockMs) {
  return (pixels || []).filter((pixel) => Date.parse(pixel.time_utc) <= clockMs);
}

// More opaque the more power: from 0.1 to 0.3 at 3000 MW, so the image and FIRMS's points show through.
function meteosatOpacity(frpMw) {
  return 0.1 + 0.2 * Math.min(1, Math.max(0, frpMw || 0) / 3000);
}
// The rectangle's edge.
const METEOSAT_EDGE_OPACITY = 0.7;

// The text on both maps.
function meteosatText(pixel, when) {
  return `${pixel.satellite} (SEVIRI): ${Math.round(pixel.frp_mw)} MW i en pixel på ${Math.round(pixel.pixel_area_km2)} km²`
    + ` – kvarten från ${when}. LSA SAF, arkivdata, inte live; pixelns läge och form är ungefärliga.`;
}

if (typeof module !== "undefined") module.exports = { METEOSAT_COLOUR, METEOSAT_EDGE_OPACITY, meteosatPixelsAt, meteosatOpacity, meteosatText };
