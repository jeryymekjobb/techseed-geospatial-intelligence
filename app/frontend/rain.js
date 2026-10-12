// Rain at the scenario clock from SMHI's hourly precipitation (/api/weather): each value is
// the sum of the hour that ends at its time. The municipality's gauges list only hours with
// rain, so an hour without a value counts as dry (an assumption, see the scenario). Pure,
// so it can be tested in Node.
"use strict";

const HOUR_MS = 3600000;

// Millimetres in the hour and the 24 hours up to the clock, and since the start (the demo's
// start; without one, the start of the data). An hour counts when it ends after the start.
function rainSums(observations, clockMs, startMs = -Infinity) {
  let hour = 0;
  let day = 0;
  let total = 0;
  for (const observation of observations) {
    const atMs = Date.parse(observation.time_utc);
    if (atMs > clockMs) break;
    const value = observation.precip_mm || 0;
    if (atMs > startMs) total += value;
    if (atMs > clockMs - 24 * HOUR_MS) day += value;
    if (atMs > clockMs - HOUR_MS) hour += value;
  }
  const round = (value) => Math.round(value * 10) / 10;
  return { hour: round(hour), day: round(day), total: round(total) };
}

// One value per playback hour, ending at startMs + 1 h, + 2 h, ..., for the chart.
function hourlyRain(observations, startMs, endMs) {
  const byHour = new Map(observations.map((item) => [Date.parse(item.time_utc), item.precip_mm || 0]));
  const values = [];
  for (let atMs = startMs + HOUR_MS; atMs <= endMs; atMs += HOUR_MS) values.push(byHour.get(atMs) || 0);
  return values;
}

// SMHI's classes of rain by the hour's sum (smhi.se, Kunskapsbanken: Nederbördsintensitet):
// light at most 0.5 mm, moderate 0.5–4 mm, heavy more than 4 mm, a cloudburst at least 50 mm.
// An hourly sum cannot tell showers from steady rain, so the classes of rain are used.
const RAIN_CLASSES = [
  { key: "none", label: "inget regn", below: 0.05, color: "#ffffff", radius: 6 },
  { key: "light", label: "lätt regn", below: 0.5 + 1e-9, color: "#a6cdf2", radius: 9 },
  { key: "moderate", label: "måttligt regn", below: 4 + 1e-9, color: "#3d8fd9", radius: 13 },
  { key: "heavy", label: "kraftigt regn", below: 50, color: "#123f8c", radius: 18 },
  { key: "cloudburst", label: "skyfall", below: Infinity, color: "#7a1fa2", radius: 24 },
];

// SMHI's radar frame for the clock: the latest at or before it (the frames are in time
// order), if it is no older than two steps; none otherwise.
function radarFrameAt(frames, clockMs, stepMinutes) {
  let found = null;
  for (const frame of frames) {
    if (Date.parse(frame.time_utc) > clockMs) break;
    found = frame;
  }
  return found && clockMs - Date.parse(found.time_utc) <= 2 * stepMinutes * 60000 ? found : null;
}

function rainClass(millimetres) {
  return RAIN_CLASSES.find((item) => millimetres < item.below);
}

if (typeof module !== "undefined") module.exports = { rainSums, hourlyRain, rainClass, radarFrameAt, RAIN_CLASSES, HOUR_MS };
