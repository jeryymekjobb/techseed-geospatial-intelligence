// The main screen of the monitoring (app/monitoring/service.py): the 3D globe over the area in real
// time, as the demos' globe (app/frontend/map3d.js) but with the live sources. The base maps are the
// municipality's map over the offline OpenStreetMap and OSM's road numbers and railway tunnels over
// both (/api/config's maps); the border, SMHI's stations, FIRMS's detections, the events in and the
// current alarms from /api/state; and the satellites that send the monitoring data, where they are
// now with their orbit 50 minutes back and ahead (orbits.js, satellite.js), from /api/satellites.
"use strict";

const STATE_MS = 30000;
const VIEW_MS = 2000;
const VIEW_RANGE_M = 75_000;
const SATELLITE_MS = 2000;
const SATELLITE_COLORS = { MODIS: "#ff8c00", VIIRS: "#ff2a00" };
const ALARM_COLORS = { new: "#ff1744", confirmed: "#2979ff" };
const clockText = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", day: "numeric", month: "short",
  hour: "2-digit", minute: "2-digit", second: "2-digit" });

// Cesium's info box shows descriptions as HTML: text from the sources is escaped first.
function escapeText(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function color(hex, alpha = 1) {
  return Cesium.Color.fromCssColorString(hex).withAlpha(alpha);
}

function credit(text) {
  if (!text) return;
  const box = document.getElementById("credits");
  if (!box.textContent.includes(text)) box.textContent += `${box.textContent ? " · " : ""}${text}`;
}

async function getJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

function addBaseMaps(viewer, maps) {
  const rectangle = (bbox) => Cesium.Rectangle.fromDegrees(...bbox);
  if (maps.offline) {
    viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
      url: maps.offline.url, maximumLevel: 18, rectangle: rectangle(maps.offline.bbox) }));
    credit(maps.offline.attribution);
  }
  for (const item of maps.municipal) {
    viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
      url: item.url, minimumLevel: item.min_zoom, maximumLevel: item.max_zoom, rectangle: rectangle(item.bbox) }));
    credit(item.attribution);
  }
  if (maps.overlay) {
    viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
      url: maps.overlay.url, maximumLevel: 18, rectangle: rectangle(maps.offline?.bbox || maps.municipal[0]?.bbox) }));
  }
  if (!maps.offline && !maps.municipal.length) {
    viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({ url: maps.online.url, maximumLevel: 18 }));
    credit(maps.online.attribution);
  }
}

async function start() {
  const config = await getJson("/api/config");
  document.getElementById("title").textContent = `Övervakning – ${config.area.name}`;
  document.title = `Övervakning – ${config.area.name} – 3D`;
  const viewer = new Cesium.Viewer("globe", {
    baseLayer: Cesium.ImageryLayer.fromProviderAsync(
      Cesium.TileMapServiceImageryProvider.fromUrl(Cesium.buildModuleUrl("Assets/Textures/NaturalEarthII"))),
    baseLayerPicker: false, geocoder: false, homeButton: false, sceneModePicker: false, navigationHelpButton: false,
    fullscreenButton: false, timeline: false, animation: false, infoBox: true, selectionIndicator: false,
  });
  viewer.bottomContainer.style.display = "none";
  credit("Natural Earth II");
  addBaseMaps(viewer, config.maps);
  // From the south and above, as the demos' view of the incident (map3d.js FIRE_VIEW), far enough
  // to see the whole municipality.
  const [lat, lon] = config.area.centre;
  viewer.camera.lookAt(Cesium.Cartesian3.fromDegrees(lon, lat),
    new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(-55), VIEW_RANGE_M));
  viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);

  const sites = new Cesium.CustomDataSource("sites");
  const satelliteLayer = new Cesium.CustomDataSource("satellites");
  viewer.dataSources.add(sites);
  viewer.dataSources.add(satelliteLayer);
  let border = null;

  const drawState = (state) => {
    const context = state.context || {};
    if (context.border && !border) {
      border = Cesium.GeoJsonDataSource.load(context.border, { stroke: color("#2979ff"), strokeWidth: 3, fill: color("#2979ff", 0.04),
        clampToGround: true }).then((source) => viewer.dataSources.add(source));
    }
    sites.entities.removeAll();
    const point = (lat, lon, hex, size, name, description) => sites.entities.add({
      name: escapeText(name), description: escapeText(description), position: Cesium.Cartesian3.fromDegrees(lon, lat),
      point: { pixelSize: size, color: color(hex), outlineColor: color("#ffffff"), outlineWidth: 2,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, disableDepthTestDistance: Number.POSITIVE_INFINITY },
    });
    for (const flow of context.flows || []) {
      if (flow.latitude != null) point(flow.latitude, flow.longitude, "#0277bd", 10, flow.name, `${flow.value} m³/s, ${flow.time_utc} – SMHI`);
    }
    for (const rain of context.rain || []) {
      if (rain.latitude != null) point(rain.latitude, rain.longitude, "#2e7d32", 9, rain.name, `${rain.mm_24h} mm senaste 24 h – SMHI`);
    }
    for (const fire of context.firms || []) {
      point(fire.latitude, fire.longitude, "#ff6d00", 8, `FIRMS ${fire.satellite}`, `${fire.instrument} ${fire.time_utc} – NASA FIRMS`);
    }
    for (const event of state.events || []) {
      point(event.latitude, event.longitude, event.simulated ? "#e040fb" : "#6a1b9a", 9, `${event.kind_word}${event.simulated ? " (simulerad)" : ""}`,
        `${event.time_utc} – ${event.source}`);
    }
    const current = state.alarms.filter((alarm) => alarm.current && alarm.state !== "dismissed");
    for (const alarm of current) {
      const c = alarm.candidate;
      if (c.latitude == null) continue;
      sites.entities.add({
        name: escapeText(c.title), description: c.facts.map((fact) => escapeText(`${fact.text} – ${fact.source}`)).join("<br>"),
        position: Cesium.Cartesian3.fromDegrees(c.longitude, c.latitude),
        point: { pixelSize: 22, color: color(ALARM_COLORS[alarm.state] || "#ff1744", 0.35), outlineColor: color(ALARM_COLORS[alarm.state] || "#ff1744"),
          outlineWidth: 3, heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, disableDepthTestDistance: Number.POSITIVE_INFINITY },
        label: { text: c.title, font: "15px system-ui, sans-serif", fillColor: color("#ffffff"), outlineColor: color("#000000"),
          outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE, pixelOffset: new Cesium.Cartesian2(16, 0),
          horizontalOrigin: Cesium.HorizontalOrigin.LEFT, heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          disableDepthTestDistance: Number.POSITIVE_INFINITY },
      });
    }
    const fresh = current.filter((alarm) => alarm.state === "new").length;
    document.getElementById("alarms").textContent = current.length
      ? `${current.length} aktuella larm${fresh ? `, ${fresh} nya` : ""}` : "Inga aktuella larm";
  };

  const refreshState = () => getJson("/api/state").then(drawState).catch(() => {
    document.getElementById("alarms").textContent = "Tjänsten svarar inte";
  });
  refreshState();
  setInterval(refreshState, STATE_MS);
  // VISA 2D in mission control: this main screen goes to the 2D map.
  setInterval(() => getJson("/api/view").then((body) => { if (body.view === "2d") window.location.assign("/2d.html"); })
    .catch(() => null), VIEW_MS);

  const data = await getJson("/api/satellites");
  credit(data.available ? `${data.label}. ${data.attribution}` : data.note);
  if (!data.available) return;
  const lib = await import("/vendor/satellite.js-7.1.0/index.js");
  const entries = new Map();
  const drawSatellites = () => {
    const now = new Date();
    document.getElementById("clock").textContent = clockText.format(now);
    for (const item of data.satellites) {
      const here = subpoint(lib, item.elements, now);
      if (!here) continue;
      const position = Cesium.Cartesian3.fromDegrees(here.longitude, here.latitude, here.height_km * 1000);
      const track = orbitTrack(lib, item.elements, now, 50, 2)
        .map((p) => Cesium.Cartesian3.fromDegrees(p.longitude, p.latitude, p.height_km * 1000));
      let entry = entries.get(item.norad);
      if (!entry) {
        const hex = SATELLITE_COLORS[item.instrument] || "#d0d0d0";
        entry = { track };
        entry.point = satelliteLayer.entities.add({
          name: `${item.name} – ${item.role}`,
          description: `${item.name} (${item.instrument}): läge nu, beräknat ur aktuella banelement (SGP4) – inte en observation.`,
          position, point: { pixelSize: 9, color: color(hex), outlineColor: color("#ffffff"), outlineWidth: 2 },
          label: { text: item.name, font: "14px system-ui, sans-serif", fillColor: color("#ffffff"), outlineColor: color("#000000"),
            outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE, pixelOffset: new Cesium.Cartesian2(10, 0),
            horizontalOrigin: Cesium.HorizontalOrigin.LEFT },
        });
        // A callback keeps the orbit dynamic, as on the demos' globe.
        satelliteLayer.entities.add({ polyline: { positions: new Cesium.CallbackProperty(() => entry.track, false),
          width: 2, material: color(hex, 0.8), arcType: Cesium.ArcType.NONE } });
        entries.set(item.norad, entry);
      } else {
        entry.point.position = position;
        entry.track = track;
      }
    }
  };
  drawSatellites();
  setInterval(drawSatellites, SATELLITE_MS);
}

start().catch((error) => { document.getElementById("credits").textContent = `Fel vid start: ${error.message}`; });
