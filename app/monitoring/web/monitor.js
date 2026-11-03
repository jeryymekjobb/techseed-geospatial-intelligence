// The operator page of the monitoring (app/monitoring/service.py): the map, the alarms with their
// confirm and dismiss buttons, the sources' status, the events in, the refused lines and what the
// rules left out. Reads /api/state every 30 s. Text from the sources is set as text, never as HTML.

const REFRESH_MS = 30000;
const STATE_WORDS = { new: "Nytt", confirmed: "Bekräftat", dismissed: "Avfärdat" };
const SOURCE_WORDS = {
  mcf_border: "Kommungräns (MCF)", smhi_flow: "Vattenföring (SMHI)", smhi_flow_statistics: "Flödesstatistik (SMHI)",
  smhi_rain: "Nederbörd (SMHI)", smhi_warnings: "Varningar (SMHI)", krisinformation: "VMA och nyheter (Krisinformation)",
  mcf_fire_ban: "Eldningsförbud (MCF)", firms: "Brandpunkter (NASA FIRMS)", inbox: "Händelser in (inkorgen)",
};

const map = L.map("map");
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 18,
  attribution: "© OpenStreetMap contributors – reserv, kommunens GIS används inte än",
}).addTo(map);
const layers = { border: L.layerGroup().addTo(map), sites: L.layerGroup().addTo(map), alarms: L.layerGroup().addTo(map) };
let placed = false;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (className) node.className = className;
  return node;
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
    L.circleMarker([flow.latitude, flow.longitude], { radius: 6, color: "#0277bd" })
      .bindTooltip(`${flow.name}: ${flow.value} m³/s ${flow.time_utc}${limits} – SMHI`).addTo(layers.sites);
  }
  for (const rain of context.rain || []) {
    if (rain.latitude == null) continue;
    L.circleMarker([rain.latitude, rain.longitude], { radius: 5, color: "#2e7d32" })
      .bindTooltip(`${rain.name}: ${rain.mm_24h} mm senaste 24 h – SMHI`).addTo(layers.sites);
  }
  for (const point of context.firms || []) {
    L.circleMarker([point.latitude, point.longitude], { radius: 4, color: "#e65100" })
      .bindTooltip(`FIRMS ${point.instrument} ${point.satellite} ${point.time_utc}`).addTo(layers.sites);
  }
  for (const event of state.events || []) {
    L.circleMarker([event.latitude, event.longitude], { radius: 5, color: event.simulated ? "#b8860b" : "#6a1b9a" })
      .bindTooltip(`${event.kind_word} ${event.time_utc} – ${event.source}${event.simulated ? " (simulerad)" : ""}`)
      .addTo(layers.sites);
  }
  layers.alarms.clearLayers();
  for (const alarm of state.alarms) {
    const c = alarm.candidate;
    if (c.latitude == null || !alarm.current) continue;
    L.circleMarker([c.latitude, c.longitude], { radius: 11, color: alarm.state === "new" ? "#c62828" : "#1565c0", weight: 3 })
      .bindTooltip(c.title).addTo(layers.alarms);
  }
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
  if (!state.alarms.length) box.append(element("p", "Inga larm.", "meta"));
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
    document.getElementById("title").textContent = `Övervakning – ${state.area.name}`;
    document.title = `Övervakning – ${state.area.name}`;
    document.getElementById("polled").textContent = state.polled_utc
      ? `Senaste avläsning ${state.polled_utc} (UTC), var ${state.area.poll_seconds / 60} min` : "Ingen avläsning än";
    drawMap(state);
    drawAlarms(state);
    drawSources(state);
    drawList("events", state.events, (e) => `${e.time_utc} ${e.kind_word} – ${e.source}${e.simulated ? " (simulerad)" : ""} [${e.origin}]`);
    drawList("refused", state.refused, (r) => `${r.logged_utc} ${r.origin}: ${r.reason} – ${r.line}`);
    drawList("filtered", state.filtered, (f) => `${f.what}: ${f.reason}`);
  } catch (error) {
    document.getElementById("polled").textContent = `Tjänsten svarar inte: ${error}`;
  }
}

refresh();
setInterval(refresh, REFRESH_MS);
