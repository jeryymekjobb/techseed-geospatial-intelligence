// Leaflet map adapter for the 2D fire map (see panel.js for the interface).
"use strict";

function spreadArrowIcon(observedDeg, modelDeg) {
  const arrow = (deg, cls) => (deg === null || deg === undefined ? "" :
    `<g transform="rotate(${deg})"><path d="M0,0 L0,-30" class="${cls}"></path><path d="M-5,-24 L0,-34 L5,-24 Z" class="${cls}-head"></path></g>`);
  return L.divIcon({
    className: "spread-arrow", iconSize: [70, 70], iconAnchor: [35, 35],
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
  let offline = null;
  if (config.layers.offline_tiles) {
    // Local tiles (tools/build_offline_tiles.py, docker compose service "tiles"): no internet needed.
    offline = L.tileLayer("/tiles/{z}/{x}/{y}.png", { maxZoom: 18, attribution: osmAttribution }).addTo(map);
    baseLayers["Offline-karta (OSM, lokal)"] = offline;
    baseLayers["OpenStreetMap (online)"] = osm;
  } else {
    baseLayers["OpenStreetMap (online)"] = osm.addTo(map);
  }
  const overlays = {};
  if (config.layers.lantmateriet_topowebb) {
    baseLayers["Lantmäteriet topowebb"] = L.tileLayer("/lm/topowebb/{z}/{x}/{y}.png", {
      maxZoom: 17, attribution: config.attribution.lantmateriet,
    });
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
  overlays["FIRMS-urval"] = L.rectangle(config.fire_selection_bounds, {
    color: "#202020", weight: 1, dashArray: "4 4", fill: false, interactive: false,
  });
  const hotspots = L.layerGroup().addTo(map);
  overlays["Hotspots"] = hotspots;
  const syntheticLayer = L.layerGroup().addTo(map);
  overlays["Syntetiska sensorer"] = syntheticLayer;
  map.attributionControl.addAttribution(config.attribution.firms);
  let markers = [];
  let windMarkers = [];
  let forecastLayer = null;

  return {
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
      layer.addTo(map);
    },

    addStations(stations) {
      for (const station of stations) {
        L.circleMarker([station.latitude, station.longitude], {
          radius: 6, color: "#1f5fa8", fillColor: "#fff", fillOpacity: 1, weight: 3,
        }).bindTooltip(`SMHI ${station.name}`, { permanent: true, direction: "right" }).addTo(map);
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
      const icon = L.divIcon({ className: "barb-icon", iconSize: [56, 56], iconAnchor: [28, 28], html: "" });
      windMarkers = wind.points.map(([lat, lon]) => L.marker([lat, lon], { icon, keyboard: false })
        .bindTooltip("", { direction: "top" }).addTo(layer));
      overlays["Vind (ERA5-Land)"] = layer;
      layer.addTo(map);
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

    finish() {
      L.control.layers(baseLayers, overlays, { collapsed: false }).addTo(map);
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

    // Mission control's GOD VIEW: out to Europe (OSM online; the offline tiles cover the
    // fire area only), and back to the fire area when it is switched off.
    showGodView(on) {
      if (on) {
        map.setMaxBounds(null);
        map.flyToBounds(GOD_VIEW_BOUNDS, { duration: 1.5 });
      } else {
        map.flyToBounds(config.view_bounds, { duration: 1.5 });
        map.once("moveend", () => map.setMaxBounds(L.latLngBounds(config.view_bounds).pad(0.5)));
      }
    },
  };
}
