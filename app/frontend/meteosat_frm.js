// LSA SAF's fire risk (meteosat_frm.py): which day's map the screens show at a moment of the
// scenario clock, and how. Pure, so it can be tested in Node.
"use strict";

// The risk classes 1 low to 5 extreme, green to purple as on fire danger maps.
const FRM_COLOURS = { 1: "#43a047", 2: "#fdd835", 3: "#fb8c00", 4: "#d32f2f", 5: "#6a1b9a" };
const FRM_OPACITY = 0.35;

// The index of the latest day whose map is valid (12 UTC) at the clock, or -1 before the first.
function frmDayAt(days, clockMs) {
  let found = -1;
  (days || []).forEach((day, index) => {
    if (Date.parse(day.valid_utc) <= clockMs) found = index;
  });
  return found;
}

// The panel's line for the day at the fire; `when` is its time of validity as the screens write it.
function frmText(day, names, when) {
  if (!day || day.risk === null || day.risk === undefined) return "ingen karta ännu";
  const fwi = day.fwi === null ? "" : `, FWI ${Math.round(day.fwi)}`;
  return `${names[day.risk] || day.risk}${fwi} (gäller ${when}; Meteosat och ERA5)`;
}

// The map's cells for one day: [{ south, west, north, east, risk, fwi }], without the missing ones.
function frmCells(info, index) {
  const day = info.days[index];
  if (!day) return [];
  const half = info.cell_deg / 2;
  const cells = [];
  info.latitudes.forEach((lat, row) => info.longitudes.forEach((lon, column) => {
    const risk = day.risk[row][column];
    if (risk === null || risk === undefined) return;
    cells.push({ south: lat - half, north: lat + half, west: lon - half, east: lon + half, risk, fwi: day.fwi[row][column] });
  }));
  return cells;
}

if (typeof module !== "undefined") module.exports = { FRM_COLOURS, FRM_OPACITY, frmDayAt, frmText, frmCells };
