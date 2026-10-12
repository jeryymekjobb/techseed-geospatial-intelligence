// The log of satellite and IoT events under the satellite monitor (monitor.html): what has
// happened with the satellites and the synthetic IoT sensors up to the scenario clock, newest
// first. Built from the clock every time, so it is the same after a RESET, a jump or a reload.
// Each line says where it comes from: passes computed from the element sets, FIRMS detections
// and satellite images of its year, the synthetic sensors' changes (/api/sensors/synthetic/events),
// threatened buildings (/api/threats: the fire forecast's places, the buildings near an alarming
// flood sensor from PostGIS) and mission control's simulated events. Pure, so it can be tested in Node.
"use strict";

// The defaults of satelliteLog's window and limit; the satellite monitor passes the time since the
// demo's start and no limit, so its list scrolls back to the first line.
const SATLOG_WINDOW_MS = 24 * 3600000;
const SATLOG_LIMIT = 50;
const SATLOG_SOURCES = {
  computed: "beräknat", firms: "FIRMS", landsat: "satellitbild", synthetic: "syntetiskt", model: "modell", postgis: "PostGIS", simulated: "simulerat",
};
// How many of a pass's newly threatened places the line names; the rest are counted.
const SATLOG_PLACES_NAMED = 4;
// What a synthetic sensor's change says, by its kind: [starts confirming, stops confirming].
const SATLOG_SENSOR_TEXTS = {
  fire: ["känner rök eller värme", "slutar känna rök eller värme"],
  sewer: ["bräddar", "slutar brädda"],
  level: ["över tidigare högsta nivå", "under tidigare högsta nivå"],
};
const SATLOG_SENSOR_NAMES = { fire: "", sewer: "Bräddgivare ", level: "Nivåsensor " };
const SATLOG_FIRMS_NAMES = { Aqua: "Aqua", Terra: "Terra", SNPP: "Suomi NPP", N20: "NOAA-20" };
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
// `firms`: firmsPasses(); `scenes`: config.layers.landsat.scenes; `events`: the scenario's events;
// `sensorEvents`: the synthetic sensors' changes, { clock_utc, sensor, name, kind, confirms };
// `threats`: /api/threats, { places: [{ clock_utc, places: [{ name, span }] }], buildings_near: { sensor: count }, distance_m }.
// A sensor that starts confirming adds the buildings near it, under the same conditions as its own line.
// A sensor's changes are left out after mission control's SENSOR FAILURE for it, and every
// sensor's while mission control has switched IoT off.
// `place` names the incident's place ("branden", "Sundsvall"). A line may carry its own
// `sourceText` (an image: its satellite and year); otherwise SATLOG_SOURCES names its source.
function satelliteLog({ satellites = [], firms = [], scenes = [], events = [], sensorEvents = [], threats = {} }, clockMs, windowMs = SATLOG_WINDOW_MS,
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
      sourceText: `FIRMS ${new Date(pass.atMs).getUTCFullYear()}`,
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
  const names = new Map(sensorEvents.map((item) => [item.sensor, `${SATLOG_SENSOR_NAMES[item.kind] ?? ""}${item.name}`]));
  const failedAt = new Map();
  const iotOff = [];  // [from, to) while IoT was off
  let iotOn = true;
  let placed = 0;
  for (const event of events) {
    const atMs = Date.parse(event.clock_utc);
    if (eventTexts[event.kind]) lines.push({ atMs, text: eventTexts[event.kind], source: "simulated", kind: event.kind });
    if (event.kind === "sensor_failure") {
      const name = names.get(event.target) || event.target || "en sensor";
      lines.push({ atMs, text: `SENSOR FAILURE – ${name} slutar svara`, source: "simulated", kind: event.kind });
      if (event.target && !failedAt.has(event.target)) failedAt.set(event.target, atMs);
    } else if (event.kind === "iot") {
      iotOn = !iotOn;
      lines.push({ atMs, text: iotOn ? "IoT påslaget från mission control" : "IoT avstängt från mission control", source: "simulated", kind: event.kind });
      if (iotOn) iotOff[iotOff.length - 1][1] = atMs;
      else iotOff.push([atMs, Infinity]);
    } else if (event.kind === "place_sensor") {
      placed += 1;
      lines.push({ atMs, text: `Syntetisk sensor P${placed} placerad på kartan`, source: "simulated", kind: event.kind });
    }
  }
  for (const item of sensorEvents) {
    const atMs = Date.parse(item.clock_utc);
    if (failedAt.has(item.sensor) && atMs >= failedAt.get(item.sensor)) continue;
    if (iotOff.some(([from, to]) => atMs >= from && atMs < to)) continue;
    const texts = SATLOG_SENSOR_TEXTS[item.kind] || ["bekräftar händelsen", "slutar bekräfta händelsen"];
    lines.push({ atMs, text: `${names.get(item.sensor)} ${item.confirms ? texts[0] : texts[1]}`, source: "synthetic", kind: "sensor" });
    const near = threats.buildings_near?.[item.sensor];
    if (item.confirms && near) {
      lines.push({
        atMs, text: `${near} ${near === 1 ? "byggnad" : "byggnader"} inom ${threats.distance_m} m från ${names.get(item.sensor)}`,
        source: "postgis", kind: "threat",
      });
    }
  }
  for (const pass of threats.places || []) {
    const named = pass.places.slice(0, SATLOG_PLACES_NAMED).map((place) => `${place.name} ${place.span}`).join(", ");
    const more = pass.places.length - SATLOG_PLACES_NAMED;
    const count = pass.places.length === 1 ? "1 ort hotas" : `${pass.places.length} orter hotas`;
    lines.push({
      atMs: Date.parse(pass.clock_utc), text: `${count} inom 24 h: ${named}${more > 0 ? ` och ${more} till` : ""}`,
      source: "model", kind: "threat",
    });
  }
  // An event recorded at a moment shows at that moment; among equal moments the later source first.
  return lines
    .map((line, order) => ({ ...line, order }))
    .filter((line) => line.atMs <= clockMs && line.atMs > clockMs - windowMs)
    .sort((a, b) => b.atMs - a.atMs || b.order - a.order)
    .slice(0, limit)
    .map(({ order, ...line }) => line);
}

// What the satellite monitor reads aloud of the log: the lines (newest first, as satelliteLog gives
// them) not yet in `heard` (a Set of satlogKey), oldest first, each with its voice; with more than
// `max` new lines, the `max` newest and how many more there were. A satellite leaving the area is
// not read. Satellite events (passes, FIRMS detections, satellite images) take the voice "nst", all
// others "alma" (speech.py). `heard` gets every line.
const SATLOG_SPOKEN_MAX = 3;
const SATLOG_SATELLITE_SOURCES = ["computed", "firms", "landsat"];

function satlogKey(line) {
  return `${line.atMs}|${line.text}`;
}

function spokenLines(lines, heard, max = SATLOG_SPOKEN_MAX) {
  const fresh = lines.filter((line) => !heard.has(satlogKey(line)));
  for (const line of fresh) heard.add(satlogKey(line));
  const said = fresh.filter((line) => line.kind !== "leave");
  const spoken = said.slice(0, max).reverse()
    .map((line) => ({ text: line.text, voice: SATLOG_SATELLITE_SOURCES.includes(line.source) ? "nst" : "alma" }));
  const more = said.length - max;
  if (more > 0) spoken.push({ text: `och ${more} ${more === 1 ? "händelse" : "händelser"} till`, voice: "alma" });
  return spoken;
}

// The level sensors' report read aloud once per scenario day while any alarms (above the highest
// flow or level measured before at its SMHI station; level_sensors.py): one part per station,
// as several sensors can share one. Null when none alarms. `sensors`: the synthetic sensors'
// `sensors` (failed ones and those switched off with IOT AV are not there or not "ok").
const SATLOG_REPORT_MS = 24 * 3600000;

function levelReport(sensors) {
  const alarming = (sensors || []).filter((item) => item.kind === "level" && item.status === "ok" && item.confirms);
  if (!alarming.length) return null;
  const stations = new Map();
  for (const item of alarming) {
    const value = item.station_kind === "level"
      ? `${item.from_record_cm} centimeter över tidigare högsta nivå`
      : `${item.percent} procent av tidigare högsta flöde`;
    stations.set(item.station, value);
  }
  const count = alarming.length === 1 ? "1 nivågivare" : `${alarming.length} nivågivare`;
  return `Nivålarm från ${count}: ${[...stations].map(([station, value]) => `${station} ${value}`).join(". ")}.`;
}

// When the report is due: { speak, next } from the next due time (null when none is set), the
// clock, whether a sensor alarms and whether the clock jumped. The first report after a sensor
// starts to alarm is a day later (its log line has already been read); a jump only sets the time.
function levelReportDue(next, clockMs, alarming, jumped) {
  if (!alarming) return { speak: false, next: null };
  if (next === null || jumped) return { speak: false, next: clockMs + SATLOG_REPORT_MS };
  if (clockMs < next) return { speak: false, next };
  let following = next;
  while (following <= clockMs) following += SATLOG_REPORT_MS;
  return { speak: true, next: following };
}

if (typeof module !== "undefined") {
  module.exports = { firmsPasses, satelliteLog, spokenLines, satlogKey, levelReport, levelReportDue, SATLOG_SOURCES };
}
