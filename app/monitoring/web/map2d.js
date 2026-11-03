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
const OFFLINE_MIN_ZOOM = 8;
// The offline map takes the place of OpenStreetMap's own after this many tiles it could not fetch.
const ONLINE_FAILURES = 5;

// The base maps (/api/config's maps): OpenStreetMap's standard map everywhere, which has land cover
// at every zoom and no edge; the municipality's own map over it; and over that, only inside the
// municipality, the road numbers and railway tunnels it lacks. Without the net the demos' offline
// map takes OpenStreetMap's place over its area.
function addBaseMaps(maps) {
  let failures = 0;
  let offline = null;
  const online = L.tileLayer(maps.online.url, { maxZoom: 18, zIndex: 1, attribution: maps.online.attribution }).addTo(map);
  online.on("tileerror", () => {
    failures += 1;
    if (offline || !maps.offline || failures < ONLINE_FAILURES) return;
    const [west, south, east, north] = maps.offline.bbox;
    offline = L.tileLayer(maps.offline.url, { minZoom: OFFLINE_MIN_ZOOM, maxZoom: 18, zIndex: 2, attribution: maps.offline.attribution,
      bounds: [[south, west], [north, east]] }).addTo(map);
  });
  for (const item of maps.municipal) {
    const [west, south, east, north] = item.bbox;
    L.tileLayer(item.url, { minZoom: item.min_zoom, maxNativeZoom: item.max_zoom, maxZoom: 18, zIndex: 3, attribution: item.attribution,
      bounds: [[south, west], [north, east]] }).addTo(map);
  }
  if (maps.overlay && maps.municipal.length) {
    L.tileLayer(maps.overlay.url, { minZoom: OFFLINE_MIN_ZOOM, maxZoom: 18, zIndex: 4, attribution: maps.overlay.attribution }).addTo(map);
  }
}

// The scenarios' overlays: MCF's flood map (WMS) and SMHI's radar, whose image is asked again after
// every poll (/api/state's polled_utc), when a newer one may have come.
let radarLayer = null;
let radarShown = null;
function addOverlays(config) {
  const flood = config.layers.flood;
  if (flood) {
    L.tileLayer.wms(flood.url, { layers: flood.layers, format: "image/png", transparent: true, opacity: 0.6, styles: "",
      attribution: flood.attribution }).addTo(map);
  }
  const [west, south, east, north] = config.layers.radar.bbox;
  radarLayer = L.imageOverlay("data:,", [[south, west], [north, east]], { opacity: 0.85, attribution: config.layers.radar.attribution })
    .addTo(map);
}

function drawRadar(radar, polled) {
  const key = `${radar?.latest_utc}|${polled}`;
  if (!radarLayer || !radar?.latest_utc || key === radarShown) return;
  radarShown = key;
  radarLayer.setUrl(`/api/radar.png?at=${encodeURIComponent(key)}`);
}

const layers = { border: L.layerGroup().addTo(map), sites: L.layerGroup().addTo(map), alarms: L.layerGroup().addTo(map) };
let placed = false;

function marker(layer, lat, lon, style, text) {
  L.circleMarker([lat, lon], style).bindTooltip(tip(text)).addTo(layer);
}

function drawMap(state) {
  const context = state.context || {};
  drawRadar(context.radar, state.polled_utc);
  refreshWeather(context.weather);
  if (!placed) {
    const [west, south, east, north] = state.area.bbox;
    areaBounds = [[south, west], [north, east]];
    map.fitBounds(areaBounds);
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

// SMHI's forecast grid (/api/weather), as the scenarios' wind arrows and weather chart: the arrows
// over the area (wind_barbs.js) and the chart over Scandinavia, isobars with highs and lows, the hour's
// rain and the thunder. Mission control's VINDPILAR and VÄDERKARTA show them (/api/view's layers);
// the chart shows Scandinavia, and the area again when it goes.
const CHART_BOUNDS = [[55, 4], [70, 31]];
const windLayer = L.layerGroup();
const chartLayer = L.layerGroup();
let weatherShown = null;
let shownLayers = {};
let areaBounds = null;

function drawWeather(data) {
  windLayer.clearLayers();
  for (const point of data.wind || []) {
    const svg = windBarbSvg(point.speed_ms).replace("<svg ", `<svg style="transform: rotate(${(point.from_deg + 180) % 360}deg)" `);
    L.marker([point.latitude, point.longitude], { icon: L.divIcon({ className: "barb-icon", html: svg, iconSize: [0, 0] }),
      interactive: false, keyboard: false }).addTo(windLayer);
  }
  chartLayer.clearLayers();
  const chart = data.chart;
  if (!chart) return;
  const [west, south, east, north] = chart.bbox;
  L.imageOverlay(chart.rain_png, [[south, west], [north, east]], { opacity: 0.85, interactive: false }).addTo(chartLayer);
  for (const line of chart.lines) {
    const main = line.hpa % 8 === 0;
    L.polyline(line.coords, { color: "#1f3a7a", weight: main ? 1.8 : 0.9, opacity: main ? 0.9 : 0.6, interactive: false }).addTo(chartLayer);
    if (main) {
      L.marker(line.coords[Math.floor(line.coords.length / 2)], { icon: L.divIcon({ className: "isobar-label", html: String(line.hpa),
        iconSize: [0, 0] }), interactive: false, keyboard: false }).addTo(chartLayer);
    }
  }
  for (const centre of chart.centres) {
    L.marker([centre.latitude, centre.longitude], { icon: L.divIcon({ className: `pressure-centre ${centre.kind === "H" ? "high" : "low"}`,
      html: `${centre.kind}<small>${centre.hpa}</small>`, iconSize: [0, 0] }), interactive: false, keyboard: false }).addTo(chartLayer);
  }
  for (const [lat, lon] of chart.thunder) {
    L.marker([lat, lon], { icon: L.divIcon({ className: "thunder-mark", html: "⚡", iconSize: [0, 0] }), interactive: false, keyboard: false })
      .addTo(chartLayer);
  }
}

function refreshWeather(summary) {
  const key = summary ? `${summary.created_utc}|${summary.valid_utc}` : null;
  if (!key || key === weatherShown) return;
  weatherShown = key;
  getJson("/api/weather").then(drawWeather).catch(() => { weatherShown = null; });
}

// The arrows show only from this zoom, so they do not crowd into one blot over Scandinavia.
const WIND_MIN_ZOOM = 8;
function showLayers(layers) {
  const wanted = { wind: layers.wind && map.getZoom() >= WIND_MIN_ZOOM, chart: layers.chart };
  for (const [name, layer] of [["wind", windLayer], ["chart", chartLayer]]) {
    if (wanted[name] && !map.hasLayer(layer)) layer.addTo(map);
    if (!wanted[name] && map.hasLayer(layer)) map.removeLayer(layer);
  }
  if (layers.chart && !shownLayers.chart) map.fitBounds(CHART_BOUNDS);
  if (!layers.chart && shownLayers.chart && areaBounds) map.fitBounds(areaBounds);
  shownLayers = { ...layers };
}

function followView() {
  getJson("/api/view").then((body) => {
    if (body.view === "3d") window.location.assign("/3d.html");
    else showLayers(body.layers || {});
  }).catch(() => null);
}

getJson("/api/config").then((config) => {
  document.getElementById("title").textContent = `Övervakning – ${config.area.name}`;
  document.title = `Övervakning – ${config.area.name} – 2D`;
  addBaseMaps(config.maps);
  addOverlays(config);
}).finally(() => {
  const refresh = () => getJson("/api/state").then(drawMap).catch(() => null);
  refresh();
  setInterval(refresh, STATE_MS);
  setInterval(followView, VIEW_MS);
});
