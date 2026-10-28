// The yearly shoreline lines of a coastal erosion scenario (shorelines.py): which of them the maps
// draw at a moment of the scenario clock, and in which colour. Pure, so it can be tested in Node.
"use strict";

// The earliest image's line blue, the latest red, the years between mixed.
const SHORELINE_FIRST = [31, 95, 191];
const SHORELINE_LAST = [214, 40, 40];

function shorelineColour(index, count) {
  const share = count > 1 ? index / (count - 1) : 1;
  const mix = SHORELINE_FIRST.map((value, channel) => Math.round(value + share * (SHORELINE_LAST[channel] - value)));
  return `#${mix.map((value) => value.toString(16).padStart(2, "0")).join("")}`;
}

// "Vegetationskant 2024-05-18, Sentinel-2B, härledd ur Sentinel-2, ±10–20 m".
function shorelineText(properties, uncertainty) {
  return `Vegetationskant ${properties.acquired_utc.slice(0, 10)}, ${properties.satellite}, härledd ur Sentinel-2, `
    + `±${uncertainty[0]}–${uncertainty[1]} m`;
}

// What a clicked line says: a title short enough for the info box's one line ("Vegetationskant
// 2026-05-25") and the details under it, the image's satellite and role ("årsbild 2026", "efter Babet").
function shorelineInfo(properties, uncertainty) {
  const label = properties.label ? `, ${properties.label[0].toLowerCase()}${properties.label.slice(1)}` : "";
  return {
    title: `Vegetationskant ${properties.acquired_utc.slice(0, 10)}`,
    details: [`${properties.satellite}${label}`, "Härledd ur Sentinel-2 (10 m pixlar), inte uppmätt",
      `Osäkerhet ±${uncertainty[0]}–${uncertainty[1]} m`],
  };
}

// The lines of the images taken up to the clock, oldest first, each with its image's index among all
// the images (the same at every clock, so a clicked line can be found again), its colour, its text,
// what a click shows and whether it is the latest (drawn heavy).
function shorelinesAt(collection, clockMs) {
  if (!collection) return [];
  const features = collection.features;
  const shown = features.filter((feature) => Date.parse(feature.properties.acquired_utc) <= clockMs);
  return shown.map((feature, index) => ({
    id: features.indexOf(feature),
    lines: feature.geometry.coordinates,
    colour: shorelineColour(features.indexOf(feature), features.length),
    latest: index === shown.length - 1,
    text: shorelineText(feature.properties, collection.uncertainty_m),
    ...shorelineInfo(feature.properties, collection.uncertainty_m),
  }));
}

// The panel's key: every image's date and colour, an image of a year by its date only and one
// such as "Före Babet" also by its label; `shown` for those taken up to the clock, `latest` for
// the last of them (drawn heavy).
function shorelineLegend(collection, clockMs) {
  const features = collection?.features || [];
  const shown = features.filter((feature) => Date.parse(feature.properties.acquired_utc) <= clockMs).length;
  return features.map((feature, index) => {
    const { role, label, acquired_utc: acquired } = feature.properties;
    const named = label && !/^\d{4}$/.test(role) ? `, ${label[0].toLowerCase()}${label.slice(1)}` : "";
    return { colour: shorelineColour(index, features.length), text: `${acquired.slice(0, 10)}${named}`,
             shown: index < shown, latest: index === shown - 1 };
  });
}

if (typeof module !== "undefined") {
  module.exports = { shorelineColour, shorelineText, shorelineInfo, shorelinesAt, shorelineLegend };
}
