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
const localTime = new Intl.DateTimeFormat("sv-SE", {
  timeZone: "Europe/Stockholm", dateStyle: "medium", timeStyle: "short",
});

const COMPASS = ["N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO", "S", "SSV", "SV", "VSV", "V", "VNV", "NV", "NNV"];

const state = {
  config: null,
  weather: null,
  weatherStation: null,
  daily: [],
  markers: [],
  source: null,
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
}

function stopStream() {
  if (state.source) state.source.close();
  state.source = null;
  $("play").textContent = "Spela";
}

function play(view) {
  if (state.source) {
    stopStream();
    $("stream-status").textContent = "Pausad.";
    return;
  }
  if (state.finished) reset(view);
  const from = (state.clock || new Date(state.config.playback.start_utc)).toISOString();
  const speed = $("speed").value;
  const source = new EventSource(`/api/stream?speed=${speed}&from=${encodeURIComponent(from)}`);
  state.source = source;
  $("play").textContent = "Paus";
  $("stream-status").textContent = "Tar emot detektioner från backend …";
  source.addEventListener("hotspot", (event) => addHotspot(view, JSON.parse(event.data)));
  source.addEventListener("clock", (event) => setClock(new Date(JSON.parse(event.data).sim_time_utc)));
  source.addEventListener("end", (event) => {
    setClock(new Date(JSON.parse(event.data).sim_time_utc));
    state.finished = true;
    stopStream();
    $("stream-status").textContent = "Uppspelningen är klar.";
  });
  source.onerror = () => {
    // EventSource reconnects by itself; stop instead so the playback does not restart.
    if (state.source === source && !state.finished) {
      stopStream();
      $("stream-status").textContent = "Strömmen avbröts. Tryck Spela för att fortsätta.";
    }
  };
}

function reset(view) {
  stopStream();
  view.hotspots.clearLayers();
  state.markers = [];
  state.finished = false;
  setClock(new Date(state.config.playback.start_utc));
  $("stream-status").textContent = "";
}

async function showUntil(view, until) {
  reset(view);
  const collection = await getJson("/api/hotspots");
  for (const feature of collection.features) {
    if (new Date(feature.properties.acq_datetime_utc) <= until) addHotspot(view, feature);
  }
  state.finished = until >= new Date(state.config.playback.end_utc);
  setClock(until);
}

async function showAll(view) {
  await showUntil(view, new Date(state.config.playback.end_utc));
  $("stream-status").textContent = "Alla detektioner visas.";
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
  L.control.layers(view.baseLayers, view.overlays, { collapsed: false }).addTo(view.map);
  setClock(new Date(config.playback.start_utc));
  $("play").addEventListener("click", () => play(view));
  $("reset").addEventListener("click", () => reset(view));
  $("show-all").addEventListener("click", () => showAll(view));
  $("speed").addEventListener("change", () => {
    if (state.source) { stopStream(); play(view); }
  });
  // Kiosk options: ?show=all shows every detection, ?at=<ISO time> the state at that
  // time (playback continues from there), ?autoplay=1 starts the playback.
  const options = new URLSearchParams(window.location.search);
  const at = options.get("at") ? new Date(options.get("at")) : null;
  if (options.get("show") === "all") await showAll(view);
  else if (at && !Number.isNaN(at.getTime())) await showUntil(view, at);
  else if (options.get("autoplay") === "1") play(view);
}

main().catch((error) => {
  $("stream-status").textContent = `Fel vid start: ${error.message}`;
});
