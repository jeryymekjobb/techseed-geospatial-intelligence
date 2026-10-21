// Which satellite image the maps show (config.layers.landsat from app/backend/landsat.py:
// Landsat and, in some scenarios, Sentinel-1 and -2), chosen in mission control and shared by
// every screen (the scenario status's `image`): "auto" the latest scene with one of the image
// types ticked in mission control (the status's `image_types`, or defaultImageTypes) taken
// up to the scenario clock, "off" the map, or one scene's image as "scene|image".
// A chosen image not yet taken at the clock gives way to the latest; one in the role "after"
// taken after the clock is a comparison, shown whenever it is chosen. Pure, so it can be
// tested in Node.
"use strict";

// The image types "auto" follows when mission control has ticked none: SWIR in the fire,
// radar in the flood, which sees through the clouds; the first type the scenario has otherwise.
function defaultImageTypes(incident, names) {
  const kinds = Object.keys(names || {});
  const wanted = incident === "wildfire" ? ["swir", "natural"] : ["radar"];
  const found = wanted.find((kind) => kinds.includes(kind)) || kinds[0];
  return found ? [found] : [];
}

// The scenario status's image types, or the default; `names` orders them (config.layers.landsat.names).
function imageTypesShown(statusTypes, incident, names) {
  const types = Array.isArray(statusTypes) ? statusTypes : defaultImageTypes(incident, names);
  return Object.keys(names || {}).filter((kind) => types.includes(kind));
}

function landsatSelection(scenes, clockMs, pick, types) {
  const ticked = typeof types === "string" ? [types] : types;
  if (pick === "off") return { scene: null, key: null, reason: "off" };
  if (pick && pick !== "auto") {
    const [name, image] = pick.split("|");
    const scene = scenes.find((item) => item.scene === name);
    if (scene && scene.images[image]) {
      const later = Date.parse(scene.acquired_utc) > clockMs;
      if (!later) return { scene, key: pick, reason: "shown" };
      if (scene.role === "after") return { scene, key: pick, reason: "comparison" };
    }
  }
  if (!ticked.length) return { scene: null, key: null, reason: "no-types" };
  // The latest scene with a ticked type, its first ticked image; none yet when no such scene has been taken.
  const scene = scenes.filter((item) => Date.parse(item.acquired_utc) <= clockMs && ticked.some((kind) => item.images[kind])).pop();
  if (!scene) return { scene: null, key: null, reason: "none-yet" };
  return { scene, key: `${scene.scene}|${ticked.find((kind) => scene.images[kind])}`, reason: "shown" };
}

// For mission control's ticks: how many images of each type are taken up to the clock, of all.
function imageTypeCounts(scenes, names, clockMs) {
  return Object.fromEntries(Object.keys(names).map((kind) => {
    const all = scenes.filter((scene) => scene.images[kind]);
    return [kind, { taken: all.filter((scene) => Date.parse(scene.acquired_utc) <= clockMs).length, total: all.length }];
  }));
}

// Mission control's list of images: every image taken up to the clock, the latest first,
// then the comparisons taken after it (role "after"), which can always be chosen.
// `names` orders a scene's images (config.layers.landsat.names); `formatTime` dates them;
// `types`, when given, keeps only the image types ticked in mission control.
function imageOptions(scenes, names, clockMs, formatTime, types = null) {
  const order = Object.keys(names).filter((image) => !types || types.includes(image));
  const entries = (scene) => order.filter((image) => scene.images[image])
    .map((image) => ({ value: `${scene.scene}|${image}`, text: `${formatTime(scene.acquired_utc)} – ${scene.satellite} – ${IMAGE_KINDS[image] || image}`
      + (scene.meteosat_cloud_pct === undefined ? "" : ` – Meteosat ${scene.meteosat_cloud_pct} % moln`) }));
  const taken = scenes.filter((scene) => Date.parse(scene.acquired_utc) <= clockMs)
    .sort((a, b) => Date.parse(b.acquired_utc) - Date.parse(a.acquired_utc));
  const comparisons = scenes.filter((scene) => scene.role === "after" && Date.parse(scene.acquired_utc) > clockMs);
  return [
    ...taken.flatMap(entries),
    ...comparisons.flatMap((scene) => entries(scene).map((item) => ({ ...item, text: `${item.text} (jämförelse – tagen senare)` }))),
  ];
}

// Short names of the images for the main screen's caption.
const IMAGE_KINDS = {
  swir: "falska färger, kortvågig IR", natural: "naturliga färger", ndmi: "fukt i vegetationen (NDMI)",
  water: "vatten (NDWI)", radar: "radar", radarwater: "vatten i radarbilden (beräknat)",
};

// What the main screen shows under its overlays, dated: the satellite image and when it was
// taken, or the map and when its data was fetched. `scene` and `image` are what is shown
// (none for the map), `reason` why no image is (landsatSelection), `choice` the image types asked for,
// `mapData` config.layers.map_data. During the fire's detection sequence `detection` is its
// FIRMS pass (instrument, pass_utc): the caption names the detections, then what lies under them.
// `baseMap`, when given, is the base map shown (basemaps.js baseMapFor; null for none).
const BASE_MAP_TEXTS = {
  online: "Karta – OpenStreetMap online", topowebb: "Karta – Lantmäteriet topowebb", kommun: "Karta – Sundsvalls kommun",
};

function mapText(baseMap, mapData, offlineTiles, formatDate) {
  if (baseMap === null) return "Karta – ingen baskarta vald i mission control (i 3D Natural Earth II)";
  if (baseMap && BASE_MAP_TEXTS[baseMap]) return BASE_MAP_TEXTS[baseMap];
  return offlineTiles && mapData
    ? `Karta – ${mapData.source}, data från ${formatDate(mapData.date_utc)}`
    : "Karta – Natural Earth II (offline-kartan är inte igång)";
}

function viewCaption({ scene, image, reason, choice, mapData, offlineTiles, formatTime, formatDate, detection, baseMap }) {
  let shown;
  if (scene && image) {
    shown = `Satellitbild – ${scene.satellite}, ${IMAGE_KINDS[image] || image}, tagen ${formatTime(scene.acquired_utc)}`
      + (scene.meteosat_cloud_pct === undefined ? "" : ` – Meteosat: ${scene.meteosat_cloud_pct} % moln över kartan`);
  } else {
    shown = mapText(baseMap, mapData, offlineTiles, formatDate)
      + (reason === "none-yet" ? `; ingen bild (${typeNames(choice)}) tagen ännu vid scenariotiden` : "")
      + (reason === "no-types" ? "; inga bildtyper valda i mission control" : "");
  }
  if (!detection) return `Visas: ${shown}` + (scene && image && reason === "comparison" ? " (jämförelse, tagen senare än scenariotiden)" : "");
  return `Visas: ${detection.instrument}-detektioner ${formatTime(detection.pass_utc)} · underlag: ${shown}`;
}

// "radar eller naturliga färger" for one type or several.
function typeNames(types) {
  return (typeof types === "string" ? [types] : types).map((kind) => IMAGE_KINDS[kind] || kind).join(" eller ");
}

if (typeof module !== "undefined") {
  module.exports = { landsatSelection, imageOptions, viewCaption, IMAGE_KINDS, defaultImageTypes, imageTypesShown, imageTypeCounts, typeNames };
}
