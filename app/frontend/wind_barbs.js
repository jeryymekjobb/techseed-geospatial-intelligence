// Wind arrows with barbs: a thin arrow pointing where the wind blows to, with
// strokes at its base for the speed (short 2.5 m/s, long 5 m/s, triangle 25 m/s).
"use strict";

const WIND_BARB = { short: 2.5, long: 5, pennant: 25, calm: 1 };

function windBarbCounts(speed) {
  const steps = Math.round(speed / WIND_BARB.short);
  return { pennants: Math.floor(steps / 10), longs: Math.floor((steps % 10) / 2), shorts: steps % 2 };
}

// SVG for an arrow pointing up (north); rotate by the direction the wind blows to.
function windBarbSvg(speed) {
  if (speed < WIND_BARB.calm) {
    return '<svg viewBox="-20 -20 40 40" class="barb"><circle r="4" class="halo"></circle><circle r="4"></circle></svg>';
  }
  const { pennants, longs, shorts } = windBarbCounts(speed);
  const parts = ["M0,15 L0,-15", "M-3,-9 L0,-15 L3,-9"];
  const fills = [];
  let y = 15;
  for (let index = 0; index < pennants; index += 1) {
    fills.push(`M0,${y} L9,${y - 2} L0,${y - 5} Z`);
    y -= 6;
  }
  for (let index = 0; index < longs; index += 1) {
    parts.push(`M0,${y} L9,${y + 4}`);
    y -= 4;
  }
  for (let index = 0; index < shorts; index += 1) {
    // A lone short stroke sits a little in from the end, as on weather maps.
    if (longs === 0 && pennants === 0) y -= 3;
    parts.push(`M0,${y} L4.5,${y + 2}`);
    y -= 4;
  }
  const path = parts.join(" ");
  const fill = fills.join(" ");
  return `<svg viewBox="-20 -20 40 40" class="barb"><path d="${path}" class="halo"></path>`
    + (fill ? `<path d="${fill}" class="halo"></path><path d="${fill}" class="pennant"></path>` : "")
    + `<path d="${path}"></path></svg>`;
}

if (typeof module !== "undefined") module.exports = { windBarbCounts, windBarbSvg };

// A lightning bolt as SVG, filled with `colour`, edged dark, for SMHI's observed lightning on both maps.
function lightningSvg(colour, size) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 32" width="${size}" height="${Math.round(size * 4 / 3)}">`
    + `<path d="M14 1 L3 18 H11 L8 31 L21 12 H13 Z" fill="${colour}" stroke="#3a2a00" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
}
// A flash's time on the maps, in Swedish time.
const lightningTimes = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });
function formatLightningTime(utc) {
  return `${lightningTimes.format(new Date(utc))} svensk tid`;
}
// The flashes near the incident that stay on the map.
const LIGHTNING_NEAR_COLOUR = "#e0301e";

// SMHI's observed lightning on both maps: yellow in its first ten minutes, orange after half an hour.
function lightningColour(ageMinutes) {
  return ageMinutes < 10 ? "#ffe600" : ageMinutes < 30 ? "#ffb300" : "#ff7a00";
}

if (typeof module !== "undefined") module.exports = { ...(module.exports || {}), lightningColour, lightningSvg };
