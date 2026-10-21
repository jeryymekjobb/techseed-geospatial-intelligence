// URL options for kiosk use and recordings: ?show=all, ?at=<ISO time>,
// ?autoplay=1, ?speed=<simulated seconds per second>, ?horizon=<3|6|12|24>; and the main screen's
// switch between the 2D map and the 3D globe from mission control (viewPage).
"use strict";

const KIOSK_HORIZONS = ["3", "6", "12", "24"];
const KIOSK_SPEED_LIMITS = [60, 4 * 86400];

function parseKioskOptions(search) {
  const options = new URLSearchParams(search);
  const at = options.get("at") ? new Date(options.get("at")) : null;
  const speed = Number(options.get("speed"));
  const horizon = options.get("horizon");
  return {
    showAll: options.get("show") === "all",
    at: at && !Number.isNaN(at.getTime()) ? at : null,
    autoplay: options.get("autoplay") === "1",
    speed: Number.isFinite(speed) && speed >= KIOSK_SPEED_LIMITS[0] && speed <= KIOSK_SPEED_LIMITS[1] ? speed : null,
    horizon: KIOSK_HORIZONS.includes(horizon) ? horizon : null,
  };
}

function speedLabel(seconds) {
  if (seconds % 86400 === 0) return `${seconds / 86400} dygn/s`;
  if (seconds % 3600 === 0) return `${seconds / 3600} ${seconds === 3600 ? "timme" : "timmar"}/s`;
  const minutes = Math.round(seconds / 60);
  return `${minutes} ${minutes === 1 ? "minut" : "minuter"}/s`;
}

// The page a display-only main screen goes to when mission control's view (the status's `view`)
// differs from its own, with its own options but without ?at= (which would seek again); null when it
// stays: the same view, or a window with ?controls=1 that someone works in.
function viewPage(dimension, wanted, search) {
  const options = new URLSearchParams(search);
  if (!wanted || wanted === dimension || options.get("controls") === "1") return null;
  options.delete("at");
  const query = options.toString();
  return `${wanted === "2d" ? "/" : "/3d.html"}${query ? `?${query}` : ""}`;
}

if (typeof module !== "undefined") module.exports = { parseKioskOptions, speedLabel, viewPage };
