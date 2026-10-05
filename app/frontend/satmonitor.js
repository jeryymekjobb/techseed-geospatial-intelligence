// Satellite monitor: a fixed box on the main screen, always visible wherever the camera is.
// A world map with the 2014 orbits and where the satellites are now, and a timeline of
// their passes over the fire (from orbits.js), with "now" marked. panel.js feeds it every
// tick; the timeline functions are pure so they can be tested in Node.
"use strict";

const MONITOR_COLORS = { MODIS: "#ff8c00", VIIRS: "#ff2a00", OLI: "#4fc3f7" };
const MONITOR_WINDOW = { beforeMs: 3600000, afterMs: 5 * 3600000 };
const MONITOR_SIZE = { width: 400, mapHeight: 200, rowHeight: 18 };
// Natural Earth II as shipped with Cesium: two 256 px tiles, west and east hemisphere.
const WORLD_TILES = ["/vendor/cesium-1.146.0/Assets/Textures/NaturalEarthII/0/0/0.jpg",
  "/vendor/cesium-1.146.0/Assets/Textures/NaturalEarthII/0/1/0.jpg"];

function monitorColor(item) {
  return MONITOR_COLORS[item.instrument] || "#d0d0d0";
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

// Hour marks for the timeline axis, as fractions of the window.
function timelineTicks(clockMs, window = MONITOR_WINDOW, stepMs = 3600000) {
  const start = clockMs - window.beforeMs;
  const span = window.beforeMs + window.afterMs;
  const ticks = [];
  for (let t = Math.ceil(start / stepMs) * stepMs; t <= start + span; t += stepMs) ticks.push({ at: t, x: (t - start) / span });
  return ticks;
}

function createSatelliteMonitor(container, fireCentre, formatTime) {
  const box = document.createElement("section");
  box.className = "sat-monitor";
  box.setAttribute("aria-label", "Satellitbevakning");
  box.innerHTML = '<h2>SATELLITBEVAKNING <small>läge 2014, beräknat</small></h2><canvas></canvas><div class="sat-monitor-now"></div>';
  container.append(box);
  const canvas = box.querySelector("canvas");
  const rowsHeight = 22;
  let latest = null;
  const monitor = {
    draw(items, clock) {
      latest = [items, clock];
      const timed = items.filter((item) => item.passes);
      const rows = new Map(timed.map((item) => [item, timelineRow(item.passes, clock.getTime())]));
      const width = MONITOR_SIZE.width;
      const height = MONITOR_SIZE.mapHeight + rowsHeight + timed.length * MONITOR_SIZE.rowHeight + 6;
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
      const g = canvas.getContext("2d");
      const mapHeight = MONITOR_SIZE.mapHeight;
      g.clearRect(0, 0, width, height);
      // The map: world image, orbits, satellites, the fire.
      if (tiles.every((image) => image.complete && image.naturalWidth)) {
        g.drawImage(tiles[0], 0, 0, width / 2, mapHeight);
        g.drawImage(tiles[1], width / 2, 0, width / 2, mapHeight);
      } else {
        g.fillStyle = "#1b2a3a";
        g.fillRect(0, 0, width, mapHeight);
      }
      for (const item of items) {
        g.strokeStyle = monitorColor(item);
        g.lineWidth = 1.5;
        g.beginPath();
        let previous = null;
        for (const point of item.track) {
          const [x, y] = mapPoint(point.longitude, point.latitude, width, mapHeight);
          // Do not draw a line across the map where the track wraps at 180 degrees.
          if (previous && Math.abs(x - previous[0]) < width / 2) g.lineTo(x, y); else g.moveTo(x, y);
          previous = [x, y];
        }
        g.stroke();
      }
      const [fx, fy] = mapPoint(fireCentre[1], fireCentre[0], width, mapHeight);
      g.fillStyle = "#ffd54a";
      g.strokeStyle = "#000";
      g.beginPath();
      g.arc(fx, fy, 5, 0, 2 * Math.PI);
      g.fill();
      g.stroke();
      g.font = "11px system-ui, sans-serif";
      for (const item of items) {
        const [x, y] = mapPoint(item.point.longitude, item.point.latitude, width, mapHeight);
        g.fillStyle = monitorColor(item);
        g.beginPath();
        g.arc(x, y, rows.get(item)?.overNow ? 6 : 4, 0, 2 * Math.PI);
        g.fill();
        g.strokeStyle = "#fff";
        g.stroke();
        g.fillStyle = "#fff";
        g.fillText(item.name, x + 7, y + 4);
      }
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
        const y = top + rowsHeight - 4 + index * MONITOR_SIZE.rowHeight;
        g.fillStyle = "#e0e0e0";
        g.fillText(item.name, 4, y + 11);
        g.fillStyle = "#3a3a3a";
        g.fillRect(left, y + 6, span, 2);
        g.fillStyle = monitorColor(item);
        for (const block of row.blocks) g.fillRect(left + block.from * span, y + 1, Math.max(3, (block.to - block.from) * span), 12);
        if (row.overNow) overNow.push(`${item.name}${item.instrument ? ` (${item.instrument})` : ""}`);
      });
      const nowX = left + timelineRow([], clock.getTime()).now * span;
      g.fillStyle = "#ffd54a";
      g.fillRect(nowX - 1, top + 12, 2, height - top - 12);
      const text = box.querySelector(".sat-monitor-now");
      text.textContent = overNow.length ? `ÖVER BRANDEN NU: ${overNow.join(", ")}` : "Ingen satellit över branden just nu";
      text.classList.toggle("active", overNow.length > 0);
    },
    redraw() {
      if (latest) monitor.draw(...latest);
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

if (typeof module !== "undefined") module.exports = { mapPoint, timelineRow, timelineTicks, MONITOR_WINDOW };
