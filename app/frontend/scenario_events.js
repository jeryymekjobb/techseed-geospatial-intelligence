// Texts for the mission-control events, shared by the main screen (panel.js) and
// mission control (control.js). The kinds match EVENT_KINDS in
// app/backend/scenario_engine.py. Every event is triggered by the operator, so
// the texts say the event is synthetic; only the satellite data behind the map is real.
"use strict";

const EVENT_TEXTS = {
  satellite_detection: { title: "SATELLITE DETECTION", detail: "Syntetisk händelse utlöst från mission control." },
  sensor_failure: { title: "SENSOR FAILURE", detail: "Syntetiskt sensorbortfall." },
  satcom_failure: { title: "SATCOM FAILURE", detail: "Simulerat avbrott: satellitdata når inte markstationen." },
  satcom_restore: { title: "SATCOM RESTORED", detail: "Simulerat avbrott slut: satellitlänken är uppe igen." },
  road_closed: { title: "ROAD CLOSED", detail: "Syntetisk händelse – inga riktiga vägdata om avstängning." },
  power_failure: { title: "POWER FAILURE", detail: "Syntetisk händelse – elnätet finns inte i kartdata." },
  plus60: { title: "+60 MIN", detail: "Prognosen visas med kortaste horisonten – modell med stor osäkerhet." },
  god_view: { title: "GOD VIEW", detail: "Kameran visar hela lägesbilden." },
};

function eventText(event) {
  const text = EVENT_TEXTS[event.kind] || { title: event.kind.toUpperCase(), detail: "" };
  const target = event.target ? ` ${event.target}` : "";
  return { title: `${text.title}${target}`, detail: text.detail };
}

// Toggles say whether they were switched on or off; `status` is the state after the event.
function eventBanner(event, status) {
  const text = eventText(event);
  if (event.kind === "plus60" && !status.plus60) return { title: "+60 MIN AV", detail: "Prognosen visas med vald horisont igen." };
  if (event.kind === "god_view" && !status.god_view) return { title: "RETURN TO INCIDENT", detail: "Kameran går tillbaka till branden." };
  return text;
}

// One line per active deviation, for the status lists on both screens.
function statusLines(status) {
  const lines = [];
  if (!status.satcom_up) lines.push({ level: "alert", text: "SATELLITE DATA UNAVAILABLE (simulerat avbrott)" });
  for (const sensor of status.failed_sensors) lines.push({ level: "alert", text: `Sensorbortfall: ${sensor ?? "sensor"} (syntetiskt)` });
  for (const road of status.closed_roads) lines.push({ level: "alert", text: `Väg avstängd: ${road ?? "väg"} (syntetiskt)` });
  if (status.power_failure) lines.push({ level: "alert", text: "Strömavbrott (syntetiskt)" });
  if (status.plus60) lines.push({ level: "info", text: "+60 MIN: prognos med kortaste horisonten" });
  if (status.god_view) lines.push({ level: "info", text: "GOD VIEW" });
  return lines;
}

// A SATCOM outage (app/backend/server.py): the queue while it lasts, the SYNC when it ends.
function queueText(queue) {
  if (!queue.since_utc) return "";
  return `EDGE PROCESSING – ${queue.queued} detektioner köade sedan ${queue.since_utc.slice(11, 16)} UTC (simulerat avbrott)`;
}

function syncBanner(summary) {
  return {
    title: `SYNC – ${summary.passes.length} NEW EVENTS`,
    detail: "Satellitpassager under det simulerade avbrottet, ur verkliga FIRMS-data 2014.",
  };
}

function syncLines(summary) {
  const lines = summary.passes.map((item) => ({
    level: "info", text: `${item.time_utc.slice(5, 16).replace("T", " ")} UTC – ${item.detections} nya detektioner (${item.instruments.join(", ")})`,
  }));
  if (summary.area_increase_pct !== null) lines.push({ level: "info", text: `Brandfrontens yta ökade ${summary.area_increase_pct} %` });
  if (!lines.length) lines.push({ level: "ok", text: "Inga satellitpassager under avbrottet." });
  return lines;
}

if (typeof module !== "undefined") module.exports = { EVENT_TEXTS, eventText, eventBanner, statusLines, queueText, syncBanner, syncLines };
