// Meteosat's cloud top height (meteosat_cth.py): which quarter the screens show at a moment of the
// scenario clock and the cells' colours (the log's lines are in satlog.js). Pure, so it can be tested in Node.
"use strict";

// Low tops light, the tops of thunderstorms dark purple; clear cells are not drawn.
const CTH_COLOURS = [[3, "#d7e3f4"], [6, "#9db7e0"], [8, "#6a7fd1"], [10, "#5b3fb0"], [Infinity, "#3b0f70"]];
const CTH_OPACITY = 0.45;

function cthColour(km) {
  return CTH_COLOURS.find(([limit]) => km < limit)[1];
}

// The index of the latest quarter at the clock, or -1 before the first.
function cthQuarterAt(quarters, clockMs) {
  let found = -1;
  (quarters || []).forEach((item, index) => {
    if (Date.parse(item.time_utc) <= clockMs) found = index;
  });
  return found;
}

if (typeof module !== "undefined") module.exports = { CTH_COLOURS, CTH_OPACITY, cthColour, cthQuarterAt };
