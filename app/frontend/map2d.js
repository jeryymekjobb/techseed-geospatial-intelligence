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
// The weather chart's view ("Väderkarta (MET Norway)"): Scandinavia, where MEPS draws the isobars.
const WEATHER_CHART_BOUNDS = [[55, 4], [70, 31]];

// How far the map can be panned: the incident's view with a margin, grown to the whole map area
// (Sundsvall's reaches Härnösand and Kramfors).
function panBounds(config) {
  return L.latLngBounds(config.view_bounds).pad(0.5).extend(L.latLngBounds(config.map_bounds));
}

function createLeafletMap(config) {
  const map = L.map("map", {
    preferCanvas: true, zoomSnap: 0.25, maxBounds: panBounds(config),
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
  const municipal = config.layers.municipal_basemap;
  if (municipal) {
    // The municipality's map, kept locally (municipal_basemap.py), enlarged beyond its highest fetched zoom.
    baseById[municipal.id] = L.tileLayer(municipal.url, {
      minZoom: municipal.min_zoom, maxZoom: 18, maxNativeZoom: municipal.max_zoom, bounds: municipal.bounds,
      attribution: municipal.attribution,
    });
    baseLayers[municipal.label] = baseById[municipal.id];
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
  const threatLayer = L.layerGroup().addTo(map);
  overlays["Hotad bebyggelse"] = threatLayer;
  // Above the sensors' permanent names (the tooltip pane, 650), so they never cover the newest threat.
  map.createPane("threats").style.zIndex = 660;
  map.getPane("threats").style.pointerEvents = "none";
  const stationLayer = L.layerGroup().addTo(map);
  // Satellite images are below the flood maps, except the transparent radar-water mask.
  // Images are in WGS 84 and stretched to their bounds.
  map.createPane("landsat").style.zIndex = 350;
  // The flood maps above ordinary satellite images, below the radar-water mask and markers.
  map.createPane("wms").style.zIndex = 360;
  // SMHI's radar above the flood maps, below the markers.
  map.createPane("radar").style.zIndex = 370;
  // The transparent Sentinel-1 water mask must be visible above the flood maps and weather radar.
  map.createPane("radarwater").style.zIndex = 420;
  // The offline map's road numbers and railway tunnels over any base map (offline_tiles.py), above
  // the images and flood maps, below the markers.
  const roadOverlay = config.layers.road_overlay;
  if (roadOverlay) {
    map.createPane("roadoverlay").style.zIndex = 430;
    map.getPane("roadoverlay").style.pointerEvents = "none";
    overlays[roadOverlay.label] = L.tileLayer(roadOverlay.url, {
      pane: "roadoverlay", maxZoom: 18, attribution: roadOverlay.attribution,
    }).addTo(map);
  }
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
  let forecastWindLayer = null;  // MET Norway's forecast wind (met_forecast.py), orange barbs
  let forecastWindVisible = false;
  let isobarLayer = null;  // MET Norway's weather chart: isobars every 2 hPa, highs and lows, rain and lightning
  let viewBeforeChart = null;  // the view to come back to when the weather chart is unticked
  let lightningLayer = null;  // SMHI's observed flashes to the ground in the last hour
  let lightningVisible = true;
  let routeImpactLayer = null;  // roads and railways the incident damaged (routes.py)
  let meteosatLayer = null;  // Meteosat's fire pixels (meteosat.py)
  let frmLayer = null;  // LSA SAF's fire risk (meteosat_frm.py), off until ticked
  let frmVisible = false;
  let dailyRainLayer = null;  // SMHI's rain by the day (daily_rain.py)
  let dailyRainVisible = true;
  let routeExposureLayer = null;  // roads and railways under heavy rain, computed from the radar
  let isobarVisible = false;

  // Fewer wind arrows further out (windMinZoom in wind_barbs.js); `visibility` is the hour's.
  function thinWind() {
    const zoom = map.getZoom();
    for (const marker of windMarkers) {
      const element = marker.getElement();
      if (element) element.style.display = zoom >= marker.minZoom ? "" : "none";
    }
  }

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
      const middle = windGridMiddle(wind.points);
      windMarkers = wind.points.map(([lat, lon]) => {
        const marker = L.marker([lat, lon], { icon, keyboard: false }).bindTooltip("", { direction: "top" }).addTo(layer);
        marker.minZoom = windMinZoom(lat, lon, middle);
        return marker;
      });
      overlays["Vind (ERA5-Land)"] = layer;
      windLayer = layer;
      setMapLayerVisible(layer, weatherCategoryVisible && windVisible);
      layer.on("add", onShow);
      map.on("zoomend", thinWind);
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
      thinWind();
    },

    // MET Norway's forecast wind over the map some hours ahead (met_forecast.py), as orange barbs;
    // off until mission control ticks it, as the ERA5-Land barbs show the wind of the hour.
    setupForecastWind() {
      forecastWindLayer = L.layerGroup();
      overlays["Prognosvind (MET Norway)"] = forecastWindLayer;
    },

    drawForecastWind(points, hoursAhead) {
      if (!forecastWindLayer) return;
      forecastWindLayer.clearLayers();
      for (const point of points || []) {
        const svg = windBarbSvg(point.wind_ms).replace("<svg ", `<svg style="transform: rotate(${(point.wind_from_deg + 180) % 360}deg)" `);
        L.marker([point.latitude, point.longitude], {
          icon: L.divIcon({ className: "barb-icon forecast-barb", iconSize: [100, 100], iconAnchor: [50, 50], html: svg }), keyboard: false,
        }).bindTooltip(`Prognosvind om ${hoursAhead} timmar (MET Norway): ${String(point.wind_ms).replace(".", ",")} m/s`, { direction: "top" })
          .addTo(forecastWindLayer);
      }
    },

    // MET Norway's weather chart (met_forecast.py): the rain of three hours as a transparent image,
    // dark blue isobars every hPa (each fourth with its value), H and L, and lightning; off until mission control ticks
    // "Väderkarta (MET Norway)".
    setupWeatherChart() {
      isobarLayer = L.layerGroup();
      overlays["Väderkarta (MET Norway)"] = isobarLayer;
    },

    drawWeatherChart(chart) {
      if (!isobarLayer) return;
      isobarLayer.clearLayers();
      if (chart?.rain_png) L.imageOverlay(chart.rain_png, chart.rain_bounds, { opacity: 0.85, interactive: false }).addTo(isobarLayer);
      for (const line of chart?.lines || []) {
        // Every hPa; each fourth (1000, 1004 …) bolder and with its value, as on weather charts.
        const main = line.hpa % 4 === 0;
        L.polyline(line.coords, { color: "#1f3a7a", weight: main ? 1.8 : 0.8, opacity: main ? 0.9 : 0.6, interactive: false }).addTo(isobarLayer);
        if (!main) continue;
        const middle = line.coords[Math.floor(line.coords.length / 2)];
        L.marker(middle, { icon: L.divIcon({ className: "isobar-label", html: String(line.hpa), iconSize: [0, 0] }), interactive: false, keyboard: false })
          .addTo(isobarLayer);
      }
      for (const centre of chart?.centres || []) {
        L.marker([centre.latitude, centre.longitude], {
          icon: L.divIcon({ className: `isobar-centre ${centre.kind === "H" ? "high" : "low"}`, html: `${centre.kind}<small>${centre.hpa}</small>`, iconSize: [0, 0] }),
          interactive: false, keyboard: false,
        }).addTo(isobarLayer);
      }
      for (const mark of chart?.thunder || []) {
        L.marker([mark.latitude, mark.longitude], { icon: L.divIcon({ className: "chart-lightning", html: "⚡", iconSize: [0, 0] }),
          interactive: false, keyboard: false }).addTo(isobarLayer);
      }
    },

    // SMHI's observed lightning (lightning.py): the flashes to the ground of the last hour, yellow when
    // fresh and fading to orange with age.
    setupLightning() {
      lightningLayer = L.layerGroup();
      overlays["Blixtar (SMHI, observerade)"] = lightningLayer;
    },

    // `history`: the flashes near the incident since the start, red, with their time on hover.
    drawLightning(strikes, history) {
      if (!lightningLayer) return;
      lightningLayer.clearLayers();
      const bolt = (size, colour, opacity) => L.divIcon({ className: "lightning-bolt", iconSize: [size, size * 4 / 3], iconAnchor: [size / 2, size * 2 / 3],
        html: `<div style="opacity:${opacity}">${lightningSvg(colour, size)}</div>` });
      for (const strike of history || []) {
        L.marker([strike.latitude, strike.longitude], { icon: bolt(18, LIGHTNING_NEAR_COLOUR, 1), keyboard: false })
          .bindTooltip(`Blixtnedslag ${formatLightningTime(strike.utc)} (SMHI, observerat), ${strike.ka} kA`, { direction: "top" })
          .addTo(lightningLayer);
      }
      for (const strike of strikes || []) {
        L.marker([strike.latitude, strike.longitude], { icon: bolt(14, lightningColour(strike.age_min), Math.max(0.35, 1 - strike.age_min / 80)),
          interactive: false, keyboard: false }).addTo(lightningLayer);
      }
    },

    // Roads and railways (routes.py): the computed pieces under heavy rain as coloured lines, and
    // the documented damage as markers with the report's text, both on from the start.
    setupRoutes(info, hasExposure) {
      if (hasExposure) {
        routeExposureLayer = L.layerGroup().addTo(map);
        overlays[info.exposure_label] = routeExposureLayer;
      }
      routeImpactLayer = L.layerGroup().addTo(map);
      overlays[info.impact_label] = routeImpactLayer;
    },

    // Meteosat's fire pixels: a purple rectangle of each pixel's area, under FIRMS's points.
    setupMeteosat(label) {
      meteosatLayer = L.layerGroup().addTo(map);
      overlays[label] = meteosatLayer;
    },

    drawMeteosat(items) {
      meteosatLayer.clearLayers();
      for (const item of items) {
        L.polygon(item.footprint, { color: METEOSAT_COLOUR, opacity: METEOSAT_EDGE_OPACITY, weight: 2, fillColor: METEOSAT_COLOUR, fillOpacity: meteosatOpacity(item.frp_mw) })
          .bindTooltip(item.text, { sticky: true }).addTo(meteosatLayer).bringToBack();
      }
    },

    // LSA SAF's fire risk: a cell of 0.05° in the risk class's colour, under everything else.
    setupMeteosatFrm(label) {
      frmLayer = L.layerGroup();
      overlays[label] = frmLayer;
    },

    drawMeteosatFrm(cells) {
      if (!frmLayer) return;
      frmLayer.clearLayers();
      for (const cell of cells) {
        L.rectangle([[cell.south, cell.west], [cell.north, cell.east]], { stroke: false, fillColor: FRM_COLOURS[cell.risk], fillOpacity: FRM_OPACITY })
          .bindTooltip(cell.text, { sticky: true }).addTo(frmLayer).bringToBack();
      }
    },

    // SMHI's rain by the day: a marker in the rain's class with the station's latest ended day.
    setupDailyRain(info) {
      dailyRainLayer = L.layerGroup().addTo(map);
      overlays[info.label] = dailyRainLayer;
    },

    drawDailyRain(items) {
      dailyRainLayer.clearLayers();
      for (const item of items) {
        L.circleMarker([item.latitude, item.longitude], { radius: 7, color: "#ffffff", weight: 2, fillColor: "#123f8c", fillOpacity: 0.95 })
          .bindTooltip(item.text, { direction: "right", permanent: true, className: "daily-rain-label" })
          .bindPopup(`${item.text}<br><small>${item.detail}</small>`)
          .addTo(dailyRainLayer);
      }
    },

    drawRoutes(impacts, pieces) {
      if (routeExposureLayer) {
        routeExposureLayer.clearLayers();
        for (const piece of pieces) {
          L.polyline(piece.coords, { color: ROUTE_EXPOSURE_COLOURS[piece.level], weight: piece.kind === "rail" ? 5 : 4, opacity: 0.9 })
            .bindTooltip(`${piece.ref || piece.name || (piece.kind === "rail" ? "Järnväg" : "Väg")}: ${Math.round(piece.rain)} mm regn sedan start `
              + "(beräknat ur radar – inte observerade skador)", { sticky: true })
            .addTo(routeExposureLayer);
        }
      }
      routeImpactLayer.clearLayers();
      for (const item of impacts) {
        const colour = ROUTE_IMPACT_COLOURS[item.kind] || "#d62828";
        L.marker([item.latitude, item.longitude], {
          icon: L.divIcon({ className: "route-impact", iconSize: [22, 22], iconAnchor: [11, 11],
            html: `<div style="width:18px;height:18px;border-radius:${item.kind === "rail" ? "3px" : "50%"};background:${colour};`
              + 'border:2px solid #fff;box-shadow:0 0 4px rgba(0,0,0,.6);color:#fff;font:bold 13px system-ui;text-align:center;line-height:18px">!</div>' }),
          keyboard: false,
        }).bindTooltip(`${item.text}<br><small>${formatLocal(item.time_utc)}${item.approximate_time ? " (tid ungefärlig)" : ""} · `
          + `plats ungefärlig · ${item.source_label || "Länsstyrelsen, utredning 2026"}</small>`, { direction: "top" }).addTo(routeImpactLayer);
      }
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
      } else if (name === "Prognosvind (MET Norway)") {
        forecastWindVisible = visible;
        effectiveVisible = visible && weatherCategoryVisible;
      } else if (layer === frmLayer) {
        frmVisible = visible;
        effectiveVisible = visible && weatherCategoryVisible;
      } else if (layer === dailyRainLayer) {
        dailyRainVisible = visible;
        effectiveVisible = visible && weatherCategoryVisible;
      } else if (name === "Blixtar (SMHI, observerade)") {
        lightningVisible = visible;
        effectiveVisible = visible && weatherCategoryVisible;
      } else if (name === "Väderkarta (MET Norway)") {
        isobarVisible = visible;
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

    // The threatened places (satlog.js threatMarks): the newest threat's large with its name, the
    // earlier ones a small icon, so the many places of a long fire do not hide the newest.
    drawThreats(marks) {
      threatLayer.clearLayers();
      for (const mark of marks) {
        const name = document.createElement("span");
        name.textContent = mark.name;  // OSM names are text, never markup
        const icon = L.divIcon({
          className: `threat-mark${mark.latest ? " latest" : ""}`, iconSize: [0, 0],
          html: `<div class="threat-body">${THREAT_ICON_SVG}${mark.latest ? name.outerHTML : ""}</div>`,
        });
        L.marker([mark.latitude, mark.longitude], { icon, pane: "threats", interactive: false, keyboard: false, zIndexOffset: mark.latest ? 1000 : 0 })
          .addTo(threatLayer);
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
        setMapLayerVisible(forecastWindLayer, visible && forecastWindVisible);
        setMapLayerVisible(isobarLayer, visible && isobarVisible);
        setMapLayerVisible(lightningLayer, visible && lightningVisible);
        setMapLayerVisible(dailyRainLayer, visible && dailyRainVisible);
        setMapLayerVisible(frmLayer, visible && frmVisible);
        return;
      }
      const groups = { space: [hotspots, meteosatLayer], iot: [syntheticLayer], infrastructure: [queryLayer, threatLayer, routeImpactLayer, routeExposureLayer] };
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
          const pane = name === "radarwater" ? "radarwater" : "landsat";
          landsatOverlays[`${scene.scene}|${name}`] = L.imageOverlay(url, info.bounds, { pane, interactive: false });
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

    // The weather chart: out over Scandinavia when its layer is ticked (the isobars are hundreds of
    // kilometres apart), back to the view one had when it is unticked; the offline tiles cover only
    // the fire area.
    showWeatherChartView(on) {
      if (on) {
        viewBeforeChart = { centre: map.getCenter(), zoom: map.getZoom(), bounds: map.options.maxBounds };
        map.setMaxBounds(null);
        map.flyToBounds(WEATHER_CHART_BOUNDS, { duration: 2 });
      } else if (viewBeforeChart) {
        const before = viewBeforeChart;
        viewBeforeChart = null;
        map.flyTo(before.centre, before.zoom, { duration: 2 });
        map.once("moveend", () => map.setMaxBounds(before.bounds || null));
      }
    },

    showGodView(on) {
      if (on) {
        map.setMaxBounds(null);
        map.flyToBounds(GOD_VIEW_BOUNDS, { duration: 3 });
      } else {
        map.flyToBounds(config.view_bounds, { duration: 3 });
        map.once("moveend", () => map.setMaxBounds(panBounds(config)));
      }
    },
  };
}
