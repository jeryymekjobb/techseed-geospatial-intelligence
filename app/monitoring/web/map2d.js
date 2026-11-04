// The 2D main screen of the monitoring (app/monitoring/service.py), the other page of mission
// control's VISA 2D / VISA 3D as in the scenarios (app/frontend/kiosk.js viewPage): the municipality's
// map with OSM under and over it (/api/config's maps), the border, SMHI's stations, the protected
// objects and place names (/api/assets), FIRMS's detections, the events in and the current alarms
// from /api/state. It follows mission control's choice of view and map layers (/api/view) and goes to
// the 3D globe when the view changes. Tooltips and labels are set as text.
"use strict";

const STATE_MS = 30000;
const VIEW_MS = 2000;

// Leaflet shows a tooltip given as a string as HTML: text from the sources is given as a text node.
function tip(text) {
  return document.createTextNode(String(text ?? ""));
}

const map = L.map("map");
// Mission control's map layers (service.LAYERS), each a group shown or hidden by showLayers.
const named = {};
for (const name of ["municipal", "flood", "flood_highest", "skyfall100", "skyfall500", "radar", "satellite", "landsat", "s1radar",
  "s1wetness", "s1water", "stations", "levels", "facilities", "names", "firms"]) {
  named[name] = L.layerGroup();
}
// The hamlets' names, part of the names layer, shown only close in, where they do not crowd.
const hamlets = L.layerGroup();
const HAMLET_MIN_ZOOM = 12;

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
      bounds: [[south, west], [north, east]] }).addTo(named.municipal);
  }
  if (maps.overlay && maps.municipal.length) {
    L.tileLayer(maps.overlay.url, { minZoom: OFFLINE_MIN_ZOOM, maxZoom: 18, zIndex: 4, attribution: maps.overlay.attribution })
      .addTo(named.municipal);
  }
}

// The scenarios' overlays: MCF's flood map (WMS), SMHI's radar and the latest Sentinel-2 image, whose
// images are asked again after every poll (/api/state's polled_utc), when newer ones may have come.
let radarLayer = null;
let radarShown = null;
let imageLayer = null;
let imageShown = null;
function addOverlays(config) {
  for (const name of ["flood", "flood_highest"]) {
    const flood = config.layers[name];
    if (flood) {
      L.tileLayer.wms(flood.url, { layers: flood.layers, format: "image/png", transparent: true, opacity: 0.6, styles: "",
        attribution: flood.attribution, zIndex: 5 }).addTo(named[name]);
    }
  }
  // The municipality's cloudburst mapping, kept locally (/basemap/skyfall100/ and skyfall500).
  for (const item of config.layers.overlays || []) {
    if (!named[item.id]) continue;
    const [w, s, e, n] = item.bbox;
    L.tileLayer(item.url, { minZoom: item.min_zoom, maxNativeZoom: item.max_zoom, maxZoom: 18, zIndex: 6, opacity: 0.8,
      attribution: item.attribution, bounds: [[s, w], [n, e]] }).addTo(named[item.id]);
  }
  const [west, south, east, north] = config.layers.radar.bbox;
  radarLayer = L.imageOverlay("data:,", [[south, west], [north, east]], { opacity: 0.85, attribution: config.layers.radar.attribution })
    .addTo(named.radar);
  imageLayer = L.imageOverlay("data:,", [[south, west], [north, east]], { opacity: 1 }).addTo(named.satellite);
  landsatLayer = L.imageOverlay("data:,", [[south, west], [north, east]], { opacity: 1 }).addTo(named.landsat);
  s1Layers = {
    radar: L.imageOverlay("data:,", [[south, west], [north, east]], { opacity: 0.9 }).addTo(named.s1radar),
    wetness: L.imageOverlay("data:,", [[south, west], [north, east]], { opacity: 0.85 }).addTo(named.s1wetness),
    water: L.imageOverlay("data:,", [[south, west], [north, east]], { opacity: 1 }).addTo(named.s1water),
  };
}

// Sentinel-1's latest pass: the grey radar image and the water outside the lakes in red.
let s1Layers = null;
let s1Shown = null;
function drawRadarPass(meta) {
  if (!s1Layers || !meta || meta.time_utc === s1Shown) return;
  s1Shown = meta.time_utc;
  s1Layers.radar.setUrl(`/api/s1radar.png?at=${encodeURIComponent(meta.time_utc)}`);
  s1Layers.water.setUrl(`/api/s1water.png?at=${encodeURIComponent(meta.time_utc)}`);
  s1Layers.wetness.setUrl(`/api/s1wetness.png?at=${encodeURIComponent(meta.time_utc)}`);
  map.attributionControl.addAttribution(meta.attribution);
}

let landsatLayer = null;
let landsatShown = null;
function drawLandsat(meta) {
  if (!landsatLayer || !meta || meta.time_utc === landsatShown) return;
  landsatShown = meta.time_utc;
  landsatLayer.setUrl(`/api/landsat.png?at=${encodeURIComponent(meta.time_utc)}`);
  map.attributionControl.addAttribution(meta.attribution);
}

function drawImage(meta) {
  if (!imageLayer || !meta || meta.time_utc === imageShown) return;
  imageShown = meta.time_utc;
  imageLayer.setUrl(`/api/satellite.png?at=${encodeURIComponent(meta.time_utc)}`);
  imageLayer.getElement()?.setAttribute("title", `${meta.platform} ${meta.time_utc}, ${meta.cloud} % moln`);
  map.attributionControl.addAttribution(meta.attribution);
}

// The protected objects from the municipality's GIS and the place names (/api/assets), drawn once.
// The marks, as the user asked: SMHI's stations round with a white ring, blue, and red while one of
// them alarms (a high flow or record, heavy rain), which the log then shows; the protected objects and
// other places of interest small, round and yellow.
const STATION_MARKS = { normal: "#1565c0", alarm: "#c62828" };
function alarming(state, key) {
  return state.alarms.some((alarm) => alarm.id === key && alarm.current && alarm.state !== "dismissed");
}
// The scenarios' simulated level sensors (levels.py): round with a magenta ring, the monitoring's mark
// for what is simulated, blue, and red while the sensor alarms.
const LEVEL_RING = "#e040fb";
function levelText(sensor) {
  const value = sensor.value == null ? `inga värden från ${sensor.station_name} ännu`
    : `${sensor.station_name} ${sensor.percent ?? "–"} % av högsta dygnsflöde i arkivet`;
  return `${sensor.name}: ${sensor.alarm ? "LARMAR" : "inget larm"}, ${value} (simulerad nivågivare, följer SMHI)`;
}
const OBJECT_MARK = { radius: 4, color: "#5d4300", weight: 1, fillColor: "#ffd600", fillOpacity: 1 };
function drawAssets(assets) {
  for (const item of assets.facilities || []) {
    L.circleMarker([item.latitude, item.longitude], OBJECT_MARK)
      .bindTooltip(tip(`${item.name} (${item.category}) – ${item.source}`)).addTo(named.facilities);
  }
  for (const place of assets.places || []) {
    const label = document.createElement("span");
    label.textContent = place.name;
    label.className = `place-name ${place.type}`;
    L.marker([place.latitude, place.longitude], { icon: L.divIcon({ className: "place-label", html: label, iconSize: [0, 0] }),
      interactive: false, keyboard: false }).addTo(place.type === "hamlet" ? hamlets : named.names);
  }
  if (assets.attribution) map.attributionControl.addAttribution(assets.attribution);
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
  drawImage(context.satellite_image);
  drawLandsat(context.landsat_image);
  drawRadarPass(context.radar_pass);
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
  named.stations.clearLayers();
  named.firms.clearLayers();
  named.levels.clearLayers();
  for (const sensor of context.level_sensors || []) {
    marker(named.levels, sensor.latitude, sensor.longitude, { radius: 5, color: LEVEL_RING, weight: 2,
      fillColor: sensor.alarm ? STATION_MARKS.alarm : STATION_MARKS.normal, fillOpacity: 1 }, levelText(sensor));
  }
  for (const flow of context.flows || []) {
    if (flow.latitude == null) continue;
    const limits = flow.limits ? ` (högt över ${flow.limits.high}, rekord ${flow.limits.record})` : "";
    const flowColour = alarming(state, `flow-${flow.station}`) ? STATION_MARKS.alarm : STATION_MARKS.normal;
    marker(named.stations, flow.latitude, flow.longitude, { radius: 7, color: "#ffffff", weight: 2, fillColor: flowColour, fillOpacity: 1 },
      `Vattenföring ${flow.name}: ${flow.value} m³/s ${flow.time_utc}${limits} – SMHI`);
  }
  for (const station of context.weather_stations || []) {
    const colour = alarming(state, `rain-${station.station}`) ? STATION_MARKS.alarm : STATION_MARKS.normal;
    marker(named.stations, station.latitude, station.longitude, { radius: 7, color: "#ffffff", weight: 2, fillColor: colour,
      fillOpacity: 1 }, stationText(station));
  }
  for (const point of context.firms || []) {
    marker(named.firms, point.latitude, point.longitude, { radius: 4, color: "#e65100" },
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

// A weather station's latest values, as SMHI gives them.
function stationText(station) {
  const v = station.values;
  const parts = [];
  if (v.temp_c !== undefined) parts.push(`${v.temp_c} °C`);
  if (v.wind_ms !== undefined) parts.push(`vind ${v.wind_ms} m/s${v.wind_from_deg !== undefined ? ` från ${v.wind_from_deg}°` : ""}`);
  if (v.rain_1h_mm !== undefined) parts.push(`regn ${v.rain_1h_mm} mm senaste timmen`);
  if (v.rain_day_mm !== undefined) parts.push(`regn ${v.rain_day_mm} mm senaste dygnet (06–06)`);
  const time = Object.values(station.times).sort().pop();
  return `SMHI ${station.name}: ${parts.join(", ")}${time ? ` – ${time}` : ""}`;
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

// The arrows show only from this zoom, so they do not crowd into one blot over Scandinavia; the
// place names likewise.
const WIND_MIN_ZOOM = 8;
function showLayers(layers) {
  const close = map.getZoom() >= WIND_MIN_ZOOM;
  const wanted = { ...layers, wind: layers.wind && close, names: layers.names && close,
    hamlets: layers.names && map.getZoom() >= HAMLET_MIN_ZOOM };
  for (const [name, layer] of [["wind", windLayer], ["chart", chartLayer], ["hamlets", hamlets], ...Object.entries(named)]) {
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
  getJson("/api/assets").then(drawAssets).catch(() => null);
}).finally(() => {
  const refresh = () => getJson("/api/state").then(drawMap).catch(() => null);
  refresh();
  setInterval(refresh, STATE_MS);
  setInterval(followView, VIEW_MS);
});
