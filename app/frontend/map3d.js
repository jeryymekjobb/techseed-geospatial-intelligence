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
// The weather chart's view ("Väderkarta (MET Norway)"): Scandinavia on the flat map (2D).
const WEATHER_CHART_RECTANGLE = [4, 55, 31, 70];
// The weather chart's lightning: a yellow bolt with a dark edge.
const LIGHTNING_IMAGE = svgImage('<svg viewBox="0 0 24 32"><path d="M14 1 L3 18 H11 L8 31 L21 12 H13 Z" fill="#ffd400" '
  + 'stroke="#3a2a00" stroke-width="1.5" stroke-linejoin="round"/></svg>', 28);
// SPACE VIEW: the satellites' orbits around Scandinavia.
const SPACE_VIEW = { lon: 16, lat: 45, height: 20_000_000, seconds: 4.0 };
// With a geostationary satellite (Meteosat, 42 164 km from the Earth's centre over 0 degrees) SPACE
// VIEW looks from DISTANCE m out in the direction of FROM at a point between the Earth's far side
// and the satellite, so both the incident and the satellite fit; the Earth is then about a quarter
// of the screen's height.
const SPACE_VIEW_GEO = { target_m: 17_896_000, from: { lat: 30, lon: 10 }, distance: 60_000_000, seconds: 4.0 };
// The detection sequence: from the south and high enough to see the satellite and the fire.
const DETECTION_VIEW = { latOffset: -12, height: 2_500_000, pitch: -60, seconds: 3.0 };
const SATELLITE_COLORS = { MODIS: "#ff8c00", VIIRS: "#ff2a00", OLI: "#4fc3f7", SAR: "#b388ff", MSI: "#69f0ae" };
// The flood maps (WMS) over the offline map, partly transparent.
const WMS_ALPHA = 0.7;
// The municipality's map is drawn from this zoom on (its coarser tiles carry huge place names).
const MUNICIPAL_MIN_LEVEL = 11;

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
const FORECAST_BARB = "#c2410c";  // MET Norway's forecast wind: orange, apart from ERA5-Land's blue
function barbImage(speed, colour = "#0b3d91") {
  const svg = windBarbSvg(speed);
  const key = `${colour}${svg}`;
  if (!barbImages.has(key)) barbImages.set(key, svgImage(svg.replace(/^(<svg [^>]*>)/, `$1${BARB_STYLE.replaceAll("#0b3d91", colour)}`), 100));
  return barbImages.get(key);
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
  // Mission control's base maps over Natural Earth II (basemaps.js): the offline map over the
  // map area and, made when first ticked, OSM online.
  const baseById = {};
  if (config.layers.offline_tiles) {
    const [[mapSouth, mapWest], [mapNorth, mapEast]] = config.map_bounds;
    baseById.offline = viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
      url: "/tiles/{z}/{x}/{y}.png", maximumLevel: 18,
      rectangle: Cesium.Rectangle.fromDegrees(mapWest, mapSouth, mapEast, mapNorth),
      credit: new Cesium.Credit("© OpenStreetMap contributors", true),
    }));
  } else {
    addNote(`Offline-kartan är inte igång; 3D-globen visar bara Natural Earth II över ${config.incident_area}.`);
  }
  const municipal = config.layers.municipal_basemap;
  if (municipal) {
    // The municipality's map, kept locally (municipal_basemap.py), over its fetched area and zooms. Its
    // place names are drawn into the tiles, so from MUNICIPAL_MIN_LEVEL only: a tilted camera would
    // otherwise show the coarse tiles' names huge on the ground far off.
    const [[municipalSouth, municipalWest], [municipalNorth, municipalEast]] = municipal.bounds;
    baseById[municipal.id] = viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
      url: municipal.url, minimumLevel: Math.max(municipal.min_zoom, MUNICIPAL_MIN_LEVEL), maximumLevel: municipal.max_zoom,
      rectangle: Cesium.Rectangle.fromDegrees(municipalWest, municipalSouth, municipalEast, municipalNorth),
      credit: new Cesium.Credit(municipal.attribution, true),
    }));
    baseById[municipal.id].show = false;
  }
  // The offline map's road numbers and railway tunnels over any base map (offline_tiles.py), kept above
  // every imagery layer added or raised later (images, flood maps, radar).
  let roadOverlayLayer = null;
  if (config.layers.road_overlay) {
    const [[overlaySouth, overlayWest], [overlayNorth, overlayEast]] = config.map_bounds;
    roadOverlayLayer = viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
      url: config.layers.road_overlay.url, maximumLevel: 18,
      rectangle: Cesium.Rectangle.fromDegrees(overlayWest, overlaySouth, overlayEast, overlayNorth),
      credit: new Cesium.Credit(config.layers.road_overlay.attribution, true),
    }));
    const keepOnTop = (layer) => {
      if (layer !== roadOverlayLayer) viewer.imageryLayers.raiseToTop(roadOverlayLayer);
    };
    viewer.imageryLayers.layerAdded.addEventListener(keepOnTop);
    viewer.imageryLayers.layerMoved.addEventListener(keepOnTop);
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
  const forecastWindLayer = group("forecast-wind");  // MET Norway's forecast wind (met_forecast.py)
  forecastWindLayer.show = false;
  const isobarLayer = group("isobars");  // MET Norway's weather chart (met_forecast.py isobars)
  isobarLayer.show = false;
  const lightningLayer = group("lightning");  // SMHI's observed lightning
  const dailyRainLayer = group("daily-rain");  // SMHI's rain by the day (daily_rain.py)
  let dailyRainVisible = true;
  const routeExposureLayer = group("route-exposure");  // roads and railways under heavy rain, computed (routes.py)
  const routeImpactLayer = group("route-impacts");  // roads and railways the incident damaged, documented
  const meteosatLayer = group("meteosat");  // Meteosat's fire pixels (meteosat.py)
  const frmLayer = group("fire-risk");  // LSA SAF's fire risk (meteosat_frm.py), off until ticked
  frmLayer.show = false;
  let frmVisible = false;
  const cthLayer = group("cloud-tops");  // Meteosat's cloud top height (meteosat_cth.py), off until ticked
  cthLayer.show = false;
  let cthVisible = false;
  let wideSpaceView = false;  // a geostationary satellite is drawn (hasGeostationary in orbits.js)
  const forecastLayer = group("forecast");
  const syntheticLayer = group("synthetic-sensors");
  const queryLayer = group("query");
  const threatLayer = group("threats");
  const stationLayer = group("stations");
  const satelliteLayer = group("satellites");
  const satelliteEntities = new Map();  // norad -> { point, track }
  const stationEntities = new Map();  // SMHI station id -> entity
  let highlighted = null;  // the detection sequence's satellite: { entry, line }
  const landsatLayers = {};  // composite name -> imagery layer
  const wmsLayers = [];  // the flood maps, normally above satellite images; radar-water is raised above them
  const wmsNames = new Map();  // imagery layer -> WMS layer name
  let wmsListener = () => {};
  const emsLayer = new Cesium.CustomDataSource("ems");
  let shownLandsatKey = null;
  let radarRectangle = null;  // SMHI's radar: one imagery layer at a time, replaced as the clock goes
  let radarLayer = null;
  let radarUrl = null;
  let radarVisible = true;
  let weatherCategoryVisible = true;
  let windVisible = true;
  let forecastWindVisible = false;
  let isobarVisible = false;
  let lightningVisible = true;
  let viewBeforeChart = null;  // the scene mode and camera to come back to when the weather chart is unticked
  const layers = [];  // [name, show(visible), shown()] for the layer panel
  if (roadOverlayLayer) {
    layers.push([config.layers.road_overlay.label, (visible) => { roadOverlayLayer.show = visible; }, () => roadOverlayLayer.show]);
  }
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
    dimension: "3d",
    wantsLabels: () => true,

    // Mission control's base map (basemaps.js baseMapFor): its id, or null for Natural Earth II only.
    // OSM online and the municipality's map have their own names, so the drawn place names are hidden over them.
    setBaseMap(id) {
      labelLayer.show = id !== "online" && id !== municipal?.id;
      if (id === "online" && !baseById.online) {
        baseById.online = viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
          url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png", maximumLevel: 19,
          credit: new Cesium.Credit("© OpenStreetMap contributors", true),
        }), 1);
      }
      for (const [key, layer] of Object.entries(baseById)) layer.show = key === id;
    },
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

    // style: { color, fill } for another kind of station (the flood's flows and lake levels).
    addStations(stations, style = {}) {
      for (const station of stations) {
        stationEntities.set(station.id, stationLayer.entities.add({
          name: `SMHI ${station.name}`,
          position: Cesium.Cartesian3.fromDegrees(station.longitude, station.latitude),
          point: {
            pixelSize: 10, color: cesiumColor(style.fill || "#ffffff"), outlineColor: cesiumColor(style.color || "#1f5fa8"), outlineWidth: 3,
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
      const middle = windGridMiddle(wind.points);
      windEntities = wind.points.map(([lat, lon], index) => windLayer.entities.add({
        name: `Vind (${wind.sources?.[index] || "ERA5-Land"})`,
        position: Cesium.Cartesian3.fromDegrees(lon, lat),
        billboard: { image: barbImage(0), alignedAxis: Cesium.Cartesian3.UNIT_Z, show: false, ...ON_GROUND,
                     // Fewer arrows further out, as in 2D (windMinZoom in wind_barbs.js).
                     distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, distanceForZoom(windMinZoom(lat, lon, middle))) },
      }));
      layers.push(["Vind (ERA5-Land)", (visible) => {
        windVisible = visible;
        windLayer.show = visible && weatherCategoryVisible;
        if (windLayer.show) onShow();
      }, () => windVisible && weatherCategoryVisible]);
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

    // MET Norway's forecast wind some hours ahead, as orange barbs; off until mission control ticks it.
    setupForecastWind() {
      layers.push(["Prognosvind (MET Norway)", (visible) => {
        forecastWindVisible = visible;
        forecastWindLayer.show = visible && weatherCategoryVisible;
      }, () => forecastWindVisible && weatherCategoryVisible]);
    },

    drawForecastWind(points, hoursAhead) {
      forecastWindLayer.entities.removeAll();
      for (const point of points || []) {
        forecastWindLayer.entities.add({
          name: `Prognosvind om ${hoursAhead} timmar (MET Norway)`,
          description: `${String(point.wind_ms).replace(".", ",")} m/s`,
          position: Cesium.Cartesian3.fromDegrees(point.longitude, point.latitude),
          billboard: { image: barbImage(point.wind_ms, FORECAST_BARB), alignedAxis: Cesium.Cartesian3.UNIT_Z,
                       rotation: northRotation((point.wind_from_deg + 180) % 360), ...ON_GROUND },
        });
      }
    },

    // MET Norway's weather chart: the rain of three hours, isobars every hPa (each fourth with its value), H and L,
    // and lightning; off until ticked.
    setupWeatherChart() {
      layers.push(["Väderkarta (MET Norway)", (visible) => {
        isobarVisible = visible;
        isobarLayer.show = visible && weatherCategoryVisible;
      }, () => isobarVisible && weatherCategoryVisible]);
    },

    drawWeatherChart(chart) {
      const entities = isobarLayer.entities;
      entities.removeAll();
      const text = (latitude, longitude, value, font, colour) => entities.add({
        position: Cesium.Cartesian3.fromDegrees(longitude, latitude),
        label: { text: value, font, fillColor: cesiumColor(colour), outlineColor: cesiumColor("#ffffff"), outlineWidth: 3,
                 style: Cesium.LabelStyle.FILL_AND_OUTLINE, ...ON_GROUND },
      });
      if (chart?.rain_png) {
        const [[south, west], [north, east]] = chart.rain_bounds;
        entities.add({ rectangle: { coordinates: Cesium.Rectangle.fromDegrees(west, south, east, north),
                                    material: new Cesium.ImageMaterialProperty({ image: chart.rain_png, transparent: true }) } });
      }
      for (const mark of chart?.thunder || []) {
        entities.add({ position: Cesium.Cartesian3.fromDegrees(mark.longitude, mark.latitude), billboard: { image: LIGHTNING_IMAGE, ...ON_GROUND } });
      }
      for (const line of chart?.lines || []) {
        // Every hPa; each fourth (1000, 1004 …) bolder and with its value, as on weather charts.
        const main = line.hpa % 4 === 0;
        entities.add({ polyline: { positions: Cesium.Cartesian3.fromDegreesArray(line.coords.flatMap(([lat, lon]) => [lon, lat])),
                                   width: main ? 1.8 : 0.8, clampToGround: true, material: cesiumColor("#1f3a7a", main ? 0.9 : 0.6) } });
        if (!main) continue;
        const [lat, lon] = line.coords[Math.floor(line.coords.length / 2)];
        text(lat, lon, String(line.hpa), "12px system-ui, sans-serif", "#1f3a7a");
      }
      for (const centre of chart?.centres || []) {
        text(centre.latitude, centre.longitude, `${centre.kind} ${centre.hpa}`, "bold 22px system-ui, sans-serif", centre.kind === "H" ? "#1f3a7a" : "#b3261e");
      }
    },

    // SMHI's observed lightning: the flashes to the ground of the last hour, yellow fading to orange.
    setupLightning() {
      layers.push(["Blixtar (SMHI, observerade)", (visible) => {
        lightningVisible = visible;
        lightningLayer.show = visible && weatherCategoryVisible;
      }, () => lightningVisible && weatherCategoryVisible]);
    },

    // `history`: the flashes near the incident since the start, red, with their time when clicked.
    drawLightning(strikes, history) {
      const entities = lightningLayer.entities;
      entities.removeAll();
      const image = (colour, size) => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(lightningSvg(colour, size))}`;
      for (const strike of history || []) {
        entities.add({ name: "Blixtnedslag (SMHI, observerat)", description: `${formatLightningTime(strike.utc)}, ${strike.ka} kA`,
                       position: Cesium.Cartesian3.fromDegrees(strike.longitude, strike.latitude),
                       billboard: { image: image(LIGHTNING_NEAR_COLOUR, 22), ...ON_GROUND } });
      }
      for (const strike of strikes || []) {
        entities.add({ position: Cesium.Cartesian3.fromDegrees(strike.longitude, strike.latitude),
                       billboard: { image: image(lightningColour(strike.age_min), 16), color: Cesium.Color.WHITE.withAlpha(Math.max(0.35, 1 - strike.age_min / 80)),
                                    ...ON_GROUND } });
      }
    },

    // Roads and railways (routes.py): the computed pieces under heavy rain as coloured lines on the
    // ground, and the documented damage as markers with the report's text when clicked.
    setupRoutes(info, hasExposure) {
      if (hasExposure) {
        layers.push([info.exposure_label, (visible) => { routeExposureLayer.show = visible; }, () => routeExposureLayer.show]);
      }
      layers.push([info.impact_label, (visible) => { routeImpactLayer.show = visible; }, () => routeImpactLayer.show]);
    },

    // Meteosat's fire pixels: a purple rectangle of each pixel's area on the ground, with its edge.
    setupMeteosat(label) {
      layers.push([label, (visible) => { meteosatLayer.show = visible; }, () => meteosatLayer.show]);
    },

    drawMeteosat(items) {
      meteosatLayer.entities.removeAll();
      for (const item of items) {
        const corners = item.footprint.flatMap(([lat, lon]) => [lon, lat]);
        meteosatLayer.entities.add({
          name: `${item.satellite} (geostationär)`,
          description: item.text,
          polygon: { hierarchy: Cesium.Cartesian3.fromDegreesArray(corners), material: cesiumColor(METEOSAT_COLOUR, meteosatOpacity(item.frp_mw)),
                     classificationType: Cesium.ClassificationType.BOTH },
        });
        meteosatLayer.entities.add({
          polyline: { positions: Cesium.Cartesian3.fromDegreesArray([...corners, corners[0], corners[1]]), width: 2,
                      material: cesiumColor(METEOSAT_COLOUR, METEOSAT_EDGE_OPACITY), clampToGround: true },
        });
      }
    },

    // LSA SAF's fire risk: a cell of 0.05° in the risk class's colour on the ground.
    setupMeteosatFrm(label) {
      layers.push([label, (visible) => {
        frmVisible = visible;
        frmLayer.show = visible && weatherCategoryVisible;
      }, () => frmVisible && weatherCategoryVisible]);
    },

    drawMeteosatFrm(cells) {
      frmLayer.entities.removeAll();
      for (const cell of cells) {
        frmLayer.entities.add({
          name: "Brandrisk (LSA SAF)",
          description: cell.text,
          rectangle: { coordinates: Cesium.Rectangle.fromDegrees(cell.west, cell.south, cell.east, cell.north),
                       material: cesiumColor(FRM_COLOURS[cell.risk], FRM_OPACITY), classificationType: Cesium.ClassificationType.BOTH },
        });
      }
    },

    // Meteosat's cloud tops: each cell of the quarter in its height's colour on the ground.
    setupMeteosatCth(label) {
      layers.push([label, (visible) => {
        cthVisible = visible;
        cthLayer.show = visible && weatherCategoryVisible;
      }, () => cthVisible && weatherCategoryVisible]);
    },

    drawMeteosatCth(cells) {
      cthLayer.entities.removeAll();
      for (const cell of cells) {
        cthLayer.entities.add({
          name: "Molntopp (Meteosat)",
          description: cell.text,
          polygon: { hierarchy: Cesium.Cartesian3.fromDegreesArray(cell.corners.flatMap(([lat, lon]) => [lon, lat])),
                     material: cesiumColor(cthColour(cell.km), CTH_OPACITY), classificationType: Cesium.ClassificationType.BOTH },
        });
      }
    },

    // SMHI's rain by the day: a dark blue point with the station's latest ended day.
    setupDailyRain(info) {
      layers.push([info.label, (visible) => {
        dailyRainVisible = visible;
        dailyRainLayer.show = visible && weatherCategoryVisible;
      }, () => dailyRainVisible && weatherCategoryVisible]);
    },

    drawDailyRain(items) {
      dailyRainLayer.entities.removeAll();
      for (const item of items) {
        dailyRainLayer.entities.add({
          name: item.text, description: item.detail,
          position: Cesium.Cartesian3.fromDegrees(item.longitude, item.latitude),
          point: { pixelSize: 12, color: cesiumColor("#123f8c"), outlineColor: cesiumColor("#ffffff"), outlineWidth: 2, ...ON_GROUND },
          label: { text: item.text, font: "bold 14px system-ui, sans-serif", fillColor: cesiumColor("#ffffff"), outlineColor: cesiumColor("#123f8c"),
                   outlineWidth: 4, style: Cesium.LabelStyle.FILL_AND_OUTLINE, pixelOffset: new Cesium.Cartesian2(10, 0),
                   horizontalOrigin: Cesium.HorizontalOrigin.LEFT, ...ON_GROUND },
        });
      }
    },

    drawRoutes(impacts, pieces) {
      routeExposureLayer.entities.removeAll();
      for (const piece of pieces) {
        routeExposureLayer.entities.add({
          name: piece.ref || piece.name || (piece.kind === "rail" ? "Järnväg" : "Väg"),
          description: `${Math.round(piece.rain)} mm regn sedan start (beräknat ur radar – inte observerade skador)`,
          polyline: { positions: Cesium.Cartesian3.fromDegreesArray(piece.coords.flatMap(([lat, lon]) => [lon, lat])),
                      width: piece.kind === "rail" ? 5 : 4, material: cesiumColor(ROUTE_EXPOSURE_COLOURS[piece.level], 0.9), clampToGround: true },
        });
      }
      routeImpactLayer.entities.removeAll();
      for (const item of impacts) {
        const colour = ROUTE_IMPACT_COLOURS[item.kind] || "#d62828";
        const shape = item.kind === "rail" ? '<rect x="3" y="3" width="26" height="26" rx="4"' : '<circle cx="16" cy="16" r="13"';
        const image = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32">${shape} `
          + `fill="${colour}" stroke="#ffffff" stroke-width="3"/><text x="16" y="22" font-family="system-ui" font-weight="bold" `
          + 'font-size="18" fill="#ffffff" text-anchor="middle">!</text></svg>')}`;
        routeImpactLayer.entities.add({
          name: item.text,
          description: `${formatLocal(item.time_utc)}${item.approximate_time ? " (tid ungefärlig)" : ""}; plats ungefärlig. ${item.source_label || "Länsstyrelsen, utredning 2026"}.`,
          position: Cesium.Cartesian3.fromDegrees(item.longitude, item.latitude),
          billboard: { image, width: 26, height: 26, ...ON_GROUND },
        });
      }
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
      layers.push(["Hotad bebyggelse", (visible) => { threatLayer.show = visible; }, () => threatLayer.show]);
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
      // Only for troubleshooting (?controls=1): mission control switches the layers.
      if (showControls()) viewer.container.append(panel);
    },

    // Mission control's layer ticks (the status's map_layers): false when the globe has no such layer yet.
    setLayerVisible(name, visible) {
      const entry = layers.find(([layerName]) => layerName === name);
      if (!entry) return false;
      entry[1](visible);
      for (const [box, shown] of layerBoxes) box.checked = shown();
      return true;
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

    // The threatened places (satlog.js threatMarks): the newest threat's large with its name, the
    // earlier ones a small icon, so the many places of a long fire do not hide the newest.
    drawThreats(marks) {
      const entities = threatLayer.entities;
      entities.removeAll();
      for (const mark of marks) {
        const size = mark.latest ? 64 : 24;
        // The newest moved towards the camera, so it is drawn over the earlier ones and the hotspots.
        const front = { eyeOffset: new Cesium.Cartesian3(0, 0, mark.latest ? -3000 : -1000) };
        entities.add({
          name: escapeText(mark.name), position: Cesium.Cartesian3.fromDegrees(mark.longitude, mark.latitude),
          billboard: { image: svgImage(THREAT_ICON_SVG, size), width: size, height: size * 58 / 64, ...front, ...ON_GROUND },
          label: mark.latest ? {
            text: mark.name, font: "bold 24px system-ui, sans-serif", fillColor: cesiumColor("#ffffff"),
            showBackground: true, backgroundColor: cesiumColor("#8b0f17", 0.92), backgroundPadding: new Cesium.Cartesian2(12, 8),
            pixelOffset: new Cesium.Cartesian2(size / 2 + 8, 0), horizontalOrigin: Cesium.HorizontalOrigin.LEFT, ...front, ...ON_GROUND,
          } : undefined,
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
      if (category === "weather") {
        weatherCategoryVisible = visible;
        windLayer.show = visible && windVisible;
        forecastWindLayer.show = visible && forecastWindVisible;
        isobarLayer.show = visible && isobarVisible;
        lightningLayer.show = visible && lightningVisible;
        dailyRainLayer.show = visible && dailyRainVisible;
        frmLayer.show = visible && frmVisible;
        cthLayer.show = visible && cthVisible;
        stationLayer.show = visible;
        if (radarLayer) radarLayer.show = visible && radarVisible;
        for (const [box, shown] of layerBoxes) box.checked = shown();
        return;
      }
      const groups = { space: [points, satelliteLayer, meteosatLayer], iot: [syntheticLayer], infrastructure: [queryLayer, threatLayer, routeImpactLayer, routeExposureLayer] };
      for (const layer of groups[category] || []) layer.show = visible;
      for (const [box, shown] of layerBoxes) box.checked = shown();
    },

    // The scenario's satellites at the clock (panel.js computes them with orbits.js): a point at
    // its height with its name, and the orbit 50 minutes back and ahead (none for a satellite that
    // sends the scenario no data: an empty track).
    drawSatellites(items) {
      wideSpaceView = hasGeostationary(items);
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
        if (wideSpaceView) {
          const target = new Cesium.Cartesian3(SPACE_VIEW_GEO.target_m, 0, 0);
          const from = Cesium.Cartesian3.normalize(Cesium.Cartesian3.fromDegrees(SPACE_VIEW_GEO.from.lon, SPACE_VIEW_GEO.from.lat), new Cesium.Cartesian3());
          const destination = Cesium.Cartesian3.add(target, Cesium.Cartesian3.multiplyByScalar(from, SPACE_VIEW_GEO.distance, new Cesium.Cartesian3()), new Cesium.Cartesian3());
          const direction = Cesium.Cartesian3.normalize(Cesium.Cartesian3.subtract(target, destination, new Cesium.Cartesian3()), new Cesium.Cartesian3());
          // North up: the Earth's axis without its part along the view.
          const along = Cesium.Cartesian3.multiplyByScalar(direction, Cesium.Cartesian3.dot(Cesium.Cartesian3.UNIT_Z, direction), new Cesium.Cartesian3());
          const up = Cesium.Cartesian3.normalize(Cesium.Cartesian3.subtract(Cesium.Cartesian3.UNIT_Z, along, new Cesium.Cartesian3()), new Cesium.Cartesian3());
          viewer.camera.flyTo({ destination, orientation: { direction, up }, duration: SPACE_VIEW_GEO.seconds, complete: resolve, cancel: resolve });
          return;
        }
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
          // No GetFeatureInfo on a click: the backend forwards only GetMap (wms.py).
          enablePickFeatures: false,
        }));
        layer.alpha = WMS_ALPHA;
        wmsLayers.push(layer);
        wmsNames.set(layer, name);
        layer.show = (source.visible || []).includes(name);
        layers.push([`${title} (modell)`, (visible) => { layer.show = visible; wmsListener(); }, () => layer.show]);
      }
    },

    // Copernicus EMS's perimeter of the fire: the product shown by the clock as a dashed outline on the ground.
    setupEms() {
      viewer.dataSources.add(emsLayer);
      layers.push(["Brandområde (Copernicus EMS)", (visible) => { emsLayer.show = visible; }, () => emsLayer.show]);
    },

    drawEms(product) {
      emsLayer.entities.removeAll();
      if (!product) return;
      for (const polygon of product.geometry.coordinates) {
        for (const ring of polygon) {
          emsLayer.entities.add({ polyline: {
            positions: ring.map(([lon, lat]) => Cesium.Cartesian3.fromDegrees(lon, lat)), width: 3, clampToGround: true,
            material: new Cesium.PolylineDashMaterialProperty({ color: cesiumColor("#7b1fa2"), dashLength: 14 }),
          } });
        }
      }
    },

    // SMHI's weather radar: an imagery layer per frame, the old one removed once the new is there.
    setupRadar(info) {
      const [[south, west], [north, east]] = info.bounds;
      radarRectangle = Cesium.Rectangle.fromDegrees(west, south, east, north);
      layers.push(["Nederbörd (SMHI radar)", (visible) => {
        radarVisible = visible;
        if (radarLayer) radarLayer.show = visible && weatherCategoryVisible;
      }, () => radarVisible && weatherCategoryVisible]);
    },

    showRadar(url) {
      radarUrl = url;
      if (!url) {
        if (radarLayer) viewer.imageryLayers.remove(radarLayer, true);
        radarLayer = null;
        return;
      }
      Cesium.SingleTileImageryProvider.fromUrl(url, { rectangle: radarRectangle }).then((provider) => {
        if (radarUrl !== url) return;  // a newer frame came while this one loaded
        const next = viewer.imageryLayers.addImageryProvider(provider);
        next.alpha = 0.85;
        next.show = radarVisible && weatherCategoryVisible;
        if (radarLayer) viewer.imageryLayers.remove(radarLayer, true);
        radarLayer = next;
        if (shownLandsatKey?.endsWith("|radarwater") && landsatLayers[shownLandsatKey]) {
          viewer.imageryLayers.raiseToTop(landsatLayers[shownLandsatKey]);
        }
      }).catch(() => {});
    },

    // callback(names) with the WMS layers shown, now and whenever one is switched on or off.
    onWmsChange(callback) {
      wmsListener = () => callback(wmsLayers.filter((layer) => layer.show).map((layer) => wmsNames.get(layer)));
      wmsListener();
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
      shownLandsatKey = name;
      for (const [key, layer] of Object.entries(landsatLayers)) layer.show = key === name;
      // This image is transparent except for its computed red water mask, which must overlay flood-map fills.
      if (name && name.endsWith("|radarwater") && landsatLayers[name]) {
        viewer.imageryLayers.raiseToTop(landsatLayers[name]);
      } else {
        for (const layer of wmsLayers) viewer.imageryLayers.raiseToTop(layer);
      }
    },

    // Show an evidence object from the assessment.
    focusOn(lat, lon) {
      return flyToFire(lon, lat);
    },

    // The weather chart: the flat map (2D) over Scandinavia when its layer is ticked, and back to the
    // scene mode and view one had when it is unticked.
    showWeatherChartView(on) {
      const scene = viewer.scene;
      if (on) {
        const camera = viewer.camera;
        viewBeforeChart = { mode: scene.mode, position: camera.position.clone(), direction: camera.direction.clone(), up: camera.up.clone() };
        scene.morphTo2D(0);
        viewer.camera.setView({ destination: Cesium.Rectangle.fromDegrees(...WEATHER_CHART_RECTANGLE) });
      } else if (viewBeforeChart) {
        const before = viewBeforeChart;
        viewBeforeChart = null;
        if (before.mode === Cesium.SceneMode.SCENE3D) scene.morphTo3D(0);
        viewer.camera.setView({ destination: before.position, orientation: { direction: before.direction, up: before.up } });
      }
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
