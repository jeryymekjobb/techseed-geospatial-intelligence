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
const ON_GROUND = { heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, disableDepthTestDistance: Number.POSITIVE_INFINITY };
const LABEL_FONTS = {
  town: "bold 16px system-ui, sans-serif", village: "600 14px system-ui, sans-serif", lake: "italic 12px system-ui, sans-serif",
};

// Camera distance that matches a Leaflet zoom level near 60° N, for the label zoom limits.
function distanceForZoom(zoom) {
  return 40_000_000 / 2 ** zoom;
}

function escapeText(text) {
  const element = document.createElement("span");
  element.textContent = text;
  return element.innerHTML;
}

function svgImage(svg, size) {
  const sized = svg.replace(/^<svg /, `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" `);
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(sized)}`;
}

// The wind barb of wind_barbs.js as a stand-alone image, with the styles of styles.css inlined.
const BARB_STYLE = "<style>path,circle{fill:none;stroke:#0b3d91;stroke-width:1.1;stroke-linecap:round;stroke-linejoin:round}"
  + ".halo{stroke:#fff;stroke-width:3;opacity:.85}.pennant{fill:#0b3d91}</style>";
const barbImages = new Map();
function barbImage(speed) {
  const svg = windBarbSvg(speed);
  if (!barbImages.has(svg)) barbImages.set(svg, svgImage(svg.replace(/^(<svg [^>]*>)/, `$1${BARB_STYLE}`), 56));
  return barbImages.get(svg);
}

// Spread arrows pointing up (north), as in the 2D map: observed solid red, model dashed orange.
const SPREAD_ARROWS = {
  observed: svgImage('<svg viewBox="-35 -35 70 70"><path d="M0,0 L0,-30" stroke="#b3261e" stroke-width="3" fill="none" stroke-linecap="round"/>'
    + '<path d="M-5,-24 L0,-34 L5,-24 Z" fill="#b3261e"/></svg>', 70),
  model: svgImage('<svg viewBox="-35 -35 70 70"><path d="M0,0 L0,-30" stroke="#d35400" stroke-width="2" fill="none" stroke-dasharray="4 3"/>'
    + '<path d="M-5,-24 L0,-34 L5,-24 Z" fill="#d35400"/></svg>', 70),
};

// Billboard rotation is counter-clockwise from north when aligned with the Z axis.
function northRotation(degrees) {
  return -Cesium.Math.toRadians(degrees);
}

function latLonPositions(points) {
  return points.map(([lat, lon]) => Cesium.Cartesian3.fromDegrees(lon, lat));
}

function closedRing(points) {
  const positions = latLonPositions(points);
  return positions.length ? [...positions, positions[0]] : positions;
}

function polygonHierarchy(rings) {
  const [outer, ...holes] = rings.map((ring) => ring.map(([lon, lat]) => Cesium.Cartesian3.fromDegrees(lon, lat)));
  return new Cesium.PolygonHierarchy(outer, holes.map((hole) => new Cesium.PolygonHierarchy(hole)));
}

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
  const home = Cesium.Rectangle.fromDegrees(west, south, east, north);
  viewer.camera.setView({ destination: home });

  const groups = {};
  const group = (name) => {
    groups[name] = new Cesium.CustomDataSource(name);
    viewer.dataSources.add(groups[name]);
    return groups[name];
  };
  const labelLayer = group("labels");
  const windLayer = group("wind");
  const forecastLayer = group("forecast");
  const layers = [];  // [name, show(visible), shown()] for the layer panel
  let terrainLayer = null;
  let windEntities = [];

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
    // Neither Natural Earth II nor the offline tiles carry names, so they are always drawn.
    wantsLabels: () => true,
    addAttribution: addCredit,

    // OSM land cover as one ground primitive with a colour per instance.
    addTerrain(collection) {
      const instances = [];
      for (const feature of collection.features) {
        const geometry = feature.geometry;
        const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
        const color = cesiumColor(TERRAIN_COLORS[feature.properties.terrain] || "#888888", 0.22);
        for (const rings of polygons) {
          instances.push(new Cesium.GeometryInstance({
            geometry: new Cesium.PolygonGeometry({ polygonHierarchy: polygonHierarchy(rings) }),
            attributes: { color: Cesium.ColorGeometryInstanceAttribute.fromColor(color) },
            id: { kind: "terrain", properties: feature.properties },
          }));
        }
      }
      terrainLayer = viewer.scene.primitives.add(new Cesium.GroundPrimitive({
        geometryInstances: instances,
        appearance: new Cesium.PerInstanceColorAppearance({ flat: true, translucent: true }),
        classificationType: Cesium.ClassificationType.TERRAIN,
      }));
      layers.push(["Terräng (OSM)", (visible) => { terrainLayer.show = visible; }, () => terrainLayer.show]);
    },

    addLabels(collection) {
      for (const feature of collection.features) {
        const [lon, lat] = feature.geometry.coordinates;
        const { name, kind, min_zoom: minZoom } = feature.properties;
        labelLayer.entities.add({
          position: Cesium.Cartesian3.fromDegrees(lon, lat),
          label: {
            text: name, font: LABEL_FONTS[kind] || "12px system-ui, sans-serif",
            fillColor: cesiumColor(kind === "lake" ? "#1f5fa8" : "#2b2b2b"), outlineColor: cesiumColor("#ffffff"), outlineWidth: 3,
            style: Cesium.LabelStyle.FILL_AND_OUTLINE, ...ON_GROUND,
            distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, distanceForZoom(minZoom)),
          },
        });
      }
      layers.push(["Ortnamn", (visible) => { labelLayer.show = visible; }, () => labelLayer.show]);
    },

    addStations(stations) {
      for (const station of stations) {
        viewer.entities.add({
          name: `SMHI ${station.name}`,
          position: Cesium.Cartesian3.fromDegrees(station.longitude, station.latitude),
          point: {
            pixelSize: 10, color: cesiumColor("#ffffff"), outlineColor: cesiumColor("#1f5fa8"), outlineWidth: 3,
            ...ON_GROUND,
          },
          label: {
            text: `SMHI ${station.name}`, font: "14px system-ui, sans-serif", fillColor: cesiumColor("#1b2430"),
            outlineColor: cesiumColor("#ffffff"), outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE,
            pixelOffset: new Cesium.Cartesian2(10, 0), horizontalOrigin: Cesium.HorizontalOrigin.LEFT, ...ON_GROUND,
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

    setupWind(wind, onShow) {
      windEntities = wind.points.map(([lat, lon]) => windLayer.entities.add({
        name: "Vind (ERA5-Land)",
        position: Cesium.Cartesian3.fromDegrees(lon, lat),
        billboard: { image: barbImage(0), alignedAxis: Cesium.Cartesian3.UNIT_Z, show: false, ...ON_GROUND },
      }));
      layers.push(["Vind (ERA5-Land)", (visible) => {
        windLayer.show = visible;
        if (visible) onShow();
      }, () => windLayer.show]);
    },

    showWind(hour, wind) {
      windEntities.forEach((entity, position) => {
        entity.billboard.show = hour >= 0;
        if (hour < 0) return;
        const [speed, from] = wind.values[hour][position];
        entity.billboard.image = barbImage(speed);
        entity.billboard.rotation = northRotation((from + 180) % 360);
        entity.description = windTooltip(position, hour);
      });
    },

    setupForecast() {
      layers.push(["Prognos (modell)", (visible) => { forecastLayer.show = visible; }, () => forecastLayer.show]);
    },

    drawForecast(current, horizon) {
      const entities = forecastLayer.entities;
      entities.removeAll();
      if (!current) return;
      const bands = current.forecast[horizon];
      const outline = (ring, color, width, dashed) => entities.add({
        polyline: {
          positions: closedRing(ring), width, clampToGround: true,
          material: dashed ? new Cesium.PolylineDashMaterialProperty({ color: cesiumColor(color), dashLength: 12 }) : cesiumColor(color),
        },
      });
      const area = (ring, color, alpha) => entities.add({
        polygon: { hierarchy: latLonPositions(ring), material: cesiumColor(color, alpha) },
      });
      area(bands.high, "#ffd54a", 0.18);
      outline(bands.high, "#b7950b", 1.5, true);
      area(bands.central, "#ff8c00", 0.25);
      outline(bands.central, "#d35400", 2, false);
      outline(bands.low, "#7a1f1f", 1.5, true);
      outline(current.front, "#202020", 2.5, false);
      const [lat, lon] = current.front_centre;
      const arrow = (degrees, image) => {
        if (degrees === null || degrees === undefined) return;
        entities.add({
          position: Cesium.Cartesian3.fromDegrees(lon, lat),
          // Moved towards the camera so the arrows are drawn over the hotspots, as in 2D.
          billboard: {
            image, rotation: northRotation(degrees), alignedAxis: Cesium.Cartesian3.UNIT_Z,
            eyeOffset: new Cesium.Cartesian3(0, 0, -2000), ...ON_GROUND,
          },
        });
      };
      arrow(current.model.towards_deg, SPREAD_ARROWS.model);
      arrow(current.observed_spread?.towards_deg, SPREAD_ARROWS.observed);
      for (const place of current.places_within_24h) {
        entities.add({
          name: escapeText(place.names.join(", ")),
          position: Cesium.Cartesian3.fromDegrees(place.longitude, place.latitude),
          point: { pixelSize: 8, color: cesiumColor("#ffd54a"), outlineColor: cesiumColor("#202020"), outlineWidth: 1, ...ON_GROUND },
          description: `${escapeText(place.names.join(", "))}: inom ${escapeText(place.span)} (spann vid dubbel–halv hastighet)`,
        });
      }
    },

    // A layer panel like Leaflet's, in the corner of the globe.
    finish() {
      layers.unshift(["Hotspots", (visible) => { points.show = visible; }, () => points.show]);
      const panel = document.createElement("form");
      panel.className = "layer-panel";
      panel.setAttribute("aria-label", "Lager");
      for (const [name, show, shown] of layers) {
        const label = document.createElement("label");
        const box = document.createElement("input");
        box.type = "checkbox";
        box.checked = shown();
        box.addEventListener("change", () => show(box.checked));
        label.append(box, ` ${name}`);
        panel.append(label);
      }
      viewer.container.append(panel);
    },

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
    } else if (picked?.id?.kind === "terrain") {
      const p = picked.id.properties;
      viewer.selectedEntity = new Cesium.Entity({
        name: escapeText(p.terrain),
        description: `${p.name ? `${escapeText(p.name)}<br>` : ""}<small>OSM ${escapeText(p.osm_tag)}</small>`,
      });
    }
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
  return adapter;
}
