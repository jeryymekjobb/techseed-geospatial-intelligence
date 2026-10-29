// Roads and railways the incident damaged and those under heavy rain (routes.py): which of them
// the maps draw at a moment of the scenario clock. Pure, so it can be tested in Node.
"use strict";

// The documented damage with a place that the clock has reached, oldest first.
function routeImpactsAt(impacts, clockMs) {
  return (impacts || []).filter((item) => item.latitude !== undefined && Date.parse(item.time_utc) <= clockMs);
}

// 0 below the first threshold, 1 above it, 2 above the second, from a piece's rain since the
// playback's start at the end of each hour (`mm`): before the first hour has passed nothing has fallen.
function routeExposureClass(mm, hoursSinceStart, thresholds) {
  const index = Math.floor(hoursSinceStart) - 1;
  if (index < 0 || !mm?.length) return 0;
  const rain = mm[Math.min(index, mm.length - 1)];
  return thresholds.filter((limit) => rain >= limit).length;
}

// The computed pieces that have passed a threshold at the clock, each with its class and rain so far.
function routeExposureAt(exposure, clockMs) {
  if (!exposure) return [];
  const hours = (clockMs - Date.parse(exposure.start_utc)) / 3600000;
  const index = Math.min(Math.floor(hours) - 1, exposure.hours - 1);
  return exposure.pieces
    .map((piece) => ({ ...piece, level: routeExposureClass(piece.mm, hours, exposure.thresholds_mm), rain: index >= 0 ? piece.mm[index] : 0 }))
    .filter((piece) => piece.level > 0);
}

// A piece's colour by its class, and the damage's by its kind, on both maps; a marked object, such
// as embankments, has its own colour.
const ROUTE_EXPOSURE_COLOURS = { 1: "#f2b705", 2: "#d62828" };
const ROUTE_IMPACT_COLOURS = { road: "#d62828", rail: "#111111" };
const ROUTE_MARKER_COLOURS = { embankment: "#7c4a1e" };

// Where the maps put an item and what its tooltip says: a marked object (`marker`) at its own place,
// with its label and note; the damage at its place, with the report's text.
function routeImpactMarker(item, timeText) {
  const when = `${timeText}${item.approximate_time ? " (tid ungefärlig)" : ""}`;
  const source = item.source_label || "Länsstyrelsen, utredning 2026";
  if (item.marker) {
    return { latitude: item.marker_latitude ?? item.latitude, longitude: item.marker_longitude ?? item.longitude,
             title: item.label || item.text, detail: `${item.text}, ${when}. ${item.note || "Plats ungefärlig"}. Källa: ${source}.` };
  }
  return { latitude: item.latitude, longitude: item.longitude, title: item.text, detail: `${when} · plats ungefärlig · ${source}` };
}

if (typeof module !== "undefined") {
  module.exports = { routeImpactsAt, routeImpactMarker, routeExposureClass, routeExposureAt, ROUTE_EXPOSURE_COLOURS,
                     ROUTE_IMPACT_COLOURS, ROUTE_MARKER_COLOURS };
}
