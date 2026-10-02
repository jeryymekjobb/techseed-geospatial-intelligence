// Cesium map adapter for the 3D globe (see panel.js for the interface). Runs without
// Cesium ion: the world imagery is the Natural Earth II set shipped with Cesium, the
// fire area uses the same offline OSM tiles as the 2D map, and the terrain is built
// from Copernicus DEM GLO-30 (tools/build_terrain.py).
"use strict";

// Camera route from space to the fire, about five seconds in total.
const FLIGHT = [
  { lon: 12, lat: 50, height: 16_000_000, pitch: -90, seconds: 0.8 },  // Earth over Europe
  { lon: 15, lat: 58, height: 3_500_000, pitch: -90, seconds: 1.0 },   // Europe
  { lon: 16, lat: 61, height: 1_100_000, pitch: -80, seconds: 1.0 },   // Sweden
  { lon: 16.3, lat: 59.6, height: 160_000, pitch: -60, seconds: 1.1 }, // Mälardalen
];
// Last step: look at the fire's centre from the south at this pitch and range.
const FIRE_VIEW = { pitch: -50, range: 42_000, seconds: 1.1 };

function cesiumColor(hex, alpha = 1) {
  return Cesium.Color.fromCssColorString(hex).withAlpha(alpha);
}

// Height of the hotspot points above the ground, so they are not hidden in the terrain.
const HOTSPOT_LIFT_METRES = 5;

async function createCesiumMap(config) {
  const terrainProvider = config.layers.terrain3d
    ? await Cesium.CesiumTerrainProvider.fromUrl("/terrain/", { requestVertexNormals: true })
    : null;
  const viewer = new Cesium.Viewer("map", {
    ...(terrainProvider ? { terrainProvider } : {}),
    baseLayer: Cesium.ImageryLayer.fromProviderAsync(
      Cesium.TileMapServiceImageryProvider.fromUrl(Cesium.buildModuleUrl("Assets/Textures/NaturalEarthII")),
    ),
    baseLayerPicker: false, geocoder: false, homeButton: false, sceneModePicker: false,
    navigationHelpButton: false, fullscreenButton: false, timeline: false, animation: false,
    infoBox: true, selectionIndicator: false, requestRenderMode: false,
  });
  viewer.scene.globe.enableLighting = false;
  viewer.scene.skyAtmosphere.show = true;
  const credits = viewer.creditDisplay;
  const addCredit = (text) => credits.addStaticCredit(new Cesium.Credit(text, true));
  addCredit("Natural Earth II");
  addCredit(config.attribution.firms);
  const [south, west] = config.view_bounds[0];
  const [north, east] = config.view_bounds[1];
  if (config.layers.offline_tiles) {
    viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
      url: "/tiles/{z}/{x}/{y}.png", maximumLevel: 18,
      rectangle: Cesium.Rectangle.fromDegrees(15.5, 59.55, 16.8, 60.3),
      credit: new Cesium.Credit("© OpenStreetMap contributors", true),
    }));
  } else {
    addNote("Offline-kartan är inte igång; 3D-globen visar bara Natural Earth II över brandområdet.");
  }
  if (terrainProvider) {
    addCredit(config.attribution.copernicus_dem);
  } else {
    addNote("3D-terrängen är inte byggd (tools/fetch_copernicus_dem.py och tools/build_terrain.py); globen är platt.");
  }
  addNote("3D: prognos, vindpilar och ortnamn kommer i nästa steg.");
  const home = Cesium.Rectangle.fromDegrees(west, south, east, north);
  viewer.camera.setView({ destination: home });

  const points = viewer.scene.primitives.add(new Cesium.PointPrimitiveCollection());
  let hotspots = [];
  // Hotspots arrive one by one from the stream; their ground heights are looked up in batches.
  let unplaced = [];
  let placing = null;
  const placeOnGround = () => {
    if (!terrainProvider || placing) return;
    placing = Promise.resolve().then(async () => {
      while (unplaced.length) {
        const batch = unplaced;
        unplaced = [];
        const positions = batch.map((point) => Cesium.Cartographic.fromCartesian(point.position));
        await Cesium.sampleTerrainMostDetailed(terrainProvider, positions);
        batch.forEach((point, index) => {
          const ground = positions[index];
          if (hotspots.includes(point)) {  // not cleared by a new sync meanwhile
            point.position = Cesium.Cartesian3.fromRadians(ground.longitude, ground.latitude, (ground.height || 0) + HOTSPOT_LIFT_METRES);
          }
        });
      }
    }).finally(() => { placing = null; });
  };

  const adapter = {
    viewer,
    wantsLabels: () => false,
    addAttribution: addCredit,
    addTerrain() {},
    addLabels() {},

    addStations(stations) {
      for (const station of stations) {
        viewer.entities.add({
          name: `SMHI ${station.name}`,
          position: Cesium.Cartesian3.fromDegrees(station.longitude, station.latitude),
          point: {
            pixelSize: 10, color: cesiumColor("#ffffff"), outlineColor: cesiumColor("#1f5fa8"), outlineWidth: 3,
            heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
          label: {
            text: `SMHI ${station.name}`, font: "14px system-ui, sans-serif", fillColor: cesiumColor("#1b2430"),
            outlineColor: cesiumColor("#ffffff"), outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE,
            pixelOffset: new Cesium.Cartesian2(10, 0), horizontalOrigin: Cesium.HorizontalOrigin.LEFT,
            heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
          description: `SMHI-station ${station.name}, ${station.distance_km} km från branden`,
        });
      }
    },

    clearHotspots() {
      points.removeAll();
      hotspots = [];
      unplaced = [];
    },

    addHotspot(feature) {
      const [lon, lat] = feature.geometry.coordinates;
      const p = feature.properties;
      const viirs = p.instrument === "VIIRS";
      const point = points.add({
        position: Cesium.Cartesian3.fromDegrees(lon, lat),
        pixelSize: hotspotRadius(p.frp) * 1.6,
        outlineWidth: viirs ? 0 : 1.5,
        // Points on the bare ellipsoid would otherwise flicker against the ground.
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
        id: { kind: "hotspot", properties: p },
      });
      point.detectedAt = new Date(p.acq_datetime_utc);
      point.viirs = viirs;
      hotspots.push(point);
      unplaced.push(point);
      placeOnGround();
    },

    hotspotCount: () => hotspots.length,

    restyleHotspots(clock) {
      for (const point of hotspots) {
        const color = hotspotColor(point.detectedAt, clock);
        point.color = cesiumColor(color, point.viirs ? 0.85 : 0.25);
        point.outlineColor = cesiumColor(color);
      }
    },

    setupWind() {},
    showWind() {},
    setupForecast() {},
    drawForecast() {},
    finish() {},

    // Fly from space to the fire; resolves when the camera has arrived.
    flyToIncident() {
      const [lat, lon] = config.fire_centre;
      const flight = FLIGHT.reduce((previous, step) => previous.then(() => new Promise((resolve) => {
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(step.lon, step.lat, step.height),
          orientation: { heading: 0, pitch: Cesium.Math.toRadians(step.pitch), roll: 0 },
          duration: step.seconds,
          easingFunction: Cesium.EasingFunction.QUADRATIC_IN_OUT,
          complete: resolve, cancel: resolve,
        });
      })), Promise.resolve());
      return flight.then(() => new Promise((resolve) => {
        viewer.camera.flyToBoundingSphere(new Cesium.BoundingSphere(Cesium.Cartesian3.fromDegrees(lon, lat), 1), {
          offset: new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(FIRE_VIEW.pitch), FIRE_VIEW.range),
          duration: FIRE_VIEW.seconds, complete: resolve, cancel: resolve,
        });
      }));
    },

    flyHome() {
      viewer.camera.flyTo({ destination: home, duration: 1.5 });
    },
  };

  // Show the FIRMS details when a hotspot is clicked.
  new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas).setInputAction((movement) => {
    const picked = viewer.scene.pick(movement.position);
    if (picked?.id?.kind === "hotspot") {
      viewer.selectedEntity = new Cesium.Entity({ name: "FIRMS-detektion", description: hotspotPopup(picked.id.properties) });
    }
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
  return adapter;
}
