// Which base map the maps show under the satellite images and overlays, ticked in mission
// control and shared by every screen (the scenario status's `base_maps`). The scenario's base
// maps are config.layers.base_maps (app/backend/server.py): the offline OSM map, OSM online and,
// when it is enabled, Lantmäteriet's topowebb, which only the 2D map has. With several ticked a
// map shows the first it has in that list's order; with none, the 3D globe shows only Natural
// Earth II and the 2D map no base map. Pure, so it can be tested in Node.
"use strict";

// Until mission control ticks others: the offline map, or OSM online when it is not running (as before).
function defaultBaseMaps(baseMaps) {
  const ids = baseMaps.map((item) => item.id);
  return ids.includes("offline") ? ["offline"] : ids.includes("online") ? ["online"] : [];
}

// The status's ticks in the list's order, or the default when none are set.
function baseMapsShown(statusMaps, baseMaps) {
  const ticked = Array.isArray(statusMaps) ? statusMaps : defaultBaseMaps(baseMaps);
  return baseMaps.map((item) => item.id).filter((id) => ticked.includes(id));
}

// The base map a 2D or 3D map shows of the ticked ones, or null for none.
function baseMapFor(ticked, baseMaps, dimension) {
  const item = baseMaps.find((entry) => ticked.includes(entry.id) && (dimension === "2d" || !entry.only_2d));
  return item ? item.id : null;
}

if (typeof module !== "undefined") module.exports = { defaultBaseMaps, baseMapsShown, baseMapFor };
