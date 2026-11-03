// The 2D main screen of the monitoring (app/monitoring/service.py), the other page of mission
// control's VISA 2D / VISA 3D as in the scenarios (app/frontend/kiosk.js viewPage): the municipality's
// map with OSM under and over it (/api/config's maps), the border, SMHI's stations, FIRMS's
// detections, the events in and the current alarms from /api/state. It follows mission control's
// choice of view (/api/view) and goes to the 3D globe when it changes. Tooltips are set as text.
"use strict";

const STATE_MS = 30000;
const VIEW_MS = 2000;

// Leaflet shows a tooltip given as a string as HTML: text from the sources is given as a text node.
function tip(text) {
  return document.createTextNode(String(text ?? ""));
}

const map = L.map("map");

// The base maps as the screens share them (/api/config's maps): the municipality's map over the
// offline OpenStreetMap, which shows where the municipal map is white, and OSM's road numbers and
// railway tunnels over both; online OSM only when neither is there.
function addBaseMaps(maps) {
  if (maps.offline) L.tileLayer(maps.offline.url, { maxZoom: 18, attribution: maps.offline.attribution }).addTo(map);
  for (const item of maps.municipal) {
    const [west, south, east, north] = item.bbox;
    L.tileLayer(item.url, { minZoom: item.min_zoom, maxNativeZoom: item.max_zoom, maxZoom: 18, attribution: item.attribution,
      bounds: [[south, west], [north, east]] }).addTo(map);
  }
  if (maps.overlay) L.tileLayer(maps.overlay.url, { maxZoom: 18, attribution: maps.overlay.attribution }).addTo(map);
  if (!maps.offline && !maps.municipal.length) {
    L.tileLayer(maps.online.url, { maxZoom: 18, attribution: maps.online.attribution }).addTo(map);
  }
}

const layers = { border: L.layerGroup().addTo(map), sites: L.layerGroup().addTo(map), alarms: L.layerGroup().addTo(map) };
let placed = false;

function marker(layer, lat, lon, style, text) {
  L.circleMarker([lat, lon], style).bindTooltip(tip(text)).addTo(layer);
}

function drawMap(state) {
  const context = state.context || {};
  if (!placed) {
    const [west, south, east, north] = state.area.bbox;
    map.fitBounds([[south, west], [north, east]]);
    placed = true;
  }
  layers.border.clearLayers();
  if (context.border) {
    L.geoJSON(context.border, { style: { color: "#1565c0", weight: 2, fill: false } }).addTo(layers.border);
  }
  layers.sites.clearLayers();
  for (const flow of context.flows || []) {
    if (flow.latitude == null) continue;
    const limits = flow.limits ? ` (högt över ${flow.limits.high}, rekord ${flow.limits.record})` : "";
    marker(layers.sites, flow.latitude, flow.longitude, { radius: 6, color: "#0277bd" },
      `${flow.name}: ${flow.value} m³/s ${flow.time_utc}${limits} – SMHI`);
  }
  for (const rain of context.rain || []) {
    if (rain.latitude == null) continue;
    marker(layers.sites, rain.latitude, rain.longitude, { radius: 5, color: "#2e7d32" }, `${rain.name}: ${rain.mm_24h} mm senaste 24 h – SMHI`);
  }
  for (const point of context.firms || []) {
    marker(layers.sites, point.latitude, point.longitude, { radius: 4, color: "#e65100" },
      `FIRMS ${point.instrument} ${point.satellite} ${point.time_utc}`);
  }
  for (const event of state.events || []) {
    marker(layers.sites, event.latitude, event.longitude, { radius: 5, color: event.simulated ? "#b8860b" : "#6a1b9a" },
      `${event.kind_word} ${event.time_utc} – ${event.source}${event.simulated ? " (simulerad)" : ""}`);
  }
  layers.alarms.clearLayers();
  for (const alarm of state.alarms) {
    const c = alarm.candidate;
    if (c.latitude == null || !alarm.current || alarm.state === "dismissed") continue;
    marker(layers.alarms, c.latitude, c.longitude, { radius: 11, color: alarm.state === "new" ? "#c62828" : "#1565c0", weight: 3 }, c.title);
  }
}

async function getJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

function followView() {
  getJson("/api/view").then((body) => { if (body.view === "3d") window.location.assign("/3d.html"); }).catch(() => null);
}

getJson("/api/config").then((config) => {
  document.getElementById("title").textContent = `Övervakning – ${config.area.name}`;
  document.title = `Övervakning – ${config.area.name} – 2D`;
  addBaseMaps(config.maps);
}).finally(() => {
  const refresh = () => getJson("/api/state").then(drawMap).catch(() => null);
  refresh();
  setInterval(refresh, STATE_MS);
  setInterval(followView, VIEW_MS);
});
