// Mission control: a touch screen next to the main screen. It sends commands to the
// shared scenario (POST /api/scenario/command) and follows it like every other
// screen (/api/scenario/stream). ?token=<SCENARIO_CONTROL_TOKEN> when the backend
// requires one.
"use strict";

const $ = (id) => document.getElementById(id);
const token = new URLSearchParams(window.location.search).get("token");
const localTime = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", dateStyle: "medium", timeStyle: "short" });
let status = null;
const realSensors = new Map();
let iotConnection = null;

async function send(name, target) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["X-Control-Token"] = token;
  const body = { command: name };
  if (target) body.target = target;
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
  $("playback").textContent = scenarioState.finished ? "Uppspelningen är klar." : scenarioState.playing ? "Spelar upp." : "Pausad.";
  $("play").classList.toggle("active", scenarioState.playing);
  const active = { satcom_down: !status.satcom_up, plus60: status.plus60, god_view: status.god_view };
  for (const button of document.querySelectorAll("[data-status]")) {
    const on = Boolean(active[button.dataset.status]);
    button.classList.toggle("active", on);
    button.setAttribute("aria-pressed", String(on));
  }
  const list = $("scenario-status");
  list.innerHTML = "";
  const lines = statusLines(status);
  for (const line of lines.length ? lines : [{ level: "ok", text: "Inga avvikelser." }]) {
    const item = document.createElement("li");
    item.className = line.level;
    item.textContent = line.text;
    list.append(item);
  }
  const log = $("event-log");
  log.innerHTML = "";
  for (const event of scenarioState.events.slice(-12).reverse()) {
    const item = document.createElement("li");
    item.textContent = `${event.clock_utc.slice(5, 16).replace("T", " ")} UTC – ${eventText(event).title}`;
    log.append(item);
  }
}

function showIot() {
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
    send(name, button.dataset.target).then((state) => {
      showState(state);
      $("command-status").textContent = "";
    }).catch((error) => {
      $("command-status").textContent = `${name} misslyckades: ${error.message}`;
    });
  });
}
fetch("/api/sensors").then((response) => response.json()).then((snapshot) => {
  iotConnection = snapshot;
  showIot();
}).catch((error) => { $("iot-connection").textContent = `IoT kunde inte laddas: ${error.message}.`; });
connect();
