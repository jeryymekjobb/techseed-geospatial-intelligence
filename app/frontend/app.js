// GUI for the Västmanland 2014 fire map: base maps, terrain, and FIRMS hotspots
// that the backend streams in compressed time.
"use strict";

const TERRAIN_COLORS = {
  "skog": "#3f7d3a",
  "myr": "#9c8f5b",
  "åker": "#e8d77a",
  "öppen mark": "#c5d98a",
  "buskmark": "#7fa36b",
  "hed": "#b9a77a",
  "berg i dagen": "#9a9a9a",
  "bebyggelse": "#c9a0a0",
  "industri": "#a8a8b8",
  "täkt": "#b0a090",
  "vatten": "#6fa8dc",
};
const AGE_COLORS = [[12, "#ff2a00"], [48, "#ff8c00"], [Infinity, "#7a1f1f"]];
const clockTime = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const localTime = new Intl.DateTimeFormat("sv-SE", {
  timeZone: "Europe/Stockholm", dateStyle: "medium", timeStyle: "short",
});

const COMPASS = ["N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO", "S", "SSV", "SV", "VSV", "V", "VNV", "NV", "NNV"];

const state = {
  config: null,
  forecast: null,
  forecastPass: undefined,
  forecastHorizon: "6",
  forecastLayer: null,
  wind: null,
  windMarkers: [],
  windHour: null,
  weather: null,
  weatherStation: null,
  daily: [],
  markers: [],
  playing: false,
  controlToken: null,
  clock: null,
  finished: false,
};

const $ = (id) => document.getElementById(id);

function hoursBetween(later, earlier) {
  return (later - earlier) / 3600000;
}

function hotspotColor(detectedAt, clock) {
  const age = hoursBetween(clock, detectedAt);
  return AGE_COLORS.find(([limit]) => age < limit)[1];
}

function hotspotRadius(frp) {
  return Math.min(14, 3 + Math.sqrt(Math.max(0, frp)) / 2);
}

function formatLocal(isoUtc) {
  return `${localTime.format(new Date(isoUtc))} svensk tid`;
}

async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

function setupMap(config) {
  const map = L.map("map", {
    preferCanvas: true, zoomSnap: 0.25, maxBounds: L.latLngBounds(config.view_bounds).pad(0.5),
  });
  map.fitBounds(config.view_bounds);
  const osm = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
  }).addTo(map);
  const baseLayers = { "OpenStreetMap": osm };
  const overlays = {};
  const notes = [];
  if (config.layers.lantmateriet_topowebb) {
    baseLayers["Lantmäteriet topowebb"] = L.tileLayer("/lm/topowebb/{z}/{x}/{y}.png", {
      maxZoom: 17, attribution: config.attribution.lantmateriet,
    });
  } else {
    notes.push("Lantmäteriets topowebb är inte aktiverad (inloggning via Geotorget saknas).");
  }
  if (config.layers.lantmateriet_fastighet) {
    overlays["Fastigheter (Lantmäteriet)"] = L.tileLayer.wms("/lm/fastighet", {
      layers: config.layers.lantmateriet_fastighet_layers, format: "image/png", transparent: true,
      attribution: config.attribution.lantmateriet,
    });
  } else {
    notes.push("Fastighetsindelning är inte aktiverad (inloggning via Geotorget saknas).");
  }
  const selection = L.rectangle(config.fire_selection_bounds, {
    color: "#202020", weight: 1, dashArray: "4 4", fill: false, interactive: false,
  });
  overlays["FIRMS-urval"] = selection;
  const hotspots = L.layerGroup().addTo(map);
  overlays["Hotspots"] = hotspots;
  map.attributionControl.addAttribution(config.attribution.firms);
  $("layer-notes").textContent = notes.join(" ");
  return { map, baseLayers, overlays, hotspots };
}

async function addTerrain(view, config) {
  const legend = $("terrain-legend");
  for (const [name, color] of Object.entries(TERRAIN_COLORS)) {
    const item = document.createElement("li");
    item.innerHTML = `<span class="swatch" style="background:${color}"></span>${name}`;
    legend.append(item);
  }
  try {
    const terrain = await getJson(config.layers.terrain);
    const layer = L.geoJSON(terrain, {
      style: (feature) => ({
        color: TERRAIN_COLORS[feature.properties.terrain] || "#888",
        weight: 0.4, fillOpacity: 0.22, opacity: 0.5,
      }),
      onEachFeature: (feature, item) => {
        const name = feature.properties.name ? `<br>${feature.properties.name}` : "";
        item.bindPopup(`<strong>${feature.properties.terrain}</strong>${name}<br><small>OSM ${feature.properties.osm_tag}</small>`);
      },
    });
    view.overlays["Terräng (OSM)"] = layer;
    layer.addTo(view.map);
    layer.bringToBack();
  } catch (error) {
    $("layer-notes").textContent += ` Terränglagret kunde inte laddas: ${error.message}.`;
  }
}

function addHotspot(view, feature) {
  const [lon, lat] = feature.geometry.coordinates;
  const p = feature.properties;
  const detectedAt = new Date(p.acq_datetime_utc);
  const viirs = p.instrument === "VIIRS";
  const marker = L.circleMarker([lat, lon], {
    radius: hotspotRadius(p.frp), weight: viirs ? 0 : 1.5, fillOpacity: viirs ? 0.75 : 0.15,
  });
  marker.bindPopup(
    `<strong>${p.instrument} (${p.satellite})</strong><br>${formatLocal(p.acq_datetime_utc)}`
    + `<br>${p.acq_datetime_utc} UTC<br>Konfidens: ${p.confidence}<br>FRP: ${p.frp} MW`,
  );
  marker.detectedAt = detectedAt;
  marker.addTo(view.hotspots);
  state.markers.push(marker);
}

function restyleHotspots(clock) {
  for (const marker of state.markers) {
    const color = hotspotColor(marker.detectedAt, clock);
    marker.setStyle({ color, fillColor: color });
  }
  $("counts").textContent = `${state.markers.length} detektioner visas`;
}

function drawTimeline(daily, clock) {
  const svg = $("timeline");
  const totals = new Map();
  for (const row of daily) totals.set(row.acq_date, (totals.get(row.acq_date) || 0) + Number(row.detections));
  const start = new Date(state.config.playback.start_utc);
  const end = new Date(state.config.playback.end_utc);
  const days = Math.round(hoursBetween(end, start) / 24);
  const width = 300;
  const height = 100;
  const barWidth = width / days;
  const max = Math.max(1, ...totals.values());
  const parts = [];
  for (let index = 0; index < days; index += 1) {
    const day = new Date(start.getTime() + index * 86400000).toISOString().slice(0, 10);
    const value = totals.get(day) || 0;
    const barHeight = (value / max) * (height - 20);
    parts.push(`<rect class="bar" x="${index * barWidth + 1}" y="${height - 14 - barHeight}" width="${barWidth - 2}" height="${barHeight}"><title>${day}: ${value}</title></rect>`);
    if (index % 3 === 0) parts.push(`<text x="${index * barWidth + 1}" y="${height - 3}">${day.slice(5)}</text>`);
  }
  if (clock) {
    const x = (hoursBetween(clock, start) / 24) * barWidth;
    parts.push(`<line class="cursor" x1="${x}" x2="${x}" y1="0" y2="${height - 14}"></line>`);
  }
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.innerHTML = parts.join("");
}

function compassPoint(degrees) {
  return COMPASS[Math.round(degrees / 22.5) % 16];
}

function observationAt(station, clock) {
  // The latest hourly observation at or before the playback clock.
  let found = null;
  for (const observation of station.observations) {
    if (new Date(observation.time_utc) > clock) break;
    found = observation;
  }
  return found;
}

function showWeather(clock) {
  const station = state.weather?.stations.find((item) => item.id === state.weatherStation);
  if (!station) return;
  const observation = observationAt(station, clock);
  const values = $("weather-values");
  const arrow = document.querySelector("#wind-arrow .arrow");
  if (!observation) {
    values.innerHTML = "<dt>Data</dt><dd>saknas för tiden</dd>";
    arrow.style.visibility = "hidden";
    return;
  }
  const calm = !observation.wind_speed_ms;
  const wind = calm ? "lugnt" : `${observation.wind_speed_ms} m/s från ${compassPoint(observation.wind_dir_deg)} (${observation.wind_dir_deg}°)`;
  values.innerHTML = [
    ["Temperatur", `${observation.temp_c} °C`],
    ["Luftfuktighet", `${observation.rh_pct} %`],
    ["Vind", wind],
    ["Byvind", `${observation.gust_ms} m/s`],
    ["Nederbörd", `${observation.precip_mm} mm/h`],
    ["Mätt", formatLocal(observation.time_utc)],
  ].map(([label, value]) => `<dt>${label}</dt><dd>${value}</dd>`).join("");
  // The arrow points where the wind blows to; SMHI gives where it comes from.
  arrow.style.visibility = calm ? "hidden" : "visible";
  arrow.style.transform = `rotate(${(observation.wind_dir_deg + 180) % 360}deg)`;
}

function windAt(clock) {
  // The latest ERA5-Land hour at or before the playback clock.
  const times = state.wind.times_utc;
  let found = -1;
  for (let index = 0; index < times.length && new Date(times[index]) <= clock; index += 1) found = index;
  return found;
}

function showWind(clock) {
  if (!state.wind) return;
  const hour = windAt(clock);
  if (hour === state.windHour) return;
  state.windHour = hour;
  state.windMarkers.forEach((marker, position) => {
    const element = marker.getElement();
    if (!element) return;
    if (hour < 0) {
      element.style.visibility = "hidden";
      return;
    }
    const [speed, from, temperature] = state.wind.values[hour][position];
    element.style.visibility = "visible";
    element.innerHTML = windBarbSvg(speed);
    element.firstChild.style.transform = `rotate(${(from + 180) % 360}deg)`;
    const [lat, lon] = state.wind.points[position];
    marker.setTooltipContent(
      `ERA5-Land ${lat.toFixed(1)} N ${lon.toFixed(1)} E<br>${speed.toFixed(1)} m/s från ${compassPoint(from)} (${from}°), ${temperature} °C`
      + `<br>${formatLocal(state.wind.times_utc[hour])}`,
    );
  });
  $("wind-note").textContent = hour < 0 ? "Inga vinddata för tiden." : `Modellvärden för ${formatLocal(state.wind.times_utc[hour])}.`;
}

async function setupWind(view) {
  try {
    state.wind = await getJson("/api/wind");
  } catch (error) {
    $("wind-note").textContent = `Vinddata kunde inte laddas: ${error.message}.`;
    return;
  }
  const layer = L.layerGroup();
  const icon = L.divIcon({ className: "barb-icon", iconSize: [56, 56], iconAnchor: [28, 28], html: "" });
  state.windMarkers = state.wind.points.map(([lat, lon]) => L.marker([lat, lon], { icon, keyboard: false })
    .bindTooltip("", { direction: "top" }).addTo(layer));
  view.overlays["Vind (ERA5-Land)"] = layer;
  layer.addTo(view.map);
  layer.on("add", () => { state.windHour = null; showWind(state.clock); });
  view.map.attributionControl.addAttribution(state.config.attribution.era5_land);
}

function forecastStateAt(clock) {
  // The latest pass at or before the playback clock; the forecast never looks ahead.
  let found = null;
  for (const item of state.forecast.states) {
    if (new Date(item.pass_utc) > clock) break;
    found = item;
  }
  return found;
}

function spreadArrowIcon(observedDeg, modelDeg) {
  const arrow = (deg, cls) => (deg === null || deg === undefined ? "" :
    `<g transform="rotate(${deg})"><path d="M0,0 L0,-30" class="${cls}"></path><path d="M-5,-24 L0,-34 L5,-24 Z" class="${cls}-head"></path></g>`);
  return L.divIcon({
    className: "spread-arrow", iconSize: [70, 70], iconAnchor: [35, 35],
    html: `<svg viewBox="-35 -35 70 70">${arrow(modelDeg, "model")}${arrow(observedDeg, "observed")}</svg>`,
  });
}

function km(value) {
  return `${String(value).replace(".", ",")} km/h`;
}

function drawForecast(clock) {
  if (!state.forecast || !state.forecastLayer) return;
  const current = forecastStateAt(clock);
  const key = `${current?.pass_utc}|${state.forecastHorizon}`;
  const values = $("forecast-values");
  if (current) {
    const since = hoursBetween(clock, new Date(current.pass_utc));
    const observed = current.observed_spread;
    const model = current.model;
    const weather = model.fire_weather;
    values.innerHTML = [
      ["Senaste passage", `${formatLocal(current.pass_utc)} (för ${since.toFixed(1).replace(".", ",")} h sedan)`],
      ["Detektioner", `${current.detections_so_far} hittills`],
      ["Observerat", observed ? `${km(observed.km_per_h)} mot ${observed.towards} (${clockTime.format(new Date(observed.from_utc))}–${clockTime.format(new Date(observed.to_utc))} mellan passager)` : "ingen mätbar spridning ännu"],
      ["Modell, trolig", `${km(model.head_km_per_h.central)} mot ${model.towards} (spann ${km(model.head_km_per_h.low)}–${km(model.head_km_per_h.high)})`],
      ["Kalibrering", `× ${String(model.calibration_factor).replace(".", ",")} mot observerad spridning`],
      ["Brandväder", weather.fwi !== undefined ? `FWI ${weather.fwi}, BUI ${weather.bui}, ISI ${weather.isi} (SMHI Sala A)` : "saknas"],
    ].map(([label, value]) => `<dt>${label}</dt><dd>${value}</dd>`).join("");
  } else {
    values.innerHTML = "<dt>Prognos</dt><dd>ingen satellitdetektion ännu</dd>";
  }
  if (key === state.forecastPass) return;
  state.forecastPass = key;
  const layer = state.forecastLayer;
  layer.clearLayers();
  if (!current) {
    $("forecast-places").textContent = "";
    return;
  }
  const bands = current.forecast[state.forecastHorizon];
  L.polygon(bands.high, { color: "#b7950b", weight: 1, dashArray: "5 4", fillColor: "#ffd54a", fillOpacity: 0.18, interactive: false }).addTo(layer);
  L.polygon(bands.central, { color: "#d35400", weight: 1.5, fillColor: "#ff8c00", fillOpacity: 0.25, interactive: false }).addTo(layer);
  L.polygon(bands.low, { color: "#7a1f1f", weight: 1, dashArray: "3 3", fill: false, interactive: false }).addTo(layer);
  L.polygon(current.front, { color: "#202020", weight: 2, fill: false, interactive: false }).addTo(layer);
  L.marker(current.front_centre, {
    icon: spreadArrowIcon(current.observed_spread?.towards_deg, current.model.towards_deg), interactive: false, keyboard: false,
  }).addTo(layer);
  for (const place of current.places_within_24h) {
    L.circleMarker([place.latitude, place.longitude], { radius: 4, color: "#202020", weight: 1, fillColor: "#ffd54a", fillOpacity: 1 })
      .bindTooltip(`${place.names.join(", ")}: inom ${place.span} (spann)`, { direction: "top" })
      .addTo(layer);
  }
  const list = current.places_within_24h.slice(0, 6).map((place) => `${place.names[0]} ${place.span}`).join(", ");
  $("forecast-places").textContent = current.places_within_24h_count
    ? `Orter inom ytan för dubbel hastighet inom 24 h: ${current.places_within_24h_count}. Först: ${list}. Spannet är tid vid dubbel–halv hastighet.`
    : "Inga orter inom ytan för dubbel hastighet inom 24 h.";
}

async function setupForecast(view) {
  try {
    state.forecast = await getJson("/api/forecast");
  } catch (error) {
    $("forecast-places").textContent = `Prognosen kunde inte laddas: ${error.message}.`;
    return;
  }
  $("forecast-label").textContent = state.forecast.label;
  state.forecastLayer = L.layerGroup().addTo(view.map);
  view.overlays["Prognos (modell)"] = state.forecastLayer;
  $("forecast-horizon").addEventListener("change", (event) => {
    state.forecastHorizon = event.target.value;
    drawForecast(state.clock);
  });
}

async function setupWeather(view) {
  try {
    state.weather = await getJson("/api/weather");
  } catch (error) {
    $("weather-note").textContent = `Väderdata kunde inte laddas: ${error.message}.`;
    return;
  }
  const select = $("weather-station");
  for (const station of state.weather.stations) {
    const option = document.createElement("option");
    option.value = station.id;
    option.textContent = `${station.name} (${station.distance_km} km)`;
    select.append(option);
    L.circleMarker([station.latitude, station.longitude], {
      radius: 6, color: "#1f5fa8", fillColor: "#fff", fillOpacity: 1, weight: 3,
    }).bindTooltip(`SMHI ${station.name}`, { permanent: true, direction: "right" }).addTo(view.map);
  }
  state.weatherStation = state.weather.stations[0]?.id || null;
  select.addEventListener("change", () => {
    state.weatherStation = select.value;
    showWeather(state.clock);
  });
  view.map.attributionControl.addAttribution(state.config.attribution.smhi);
  $("weather-note").textContent = "Mätningar vid stationen, inte i brandområdet.";
}

function setClock(clock) {
  state.clock = clock;
  $("sim-time").textContent = formatLocal(clock.toISOString());
  restyleHotspots(clock);
  drawTimeline(state.daily, clock);
  showWeather(clock);
  showWind(clock);
  drawForecast(clock);
}

// The playback is shared: the backend holds one scenario clock that every screen
// follows (/api/scenario/stream); the buttons send commands to it.
async function command(name, extra = {}) {
  const headers = { "Content-Type": "application/json" };
  if (state.controlToken) headers["X-Control-Token"] = state.controlToken;
  const response = await fetch("/api/scenario/command", {
    method: "POST", headers, body: JSON.stringify({ command: name, ...extra }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || body.error || `HTTP ${response.status}`);
  }
  return response.json();
}

function runCommand(name, extra) {
  command(name, extra).catch((error) => {
    $("stream-status").textContent = `Kommandot ${name} misslyckades: ${error.message}`;
  });
}

function showSpeed(speed) {
  const select = $("speed");
  if (![...select.options].some((option) => Number(option.value) === speed)) {
    select.append(new Option(speedLabel(speed), String(speed)));
  }
  select.value = String(speed);
}

function applyState(scenarioState) {
  state.playing = scenarioState.playing;
  state.finished = scenarioState.finished;
  $("play").textContent = scenarioState.playing ? "Paus" : "Spela";
  showSpeed(scenarioState.speed);
  $("stream-status").textContent = scenarioState.finished
    ? "Uppspelningen är klar."
    : scenarioState.playing ? "Spelar upp – alla skärmar följer samma klocka." : "Pausad.";
  // Read by tools/record_demo.py.
  document.body.dataset.playback = scenarioState.finished ? "finished" : scenarioState.playing ? "playing" : "paused";
  setClock(new Date(scenarioState.clock_utc));
}

function clearHotspots(view) {
  view.hotspots.clearLayers();
  state.markers = [];
}

function connectScenario(view) {
  return new Promise((resolve) => {
    const source = new EventSource("/api/scenario/stream");
    source.addEventListener("sync", (event) => {
      const data = JSON.parse(event.data);
      clearHotspots(view);
      for (const feature of data.features) addHotspot(view, feature);
      applyState(data.state);
      resolve();
    });
    source.addEventListener("hotspot", (event) => addHotspot(view, JSON.parse(event.data)));
    source.addEventListener("state", (event) => applyState(JSON.parse(event.data)));
    source.onerror = () => {
      // EventSource reconnects by itself and the backend then sends a new sync.
      $("stream-status").textContent = "Anslutningen till backend bröts – försöker igen …";
    };
  });
}

async function main() {
  const config = await getJson("/api/config");
  state.config = config;
  $("title").textContent = config.title;
  $("data-label").textContent = config.data_label;
  const view = setupMap(config);
  const summary = await getJson("/api/hotspots");
  state.daily = summary.daily;
  await addTerrain(view, config);
  await setupWeather(view);
  await setupWind(view);
  await setupForecast(view);
  L.control.layers(view.baseLayers, view.overlays, { collapsed: false }).addTo(view.map);
  setClock(new Date(config.playback.start_utc));
  state.controlToken = new URLSearchParams(window.location.search).get("token");
  $("play").addEventListener("click", () => runCommand(state.playing ? "pause" : "play"));
  $("reset").addEventListener("click", () => runCommand("reset"));
  $("show-all").addEventListener("click", () => runCommand("seek", { at: config.playback.end_utc }));
  $("speed").addEventListener("change", (event) => runCommand("speed", { speed: Number(event.target.value) }));
  await connectScenario(view);
  // Kiosk options (kiosk.js): ?show=all, ?at=<ISO time>, ?autoplay=1, ?speed=, ?horizon=.
  // Options that move the clock change the shared scenario for every screen.
  const options = parseKioskOptions(window.location.search);
  if (options.horizon) {
    $("forecast-horizon").value = options.horizon;
    state.forecastHorizon = options.horizon;
    state.forecastPass = undefined;
    drawForecast(state.clock);
  }
  if (options.speed) await command("speed", { speed: options.speed });
  if (options.showAll) await command("seek", { at: config.playback.end_utc });
  else if (options.at) await command("seek", { at: options.at.toISOString() });
  if (options.autoplay && !options.showAll) await command("play");
  document.body.dataset.ready = "true";
}

main().catch((error) => {
  $("stream-status").textContent = `Fel vid start: ${error.message}`;
});
