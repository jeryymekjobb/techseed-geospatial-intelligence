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
let imageList = null;  // the values in the image list, to rebuild it only when they change
let clockShown = null;  // the scenario clock last shown, for when /api/config arrives after it
let pendingPick = null;  // an image chosen in the list, shown on the screens only with VISA VALD BILD
const realSensors = new Map();
let iotConnection = null;

async function send(name, target, speed) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["X-Control-Token"] = token;
  const body = { command: name };
  if (target !== undefined && target !== null) body.target = target;
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
  showBaseMaps();
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
    $("show-pick").disabled = true;
    for (const button of document.querySelectorAll("[data-image]")) button.disabled = true;
    $("image-shown").textContent = "Satellitbilderna är inte hämtade.";
    return;
  }
  const clockMs = Date.parse(clockUtc);
  // The ticked image types: "auto" follows the latest of them, and the list holds only them.
  const types = imageTypesShown(status.image_types, config.incident, info.names);
  const counts = imageTypeCounts(info.scenes, info.names, clockMs);
  for (const box of document.querySelectorAll("#image-types input")) {
    box.checked = types.includes(box.value);
    const count = counts[box.value];
    box.parentElement.querySelector(".count").textContent = `${count.taken} av ${count.total} tagna`;
  }
  const options = imageOptions(info.scenes, info.names, clockMs, (isoUtc) => shortTime.format(new Date(isoUtc)), types);
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
  const selection = landsatSelection(info.scenes, clockMs, pick, types);
  // A chosen image not taken yet gives way to the latest, as on the main screen.
  const current = selection.key === pick || pick === "off" ? pick : "auto";
  // The list keeps an image chosen in it until VISA VALD BILD, unless it is shown already or has left the list.
  if (pendingPick === current || ![...select.options].some((option) => option.value === pendingPick)) pendingPick = null;
  select.value = pendingPick ?? current;
  $("show-pick").disabled = pendingPick === null;
  for (const button of document.querySelectorAll("[data-image]")) {
    const on = button.dataset.image === current;
    button.classList.toggle("active", on);
    button.setAttribute("aria-pressed", String(on));
  }
  const [name, image] = (selection.key || "").split("|");
  const scene = info.scenes.find((item) => item.scene === name) || null;
  $("image-shown").textContent = viewCaption({
    scene, image, reason: selection.reason, choice: types, mapData: config.layers.map_data,
    // As on the 3D main screen in the booth.
    baseMap: baseMapFor(baseMapsShown(status.base_maps, config.layers.base_maps), config.layers.base_maps, "3d"),
    offlineTiles: config.layers.offline_tiles, formatTime: (isoUtc) => `${localTime.format(new Date(isoUtc))} svensk tid`,
    formatDate: (isoUtc) => localDate.format(new Date(isoUtc)),
  }) + (pendingPick === null ? "" : `\nVald i listan: ${select.options[select.selectedIndex].text} – tryck VISA VALD BILD.`);
}

// The base maps ticked in mission control, for every screen (the scenario status's base_maps;
// basemaps.js). The note says which map each screen shows of them.
function setupBaseMaps(baseMaps) {
  const box = $("base-maps");
  for (const item of baseMaps) {
    const label = document.createElement("label");
    label.innerHTML = `<input type="checkbox" value="${item.id}"> <span></span> <span class="count"></span>`;
    label.querySelector("span").textContent = item.label;
    label.querySelector(".count").textContent = item.only_2d ? "bara 2D" : "";
    box.append(label);
  }
  box.addEventListener("change", () => {
    const ticked = [...box.querySelectorAll("input:checked")].map((input) => input.value);
    send("base_maps", ticked.join(",")).then((state) => {
      showState(state);
      $("command-status").textContent = "";
    }).catch((error) => {
      $("command-status").textContent = `Valet av baskartor misslyckades: ${error.message}`;
    });
  });
}

function showBaseMaps() {
  if (!config || !status) return;
  const baseMaps = config.layers.base_maps;
  const ticked = baseMapsShown(status.base_maps, baseMaps);
  for (const box of document.querySelectorAll("#base-maps input")) box.checked = ticked.includes(box.value);
}

// The image types ticked in mission control, for every screen (the scenario status's image_types).
function setupImageTypes(info) {
  const box = $("image-types");
  for (const [kind, text] of Object.entries(info?.names || {})) {
    const label = document.createElement("label");
    label.innerHTML = `<input type="checkbox" value="${kind}"> <span>${IMAGE_KINDS[kind] || kind}</span> <span class="count"></span>`;
    label.title = text;
    box.append(label);
  }
  box.hidden = !info;
  box.addEventListener("change", () => {
    const ticked = [...box.querySelectorAll("input:checked")].map((input) => input.value);
    send("image_types", ticked.join(",")).then((state) => {
      showState(state);
      $("command-status").textContent = "";
    }).catch((error) => {
      $("command-status").textContent = `Valet av bildtyper misslyckades: ${error.message}`;
    });
  });
}

function chooseImage(value) {
  pendingPick = null;
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
$("image-pick").addEventListener("change", (event) => {
  pendingPick = event.target.value;
  showImages(clockShown);
});
$("show-pick").addEventListener("click", () => { if (pendingPick !== null) chooseImage(pendingPick); });
// The scenario's name in the header.
fetch("/api/config").then((response) => response.json()).then((loaded) => {
  config = loaded;
  setupImageTypes(config.layers.landsat);
  setupBaseMaps(config.layers.base_maps);
  $("control-label").textContent = config.control_label;
  place = config.incident_place;
  if (clockShown) showImages(clockShown);
  showBaseMaps();
  // Only the buttons of the scenario's kind of incident (styles.css).
  document.body.dataset.incident = config.incident;
}).catch(() => {});
fetch("/api/sensors").then((response) => response.json()).then((snapshot) => {
  iotConnection = snapshot;
  showIot();
}).catch((error) => { $("iot-connection").textContent = `IoT kunde inte laddas: ${error.message}.`; });
connect();
