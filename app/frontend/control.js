// Mission control: a touch screen next to the main screen. It sends commands to the
// shared scenario (POST /api/scenario/command) and follows it like every other
// screen (/api/scenario/stream). ?token=<SCENARIO_CONTROL_TOKEN> when the backend
// requires one.
"use strict";

const $ = (id) => document.getElementById(id);
const token = new URLSearchParams(window.location.search).get("token");
const localTime = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", dateStyle: "medium", timeStyle: "short" });
const localDate = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", dateStyle: "medium" });
const shortTime = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
let status = null;
let place = "branden";  // the incident's place, from /api/config
let config = null;
let latestImage = "swir";  // the image "auto" shows: SWIR in the fire, radar in the flood (as panel.js)
let imageList = "";  // the values in the image list, to rebuild it only when they change
let clockShown = null;  // the scenario clock last shown, for when /api/config arrives after it
const realSensors = new Map();
let iotConnection = null;

async function send(name, target, speed) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["X-Control-Token"] = token;
  const body = { command: name };
  if (target) body.target = target;
  if (speed) body.speed = Number(speed);
  const response = await fetch("/api/scenario/command", { method: "POST", headers, body: JSON.stringify(body) });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error === "control_token_required" ? "fel eller saknad token (?token=)" : error.detail || error.error || `HTTP ${response.status}`);
  }
  return response.json();
}

// SATCOM FAILURE is a toggle on this screen: pressed again it sends satcom_restore.
function commandFor(button) {
  if (button.dataset.toggleOff && status && !status.satcom_up) return button.dataset.toggleOff;
  return button.dataset.command;
}

function showState(scenarioState) {
  status = scenarioState.status;
  $("sim-time").textContent = `${localTime.format(new Date(scenarioState.clock_utc))} svensk tid`;
  $("playback").textContent = scenarioState.finished ? "Uppspelningen är klar."
    : !scenarioState.playing ? "Pausad."
    : scenarioState.slowed ? "Saktar in: satellitpassage (1 minut/s)." : "Spelar upp.";
  $("play").classList.toggle("active", scenarioState.playing);
  for (const button of document.querySelectorAll("[data-speed]")) {
    const on = Number(button.dataset.speed) === scenarioState.speed;
    button.classList.toggle("active", on);
    button.setAttribute("aria-pressed", String(on));
  }
  const active = { satcom_down: !status.satcom_up, plus60: status.plus60, god_view: status.god_view, space_view: status.space_view, iot: status.iot, detection: Boolean(status.detection) };
  for (const button of document.querySelectorAll("[data-filter]")) {
    const shown = !status.hidden_layers.includes(button.dataset.filter);
    button.classList.toggle("active", shown);
    button.setAttribute("aria-pressed", String(shown));
  }
  for (const button of document.querySelectorAll("[data-status]")) {
    const on = Boolean(active[button.dataset.status]);
    button.classList.toggle("active", on);
    button.setAttribute("aria-pressed", String(on));
  }
  $("next").disabled = !status.detection;
  showImages(scenarioState.clock_utc);
  $("detection-step").textContent = detectionStepLine(status.detection, place);
  const list = $("scenario-status");
  list.innerHTML = "";
  const lines = statusLines(status);
  for (const line of lines.length ? lines : [{ level: "ok", text: "Inga avvikelser." }]) {
    const item = document.createElement("li");
    item.className = line.level;
    item.textContent = line.text;
    list.append(item);
  }
  showIot();
  const log = $("event-log");
  log.innerHTML = "";
  for (const event of scenarioState.events.slice(-12).reverse()) {
    const item = document.createElement("li");
    item.textContent = `${event.clock_utc.slice(5, 16).replace("T", " ")} UTC – ${eventText(event).title}`;
    log.append(item);
  }
}

// The map or a satellite image for every screen: the list grows with the scenario clock
// (landsat.js imageOptions), and the choice is the scenario status's image.
function showImages(clockUtc) {
  clockShown = clockUtc;
  if (!config || !status) return;
  const info = config.layers.landsat;
  const select = $("image-pick");
  if (!info) {
    select.disabled = true;
    for (const button of document.querySelectorAll("[data-image]")) button.disabled = true;
    $("image-shown").textContent = "Satellitbilderna är inte hämtade.";
    return;
  }
  const clockMs = Date.parse(clockUtc);
  const options = imageOptions(info.scenes, info.names, clockMs, (isoUtc) => shortTime.format(new Date(isoUtc)));
  const values = options.map((item) => item.value).join(",");
  if (values !== imageList) {
    imageList = values;
    select.innerHTML = "";
    select.append(new Option("Karta (ingen satellitbild)", "off"), new Option("Senaste satellitbild fram till scenariotiden", "auto"));
    const taken = document.createElement("optgroup");
    taken.label = "Tagna fram till scenariotiden";
    const later = document.createElement("optgroup");
    later.label = "Jämförelse";
    for (const item of options) (item.text.endsWith("(jämförelse – tagen senare)") ? later : taken).append(new Option(item.text, item.value));
    for (const group of [taken, later]) if (group.children.length) select.append(group);
  }
  const pick = status.image || "auto";
  const selection = landsatSelection(info.scenes, clockMs, pick, latestImage);
  // A chosen image not taken yet gives way to the latest, as on the main screen.
  select.value = selection.key === pick || pick === "off" ? pick : "auto";
  for (const button of document.querySelectorAll("[data-image]")) {
    const on = button.dataset.image === select.value;
    button.classList.toggle("active", on);
    button.setAttribute("aria-pressed", String(on));
  }
  const [name, image] = (selection.key || "").split("|");
  const scene = info.scenes.find((item) => item.scene === name) || null;
  $("image-shown").textContent = viewCaption({
    scene, image, reason: selection.reason, choice: latestImage, mapData: config.layers.map_data,
    offlineTiles: config.layers.offline_tiles, formatTime: (isoUtc) => `${localTime.format(new Date(isoUtc))} svensk tid`,
    formatDate: (isoUtc) => localDate.format(new Date(isoUtc)),
  });
}

function chooseImage(value) {
  send("image", value).then((state) => {
    showState(state);
    $("command-status").textContent = "";
  }).catch((error) => {
    $("command-status").textContent = `Bildvalet misslyckades: ${error.message}`;
  });
}

function showIot() {
  if (status && status.iot === false) {
    $("real-sensors").innerHTML = '<li class="alert">IoT avstängt</li>';
    return;
  }
  const readings = [...realSensors.values()].sort((a, b) => `${a.node}/${a.kind}`.localeCompare(`${b.node}/${b.kind}`));
  const list = $("real-sensors");
  list.innerHTML = "";
  for (const line of readings.length ? readings.map(realSensorLine) : [{ level: "ok", text: "Inga noder." }]) {
    const item = document.createElement("li");
    item.className = line.level;
    item.textContent = line.text;
    list.append(item);
  }
  if (iotConnection) $("iot-connection").textContent = connectionText({ ...iotConnection, sensors: readings });
}

function connect() {
  const source = new EventSource("/api/scenario/stream");
  const follow = (event) => {
    const data = JSON.parse(event.data);
    showState(data.state || data);
  };
  source.addEventListener("sync", follow);
  source.addEventListener("state", follow);
  source.addEventListener("satcom_queue", (event) => { $("satcom-queue").textContent = queueText(JSON.parse(event.data)); });
  source.addEventListener("synthetic_sensors", (event) => { $("iot-confirms").textContent = confirmsText(JSON.parse(event.data)); });
  source.addEventListener("sensor", (event) => {
    const reading = JSON.parse(event.data);
    realSensors.set(`${reading.node}/${reading.kind}`, reading);
    showIot();
  });
  source.addEventListener("sensor_health", (event) => {
    const health = JSON.parse(event.data);
    const reading = realSensors.get(`${health.node}/${health.kind}`);
    if (reading) reading.online = health.online;
    showIot();
  });
  source.onerror = () => { $("playback").textContent = "Anslutningen till backend bröts – försöker igen …"; };
}

for (const button of document.querySelectorAll("[data-command]")) {
  button.addEventListener("click", () => {
    const name = commandFor(button);
    send(name, button.dataset.target, button.dataset.speed).then((state) => {
      showState(state);
      $("command-status").textContent = "";
    }).catch((error) => {
      $("command-status").textContent = `${name} misslyckades: ${error.message}`;
    });
  });
}
for (const button of document.querySelectorAll("[data-image]")) button.addEventListener("click", () => chooseImage(button.dataset.image));
// BYT DEMO: the backend stops and tools/start_demo.py shows its menu here in mission control.
$("switch-demo").addEventListener("click", async () => {
  if (!window.confirm("Avsluta demon och visa menyn med demos här i mission control?")) return;
  const headers = token ? { "X-Control-Token": token } : {};
  const response = await fetch("/api/demo/menu", { method: "POST", headers }).catch(() => null);
  const error = response && !response.ok ? await response.json().catch(() => ({})) : null;
  $("command-status").textContent = !response ? "BYT DEMO: backend svarar inte."
    : error ? `BYT DEMO gick inte: ${error.detail || error.error}` : "Demon avslutas – menyn visas strax här.";
});
$("image-pick").addEventListener("change", (event) => chooseImage(event.target.value));
// The scenario's name in the header.
fetch("/api/config").then((response) => response.json()).then((loaded) => {
  config = loaded;
  const names = config.layers.landsat?.names || {};
  latestImage = config.incident !== "wildfire" ? (names.radar ? "radar" : Object.keys(names)[0]) : names.swir ? "swir" : "natural";
  $("control-label").textContent = config.control_label;
  place = config.incident_place;
  if (clockShown) showImages(clockShown);
  // Only the buttons of the scenario's kind of incident (styles.css).
  document.body.dataset.incident = config.incident;
}).catch(() => {});
fetch("/api/sensors").then((response) => response.json()).then((snapshot) => {
  iotConnection = snapshot;
  showIot();
}).catch((error) => { $("iot-connection").textContent = `IoT kunde inte laddas: ${error.message}.`; });
connect();
