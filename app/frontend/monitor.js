// The satellite monitor in a window of its own (monitor.html): the world map with the scenario year's
// orbits and the timeline of passes over the fire, filling the window, plus each satellite's
// height, speed and next pass. It follows the shared scenario clock like every other screen.
"use strict";

const DAY = 86400000;
const passCache = new Map();
const hourMinute = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", hour: "2-digit", minute: "2-digit" });
const dayTime = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
const dayShort = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", day: "numeric", month: "short" });

async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

function passesOn(lib, item, day, centre) {
  const key = `${item.norad}|${day}`;
  if (!passCache.has(key)) {
    passCache.set(key, satellitePasses(lib, item, day * DAY, (day + 1) * DAY, centre[0], centre[1]));
  }
  return passCache.get(key);
}

async function start() {
  const note = document.getElementById("monitor-note");
  const config = await getJson("/api/config");
  document.title = `Satellitbevakning – ${config.title}`;
  document.getElementById("monitor-label").textContent =
    `Satelliternas läge ${config.playback.start_utc.slice(0, 4)}, beräknat ur banelement – inte live`;
  const data = await getJson("/api/satellites");
  if (!data.available) {
    note.textContent = data.note;
    return;
  }
  const lib = await import("/vendor/satellite.js-7.1.0/index.js");
  // The read-aloud voices' credit (speech.py; alma is CC BY 4.0) after the satellites' source.
  note.textContent = `${data.label}. Källa: ${data.source}.${config.speech_credit ? ` ${config.speech_credit}.` : ""}`;
  const centre = config.fire_centre;
  const place = config.incident_place;
  // The log of satellite and IoT events: FIRMS passes, Landsat scenes and the synthetic sensors' changes
  // once (each line shows when the clock reaches it), the computed passes per day from passCache.
  const firms = firmsPasses((await getJson("/api/hotspots").catch(() => ({ features: [] }))).features);
  const sensorEvents = (await getJson("/api/sensors/synthetic/events").catch(() => ({ events: [] }))).events;
  // Threatened buildings: asked again on the next load if PostGIS could not answer.
  const threats = await getJson("/api/threats").catch(() => ({}));
  const scenes = config.layers.landsat?.scenes || [];
  // Only the satellites that send the scenario data to the ground get an orbit (orbits.js).
  const contributing = contributingSatellites(data.satellites, scenes);
  let logShown = null;
  let logKey = null;  // the lines last drawn, so the list is only rebuilt when they change
  // Reading aloud (mission control's UPPLÄSNING, the status's `speech`): only lines that come in while
  // the clock runs; a load, a RESET or a jump in time (the state's `jump`) only marks the lines as heard.
  // The backend speaks them in Swedish through this computer's speakers (POST /api/speak, speech.py).
  const heard = new Set();
  let heardJump = null;
  let speaking = false;
  let nextVoice = 0;  // the voices take turns, one message each (alternateVoices); now alma alone
  let summarySince = null;  // when the scenario came to its start (summaryState), to read its summary once
  const post = (path, body) => fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
    .catch(() => null);
  // The level sensors' report (levelReport), once per scenario day while any alarms; from the stream's
  // synthetic_sensors events, which come when the sensors change.
  let levelSensors = [];
  let reportNext = null;
  let reportJump = null;
  const speak = (lines, keep = false) => {
    if (!lines.length) return;
    post("/api/speak", keep ? { lines, keep } : { lines });
    document.body.dataset.spoken = lines.map((line) => `${line.voice}: ${line.text}`).join(" | ");  // read by the tests
  };
  // Scrolled down to older lines, how far the view is from the list's end; null at the top. The
  // view keeps that distance while new lines come in at the top and while the list changes size.
  const logList = document.getElementById("monitor-log-lines");
  let logFromEnd = null;
  let logRestoring = false;
  const keepLogView = () => {
    if (logFromEnd === null) return;
    logRestoring = true;
    logList.scrollTop = Math.max(0, logList.scrollHeight - logList.clientHeight - logFromEnd);
    requestAnimationFrame(() => { logRestoring = false; });
  };
  logList.addEventListener("scroll", () => {
    if (logRestoring) return;
    logFromEnd = logList.scrollTop > 0 ? logList.scrollHeight - logList.scrollTop - logList.clientHeight : null;
  });
  new ResizeObserver(keepLogView).observe(logList);
  // Everything from the demo's start (scenarioState.start_utc) up to the clock, newest first; the
  // list scrolls back to the first line.
  const showLog = (scenarioState, clock) => {
    logShown = [scenarioState, clock];
    const startMs = Date.parse(scenarioState.start_utc || config.playback.start_utc);
    const first = Math.floor(startMs / DAY);
    const last = Math.floor(clock.getTime() / DAY);
    const satellites = data.satellites.filter(hasPasses).map((satellite) => ({
      name: satellite.name, instrument: satellite.instrument,
      passes: Array.from({ length: Math.max(0, last - first + 1) }, (_, i) => passesOn(lib, satellite, first + i, centre)).flat(),
    }));
    const lines = satelliteLog({ satellites, firms, scenes, events: scenarioState.events || [], sensorEvents, threats,
      forecastIssues: config.layers.met_forecast?.issues || [], lightningEvents: config.layers.lightning?.events || [],
      lightningKm: config.layers.lightning?.near_km || 30, routeImpacts: config.layers.routes?.impacts || [],
      meteosatQuarters: config.layers.meteosat?.quarters || [], fireRiskChanges: config.layers.meteosat_frm?.changes || [] }, clock.getTime(),
      clock.getTime() - startMs + 1, Infinity, place);
    if (scenarioState.jump !== heardJump) {
      heardJump = scenarioState.jump;
      heard.clear();
      for (const line of lines) heard.add(satlogKey(line));
    }
    const spoken = spokenLines(lines, heard);
    const report = levelReport(levelSensors);
    const due = levelReportDue(reportNext, clock.getTime(), report !== null, scenarioState.jump !== reportJump);
    reportNext = due.next;
    reportJump = scenarioState.jump;
    if (due.speak && scenarioState.playing) spoken.push({ text: report });
    // The scenario's summary when it comes to its start, as the main screen shows it; all of it waits
    // in the backend's queue, as the clock stands still.
    const summary = summaryState(summarySince, scenarioState, Date.now());
    summarySince = summary.since;
    if (scenarioState.status?.speech) {
      if (summary.entered && config.summary?.length) {
        const duration = summaryDuration(scenarioState);
        const voiced = alternateVoices(summaryMessages(config.title, [...config.summary, ...(duration ? [duration] : [])]), nextVoice);
        nextVoice = voiced.next;
        speak(voiced.lines, true);
      }
      if (spoken.length) {
        const voiced = alternateVoices(spoken, nextVoice);
        nextVoice = voiced.next;
        speak(voiced.lines);
      }
    } else if (speaking) post("/api/speak/stop", {});  // switched off, and only then: silence at once
    speaking = Boolean(scenarioState.status?.speech);
    const key = lines.map(satlogKey).join("\n");
    if (key === logKey) return;
    logKey = key;
    const log = logList;
    log.innerHTML = "";
    if (!lines.length) {
      const empty = document.createElement("li");
      empty.className = "monitor-log-empty";
      empty.textContent = "Inga satellit- eller IoT-händelser sedan demons start.";
      log.append(empty);
      return;
    }
    lines.forEach((line, index) => {
      const row = document.createElement("li");
      row.className = `${index === 0 ? "latest " : ""}${line.source}`;
      const time = document.createElement("time");
      time.textContent = `${dayShort.format(new Date(line.atMs))} ${hourMinute.format(new Date(line.atMs))}`;
      const source = document.createElement("span");
      source.className = "monitor-log-source";
      source.textContent = line.sourceText || SATLOG_SOURCES[line.source];
      row.append(time, ` ${line.text} `, source);
      log.append(row);
    });
    keepLogView();
  };
  const monitor = createSatelliteMonitor(document.getElementById("monitor"), centre, (time) => hourMinute.format(time),
    { width: 0, mapHeight: 0, rowHeight: 30, fit: true }, place, config.playback.start_utc.slice(0, 4));
  let drawnAt = null;
  // The pass of mission control's detection sequence, from /api/detection once per pass.
  let markPass = null;

  const followDetection = async (detection) => {
    const pass = detection ? detection.pass_utc : null;
    if (pass === markPass) return;
    markPass = pass;
    const info = pass ? await getJson("/api/detection").catch(() => null) : null;
    if (markPass !== pass) return;
    monitor.setMark(info ? { atMs: Date.parse(info.pass.pass_utc), firms: info.pass.satellite, norad: info.pass.norad } : null);
    document.body.dataset.mark = info ? info.pass.pass_utc : "";  // read by tools/check_demo.py
  };

  const show = (scenarioState) => {
    const clock = new Date(scenarioState.clock_utc);
    const slowed = scenarioState.playing && scenarioState.slowed ? " · saktar in vid passage" : "";
    document.getElementById("monitor-clock").textContent = `${dayTime.format(clock)} svensk tid${slowed}`;
    followDetection(scenarioState.status.detection);
    // Mission control's events can change while the clock stands still.
    showLog(scenarioState, clock);
    if (drawnAt === clock.getTime()) return;
    drawnAt = clock.getTime();
    const first = Math.floor((clock.getTime() - MONITOR_WINDOW.beforeMs) / DAY);
    const last = Math.floor((clock.getTime() + MONITOR_WINDOW.afterMs) / DAY) + 1;
    const items = data.satellites.map((satellite) => ({
      ...satellite,
      point: subpoint(lib, satellite.elements, clock),
      track: contributing.has(satellite.name) ? orbitTrack(lib, satellite.elements, clock, 50, 2) : [],
      passes: hasPasses(satellite)
        ? Array.from({ length: last - first + 1 }, (_, i) => passesOn(lib, satellite, first + i, centre)).flat() : null,
    })).filter((item) => item.point);
    monitor.draw(items, clock);
    const list = document.getElementById("monitor-list");
    list.innerHTML = "";
    for (const item of items) {
      const next = item.passes?.find((pass) => pass.end > clock.getTime());
      const pass = !item.passes ? "" : !next ? ` · ingen passage över ${place} närmaste dygnet`
        : next.start <= clock.getTime() ? ` · ÖVER ${place.toUpperCase()} NU` : ` · nästa passage över ${place} ${hourMinute.format(new Date(next.start))}`;
      const row = document.createElement("li");
      const swatch = document.createElement("span");
      swatch.className = "monitor-swatch";
      swatch.style.background = monitorColor(item);
      row.append(swatch, `${item.name}${item.instrument ? ` (${item.instrument})` : ""}: ${Math.round(item.point.height_km)} km, `
        + `${item.point.speed_km_s.toFixed(1).replace(".", ",")} km/s${pass}`);
      row.className = next && next.start <= clock.getTime() ? "active" : "";
      list.append(row);
    }
  };

  const source = new EventSource("/api/scenario/stream");
  const follow = (event) => { const body = JSON.parse(event.data); show(body.state || body); };
  source.addEventListener("sync", follow);
  source.addEventListener("state", follow);
  source.addEventListener("synthetic_sensors", (event) => { levelSensors = JSON.parse(event.data).sensors || []; });
  source.onerror = () => { note.textContent = "Anslutningen till backend bröts – försöker igen …"; };
  window.addEventListener("resize", () => {
    monitor.redraw();
    if (logShown) showLog(...logShown);
  });
}

start().catch((error) => { document.getElementById("monitor-note").textContent = `Fel vid start: ${error.message}`; });
