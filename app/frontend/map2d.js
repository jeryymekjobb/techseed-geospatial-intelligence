// Leaflet map adapter for the 2D fire map (see panel.js for the interface).
"use strict";

function spreadArrowIcon(observedDeg, modelDeg) {
  const arrow = (deg, cls) => (deg === null || deg === undefined ? "" :
    `<g transform="rotate(${deg})"><path d="M0,0 L0,-30 M-5,-24 L0,-34 L5,-24 Z" class="halo"></path><path d="M0,0 L0,-30" class="${cls}"></path><path d="M-5,-24 L0,-34 L5,-24 Z" class="${cls}-head"></path></g>`);
  return L.divIcon({
    className: "spread-arrow", iconSize: [180, 180], iconAnchor: [90, 90],
    html: `<svg viewBox="-35 -35 70 70">${arrow(modelDeg, "model")}${arrow(observedDeg, "observed")}</svg>`,
  });
}

// GOD VIEW in 2D: Europe, south-west and north-east corners.
const GOD_VIEW_BOUNDS = [[36, -10], [71, 40]];

function createLeafletMap(config) {
  const map = L.map("map", {
    preferCanvas: true, zoomSnap: 0.25, maxBounds: L.latLngBounds(config.view_bounds).pad(0.5),
  });
  map.fitBounds(config.view_bounds);
  const osmAttribution = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>';
  const osm = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: osmAttribution });
  const baseLayers = {};
  const baseById = { online: osm };  // mission control's base maps (basemaps.js) by id
  let labelLayer = null;  // the place names, drawn only over a base map without text
  let offline = null;
  if (config.layers.offline_tiles) {
    // Local tiles (tools/build_offline_tiles.py, docker compose service "tiles"): no internet needed.
    offline = L.tileLayer("/tiles/{z}/{x}/{y}.png", { maxZoom: 18, attribution: osmAttribution }).addTo(map);
    baseLayers["Offline-karta (OSM, lokal)"] = offline;
    baseById.offline = offline;
    baseLayers["OpenStreetMap (online)"] = osm;
  } else {
    baseLayers["OpenStreetMap (online)"] = osm.addTo(map);
  }
  const overlays = {};
  if (config.layers.lantmateriet_topowebb) {
    baseLayers["Lantmäteriet topowebb"] = L.tileLayer("/lm/topowebb/{z}/{x}/{y}.png", {
      maxZoom: 17, attribution: config.attribution.lantmateriet,
    });
    baseById.topowebb = baseLayers["Lantmäteriet topowebb"];
  } else {
    addNote("Lantmäteriets topowebb är inte aktiverad (inloggning via Geotorget saknas).");
  }
  if (config.layers.lantmateriet_fastighet) {
    overlays["Fastigheter (Lantmäteriet)"] = L.tileLayer.wms("/lm/fastighet", {
      layers: config.layers.lantmateriet_fastighet_layers, format: "image/png", transparent: true,
      attribution: config.attribution.lantmateriet,
    });
  } else {
    addNote("Fastighetsindelning är inte aktiverad (inloggning via Geotorget saknas).");
  }
  const hotspots = L.layerGroup().addTo(map);
  const syntheticLayer = L.layerGroup().addTo(map);
  // The fire's own layers.
  if (config.incident === "wildfire") {
    overlays["FIRMS-urval"] = L.rectangle(config.fire_selection_bounds, {
      color: "#202020", weight: 1, dashArray: "4 4", fill: false, interactive: false,
    });
    overlays["Hotspots"] = hotspots;
    overlays["Syntetiska sensorer"] = syntheticLayer;
  }
  const queryLayer = L.layerGroup().addTo(map);
  overlays["Svar på fråga"] = queryLayer;
  const stationLayer = L.layerGroup().addTo(map);
  // The Landsat 8 scene below the hotspots and other overlays. It is in WGS 84 and
  // stretched to its bounds; over this small area the distortion is about one per cent.
  map.createPane("landsat").style.zIndex = 350;
  // The flood maps above the satellite image, below the markers.
  map.createPane("wms").style.zIndex = 360;
  // SMHI's radar above the flood maps, below the markers.
  map.createPane("radar").style.zIndex = 370;
  let radarOverlay = null;
  let emsLayer = null;
  const landsatOverlays = {};
  let windLayer = null;
  const wmsLayers = new Map();  // WMS layer name -> Leaflet layer
  if (config.attribution.firms) map.attributionControl.addAttribution(config.attribution.firms);
  const stationMarkers = new Map();  // SMHI station id -> marker
  let markers = [];
  let windMarkers = [];
  let forecastLayer = null;
  let weatherCategoryVisible = true;
  let windVisible = true;
  let radarVisible = true;

  function setMapLayerVisible(layer, visible) {
    if (!layer) return;
    if (visible && !map.hasLayer(layer)) layer.addTo(map);
    else if (!visible && map.hasLayer(layer)) layer.remove();
  }

  return {
    dimension: "2d",
    wantsLabels: () => Boolean(offline),
    addAttribution: (text) => map.attributionControl.addAttribution(text),

    addTerrain(collection) {
      const layer = L.geoJSON(collection, {
        style: (feature) => ({
          color: TERRAIN_COLORS[feature.properties.terrain] || "#888",
          weight: 0.4, fillOpacity: 0.22, opacity: 0.5,
        }),
        onEachFeature: (feature, item) => {
          const name = feature.properties.name ? `<br>${feature.properties.name}` : "";
          item.bindPopup(`<strong>${feature.properties.terrain}</strong>${name}<br><small>OSM ${feature.properties.osm_tag}</small>`);
        },
      });
      overlays["Terräng (OSM)"] = layer;
      layer.addTo(map);
      layer.bringToBack();
    },

    // The offline tiles carry no text, so place and lake names are drawn here; the online
    // OSM map has its own names, so they show only with the offline map.
    addLabels(collection) {
      const pane = map.createPane("labels");
      pane.style.zIndex = 450;
      pane.style.pointerEvents = "none";
      const labelMarkers = collection.features.map((feature) => {
        const [lon, lat] = feature.geometry.coordinates;
        const text = document.createElement("span");
        text.textContent = feature.properties.name;  // OSM names are text, never markup
        const icon = L.divIcon({ className: `map-label map-label-${feature.properties.kind}`, html: text.outerHTML, iconSize: [0, 0] });
        const marker = L.marker([lat, lon], { icon, pane: "labels", interactive: false, keyboard: false });
        marker.minZoom = feature.properties.min_zoom;
        return marker;
      });
      const layer = L.layerGroup();
      const update = () => {
        const zoom = map.getZoom();
        for (const marker of labelMarkers) {
          const visible = zoom >= marker.minZoom;
          if (visible && !layer.hasLayer(marker)) layer.addLayer(marker);
          if (!visible && layer.hasLayer(marker)) layer.removeLayer(marker);
        }
      };
      map.on("zoomend", update);
      map.on("baselayerchange", (event) => {
        if (event.layer === offline) layer.addTo(map); else layer.remove();
      });
      update();
      labelLayer = layer;
      if (!offline || map.hasLayer(offline)) layer.addTo(map);
    },

    // Mission control's base map (basemaps.js baseMapFor): its id, or null for none. The place
    // names show over the offline map and no map, which carry no text of their own.
    setBaseMap(id) {
      for (const [key, layer] of Object.entries(baseById)) {
        if (key === id) { if (!map.hasLayer(layer)) layer.addTo(map); layer.bringToBack(); } else layer.remove();
      }
      if (labelLayer) {
        if (id === "offline" || id === null) labelLayer.addTo(map); else labelLayer.remove();
      }
    },

    // style: { color, fill } for another kind of station (the flood's flows and lake levels).
    addStations(stations, style = {}) {
      for (const station of stations) {
        stationMarkers.set(station.id, L.circleMarker([station.latitude, station.longitude], {
          radius: 6, color: style.color || "#1f5fa8", fillColor: style.fill || "#fff", fillOpacity: 1, weight: 3,
        }).bindTooltip(`SMHI ${station.name}`, { permanent: true, direction: "right" }).addTo(stationLayer));
      }
    },

    // New texts for the station labels, by station id (the flood's rain per hour).
    labelStations(texts) {
      for (const [id, text] of Object.entries(texts)) stationMarkers.get(id)?.setTooltipContent(text);
    },

    // The rain at each station in SMHI's classes (rain.js): the marker's size and colour, by station id.
    markRain(classes) {
      for (const [id, rain] of Object.entries(classes)) {
        stationMarkers.get(id)?.setRadius(rain.radius).setStyle({ fillColor: rain.color });
      }
    },

    // Copernicus EMS's perimeter of the fire: the product shown by the clock, or none.
    setupEms() {
      emsLayer = L.layerGroup().addTo(map);
      overlays["Brandområde (Copernicus EMS)"] = emsLayer;
    },

    drawEms(product) {
      emsLayer.clearLayers();
      if (!product) return;
      L.geoJSON(product.geometry, { style: { color: "#7b1fa2", weight: 3, dashArray: "8 5", fill: false }, interactive: false }).addTo(emsLayer);
    },

    // SMHI's weather radar: one overlay whose image follows the clock (showRadar).
    setupRadar(info) {
      radarOverlay = L.imageOverlay(info.frames[0].url, info.bounds, { pane: "radar", opacity: 0, interactive: false });
      overlays["Nederbörd (SMHI radar)"] = radarOverlay;
      setMapLayerVisible(radarOverlay, weatherCategoryVisible && radarVisible);
    },

    showRadar(url) {
      if (!radarOverlay) return;
      if (url) radarOverlay.setUrl(url);
      radarOverlay.setOpacity(url ? 0.85 : 0);
    },

    // callback(names) with the WMS layers shown, now and whenever one is switched on or off.
    onWmsChange(callback) {
      const notify = () => callback([...wmsLayers].filter(([, layer]) => map.hasLayer(layer)).map(([name]) => name));
      map.on("overlayadd overlayremove", notify);
      notify();
    },

    // The scenario's WMS layers (wms.py, through the backend) in the layer control; `visible` start shown.
    // In WGS 84: MCF's service has no Web Mercator.
    addWms(source) {
      for (const [name, title] of Object.entries(source.layers)) {
        const layer = L.tileLayer.wms(source.url, {
          layers: name, format: "image/png", transparent: true, version: "1.1.1", crs: L.CRS.EPSG4326,
          opacity: 0.7, attribution: source.attribution, pane: "wms",
        });
        overlays[`${title} (modell)`] = layer;
        wmsLayers.set(name, layer);
        if ((source.visible || []).includes(name)) layer.addTo(map);
      }
    },

    clearHotspots() {
      hotspots.clearLayers();
      markers = [];
    },

    addHotspot(feature) {
      const [lon, lat] = feature.geometry.coordinates;
      const p = feature.properties;
      const viirs = p.instrument === "VIIRS";
      const marker = L.circleMarker([lat, lon], {
        radius: hotspotRadius(p.frp), weight: viirs ? 0 : 1.5, fillOpacity: viirs ? 0.75 : 0.15,
      });
      marker.bindPopup(hotspotPopup(p));
      marker.detectedAt = new Date(p.acq_datetime_utc);
      marker.addTo(hotspots);
      markers.push(marker);
    },

    hotspotCount: () => markers.length,

    restyleHotspots(clock) {
      for (const marker of markers) {
        const color = hotspotColor(marker.detectedAt, clock);
        marker.setStyle({ color, fillColor: color });
      }
    },

    setupWind(wind, onShow) {
      const layer = L.layerGroup();
      const icon = L.divIcon({ className: "barb-icon", iconSize: [100, 100], iconAnchor: [50, 50], html: "" });
      windMarkers = wind.points.map(([lat, lon]) => L.marker([lat, lon], { icon, keyboard: false })
        .bindTooltip("", { direction: "top" }).addTo(layer));
      overlays["Vind (ERA5-Land)"] = layer;
      windLayer = layer;
      setMapLayerVisible(layer, weatherCategoryVisible && windVisible);
      layer.on("add", onShow);
    },

    showWind(hour, wind) {
      windMarkers.forEach((marker, position) => {
        const element = marker.getElement();
        if (!element) return;
        if (hour < 0) {
          element.style.visibility = "hidden";
          return;
        }
        const [speed, from] = wind.values[hour][position];
        element.style.visibility = "visible";
        element.innerHTML = windBarbSvg(speed);
        element.firstChild.style.transform = `rotate(${(from + 180) % 360}deg)`;
        marker.setTooltipContent(windTooltip(position, hour));
      });
    },

    setupForecast() {
      forecastLayer = L.layerGroup().addTo(map);
      overlays["Prognos (modell)"] = forecastLayer;
    },

    drawForecast(current, horizon) {
      forecastLayer.clearLayers();
      if (!current) return;
      const bands = current.forecast[horizon];
      L.polygon(bands.high, { color: "#b7950b", weight: 1, dashArray: "5 4", fillColor: "#ffd54a", fillOpacity: 0.18, interactive: false }).addTo(forecastLayer);
      L.polygon(bands.central, { color: "#d35400", weight: 1.5, fillColor: "#ff8c00", fillOpacity: 0.25, interactive: false }).addTo(forecastLayer);
      L.polygon(bands.low, { color: "#7a1f1f", weight: 1, dashArray: "3 3", fill: false, interactive: false }).addTo(forecastLayer);
      L.polygon(current.front, { color: "#202020", weight: 2, fill: false, interactive: false }).addTo(forecastLayer);
      L.marker(current.front_centre, {
        icon: spreadArrowIcon(current.observed_spread?.towards_deg, current.model.towards_deg), interactive: false, keyboard: false,
      }).addTo(forecastLayer);
      for (const place of current.places_within_24h) {
        L.circleMarker([place.latitude, place.longitude], { radius: 4, color: "#202020", weight: 1, fillColor: "#ffd54a", fillOpacity: 1 })
          .bindTooltip(`${place.names.join(", ")}: inom ${place.span} (spann)`, { direction: "top" })
          .addTo(forecastLayer);
      }
    },

    // The layer control only for troubleshooting (?controls=1): mission control switches the layers.
    finish() {
      if (showControls()) L.control.layers(baseLayers, overlays, { collapsed: false }).addTo(map);
    },

    // Mission control's layer ticks (the status's map_layers): false when the map has no such layer yet.
    setLayerVisible(name, visible) {
      const layer = overlays[name];
      if (!layer) return false;
      let effectiveVisible = visible;
      if (name === "Vind (ERA5-Land)") {
        windVisible = visible;
        effectiveVisible = visible && weatherCategoryVisible;
      } else if (name === "Nederbörd (SMHI radar)") {
        radarVisible = visible;
        effectiveVisible = visible && weatherCategoryVisible;
      }
      if (effectiveVisible === map.hasLayer(layer)) return true;
      setMapLayerVisible(layer, effectiveVisible);
      // As the layer control does, so the WMS listeners (the flood's legend) follow.
      map.fire(visible ? "overlayadd" : "overlayremove", { layer, name });
      return true;
    },

    // The synthetic sensors at the clock (sensor_sim.py): red confirms the fire, grey failed.
    drawSyntheticSensors(result) {
      syntheticLayer.clearLayers();
      for (const sensor of result.sensors) {
        L.circleMarker([sensor.latitude, sensor.longitude], {
          radius: 8, color: "#202020", weight: 2, dashArray: "3 2", fillColor: SYNTHETIC_COLORS[syntheticState(sensor)], fillOpacity: 0.9,
        }).bindTooltip(sensor.name, { permanent: true, direction: "right", offset: [8, 0] })
          .bindPopup(`<strong>${sensor.name} (syntetisk)</strong><br>${syntheticSensorText(sensor)}<br><small>${result.label}</small>`)
          .addTo(syntheticLayer);
      }
    },

    // The result of a prepared question (spatial.py); null clears it.
    drawQueryResult(collection) {
      queryLayer.clearLayers();
      if (!collection || !collection.features.length) return;
      const layer = L.geoJSON(collection, {
        style: { color: QUERY_COLOR, weight: 4, opacity: 0.85 },
        pointToLayer: (feature, latlng) => L.circleMarker(latlng, { radius: 6, color: "#ffffff", weight: 2, fillColor: QUERY_COLOR, fillOpacity: 1 }),
        onEachFeature: (feature, item) => item.bindTooltip(queryLabel(feature.properties)),
      }).addTo(queryLayer);
      map.flyToBounds(layer.getBounds().pad(0.1), { maxZoom: 13, duration: 2 });
    },

    // GOD VIEW's filter: hide or show a category of layers.
    setCategoryVisible(category, visible) {
      if (category === "weather") {
        weatherCategoryVisible = visible;
        setMapLayerVisible(windLayer, visible && windVisible);
        setMapLayerVisible(stationLayer, visible);
        setMapLayerVisible(radarOverlay, visible && radarVisible);
        return;
      }
      const groups = { space: [hotspots], iot: [syntheticLayer], infrastructure: [queryLayer] };
      for (const layer of groups[category] || []) {
        if (!layer) continue;
        if (visible) layer.addTo(map);
        else layer.remove();
      }
    },

    // The satellites and SPACE VIEW are drawn on the 3D globe only; the panel lists them.
    drawSatellites() {},
    flashSatellite() {},
    highlightSatellite() {},

    // A right click on the map: callback({ latitude, longitude, x, y }) with the page position.
    onContextMenu(callback) {
      map.on("contextmenu", (event) => callback({
        latitude: event.latlng.lat, longitude: event.latlng.lng,
        x: event.originalEvent.clientX, y: event.originalEvent.clientY,
      }));
    },
    showSpaceView() {},

    setupLandsat(info) {
      // One overlay per scene and image, keyed "scene|image" as landsat.js names them.
      for (const scene of info.scenes) {
        for (const [name, url] of Object.entries(scene.images)) {
          landsatOverlays[`${scene.scene}|${name}`] = L.imageOverlay(url, info.bounds, { pane: "landsat", interactive: false });
        }
      }
    },

    showLandsat(name) {
      for (const [key, overlay] of Object.entries(landsatOverlays)) {
        if (key === name) overlay.addTo(map);
        else overlay.remove();
      }
    },

    // Show an evidence object from the assessment.
    focusOn(lat, lon) {
      map.flyTo([lat, lon], Math.max(map.getZoom(), 12), { duration: 2 });
    },

    // Mission control's GOD VIEW: out to Europe (OSM online; the offline tiles cover the
    // fire area only), and back to the fire area when it is switched off.
    // Mission control's FLYG TILL and ÖVERSIKT (the status's camera): to the incident, or the whole view.
    flyToIncident() {
      return new Promise((resolve) => {
        map.once("moveend", resolve);
        map.flyTo(config.fire_centre, 12, { duration: 2 });
      });
    },

    flyHome() {
      map.flyToBounds(config.view_bounds, { duration: 2 });
    },

    showGodView(on) {
      if (on) {
        map.setMaxBounds(null);
        map.flyToBounds(GOD_VIEW_BOUNDS, { duration: 3 });
      } else {
        map.flyToBounds(config.view_bounds, { duration: 3 });
        map.once("moveend", () => map.setMaxBounds(L.latLngBounds(config.view_bounds).pad(0.5)));
      }
    },
  };
}
