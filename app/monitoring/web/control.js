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
  smhi_radar: "Väderradar (SMHI)", smhi_grid: "Vind och väderkarta (SMHI)", smhi_fire_risk: "Brandrisk (SMHI)", smhi_forecast: "Väderprognos (SMHI)",
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

// VINDPILAR and VÄDERKARTA: SMHI's wind arrows and weather chart on the main screen, on or off.
const LAYER_WORDS = { wind: "VINDPILAR", chart: "VÄDERKARTA" };
let layersShown = { wind: true, chart: false };
function showLayers(layers) {
  layersShown = { ...layersShown, ...(layers || {}) };
  for (const [name, word] of Object.entries(LAYER_WORDS)) {
    const button = document.getElementById(`${name}-toggle`);
    button.textContent = `${word} ${layersShown[name] ? "PÅ" : "AV"}`;
    button.setAttribute("aria-pressed", String(Boolean(layersShown[name])));
  }
}
for (const name of Object.keys(LAYER_WORDS)) {
  document.getElementById(`${name}-toggle`).addEventListener("click", async () => {
    const response = await fetch("/api/layers", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [name]: !layersShown[name] }) }).catch(() => null);
    if (response?.ok) showLayers((await response.json()).layers);
    else document.getElementById("command-status").textContent = "Växlingen gick inte – tjänsten svarar inte.";
  });
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
