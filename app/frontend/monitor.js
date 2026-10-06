// The satellite monitor in a window of its own (monitor.html): the world map with the 2014
// orbits and the timeline of passes over the fire, filling the window, plus each satellite's
// height, speed and next pass. It follows the shared scenario clock like every other screen.
"use strict";

const DAY = 86400000;
const passCache = new Map();
const hourMinute = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", hour: "2-digit", minute: "2-digit" });
const dayTime = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

function passesOn(lib, item, day, centre) {
  const key = `${item.norad}|${day}`;
  if (!passCache.has(key)) {
    passCache.set(key, passesBetween(lib, item.elements, day * DAY, (day + 1) * DAY, centre[0], centre[1], item.half_swath_km));
  }
  return passCache.get(key);
}

async function start() {
  const note = document.getElementById("monitor-note");
  const config = await getJson("/api/config");
  const data = await getJson("/api/satellites");
  if (!data.available) {
    note.textContent = data.note;
    return;
  }
  const lib = await import("/vendor/satellite.js-7.1.0/index.js");
  note.textContent = `${data.label}. Källa: ${data.source}.`;
  const centre = config.fire_centre;
  const monitor = createSatelliteMonitor(document.getElementById("monitor"), centre, (time) => hourMinute.format(time),
    { width: 0, mapHeight: 0, rowHeight: 30, fit: true });
  let drawnAt = null;
  // The pass of mission control's detection sequence, from /api/detection once per pass.
  let markPass = null;

  const followDetection = async (detection) => {
    const pass = detection ? detection.pass_utc : null;
    if (pass === markPass) return;
    markPass = pass;
    const info = pass ? await getJson("/api/detection").catch(() => null) : null;
    if (markPass !== pass) return;
    monitor.setMark(info ? { atMs: Date.parse(info.pass.pass_utc), firms: info.pass.satellite } : null);
    document.body.dataset.mark = info ? info.pass.pass_utc : "";  // read by tools/check_demo.py
  };

  const show = (scenarioState) => {
    const clock = new Date(scenarioState.clock_utc);
    const slowed = scenarioState.playing && scenarioState.slowed ? " · saktar in vid passage" : "";
    document.getElementById("monitor-clock").textContent = `${dayTime.format(clock)} svensk tid${slowed}`;
    followDetection(scenarioState.status.detection);
    if (drawnAt === clock.getTime()) return;
    drawnAt = clock.getTime();
    const first = Math.floor((clock.getTime() - MONITOR_WINDOW.beforeMs) / DAY);
    const last = Math.floor((clock.getTime() + MONITOR_WINDOW.afterMs) / DAY) + 1;
    const items = data.satellites.map((satellite) => ({
      ...satellite,
      point: subpoint(lib, satellite.elements, clock),
      track: orbitTrack(lib, satellite.elements, clock, 50, 2),
      passes: satellite.half_swath_km
        ? Array.from({ length: last - first + 1 }, (_, i) => passesOn(lib, satellite, first + i, centre)).flat() : null,
    })).filter((item) => item.point);
    monitor.draw(items, clock);
    const list = document.getElementById("monitor-list");
    list.innerHTML = "";
    for (const item of items) {
      const next = item.passes?.find((pass) => pass.end > clock.getTime());
      const pass = !item.passes ? "" : !next ? " · ingen passage över branden närmaste dygnet"
        : next.start <= clock.getTime() ? " · ÖVER BRANDEN NU" : ` · nästa passage över branden ${hourMinute.format(new Date(next.start))}`;
      const row = document.createElement("li");
      row.textContent = `${item.name}${item.instrument ? ` (${item.instrument})` : ""}: ${Math.round(item.point.height_km)} km, `
        + `${item.point.speed_km_s.toFixed(1).replace(".", ",")} km/s${pass}`;
      row.className = next && next.start <= clock.getTime() ? "active" : "";
      list.append(row);
    }
  };

  const source = new EventSource("/api/scenario/stream");
  const follow = (event) => { const body = JSON.parse(event.data); show(body.state || body); };
  source.addEventListener("sync", follow);
  source.addEventListener("state", follow);
  source.onerror = () => { note.textContent = "Anslutningen till backend bröts – försöker igen …"; };
  window.addEventListener("resize", () => monitor.redraw());
}

start().catch((error) => { document.getElementById("monitor-note").textContent = `Fel vid start: ${error.message}`; });
