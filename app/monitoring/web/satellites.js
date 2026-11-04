// The satellite monitor of the monitoring (app/monitoring/service.py), in a window of its own as the
// demos' (app/frontend/monitor.js), but live: the world map with the orbits and where the satellites
// that send the monitoring data are now, the timeline of their passes over the area with "now"
// marked (satmonitor.js, orbits.js), and each satellite's height, speed and next pass; what was
// detected and the alarms are in mission control (control.js). Text is set as text, never as HTML.
"use strict";

const DAY = 86400000;
const DRAW_MS = 2000;
const hourMinute = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", hour: "2-digit", minute: "2-digit" });
const clockText = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", day: "numeric", month: "short", year: "numeric",
  hour: "2-digit", minute: "2-digit", second: "2-digit" });

async function getJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
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
  const draw = () => {
    const now = new Date();
    const nowMs = now.getTime();
    document.getElementById("monitor-clock").textContent = clockText.format(now);
    const today = Math.floor(nowMs / DAY);
    const items = data.satellites.map((item) => ({
      ...item,
      point: subpoint(lib, item.elements, now),
      track: orbitTrack(lib, item.elements, now, 50, 2),
      // A geostationary satellite (Meteosat) always sees the area, so it has no passes.
      passes: item.geostationary ? null : [today - 1, today, today + 1].flatMap((day) => passesOn(item, day)),
    })).filter((item) => item.point);
    monitor.draw(items, now);
    const list = document.getElementById("monitor-list");
    list.replaceChildren();
    for (const item of items) {
      const next = item.passes?.find((pass) => pass.end > nowMs);
      const pass = item.geostationary ? ` · geostationär, ser ${place} hela tiden` : !next ? ` · ingen passage över ${place} närmaste dygnet`
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
  };
  draw();
  setInterval(draw, DRAW_MS);
  window.addEventListener("resize", () => monitor.redraw());
}

start().catch((error) => { document.getElementById("monitor-note").textContent = `Fel vid start: ${error.message}`; });
