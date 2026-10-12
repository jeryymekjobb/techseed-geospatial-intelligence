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
  note.textContent = `${data.label}. Källa: ${data.source}.`;
  const centre = config.fire_centre;
  const place = config.incident_place;
  // The log of satellite and IoT events: FIRMS passes, Landsat scenes and the synthetic sensors' changes
  // once (each line shows when the clock reaches it), the computed passes per day from passCache.
  const firms = firmsPasses((await getJson("/api/hotspots").catch(() => ({ features: [] }))).features);
  const sensorEvents = (await getJson("/api/sensors/synthetic/events").catch(() => ({ events: [] }))).events;
  const scenes = config.layers.landsat?.scenes || [];
  let logShown = null;
  const showLog = (scenarioState, clock) => {
    logShown = [scenarioState, clock];
    const first = Math.floor((clock.getTime() - SATLOG_WINDOW_MS) / DAY);
    const last = Math.floor(clock.getTime() / DAY);
    const satellites = data.satellites.filter(hasPasses).map((satellite) => ({
      name: satellite.name, instrument: satellite.instrument,
      passes: Array.from({ length: last - first + 1 }, (_, i) => passesOn(lib, satellite, first + i, centre)).flat(),
    }));
    const lines = satelliteLog({ satellites, firms, scenes, events: scenarioState.events || [], sensorEvents }, clock.getTime(),
      SATLOG_WINDOW_MS, SATLOG_LIMIT, place);
    const log = document.getElementById("monitor-log-lines");
    log.innerHTML = "";
    if (!lines.length) {
      const empty = document.createElement("li");
      empty.className = "monitor-log-empty";
      empty.textContent = "Inga satellit- eller IoT-händelser det senaste dygnet.";
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
    // Show only whole lines: drop the oldest that do not fit the space below the overview.
    const bottom = log.getBoundingClientRect().bottom;
    for (const row of [...log.children].reverse()) {
      if (row.getBoundingClientRect().bottom <= bottom + 0.5 || log.children.length === 1) break;
      row.remove();
    }
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
      track: orbitTrack(lib, satellite.elements, clock, 50, 2),
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
  source.onerror = () => { note.textContent = "Anslutningen till backend bröts – försöker igen …"; };
  window.addEventListener("resize", () => {
    monitor.redraw();
    if (logShown) showLog(...logShown);
  });
}

start().catch((error) => { document.getElementById("monitor-note").textContent = `Fel vid start: ${error.message}`; });
