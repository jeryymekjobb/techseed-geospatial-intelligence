// Mission control of the monitoring (app/monitoring/service.py): the alarms with their confirm and
// dismiss buttons and briefing, the sources' status, the events in, the refused lines and what the
// rules left out; VISA 2D / VISA 3D, which switches the main screen between the 2D map and the 3D
// globe as in the scenarios; what was detected and the alarms of the last day; and BYT back to the
// start page. Reads /api/state every 30 s. Text from
// the sources is set as text, never as HTML.

const REFRESH_MS = 30000;
const localTime = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", day: "numeric", month: "short",
  hour: "2-digit", minute: "2-digit" });
const clockTime = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", day: "numeric", month: "short", year: "numeric",
  hour: "2-digit", minute: "2-digit", second: "2-digit" });
const DAY_MS = 86400000;
let waterLogPct = 0.5;
// The area's own maps and layers (/api/config): a layer the area lacks has no box to tick.
let areaConfig = null;
fetch("/api/config", { cache: "no-store" }).then((response) => response.json())
  .then((config) => { areaConfig = config; waterLogPct = config.area.s1_water_log_pct; showLayers(layersShown); }).catch(() => null);
const STATE_WORDS = { new: "Nytt", confirmed: "Bekräftat", dismissed: "Avfärdat" };
const SOURCE_WORDS = {
  mcf_border: "Kommungräns (MCF)", smhi_flow: "Vattenföring (SMHI)", smhi_flow_statistics: "Flödesstatistik (SMHI)",
  smhi_rain: "Nederbörd (SMHI)", smhi_warnings: "Varningar (SMHI)", krisinformation: "VMA och nyheter (Krisinformation)",
  smhi_radar: "Väderradar (SMHI)", smhi_grid: "Vind och väderkarta (SMHI)", smhi_stations: "Väderstationer (SMHI)",
  sentinel2: "Satellitbild (Sentinel-2)", landsat: "Satellitbild (Landsat)", sentinel1: "Radarbild (Sentinel-1)", gis: "Skyddsvärda objekt (GIS, OSM)", smhi_fire_risk: "Brandrisk (SMHI)", smhi_forecast: "Väderprognos (SMHI)",
  meteosat_clm: "Moln (Meteosat)", mcf_fire_ban: "Eldningsförbud (MCF)", firms: "Brandpunkter (NASA FIRMS)", inbox: "Händelser in (inkorgen)",
};

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (className) node.className = className;
  return node;
}


async function act(alarmId, action, note) {
  const response = await fetch(`/api/alarms/${encodeURIComponent(alarmId)}/${action}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ note }),
  });
  if (!response.ok) alert(`Åtgärden misslyckades (${response.status})`);
  await refresh();
}

function drawAlarms(state) {
  const box = document.getElementById("alarms");
  box.replaceChildren();
  if (!state.alarms.length) box.append(element("p", "Inga larm.", "status"));
  for (const alarm of state.alarms) {
    const c = alarm.candidate;
    const card = element("div", null, `alarm ${alarm.state}`);
    card.append(element("div", c.title, "head"));
    const tags = element("div", null, "tags");
    tags.append(element("span", STATE_WORDS[alarm.state]), element("span", c.kind_word));
    if (!alarm.current) tags.append(element("span", "inte längre aktuellt"));
    if (c.single_source) tags.append(element("span", "en källa"));
    if (c.simulated) tags.append(element("span", "SIMULERAD", "sim"));
    card.append(tags);
    const facts = element("ul");
    for (const fact of c.facts.slice(0, 4)) {
      facts.append(element("li", `${fact.text}${fact.uncertain ? " (osäkert)" : ""} – ${fact.source}${fact.time_utc ? `, ${fact.time_utc}` : ""}`));
    }
    for (const confirmation of c.confirmations) facts.append(element("li", `Bekräftelse: ${confirmation}`));
    if (c.exposure) {
      const names = c.exposure.facilities.slice(0, 4).map((item) => item.name).join(", ");
      facts.append(element("li", `${c.exposure.where}: ${c.exposure.facilities.length} skyddsvärda objekt`
        + `${names ? ` (${names}${c.exposure.facilities.length > 4 ? " …" : ""})` : ""}, ${c.exposure.buildings} byggnader`
        + `${c.exposure.railways.length ? ", järnväg" : ""} – kommunens GIS och OSM`));
    }
    for (const note of c.notes) facts.append(element("li", note));
    card.append(facts);
    const actions = element("div", null, "actions");
    const note = element("input");
    note.placeholder = "Anteckning";
    note.maxLength = 500;
    const confirm = element("button", "Bekräfta");
    confirm.onclick = () => act(alarm.id, "confirm", note.value);
    const dismiss = element("button", "Avfärda");
    dismiss.onclick = () => act(alarm.id, "dismiss", note.value);
    const link = element("a", "Briefing");
    link.href = `/briefing/${encodeURIComponent(alarm.id)}`;
    link.target = "_blank";
    actions.append(note, confirm, dismiss, link);
    card.append(actions);
    box.append(card);
  }
}

// Läget nu: the radar, the fire risk and the forecast, as the scenarios' Läge.
function drawSituation(state) {
  const context = state.context || {};
  const lines = [];
  const radar = context.radar;
  lines.push(radar?.frames ? `Väderradar ${localTime.format(new Date(radar.latest_utc))}: som mest ${radar.max_mm_h} mm/h i kommunen, `
    + `${radar.hour_mm} mm senaste timmen (uppskattat)` : "Väderradar: ingen bild än");
  const today = new Date().toISOString().slice(0, 10);
  const risk = (context.fire_risk || []).find((day) => day.day_utc === today);
  if (risk) lines.push(`Brandrisk i dag: ${risk.fwi_word || "utanför brandsäsongen"}${risk.grass_word ? `, gräsbrand ${risk.grass_word}` : ""}`);
  for (const item of context.forecast || []) {
    lines.push(`Prognos: ${item.rain_24h_mm} mm regn närmaste dygnet, ${item.rain_48h_mm} mm två dygn, ${item.temp_min}–${item.temp_max} °C`);
  }
  const wind = context.weather?.centre_wind;
  if (wind) {
    lines.push(`Vind ${localTime.format(new Date(context.weather.valid_utc))}: ${wind.speed_ms} m/s från ${wind.from_deg}° (prognos, SMHI)`);
  }
  for (const flow of context.flows || []) lines.push(`${flow.name}: ${flow.value} m³/s`);
  const list = document.getElementById("situation");
  list.replaceChildren(...lines.map((text) => element("li", text, "info")));
}

// What was detected and the alarms, newest first, moved here from the satellite monitor as the user
// asked: FIRMS's detections, Sentinel-1's water outside the lakes from waterLogPct % of the land where
// water and land can be told apart, and every alarm with its station and value, of the last day.
function drawDetections(state) {
  const nowMs = Date.now();
  const lines = [];
  const radar = state.context?.radar_pass;
  if (radar && radar.separable && radar.new_water_pct >= waterLogPct) {
    lines.push({ atMs: Date.parse(radar.time_utc), kind: "computed",
      text: `${radar.platform}: vatten utanför sjöarna på ${String(radar.new_water_pct).replace(".", ",")} % av marken (beräknat)` });
  }
  for (const fire of state.context?.firms || []) {
    lines.push({ atMs: Date.parse(fire.time_utc), kind: "firms",
      text: `NASA FIRMS: värmedetektion ${fire.instrument} (${fire.satellite}) vid ${fire.latitude.toFixed(3)} N, ${fire.longitude.toFixed(3)} E` });
  }
  for (const alarm of state.alarms) {
    lines.push({ atMs: Date.parse(alarm.created_utc), kind: alarm.candidate.simulated ? "simulated" : "synthetic",
      text: `LARM: ${alarm.candidate.title}${alarm.candidate.facts[0] ? ` – ${alarm.candidate.facts[0].text}` : ""}`
        + `${alarm.candidate.simulated ? " (simulerad)" : ""}` });
  }
  const shown = lines.filter((line) => line.atMs >= nowMs - DAY_MS && line.atMs <= nowMs).sort((a, b) => b.atMs - a.atMs);
  const list = document.getElementById("detections");
  list.replaceChildren(...shown.map((line, index) => {
    const row = element("li", undefined, `${line.kind}${index === 0 ? " latest" : ""}`);
    row.append(element("time", localTime.format(new Date(line.atMs))), ` ${line.text}`);
    return row;
  }));
  if (!list.children.length) list.append(element("li", "Inget upptäckt och inga larm det senaste dygnet."));
}

// The log, as the scenarios' mission control's: every alarm, confirmation and dismissal with its time.
function drawLog(state) {
  const entries = state.alarms.flatMap((alarm) => alarm.history.map((item) => ({ ...item, title: alarm.candidate.title,
    value: alarm.candidate.facts[0]?.text })));
  entries.sort((a, b) => b.time_utc.localeCompare(a.time_utc));
  const list = document.getElementById("event-log");
  list.replaceChildren(...entries.slice(0, 60).map((item) => element("li",
    `${localTime.format(new Date(item.time_utc))} ${item.action.toUpperCase()}: ${item.title}`
      + `${item.action === "larm" && item.value ? ` – ${item.value}` : ""}${item.note && item.action !== "larm" ? ` – ${item.note}` : ""}`,
    item.action === "larm" ? "alert" : "info")));
  if (!list.children.length) list.append(element("li", "Inga larm än.", "ok"));
}

function drawSources(state) {
  const table = document.getElementById("sources");
  table.replaceChildren();
  for (const source of state.sources) {
    const row = element("tr");
    row.append(element("td", SOURCE_WORDS[source.source] || source.source),
      element("td", source.ok ? "ok" : "FEL", source.ok ? "" : "bad"),
      element("td", source.count), element("td", source.error || source.note || ""));
    table.append(row);
  }
}

function drawList(id, items, text) {
  const box = document.getElementById(id);
  box.replaceChildren();
  box.className = "list";
  if (!items.length) box.append(element("div", "Inga.", "meta"));
  for (const item of items.slice().reverse()) box.append(element("div", text(item)));
}

async function refresh() {
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    const state = await response.json();
    document.getElementById("control-label").textContent = `Övervakning: ${state.area.name} – live`;
    document.title = `TechSeed Mission Control – ${state.area.name}`;
    showView(state.view);
    showLayers(state.layers);
    showSpeech(state.speech);
    showSettings(state.settings);
    drawCharts(state);
    drawSatelliteImage(state);
    drawIot(state);
    drawDetections(state);
    drawLog(state);
    document.getElementById("polled").textContent = state.polled_utc
      ? `Senaste avläsning ${localTime.format(new Date(state.polled_utc))}, var ${state.area.poll_seconds / 60}:e minut` : "Ingen avläsning än";
    drawAlarms(state);
    drawSituation(state);
    drawSources(state);
    drawList("events", state.events, (e) => `${e.time_utc} ${e.kind_word} – ${e.source}${e.simulated ? " (simulerad)" : ""} [${e.origin}]`);
    drawList("refused", state.refused, (r) => `${r.logged_utc} ${r.origin}: ${r.reason} – ${r.line}`);
    drawList("filtered", state.filtered, (f) => `${f.what}: ${f.reason}`);
  } catch (error) {
    document.getElementById("polled").textContent = `Tjänsten svarar inte: ${error}`;
  }
}

document.getElementById("switch-demo").addEventListener("click", async () => {
  if (!window.confirm("Avsluta övervakningen på skärmarna och visa startsidan här i mission control?")) return;
  const status = document.getElementById("command-status");
  const response = await fetch("/api/demo/menu", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })
    .catch(() => null);
  status.textContent = response?.ok ? "Övervakningen avslutas – startsidan visas strax här."
    : response?.status === 409 ? "BYT fungerar bara när övervakningen är startad från startsidan." : "Tjänsten svarar inte.";
});

// The map layers on the main screen, ticked here as in the scenarios' mission control (/api/layers).
const LAYER_LABELS = {
  municipal: "Kommunens karta", flood: "Översvämning, 100-årsflöde (MCF)", radar: "Väderradar (SMHI)",
  wind: "Vindpilar (SMHI, prognos)", chart: "Väderkarta (SMHI, prognos)", stations: "SMHI:s stationer",
  facilities: "Skyddsvärda objekt (kommunens GIS)", names: "Ortnamn (OSM)", firms: "Brandpunkter (NASA FIRMS)",
  satellite: "Satellitbild (Sentinel-2)", s1radar: "Radarbild (Sentinel-1)", s1water: "Vatten utanför sjöarna, radar (rött)",
  s1wetness: "Fukt i terrängen, radar (brun torr – blå blöt)", landsat: "Satellitbild (Landsat)",
  flood_highest: "Översvämning, beräknat högsta flöde (MCF)",
  skyfall30: "Skyfall, vattendjup vid 30-årsregn (kommunen)", skyfall100: "Skyfall, vattendjup vid 100-årsregn (kommunen)", skyfall500: "Skyfall, vattendjup vid 500-årsregn (kommunen)",
};
let layersShown = {};
// The labels of the area's own layers, and whether the area has them (areaConfig; all until it comes).
function areaLayers() {
  if (!areaConfig) return { labels: {}, has: () => true };
  const overlays = Object.fromEntries((areaConfig.layers.overlays || []).map((item) => [item.id, item]));
  const labels = { municipal: `Kommunens karta (${areaConfig.area.name})` };
  for (const name of ["flood", "flood_highest"]) if (areaConfig.layers[name]) labels[name] = `Översvämning, ${areaConfig.layers[name].label}`;
  for (const [id, item] of Object.entries(overlays)) labels[id] = item.label;
  const has = (name) => (name === "municipal" ? areaConfig.maps.municipal.length > 0
    : name === "flood" || name === "flood_highest" ? Boolean(areaConfig.layers[name])
      : name.startsWith("skyfall") ? Boolean(overlays[name]) : true);
  return { labels, has };
}
function showLayers(layers) {
  layersShown = { ...(layers || {}) };
  const box = document.getElementById("map-layers");
  const own = areaLayers();
  for (const [name, fallback] of Object.entries(LAYER_LABELS)) {
    const label = own.labels[name] || fallback;
    let input = box.querySelector(`input[value="${name}"]`);
    if (!input) {
      const row = element("label");
      input = element("input");
      input.type = "checkbox";
      input.value = name;
      input.addEventListener("change", () => postLayers({ [name]: input.checked }));
      row.append(input, element("span", label));
      box.append(row);
    }
    input.checked = Boolean(layersShown[name]);
    input.closest("label").hidden = !own.has(name);
    input.nextElementSibling.textContent = label;
  }
  document.getElementById("simulated-toggle").checked = Boolean(layersShown.simulated);
}

async function postLayers(changes) {
  const response = await fetch("/api/layers", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changes) }).catch(() => null);
  if (response?.ok) showLayers((await response.json()).layers);
  else document.getElementById("command-status").textContent = "Växlingen gick inte – tjänsten svarar inte.";
  refresh();
}
// One switch for every simulated sensor (the service's layer "simulated").
document.getElementById("simulated-toggle").addEventListener("change", (event) => postLayers({ simulated: event.target.checked }));

// SPARA INSTÄLLNINGAR, as the scenarios' SPARA PROFIL: red while the settings differ from those the
// monitoring starts with; the line under it says which apply.
function showSettings(settings) {
  if (!settings) return;
  document.getElementById("save-settings").classList.toggle("unsaved", Boolean(settings.unsaved));
  document.getElementById("settings-status").textContent = (settings.saved_utc
    ? `Övervakningen startar med inställningarna sparade ${localTime.format(new Date(settings.saved_utc))}.`
    : "Inga sparade inställningar – övervakningen startar med standardvalen.")
    + (settings.unsaved ? " Valen nu skiljer sig från dem; spara för att starta med dem." : "");
}
document.getElementById("save-settings").addEventListener("click", async () => {
  const response = await fetch("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })
    .catch(() => null);
  if (response?.ok) showSettings(await response.json());
  else document.getElementById("settings-status").textContent = "Inställningarna sparades inte – tjänsten svarar inte.";
});

// UPPLÄSNING: new alarms read aloud by the service with the scenarios' voice alma.
let speech = false;
function showSpeech(value) {
  speech = Boolean(value);
  const button = document.getElementById("speech-toggle");
  button.textContent = speech ? "UPPLÄSNING PÅ" : "UPPLÄSNING AV";
  button.setAttribute("aria-pressed", String(speech));
}
document.getElementById("speech-toggle").addEventListener("click", async () => {
  const response = await fetch("/api/speech", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ speech: !speech }) }).catch(() => null);
  if (response?.ok) showSpeech((await response.json()).speech);
});

// The charts of the latest day, as the scenarios' time charts: each station's flow with the limit
// for a high flow and the record, the rain by the hour at the rain stations, the radar's highest
// rate in the municipality in the last hour.
const hourText = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", hour: "2-digit", minute: "2-digit" });
function drawChart(canvas, points, { kind = "line", lines = [], unit = "" } = {}) {
  const width = canvas.clientWidth || 300;
  const height = canvas.clientHeight || 90;
  canvas.width = width * devicePixelRatio;
  canvas.height = height * devicePixelRatio;
  const g = canvas.getContext("2d");
  g.scale(devicePixelRatio, devicePixelRatio);
  g.clearRect(0, 0, width, height);
  if (!points.length) {
    g.fillStyle = "#888";
    g.fillText("Inga värden", 8, height / 2);
    return;
  }
  const left = 40;
  const bottom = height - 16;
  const times = points.map((point) => Date.parse(point.time));
  const t0 = Math.min(...times);
  const t1 = Math.max(...times, t0 + 1);
  const top = Math.max(...points.map((point) => point.value), ...lines.map((line) => line.value), 0.1) * 1.1;
  const x = (t) => left + (t - t0) / (t1 - t0) * (width - left - 6);
  const y = (v) => bottom - v / top * (bottom - 6);
  g.font = "11px system-ui, sans-serif";
  g.fillStyle = "#b8b8b8";
  g.fillText(`${Math.round(top * 10) / 10} ${unit}`, 2, 12);
  g.fillText("0", 2, bottom);
  g.fillText(hourText.format(new Date(t0)), left, height - 3);
  g.fillText(hourText.format(new Date(t1)), width - 40, height - 3);
  for (const line of lines) {
    if (line.value > top) continue;
    g.strokeStyle = line.colour;
    g.setLineDash([4, 3]);
    g.beginPath();
    g.moveTo(left, y(line.value));
    g.lineTo(width - 6, y(line.value));
    g.stroke();
    g.setLineDash([]);
    g.fillStyle = line.colour;
    g.fillText(line.label, left + 4, y(line.value) - 2);
  }
  g.fillStyle = "#4fc3f7";
  g.strokeStyle = "#4fc3f7";
  if (kind === "bars") {
    const bar = Math.max(2, (width - left) / Math.max(points.length, 1) - 2);
    for (const point of points) g.fillRect(x(Date.parse(point.time)) - bar / 2, y(point.value), bar, bottom - y(point.value));
  } else {
    g.lineWidth = 2;
    g.beginPath();
    points.forEach((point, index) => {
      const px = x(Date.parse(point.time));
      const py = y(point.value);
      if (index) g.lineTo(px, py); else g.moveTo(px, py);
    });
    g.stroke();
  }
}

function chartBox(key, title) {
  const box = document.getElementById("charts");
  let chart = box.querySelector(`[data-chart="${key}"]`);
  if (!chart) {
    chart = element("div", null, "chart");
    chart.dataset.chart = key;
    chart.append(element("h3"), element("canvas"));
    box.append(chart);
  }
  chart.querySelector("h3").textContent = title;
  return chart.querySelector("canvas");
}

function drawCharts(state) {
  const context = state.context || {};
  for (const flow of context.flows || []) {
    const limits = flow.limits ? [{ value: flow.limits.high, label: "högt flöde", colour: "#ffb300" },
      { value: flow.limits.record, label: "rekord", colour: "#ef5350" }] : [];
    drawChart(chartBox(`flow-${flow.station}`, `Vattenföring ${flow.name} (m³/s, senaste dygnet) – SMHI`),
      (flow.series || []).map((point) => ({ time: point.time_utc, value: point.value })), { lines: limits, unit: "m³/s" });
  }
  for (const station of context.rain || []) {
    drawChart(chartBox(`rain-${station.station}`, `Regn ${station.name} (mm per timme, senaste dygnet) – SMHI`),
      (station.series || []).map((point) => ({ time: point.time_utc, value: point.mm })), { kind: "bars", unit: "mm" });
  }
  const radar = context.radar;
  drawChart(chartBox("radar", "Väderradar, högsta intensitet i kommunen (mm/h, senaste timmen) – SMHI, uppskattat"),
    (radar?.series || []).map((point) => ({ time: point.time_utc, value: point.max_mm_h })),
    { kind: "bars", unit: "mm/h", lines: [{ value: 20, label: "skyfall", colour: "#ef5350" }] });
  const clouds = context.cloud_mask;
  if (clouds) {
    drawChart(chartBox("clouds", "Moln över kommunen (% av pixlarna, senaste dygnet) – Meteosat, några km per pixel"),
      (clouds.series || []).map((point) => ({ time: point.time_utc, value: point.cloud_pct })), { unit: "%" });
  }
}

function drawSatelliteImage(state) {
  const meta = state.context?.satellite_image;
  const radar = state.context?.radar_pass;
  const landsat = state.context?.landsat_image;
  const optical = (image) => `${image.platform} ${localTime.format(new Date(image.time_utc))}, ${image.cloud} % moln`
    + `${image.recent ? "" : " – ingen klarare bild de senaste två veckorna"}`;
  document.getElementById("satellite-image").textContent = (!meta ? "Optiskt: ingen bild än." : `Optiskt: ${optical(meta)}`)
    + (landsat ? `; ${optical(landsat)}.` : ".")
    + (!radar ? " Radar: ingen passage än." : ` Radar: ${radar.platform} ${localTime.format(new Date(radar.time_utc))}, `
      + `vatten utanför sjöarna ${String(radar.new_water_pct).replace(".", ",")} % av marken (tröskel ${String(radar.threshold_db).replace(".", ",")} dB`
      + `${radar.separable ? "" : ", vatten och mark går inte att skilja åt – osäker"}). Beräknat, inte en kartlagd översvämning.`
      + (radar.wetness_median_pct != null ? ` Fukt i terrängen: i median ${radar.wetness_median_pct} % mellan torrast och blötast `
        + `de senaste ${radar.wetness_passes} passagerna från samma bana – beräknat, inte uppmätt.` : ""))
    + ` ${(meta || radar)?.attribution || ""}${landsat ? ` ${landsat.attribution}.` : ""}`
    + cloudText(state.context?.cloud_mask);
}

// Meteosat's cloud mask (meteosat.py): why the optical image may be old or missing.
function cloudText(clouds) {
  if (!clouds) return "";
  return ` Moln just nu: ${clouds.cloud_pct ?? "–"} % av kommunen enligt ${clouds.satellite} `
    + `${localTime.format(new Date(clouds.time_utc))} (molnmask, några km per pixel). ${clouds.attribution}.`;
}

function drawIot(state) {
  const iot = state.iot || {};
  document.getElementById("iot-connection").textContent = `${iot.detail || "IoT är inte startat."}`
    + `${iot.rejected ? ` ${iot.rejected} meddelanden avvisade.` : ""}`;
  const list = document.getElementById("iot-sensors");
  // Without the simulated sensors, only the nodes that said they are real.
  const simulated = Boolean(state.layers?.simulated);
  const hidden = (iot.sensors || []).filter((sensor) => !sensor.real).length + (state.context?.level_sensors || []).length;
  list.replaceChildren(...(iot.sensors || []).filter((sensor) => simulated || sensor.real).map((sensor) => element("li",
    `${sensor.node} ${sensor.kind}: ${sensor.value}${sensor.unit ? ` ${sensor.unit}` : ""}`
      + `${sensor.real ? "" : " (simulerad)"}${sensor.online ? "" : " – har tystnat"}`, sensor.online ? "info" : "alert")));
  // The scenarios' simulated level sensors (levels.py), driven by SMHI's flows.
  for (const sensor of simulated ? state.context?.level_sensors || [] : []) {
    const value = sensor.value == null ? `inga värden från ${sensor.station_name} ännu`
      : `${sensor.station_name} ${sensor.percent ?? "–"} % av högsta dygnsflöde i arkivet`;
    list.append(element("li", `${sensor.name}: ${sensor.alarm ? "LARMAR" : "inget larm"}, ${value} (simulerad nivågivare)`,
      sensor.alarm ? "alert" : "info"));
  }
  if (!simulated && hidden) list.append(element("li", `${hidden} simulerade sensorer är dolda.`, "info"));
  if (!list.children.length) list.append(element("li", "Inga sensorer har hörts av.", "ok"));
}

// VISA 2D / VISA 3D: the main screen's map; the button names the other one.
let view = "3d";
function showView(value) {
  view = value || "3d";
  document.getElementById("view-toggle").textContent = view === "2d" ? "VISA 3D" : "VISA 2D";
}
document.getElementById("view-toggle").addEventListener("click", async () => {
  const wanted = view === "2d" ? "3d" : "2d";
  const response = await fetch("/api/view", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ view: wanted }) }).catch(() => null);
  if (response?.ok) showView((await response.json()).view);
  else document.getElementById("command-status").textContent = "Växlingen gick inte – tjänsten svarar inte.";
});

// The live clock in Swedish time, where the scenarios show the scenario clock.
const tick = () => { document.getElementById("live-time").textContent = `${clockTime.format(new Date())} – svensk tid, live`; };
tick();
setInterval(tick, 1000);
refresh();
setInterval(refresh, REFRESH_MS);
