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

// Whether the period's highest so far exceeds every value measured before it; given the clock and the
// station's record_hold_days, also whether it was measured at most that many days before (the map's label).
function hydroRecord(station, highest, clockMs) {
  if (!highest || !station.earlier_max || highest.value <= station.earlier_max.value) return false;
  const hold = station.record_hold_days;
  if (clockMs === undefined || hold === null || hold === undefined) return true;
  return clockMs - Date.parse(highest.time_utc) <= hold * 86_400_000;
}

// When a value was measured: a value by the day (`daily`, a level unless said otherwise) is SMHI's value
// for the day, stamped at 00:00 UTC, so only its date ("10 feb 2024"); an hourly value is given with
// `formatTime` (local time).
const MONTHS = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"];

function hydroWhen(kind, isoUtc, formatTime, daily = kind === "level") {
  if (!daily) return formatTime(isoUtc);
  const [year, month, day] = isoUtc.slice(0, 10).split("-").map(Number);
  return `${day} ${MONTHS[month - 1]} ${year}`;
}

// The longest return period of SMHI's flow statistics (HQ2-HQ50, a modelled station's `statistics`) that a
// flow reaches: 5 for a flow at or above HQ5 but below HQ10, null below HQ2 or without statistics.
function hydroReturnPeriod(statistics, value) {
  if (!statistics || value === null || value === undefined) return null;
  let years = null;
  for (const period of [2, 5, 10, 25, 50]) {
    const limit = statistics[`HQ${period}`];
    if (limit !== undefined && value >= limit) years = period;
  }
  return years;
}

// The highest value in the `hours` after the clock (a sea level measured afterwards, not a forecast), or null.
function hydroAhead(observations, clockMs, hours) {
  const until = clockMs + hours * 3_600_000;
  let highest = null;
  for (const item of observations) {
    const ms = Date.parse(item.time_utc);
    if (ms > clockMs && ms <= until && (!highest || item.value > highest.value)) highest = item;
  }
  return highest;
}

if (typeof module !== "undefined") module.exports = { hydroAt, hydroText, hydroRecord, hydroWhen, hydroReturnPeriod, hydroAhead };
