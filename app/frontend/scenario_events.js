// Texts for the mission-control events, shared by the main screen (panel.js) and
// mission control (control.js). The kinds match EVENT_KINDS in
// app/backend/scenario_engine.py. Every event is triggered by the operator, so
// the texts say the event is synthetic; only the satellite data behind the map is real.
"use strict";

const EVENT_TEXTS = {
  satellite_detection: { title: "SATELLITE DETECTION", detail: "Upptäckten bygger på nästa verkliga FIRMS-passage; varje steg märks verkligt eller syntetiskt." },
  sensor_failure: { title: "SENSOR FAILURE", detail: "Syntetiskt sensorbortfall." },
  satcom_failure: { title: "SATCOM FAILURE", detail: "Simulerat avbrott: satellitdata når inte markstationen." },
  satcom_restore: { title: "SATCOM RESTORED", detail: "Simulerat avbrott slut: satellitlänken är uppe igen." },
  road_closed: { title: "ROAD CLOSED", detail: "Syntetisk händelse – inga riktiga vägdata om avstängning." },
  power_failure: { title: "POWER FAILURE", detail: "Syntetisk händelse – elnätet finns inte i kartdata." },
  plus60: { title: "+60 MIN", detail: "Prognosen visas med kortaste horisonten – modell med stor osäkerhet." },
  god_view: { title: "GOD VIEW", detail: "Kameran visar hela lägesbilden." },
  iot: { title: "IOT PÅ", detail: "Sensorerna räknas med i lägesbilden och bedömningen igen." },
  space_view: { title: "SPACE VIEW", detail: "Satelliternas läge {year}, beräknat ur banelement." },
  filter: { title: "FILTER", detail: "Ett lager visas eller döljs på kartan." },
  place_sensor: { title: "IOT-SENSOR PLACERAD", detail: "Syntetisk sensor, placerad av operatören – värdena beräknas ur brandfronten och vädret." },
};

// GOD VIEW's filter: the categories in the demo, and those the one-pager names but the demo lacks.
const FILTER_CATEGORIES = [
  { id: "space", label: "Space" }, { id: "iot", label: "IoT" },
  { id: "infrastructure", label: "Infrastructure" }, { id: "weather", label: "Weather" },
  { id: "maritime", label: "Maritime", missing: true }, { id: "aviation", label: "Aviation", missing: true },
  { id: "emergency", label: "Emergency", missing: true },
];
const MISSING_NOTE = "ingår inte i demon";

function eventText(event) {
  const text = EVENT_TEXTS[event.kind] || { title: event.kind.toUpperCase(), detail: "" };
  // A filter names its category as on the buttons ("FILTER SPACE"); other targets are ids such as sensor-17.
  const category = event.kind === "filter" ? FILTER_CATEGORIES.find((item) => item.id === event.target) : null;
  // A placed sensor is named P1, P2 … as on the map; its id is placed-1, placed-2 …
  const placed = event.kind === "place_sensor" && event.target ? ` P${event.target.replace("placed-", "")}` : null;
  const target = category ? ` ${category.label.toUpperCase()}` : placed ?? (event.target ? ` ${event.target}` : "");
  // {year} is the scenario's year, the year on the scenario clock when the event came.
  return { title: `${text.title}${target}`, detail: text.detail.replace("{year}", (event.clock_utc || "").slice(0, 4)) };
}

// Toggles say whether they were switched on or off; `status` is the state after the event.
function eventBanner(event, status) {
  const text = eventText(event);
  if (event.kind === "plus60" && !status.plus60) return { title: "+60 MIN AV", detail: "Prognosen visas med vald horisont igen." };
  if (event.kind === "god_view" && !status.god_view) return { title: "RETURN TO INCIDENT", detail: "Kameran går tillbaka till branden." };
  if (event.kind === "iot" && !status.iot) return { title: "IOT AV", detail: "Inga sensorer i lägesbilden eller bedömningen." };
  if (event.kind === "space_view" && !status.space_view) return { title: "RETURN TO INCIDENT", detail: "Kameran går tillbaka till branden." };
  if (event.kind === "filter") {
    const hidden = status.hidden_layers.includes(event.target);
    return { title: text.title, detail: hidden ? "Lagret döljs." : "Lagret visas." };
  }
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
  if (status.iot === false) lines.push({ level: "alert", text: "IoT avstängt – inga sensorer räknas" });
  const placed = status.placed_sensors || [];
  if (placed.length) lines.push({ level: "info", text: `Placerade sensorer: ${placed.map((item) => item.name.replace("Sensor ", "")).join(", ")} (syntetiska)` });
  if (status.god_view) lines.push({ level: "info", text: "GOD VIEW" });
  if (status.space_view) lines.push({ level: "info", text: "SPACE VIEW" });
  const hidden = FILTER_CATEGORIES.filter((item) => status.hidden_layers.includes(item.id)).map((item) => item.label);
  if (hidden.length) lines.push({ level: "info", text: `Dolda lager: ${hidden.join(", ")}` });
  return lines;
}

// A SATCOM outage (app/backend/server.py): the queue while it lasts, the SYNC when it ends.
// The unit of the queue in the singular, for one held-back item.
const QUEUE_SINGULAR = { detektioner: "detektion", satellitbilder: "satellitbild" };

function queueText(queue) {
  if (!queue.since_utc) return "";
  const unit = queue.unit || "detektioner";
  return `EDGE PROCESSING – ${queue.queued} ${queue.queued === 1 ? QUEUE_SINGULAR[unit] || unit : unit} köade `
    + `sedan ${queue.since_utc.slice(11, 16)} UTC (simulerat avbrott)`;
}

function syncBanner(summary) {
  return {
    title: `SYNC – ${summary.passes.length} NEW EVENTS`,
    detail: `Satellitpassager under det simulerade avbrottet, ur verkliga FIRMS-data ${(summary.passes[0]?.time_utc || "").slice(0, 4)}.`.replace(" .", "."),
  };
}

function syncLines(summary) {
  // The fire's passes count detections; the flood's name their image (assessment.py, flood_assessment.py).
  const lines = summary.passes.map((item) => ({
    level: "info", text: `${item.time_utc.slice(5, 16).replace("T", " ")} UTC – `
      + (item.text || `${item.detections} nya detektioner (${item.instruments.join(", ")})`),
  }));
  if (summary.area_increase_pct !== null) lines.push({ level: "info", text: `Brandfrontens yta ökade ${summary.area_increase_pct} %` });
  if (!lines.length) lines.push({ level: "ok", text: "Inga satellitpassager under avbrottet." });
  return lines;
}

// The detection sequence (DETECTION_STEPS in app/backend/scenario_engine.py): each step
// says whether it rests on real 2014 data or is the story's synthetic part - the
// satellites did not analyse their images on board in 2014.
const DETECTION_STEPS = [
  { name: "acquired", title: "Bild tagen", real: true },
  { name: "anomaly", title: "Anomali upptäckt ombord", real: false },
  { name: "downlink", title: "Nedlänk till markstation", real: false },
  { name: "zoom", title: "Zoom till {place}", real: true },
  { name: "iot", title: "IoT på marken", real: false },
  { name: "correlate", title: "Korrelering", real: true },
];
const FIRMS_SATELLITES = { Aqua: "Aqua", Terra: "Terra", SNPP: "Suomi NPP", N20: "NOAA-20" };

function decimalText(value) {
  return String(value).replace(".", ",");
}

// The flood's sequence: a real Sentinel-1 acquisition; the radar image is not analysed in the demo.
function floodDetectionDetail(info, iotText, place, sensors) {
  const pass = info.pass;
  const { counts, rules } = info.classification;
  switch (info.name) {
    case "acquired":
      return `Radar (${pass.instrument}) på ${pass.satellite} tar en bild över ${place} ${pass.pass_utc.slice(11, 16)} UTC – den verkliga radarbilden visas på kartan.`;
    case "anomaly":
      return `Illustrativt: ${pass.satellite} flaggar vatten på marken i bilden. Sentinel-1 analyserar inte bilderna ombord.`;
    case "downlink":
      return "Illustrativt: satelliten skickar larmet till en markstation och vidare till lägescentralen.";
    case "zoom":
      return `Kartan zoomar till ${place} och den verkliga radarbilden: släta vattenytor är mörka. Nästa steg visar beräknat vatten utanför sjöar och hav.`;
    case "iot":
      return `Blått på kartan är vatten i radarbilden utanför sjöar och hav – en beräknad mask, inte en kartlagd översvämning. `
        + `${sensors[0].toUpperCase()}${sensors.slice(1)} på marken kontrollerar larmet: ${iotText || "inga sensorvärden ännu"}.`;
    case "correlate":
      return `${info.classification.outcome} – ${counts.Översvämning} av ${rules.length} regler för översvämning håller.`;
    default:
      return "";
  }
}

// The detail of the current step; `info` is /api/detection, `iotText` the synthetic sensors' line.
// `place` is the flood scenario's place (config.incident_place), `sensors` its word for its sensors
// (config.sensor_words.the_sensors).
function detectionDetail(info, iotText, place = "Sundsvall", sensors = "bräddgivarna") {
  if (info.pass.kind === "flood") return floodDetectionDetail(info, iotText, place, sensors);
  const pass = info.pass;
  const satellite = FIRMS_SATELLITES[pass.satellite] || pass.satellite;
  const { counts, rules } = info.classification;
  const total = (category) => rules.filter((rule) => rule.category === category).length;
  switch (info.name) {
    case "acquired":
      return `${pass.instrument} på ${satellite} passerar över branden ${pass.pass_utc.slice(11, 16)} UTC – verklig passage ur FIRMS ${pass.pass_utc.slice(0, 4)}.`;
    case "anomaly":
      return `Illustrativt: ${satellite} flaggar ett varmt område i bilden. Satelliterna analyserade inte bilderna ombord ${pass.pass_utc.slice(0, 4)}.`;
    case "downlink":
      return "Illustrativt: satelliten skickar larmet till en markstation och vidare till lägescentralen.";
    case "zoom":
      return `${pass.detections} detektioner, starkast ${decimalText(pass.max_frp_mw)} MW – verkliga FIRMS-data.`;
    case "iot":
      return `Sensorerna på marken kontrollerar larmet: ${iotText || "inga sensorvärden ännu"}.`;
    case "correlate":
      return `${info.classification.outcome} – ${counts.Vegetationsbrand} av ${total("Vegetationsbrand")} regler för vegetationsbrand och ${counts.Industri} av ${total("Industri")} för industri håller.`;
    default:
      return "";
  }
}

function stepTitle(item, place) {
  return item.title.replace("{place}", place);
}

// The steps for a list: done, current or still to come; `place` names the incident's place.
function detectionSteps(step, place = "branden") {
  return DETECTION_STEPS.map((item, index) => ({
    ...item, title: stepTitle(item, place), state: index < step ? "done" : index === step ? "current" : "todo",
  }));
}

function detectionStepLine(detection, place = "branden") {
  if (!detection) return "Ingen sekvens – tryck SATELLITE DETECTION.";
  const item = DETECTION_STEPS[detection.step];
  return `Steg ${detection.step + 1}/${detection.steps}: ${stepTitle(item, place)} (${item.real ? "verkliga data" : "syntetiskt"})`;
}

if (typeof module !== "undefined") module.exports = { EVENT_TEXTS, DETECTION_STEPS, detectionDetail, detectionSteps, detectionStepLine, FILTER_CATEGORIES, MISSING_NOTE, eventText, eventBanner, statusLines, queueText, syncBanner, syncLines };
