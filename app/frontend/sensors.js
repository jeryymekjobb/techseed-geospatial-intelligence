// Texts for the IoT sensors, shared by the main screen (panel.js, the map adapters)
// and mission control (control.js). Real nodes (app/backend/iot.py) are live
// readings in the booth; synthetic sensors are computed - from the 2014 fire and the weather
// (app/backend/sensor_sim.py), or from the 2026 rain (app/backend/flood_sensors.py) - and are
// always marked synthetic.
"use strict";

const SENSOR_KINDS = { temp: "TEMP", water: "WATER", air: "AIR", ntn: "NTN" };
const SYNTHETIC_COLORS = { confirms: "#b3261e", quiet: "#1f5fa8", failed: "#9a9a9a" };

function decimal(value) {
  return String(value).replace(".", ",");
}

function readingValue(reading) {
  if (typeof reading.value === "number") return `${decimal(reading.value)} ${reading.unit || ""}`.trim();
  return reading.value;
}

// One line per booth node: "TECHSEED TEMP booth-temp: 24,7 °C · live", or "simulerad"
// when tools/mqtt_node_sim.py sent it.
function realSensorLine(reading) {
  const kind = SENSOR_KINDS[reading.kind] || reading.kind.toUpperCase();
  const state = !reading.online ? "OFFLINE" : reading.real === false ? "simulerad" : "live";
  return { level: reading.online ? "ok" : "alert", text: `TECHSEED ${kind} ${reading.node}: ${readingValue(reading)} · ${state}` };
}

function connectionText(snapshot) {
  if (snapshot.connection === "connected") return snapshot.sensors.length ? "" : "Ansluten, inga noder har rapporterat ännu.";
  return `IoT: ${snapshot.detail}`;
}

function syntheticState(sensor) {
  if (sensor.status === "failed") return "failed";
  return sensor.confirms ? "confirms" : "quiet";
}

// The flood's overflow sensors (flood_sensors.py), shaped like diwise's Sewer.
function sewerSensorText(sensor, kind) {
  if (sensor.status === "failed") return `${sensor.name}: SENSOR FAILURE (${kind})`;
  const overflow = sensor.overflow === "started" ? `BRÄDDAR sedan ${sensor.overflow_observed_at.slice(11, 16)} UTC` : "ingen bräddning";
  const hours = sensor.overflow_cumulative_h ? `, bräddat ${sensor.overflow_cumulative_h} h totalt` : "";
  const model = sensor.model_depth_m === null ? "" : `; modell ${decimal(Math.round(sensor.model_depth_m * 100) / 100)} m vid 100-årsregn`;
  return `${sensor.name}: nivå ${decimal(sensor.level_m)} m, ${sensor.percent} % fyllt, ${overflow}${hours}${model} (${kind})`;
}

function syntheticSensorText(sensor) {
  const kind = sensor.placed ? "syntetisk, placerad av operatören" : "syntetisk";
  if (sensor.kind === "sewer") return sewerSensorText(sensor, kind);
  if (sensor.status === "failed") return `${sensor.name}: SENSOR FAILURE (${sensor.placed ? kind : "syntetiskt"})`;
  const temp = sensor.temp_c === null ? "temperatur saknas" : `${decimal(sensor.temp_c)} °C`;
  const smoke = sensor.smoke === "DETECTED" ? "Smoke DETECTED" : "ingen rök";
  const distance = sensor.distance_km === null ? "" : sensor.distance_km === 0 ? ", i brandområdet" : `, ${decimal(sensor.distance_km)} km från fronten`;
  return `${sensor.name}: ${temp}, ${smoke}${distance} (${kind})`;
}

function syntheticSensorLine(sensor) {
  const state = syntheticState(sensor);
  return { level: state === "quiet" ? "ok" : "alert", text: syntheticSensorText(sensor) };
}

function confirmsText(result) {
  if (result.disabled) return "IoT avstängt från mission control";
  return `IoT bekräftar ${result.confirms}/${result.operating} (syntetiska sensorer)`;
}

if (typeof module !== "undefined") {
  module.exports = { SYNTHETIC_COLORS, realSensorLine, connectionText, syntheticState, syntheticSensorText, syntheticSensorLine, confirmsText };
}
