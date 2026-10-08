// SMHI's measured flows and lake levels at the scenario clock (/api/hydro, app/backend/hydro.py):
// the latest value up to the clock, the highest so far in the period, and whether it is above
// the highest measured before. Levels are in cm in the station's height system, shown in metres.
// Pure, so it can be tested in Node.
"use strict";

function hydroAt(observations, clockMs) {
  let latest = null;
  let highest = null;
  for (const item of observations) {
    if (Date.parse(item.time_utc) > clockMs) break;
    latest = item;
    if (!highest || item.value > highest.value) highest = item;
  }
  return { latest, highest };
}

// "30,3 m³/s" for a flow, "54,94 m" for a level.
function hydroText(kind, value) {
  if (value === null || value === undefined) return "–";
  const text = kind === "level" ? (value / 100).toFixed(2) : value.toFixed(1);
  return `${text.replace(".", ",")} ${kind === "level" ? "m" : "m³/s"}`;
}

// Whether the period's highest so far exceeds every value measured before it.
function hydroRecord(station, highest) {
  return Boolean(highest && station.earlier_max && highest.value > station.earlier_max.value);
}

// When a value was measured: a level is SMHI's value for the day, stamped at 00:00 UTC, so only its
// date ("10 feb 2024"); a flow is an hourly mean, given with `formatTime` (local time).
const MONTHS = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"];

function hydroWhen(kind, isoUtc, formatTime) {
  if (kind !== "level") return formatTime(isoUtc);
  const [year, month, day] = isoUtc.slice(0, 10).split("-").map(Number);
  return `${day} ${MONTHS[month - 1]} ${year}`;
}

if (typeof module !== "undefined") module.exports = { hydroAt, hydroText, hydroRecord, hydroWhen };
