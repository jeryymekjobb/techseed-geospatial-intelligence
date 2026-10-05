// Satellite positions in 2014 from the Space-Track element sets (/api/satellites),
// with satellite.js (SGP4). Used by the 3D globe and checked against the FIRMS
// detection times in tests/test_satellite_passes.py. `lib` is the satellite.js
// module, passed in so the same code runs in the browser and in Node.
"use strict";

const EARTH_RADIUS_KM = 6371.0;

// The latest element set at or before the time, or the first one before the period.
function elementAt(elements, time) {
  let found = elements[0];
  for (const element of elements) {
    if (new Date(element.epoch_utc) > time) break;
    found = element;
  }
  return found;
}

const satrecs = new Map();

function satrecFor(lib, element) {
  const key = element.line1;
  if (!satrecs.has(key)) satrecs.set(key, lib.twoline2satrec(element.line1, element.line2));
  return satrecs.get(key);
}

// Latitude and longitude of the point below the satellite, its height and speed.
function subpoint(lib, elements, time) {
  const element = elementAt(elements, time);
  const state = lib.propagate(satrecFor(lib, element), time);
  if (!state || !state.position || typeof state.position === "boolean") return null;
  const geodetic = lib.eciToGeodetic(state.position, lib.gstime(time));
  const { x, y, z } = state.velocity;
  return {
    latitude: lib.degreesLat(geodetic.latitude),
    longitude: lib.degreesLong(geodetic.longitude),
    height_km: geodetic.height,
    speed_km_s: Math.sqrt(x * x + y * y + z * z),
    epoch_utc: element.epoch_utc,
  };
}

// Great-circle distance on the ground, in km.
function groundDistanceKm(lat1, lon1, lat2, lon2) {
  const rad = Math.PI / 180;
  const a = Math.sin(((lat2 - lat1) * rad) / 2) ** 2
    + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(((lon2 - lon1) * rad) / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(a)));
}

if (typeof module !== "undefined") module.exports = { elementAt, subpoint, groundDistanceKm };
