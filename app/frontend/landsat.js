// Which satellite image the maps show (config.layers.landsat from app/backend/landsat.py:
// Landsat and, in some scenarios, Sentinel-2). By default the latest scene with the chosen
// image taken up to the scenario clock; a chosen date - a scene, or a role such as "before" -
// is shown once the clock has reached it, except a scene in the role "after", which is a
// comparison shown whenever it is chosen. Pure, so it can be tested in Node.
"use strict";

function landsatSelection(scenes, clockMs, dateChoice, imageChoice) {
  if (imageChoice === "off") return { scene: null, key: null, reason: "off" };
  let scene;
  if (dateChoice === "auto") {
    // The latest scene with the chosen image; none yet when no such scene has been taken.
    scene = scenes.filter((item) => Date.parse(item.acquired_utc) <= clockMs && item.images[imageChoice]).pop();
    if (!scene) return { scene: null, key: null, reason: "none-yet" };
  } else {
    scene = scenes.find((item) => item.scene === dateChoice) || scenes.find((item) => item.role === dateChoice);
    if (!scene) return { scene: null, key: null, reason: "missing" };
    if (scene.role !== "after" && Date.parse(scene.acquired_utc) > clockMs) return { scene, key: null, reason: "not-yet" };
  }
  if (!scene.images[imageChoice]) return { scene, key: null, reason: "missing" };
  return { scene, key: `${scene.scene}|${imageChoice}`, reason: scene.role === "after" ? "comparison" : "shown" };
}

// Short names of the images for the main screen's caption.
const IMAGE_KINDS = {
  swir: "falska färger, kortvågig IR", natural: "naturliga färger", ndmi: "fukt i vegetationen (NDMI)",
  water: "vatten (NDWI)", radar: "radar", radarwater: "vatten i radarbilden (beräknat)",
};

// What the main screen shows under its overlays, dated: the satellite image and when it was
// taken, or the map and when its data was fetched. `scene` and `image` are what is shown
// (none for the map), `reason` why no image is (landsatSelection), `choice` the image asked for,
// `mapData` config.layers.map_data.
function viewCaption({ scene, image, reason, choice, mapData, offlineTiles, formatTime, formatDate }) {
  if (scene && image) {
    return `Visas: Satellitbild – ${scene.satellite}, ${IMAGE_KINDS[image] || image}, tagen ${formatTime(scene.acquired_utc)}`
      + (reason === "comparison" ? " (jämförelse, tagen senare än scenariotiden)" : "");
  }
  const map = offlineTiles && mapData
    ? `Visas: Karta – ${mapData.source}, data från ${formatDate(mapData.date_utc)}`
    : "Visas: Karta – Natural Earth II (offline-kartan är inte igång)";
  return map + (reason === "none-yet" ? `; ingen bild (${IMAGE_KINDS[choice] || choice}) tagen ännu vid scenariotiden` : "");
}

if (typeof module !== "undefined") module.exports = { landsatSelection, viewCaption, IMAGE_KINDS };
