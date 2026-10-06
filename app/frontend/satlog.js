// The satellite log under the satellite monitor (monitor.html): what has happened with the
// satellites up to the scenario clock, newest first. Built from the clock every time, so it
// is the same after a RESET, a jump or a reload. Each line says where it comes from:
// passes computed from the element sets, FIRMS detections and Landsat scenes from 2014, and
// mission control's simulated events. Pure, so it can be tested in Node.
"use strict";

const SATLOG_WINDOW_MS = 24 * 3600000;
// More lines than fit; the page shows as many as its space allows and cuts the oldest.
const SATLOG_LIMIT = 50;
const SATLOG_SOURCES = { computed: "beräknat", firms: "FIRMS 2014", landsat: "Landsat 2014", simulated: "simulerat" };
const SATLOG_FIRMS_NAMES = { Aqua: "Aqua", Terra: "Terra", SNPP: "Suomi NPP" };
// FIRMS detections of one satellite this close in time come from the same pass.
const SATLOG_PASS_GAP_MS = 15 * 60000;

// The FIRMS detections (features of /api/hotspots) grouped into passes: when, which
// satellite and instrument, how many and the strongest.
function firmsPasses(features) {
  const items = features.map((feature) => ({ ...feature.properties, atMs: Date.parse(feature.properties.acq_datetime_utc) }))
    .sort((a, b) => a.atMs - b.atMs);
  const passes = [];
  const open = new Map();
  for (const item of items) {
    const key = `${item.satellite}|${item.instrument}`;
    let pass = open.get(key);
    if (!pass || item.atMs - pass.lastMs > SATLOG_PASS_GAP_MS) {
      pass = { atMs: item.atMs, lastMs: item.atMs, satellite: item.satellite, instrument: item.instrument, detections: 0, maxFrp: 0 };
      passes.push(pass);
      open.set(key, pass);
    }
    pass.lastMs = item.atMs;
    pass.detections += 1;
    pass.maxFrp = Math.max(pass.maxFrp, item.frp || 0);
  }
  return passes.map(({ lastMs, ...pass }) => pass);
}

function satlogDecimal(value) {
  return String(Math.round(value * 10) / 10).replace(".", ",");
}

// The log lines, newest first: { atMs, text, source, kind }.
// `satellites`: [{ name, instrument, passes: [{ start, end }] }] over the fire (orbits.js);
// `firms`: firmsPasses(); `scenes`: config.layers.landsat.scenes; `events`: the scenario's events.
// `place` names the incident's place ("branden", "Sundsvall"). A line may carry its own
// `sourceText` (an image: its satellite and year); otherwise SATLOG_SOURCES names its source.
function satelliteLog({ satellites = [], firms = [], scenes = [], events = [] }, clockMs, windowMs = SATLOG_WINDOW_MS,
  limit = SATLOG_LIMIT, place = "branden") {
  const lines = [];
  for (const satellite of satellites) {
    const label = `${satellite.name}${satellite.instrument ? ` (${satellite.instrument})` : ""}`;
    for (const pass of satellite.passes || []) {
      lines.push({ atMs: pass.start, text: `${label} över ${place}`, source: "computed", kind: "enter" });
      lines.push({ atMs: pass.end, text: `${label} lämnar ${place}`, source: "computed", kind: "leave" });
    }
  }
  for (const pass of firms) {
    const name = SATLOG_FIRMS_NAMES[pass.satellite] || pass.satellite;
    const count = pass.detections === 1 ? "1 detektion" : `${pass.detections} detektioner`;
    lines.push({
      atMs: pass.atMs, text: `${count} från ${name} (${pass.instrument}), starkast ${satlogDecimal(pass.maxFrp)} MW`, source: "firms", kind: "firms",
    });
  }
  for (const scene of scenes) {
    const satellite = scene.satellite || "Landsat 8";
    lines.push({
      atMs: Date.parse(scene.acquired_utc), text: `${satellite} tar bild över ${place}`, source: "landsat", kind: "landsat",
      // "Landsat 2014", "Sentinel-2 2026": the mission without the unit.
      sourceText: `${satellite.replace(/(Sentinel-\d)[A-Z]$/, "$1").replace(/ \d$/, "")} ${scene.acquired_utc.slice(0, 4)}`,
    });
  }
  const eventTexts = {
    satellite_detection: "Mission control startar detektionssekvensen",
    satcom_failure: "SATCOM nere – satellitdata köas",
    satcom_restore: "SATCOM åter – SYNC av köade data",
  };
  for (const event of events) {
    if (eventTexts[event.kind]) lines.push({ atMs: Date.parse(event.clock_utc), text: eventTexts[event.kind], source: "simulated", kind: event.kind });
  }
  // An event recorded at a moment shows at that moment; among equal moments the later source first.
  return lines
    .map((line, order) => ({ ...line, order }))
    .filter((line) => line.atMs <= clockMs && line.atMs > clockMs - windowMs)
    .sort((a, b) => b.atMs - a.atMs || b.order - a.order)
    .slice(0, limit)
    .map(({ order, ...line }) => line);
}

if (typeof module !== "undefined") module.exports = { firmsPasses, satelliteLog, SATLOG_SOURCES };
