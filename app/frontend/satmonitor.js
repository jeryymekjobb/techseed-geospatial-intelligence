// Satellite monitor: a fixed box on the main screen, always visible wherever the camera is.
// A world map with the orbits of the scenario's year and where the satellites are now, and a timeline of
// their passes over the fire (from orbits.js), with "now" marked. panel.js feeds it every
// tick; the timeline functions are pure so they can be tested in Node.
"use strict";

// By instrument; Terra and Aqua both carry MODIS and get two shades of orange of their own.
const MONITOR_COLORS = {
  Terra: "#ff8c00", Aqua: "#ffb000", MODIS: "#ff8c00", VIIRS: "#ff2a00", OLI: "#4fc3f7", SAR: "#b388ff", MSI: "#69f0ae",
};
const MONITOR_WINDOW = { beforeMs: 3600000, afterMs: 5 * 3600000 };
const MONITOR_SIZE = { width: 400, mapHeight: 200, rowHeight: 18 };
const MARK_COLOR = "#e040fb";
// Natural Earth II as shipped with Cesium: two 256 px tiles, west and east hemisphere.
const WORLD_TILES = ["/vendor/cesium-1.146.0/Assets/Textures/NaturalEarthII/0/0/0.jpg",
  "/vendor/cesium-1.146.0/Assets/Textures/NaturalEarthII/0/1/0.jpg"];

function monitorColor(item) {
  return MONITOR_COLORS[item.firms] || MONITOR_COLORS[item.instrument] || "#d0d0d0";
}

// The track split where the satellite is now: the part already flown and the part ahead
// (orbitTrack() runs from before to after the clock, so the point nearest the satellite is now).
function splitTrack(track, point) {
  if (!track.length) return { past: [], ahead: [] };
  let nearest = 0;
  track.forEach((item, index) => {
    const distance = (lat, lon) => (lat - point.latitude) ** 2 + (lon - point.longitude) ** 2;
    if (distance(item.latitude, item.longitude) < distance(track[nearest].latitude, track[nearest].longitude)) nearest = index;
  });
  return { past: track.slice(0, nearest + 1), ahead: track.slice(nearest) };
}

// Whether a satellite is the one of the detection sequence: by FIRMS name (the fire) or NORAD number (the flood).
function marked(item, mark) {
  return Boolean(mark) && ((Boolean(mark.firms) && item.firms === mark.firms) || (Boolean(mark.norad) && item.norad === mark.norad));
}

// The sun at a moment: where it stands overhead, by the usual low-precision formulas for its
// declination and the equation of time (about 0.1 degree; enough for a world map).
function subsolarPoint(ms) {
  const rad = Math.PI / 180;
  const d = ms / 86400000 + 2440587.5 - 2451545.0;  // days from J2000
  const g = (357.528 + 0.9856003 * d) * rad;
  const lambda = (280.460 + 0.9856474 * d + 1.915 * Math.sin(g) + 0.020 * Math.sin(2 * g)) * rad;
  const epsilon = (23.439 - 0.0000004 * d) * rad;
  const declination = Math.asin(Math.sin(epsilon) * Math.sin(lambda)) / rad;
  const rightAscension = Math.atan2(Math.cos(epsilon) * Math.sin(lambda), Math.cos(lambda)) / rad;
  const sidereal = (18.697374558 + 24.06570982441908 * d) * 15;
  const longitude = ((((rightAscension - sidereal) % 360) + 540) % 360) - 180;
  return { latitude: declination, longitude };
}

// The sun's height above the horizon at a place, in degrees; below 0 it is night.
function solarElevation(latitude, longitude, ms, sun = subsolarPoint(ms)) {
  const rad = Math.PI / 180;
  const cosine = Math.sin(latitude * rad) * Math.sin(sun.latitude * rad)
    + Math.cos(latitude * rad) * Math.cos(sun.latitude * rad) * Math.cos((longitude - sun.longitude) * rad);
  return Math.asin(Math.max(-1, Math.min(1, cosine))) / rad;
}

// How dark the night layer is at a sun height: none by day, full below civil twilight (-6 degrees).
const NIGHT_ALPHA = 0.75;
function nightShade(elevation) {
  return elevation >= 0 ? 0 : elevation <= -6 ? NIGHT_ALPHA : (NIGHT_ALPHA * -elevation) / 6;
}

// The night over the map: a coarse grid of shades, drawn stretched so its edge is soft.
const NIGHT_GRID = { width: 180, height: 90 };
function nightLayer(ms) {
  const sun = subsolarPoint(ms);
  const canvas = document.createElement("canvas");
  canvas.width = NIGHT_GRID.width;
  canvas.height = NIGHT_GRID.height;
  const g = canvas.getContext("2d");
  const image = g.createImageData(NIGHT_GRID.width, NIGHT_GRID.height);
  for (let row = 0; row < NIGHT_GRID.height; row += 1) {
    const latitude = 90 - ((row + 0.5) * 180) / NIGHT_GRID.height;
    for (let col = 0; col < NIGHT_GRID.width; col += 1) {
      const longitude = -180 + ((col + 0.5) * 360) / NIGHT_GRID.width;
      const at = (row * NIGHT_GRID.width + col) * 4;
      image.data[at] = 2;
      image.data[at + 1] = 6;
      image.data[at + 2] = 24;
      image.data[at + 3] = Math.round(255 * nightShade(solarElevation(latitude, longitude, ms, sun)));
    }
  }
  g.putImageData(image, 0, 0);
  return { canvas, sun };
}

// The night at a place across the timeline: [from, to] fractions of the window where the sun is down.
function nightSpans(latitude, longitude, clockMs, window = MONITOR_WINDOW, stepMs = 300000) {
  const start = clockMs - window.beforeMs;
  const span = window.beforeMs + window.afterMs;
  const spans = [];
  let open = null;
  for (let t = start; t <= start + span; t += stepMs) {
    const night = solarElevation(latitude, longitude, t) < 0;
    if (night && open === null) open = (t - start) / span;
    if (!night && open !== null) {
      spans.push([open, (t - start) / span]);
      open = null;
    }
  }
  if (open !== null) spans.push([open, 1]);
  return spans;
}

// Equirectangular: longitude -180..180 and latitude 90..-90 onto the map box.
function mapPoint(longitude, latitude, width, height) {
  return [((longitude + 180) / 360) * width, ((90 - latitude) / 180) * height];
}

// The timeline of one satellite: its passes over the fire inside the window, as fractions
// of the window's width, and whether one is going on now.
function timelineRow(passes, clockMs, window = MONITOR_WINDOW) {
  const start = clockMs - window.beforeMs;
  const end = clockMs + window.afterMs;
  const span = end - start;
  const blocks = passes
    .filter((pass) => pass.end > start && pass.start < end)
    .map((pass) => ({
      from: Math.max(0, (pass.start - start) / span),
      to: Math.min(1, (pass.end - start) / span),
      start: pass.start,
    }));
  const overNow = passes.some((pass) => pass.start <= clockMs && clockMs < pass.end);
  const next = passes.find((pass) => pass.start > clockMs);
  return { blocks, overNow, next: next ? next.start : null, now: window.beforeMs / span };
}

// Where a moment falls on the timeline, as a fraction of the window; null outside it.
function timelineX(atMs, clockMs, window = MONITOR_WINDOW) {
  const x = (atMs - (clockMs - window.beforeMs)) / (window.beforeMs + window.afterMs);
  return x >= 0 && x <= 1 ? x : null;
}

// Hour marks for the timeline axis, as fractions of the window.
function timelineTicks(clockMs, window = MONITOR_WINDOW, stepMs = 3600000) {
  const start = clockMs - window.beforeMs;
  const span = window.beforeMs + window.afterMs;
  const ticks = [];
  for (let t = Math.ceil(start / stepMs) * stepMs; t <= start + span; t += stepMs) ticks.push({ at: t, x: (t - start) / span });
  return ticks;
}

// `size` gives the canvas width, map height and timeline row height; `size.fit` makes the
// monitor fill its container (the stand-alone monitor page) and follow its size.
// setMark() takes the pass of mission control's detection sequence, { atMs, firms, norad }, to
// mark on the timeline and around its satellite; null when no sequence runs.
// `place` names the incident's place in the texts ("branden", "Sundsvall"), `year` the scenario's.
// The night is shaded on the map and on the timeline, and the text says whether it is day or
// night at the incident.
function createSatelliteMonitor(container, fireCentre, formatTime, size = MONITOR_SIZE, place = "branden", year = "2014") {
  const box = document.createElement("section");
  box.className = "sat-monitor";
  box.setAttribute("aria-label", "Satellitbevakning");
  box.innerHTML = `<h2>SATELLITBEVAKNING <small>läge ${year}, beräknat</small></h2><canvas></canvas><div class="sat-monitor-now"></div>`;
  container.append(box);
  const canvas = box.querySelector("canvas");
  const rowsHeight = 22;
  let latest = null;
  let mark = null;
  let night = null;  // { atMs, canvas, sun }: recomputed when the clock has moved five minutes
  const monitor = {
    draw(items, clock) {
      latest = [items, clock];
      const timed = items.filter((item) => item.passes);
      const rows = new Map(timed.map((item) => [item, timelineRow(item.passes, clock.getTime())]));
      const rowHeight = size.rowHeight;
      let width = size.width;
      let mapHeight = size.mapHeight;
      if (size.fit) {
        // Fill the window: the map keeps its 2:1 shape and leaves room for the timeline.
        const free = container.clientHeight - rowsHeight - timed.length * rowHeight - 60;
        width = Math.max(320, Math.min(container.clientWidth - 24, 2 * free));
        mapHeight = Math.round(width / 2);
      }
      const height = mapHeight + rowsHeight + timed.length * rowHeight + 6;
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
      const g = canvas.getContext("2d");
      g.clearRect(0, 0, width, height);
      // The map: world image, orbits, satellites, the fire.
      if (tiles.every((image) => image.complete && image.naturalWidth)) {
        g.drawImage(tiles[0], 0, 0, width / 2, mapHeight);
        g.drawImage(tiles[1], width / 2, 0, width / 2, mapHeight);
        // Darkened so the orbits stand out against the bright world image; the night darker still.
        g.fillStyle = "#00000040";
        g.fillRect(0, 0, width, mapHeight);
      } else {
        g.fillStyle = "#1b2a3a";
        g.fillRect(0, 0, width, mapHeight);
      }
      if (!night || Math.abs(clock.getTime() - night.atMs) >= 300000) night = { atMs: clock.getTime(), ...nightLayer(clock.getTime()) };
      g.imageSmoothingEnabled = true;
      g.drawImage(night.canvas, 0, 0, width, mapHeight);
      // The sun where it stands overhead.
      const [sunX, sunY] = mapPoint(night.sun.longitude, night.sun.latitude, width, mapHeight);
      const sunRadius = size.fit ? 9 : 6;
      g.strokeStyle = "#ffd54a";
      g.fillStyle = "#ffd54a";
      g.lineWidth = 2;
      for (let ray = 0; ray < 8; ray += 1) {
        const angle = (ray * Math.PI) / 4;
        g.beginPath();
        g.moveTo(sunX + Math.cos(angle) * sunRadius * 1.4, sunY + Math.sin(angle) * sunRadius * 1.4);
        g.lineTo(sunX + Math.cos(angle) * sunRadius * 2, sunY + Math.sin(angle) * sunRadius * 2);
        g.stroke();
      }
      g.beginPath();
      g.arc(sunX, sunY, sunRadius, 0, 2 * Math.PI);
      g.fill();
      // Thick enough to be followed from a distance: the stand-alone page is seen across the booth.
      const line = size.fit ? 4 : 2.5;
      const path = (points) => {
        g.beginPath();
        let previous = null;
        for (const point of points) {
          const [x, y] = mapPoint(point.longitude, point.latitude, width, mapHeight);
          // Do not draw a line across the map where the track wraps at 180 degrees.
          if (previous && Math.abs(x - previous[0]) < width / 2) g.lineTo(x, y); else g.moveTo(x, y);
          previous = [x, y];
        }
      };
      g.lineJoin = "round";
      g.lineCap = "round";
      for (const item of items) {
        // The part already flown faint, the part ahead strong, each over a dark edge.
        const { past, ahead } = splitTrack(item.track, item.point);
        for (const [points, alpha] of [[past, 0.35], [ahead, 1]]) {
          g.globalAlpha = alpha;
          path(points);
          g.strokeStyle = "#000000b0";
          g.lineWidth = line + 3;
          g.stroke();
          g.strokeStyle = monitorColor(item);
          g.lineWidth = line;
          g.stroke();
        }
        g.globalAlpha = 1;
      }
      const [fx, fy] = mapPoint(fireCentre[1], fireCentre[0], width, mapHeight);
      g.fillStyle = "#ffd54a";
      g.strokeStyle = "#000";
      g.lineWidth = 2;
      g.beginPath();
      g.arc(fx, fy, size.fit ? 9 : 6, 0, 2 * Math.PI);
      g.fill();
      g.stroke();
      const dot = size.fit ? 9 : 5;
      const font = `${size.fit ? 15 : 11}px system-ui, sans-serif`;
      g.font = `bold ${size.fit ? 20 : 12}px system-ui, sans-serif`;
      for (const item of items) {
        const [x, y] = mapPoint(item.point.longitude, item.point.latitude, width, mapHeight);
        const radius = rows.get(item)?.overNow ? dot + 3 : dot;
        g.fillStyle = monitorColor(item);
        g.beginPath();
        g.arc(x, y, radius, 0, 2 * Math.PI);
        g.fill();
        g.strokeStyle = "#fff";
        g.lineWidth = 2;
        g.stroke();
        if (marked(item, mark)) {
          g.strokeStyle = MARK_COLOR;
          g.lineWidth = 3;
          g.beginPath();
          g.arc(x, y, radius + 6, 0, 2 * Math.PI);
          g.stroke();
        }
        g.strokeStyle = "#000";
        g.lineWidth = 4;
        g.strokeText(item.name, x + radius + 4, y + 6);
        g.fillStyle = "#fff";
        g.fillText(item.name, x + radius + 4, y + 6);
      }
      g.font = font;
      g.lineWidth = 1.5;
      // The timeline of passes over the fire.
      const top = mapHeight + 4;
      const left = 72;
      const span = width - left - 6;
      g.fillStyle = "#202020";
      g.fillRect(0, mapHeight, width, height - mapHeight);
      // The hours of night at the incident, behind the rows: optical satellites see nothing then.
      g.fillStyle = "#0b1220";
      for (const [from, to] of nightSpans(fireCentre[0], fireCentre[1], clock.getTime())) {
        g.fillRect(left + from * span, top + 12, (to - from) * span, height - top - 12);
      }
      g.fillStyle = "#b8b8b8";
      for (const tick of timelineTicks(clock.getTime())) {
        const x = left + tick.x * span;
        g.fillRect(x, top + 14, 1, height - top - 14);
        g.fillText(formatTime(new Date(tick.at)), x - 14, top + 10);
      }
      const overNow = [];
      timed.forEach((item, index) => {
        const row = rows.get(item);
        const y = top + rowsHeight - 4 + index * rowHeight;
        g.fillStyle = marked(item, mark) ? MARK_COLOR : "#e0e0e0";
        g.fillText(item.name, 4, y + 11);
        g.fillStyle = "#3a3a3a";
        g.fillRect(left, y + 6, span, 2);
        g.fillStyle = monitorColor(item);
        for (const block of row.blocks) g.fillRect(left + block.from * span, y + 1, Math.max(3, (block.to - block.from) * span), 12);
        if (row.overNow) overNow.push(`${item.name}${item.instrument ? ` (${item.instrument})` : ""}`);
      });
      const markX = mark ? timelineX(mark.atMs, clock.getTime()) : null;
      if (markX !== null) {
        const x = left + markX * span;
        g.strokeStyle = MARK_COLOR;
        g.lineWidth = 2;
        g.setLineDash([5, 4]);
        g.beginPath();
        g.moveTo(x, top + 12);
        g.lineTo(x, height);
        g.stroke();
        g.setLineDash([]);
        g.lineWidth = 1.5;
        g.fillStyle = MARK_COLOR;
        g.fillText(`UPPTÄCKT ${formatTime(new Date(mark.atMs))}`, Math.min(x + 4, width - 110), top + 24);
      }
      const nowX = left + timelineRow([], clock.getTime()).now * span;
      g.fillStyle = "#ffd54a";
      g.fillRect(nowX - 1, top + 12, 2, height - top - 12);
      const text = box.querySelector(".sat-monitor-now");
      const daylight = solarElevation(fireCentre[0], fireCentre[1], clock.getTime(), night.sun) >= 0 ? "Dag" : "Natt";
      text.textContent = (overNow.length ? `ÖVER ${place.toUpperCase()} NU: ${overNow.join(", ")}` : `Ingen satellit över ${place} just nu`)
        + ` · ${daylight} över ${place}`;
      text.classList.toggle("active", overNow.length > 0);
    },
    redraw() {
      if (latest) monitor.draw(...latest);
    },
    setMark(value) {
      mark = value;
      monitor.redraw();
    },
  };
  const tiles = WORLD_TILES.map((url) => {
    const image = new Image();
    image.onload = () => monitor.redraw();
    image.src = url;
    return image;
  });
  return monitor;
}

if (typeof module !== "undefined") module.exports = { subsolarPoint, solarElevation, nightShade, nightSpans, mapPoint, splitTrack, timelineRow, timelineTicks, timelineX, MONITOR_WINDOW };
