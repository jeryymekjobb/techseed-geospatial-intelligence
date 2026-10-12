// Satellite positions in 2014 from the Space-Track element sets (/api/satellites),
// with satellite.js (SGP4). Used by the 3D globe and checked against the FIRMS
// detection times in tests/test_satellite_passes.py. `lib` is the satellite.js
// module, passed in so the same code runs in the browser and in Node.
"use strict";

const EARTH_RADIUS_KM = 6371.0;

const epochs = new WeakMap();  // elements -> their epochs in ms, in order

// The latest element set at or before the time, or the first one before the period.
function elementAt(elements, time) {
  if (!epochs.has(elements)) epochs.set(elements, elements.map((element) => Date.parse(element.epoch_utc)));
  const times = epochs.get(elements);
  const target = time.getTime();
  let [low, high] = [0, times.length - 1];
  if (target < times[0]) return elements[0];
  while (low < high) {  // the last index with times[index] <= target
    const middle = Math.ceil((low + high) / 2);
    if (times[middle] <= target) low = middle; else high = middle - 1;
  }
  return elements[low];
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

// Points along the orbit from `minutes` before to `minutes` after the time, with heights.
function orbitTrack(lib, elements, time, minutes = 50, stepMinutes = 1) {
  const points = [];
  for (let offset = -minutes; offset <= minutes; offset += stepMinutes) {
    const point = subpoint(lib, elements, new Date(time.getTime() + offset * 60000));
    if (point) points.push(point);
  }
  return points;
}

// The first time from `from` on at which the point lies within half the swath of the
// ground track: coarse steps of 30 s, refined to 5 s near the swath edge. null when no
// pass comes within `hours`.
function nextPass(lib, elements, from, latitude, longitude, halfSwathKm, hours = 24) {
  const distanceAt = (ms) => {
    const point = subpoint(lib, elements, new Date(ms));
    return point ? groundDistanceKm(point.latitude, point.longitude, latitude, longitude) : Infinity;
  };
  const start = from.getTime();
  for (let ms = start; ms <= start + hours * 3600000; ms += 30000) {
    const km = distanceAt(ms);
    if (km <= halfSwathKm) return new Date(ms);
    if (km <= halfSwathKm + 250) {
      for (let fine = ms + 5000; fine < ms + 30000; fine += 5000) {
        if (distanceAt(fine) <= halfSwathKm) return new Date(fine);
      }
    }
  }
  return null;
}

// A catalogue acquisition (Sentinel-1) as a pass: the product's first 25 seconds.
const ACQUISITION_MS = 25000;

// Whether a satellite has passes over the incident: a swath round its track or known acquisitions.
function hasPasses(item) {
  return Boolean(item.half_swath_km || item.acquisitions);
}

// The satellites that send the scenario data to the ground, by name: FIRMS's detections (`firms`),
// Sentinel-1's catalogue acquisitions, or one of the scenario's satellite images (`scenes`,
// config.layers.landsat.scenes; an image without a satellite is Landsat 8's). Only they get an orbit
// on the screens; the others, such as the ISS, show where they are without one.
function contributingSatellites(satellites, scenes) {
  const imaged = new Set((scenes || []).map((scene) => scene.satellite || "Landsat 8"));
  return new Set((satellites || []).filter((item) => item.firms || item.acquisitions || imaged.has(item.name)).map((item) => item.name));
}

// The passes of a satellite between two times: its catalogue acquisitions, or computed from its swath.
function satellitePasses(lib, item, startMs, endMs, latitude, longitude) {
  if (item.acquisitions) {
    return item.acquisitions.map((time) => Date.parse(time)).filter((ms) => ms >= startMs && ms < endMs)
      .map((ms) => ({ start: ms, end: ms + ACQUISITION_MS }));
  }
  return passesBetween(lib, item.elements, startMs, endMs, latitude, longitude, item.half_swath_km);
}

// Every pass over the point between two times, as { start, end } in ms: the incident inside
// half the swath. The ground track is sampled at a step short enough not to jump a
// whole swath (30 s, less for Landsat's narrow one), and each entry and exit is found by
// halving the step down to 1 s. The globe computes this once per scenario day and looks
// the next pass up, instead of searching every tick.
// app/backend/passes.py computes the same for the scenario clock.
function passesBetween(lib, elements, startMs, endMs, latitude, longitude, halfSwathKm) {
  const inside = (ms) => {
    const point = subpoint(lib, elements, new Date(ms));
    return Boolean(point) && groundDistanceKm(point.latitude, point.longitude, latitude, longitude) <= halfSwathKm;
  };
  // A ground point moves about 7 km/s; never step past more than the swath.
  const step = Math.min(30000, Math.max(2000, Math.floor((halfSwathKm / 7) * 1000)));
  const edge = (outside, insideMs) => {
    let [low, high] = [outside, insideMs];  // inside(low) differs from inside(high)
    const wanted = inside(high);
    while (Math.abs(high - low) > 1000) {
      const middle = Math.round((low + high) / 2);
      if (inside(middle) === wanted) high = middle; else low = middle;
    }
    return high;
  };
  const passes = [];
  let previous = startMs;
  let wasInside = inside(startMs);
  let current = wasInside ? { start: startMs } : null;
  for (let ms = startMs + step; ms <= endMs; ms += step) {
    const isInside = inside(ms);
    if (isInside && !wasInside) current = { start: edge(previous, ms) };
    else if (!isInside && wasInside) {
      current.end = edge(ms, previous) + 1000;
      passes.push(current);
      current = null;
    }
    previous = ms;
    wasInside = isInside;
  }
  if (current) {
    current.end = endMs;
    passes.push(current);
  }
  return passes;
}

if (typeof module !== "undefined") module.exports = { elementAt, subpoint, groundDistanceKm, orbitTrack, nextPass, passesBetween, hasPasses, contributingSatellites, satellitePasses };
