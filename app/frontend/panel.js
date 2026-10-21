// Map-independent part of the fire-map GUI: shared state, the side panel, the shared
// scenario clock and kiosk options. A map adapter (map2d.js for Leaflet, map3d.js for
// Cesium) draws the layers; startApp() wires the two together.
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
const COMPASS = ["N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO", "S", "SSV", "SV", "VSV", "V", "VNV", "NV", "NNV"];
const clockTime = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const localTime = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", dateStyle: "medium", timeStyle: "short" });
const localDate = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", dateStyle: "medium" });
const dayMonth = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", day: "numeric", month: "long" });
const chartDay = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", month: "2-digit", day: "2-digit", hour: "2-digit", hourCycle: "h23" });

const state = {
  config: null,
  map: null,
  forecast: null,
  forecastPass: undefined,
  forecastHorizon: "6",
  wind: null,
  windHour: null,
  weather: null,
  weatherStation: null,
  rainStation: null,
  rainShownAt: null,
  daily: [],
  playing: false,
  controlToken: null,
  clock: null,
  finished: false,
  // Mission-control status (scenario_events.js): applied when it changes.
  scenarioStatus: null,
  hiddenLayers: [],
  // The scenario's satellites (/api/satellites, orbits.js with satellite.js).
  satellites: null,
  satelliteLib: null,
  satelliteInfoAt: null,
  satellitesDrawnAt: null,
  monitor: null,  // satmonitor.js, always on screen
  passCache: new Map(),  // "norad|day" -> passes over the fire that scenario day
  flashedPasses: new Set(),
  // The Landsat 8 scene (config.layers.landsat): shown from its acquisition time.
  landsat: null,
  imageTypes: ["swir"],  // the image types "auto" follows (landsat.js imageTypesShown)
  baseMap: undefined,
  layersApplied: {},
  choicesApplied: {},  // mission control's panel choices as last applied, by key  // the map layers as mission control's ticks last set them, by name  // the base map shown (basemaps.js baseMapFor), undefined until mission control's status arrives
  landsatPick: "auto",  // mission control's choice (the scenario status's image)
  landsatShown: undefined,
  pendingEvents: [],
  threatData: null,  // { sensorEvents, threats } for the threatened places (showThreats)
  threatKey: null,
  threatState: null,  // the last state showThreats drew, for the timer that ends a highlight
  threatJump: undefined,
  threatSeen: new Set(),  // the threat lines already come in (satlogKey)
  threatHighlights: new Map(),  // satlogKey -> when its highlight ends (Date.now())
  threatTimer: null,
  horizonBeforePlus60: null,
  // IoT (sensors.js): real nodes by "node/kind", the synthetic sensors at the clock.
  realSensors: new Map(),
  iotConnection: null,
  synthetic: null,
  // The detection sequence (scenario_events.js): /api/detection per pass and the step shown.
  detection: null,
  detectionKey: null,
  detectionImage: null,  // "scene|image" the flood's sequence shows, or null
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

function km(value) {
  return `${String(value).replace(".", ",")} km/h`;
}

function compassPoint(degrees) {
  return COMPASS[Math.round(degrees / 22.5) % 16];
}

function hotspotPopup(p) {
  return `<strong>${p.instrument} (${p.satellite})</strong><br>${formatLocal(p.acq_datetime_utc)}`
    + `<br>${p.acq_datetime_utc} UTC<br>Konfidens: ${p.confidence}<br>FRP: ${p.frp} MW`;
}

function addNote(text) {
  $("layer-notes").textContent = `${$("layer-notes").textContent} ${text}`.trim();
}

async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

// The time charts' height in their viewBox, 300 wide; compact, so the rain and the flows both fit
// under the playback.
const CHART_HEIGHT = 80;

function drawTimeline(daily, clock) {
  const svg = $("timeline");
  const totals = new Map();
  for (const row of daily) totals.set(row.acq_date, (totals.get(row.acq_date) || 0) + Number(row.detections));
  const start = new Date(state.config.playback.start_utc);
  const end = new Date(state.config.playback.end_utc);
  const days = Math.round(hoursBetween(end, start) / 24);
  const width = 300;
  const height = CHART_HEIGHT;
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

// The flood: rain at the chosen gauge (rain.js), a bar per playback hour, and every
// gauge's last hour on the map.
function showRain(clock) {
  if (!state.weather || state.config.incident !== "flood") return;
  const hour = Math.floor(clock.getTime() / 3600000);
  if (hour === state.rainShownAt) return;
  state.rainShownAt = hour;
  const labels = {};
  const classes = {};
  for (const station of state.weather.stations) {
    const hourSum = rainSums(station.observations, clock.getTime()).hour;
    classes[station.id] = rainClass(hourSum);
    labels[station.id] = `${station.name}: ${decimal(hourSum)} mm/h`;
  }
  state.map.labelStations(labels);
  state.map.markRain(classes);
  const station = state.weather.stations.find((item) => item.id === state.rainStation);
  if (!station) return;
  const sums = rainSums(station.observations, clock.getTime(), Date.parse(state.config.playback.start_utc));
  $("rain-values").innerHTML = [
    ["Senaste timmen", `${decimal(sums.hour)} mm`],
    ["Senaste dygnet", `${decimal(sums.day)} mm`],
    ["Sedan start", `${decimal(sums.total)} mm`],
  ].map(chartValue).join("");
  drawRain(station, clock);
}

// A label and its value in a time chart's list, kept together on one line.
function chartValue([label, value]) {
  return `<div><dt>${label}</dt><dd>${value}</dd></div>`;
}

function decimal(value) {
  return String(value).replace(".", ",");
}

function drawRain(station, clock) {
  const start = Date.parse(state.config.playback.start_utc);
  const end = Date.parse(state.config.playback.end_utc);
  const values = hourlyRain(station.observations, start, end);
  const width = 300;
  const height = CHART_HEIGHT;
  const step = width / values.length;
  const max = Math.max(5, ...values);
  const parts = values.map((value, index) => {
    const barHeight = (value / max) * (height - 20);
    const at = new Date(start + (index + 1) * HOUR_MS).toISOString();
    return `<rect class="rain-bar" x="${index * step}" y="${height - 14 - barHeight}" width="${Math.max(1, step - 0.5)}" height="${barHeight}">`
      + `<title>${formatLocal(at)}: ${decimal(value)} mm</title></rect>`;
  });
  // A date at every Swedish midnight, or every few days in a long period, so the dates do not overlap.
  const every = Math.max(1, Math.ceil((end - start) / 86400000 / 9));
  let midnights = 0;
  for (let at = start; at < end; at += HOUR_MS) {
    const local = Object.fromEntries(chartDay.formatToParts(new Date(at)).map((part) => [part.type, part.value]));
    if (local.hour !== "00") continue;
    if (midnights++ % every === 0) {
      parts.push(`<text x="${((at - start) / HOUR_MS) * step + 1}" y="${height - 3}">${local.month}-${local.day}</text>`);
    }
  }
  const x = ((clock.getTime() - start) / HOUR_MS) * step;
  parts.push(`<line class="rain-now" x1="${x}" x2="${x}" y1="0" y2="${height - 14}"></line>`);
  parts.push(`<text x="${width - 2}" y="10" text-anchor="end">max ${decimal(max)} mm/h</text>`);
  const svg = $("rain-chart");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.innerHTML = parts.join("");
}

function setupRain(config) {
  const select = $("rain-station");
  for (const station of state.weather.stations) select.append(new Option(`${station.name} (${station.distance_km} km)`, station.id));
  state.map.addStations(state.weather.stations);
  state.rainStation = state.weather.stations[0]?.id || null;
  select.addEventListener("change", () => {
    state.rainStation = select.value;
    state.rainShownAt = null;
    showRain(state.clock);
  });
  state.map.addAttribution(config.attribution.smhi);
  // The markers' classes, as SMHI names rain by the hour's sum.
  const limits = ["0 mm", "högst 0,5 mm", "0,5–4 mm", "mer än 4 mm", "minst 50 mm"];
  $("rain-legend").innerHTML = RAIN_CLASSES.map((item, index) => `<li><span class="swatch" style="background:${item.color};`
    + `border:2px solid #1f5fa8;border-radius:50%"></span>${item.label}: ${limits[index]} på en timme</li>`).join("");
  const gauges = config.rain_gauges.charAt(0).toUpperCase() + config.rain_gauges.slice(1);
  $("rain-note").textContent = `Timsummor från SMHI. ${gauges} redovisar bara timmar med regn; `
    + "en timme utan värde räknas som torr. Senaste månaderna är inte alltid kvalitetsgranskade.";
}

// MET Norway's weather forecast as issued at the clock (/api/met-forecast, met_forecast.py and
// met_forecast.js): a section after the detections' chart, fetched again when the clock enters a
// new hour, and the forecast wind as a map layer that mission control ticks.
function setupMetForecast(config) {
  const section = document.createElement("section");
  section.id = "met-forecast-section";
  section.className = "chart-section";
  const place = config.incident === "wildfire" ? "branden" : config.incident_place;
  section.innerHTML = "<h2>Väderprognos (MET Norway)</h2>"
    + '<div id="met-forecast-issued" class="forecast-label"></div>'
    + `<svg id="met-forecast-chart" class="timeline" role="img" aria-label="Prognos för vind, byvind och regn vid ${place}"></svg>`
    + `<div class="met-legend"><span class="wind">━ vind</span> · <span class="gust">┅ byvind</span> · <span class="rain">▮ regn</span> vid ${place}</div>`
    + '<dl id="met-forecast-values" class="forecast-values met-forecast-values"></dl>'
    + '<ul id="met-forecast-notices" class="met-forecast-notices"></ul><div id="met-forecast-fwi" class="status"></div>'
    + '<div id="met-forecast-chart-time" class="status"></div>';
  // After the time charts: the fire's detections, or the flood's rain and flows.
  const charts = [...document.querySelectorAll(".panel .chart-section")]
    .filter((chart) => chart !== section && (!chart.dataset.incident || chart.dataset.incident === config.incident));
  charts[charts.length - 1].after(section);
  state.map.setupForecastWind();
  state.map.setupWeatherChart();
  const caption = document.createElement("div");
  caption.id = "forecast-caption";
  caption.className = "forecast-caption";
  caption.hidden = true;
  $("map").append(caption);
  state.map.addAttribution(config.layers.met_forecast.attribution);
}

async function showMetForecast(clock) {
  if (!state.config.layers.met_forecast || !clock) return;
  const hour = new Date(Math.floor(clock.getTime() / HOUR_MS) * HOUR_MS).toISOString().replace(".000Z", "Z");
  if (hour === state.metForecastHour) return;
  state.metForecastHour = hour;
  let forecast = null;
  try {
    const response = await fetch(`/api/met-forecast?at=${encodeURIComponent(hour)}`);
    forecast = response.ok ? await response.json() : null;
  } catch {
    forecast = null;
  }
  if (hour !== state.metForecastHour) return;  // the clock has moved on meanwhile
  if (!forecast) {
    $("met-forecast-issued").textContent = "Ingen prognos utfärdad ännu vid scenariotiden.";
    for (const id of ["met-forecast-chart", "met-forecast-values", "met-forecast-notices"]) $(id).innerHTML = "";
    $("met-forecast-fwi").textContent = "";
    $("met-forecast-chart-time").textContent = "";
    state.map.drawForecastWind([], 0);
    state.map.drawWeatherChart(null);
    state.metForecastShown = null;
    showForecastCaption();
    return;
  }
  $("met-forecast-issued").textContent = `Utfärdad ${formatLocal(forecast.issued_utc)} – historisk prognos, inte live`;
  const svg = $("met-forecast-chart");
  svg.setAttribute("viewBox", `0 0 300 ${MET_CHART_HEIGHT}`);
  svg.innerHTML = metForecastChart(forecast.hours, clock.getTime(), (ms) => {
    const local = Object.fromEntries(chartDay.formatToParts(new Date(ms)).map((part) => [part.type, part.value]));
    return local.hour === "00" ? `${local.month}-${local.day}` : null;
  });
  $("met-forecast-values").innerHTML = metSummaryRows(forecast.summaries.filter((item) => item.hours <= 24)).map(chartValue).join("");
  const notices = $("met-forecast-notices");
  notices.innerHTML = "";
  for (const notice of forecast.notices) {
    const item = document.createElement("li");
    item.textContent = notice.text;
    notices.append(item);
  }
  $("met-forecast-fwi").textContent = forecast.fwi.length
    ? `Brandrisk (FWI, beräknad ur prognosen): ${forecast.fwi.map((day) => `${dayMonth.format(new Date(`${day.date}T12:00:00Z`))} ${Math.round(day.fwi)}`).join(", ")}`
    : "";
  state.map.drawForecastWind(forecast.wind_grid, forecast.wind_grid_hours_ahead);
  state.map.drawWeatherChart(forecast.isobars);
  $("met-forecast-chart-time").textContent = forecast.isobars
    ? `Väderkartan (lagret Väderkarta): prognos för ${zulu(forecast.isobars.valid_utc)}, ${formatLocal(forecast.isobars.valid_utc)}`
    : "";
  state.metForecastShown = forecast;
  showForecastCaption();
}

// "15 juli 00Z": a forecast's time as weather charts name it.
const utcDayMonth = new Intl.DateTimeFormat("sv-SE", { timeZone: "UTC", day: "numeric", month: "long" });
function zulu(isoUtc) {
  return `${utcDayMonth.format(new Date(isoUtc))} ${String(new Date(isoUtc).getUTCHours()).padStart(2, "0")}Z`;
}

// Over the map, while a forecast layer is ticked: which forecast time it shows, from which run.
function showForecastCaption() {
  const caption = $("forecast-caption");
  if (!caption) return;
  const forecast = state.metForecastShown;
  const lines = [];
  const notes = [];
  if (forecast && state.layersApplied["Väderkarta (MET Norway)"] && forecast.isobars) {
    lines.push(`<strong>Väderkarta ${zulu(forecast.isobars.valid_utc)}</strong> (${formatLocal(forecast.isobars.valid_utc)})`);
  }
  if (forecast && state.layersApplied["Prognosvind (MET Norway)"]) {
    lines.push(`<strong>Prognosvind ${zulu(forecast.wind_grid_valid_utc)}</strong> (${formatLocal(forecast.wind_grid_valid_utc)})`);
  }
  if (lines.length) {
    const details = state.layersApplied["Väderkarta (MET Norway)"]
      ? ` · isobarer var 1 hPa, regn senaste 3 timmar${forecast.has_thunder ? ", ⚡ åska" : ""}` : "";
    notes.push(`Prognos från MET Norway utfärdad ${zulu(forecast.issued_utc)}${details} – inte live`);
  }
  // SMHI's observed lightning, when the layer is ticked and any struck in the hour.
  const flashes = state.lightningShown;
  if (flashes?.strikes.length && state.layersApplied["Blixtar (SMHI, observerade)"]) {
    lines.push(`<strong>Blixtnedslag senaste timmen:</strong> ${flashes.strikes.length}, varav ${flashes.near} inom ${flashes.near_km} km`);
    notes.push("Blixtar observerade av SMHI – gula är nyast");
  }
  caption.hidden = !lines.length;
  if (lines.length) caption.innerHTML = `${lines.join("<br>")}<small>${notes.join(" · ")}</small>`;
}

// SMHI's observed lightning in the hour before the clock (/api/lightning, lightning.py), fetched
// again when the clock has moved five minutes.
async function showLightning(clock) {
  if (!state.config.layers.lightning || !clock) return;
  const step = Math.floor(clock.getTime() / 300000);
  if (step === state.lightningStep) return;
  state.lightningStep = step;
  const at = new Date(step * 300000).toISOString().replace(".000Z", "Z");
  const data = await fetch(`/api/lightning?at=${encodeURIComponent(at)}`).then((response) => (response.ok ? response.json() : null)).catch(() => null);
  if (step !== state.lightningStep) return;
  state.lightningShown = data;
  state.map.drawLightning(data?.strikes || [], data?.near_history || []);
  showForecastCaption();
}

// Roads and railways the incident damaged (documented) and those under heavy rain (computed from
// the radar; routes.py, routes.js): both maps' layers and the computed pieces, fetched once.
async function setupRoutes(info) {
  state.routes = info;
  state.routeExposure = info.exposure_url ? await loadOptional(info.exposure_url, () => {}) : null;
  state.map.setupRoutes(info, Boolean(state.routeExposure));
  state.map.addAttribution(info.attribution);
}

// SMHI's rain by the day (daily_rain.py): each station's latest ended day, redrawn when one ends.
function showDailyRain(clock) {
  const info = state.config.layers.daily_rain;
  if (!info || !clock) return;
  const items = dailyRainAt(info.stations, clock.getTime());
  const key = items.map((item) => item.to_utc).join("|");
  if (key === state.dailyRainKey) return;
  state.dailyRainKey = key;
  state.map.drawDailyRain(items.map((item) => ({ ...item, text: `${item.name}: ${dailyRainText(item.mm)}`,
    detail: `Dygnet ${formatLocal(item.from_utc)} – ${formatLocal(item.to_utc)} (SMHI, dygnsvärde)` })));
}

// Meteosat's fire pixels (meteosat.py, meteosat.js), redrawn when the clock reaches a new one.
function showMeteosat(clock) {
  const info = state.config.layers.meteosat;
  if (!info || !clock) return;
  const pixels = meteosatPixelsAt(info.pixels, clock.getTime());
  if (pixels.length === state.meteosatCount) return;
  state.meteosatCount = pixels.length;
  state.map.drawMeteosat(pixels.map((pixel) => ({ ...pixel, text: meteosatText(pixel, formatLocal(pixel.time_utc)) })));
}

// LSA SAF's fire risk (meteosat_frm.py, meteosat_frm.js): a line under the demo's own FWI, with
// the classes' colours, and the maps' grid; both follow the latest day valid at the clock (12 UTC).
function setupMeteosatFrm(info) {
  const line = document.createElement("div");
  line.id = "frm-status";
  line.className = "status";
  line.innerHTML = '<strong>Brandrisk enligt LSA SAF:</strong> <span id="frm-text">ingen karta ännu</span><div class="frm-legend">'
    + Object.entries(info.risk_names).map(([risk, name]) => `<span><i style="background:${FRM_COLOURS[risk]}"></i>${name}</span>`).join("")
    + "</div>";
  const anchor = $("met-forecast-fwi") || $("forecast-values");
  if (anchor) anchor.after(line);
  else document.querySelector(".panel")?.append(line);
  state.map.setupMeteosatFrm(info.label);
  state.map.addAttribution(info.attribution);
}

function showMeteosatFrm(clock) {
  const info = state.config.layers.meteosat_frm;
  if (!info || !clock) return;
  const index = frmDayAt(info.days, clock.getTime());
  if (index === state.frmIndex) return;
  state.frmIndex = index;
  const when = index >= 0 ? formatLocal(info.days[index].valid_utc) : "";
  $("frm-text").textContent = frmText(info.at_fire[index], info.risk_names, when);
  state.map.drawMeteosatFrm(frmCells(info, index).map((cell) => ({ ...cell,
    text: `Brandrisk ${info.risk_names[cell.risk]}${cell.fwi === null ? "" : `, FWI ${Math.round(cell.fwi)}`} (LSA SAF, gäller ${when}; Meteosat och ERA5)` })));
}

// Meteosat's cloud top height (meteosat_cth.py, meteosat_cth.js): a chart of the mean over the map
// area after the rain and flows, with the log's thresholds, and the maps' cells of the quarter.
function setupMeteosatCth(info) {
  const section = document.createElement("section");
  section.id = "cth-section";
  section.className = "chart-section";
  section.innerHTML = "<h2>Molntoppar (Meteosat)</h2>"
    + '<svg id="cth-chart" class="timeline" role="img" aria-label="Molntopparnas medelhöjd över kartområdet"></svg>'
    + '<dl id="cth-values" class="forecast-values"></dl>'
    + '<div class="status">Medelhöjd över kartområdet, var 15:e minut. Stigande toppar visar åskmoln som växer, '
    + "ofta innan regnet når marken. Grova rutor så här långt norrut.</div>";
  const after = $("hydro-section") || $("rain-station")?.closest("section");
  if (after) after.after(section);
  else document.querySelector(".panel")?.append(section);
  state.map.setupMeteosatCth(info.label);
  state.map.addAttribution(info.attribution);
}

function showMeteosatCth(clock) {
  const info = state.config.layers.meteosat_cth;
  if (!info || !clock) return;
  const index = cthQuarterAt(info.quarters, clock.getTime());
  const key = `${index}|${state.config.playback.start_utc}|${state.config.playback.end_utc}`;
  if (key === state.cthKey) return;
  state.cthKey = key;
  const item = info.quarters[index];
  const when = item ? formatLocal(item.time_utc) : "";
  const decimal = (km) => String(km).replace(".", ",");
  $("cth-values").innerHTML = [
    ["Nu", item && item.mean_km !== null ? `${decimal(item.mean_km)} km, ${item.cloud_pct} % moln (kvarten från ${when})` : "ingen produkt ännu"],
  ].map(chartValue).join("");
  drawMeteosatCth(info, clock);
  state.map.drawMeteosatCth(item ? info.cells.flatMap((cell, position) => {
    const km = item.heights_km[position];
    return km === null ? [] : [{ corners: cell.corners, km, text: `Molntopp ${decimal(km)} km (Meteosat, kvarten från ${when})` }];
  }) : []);
}

function drawMeteosatCth(info, clock) {
  const start = Date.parse(state.config.playback.start_utc);
  const end = Date.parse(state.config.playback.end_utc);
  const width = 300;
  const height = CHART_HEIGHT;
  const top = 12;
  const xOf = (ms) => ((ms - start) / (end - start)) * width;
  const yOf = (km) => 6 + (1 - Math.min(km, top) / top) * (height - 26);
  const points = info.quarters.filter((item) => item.mean_km !== null);
  const path = points.map((item, index) => `${index ? "L" : "M"}${xOf(Date.parse(item.time_utc)).toFixed(1)},${yOf(item.mean_km).toFixed(1)}`).join(" ");
  const parts = [`<path class="cth-line" d="${path}"></path>`];
  for (const km of info.thresholds_km) {
    const y = yOf(km);
    parts.push(`<line class="hydro-record" x1="0" x2="${width}" y1="${y}" y2="${y}"></line>`, `<text x="2" y="${y - 2}">${km} km</text>`);
  }
  const every = Math.max(1, Math.ceil((end - start) / 86400000 / 9));
  for (let day = start; day < end; day += every * 86400000) {
    parts.push(`<text x="${xOf(day) + 1}" y="${height - 3}">${new Date(day).toISOString().slice(5, 10)}</text>`);
  }
  const x = xOf(clock.getTime());
  parts.push(`<line class="rain-now" x1="${x}" x2="${x}" y1="0" y2="${height - 14}"></line>`);
  const svg = $("cth-chart");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.innerHTML = parts.join("");
}

// Redrawn when a damage is reached or the computed rain passes into a new hour.
function showRoutes(clock) {
  if (!state.routes || !clock) return;
  const clockMs = clock.getTime();
  const impacts = routeImpactsAt(state.routes.impacts, clockMs);
  const hour = state.routeExposure ? Math.floor((clockMs - Date.parse(state.routeExposure.start_utc)) / 3600000) : 0;
  const key = `${impacts.length}|${hour}`;
  if (key === state.routesKey) return;
  state.routesKey = key;
  state.map.drawRoutes(impacts, routeExposureAt(state.routeExposure, clockMs));
}

// Copernicus EMS's perimeter of the fire (/api/ems, ems.js), with a line in the forecast's legend.
function setupEms(config) {
  state.map.setupEms();
  state.map.addAttribution(state.ems.attribution);
  const item = document.createElement("li");
  item.innerHTML = '<svg class="legend-arrow" viewBox="0 0 28 14" aria-hidden="true"><path d="M1,7 L27,7" stroke="#7b1fa2" '
    + 'stroke-width="3" stroke-dasharray="6 4" fill="none"/></svg><span><strong>lila streckad linje:</strong> brandområdet enligt '
    + 'Copernicus EMS, kartlagt ur en satellitbild – <span id="ems-note">ingen karta ännu</span>.</span>';
  $("forecast-label").closest("section").querySelector(".legend").prepend(item);
  showEms(state.clock);
}

function showEms(clock) {
  if (!state.ems || !clock) return;
  const product = emsAt(state.ems.products, clock.getTime());
  if (product === state.emsShown) return;
  state.emsShown = product;
  state.map.drawEms(product);
  $("ems-note").textContent = product ? emsText(product, (day) => localDate.format(new Date(`${day}T12:00:00Z`))) : "ingen karta ännu";
}

// SMHI's measured flows and lake levels (/api/hydro, hydro.js): a section after the rain with a
// chart of the chosen station, and a label on the map for each station.
const HYDRO_STYLE = { color: "#0b6e4f", fill: "#d8f3e8" };

function setupHydro(config) {
  const section = document.createElement("section");
  section.id = "hydro-section";
  section.dataset.incident = "flood";
  section.className = "chart-section";
  section.innerHTML = '<div class="chart-head"><h2>Vattenföring och vattenstånd (SMHI)</h2>'
    + '<label>Station <select id="hydro-station"></select></label></div>'
    + '<svg id="hydro-chart" class="timeline" role="img" aria-label="Vattenföring eller vattenstånd vid stationen"></svg>'
    + '<dl id="hydro-values" class="forecast-values"></dl><div id="hydro-note" class="status"></div>';
  $("rain-station").closest("section").after(section);
  for (const station of state.hydro.stations) {
    $("hydro-station").append(new Option(`${station.name} (${station.kind === "level" ? "vattenstånd" : "vattenföring"})`, station.id));
  }
  state.map.addStations(state.hydro.stations.map((station) => ({ ...station, id: `hydro-${station.id}` })), HYDRO_STYLE);
  state.hydroStation = state.hydro.stations[0]?.id || null;
  $("hydro-station").addEventListener("change", (event) => {
    state.hydroStation = event.target.value;
    state.hydroShownAt = null;
    showHydro(state.clock);
  });
  state.map.addAttribution(state.hydro.source);
  showHydro(state.clock);
}

function showHydro(clock) {
  if (!state.hydro || !clock) return;
  const hour = Math.floor(clock.getTime() / HOUR_MS);
  if (hour === state.hydroShownAt) return;
  state.hydroShownAt = hour;
  const labels = {};
  for (const station of state.hydro.stations) {
    const { latest, highest } = hydroAt(station.observations, clock.getTime());
    labels[`hydro-${station.id}`] = `${station.name}: ${hydroText(station.kind, latest?.value)}${hydroRecord(station, highest) ? " – rekord" : ""}`;
  }
  state.map.labelStations(labels);
  const station = state.hydro.stations.find((item) => item.id === state.hydroStation);
  if (!station) return;
  const { latest, highest } = hydroAt(station.observations, clock.getTime());
  const earlier = station.earlier_max;
  $("hydro-values").innerHTML = [
    ["Nu", latest ? `${hydroText(station.kind, latest.value)} (${hydroWhen(station.kind, latest.time_utc, formatLocal)})` : "inga värden ännu"],
    ["Högst i perioden", highest ? `${hydroText(station.kind, highest.value)} (${hydroWhen(station.kind, highest.time_utc, formatLocal)})` : "–"],
    ["Tidigare högsta", earlier ? `${hydroText(station.kind, earlier.value)} (${earlier.time_utc.slice(0, 4)}, mätt sedan ${station.measured_since.slice(0, 4)})` : "–"],
  ].map(chartValue).join("");
  $("hydro-note").textContent = (hydroRecord(station, highest) ? "Högre än allt som mätts här tidigare. " : "")
    + (station.kind === "level" ? "Vattenstånd per dygn i stationens höjdsystem. " : "Vattenföring, timmedelvärden. ")
    + (station.unchecked ? "SMHI har ännu inte kvalitetsgranskat alla värden." : "Kvalitetsgranskade värden från SMHI.");
  drawHydro(station, clock);
}

function drawHydro(station, clock) {
  const start = Date.parse(state.config.playback.start_utc);
  const end = Date.parse(state.config.playback.end_utc);
  const width = 300;
  const height = CHART_HEIGHT;
  const values = station.observations.map((item) => item.value);
  const top = Math.max(...values, station.earlier_max?.value ?? -Infinity);
  const bottom = Math.min(...values);
  const span = Math.max(top - bottom, 1e-6);
  const xOf = (ms) => ((ms - start) / (end - start)) * width;
  const yOf = (value) => 6 + (1 - (value - bottom) / span) * (height - 26);
  const path = station.observations.map((item, index) => `${index ? "L" : "M"}${xOf(Date.parse(item.time_utc)).toFixed(1)},${yOf(item.value).toFixed(1)}`).join(" ");
  const parts = [`<path class="hydro-line" d="${path}"></path>`];
  if (station.earlier_max) {
    const y = yOf(station.earlier_max.value);
    parts.push(`<line class="hydro-record" x1="0" x2="${width}" y1="${y}" y2="${y}"></line>`,
      `<text x="2" y="${y - 2}">tidigare högsta ${station.earlier_max.time_utc.slice(0, 4)}</text>`);
  }
  const every = Math.max(1, Math.ceil((end - start) / 86400000 / 9));
  for (let day = start; day < end; day += every * 86400000) {
    parts.push(`<text x="${xOf(day) + 1}" y="${height - 3}">${new Date(day).toISOString().slice(5, 10)}</text>`);
  }
  const x = xOf(clock.getTime());
  parts.push(`<line class="rain-now" x1="${x}" x2="${x}" y1="0" y2="${height - 14}"></line>`);
  const svg = $("hydro-chart");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.innerHTML = parts.join("");
}

// SMHI's weather radar as a rain layer (config.layers.radar, tools/fetch_smhi_radar.py), in the
// stations' classes; it follows the scenario clock.
function setupRadar(config) {
  state.radar = config.layers.radar;
  state.map.setupRadar(state.radar);
  state.map.addAttribution(state.radar.attribution);
  const item = document.createElement("li");
  item.textContent = "Radarlagret Nederbörd (SMHI radar), även över havet: SMHI:s väderradar omräknad till regn "
    + "(Z = 200·R^1,6) i samma klasser – en uppskattning från radarn, inte en mätning på marken.";
  $("rain-legend").append(item);
  showRadar(state.clock);
}

function showRadar(clock) {
  if (!state.radar || !clock) return;
  const frame = radarFrameAt(state.radar.frames, clock.getTime(), state.radar.step_minutes);  // rain.js
  const url = frame ? frame.url : null;
  if (url === state.radarShown) return;
  state.radarShown = url;
  state.map.showRadar(url);
}

// The flood maps (config.layers.wms): the municipality's and MCF's models, through the backend.
// A service that does not answer is left out, so its requests do not hold up the screens.
function setupFloodMaps(config) {
  const legend = $("flood-legend");
  // The scenario's own period, not the demo's start and stop.
  const period = floodPeriodText(config.playback.data_start_utc, config.playback.data_end_utc);
  $("flood-maps-note").textContent = `Modeller av vad som kan översvämmas, inte observationer av ${period}. Välj lager i kartans lagerlista.`;
  for (const source of config.layers.wms || []) {
    if (source.available === false) {
      const item = document.createElement("li");
      item.className = "alert";
      item.textContent = `${source.attribution}: karttjänsten svarar inte – dess översvämningskartor visas inte.`;
      legend.append(item);
      continue;
    }
    state.map.addWms(source);
    state.map.addAttribution(source.attribution);
    for (const title of Object.values(source.layers)) {
      const item = document.createElement("li");
      item.textContent = `${title} – ${source.attribution}`;
      legend.append(item);
    }
  }
}

// The cloudburst model's depth colours (flood_legend.js), shown while a depth layer is.
function setupDepthLegend() {
  $("depth-classes").innerHTML = DEPTH_CLASSES.map((item) => `<li><span class="swatch" style="background:${item.color}"></span>${item.text}</li>`).join("");
  state.map.onWmsChange((names) => { $("depth-legend").hidden = !depthLegendShown(names); });
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
  state.map.showWind(hour, state.wind);
  const sea = state.wind.sources?.some((source) => source !== "ERA5-Land") ? " Över havet: ERA5, interpolerad från 0,25°." : "";
  $("wind-note").textContent = hour < 0 ? "Inga vinddata för tiden." : `Modellvärden för ${formatLocal(state.wind.times_utc[hour])}.${sea}`;
}

function windTooltip(position, hour) {
  const [speed, from, temperature] = state.wind.values[hour][position];
  const [lat, lon] = state.wind.points[position];
  return `${state.wind.sources?.[position] || "ERA5-Land"} ${lat.toFixed(1)} N ${lon.toFixed(1)} E<br>${speed.toFixed(1)} m/s från ${compassPoint(from)} (${from}°), ${temperature} °C`
    + `<br>${formatLocal(state.wind.times_utc[hour])}`;
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

function drawForecast(clock) {
  if (!state.forecast) return;
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
      ["Brandväder", weather.fwi !== undefined ? `FWI ${weather.fwi}, BUI ${weather.bui}, ISI ${weather.isi} (${state.config.forecast_station})` : "saknas"],
    ].map(([label, value]) => `<dt>${label}</dt><dd>${value}</dd>`).join("");
  } else {
    values.innerHTML = "<dt>Prognos</dt><dd>ingen satellitdetektion ännu</dd>";
  }
  if (key === state.forecastPass) return;
  state.forecastPass = key;
  state.map.drawForecast(current, state.forecastHorizon);
  if (!current) {
    $("forecast-places").textContent = "";
    return;
  }
  const list = current.places_within_24h.slice(0, 6).map((place) => `${place.names[0]} ${place.span}`).join(", ");
  $("forecast-places").textContent = current.places_within_24h_count
    ? `Orter inom ytan för dubbel hastighet inom 24 h: ${current.places_within_24h_count}. Först: ${list}. Spannet är tid vid dubbel–halv hastighet.`
    : "Inga orter inom ytan för dubbel hastighet inom 24 h.";
}

function setClock(clock) {
  state.clock = clock;
  $("sim-time").textContent = formatLocal(clock.toISOString());
  state.map.restyleHotspots(clock);
  $("counts").textContent = `${state.map.hotspotCount()} detektioner visas`;
  if (state.config.incident === "wildfire") {
    drawTimeline(state.daily, clock);
    showWeather(clock);
  }
  showMetForecast(clock);
  showLightning(clock);
  showMeteosat(clock);
  showMeteosatFrm(clock);
  showMeteosatCth(clock);
  showRoutes(clock);
  showDailyRain(clock);
  showRain(clock);
  showHydro(clock);
  showEms(clock);
  showRadar(clock);
  showWind(clock);
  drawForecast(clock);
  showSatellites(clock);
  showLandsatAt(clock);
}

async function setupLandsat(config) {
  const section = document.createElement("section");
  section.innerHTML = '<h2>Satellitbild</h2>'
    + '<div id="landsat-legend" class="ndmi-legend" hidden></div>'
    // The radar's computed water (radarwater): what its red means, while it is shown.
    + '<div id="radarwater-legend" class="radarwater-legend" hidden><span class="swatch"></span><span><strong>Rött:</strong> vatten '
    + 'i radarbilden utanför sjöar och hav, beräknat med en enkel tröskel – inte en kartlagd översvämning. '
    + 'Sentinel-1 ser genom moln.</span></div>'
    + '<div id="landsat-note" class="status"></div>'
    + '<div class="status">Välj karta eller bild i mission control.</div>';
  $("satellite-section").after(section);
  const info = config.layers.landsat;
  // The image types "auto" follows until mission control ticks others (landsat.js defaultImageTypes).
  state.imageTypes = defaultImageTypes(config.incident, info?.names);
  if (!info) {
    $("landsat-note").textContent = "Satellitbilden är inte hämtad (tools/fetch_landsat_scene.py).";
    showViewCaption(null, null, "missing");
    return;
  }
  if (info.ndmi_colours) {
    // The NDMI scale: brown dry to blue moist, with the index at the ends and the middle.
    const stops = info.ndmi_colours;
    const low = stops[0][0];
    const high = stops[stops.length - 1][0];
    const gradient = stops.map(([value, rgb]) => `rgb(${rgb.join(",")}) ${Math.round((100 * (value - low)) / (high - low))}%`).join(", ");
    $("landsat-legend").innerHTML = `<span class="bar" style="background: linear-gradient(to right, ${gradient})"></span>`
      + `<span>torrt ${String(low).replace(".", ",")}</span><span>fuktigt ${String(high).replace(".", ",")}</span>`;
  }
  state.landsat = info;
  await state.map.setupLandsat(info);
  state.map.addAttribution(info.attribution);
  showLandsatAt(state.clock);
}

// The main screen's caption: what is shown under the overlays, dated (landsat.js viewCaption).
function showViewCaption(scene, image, reason) {
  $("view-caption").textContent = viewCaption({
    scene, image, reason, choice: state.imageTypes, baseMap: state.baseMap, mapData: state.config.layers.map_data, offlineTiles: state.config.layers.offline_tiles,
    formatTime: formatLocal, formatDate: (isoUtc) => localDate.format(new Date(isoUtc)),
    // The fire's detection sequence: its FIRMS pass over the image or map (the flood's image is the detection).
    detection: state.detection && state.detection.pass.kind !== "flood" ? state.detection.pass : null,
  });
}

// The scene and image of a key "scene|image" (landsat.js).
function sceneOfKey(key) {
  const [name, image] = key.split("|");
  return [state.landsat.scenes.find((item) => item.scene === name) || null, image];
}

// What an image says about its conditions: cloud for the optical, the water mask's certainty for the radar.
function sceneConditions(scene) {
  if (scene.cloud_pct !== null && scene.cloud_pct !== undefined) {
    return `${String(scene.cloud_pct).replace(".", ",")} % moln över ${state.config.incident_area}`;
  }
  if (scene.separable === false) return "radar genom molnen; vatten och land skiljs dåligt åt i bilden";
  if (scene.new_water_pct !== undefined) {
    return `radar genom molnen; beräknat vatten utanför sjöar och hav på ${String(scene.new_water_pct).replace(".", ",")} % av ${state.config.focus_land}`;
  }
  return "radar genom molnen";
}

// The image mission control chose, or the latest taken up to the scenario clock; an image
// taken after the scenario is a comparison (landsat.js).
function showLandsatAt(clock) {
  if (!state.landsat || !clock) return;
  // The flood's detection sequence shows its own radar image while it runs.
  if (state.detectionImage) {
    if (state.landsatShown !== state.detectionImage) state.map.showLandsat(state.detectionImage);
    state.landsatShown = state.detectionImage;
    showViewCaption(...sceneOfKey(state.detectionImage), "shown");
    return;
  }
  const selection = landsatSelection(state.landsat.scenes, clock.getTime(), state.landsatPick, state.imageTypes);
  const key = state.hiddenLayers.includes("space") ? null : selection.key;
  const scene = selection.scene;
  const image = selection.key?.split("|")[1];
  const notes = {
    off: "Kartan visas, ingen satellitbild.",
    "none-yet": "Ingen bild är tagen ännu vid scenariotiden.",
    "no-types": "Kartan visas: inga bildtyper är valda i mission control.",
  };
  $("landsat-note").textContent = notes[selection.reason]
    || `${scene.label}, ${sceneConditions(scene)}. ${state.landsat.names[image]}.`
      + (selection.reason === "comparison" ? " Tagen senare – inte läget vid scenariotiden." : "");
  $("landsat-legend").hidden = !(key && image === "ndmi");
  $("radarwater-legend").hidden = !(key && image === "radarwater");
  if (key) showViewCaption(...sceneOfKey(key), selection.reason);
  else showViewCaption(null, null, selection.reason);
  if (key === state.landsatShown) return;
  state.landsatShown = key;
  state.map.showLandsat(key);
}

const SATELLITE_JS = "/vendor/satellite.js-7.1.0/index.js";

async function setupSatellites(config) {
  const section = document.createElement("section");
  section.id = "satellite-section";
  section.innerHTML = `<h2>Satelliter ${config.playback.start_utc.slice(0, 4)}</h2><ul id="satellite-list"`
    + ' class="scenario-status"></ul><div id="satellite-note" class="status"></div>';
  $("assessment-evidence").closest("section").after(section);
  if (!config.layers.satellites) {
    $("satellite-note").textContent = "Banelementen är inte hämtade (tools/fetch_tle_history.py); inga satelliter visas.";
    return;
  }
  const data = await loadOptional("/api/satellites", (error) => { $("satellite-note").textContent = `Satelliterna kunde inte laddas: ${error.message}.`; });
  if (!data?.available) return;
  try {
    state.satelliteLib = await import(SATELLITE_JS);
  } catch (error) {
    $("satellite-note").textContent = `satellite.js saknas (tools/fetch_web_vendor.py): ${error.message}.`;
    return;
  }
  state.satellites = data;
  $("satellite-note").textContent = `${data.label}. Källa: ${data.source}.`;
  // The satellite monitor has its own window (monitor.html); ?monitor=1 also shows it in a corner here.
  if (new URLSearchParams(window.location.search).get("monitor") === "1") {
    const hourMinute = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", hour: "2-digit", minute: "2-digit" });
    state.monitor = createSatelliteMonitor($("map"), config.fire_centre, (time) => hourMinute.format(time), MONITOR_SIZE, config.incident_place,
      config.playback.start_utc.slice(0, 4));
  }
  precomputePasses();
}

// Compute the passes of every playback day in the background, one satellite day at a time,
// so the playback never waits for them.
function precomputePasses() {
  const first = Math.floor(Date.parse(state.config.playback.start_utc) / DAY_MS);
  const last = Math.floor(Date.parse(state.config.playback.end_utc) / DAY_MS);
  const work = [];
  for (let day = first; day <= last + 1; day += 1) {
    for (const item of state.satellites.satellites) if (hasPasses(item)) work.push([item, day]);
  }
  const later = window.requestIdleCallback || ((callback) => setTimeout(callback, 50));
  const next = () => {
    const entry = work.shift();
    if (!entry) return;
    passesOn(entry[0], entry[1]);
    later(next);
  };
  later(next);
}

function passesOn(item, day) {
  const key = `${item.norad}|${day}`;
  if (!state.passCache.has(key)) {
    const [lat, lon] = state.config.fire_centre;
    state.passCache.set(key, satellitePasses(state.satelliteLib, item, day * DAY_MS, (day + 1) * DAY_MS, lat, lon));
  }
  return state.passCache.get(key);
}

const DAY_MS = 86400000;

// The pass over the fire that is going on or comes next, from the passes of this and the
// next scenario day (computed once per day and kept).
function passFor(item, clock) {
  const now = clock.getTime();
  const today = Math.floor(now / DAY_MS);
  for (const day of [today, today + 1]) {
    const pass = passesOn(item, day).find((candidate) => candidate.end > now);
    if (pass) return pass;
  }
  return null;
}

function showSatellites(clock) {
  if (!state.satelliteLib || !clock) return;
  // Nothing moves while the playback stands still.
  if (state.satellitesDrawnAt === clock.getTime()) return;
  state.satellitesDrawnAt = clock.getTime();
  const lib = state.satelliteLib;
  // Only the satellites that send the scenario data to the ground get an orbit (orbits.js).
  const contributing = contributingSatellites(state.satellites.satellites, state.config.layers.landsat?.scenes);
  const items = state.satellites.satellites.map((satellite) => ({
    ...satellite,
    point: subpoint(lib, satellite.elements, clock),
    track: contributing.has(satellite.name) ? orbitTrack(lib, satellite.elements, clock, 50, 2) : [],
  })).filter((item) => item.point);
  state.map.drawSatellites(items);
  if (state.monitor) {
    // The monitor's timeline needs the passes from an hour back to five hours ahead.
    const first = Math.floor((clock.getTime() - MONITOR_WINDOW.beforeMs) / DAY_MS);
    const last = Math.floor((clock.getTime() + MONITOR_WINDOW.afterMs) / DAY_MS);
    state.monitor.draw(items.map((item) => ({
      ...item,
      passes: hasPasses(item) ? Array.from({ length: last - first + 1 }, (_, i) => passesOn(item, first + i)).flat() : null,
    })), clock);
  }
  // Height, speed and next pass change slowly; recompute them every 10 scenario minutes.
  if (state.satelliteInfoAt !== null && Math.abs(clock - state.satelliteInfoAt) < 600000) return;
  state.satelliteInfoAt = clock;
  fillList("satellite-list", items.map((item) => {
    const instrument = item.instrument ? ` (${item.instrument})` : "";
    let pass = item.geostationary ? ` · geostationär, ser ${state.config.incident_place} hela tiden` : "";
    if (hasPasses(item)) {
      const next = passFor(item, clock);
      const place = state.config.incident_place;
      pass = next === null ? ` · ingen passage över ${place} inom 24 h`
        : next.start <= clock.getTime() ? ` · över ${place} nu`
        : ` · nästa passage över ${place} ${clockTime.format(new Date(next.start))} svensk tid`;
    }
    return { level: "info", text: `${item.name}${instrument}: ${Math.round(item.point.height_km)} km, `
      + `${item.point.speed_km_s.toFixed(1).replace(".", ",")} km/s${pass}` };
  }), "Inga satelliter.");
}

// A new detection: the satellite that made it, at the time it made it, with a line down to it.
function flashDetectionSatellite(feature) {
  if (!state.satelliteLib) return;
  const properties = feature.properties;
  const satellite = state.satellites.satellites.find((item) => item.firms === properties.satellite);
  const key = `${properties.satellite}|${properties.acq_datetime_utc}`;
  if (!satellite || state.flashedPasses.has(key)) return;
  state.flashedPasses.add(key);
  const time = new Date(properties.acq_datetime_utc);
  const from = subpoint(state.satelliteLib, satellite.elements, time);
  if (!from) return;
  const [lon, lat] = feature.geometry.coordinates;
  state.map.flashSatellite({
    norad: satellite.norad, from, to: [lat, lon],
    label: `${properties.instrument}-detektion ${properties.acq_datetime_utc.slice(11, 16)} UTC (${satellite.name})`,
  });
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

// Mission-control events: a banner over the map per event and a status list in the
// panel. The banner waits for the state that follows the event, so a toggle shows
// whether it was switched on or off.
function setupScenarioView() {
  const section = document.createElement("section");
  section.innerHTML = '<h2>Läge</h2><ul id="scenario-status" class="scenario-status"></ul><div id="satcom-queue" class="satcom-queue"></div>'
    + '<ul id="satcom-sync" class="scenario-status"></ul><div id="iot-confirms" class="iot-confirms"></div>';
  // After the playback and its time charts.
  const charts = document.querySelectorAll(".panel .chart-section");
  (charts[charts.length - 1] || document.querySelector(".panel section")).after(section);
  const assessmentSection = document.createElement("section");
  assessmentSection.innerHTML = '<h2>AI ASSESSMENT</h2><div id="assessment-outcome" class="assessment-outcome">–</div>'
    + '<div id="assessment-score" class="status"></div><h3>Evidence</h3><ul id="assessment-evidence" class="evidence"></ul>'
    + '<div class="status">Klicka på en rad för att visa objektet på kartan.</div>'
    + '<h3>Fråga</h3><div id="questions" class="questions"></div>'
    + '<div id="answer" class="answer" hidden><p id="answer-text"></p><div id="answer-meta" class="status"></div>'
    + '<details><summary>SQL som kördes</summary><pre id="answer-sql"></pre></details>'
    + '<button id="answer-clear" type="button">Rensa svaret från kartan</button></div>';
  section.after(assessmentSection);
  const iotSection = document.createElement("section");
  iotSection.innerHTML = '<h2>IoT</h2><h3>Noder i montern</h3><ul id="real-sensors" class="scenario-status"></ul>'
    + `<div id="iot-connection" class="status"></div><h3>Syntetiska sensorer i ${state.config.incident_area}</h3>`
    + '<ul id="synthetic-sensors" class="scenario-status"></ul><div id="synthetic-label" class="status"></div>';
  assessmentSection.after(iotSection);
  const banner = document.createElement("div");
  banner.id = "event-banner";
  banner.className = "event-banner";
  banner.setAttribute("role", "status");
  banner.hidden = true;
  document.body.append(banner);
  const summary = document.createElement("section");
  summary.id = "scenario-summary";
  summary.className = "scenario-summary";
  summary.setAttribute("role", "status");
  summary.hidden = true;
  document.body.append(summary);
  const card = document.createElement("section");
  card.id = "detection-card";
  card.className = "detection-card";
  card.setAttribute("aria-live", "polite");
  card.hidden = true;
  card.innerHTML = '<h2>UPPTÄCKT FRÅN RYMDEN <small id="detection-pass"></small></h2><ol id="detection-steps" class="detection-steps"></ol>'
    + '<p id="detection-detail" class="detection-detail"></p><div id="detection-rules" hidden><h3 id="detection-outcome"></h3>'
    + '<ul id="detection-rule-list" class="evidence"></ul><div id="detection-label" class="status"></div></div>';
  $("map").append(card);
  if (window.L) L.DomEvent.disableClickPropagation(card);
}

// The detection sequence (mission control's SATELLITE DETECTION and NEXT): a card over the
// map with the steps, each marked real or synthetic, and what the current step shows.
async function followDetection(detection) {
  const key = detection ? `${detection.pass_utc}|${detection.step}` : null;
  if (key === state.detectionKey) return;
  state.detectionKey = key;
  if (!detection) {
    state.detection = null;
    if (state.detectionImage) {
      state.detectionImage = null;
      state.landsatShown = undefined;
    }
    showLandsatAt(state.clock);  // the caption without the sequence's detections
    $("detection-card").hidden = true;
    state.map.highlightSatellite(null);
    state.monitor?.setMark(null);
    return;
  }
  if (state.detection?.pass_utc !== detection.pass_utc) {
    const info = await getJson("/api/detection").catch(() => null);
    if (state.detectionKey !== key || !info) return;  // a newer step came while waiting
    state.detection = { pass_utc: info.pass_utc, pass: info.pass, classification: info.classification };
    state.monitor?.setMark({ atMs: Date.parse(info.pass.pass_utc), firms: info.pass.satellite, norad: info.pass.norad });
  }
  const info = { ...state.detection, ...detection };
  showDetection(info);
  showDetectionImage(info);
  showLandsatAt(state.clock);  // the caption with the sequence's detections
  // The fire's passes name the FIRMS satellite, the flood's the NORAD number.
  const satellite = state.satellites?.satellites.find((item) => (item.firms && item.firms === info.pass.satellite) || item.norad === info.pass.norad);
  if (info.name === "acquired") state.map.highlightSatellite(satellite?.norad, { fly: true });
  if (info.name === "zoom") {
    state.map.highlightSatellite(null);
    state.map.focusOn(info.pass.centre.latitude, info.pass.centre.longitude);
  }
}

// The flood's sequence: its radar image from "Bild tagen" to "Zoom", where the camera is close
// enough to see it, and the image's computed water from "IoT på marken" on, over the map.
// The fire's sequence shows its detections instead.
function showDetectionImage(info) {
  if (info.pass.kind !== "flood" || !state.landsat) return;
  const scene = state.landsat.scenes.find((item) => item.acquired_utc === info.pass.pass_utc && item.images.radar);
  const steps = DETECTION_STEPS.map((item) => item.name);
  const image = steps.indexOf(info.name) >= steps.indexOf("iot") ? "radarwater" : "radar";
  state.detectionImage = scene ? `${scene.scene}|${image}` : null;
  state.landsatShown = undefined;
  showLandsatAt(state.clock);
}

function showDetection(info) {
  const card = $("detection-card");
  card.hidden = false;
  $("detection-pass").textContent = `${info.pass.instrument} · ${info.pass.pass_utc.slice(0, 16).replace("T", " ")} UTC`;
  const list = $("detection-steps");
  list.innerHTML = "";
  for (const item of detectionSteps(info.step, state.config.incident_place)) {
    const row = document.createElement("li");
    row.className = item.state;
    const tag = document.createElement("span");
    tag.className = item.real ? "tag real" : "tag synthetic";
    tag.textContent = item.real ? "VERKLIGA DATA" : "SYNTETISKT";
    row.append(item.title, " ", tag);
    list.append(row);
  }
  $("detection-detail").textContent = detectionDetail(info, state.synthetic ? confirmsText(state.synthetic) : null, state.config.incident_place,
    state.config.sensor_words.the_sensors);
  const rules = $("detection-rules");
  rules.hidden = info.name !== "correlate";
  if (rules.hidden) return;
  $("detection-outcome").textContent = info.classification.outcome;
  $("detection-label").textContent = info.classification.label;
  const ruleList = $("detection-rule-list");
  ruleList.innerHTML = "";
  for (const rule of info.classification.rules) {
    const row = document.createElement("li");
    row.className = rule.holds ? "ok" : "miss";
    row.textContent = `${rule.holds ? "✓" : "✗"} ${rule.category}: ${rule.text}`;
    if (rule.ref) {
      row.tabIndex = 0;
      row.classList.add("linked");
      const focus = () => state.map.focusOn(rule.ref.latitude, rule.ref.longitude);
      row.addEventListener("click", focus);
      row.addEventListener("keydown", (event) => { if (event.key === "Enter") focus(); });
    }
    ruleList.append(row);
  }
}

let bannerTimer = null;

function showBanner(text) {
  const banner = $("event-banner");
  banner.innerHTML = "";
  const title = document.createElement("strong");
  title.textContent = text.title;
  const detail = document.createElement("span");
  detail.textContent = text.detail;
  banner.append(title, detail);
  banner.hidden = false;
  clearTimeout(bannerTimer);
  bannerTimer = setTimeout(() => { banner.hidden = true; }, 10000);
}

function setHorizon(horizon) {
  $("forecast-horizon").value = horizon;
  state.forecastHorizon = horizon;
  drawForecast(state.clock);
}

// The main screen's own controls (the map's layer list) only for troubleshooting: ?controls=1.
function showControls() {
  return new URLSearchParams(window.location.search).get("controls") === "1";
}

// Mission control's choices for the panel (the status's choices; server.py panel_choices): the
// forecast horizon and the stations shown. A choice not set keeps the panel's own.
const CHOICE_APPLY = {
  horizon: (value) => {
    if (state.scenarioStatus?.plus60) state.horizonBeforePlus60 = value;  // +60 MIN keeps its horizon until switched off
    else setHorizon(value);
  },
  weather_station: (value) => {
    state.weatherStation = value;
    $("weather-station").value = value;
    showWeather(state.clock);
  },
  rain_station: (value) => {
    state.rainStation = value;
    $("rain-station").value = value;
    state.rainShownAt = null;
    showRain(state.clock);
  },
  hydro_station: (value) => {
    state.hydroStation = value;
    $("hydro-station").value = value;
    state.hydroShownAt = null;
    showHydro(state.clock);
  },
};

function applyChoices(status) {
  for (const [key, value] of Object.entries(status.choices || {})) {
    if (state.choicesApplied[key] === value || !CHOICE_APPLY[key]) continue;
    if (key === "hydro_station" && !state.hydro) continue;  // tried again once the stations are loaded
    state.choicesApplied[key] = value;
    CHOICE_APPLY[key](value);
  }
}

// Mission control's layer ticks: a switched layer as switched, the others as this map starts them.
// A layer the map has not made yet is tried again with the next state.
function applyMapLayers(status) {
  const key = state.map.dimension === "2d" ? "default_2d" : "default_3d";
  for (const item of state.config.layers.map_layers || []) {
    const wanted = status.map_layers?.[item.name] ?? item[key];
    if (wanted === null || wanted === undefined || state.layersApplied[item.name] === wanted) continue;
    if (!state.map.setLayerVisible(item.name, wanted)) continue;
    // The weather chart is read over Scandinavia: the map flies out when it is ticked and back when not.
    if (item.name === "Väderkarta (MET Norway)" && (wanted || state.layersApplied[item.name])) state.map.showWeatherChartView(wanted);
    state.layersApplied[item.name] = wanted;
  }
  showForecastCaption();
}

// Mission control's questions: a new one is asked and answered here; a screen that connects shows
// the one standing; RENSA SVARET and RESET take it away.
function applyQuestion(status, previous) {
  const question = status.question;
  if (!question || (previous && previous.question?.seq === question.seq)) return;
  if (question.id) askQuestion(question.id);
  else if (previous) {
    state.map.drawQueryResult(null);
    $("answer").hidden = true;
  }
}

function applyStatus(status) {
  const previous = state.scenarioStatus;
  state.scenarioStatus = status;
  const lines = statusLines(status);
  const list = $("scenario-status");
  list.innerHTML = "";
  for (const line of lines.length ? lines : [{ level: "ok", text: "Inga händelser från mission control." }]) {
    const item = document.createElement("li");
    item.className = line.level;
    item.textContent = line.text;
    list.append(item);
  }
  // Read by styles.css and tools/record_demo.py.
  document.body.dataset.satcom = status.satcom_up ? "up" : "down";
  if (state.forecast && status.plus60 !== Boolean(previous?.plus60)) {
    if (status.plus60) {
      state.horizonBeforePlus60 = state.forecastHorizon;
      setHorizon(String(Math.min(...state.forecast.horizons_h)));
    } else if (state.horizonBeforePlus60) {
      setHorizon(state.horizonBeforePlus60);
      state.horizonBeforePlus60 = null;
    }
  }
  if (status.god_view !== Boolean(previous?.god_view)) state.map.showGodView(status.god_view);
  // FLYG TILL and ÖVERSIKT in mission control: only a new request, not the one a screen finds when it connects.
  if (previous && status.camera && status.camera.seq !== previous.camera?.seq) {
    if (status.camera.target === "incident") state.map.flyToIncident();
    else if (status.camera.target === "home") state.map.flyHome();
  }
  if (status.space_view !== Boolean(previous?.space_view)) {
    state.map.showSpaceView(status.space_view);
    $("satellite-section")?.classList.toggle("space-view", status.space_view);
  }
  showFilter(status);
  applyMapLayers(status);
  applyChoices(status);
  applyQuestion(status, previous);
  if (status.iot !== (previous?.iot ?? true)) showRealSensors();
  followDetection(status.detection);
}

// GOD VIEW's filter, set from mission control: the list on the map and the hidden categories.
function showFilter(status) {
  for (const category of FILTER_CATEGORIES.filter((item) => !item.missing)) {
    const hidden = status.hidden_layers.includes(category.id);
    if (hidden !== state.hiddenLayers.includes(category.id)) state.map.setCategoryVisible(category.id, !hidden);
  }
  state.hiddenLayers = [...status.hidden_layers];
  state.landsatPick = status.image || "auto";  // mission control's choice of map or image
  if (state.landsat) state.imageTypes = imageTypesShown(status.image_types, state.config.incident, state.landsat.names);
  // Mission control's base maps: the first this map has of the ticked ones.
  const baseMaps = state.config.layers.base_maps;
  const baseMap = baseMapFor(baseMapsShown(status.base_maps, baseMaps), baseMaps, state.map.dimension);
  if (baseMap !== state.baseMap) {
    state.baseMap = baseMap;
    state.map.setBaseMap(baseMap);
  }
  showLandsatAt(state.clock);
  let panel = $("god-filter");
  if (!panel) {
    panel = document.createElement("ul");
    panel.id = "god-filter";
    panel.className = "god-filter";
    $("map").append(panel);
  }
  panel.hidden = !status.god_view;
  panel.innerHTML = "";
  for (const category of FILTER_CATEGORIES) {
    const item = document.createElement("li");
    const shown = !category.missing && !status.hidden_layers.includes(category.id);
    item.className = category.missing ? "missing" : shown ? "shown" : "hidden";
    item.textContent = `${shown ? "☑" : "☐"} ${category.label}${category.missing ? ` – ${MISSING_NOTE}` : ""}`;
    panel.append(item);
  }
}

function fillList(id, lines, empty) {
  const list = $(id);
  list.innerHTML = "";
  for (const line of lines.length ? lines : [{ level: "ok", text: empty }]) {
    const item = document.createElement("li");
    item.className = line.level;
    item.textContent = line.text;
    list.append(item);
  }
}

function showRealSensors() {
  const readings = [...state.realSensors.values()].sort((a, b) => `${a.node}/${a.kind}`.localeCompare(`${b.node}/${b.kind}`));
  if (state.scenarioStatus?.iot === false) {
    fillList("real-sensors", [{ level: "alert", text: "IoT avstängt från mission control" }], "");
    return;
  }
  fillList("real-sensors", readings.map(realSensorLine), "Inga noder.");
  if (state.iotConnection) $("iot-connection").textContent = connectionText({ ...state.iotConnection, sensors: readings });
}

function showSynthetic(result) {
  state.synthetic = result;
  fillList("synthetic-sensors", result.sensors.map(syntheticSensorLine), result.disabled ? "IoT avstängt." : "Inga sensorer.");
  $("synthetic-label").textContent = result.label;
  $("iot-confirms").textContent = confirmsText(result);
  state.map.drawSyntheticSensors(result);
  // The IoT step of the detection sequence quotes the sensors at its time.
  if (state.detection && state.scenarioStatus?.detection?.name === "iot") {
    $("detection-detail").textContent = detectionDetail({ ...state.detection, ...state.scenarioStatus.detection }, confirmsText(result),
      state.config.incident_place, state.config.sensor_words.the_sensors);
  }
}

const QUERY_COLOR = "#7b1fa2";

function queryLabel(properties) {
  const name = properties.name || `${properties.kind} (${properties.type})`;
  if (properties.distance_m === null || properties.distance_m === undefined) return name;
  return `${name} – ${String((properties.distance_m / 1000).toFixed(1)).replace(".", ",")} km från brandfronten`;
}

const EVIDENCE_MARKS = { ok: "✓", warn: "⚠", miss: "✗", info: "ℹ" };

// The assessment (app/backend/assessment.py): each evidence line points at its object.
function showAssessment(result) {
  $("assessment-outcome").textContent = result.outcome;
  $("assessment-outcome").dataset.outcome = result.outcome;
  $("assessment-score").textContent = `Poäng ${result.score_pct} % – ${result.score_label}`;
  const list = $("assessment-evidence");
  list.innerHTML = "";
  for (const item of result.evidence) {
    const row = document.createElement("li");
    row.className = item.status;
    row.textContent = `${EVIDENCE_MARKS[item.status] || ""} ${item.text}`;
    if (item.ref) {
      row.tabIndex = 0;
      row.classList.add("linked");
      const focus = () => state.map.focusOn(item.ref.latitude, item.ref.longitude);
      row.addEventListener("click", focus);
      row.addEventListener("keydown", (event) => { if (event.key === "Enter") focus(); });
    }
    list.append(row);
  }
}

// Prepared questions (app/backend/spatial.py): the answer, its SQL and the result on the map.
async function askQuestion(id) {
  $("answer").hidden = false;
  $("answer-text").textContent = "Frågar PostGIS …";
  $("answer-meta").textContent = "";
  try {
    const response = await fetch(`/api/ask?q=${encodeURIComponent(id)}`);
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || body.error || `HTTP ${response.status}`);
    $("answer-text").textContent = body.answer;
    $("answer-meta").textContent = `${body.source} · ${String(body.elapsed_ms).replace(".", ",")} ms · scenariotid ${formatLocal(body.clock_utc)}`;
    $("answer-sql").textContent = body.sql || "Ingen SQL – svaret kommer från bedömningen ovan.";
    state.map.drawQueryResult(body.features);
  } catch (error) {
    $("answer-text").textContent = `Frågan kunde inte besvaras: ${error.message}`;
    state.map.drawQueryResult(null);
  }
}

async function setupQuestions() {
  const questions = await loadOptional("/api/questions", (error) => { $("questions").textContent = `Frågorna kunde inte laddas: ${error.message}.`; });
  for (const question of questions || []) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = question.question;
    button.addEventListener("click", () => askQuestion(question.id));
    $("questions").append(button);
  }
  $("answer-clear").addEventListener("click", () => {
    state.map.drawQueryResult(null);
    $("answer").hidden = true;
  });
}

// The demo's start and stop (config.playback, from the saved profile) follow the scenario when
// mission control changes them, and the charts that span them are drawn again.
function followPlaybackWindow(scenarioState) {
  const playback = state.config.playback;
  if (!scenarioState.start_utc || (playback.start_utc === scenarioState.start_utc && playback.end_utc === scenarioState.end_utc)) return;
  playback.start_utc = scenarioState.start_utc;
  playback.end_utc = scenarioState.end_utc;
  state.rainShownAt = null;
  state.hydroShownAt = null;
}

// The threatened buildings on the map, from the clock as in the satellite monitor's log
// (satlog.js): only a threat that has just come in while the clock plays, as it is read aloud, large
// with its name for THREAT_HIGHLIGHT_MS; then it goes from the map and stays in the log.
function showThreats(scenarioState) {
  if (!state.threatData) return;
  state.threatState = scenarioState;
  const clockMs = Date.parse(scenarioState.clock_utc);
  const startMs = Date.parse(scenarioState.start_utc || state.config.playback.start_utc);
  const lines = satelliteLog({ events: scenarioState.events || [], ...state.threatData }, clockMs, clockMs - startMs + 1, Infinity,
    state.config.incident_place);
  const now = Date.now();
  const jumped = scenarioState.jump !== state.threatJump;
  state.threatJump = scenarioState.jump;
  ({ highlights: state.threatHighlights, seen: state.threatSeen } = threatHighlights(state.threatHighlights, state.threatSeen, lines, now,
    scenarioState.playing, jumped));
  // Drawn again when the next highlight ends, also while the clock stands still.
  clearTimeout(state.threatTimer);
  if (state.threatHighlights.size) {
    const ends = Math.min(...state.threatHighlights.values());
    state.threatTimer = setTimeout(() => showThreats(state.threatState), Math.max(0, ends - now) + 50);
  }
  const marks = threatMarks(lines, new Set(state.threatHighlights.keys()));
  const key = JSON.stringify(marks);
  if (key === state.threatKey) return;
  state.threatKey = key;
  state.map.drawThreats(marks);
  document.body.dataset.threats = marks.map((mark) => `${mark.latest ? "*" : ""}${mark.name}`).join("|");  // read by the tests
}

// The scenario's summary when it comes to its start (satlog.js summaryState), until PLAY, with a
// button that starts the scenario; the satellite monitor reads it aloud.
function showSummary(scenarioState) {
  const duration = summaryDuration(scenarioState);
  const lines = [...(state.config.summary || []), ...(duration ? [duration] : [])];
  const summary = summaryState(state.summarySince ?? null, scenarioState, Date.now());
  state.summarySince = summary.since;
  const element = $("scenario-summary");
  // Drawn again when it comes or its lines change (the playback's length follows the speed).
  if (summary.shown && lines.length && (element.hidden || element.dataset.lines !== lines.join("\n"))) {
    element.dataset.lines = lines.join("\n");
    element.innerHTML = "";
    const title = document.createElement("h2");
    title.textContent = `${state.config.title} – det här visas`;
    const list = document.createElement("ul");
    for (const line of lines) {
      const item = document.createElement("li");
      item.textContent = line;
      list.append(item);
    }
    // Starts the scenario as PLAY in mission control does; the card goes when the clock runs.
    const start = document.createElement("button");
    start.type = "button";
    start.className = "summary-start";
    start.textContent = "▶ STARTA SCENARIOT";
    start.addEventListener("click", () => runCommand("play"));
    element.append(title, list, start);
  }
  element.hidden = !(summary.shown && lines.length);
}

function applyState(scenarioState) {
  followPlaybackWindow(scenarioState);
  showSummary(scenarioState);
  showThreats(scenarioState);
  state.playing = scenarioState.playing;
  state.finished = scenarioState.finished;
  $("play").textContent = scenarioState.playing ? "Paus" : "Spela";
  showSpeed(scenarioState.speed);
  $("stream-status").textContent = scenarioState.finished
    ? "Uppspelningen är klar."
    : !scenarioState.playing ? "Pausad."
    : scenarioState.slowed ? "Saktar in: satellitpassage (1 minut/s) – alla skärmar följer samma klocka."
    : "Spelar upp – alla skärmar följer samma klocka.";
  document.body.dataset.slowed = String(Boolean(scenarioState.slowed && scenarioState.playing));
  // Read by tools/record_demo.py.
  document.body.dataset.playback = scenarioState.finished ? "finished" : scenarioState.playing ? "playing" : "paused";
  setClock(new Date(scenarioState.clock_utc));
  applyStatus(scenarioState.status);
  for (const event of state.pendingEvents.splice(0)) showBanner(eventBanner(event, scenarioState.status));
}

function connectScenario() {
  return new Promise((resolve) => {
    const source = new EventSource("/api/scenario/stream");
    source.addEventListener("sync", (event) => {
      const data = JSON.parse(event.data);
      state.map.clearHotspots();
      for (const feature of data.features) state.map.addHotspot(feature);
      applyState(data.state);
      resolve();
    });
    source.addEventListener("hotspot", (event) => {
      const feature = JSON.parse(event.data);
      state.map.addHotspot(feature);
      flashDetectionSatellite(feature);
    });
    source.addEventListener("scenario_event", (event) => {
      const scenarioEvent = JSON.parse(event.data);
      state.pendingEvents.push(scenarioEvent);
      if (scenarioEvent.kind !== "satcom_restore") $("satcom-sync").innerHTML = "";  // the SYNC list stays until the next event
    });
    source.addEventListener("satcom_queue", (event) => { $("satcom-queue").textContent = queueText(JSON.parse(event.data)); });
    source.addEventListener("satcom_sync", (event) => {
      const summary = JSON.parse(event.data);
      // The SYNC banner replaces the plain SATCOM RESTORED one.
      state.pendingEvents = state.pendingEvents.filter((item) => item.kind !== "satcom_restore");
      showBanner(syncBanner(summary));
      fillList("satcom-sync", syncLines(summary), "");
    });
    source.addEventListener("sensor", (event) => {
      const reading = JSON.parse(event.data);
      state.realSensors.set(`${reading.node}/${reading.kind}`, reading);
      showRealSensors();
    });
    source.addEventListener("sensor_health", (event) => {
      const health = JSON.parse(event.data);
      const reading = state.realSensors.get(`${health.node}/${health.kind}`);
      if (reading) reading.online = health.online;
      showRealSensors();
    });
    source.addEventListener("synthetic_sensors", (event) => showSynthetic(JSON.parse(event.data)));
    source.addEventListener("assessment", (event) => showAssessment(JSON.parse(event.data)));
    source.addEventListener("state", (event) => applyState(JSON.parse(event.data)));
    source.onerror = () => {
      // EventSource reconnects by itself and the backend then sends a new sync.
      $("stream-status").textContent = "Anslutningen till backend bröts – försöker igen …";
    };
  });
}

async function loadOptional(path, onError) {
  try {
    return await getJson(path);
  } catch (error) {
    onError(error);
    return null;
  }
}

// `createMap(config)` returns the map adapter: setup*/add*/draw*/show* methods used above.
// Right-click menu on the map: place a synthetic IoT sensor where the operator clicked.
// The sensor is a scenario command, so every screen shows it and RESET removes it.
const coordinate = new Intl.NumberFormat("sv-SE", { minimumFractionDigits: 4, maximumFractionDigits: 4 });

function setupMapMenu() {
  const menu = document.createElement("div");
  menu.id = "map-menu";
  menu.className = "map-menu";
  menu.setAttribute("role", "menu");
  menu.hidden = true;
  menu.innerHTML = '<div id="map-menu-place" class="map-menu-place"></div>'
    + '<button id="map-menu-sensor" type="button" role="menuitem">Placera IoT-sensor</button>';
  document.body.append(menu);
  let target = null;
  const close = () => { menu.hidden = true; target = null; };
  state.map.onContextMenu((click) => {
    target = click;
    $("map-menu-place").textContent = `${coordinate.format(click.latitude)} N, ${coordinate.format(click.longitude)} O`;
    menu.hidden = false;
    // Keep the menu inside the window.
    menu.style.left = `${Math.min(click.x, window.innerWidth - menu.offsetWidth - 8)}px`;
    menu.style.top = `${Math.min(click.y, window.innerHeight - menu.offsetHeight - 8)}px`;
    $("map-menu-sensor").focus();
  });
  $("map-menu-sensor").addEventListener("click", () => {
    if (target) runCommand("place_sensor", { latitude: target.latitude, longitude: target.longitude });
    close();
  });
  document.addEventListener("pointerdown", (event) => { if (!menu.contains(event.target)) close(); });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") close(); });
}

async function startApp(createMap) {
  // The main screen only shows: mission control has every button, list and tick (styles.css).
  // ?controls=1 keeps them here for troubleshooting.
  document.body.classList.toggle("display-only", !showControls());
  const config = await getJson("/api/config");
  state.config = config;
  $("title").textContent = config.title;
  document.title = `${config.title}${document.body.dataset.titleSuffix || ""}`;
  $("data-label").textContent = config.data_label;
  // Only the parts of the scenario's kind of incident are shown (styles.css).
  document.body.dataset.incident = config.incident;
  if ($("fly")) $("fly").textContent = `Flyg till ${config.incident_place}`;
  state.map = await createMap(config);
  setupMapMenu();
  const summary = await getJson("/api/hotspots");
  state.daily = summary.daily;

  const legend = $("terrain-legend");
  for (const [name, color] of Object.entries(TERRAIN_COLORS)) {
    const item = document.createElement("li");
    item.innerHTML = `<span class="swatch" style="background:${color}"></span>${name}`;
    legend.append(item);
  }
  const terrain = await loadOptional(config.layers.terrain, (error) => addNote(`Terränglagret kunde inte laddas: ${error.message}.`));
  if (terrain) state.map.addTerrain(terrain);
  if (state.map.wantsLabels()) {
    const labels = await loadOptional("/api/layers/labels", (error) => addNote(`Ortnamnen kunde inte laddas: ${error.message}.`));
    if (labels) state.map.addLabels(labels);
  }

  state.weather = await loadOptional("/api/weather", (error) => { $("weather-note").textContent = `Väderdata kunde inte laddas: ${error.message}.`; });
  const wildfire = config.incident === "wildfire";
  if (state.weather && !wildfire) setupRain(config);
  if (config.layers.radar) setupRadar(config);
  if (!wildfire && state.weather && config.layers.hydro) {  // only some flood scenarios have it
    state.hydro = await loadOptional("/api/hydro", () => {});
    if (state.hydro) setupHydro(config);
  }
  if (state.weather && wildfire) {
    const select = $("weather-station");
    for (const station of state.weather.stations) {
      select.append(new Option(`${station.name} (${station.distance_km} km)`, station.id));
    }
    state.map.addStations(state.weather.stations);
    state.weatherStation = state.weather.stations[0]?.id || null;
    select.addEventListener("change", () => {
      state.weatherStation = select.value;
      showWeather(state.clock);
    });
    state.map.addAttribution(config.attribution.smhi);
    $("weather-note").textContent = `Mätningar vid stationen, inte i ${config.incident_area}.`;
  }

  if (!wildfire) setupFloodMaps(config);
  if (!wildfire) setupDepthLegend();
  // The fire's wind field and spread forecast.
  state.wind = await loadOptional("/api/wind", (error) => { $("wind-note").textContent = `Vinddata kunde inte laddas: ${error.message}.`; });
  if (state.wind) {
    state.map.setupWind(state.wind, () => { state.windHour = null; showWind(state.clock); });
    state.map.addAttribution(config.attribution.era5_land);
  }

  if (wildfire) state.forecast = await loadOptional("/api/forecast", (error) => { $("forecast-places").textContent = `Prognosen kunde inte laddas: ${error.message}.`; });
  if (state.forecast) {
    $("forecast-label").textContent = state.forecast.label;
    if (config.layers.ems) {
      state.ems = await loadOptional("/api/ems", () => {});
      if (state.ems) setupEms(config);
    }
    for (const item of document.querySelectorAll(".forecast-station")) item.textContent = config.forecast_station;
    state.map.setupForecast();
    $("forecast-horizon").addEventListener("change", (event) => {
      state.forecastHorizon = event.target.value;
      drawForecast(state.clock);
    });
  }

  if (config.layers.met_forecast) setupMetForecast(config);
  if (config.layers.lightning) {
    state.map.setupLightning();
    state.map.addAttribution(config.layers.lightning.attribution);
    if (!$("forecast-caption")) {
      const caption = document.createElement("div");
      caption.id = "forecast-caption";
      caption.className = "forecast-caption";
      caption.hidden = true;
      $("map").append(caption);
    }
  }
  if (config.layers.meteosat_frm) setupMeteosatFrm(config.layers.meteosat_frm);
  if (config.layers.meteosat_cth) setupMeteosatCth(config.layers.meteosat_cth);
  if (config.layers.meteosat) {
    state.map.setupMeteosat(config.layers.meteosat.label);
    state.map.addAttribution(config.layers.meteosat.attribution);
  }
  if (config.layers.routes) await setupRoutes(config.layers.routes);
  if (config.layers.daily_rain) {
    state.map.setupDailyRain(config.layers.daily_rain);
    state.map.addAttribution(config.layers.daily_rain.attribution);
  }
  state.map.finish();
  setupScenarioView();
  // The flood's rain classes and maps right after the status, where the fire has its forecast; its
  // rain and flows are charts under the playback.
  if (!wildfire) $("scenario-status").closest("section").after($("rain-legend").closest("section"), $("flood-legend").closest("section"));
  await setupQuestions();
  await setupSatellites(config);
  await setupLandsat(config);
  state.iotConnection = await loadOptional("/api/sensors", (error) => { $("iot-connection").textContent = `IoT kunde inte laddas: ${error.message}.`; });
  showRealSensors();
  // The threats and the sensors' changes that decide them, once, as in the satellite monitor.
  state.threatData = {
    sensorEvents: (await loadOptional("/api/sensors/synthetic/events", () => {}))?.events || [],
    threats: (await loadOptional("/api/threats", () => {})) || {},
  };
  setClock(new Date(config.playback.start_utc));
  state.controlToken = new URLSearchParams(window.location.search).get("token");
  $("play").addEventListener("click", () => runCommand(state.playing ? "pause" : "play"));
  $("reset").addEventListener("click", () => runCommand("reset"));
  $("show-all").addEventListener("click", () => runCommand("seek", { at: config.playback.end_utc }));
  $("speed").addEventListener("change", (event) => runCommand("speed", { speed: Number(event.target.value) }));
  await connectScenario();
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
  return options;
}

function startWithErrors(createMap) {
  return startApp(createMap).catch((error) => {
    $("stream-status").textContent = `Fel vid start: ${error.message}`;
    throw error;
  });
}
