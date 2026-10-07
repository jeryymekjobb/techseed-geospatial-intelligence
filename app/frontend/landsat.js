// Which satellite image the maps show (config.layers.landsat from app/backend/landsat.py:
// Landsat and, in some scenarios, Sentinel-1 and -2), chosen in mission control and shared by
// every screen (the scenario status's `image`): "auto" the latest scene with `latestImage`
// taken up to the scenario clock, "off" the map, or one scene's image as "scene|image".
// A chosen image not yet taken at the clock gives way to the latest; one in the role "after"
// taken after the clock is a comparison, shown whenever it is chosen. Pure, so it can be
// tested in Node.
"use strict";

function landsatSelection(scenes, clockMs, pick, latestImage) {
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
  // The latest scene with the image; none yet when no such scene has been taken.
  const scene = scenes.filter((item) => Date.parse(item.acquired_utc) <= clockMs && item.images[latestImage]).pop();
  if (!scene) return { scene: null, key: null, reason: "none-yet" };
  return { scene, key: `${scene.scene}|${latestImage}`, reason: "shown" };
}

// Mission control's list of images: every image taken up to the clock, the latest first,
// then the comparisons taken after it (role "after"), which can always be chosen.
// `names` orders a scene's images (config.layers.landsat.names); `formatTime` dates them.
function imageOptions(scenes, names, clockMs, formatTime) {
  const order = Object.keys(names);
  const entries = (scene) => order.filter((image) => scene.images[image])
    .map((image) => ({ value: `${scene.scene}|${image}`, text: `${formatTime(scene.acquired_utc)} – ${scene.satellite} – ${IMAGE_KINDS[image] || image}` }));
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
// (none for the map), `reason` why no image is (landsatSelection), `choice` the image asked for,
// `mapData` config.layers.map_data. During the fire's detection sequence `detection` is its
// FIRMS pass (instrument, pass_utc): the caption names the detections, then what lies under them.
function viewCaption({ scene, image, reason, choice, mapData, offlineTiles, formatTime, formatDate, detection }) {
  let shown;
  if (scene && image) {
    shown = `Satellitbild – ${scene.satellite}, ${IMAGE_KINDS[image] || image}, tagen ${formatTime(scene.acquired_utc)}`;
  } else {
    shown = (offlineTiles && mapData
      ? `Karta – ${mapData.source}, data från ${formatDate(mapData.date_utc)}`
      : "Karta – Natural Earth II (offline-kartan är inte igång)")
      + (reason === "none-yet" ? `; ingen bild (${IMAGE_KINDS[choice] || choice}) tagen ännu vid scenariotiden` : "");
  }
  if (!detection) return `Visas: ${shown}` + (scene && image && reason === "comparison" ? " (jämförelse, tagen senare än scenariotiden)" : "");
  return `Visas: ${detection.instrument}-detektioner ${formatTime(detection.pass_utc)} · underlag: ${shown}`;
}

if (typeof module !== "undefined") module.exports = { landsatSelection, imageOptions, viewCaption, IMAGE_KINDS };
