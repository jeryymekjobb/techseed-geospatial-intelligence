// The satellite monitor of the monitoring (app/monitoring/service.py), in a window of its own as the
// demos' (app/frontend/monitor.js), but live: the world map with the orbits and where the satellites
// that send the monitoring data are now, the timeline of their passes over the area with "now"
// marked (satmonitor.js, orbits.js), each satellite's height, speed and next pass, and a log of the
// computed passes, FIRMS's detections and the alarms. Text is set as text, never as HTML.
"use strict";

const DAY = 86400000;
const LOG_BACK_MS = DAY;
const LOG_AHEAD_MS = 6 * 3600000;
const DRAW_MS = 2000;
const STATE_MS = 30000;
const hourMinute = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", hour: "2-digit", minute: "2-digit" });
const dayTime = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const clockText = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", day: "numeric", month: "short", year: "numeric",
  hour: "2-digit", minute: "2-digit", second: "2-digit" });

async function getJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

// The log's lines, newest first: each satellite's passes from a day back to six hours ahead (the
// future ones marked as computed), FIRMS's detections and the alarms.
function monitoringLog(passes, state, nowMs) {
  const lines = [];
  for (const { item, pass } of passes) {
    const ahead = pass.start > nowMs;
    lines.push({ atMs: pass.start, kind: "computed",
      text: `${item.name} (${item.instrument}) ${ahead ? "passerar" : "passerade"} över ${state.area.name}${ahead ? " (beräknat)" : ""}` });
  }
  for (const fire of state.context?.firms || []) {
    lines.push({ atMs: Date.parse(fire.time_utc), kind: "firms",
      text: `NASA FIRMS: värmedetektion ${fire.instrument} (${fire.satellite}) vid ${fire.latitude.toFixed(3)} N, ${fire.longitude.toFixed(3)} E` });
  }
  for (const alarm of state.alarms) {
    lines.push({ atMs: Date.parse(alarm.created_utc), kind: alarm.candidate.simulated ? "simulated" : "synthetic",
      text: `LARM: ${alarm.candidate.title}${alarm.candidate.simulated ? " (simulerad)" : ""}` });
  }
  return lines.filter((line) => line.atMs >= nowMs - LOG_BACK_MS && line.atMs <= nowMs + LOG_AHEAD_MS)
    .sort((a, b) => b.atMs - a.atMs);
}

async function start() {
  const config = await getJson("/api/config");
  const place = config.area.name;
  document.title = `Satellitbevakning – ${place}`;
  const centre = config.area.centre;
  const note = document.getElementById("monitor-note");
  const data = await getJson("/api/satellites");
  note.textContent = data.available ? `${data.label}. Källa: ${data.source}.${data.note ? ` ${data.note}` : ""}` : data.note;
  if (!data.available) return;
  const lib = await import("/vendor/satellite.js-7.1.0/index.js");
  const monitor = createSatelliteMonitor(document.getElementById("monitor"), centre, (time) => hourMinute.format(time),
    { width: 0, mapHeight: 0, rowHeight: 30, fit: true }, place, String(new Date().getUTCFullYear()));
  const passCache = new Map();
  const passesOn = (item, day) => {
    const key = `${item.norad}|${day}`;
    if (!passCache.has(key)) passCache.set(key, satellitePasses(lib, item, day * DAY, (day + 1) * DAY, centre[0], centre[1]));
    return passCache.get(key);
  };
  let state = null;
  let logKey = null;
  const refreshState = () => getJson("/api/state").then((value) => { state = value; }).catch(() => null);
  await refreshState();
  setInterval(refreshState, STATE_MS);

  const draw = () => {
    const now = new Date();
    const nowMs = now.getTime();
    document.getElementById("monitor-clock").textContent = clockText.format(now);
    const today = Math.floor(nowMs / DAY);
    const items = data.satellites.map((item) => ({
      ...item,
      point: subpoint(lib, item.elements, now),
      track: orbitTrack(lib, item.elements, now, 50, 2),
      passes: [today - 1, today, today + 1].flatMap((day) => passesOn(item, day)),
    })).filter((item) => item.point);
    monitor.draw(items, now);
    const list = document.getElementById("monitor-list");
    list.replaceChildren();
    for (const item of items) {
      const next = item.passes.find((pass) => pass.end > nowMs);
      const pass = !next ? ` · ingen passage över ${place} närmaste dygnet`
        : next.start <= nowMs ? ` · ÖVER ${place.toUpperCase()} NU` : ` · nästa passage över ${place} ${hourMinute.format(new Date(next.start))}`;
      const row = document.createElement("li");
      const swatch = document.createElement("span");
      swatch.className = "monitor-swatch";
      swatch.style.background = monitorColor(item);
      row.append(swatch, `${item.name} (${item.instrument}): ${Math.round(item.point.height_km)} km, `
        + `${item.point.speed_km_s.toFixed(1).replace(".", ",")} km/s${pass}`);
      row.className = next && next.start <= nowMs ? "active" : "";
      list.append(row);
    }
    if (!state) return;
    const passes = items.flatMap((item) => item.passes.map((p) => ({ item, pass: p })));
    const lines = monitoringLog(passes, state, nowMs);
    const key = lines.map((line) => `${line.atMs}${line.text}`).join("|");
    if (key === logKey) return;
    logKey = key;
    const box = document.getElementById("monitor-log-lines");
    box.replaceChildren();
    lines.forEach((line, index) => {
      const row = document.createElement("li");
      row.className = `${line.kind}${index === 0 && line.atMs <= nowMs ? " latest" : ""}`;
      const time = document.createElement("time");
      time.textContent = dayTime.format(new Date(line.atMs));
      row.append(time, ` ${line.text}`);
      box.append(row);
    });
  };
  draw();
  setInterval(draw, DRAW_MS);
  window.addEventListener("resize", () => monitor.redraw());
}

start().catch((error) => { document.getElementById("monitor-note").textContent = `Fel vid start: ${error.message}`; });
