// Entry point of the 3D globe: the panel (panel.js) with the Cesium adapter (map3d.js).
// ?fly=1 starts the camera flight from space to the fire once the page is ready.
"use strict";

startWithErrors(createCesiumMap).then(() => {
  $("fly").addEventListener("click", () => state.map.flyToIncident());
  $("home").addEventListener("click", () => state.map.flyHome());
  if (new URLSearchParams(window.location.search).get("fly") === "1") {
    document.body.dataset.flight = "flying";
    state.map.flyToIncident().then(() => { document.body.dataset.flight = "arrived"; });
  }
});
