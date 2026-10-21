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
const startupAt = new URLSearchParams(window.location.search).get("at");
let documentLoaded = document.readyState === "complete";
let startupConfigReady = false;
let startupSyncReady = false;
let startupResetSent = false;
let pendingPick = null;  // an image chosen in the list, shown on the screens only with VISA VALD BILD
let pendingSpeed = null;  // a speed chosen in the list, used only with ANVÄND
let pendingWindow = false;  // the demo's start or stop edited, sent only with ANVÄND TIDER

// A button that applies a choice (ANVÄND, VISA VALD BILD, ANVÄND TIDER) is red while the choice
// differs from what the screens show, and greyed out when there is nothing to apply.
function markPending(id, pending) {
  $(id).disabled = !pending;
  $(id).classList.toggle("unsaved", pending);
}
let savedProfile = null;  // the profile the demo starts with (config, then SPARA PROFIL)
let lastState = null;  // the scenario state last shown, to mark unsaved profile settings
const realSensors = new Map();
let iotConnection = null;

async function send(name, target, speed, at) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["X-Control-Token"] = token;
  const body = { command: name };
  if (target !== undefined && target !== null) body.target = target;
  if (speed) body.speed = Number(speed);
  if (at) body.at = at;
  const response = await fetch("/api/scenario/command", { method: "POST", headers, body: JSON.stringify(body) });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error === "control_token_required" ? "fel eller saknad token (?token=)" : error.detail || error.error || `HTTP ${response.status}`);
  }
  return response.json();
}

function resetAfterMissionControlLoad() {
  if (!documentLoaded || !startupConfigReady || !startupSyncReady || startupResetSent) return;
  startupResetSent = true;  // EventSource may send another sync after a reconnect.
  (async () => {
    try {
      showState(await send("reset"));
      // Only an explicit non-default start point is applied after the reset.
      if (startupAt && startupAt !== config.playback.start_utc) showState(await send("seek", null, null, startupAt));
      $("command-status").textContent = "";
    } catch (error) {
      $("command-status").textContent = `Reset vid laddning misslyckades: ${error.message}`;
    }
  })();
}

if (!documentLoaded) {
  window.addEventListener("load", () => {
    documentLoaded = true;
    resetAfterMissionControlLoad();
  }, { once: true });
}

// SATCOM FAILURE is a toggle on this screen: pressed again it sends satcom_restore.
function commandFor(button) {
  if (button.dataset.toggleOff && status && !status.satcom_up) return button.dataset.toggleOff;
  return button.dataset.command;
}

function showState(scenarioState) {
  status = scenarioState.status;
  if (!status.question?.id) $("control-answer").textContent = "";  // RENSA SVARET or RESET
  $("sim-time").textContent = `${localTime.format(new Date(scenarioState.clock_utc))} svensk tid`;
  $("playback").textContent = scenarioState.finished ? "Uppspelningen är klar."
    : !scenarioState.playing ? "Pausad."
    : scenarioState.slowed ? "Saktar in: satellitpassage (1 minut/s)." : "Spelar upp.";
  $("play").classList.toggle("active", scenarioState.playing);
  // The speed list shows the speed in use, or the one chosen until ANVÄND.
  const speeds = $("speed-pick");
  if (pendingSpeed === String(scenarioState.speed)) pendingSpeed = null;
  showWindow(scenarioState);
  // UPPLÄSNING: the satellite monitor reads new log lines aloud.
  $("speech-toggle").textContent = status.speech ? "UPPLÄSNING PÅ" : "UPPLÄSNING AV";
  $("speech-toggle").classList.toggle("active", Boolean(status.speech));
  // VISA 2D / VISA 3D: the main screen's map; the button names the other one.
  $("view-toggle").textContent = status.view === "2d" ? "VISA 3D" : "VISA 2D";
  lastState = scenarioState;
  showUnsaved();
  if (![...speeds.options].some((option) => Number(option.value) === scenarioState.speed)) {
    speeds.append(new Option(`${scenarioState.speed} s/s`, String(scenarioState.speed)));
  }
  speeds.value = pendingSpeed ?? String(scenarioState.speed);
  markPending("apply-speed", pendingSpeed !== null);
  const active = { satcom_down: !status.satcom_up, plus60: status.plus60, god_view: status.god_view, space_view: status.space_view, iot: status.iot, detection: Boolean(status.detection) };
  for (const button of document.querySelectorAll("[data-status]")) {
    const on = Boolean(active[button.dataset.status]);
    button.classList.toggle("active", on);
    button.setAttribute("aria-pressed", String(on));
  }
  $("next").disabled = !status.detection;
  showImages(scenarioState.clock_utc);
  showBaseMaps();
  showMapLayers();
  showChoices();
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
    markPending("show-pick", false);
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
  markPending("show-pick", pendingPick !== null);
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

// The prepared questions (spatial.py): asked on every main screen, which shows the answer on its map;
// mission control shows the answer's text.
function setupQuestions(questions) {
  for (const question of questions) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = question.question;
    button.addEventListener("click", async () => {
      $("control-answer").textContent = "Frågar PostGIS …";
      try {
        showState(await send("ask", question.id));
        const response = await fetch(`/api/ask?q=${encodeURIComponent(question.id)}`);
        const body = await response.json();
        $("control-answer").textContent = response.ok ? body.answer : `Frågan kunde inte besvaras: ${body.detail || body.error}`;
      } catch (error) {
        $("control-answer").textContent = `Frågan kunde inte ställas: ${error.message}`;
      }
    });
    $("control-questions").append(button);
  }
}

// The main screen's panel: the forecast horizon and the stations it shows (the status's choices;
// server.py panel_choices), one list each; a list not chosen in shows the panel's default.
// The panel's choices that sit in mission control's left column; the others are under Kartan.
const LEFT_CHOICES = ["rain_station"];

function setupChoices(choices) {
  for (const [key, choice] of Object.entries(choices)) {
    const box = $(LEFT_CHOICES.includes(key) ? "left-choices" : "panel-choices");
    const label = document.createElement("label");
    label.className = "image-pick";
    label.append(`${choice.label} `);
    const select = document.createElement("select");
    select.dataset.choice = key;
    for (const [value, text] of choice.options) select.append(new Option(text, value));
    select.addEventListener("change", () => {
      send("choose", `${key}=${select.value}`).then((state) => {
        showState(state);
        $("command-status").textContent = "";
      }).catch((error) => {
        $("command-status").textContent = `${choice.label} kunde inte väljas: ${error.message}`;
      });
    });
    label.append(select);
    box.append(label);
  }
}

function showChoices() {
  if (!config || !status) return;
  for (const select of document.querySelectorAll("select[data-choice]")) {
    const key = select.dataset.choice;
    select.value = status.choices?.[key] ?? config.layers.panel_choices[key].default;
  }
}

// The maps' layers and GOD VIEW's filter in one box. A category (FILTER_CATEGORIES) is a row of
// its own that sends the filter event as its button did, with its layers under it; the other
// layers follow. A layer is switched for every screen (the status's map_layers; panel.js
// applyMapLayers); one not switched yet is as the 3D globe in the booth starts it, or the 2D map
// for a 2D-only layer. The categories the demo lacks are greyed out.
function layerRow(item, className) {
  const label = document.createElement("label");
  label.className = className;
  label.innerHTML = '<input type="checkbox"> <span></span> <span class="count"></span>';
  label.querySelector("input").value = item.name;
  label.querySelector("span").textContent = item.name;
  label.querySelector(".count").textContent = item.default_2d === null ? "bara 3D" : item.default_3d === null ? "bara 2D" : "";
  return label;
}

function setupMapLayers(items) {
  const box = $("map-layers");
  for (const category of FILTER_CATEGORIES) {
    const row = document.createElement("label");
    row.className = "layer-category";
    row.innerHTML = '<input type="checkbox"> <span></span> <span class="count"></span>';
    const input = row.querySelector("input");
    input.dataset.category = category.id;
    input.disabled = Boolean(category.missing);
    row.querySelector("span").textContent = category.label;
    row.querySelector(".count").textContent = category.missing ? MISSING_NOTE : "";
    box.append(row);
    for (const item of items.filter((entry) => entry.category === category.id)) box.append(layerRow(item, "layer-child"));
  }
  for (const item of items.filter((entry) => !entry.category)) box.append(layerRow(item, ""));
  box.addEventListener("change", (event) => {
    const input = event.target;
    if (input.dataset.category) {
      send("filter", input.dataset.category).then((state) => {
        showState(state);
        $("command-status").textContent = "";
      }).catch((error) => {
        $("command-status").textContent = `Filtret kunde inte ändras: ${error.message}`;
      });
      return;
    }
    send(input.checked ? "map_layer_on" : "map_layer_off", input.value).then((state) => {
      showState(state);
      $("command-status").textContent = "";
    }).catch((error) => {
      $("command-status").textContent = `Lagret ${input.value} kunde inte ändras: ${error.message}`;
    });
  });
}

function showMapLayers() {
  if (!config || !status) return;
  for (const input of document.querySelectorAll("#map-layers input[data-category]")) {
    const category = FILTER_CATEGORIES.find((entry) => entry.id === input.dataset.category);
    input.checked = !category.missing && !status.hidden_layers.includes(category.id);
  }
  for (const input of document.querySelectorAll("#map-layers input:not([data-category])")) {
    const item = config.layers.map_layers.find((entry) => entry.name === input.value);
    input.checked = Boolean(status.map_layers?.[input.value] ?? item.default_3d ?? item.default_2d);
    // A layer under a category the filter hides is hidden with it.
    input.disabled = Boolean(item.category && status.hidden_layers.includes(item.category));
  }
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

// The demo's start and stop (playback_window), within the scenario's period, shown and entered in
// Swedish time; datetime-local fields hold Stockholm wall time ("2026-08-14T02:00").
const wallClock = new Intl.DateTimeFormat("sv-SE", {
  timeZone: "Europe/Stockholm", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});

function wallTime(utc) {
  const parts = Object.fromEntries(wallClock.formatToParts(new Date(utc)).map((part) => [part.type, part.value]));
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

function utcFromWallTime(text) {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(text || "");
  if (!match) return null;
  const wanted = Date.UTC(match[1], match[2] - 1, match[3], match[4], match[5]);
  let guess = wanted;
  for (let round = 0; round < 2; round += 1) {  // Stockholm's offset at the guess, then again across a DST change
    const shown = Date.parse(`${wallTime(guess)}:00Z`);
    guess += wanted - shown;
  }
  return new Date(guess).toISOString().replace(/\.\d{3}Z$/, "Z");
}

function showWindow(scenarioState) {
  if (!config || pendingWindow) return;
  $("window-start").value = wallTime(scenarioState.start_utc);
  $("window-end").value = wallTime(scenarioState.end_utc);
}

function setupWindow() {
  const first = wallTime(config.playback.data_start_utc);
  const last = wallTime(config.playback.data_end_utc);
  for (const input of [$("window-start"), $("window-end")]) {
    input.min = first;
    input.max = last;
    input.addEventListener("input", () => {
      pendingWindow = true;
      markPending("apply-window", true);
    });
  }
  $("window-note").textContent = `Scenariots data: ${localTime.format(new Date(config.playback.data_start_utc))} – `
    + `${localTime.format(new Date(config.playback.data_end_utc))}. RESET går till start men ändrar inte tiderna, uppspelningen stannar vid stopp; SPARA PROFIL sparar tiderna.`;
}

$("view-toggle").addEventListener("click", () => {
  send("view", status?.view === "2d" ? "3d" : "2d").then((state) => {
    showState(state);
    $("command-status").textContent = "";
  }).catch((error) => {
    $("command-status").textContent = `Vyn kunde inte bytas: ${error.message}`;
  });
});

$("speech-toggle").addEventListener("click", () => {
  send("speech", status?.speech ? "off" : "on").then((state) => {
    showState(state);
    $("command-status").textContent = "";
  }).catch((error) => {
    $("command-status").textContent = `Uppläsningen kunde inte ändras: ${error.message}`;
  });
});

$("apply-window").addEventListener("click", () => {
  const first = utcFromWallTime($("window-start").value);
  const last = utcFromWallTime($("window-end").value);
  if (!first || !last) {
    $("command-status").textContent = "Ange både start och stopp.";
    return;
  }
  send("playback_window", `${first}/${last}`).then((state) => {
    pendingWindow = false;
    markPending("apply-window", false);
    showState(state);
    $("command-status").textContent = "";
  }).catch((error) => {
    $("command-status").textContent = `Tiderna kunde inte ändras: ${error.message}`;
  });
});

// SPARA PROFIL: the ticked image types, base maps, map layers and the demo's start and stop become
// the scenario's profile (app/backend/profiles.py), which the demo starts with and RESET returns to.
// A scenario without one uses the older profile of its kind of incident until it is saved.
const INCIDENT_WORDS = { wildfire: "skogsbrand", flood: "översvämning" };

// Whether the scenario's ticks, start and stop or speed differ from the profile the demo starts
// with, compared as SPARA PROFIL saves them: untouched layers and base maps count with their
// defaults, a profile without start and stop has the whole period, one without a speed the default.
function profileUnsaved(cfg, profile, scenarioState) {
  const saved = profile || {};
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const types = (ticked) => imageTypesShown(ticked, cfg.incident, cfg.layers.landsat?.names);
  const maps = (ticked) => baseMapsShown(ticked, cfg.layers.base_maps);
  const layers = (ticked) => (cfg.layers.map_layers || []).map((item) => [item.name, ticked?.[item.name] ?? item.default_3d ?? item.default_2d])
    .filter(([, visible]) => visible !== null && visible !== undefined).map(([name, visible]) => [name, Boolean(visible)]);
  const window = saved.playback || { start_utc: cfg.playback.data_start_utc, end_utc: cfg.playback.data_end_utc };
  const now = scenarioState.status;
  return !same(types(now.image_types), types(saved.image_types))
    || !same(maps(now.base_maps), maps(saved.base_maps))
    || !same(layers(now.map_layers), layers(saved.map_layers))
    || scenarioState.start_utc !== window.start_utc || scenarioState.end_utc !== window.end_utc
    || scenarioState.speed !== (saved.speed ?? cfg.playback.default_speed)
    || Boolean(now.speech) !== (saved.speech !== false);
}

// SPARA PROFIL is red while the settings differ from the profile.
function showUnsaved() {
  if (!config || !lastState) return;
  const unsaved = profileUnsaved(config, savedProfile, lastState);
  $("save-profile").classList.toggle("unsaved", unsaved);
  $("save-profile").title = unsaved ? "Inställningarna skiljer sig från den sparade profilen." : "";
}

function showProfile(profile) {
  savedProfile = profile;
  const kind = INCIDENT_WORDS[config.incident] || config.incident;
  const saved = profile ? `${localTime.format(new Date(profile.saved_utc))} svensk tid` : "";
  const speedOption = [...$("speed-pick").options].find((option) => Number(option.value) === (profile?.speed ?? config.playback.default_speed));
  const speed = speedOption ? speedOption.textContent : `${profile?.speed ?? config.playback.default_speed} s/s`;
  const period = profile?.playback
    ? `${localTime.format(new Date(profile.playback.start_utc))} – ${localTime.format(new Date(profile.playback.end_utc))}`
    : "hela perioden";
  $("save-profile").textContent = "SPARA PROFIL FÖR SCENARIOT";
  $("profile-note").textContent = !profile
    ? `Ingen sparad profil för ${config.title}: standardvalet och hela perioden gäller.`
    : profile.source === "incident"
      ? `Ingen egen profil för ${config.title}: den äldre profilen för ${kind}, sparad ${saved}, används för bildtyper, baskartor och kartlager. SPARA PROFIL sparar en för det här scenariot.`
      : `Profil för ${config.title} sparad ${saved}; bildtyper, baskartor och kartlager används vid start och RESET, demons tider (${period}) och hastigheten (${speed}) när demon startar.`;
  showUnsaved();
}

$("save-profile").addEventListener("click", async () => {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["X-Control-Token"] = token;
  const response = await fetch("/api/scenario/command", { method: "POST", headers, body: JSON.stringify({ command: "save_profile" }) })
    .catch(() => null);
  const data = response ? await response.json().catch(() => ({})) : {};
  if (!response || !response.ok) {
    $("command-status").textContent = `Profilen sparades inte: ${data.detail || data.error || "backend svarar inte"}`;
    return;
  }
  showProfile(data.display_profile);
  showState(data);
  $("command-status").textContent = "";
});

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
    if (event.type === "sync" && !startupSyncReady) {
      startupSyncReady = true;
      resetAfterMissionControlLoad();
    }
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
    send(name, button.dataset.target, button.dataset.speed, button.dataset.at).then((state) => {
      showState(state);
      $("command-status").textContent = "";
    }).catch((error) => {
      $("command-status").textContent = `${name} misslyckades: ${error.message}`;
    });
  });
}
for (const button of document.querySelectorAll("[data-image]")) button.addEventListener("click", () => chooseImage(button.dataset.image));
// BYT SCENARIO: the backend stops and tools/start_demo.py shows its menu here in mission control.
// STARTA OM DEMO: the backend stops, start_demo closes every screen and starts the same scenario again.
async function demoExit(path, label, question, done) {
  if (!window.confirm(question)) return;
  const headers = token ? { "X-Control-Token": token } : {};
  const response = await fetch(path, { method: "POST", headers }).catch(() => null);
  const error = response && !response.ok ? await response.json().catch(() => ({})) : null;
  $("command-status").textContent = !response ? `${label}: backend svarar inte.`
    : error ? `${label} gick inte: ${error.detail || error.error}` : done;
}
$("switch-demo").addEventListener("click", () => demoExit("/api/demo/menu", "BYT SCENARIO",
  "Avsluta scenariot och visa menyn med scenarier här i mission control?", "Scenariot avslutas – menyn visas strax här."));
$("restart-demo").addEventListener("click", () => demoExit("/api/demo/restart", "STARTA OM DEMO",
  "Starta om demon? Alla skärmar stängs, servern startas om och skärmarna öppnas igen.",
  "Demon startas om – skärmarna stängs och öppnas igen om en stund."));
$("image-pick").addEventListener("change", (event) => {
  pendingPick = event.target.value;
  showImages(clockShown);
});
$("show-pick").addEventListener("click", () => { if (pendingPick !== null) chooseImage(pendingPick); });
$("speed-pick").addEventListener("change", (event) => {
  pendingSpeed = event.target.value;
  markPending("apply-speed", true);
});
$("apply-speed").addEventListener("click", () => {
  if (pendingSpeed === null) return;
  send("speed", null, pendingSpeed).then((state) => {
    pendingSpeed = null;
    showState(state);
    $("command-status").textContent = "";
  }).catch((error) => {
    $("command-status").textContent = `Hastigheten kunde inte ändras: ${error.message}`;
  });
});
// The scenario's name in the header.
fetch("/api/config").then((response) => response.json()).then((loaded) => {
  config = loaded;
  setupImageTypes(config.layers.landsat);
  setupBaseMaps(config.layers.base_maps);
  setupMapLayers(config.layers.map_layers || []);
  showMapLayers();
  setupChoices(config.layers.panel_choices || {});
  fetch("/api/questions").then((response) => response.json()).then(setupQuestions).catch(() => {
    $("control-answer").textContent = "Frågorna kunde inte laddas.";
  });
  showChoices();
  // VISA ALLA: the end of the playback, every detection; FLYG TILL names the incident's place.
  $("show-all").dataset.at = config.playback.end_utc;
  $("fly-incident").textContent = `FLYG TILL ${config.incident_place.toUpperCase()}`;
  showProfile(config.layers.display_profile);
  setupWindow();
  $("control-label").textContent = config.control_label;
  // The branch of the code the backend runs, when known.
  $("code-branch").textContent = config.code_branch ? `Branch: ${config.code_branch}` : "";
  $("code-branch").hidden = !config.code_branch;
  place = config.incident_place;
  if (clockShown) showImages(clockShown);
  showBaseMaps();
  startupConfigReady = true;
  resetAfterMissionControlLoad();
  // Only the buttons of the scenario's kind of incident (styles.css).
  document.body.dataset.incident = config.incident;
}).catch(() => {});
fetch("/api/sensors").then((response) => response.json()).then((snapshot) => {
  iotConnection = snapshot;
  showIot();
}).catch((error) => { $("iot-connection").textContent = `IoT kunde inte laddas: ${error.message}.`; });
connect();
