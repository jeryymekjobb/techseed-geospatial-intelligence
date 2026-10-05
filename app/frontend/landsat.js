// Which Landsat 8 image the maps show (config.layers.landsat from app/backend/landsat.py).
// By default the latest scene taken up to the scenario clock; a chosen date is shown once
// the clock has reached it, except the scene after the fire, which is a comparison shown
// whenever it is chosen. Pure, so it can be tested in Node.
"use strict";

function landsatSelection(scenes, clockMs, dateChoice, imageChoice) {
  if (imageChoice === "off") return { scene: null, key: null, reason: "off" };
  let scene;
  if (dateChoice === "auto") {
    scene = [...scenes].reverse().find((item) => Date.parse(item.acquired_utc) <= clockMs);
    if (!scene) return { scene: null, key: null, reason: "none-yet" };
  } else {
    scene = scenes.find((item) => item.role === dateChoice);
    if (!scene) return { scene: null, key: null, reason: "missing" };
    if (scene.role !== "after" && Date.parse(scene.acquired_utc) > clockMs) return { scene, key: null, reason: "not-yet" };
  }
  if (!scene.images[imageChoice]) return { scene, key: null, reason: "missing" };
  return { scene, key: `${scene.scene}|${imageChoice}`, reason: scene.role === "after" ? "comparison" : "shown" };
}

if (typeof module !== "undefined") module.exports = { landsatSelection };
