// Mission control of the monitoring (app/monitoring/service.py): the alarms with their confirm and
// dismiss buttons and briefing, the sources' status, the events in, the refused lines and what the
// rules left out; VISA 2D / VISA 3D, which switches the main screen between the 2D map and the 3D
// globe as in the scenarios; and BYT back to the start page. Reads /api/state every 30 s. Text from
// the sources is set as text, never as HTML.

const REFRESH_MS = 30000;
const localTime = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", day: "numeric", month: "short",
  hour: "2-digit", minute: "2-digit" });
const clockTime = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", day: "numeric", month: "short", year: "numeric",
  hour: "2-digit", minute: "2-digit", second: "2-digit" });
const STATE_WORDS = { new: "Nytt", confirmed: "Bekräftat", dismissed: "Avfärdat" };
const SOURCE_WORDS = {
  mcf_border: "Kommungräns (MCF)", smhi_flow: "Vattenföring (SMHI)", smhi_flow_statistics: "Flödesstatistik (SMHI)",
  smhi_rain: "Nederbörd (SMHI)", smhi_warnings: "Varningar (SMHI)", krisinformation: "VMA och nyheter (Krisinformation)",
  smhi_radar: "Väderradar (SMHI)", smhi_grid: "Vind och väderkarta (SMHI)", smhi_stations: "Väderstationer (SMHI)",
  sentinel2: "Satellitbild (Sentinel-2)", sentinel1: "Radarbild (Sentinel-1)", flen_gis: "Skyddsvärda objekt (kommunens GIS)", smhi_fire_risk: "Brandrisk (SMHI)", smhi_forecast: "Väderprognos (SMHI)",
  mcf_fire_ban: "Eldningsförbud (MCF)", firms: "Brandpunkter (NASA FIRMS)", inbox: "Händelser in (inkorgen)",
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
    drawCharts(state);
    drawSatelliteImage(state);
    drawIot(state);
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
  municipal: "Kommunens karta (Flens kommun)", flood: "Översvämning, 100-årsflöde (MCF)", radar: "Väderradar (SMHI)",
  wind: "Vindpilar (SMHI, prognos)", chart: "Väderkarta (SMHI, prognos)", stations: "SMHI:s stationer",
  facilities: "Skyddsvärda objekt (kommunens GIS)", names: "Ortnamn (OSM)", firms: "Brandpunkter (NASA FIRMS)",
  satellite: "Satellitbild (Sentinel-2)", s1radar: "Radarbild (Sentinel-1)", s1water: "Vatten utanför sjöarna, radar (rött)",
};
let layersShown = {};
function showLayers(layers) {
  layersShown = { ...(layers || {}) };
  const box = document.getElementById("map-layers");
  for (const [name, label] of Object.entries(LAYER_LABELS)) {
    let input = box.querySelector(`input[value="${name}"]`);
    if (!input) {
      const row = element("label");
      input = element("input");
      input.type = "checkbox";
      input.value = name;
      input.addEventListener("change", async () => {
        const response = await fetch("/api/layers", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ [name]: input.checked }) }).catch(() => null);
        if (response?.ok) showLayers((await response.json()).layers);
        else document.getElementById("command-status").textContent = "Växlingen gick inte – tjänsten svarar inte.";
      });
      row.append(input, element("span", label));
      box.append(row);
    }
    input.checked = Boolean(layersShown[name]);
  }
}

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
}

function drawSatelliteImage(state) {
  const meta = state.context?.satellite_image;
  const radar = state.context?.radar_pass;
  document.getElementById("satellite-image").textContent = (!meta ? "Optiskt: ingen bild än."
    : `Optiskt: ${meta.platform} ${localTime.format(new Date(meta.time_utc))}, ${meta.cloud} % moln`
      + `${meta.recent ? "" : " – ingen klarare bild de senaste två veckorna"}.`)
    + (!radar ? " Radar: ingen passage än." : ` Radar: ${radar.platform} ${localTime.format(new Date(radar.time_utc))}, `
      + `vatten utanför sjöarna ${String(radar.new_water_pct).replace(".", ",")} % av marken (tröskel ${String(radar.threshold_db).replace(".", ",")} dB`
      + `${radar.separable ? "" : ", vatten och mark går inte att skilja åt – osäker"}). Beräknat, inte en kartlagd översvämning.`)
    + ` ${(meta || radar)?.attribution || ""}`;
}

function drawIot(state) {
  const iot = state.iot || {};
  document.getElementById("iot-connection").textContent = `${iot.detail || "IoT är inte startat."}`
    + `${iot.rejected ? ` ${iot.rejected} meddelanden avvisade.` : ""}`;
  const list = document.getElementById("iot-sensors");
  list.replaceChildren(...(iot.sensors || []).map((sensor) => element("li",
    `${sensor.node} ${sensor.kind}: ${sensor.value}${sensor.unit ? ` ${sensor.unit}` : ""}`
      + `${sensor.real ? "" : " (simulerad)"}${sensor.online ? "" : " – har tystnat"}`, sensor.online ? "info" : "alert")));
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
