// The colours of Sundsvall municipality's cloudburst model, largest water depth
// (SundsvallsKommun:30-, 100- and 500-ar_maxvattendjup), as its WMS legend gives them
// (GetLegendGraphic, checked 2026-10-07). Pure, so it can be tested in Node.
"use strict";

const DEPTH_CLASSES = [
  { color: "#17DB2E", text: "0,1–0,2 m" },
  { color: "#80FF01", text: "0,2–0,3 m" },
  { color: "#FBFF01", text: "0,3–0,4 m" },
  { color: "#FFC001", text: "0,4–0,5 m" },
  { color: "#FF7C01", text: "0,5–1 m" },
  { color: "#DE1E22", text: "1–2 m" },
  { color: "#680404", text: "mer än 2 m" },
];

// Whether the depth legend belongs on screen: a depth layer is shown.
function depthLegendShown(visibleLayers) {
  return visibleLayers.some((name) => name.endsWith("maxvattendjup"));
}

// The scenario's period in words for the flood maps' note: "augusti 2026", "januari–februari 2024".
// The periods are whole UTC days, so the months are counted in UTC.
function floodPeriodText(startUtc, endUtc) {
  const month = new Intl.DateTimeFormat("sv-SE", { timeZone: "UTC", month: "long" });
  const year = new Intl.DateTimeFormat("sv-SE", { timeZone: "UTC", year: "numeric" });
  const start = new Date(startUtc);
  const end = new Date(Date.parse(endUtc) - 1);  // the period ends just before its end time
  const [startMonth, endMonth, startYear, endYear] = [month.format(start), month.format(end), year.format(start), year.format(end)];
  if (startYear !== endYear) return `${startMonth} ${startYear}–${endMonth} ${endYear}`;
  return startMonth === endMonth ? `${startMonth} ${startYear}` : `${startMonth}–${endMonth} ${startYear}`;
}

if (typeof module !== "undefined") module.exports = { DEPTH_CLASSES, depthLegendShown, floodPeriodText };
