// Rain at the scenario clock from SMHI's hourly precipitation (/api/weather): each value is
// the sum of the hour that ends at its time. The municipality's gauges list only hours with
// rain, so an hour without a value counts as dry (an assumption, see the scenario). Pure,
// so it can be tested in Node.
"use strict";

const HOUR_MS = 3600000;

// Millimetres in the hour and the 24 hours up to the clock, and since the start of the data.
function rainSums(observations, clockMs) {
  let hour = 0;
  let day = 0;
  let total = 0;
  for (const observation of observations) {
    const atMs = Date.parse(observation.time_utc);
    if (atMs > clockMs) break;
    const value = observation.precip_mm || 0;
    total += value;
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

if (typeof module !== "undefined") module.exports = { rainSums, hourlyRain, HOUR_MS };
