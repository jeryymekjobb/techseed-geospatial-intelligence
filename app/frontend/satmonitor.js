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
// setMark() takes the pass of mission control's detection sequence, { atMs, firms }, to
// mark on the timeline and around its satellite; null when no sequence runs.
// `place` names the incident's place in the texts ("branden", "Sundsvall"), `year` the scenario's.
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
        // Darkened so the orbits stand out against the bright world image.
        g.fillStyle = "#00000080";
        g.fillRect(0, 0, width, mapHeight);
      } else {
        g.fillStyle = "#1b2a3a";
        g.fillRect(0, 0, width, mapHeight);
      }
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
        if (mark && item.firms === mark.firms) {
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
        g.fillStyle = mark && item.firms === mark.firms ? MARK_COLOR : "#e0e0e0";
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
      text.textContent = overNow.length ? `ÖVER ${place.toUpperCase()} NU: ${overNow.join(", ")}` : `Ingen satellit över ${place} just nu`;
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

if (typeof module !== "undefined") module.exports = { mapPoint, splitTrack, timelineRow, timelineTicks, timelineX, MONITOR_WINDOW };
