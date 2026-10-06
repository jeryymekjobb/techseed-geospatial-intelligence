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
    const taken = scenes.filter((item) => Date.parse(item.acquired_utc) <= clockMs);
    scene = [...taken].reverse().find((item) => item.images[imageChoice]) || taken[taken.length - 1];
    if (!scene) return { scene: null, key: null, reason: "none-yet" };
  } else {
    scene = scenes.find((item) => item.scene === dateChoice) || scenes.find((item) => item.role === dateChoice);
    if (!scene) return { scene: null, key: null, reason: "missing" };
    if (scene.role !== "after" && Date.parse(scene.acquired_utc) > clockMs) return { scene, key: null, reason: "not-yet" };
  }
  if (!scene.images[imageChoice]) return { scene, key: null, reason: "missing" };
  return { scene, key: `${scene.scene}|${imageChoice}`, reason: scene.role === "after" ? "comparison" : "shown" };
}

if (typeof module !== "undefined") module.exports = { landsatSelection };
