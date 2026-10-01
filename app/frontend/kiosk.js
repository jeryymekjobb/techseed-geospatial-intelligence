// URL options for kiosk use and recordings: ?show=all, ?at=<ISO time>,
// ?autoplay=1, ?speed=<simulated seconds per second>, ?horizon=<3|6|12|24>.
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
  return `${Math.round(seconds / 60)} minuter/s`;
}

if (typeof module !== "undefined") module.exports = { parseKioskOptions, speedLabel };
