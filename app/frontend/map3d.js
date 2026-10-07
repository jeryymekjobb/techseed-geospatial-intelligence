// Cesium map adapter for the 3D globe (see panel.js for the interface). Runs without
// Cesium ion: the world imagery is the Natural Earth II set shipped with Cesium, the
// fire area uses the same offline OSM tiles as the 2D map, and the terrain is built
// from Copernicus DEM GLO-30 (tools/build_terrain.py).
"use strict";

// The camera route from space to the incident is the scenario's (config.camera_route).
// Last step: look at the fire's centre from the south at this pitch and range.
const FIRE_VIEW = { pitch: -50, range: 42_000, seconds: 2.2 };
// GOD VIEW: the whole of Europe, so satellites and other layers fit around the fire.
const GOD_VIEW = { lon: 15, lat: 55, height: 12_000_000, seconds: 4.0 };
// SPACE VIEW: the satellites' orbits around Scandinavia.
const SPACE_VIEW = { lon: 16, lat: 45, height: 20_000_000, seconds: 4.0 };
// The detection sequence: from the south and high enough to see the satellite and the fire.
const DETECTION_VIEW = { latOffset: -12, height: 2_500_000, pitch: -60, seconds: 3.0 };
const SATELLITE_COLORS = { MODIS: "#ff8c00", VIIRS: "#ff2a00", OLI: "#4fc3f7", SAR: "#b388ff", MSI: "#69f0ae" };
// The flood maps (WMS) over the offline map, partly transparent.
const WMS_ALPHA = 0.7;

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
const BARB_STYLE = "<style>path,circle{fill:none;stroke:#0b3d91;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}"
  + ".halo{stroke:#fff;stroke-width:4.5;opacity:.85}.pennant{fill:#0b3d91}</style>";
const barbImages = new Map();
function barbImage(speed) {
  const svg = windBarbSvg(speed);
  if (!barbImages.has(svg)) barbImages.set(svg, svgImage(svg.replace(/^(<svg [^>]*>)/, `$1${BARB_STYLE}`), 100));
  return barbImages.get(svg);
}

// Spread arrows pointing up (north), as in the 2D map: observed solid red, model dashed orange.
// 180 px with a white edge, to be seen from the back of an auditorium and against the red hotspots.
const SPREAD_HALO = '<path d="M0,0 L0,-30 M-5,-24 L0,-34 L5,-24 Z" stroke="#fff" stroke-width="6" fill="#fff" stroke-linecap="round" stroke-linejoin="round"/>';
const SPREAD_ARROWS = {
  observed: svgImage(`<svg viewBox="-35 -35 70 70">${SPREAD_HALO}<path d="M0,0 L0,-30" stroke="#b3261e" stroke-width="3" fill="none" stroke-linecap="round"/>`
    + '<path d="M-5,-24 L0,-34 L5,-24 Z" fill="#b3261e"/></svg>', 180),
  model: svgImage(`<svg viewBox="-35 -35 70 70">${SPREAD_HALO}<path d="M0,0 L0,-30" stroke="#d35400" stroke-width="2" fill="none" stroke-dasharray="4 3"/>`
    + '<path d="M-5,-24 L0,-34 L5,-24 Z" fill="#d35400"/></svg>', 180),
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
  let clickedAt = null;  // where the latest click on the globe was, in canvas pixels
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
  const addCredit = (text) => { if (text) credits.addStaticCredit(new Cesium.Credit(text, true)); };
  addCredit("Natural Earth II");
  addCredit(config.attribution.firms);
  const [south, west] = config.view_bounds[0];
  const [north, east] = config.view_bounds[1];
  if (config.layers.offline_tiles) {
    const [[mapSouth, mapWest], [mapNorth, mapEast]] = config.map_bounds;
    viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
      url: "/tiles/{z}/{x}/{y}.png", maximumLevel: 18,
      rectangle: Cesium.Rectangle.fromDegrees(mapWest, mapSouth, mapEast, mapNorth),
      credit: new Cesium.Credit("© OpenStreetMap contributors", true),
    }));
  } else {
    addNote(`Offline-kartan är inte igång; 3D-globen visar bara Natural Earth II över ${config.incident_area}.`);
  }
  if (terrainProvider) {
    addCredit(config.attribution.copernicus_dem);
  } else {
    addNote("3D-terrängen är inte byggd (tools/fetch_copernicus_dem.py och tools/build_terrain.py); globen är platt.");
  }
  const home = Cesium.Rectangle.fromDegrees(west, south, east, north);
  viewer.camera.setView({ destination: home });
  const flyToFire = (lon, lat) => new Promise((resolve) => {
    viewer.camera.flyToBoundingSphere(new Cesium.BoundingSphere(Cesium.Cartesian3.fromDegrees(lon, lat), 1), {
      offset: new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(FIRE_VIEW.pitch), FIRE_VIEW.range),
      duration: FIRE_VIEW.seconds, complete: resolve, cancel: resolve,
    });
  });

  const groups = {};
  const group = (name) => {
    groups[name] = new Cesium.CustomDataSource(name);
    viewer.dataSources.add(groups[name]);
    return groups[name];
  };
  const labelLayer = group("labels");
  const windLayer = group("wind");
  const forecastLayer = group("forecast");
  const syntheticLayer = group("synthetic-sensors");
  const queryLayer = group("query");
  const stationLayer = group("stations");
  const satelliteLayer = group("satellites");
  const satelliteEntities = new Map();  // norad -> { point, track }
  const stationEntities = new Map();  // SMHI station id -> entity
  let highlighted = null;  // the detection sequence's satellite: { entry, line }
  const landsatLayers = {};  // composite name -> imagery layer
  const wmsLayers = [];  // the flood maps, kept above the satellite images
  const layers = [];  // [name, show(visible), shown()] for the layer panel
  const layerBoxes = [];  // [checkbox, shown()], kept in step when mission control filters
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
      // Off at the start: draping thousands of land-cover polygons on the 3D terrain halved
      // the frame rate in a measurement (11 -> 5.5 frames per second on Intel graphics);
      // the Landsat image shows the ground as well. It can be switched on in the layer panel.
      terrainLayer.show = false;
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
        stationEntities.set(station.id, stationLayer.entities.add({
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
          description: `SMHI-station ${station.name}, ${station.distance_km} km från ${config.incident_place}`,
        }));
      }
    },

    // New texts for the station labels, by station id (the flood's rain per hour).
    labelStations(texts) {
      for (const [id, text] of Object.entries(texts)) {
        const entity = stationEntities.get(id);
        if (entity) entity.label.text = text;
      }
    },

    // The rain at each station in SMHI's classes (rain.js): the point's size and colour, by station id.
    markRain(classes) {
      for (const [id, rain] of Object.entries(classes)) {
        const entity = stationEntities.get(id);
        if (!entity) continue;
        entity.point.pixelSize = rain.radius * 2;
        entity.point.color = cesiumColor(rain.color);
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
      if (config.incident === "wildfire") {
        layers.unshift(["Hotspots", (visible) => { points.show = visible; }, () => points.show]);
        layers.push(["Syntetiska sensorer", (visible) => { syntheticLayer.show = visible; }, () => syntheticLayer.show]);
      }
      layers.push(["Svar på fråga", (visible) => { queryLayer.show = visible; }, () => queryLayer.show]);
      layers.push([`Satelliter (${config.playback.start_utc.slice(0, 4)})`, (visible) => { satelliteLayer.show = visible; }, () => satelliteLayer.show]);
      const panel = document.createElement("form");
      panel.className = "layer-panel";
      panel.setAttribute("aria-label", "Lager");
      for (const [name, show, shown] of layers) {
        const label = document.createElement("label");
        const box = document.createElement("input");
        box.type = "checkbox";
        box.checked = shown();
        box.addEventListener("change", () => show(box.checked));
        layerBoxes.push([box, shown]);
        label.append(box, ` ${name}`);
        panel.append(label);
      }
      viewer.container.append(panel);
    },

    // Fly from space to the fire; resolves when the camera has arrived.
    flyToIncident() {
      const [lat, lon] = config.fire_centre;
      const flight = config.camera_route.reduce((previous, step) => previous.then(() => new Promise((resolve) => {
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(step.lon, step.lat, step.height),
          orientation: { heading: 0, pitch: Cesium.Math.toRadians(step.pitch), roll: 0 },
          duration: step.seconds,
          easingFunction: Cesium.EasingFunction.QUADRATIC_IN_OUT,
          complete: resolve, cancel: resolve,
        });
      })), Promise.resolve());
      return flight.then(() => flyToFire(lon, lat));
    },

    // The synthetic sensors at the clock (sensor_sim.py): red confirms the fire, grey failed.
    drawSyntheticSensors(result) {
      const entities = syntheticLayer.entities;
      entities.removeAll();
      for (const sensor of result.sensors) {
        const color = SYNTHETIC_COLORS[syntheticState(sensor)];
        entities.add({
          name: `${escapeText(sensor.name)} (syntetisk)`,
          position: Cesium.Cartesian3.fromDegrees(sensor.longitude, sensor.latitude),
          point: { pixelSize: 14, color: cesiumColor(color), outlineColor: cesiumColor("#ffffff"), outlineWidth: 2, ...ON_GROUND },
          label: {
            text: escapeText(sensor.name), font: "14px system-ui, sans-serif", fillColor: cesiumColor("#1b2430"),
            outlineColor: cesiumColor("#ffffff"), outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE,
            pixelOffset: new Cesium.Cartesian2(12, 0), horizontalOrigin: Cesium.HorizontalOrigin.LEFT, ...ON_GROUND,
          },
          description: `${escapeText(syntheticSensorText(sensor))}<br><small>${escapeText(result.label)}</small>`,
        });
      }
    },

    // The result of a prepared question (spatial.py); null clears it.
    drawQueryResult(collection) {
      const entities = queryLayer.entities;
      entities.removeAll();
      for (const feature of collection?.features || []) {
        const { type, coordinates } = feature.geometry;
        const description = escapeText(queryLabel(feature.properties));
        if (type === "Point") {
          entities.add({
            name: description, description, position: Cesium.Cartesian3.fromDegrees(...coordinates),
            point: { pixelSize: 11, color: cesiumColor(QUERY_COLOR), outlineColor: cesiumColor("#ffffff"), outlineWidth: 2, ...ON_GROUND },
          });
        } else if (type === "LineString" || type === "MultiLineString") {
          for (const line of type === "LineString" ? [coordinates] : coordinates) {
            entities.add({
              name: description, description,
              polyline: { positions: line.map(([lon, lat]) => Cesium.Cartesian3.fromDegrees(lon, lat)), width: 4,
                material: cesiumColor(QUERY_COLOR, 0.85), clampToGround: true },
            });
          }
        }
      }
    },

    // GOD VIEW's filter: hide or show a category of layers.
    setCategoryVisible(category, visible) {
      const groups = { space: [points, satelliteLayer], iot: [syntheticLayer], infrastructure: [queryLayer], weather: [windLayer, stationLayer] };
      for (const layer of groups[category] || []) layer.show = visible;
      for (const [box, shown] of layerBoxes) box.checked = shown();
    },

    // The scenario's satellites at the clock (panel.js computes them with orbits.js): a point at
    // its height with its name, and the orbit 50 minutes back and ahead.
    drawSatellites(items) {
      for (const item of items) {
        const color = cesiumColor(SATELLITE_COLORS[item.instrument] || "#d0d0d0");
        const position = Cesium.Cartesian3.fromDegrees(item.point.longitude, item.point.latitude, item.point.height_km * 1000);
        const track = item.track.map((point) => Cesium.Cartesian3.fromDegrees(point.longitude, point.latitude, point.height_km * 1000));
        let entry = satelliteEntities.get(item.norad);
        if (!entry) {
          entry = {
            point: satelliteLayer.entities.add({
              name: escapeText(`${item.name} – ${item.role}`),
              description: escapeText(`${item.name}${item.instrument ? ` (${item.instrument})` : ""}: position ${config.playback.start_utc.slice(0, 4)}, beräknad ur banelement (SGP4) – inte en observation.`),
              position,
              point: { pixelSize: 9, color, outlineColor: cesiumColor("#ffffff"), outlineWidth: 2 },
              label: {
                text: item.name, font: "14px system-ui, sans-serif", fillColor: cesiumColor("#ffffff"),
                outlineColor: cesiumColor("#000000"), outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                pixelOffset: new Cesium.Cartesian2(10, 0), horizontalOrigin: Cesium.HorizontalOrigin.LEFT,
              },
            }),
            trackPositions: track,
          };
          // A callback keeps the orbit dynamic: replacing the positions every tick would
          // rebuild the geometry asynchronously, and it would never be drawn.
          entry.track = satelliteLayer.entities.add({
            polyline: {
              positions: new Cesium.CallbackProperty(() => entry.trackPositions, false),
              width: 2, material: color.withAlpha(0.8), arcType: Cesium.ArcType.NONE,
            },
          });
          satelliteEntities.set(item.norad, entry);
        } else {
          entry.point.position = position;
          entry.trackPositions = track;
        }
      }
    },

    // A detection arrived: a line from the satellite where it observed down to the detection.
    flashSatellite({ norad, from, to, label }) {
      const line = satelliteLayer.entities.add({
        polyline: {
          positions: [Cesium.Cartesian3.fromDegrees(from.longitude, from.latitude, from.height_km * 1000), Cesium.Cartesian3.fromDegrees(to[1], to[0], 0)],
          width: 2.5, material: cesiumColor("#ffd54a", 0.9), arcType: Cesium.ArcType.NONE,
        },
        position: Cesium.Cartesian3.fromDegrees(from.longitude, from.latitude, from.height_km * 1000),
        label: {
          text: label, font: "13px system-ui, sans-serif", fillColor: cesiumColor("#ffd54a"),
          outlineColor: cesiumColor("#000000"), outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          pixelOffset: new Cesium.Cartesian2(10, 18), horizontalOrigin: Cesium.HorizontalOrigin.LEFT,
        },
      });
      const satellite = satelliteEntities.get(norad);
      if (satellite) satellite.point.point.pixelSize = 16;
      setTimeout(() => {
        satelliteLayer.entities.remove(line);
        if (satellite) satellite.point.point.pixelSize = highlighted?.entry === satellite ? 18 : 9;
      }, 4000);
    },

    // The detection sequence's satellite: larger, with a dashed line down to the fire, and
    // with `fly` the camera out far enough to see both; null clears it.
    highlightSatellite(norad, { fly = false } = {}) {
      if (highlighted) {
        satelliteLayer.entities.remove(highlighted.line);
        highlighted.entry.point.point.pixelSize = 9;
        highlighted = null;
      }
      const entry = norad ? satelliteEntities.get(norad) : null;
      if (!entry) return Promise.resolve();
      const [lat, lon] = config.fire_centre;
      const ground = Cesium.Cartesian3.fromDegrees(lon, lat, 0);
      const line = satelliteLayer.entities.add({
        polyline: {
          positions: new Cesium.CallbackProperty((time) => [entry.point.position.getValue(time), ground], false),
          width: 3, material: new Cesium.PolylineDashMaterialProperty({ color: cesiumColor("#e040fb") }), arcType: Cesium.ArcType.NONE,
        },
      });
      entry.point.point.pixelSize = 18;
      highlighted = { entry, line };
      if (!fly) return Promise.resolve();
      return new Promise((resolve) => {
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(lon, lat + DETECTION_VIEW.latOffset, DETECTION_VIEW.height),
          orientation: { heading: 0, pitch: Cesium.Math.toRadians(DETECTION_VIEW.pitch), roll: 0 },
          duration: DETECTION_VIEW.seconds, complete: resolve, cancel: resolve,
        });
      });
    },

    // Mission control's SPACE VIEW: far enough out for the orbits; back to the fire when off.
    showSpaceView(on) {
      if (!on) {
        const [lat, lon] = config.fire_centre;
        return flyToFire(lon, lat);
      }
      return new Promise((resolve) => {
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(SPACE_VIEW.lon, SPACE_VIEW.lat, SPACE_VIEW.height),
          duration: SPACE_VIEW.seconds, complete: resolve, cancel: resolve,
        });
      });
    },

    // The Landsat 8 scene as imagery over the map area, one hidden layer per composite.
    // The scenario's WMS layers (wms.py, through the backend) in the layer panel; `visible` start shown.
    addWms(source) {
      const [[south, west], [north, east]] = config.map_bounds;
      for (const [name, title] of Object.entries(source.layers)) {
        const layer = viewer.imageryLayers.addImageryProvider(new Cesium.WebMapServiceImageryProvider({
          url: source.url, layers: name, rectangle: Cesium.Rectangle.fromDegrees(west, south, east, north),
          parameters: { transparent: true, format: "image/png" },
        }));
        layer.alpha = WMS_ALPHA;
        wmsLayers.push(layer);
        layer.show = (source.visible || []).includes(name);
        layers.push([`${title} (modell)`, (visible) => { layer.show = visible; }, () => layer.show]);
      }
    },

    setupLandsat(info) {
      const [[south, west], [north, east]] = info.bounds;
      const rectangle = Cesium.Rectangle.fromDegrees(west, south, east, north);
      // One hidden layer per scene and image, keyed "scene|image" as landsat.js names them.
      const images = info.scenes.flatMap((scene) => Object.entries(scene.images).map(([name, url]) => [`${scene.scene}|${name}`, url]));
      return Promise.all(images.map(async ([key, url]) => {
        const layer = viewer.imageryLayers.addImageryProvider(await Cesium.SingleTileImageryProvider.fromUrl(url, { rectangle }));
        layer.show = false;
        landsatLayers[key] = layer;
      })).then(() => {
        for (const layer of wmsLayers) viewer.imageryLayers.raiseToTop(layer);
      });
    },

    showLandsat(name) {
      for (const [key, layer] of Object.entries(landsatLayers)) layer.show = key === name;
    },

    // Show an evidence object from the assessment.
    focusOn(lat, lon) {
      return flyToFire(lon, lat);
    },

    // Mission control's GOD VIEW: out to Europe, and back to the fire when it is switched off.
    showGodView(on) {
      if (!on) {
        const [lat, lon] = config.fire_centre;
        return flyToFire(lon, lat);
      }
      return new Promise((resolve) => {
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(GOD_VIEW.lon, GOD_VIEW.lat, GOD_VIEW.height),
          duration: GOD_VIEW.seconds, complete: resolve, cancel: resolve,
        });
      });
    },

    flyHome() {
      viewer.camera.flyTo({ destination: home, duration: 3 });
    },

    // A right click on the ground: callback({ latitude, longitude, x, y }) with the page
    // position of the click. Cesium reports a click only when the mouse did not move, so
    // a right-drag still zooms.
    onContextMenu(callback) {
      viewer.scene.canvas.addEventListener("contextmenu", (event) => event.preventDefault());
      new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas).setInputAction((click) => {
        const ray = viewer.camera.getPickRay(click.position);
        const ground = (ray && viewer.scene.globe.pick(ray, viewer.scene)) || viewer.camera.pickEllipsoid(click.position);
        if (!ground) return;
        const place = Cesium.Cartographic.fromCartesian(ground);
        const box = viewer.scene.canvas.getBoundingClientRect();
        callback({
          latitude: Cesium.Math.toDegrees(place.latitude), longitude: Cesium.Math.toDegrees(place.longitude),
          x: box.left + click.position.x, y: box.top + click.position.y,
        });
      }, Cesium.ScreenSpaceEventType.RIGHT_CLICK);
    },
  };

  // Show the FIRMS details when a hotspot is clicked.
  new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas).setInputAction((movement) => {
    clickedAt = Cesium.Cartesian2.clone(movement.position);
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
  viewer.scene.postRender.addEventListener(placeInfoBox);
  return adapter;

  // The info box beside what was clicked, following it as the camera moves, and clear of the
  // layer panel; at the click for what has no position of its own (FIRMS hotspots, terrain).
  function placeInfoBox() {
    const box = viewer.container.querySelector(".cesium-infoBox");
    if (!box) return;
    const entity = viewer.selectedEntity;
    box.classList.toggle("anchored", Boolean(entity));
    if (!entity) return;
    const at = infoBoxAnchor(entity);
    box.style.visibility = at ? "" : "hidden";  // behind the globe or out of view
    if (!at) return;
    const gap = 16;
    const margin = 8;
    const width = viewer.container.clientWidth;
    const height = viewer.container.clientHeight;
    const boxWidth = box.offsetWidth;
    const boxHeight = box.offsetHeight;
    const top = Math.min(Math.max(at.y - boxHeight / 2, margin), Math.max(margin, height - boxHeight - margin));
    const panel = viewer.container.querySelector(".layer-panel");
    const overlapsPanel = (left) => panel && panel.offsetParent !== null
      && left < panel.offsetLeft + panel.offsetWidth && left + boxWidth > panel.offsetLeft
      && top < panel.offsetTop + panel.offsetHeight && top + boxHeight > panel.offsetTop;
    const right = at.x + gap;
    const leftSide = at.x - gap - boxWidth;
    const onLeft = (right + boxWidth > width - margin || overlapsPanel(right)) && leftSide >= margin;
    box.style.left = `${onLeft ? leftSide : right}px`;
    box.style.top = `${top}px`;
    box.dataset.side = onLeft ? "left" : "right";
    box.style.setProperty("--pointer-y", `${Math.min(Math.max(at.y - top, 14), boxHeight - 14)}px`);
  }

  function infoBoxAnchor(entity) {
    const scene = viewer.scene;
    let world = entity.position?.getValue(viewer.clock.currentTime);
    if (!world) return clickedAt;
    const place = Cesium.Cartographic.fromCartesian(world);
    const ground = place && place.height < 1 ? scene.globe.getHeight(place) : undefined;  // clamped to the terrain
    if (ground !== undefined) world = Cesium.Cartesian3.fromRadians(place.longitude, place.latitude, ground);
    const occluder = new Cesium.EllipsoidalOccluder(Cesium.Ellipsoid.WGS84, scene.camera.positionWC);
    if (!occluder.isPointVisible(world)) return null;
    const screen = Cesium.SceneTransforms.worldToWindowCoordinates(scene, world);
    if (!screen || screen.x < 0 || screen.y < 0 || screen.x > scene.canvas.clientWidth || screen.y > scene.canvas.clientHeight) return null;
    return screen;
  }
}
