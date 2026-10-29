// SWOT's water surface heights (swot.py): each lake and reach coloured by how much it rose from the
// passes before the playback, from SWOT's pass on. An uncertain measurement is drawn dashed, its label
// ends in "?" and its tooltip says why. Pure, so it can be tested in Node.
"use strict";

// From a fall (grey) through small rises (light blue) to a metre and more (dark blue).
const SWOT_STEPS = [[0, "#9ca3af"], [0.25, "#bfdbfe"], [0.5, "#60a5fa"], [1, "#2563eb"], [Infinity, "#1e3a8a"]];
// Lakes this large and every reach carry their change as a label on the map.
const SWOT_LABEL_KM2 = 1;

function swotColour(change) {
  return SWOT_STEPS.find(([limit]) => change < limit)[1];
}

function swotMetres(value) {
  return `${value > 0 ? "+" : value < 0 ? "−" : "±"}${Math.abs(value).toFixed(2).replace(".", ",")} m`;
}

function swotLabel(item) {
  return `${swotMetres(item.change_m)}${item.uncertain ? "?" : ""}`;
}

function swotLabelled(item) {
  return item.kind === "river" || (item.area_km2 || 0) >= SWOT_LABEL_KM2;
}

const SWOT_QUALITY = { 0: "god", 1: "osäker (suspect)", 2: "försämrad (degraded)", 3: "dålig (bad)" };

function swotTooltip(item) {
  const name = item.name || (item.kind === "lake" ? "Sjö utan namn" : "Älvsträcka");
  const sigma = item.wse_u_m === null || item.wse_u_m === undefined ? "" : ` (±${item.wse_u_m.toFixed(2).replace(".", ",")} m)`;
  const lines = [`<strong>${name}</strong>: ${swotMetres(item.change_m)} sedan ${item.baseline.length === 1 ? "mätningen" : "mätningarna"} före regnet${sigma}`,
                 `Kvalitet: ${SWOT_QUALITY[item.quality] ?? "okänd"}${item.uncertain ? " – osäker mätning" : ""}`];
  return [...lines, ...item.uncertainty_notes].join("<br>");
}

// Whether the clock has reached SWOT's pass.
function swotShown(info, clockMs) {
  return Boolean(info) && clockMs >= Date.parse(info.pass_utc);
}

if (typeof module !== "undefined") module.exports = { swotColour, swotMetres, swotLabel, swotLabelled, swotTooltip, swotShown, SWOT_STEPS };
