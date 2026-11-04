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
const SATELLITE_COLORS = { MODIS: "#ff8c00", VIIRS: "#ff2a00", OLI: "#4fc3f7", SAR: "#b388ff", MSI: "#69f0ae" };
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

// As the 2D map (map2d.js addBaseMaps): OpenStreetMap's standard map over Natural Earth, the
// municipality's map over it, the road numbers and railway tunnels only inside the municipality, and
// the demos' offline map in OpenStreetMap's place when it cannot be fetched.
const ONLINE_FAILURES = 5;
function addBaseMaps(viewer, maps) {
  const rectangle = (bbox) => Cesium.Rectangle.fromDegrees(...bbox);
  const online = new Cesium.UrlTemplateImageryProvider({ url: maps.online.url, maximumLevel: 18 });
  const onlineLayer = viewer.imageryLayers.addImageryProvider(online);
  credit(maps.online.attribution);
  let failures = 0;
  let offline = null;
  online.errorEvent.addEventListener(() => {
    failures += 1;
    if (offline || !maps.offline || failures < ONLINE_FAILURES) return;
    offline = new Cesium.ImageryLayer(new Cesium.UrlTemplateImageryProvider({
      url: maps.offline.url, maximumLevel: 18, rectangle: rectangle(maps.offline.bbox) }));
    viewer.imageryLayers.add(offline, viewer.imageryLayers.indexOf(onlineLayer) + 1);
  });
  const municipal = [];
  for (const item of maps.municipal) {
    municipal.push(viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
      url: item.url, minimumLevel: Math.max(item.min_zoom, MUNICIPAL_MIN_LEVEL), maximumLevel: item.max_zoom,
      rectangle: rectangle(item.bbox) })));
    credit(item.attribution);
  }
  if (maps.overlay && maps.municipal.length) {
    municipal.push(viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
      url: maps.overlay.url, maximumLevel: 18, rectangle: rectangle(maps.municipal[0].bbox) })));
  }
  return municipal;
}

// The scenarios' overlays: MCF's flood map (WMS) and SMHI's radar as one image over the area, put
// back after every poll, when a newer one may have come.
function addFlood(viewer, flood) {
  if (!flood) return [];
  // Over the area's box only, so the service is not asked for the whole world.
  const layer = viewer.imageryLayers.addImageryProvider(new Cesium.WebMapServiceImageryProvider({
    url: flood.url, layers: flood.layers, parameters: { format: "image/png", transparent: true, styles: "" } }));
  layer.alpha = 0.6;
  credit(flood.attribution);
  return [layer];
}

// One image over the area, put back when a newer one has come (the radar after every poll, the
// satellite image when a newer scene is chosen), and shown or hidden by mission control's layers.
function imageDrawer(viewer, url, bbox, alpha) {
  let layer = null;
  let shown = null;
  let visible = true;
  return {
    draw(key, attribution) {
      if (!key || key === shown) return;
      shown = key;
      const next = viewer.imageryLayers.addImageryProvider(new Cesium.SingleTileImageryProvider({
        url: `${url}?at=${encodeURIComponent(key)}`, rectangle: Cesium.Rectangle.fromDegrees(...bbox), tileWidth: 256, tileHeight: 256 }));
      next.alpha = alpha;
      next.show = visible;
      if (layer) viewer.imageryLayers.remove(layer);
      layer = next;
      credit(attribution);
    },
    show(value) {
      visible = Boolean(value);
      if (layer) layer.show = visible;
    },
  };
}

// A weather station's latest values, as SMHI gives them (as map2d.js stationText).
function stationText(station) {
  const v = station.values;
  const parts = [];
  if (v.temp_c !== undefined) parts.push(`${v.temp_c} °C`);
  if (v.wind_ms !== undefined) parts.push(`vind ${v.wind_ms} m/s${v.wind_from_deg !== undefined ? ` från ${v.wind_from_deg}°` : ""}`);
  if (v.rain_1h_mm !== undefined) parts.push(`regn ${v.rain_1h_mm} mm senaste timmen`);
  if (v.rain_day_mm !== undefined) parts.push(`regn ${v.rain_day_mm} mm senaste dygnet (06–06)`);
  const time = Object.values(station.times).sort().pop();
  return `${parts.join(", ")}${time ? ` – SMHI, ${time}` : ""}`;
}

// The marks, as on the 2D map (map2d.js): SMHI's stations round with a white ring, blue, and red while
// one of them alarms; the protected objects and other places of interest small, round and yellow.
const STATION_MARKS = { normal: "#1565c0", alarm: "#c62828" };
function alarming(state, key) {
  return state.alarms.some((alarm) => alarm.id === key && alarm.current && alarm.state !== "dismissed");
}
const OBJECT_MARK = "#ffd600";
// The simulated level sensors (levels.py), as on the 2D map: a magenta ring, blue, red while alarming.
const LEVEL_RING = "#e040fb";
function levelText(sensor) {
  const value = sensor.value == null ? `inga värden från ${sensor.station_name} ännu`
    : `${sensor.station_name} ${sensor.percent ?? "–"} % av högsta dygnsflöde i arkivet`;
  return `${sensor.alarm ? "LARMAR" : "inget larm"}, ${value} (simulerad nivågivare, följer SMHI)`;
}

// SMHI's forecast grid (/api/weather) as the scenarios' globe draws ERA5-Land's wind and MET Norway's
// chart (map3d.js): barbs lying on the ground, and the isobars, highs and lows, rain and thunder over
// Scandinavia. Mission control's VINDPILAR and VÄDERKARTA show them (/api/view's layers).
const BARB_STYLE = "<style>path,circle{fill:none;stroke:#0b3d91;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}"
  + ".halo{stroke:#fff;stroke-width:4.5;opacity:.85}.pennant{fill:#0b3d91}</style>";
const CHART_VIEW = { lon: 17, lat: 62, height: 3_600_000 };
// The arrows show only near the area, so they do not crowd into one blot over Scandinavia.
const WIND_SHOWN_M = 400_000;
// As the scenarios' globe (map3d.js MUNICIPAL_MIN_LEVEL): the municipal map from this level, the
// offline OpenStreetMap below it, so its names are not drawn huge and blurred from afar.
const MUNICIPAL_MIN_LEVEL = 11;
const barbImages = new Map();
function barbImage(speed) {
  const svg = windBarbSvg(speed);
  if (!barbImages.has(svg)) {
    const sized = svg.replace(/^<svg /, '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" ').replace(/^(<svg [^>]*>)/, `$1${BARB_STYLE}`);
    barbImages.set(svg, `data:image/svg+xml;charset=utf-8,${encodeURIComponent(sized)}`);
  }
  return barbImages.get(svg);
}

function weatherDrawer(viewer) {
  const wind = new Cesium.CustomDataSource("wind");
  const chart = new Cesium.CustomDataSource("chart");
  viewer.dataSources.add(wind);
  viewer.dataSources.add(chart);
  let rain = null;
  let shown = null;
  let layers = { wind: true, chart: false };
  const apply = () => {
    wind.show = Boolean(layers.wind);
    chart.show = Boolean(layers.chart);
    if (rain) rain.show = Boolean(layers.chart);
  };
  const draw = (data) => {
    wind.entities.removeAll();
    for (const point of data.wind || []) {
      wind.entities.add({ position: Cesium.Cartesian3.fromDegrees(point.longitude, point.latitude),
        billboard: { image: barbImage(point.speed_ms), alignedAxis: Cesium.Cartesian3.UNIT_Z, width: 64, height: 64,
          rotation: -Cesium.Math.toRadians((point.from_deg + 180) % 360), heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          disableDepthTestDistance: Number.POSITIVE_INFINITY, distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, WIND_SHOWN_M) } });
    }
    chart.entities.removeAll();
    if (rain) viewer.imageryLayers.remove(rain);
    rain = null;
    if (!data.chart) return apply();
    rain = viewer.imageryLayers.addImageryProvider(new Cesium.SingleTileImageryProvider({ url: data.chart.rain_png,
      rectangle: Cesium.Rectangle.fromDegrees(...data.chart.bbox), tileWidth: 256, tileHeight: 256 }));
    for (const line of data.chart.lines) {
      const main = line.hpa % 8 === 0;
      chart.entities.add({ polyline: { positions: line.coords.map(([lat, lon]) => Cesium.Cartesian3.fromDegrees(lon, lat)),
        width: main ? 2 : 1, material: color("#1f3a7a", main ? 0.9 : 0.6), clampToGround: true } });
    }
    for (const centre of data.chart.centres) {
      chart.entities.add({ position: Cesium.Cartesian3.fromDegrees(centre.longitude, centre.latitude),
        label: { text: `${centre.kind} ${centre.hpa}`, font: "bold 22px system-ui, sans-serif",
          fillColor: color(centre.kind === "H" ? "#1565c0" : "#c62828"), outlineColor: color("#ffffff"), outlineWidth: 3,
          style: Cesium.LabelStyle.FILL_AND_OUTLINE, disableDepthTestDistance: Number.POSITIVE_INFINITY } });
    }
    for (const [lat, lon] of data.chart.thunder) {
      chart.entities.add({ position: Cesium.Cartesian3.fromDegrees(lon, lat),
        label: { text: "⚡", font: "22px system-ui, sans-serif", disableDepthTestDistance: Number.POSITIVE_INFINITY } });
    }
    apply();
  };
  return {
    refresh(summary) {
      const key = summary ? `${summary.created_utc}|${summary.valid_utc}` : null;
      if (!key || key === shown) return;
      shown = key;
      getJson("/api/weather").then((data) => { draw(data); credit(data.attribution); }).catch(() => { shown = null; });
    },
    show(next, home) {
      const opened = next.chart && !layers.chart;
      const closed = !next.chart && layers.chart;
      layers = { ...next };
      apply();
      if (opened) viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees(CHART_VIEW.lon, CHART_VIEW.lat, CHART_VIEW.height), duration: 2 });
      if (closed) home();
    },
  };
}

async function start() {
  const config = await getJson("/api/config");
  document.getElementById("title").textContent = `Övervakning – ${config.area.name}`;
  document.title = `Övervakning – ${config.area.name} – 3D`;
  // The scenarios' 3D terrain when the area has it, as on the demos' globe (map3d.js).
  const terrainProvider = config.terrain
    ? await Cesium.CesiumTerrainProvider.fromUrl(config.terrain, { requestVertexNormals: true }).catch(() => null) : null;
  const viewer = new Cesium.Viewer("globe", {
    ...(terrainProvider ? { terrainProvider } : {}),
    baseLayer: Cesium.ImageryLayer.fromProviderAsync(
      Cesium.TileMapServiceImageryProvider.fromUrl(Cesium.buildModuleUrl("Assets/Textures/NaturalEarthII"))),
    baseLayerPicker: false, geocoder: false, homeButton: false, sceneModePicker: false, navigationHelpButton: false,
    fullscreenButton: false, timeline: false, animation: false, infoBox: true, selectionIndicator: false,
  });
  viewer.bottomContainer.style.display = "none";
  credit("Natural Earth II");
  // Mission control's map layers (service.LAYERS): imagery layers and data sources shown or hidden.
  const municipal = addBaseMaps(viewer, config.maps);
  const flood = addFlood(viewer, config.layers.flood);
  const floodHighest = addFlood(viewer, config.layers.flood_highest);
  const overlays = {};
  for (const item of config.layers.overlays || []) {
    const layer = viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
      url: item.url, minimumLevel: item.min_zoom, maximumLevel: item.max_zoom, rectangle: Cesium.Rectangle.fromDegrees(...item.bbox) }));
    layer.alpha = 0.8;
    overlays[item.id] = layer;
    credit(item.attribution);
  }
  const landsatImage = imageDrawer(viewer, "/api/landsat.png", config.layers.radar.bbox, 1.0);
  const radarImage = imageDrawer(viewer, "/api/radar.png", config.layers.radar.bbox, 0.85);
  const satelliteImage = imageDrawer(viewer, "/api/satellite.png", config.layers.radar.bbox, 1.0);
  const s1Radar = imageDrawer(viewer, "/api/s1radar.png", config.layers.radar.bbox, 0.9);
  const s1Water = imageDrawer(viewer, "/api/s1water.png", config.layers.radar.bbox, 1.0);
  const s1Wetness = imageDrawer(viewer, "/api/s1wetness.png", config.layers.radar.bbox, 0.85);
  const drawRadar = (stats, polled) => radarImage.draw(stats?.latest_utc ? `${stats.latest_utc}|${polled}` : null, config.layers.radar.attribution);
  const sources = {};
  for (const name of ["stations", "levels", "facilities", "names", "firms"]) {
    sources[name] = new Cesium.CustomDataSource(name);
    viewer.dataSources.add(sources[name]);
  }
  const applyLayers = (layers) => {
    for (const layer of municipal) layer.show = Boolean(layers.municipal);
    for (const layer of flood) layer.show = Boolean(layers.flood);
    for (const layer of floodHighest) layer.show = Boolean(layers.flood_highest);
    for (const [id, layer] of Object.entries(overlays)) layer.show = Boolean(layers[id]);
    landsatImage.show(layers.landsat);
    radarImage.show(layers.radar);
    satelliteImage.show(layers.satellite);
    s1Radar.show(layers.s1radar);
    s1Water.show(layers.s1water);
    s1Wetness.show(layers.s1wetness);
    for (const [name, source] of Object.entries(sources)) source.show = Boolean(layers[name]);
  };
  getJson("/api/assets").then((assets) => {
    for (const item of assets.facilities || []) {
      sources.facilities.entities.add({ name: escapeText(item.name), description: escapeText(`${item.category} – ${item.source}`),
        position: Cesium.Cartesian3.fromDegrees(item.longitude, item.latitude),
        point: { pixelSize: 7, color: color(OBJECT_MARK), outlineColor: color("#5d4300"), outlineWidth: 1,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, disableDepthTestDistance: Number.POSITIVE_INFINITY,
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 150_000) } });
    }
    for (const place of assets.places || []) {
      sources.names.entities.add({ position: Cesium.Cartesian3.fromDegrees(place.longitude, place.latitude),
        label: { text: place.name, font: place.type === "town" ? "bold 16px system-ui, sans-serif" : "600 13px system-ui, sans-serif",
          fillColor: color("#1d1d1b"), outlineColor: color("#ffffff"), outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, disableDepthTestDistance: Number.POSITIVE_INFINITY,
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, place.type === "hamlet" ? 40_000 : 150_000) } });
    }
    if (assets.attribution) credit(assets.attribution);
  }).catch(() => null);
  const weather = weatherDrawer(viewer);
  // From the south and above, as the demos' view of the incident (map3d.js FIRE_VIEW), far enough
  // to see the whole municipality.
  const [lat, lon] = config.area.centre;
  const home = () => {
    viewer.camera.lookAt(Cesium.Cartesian3.fromDegrees(lon, lat),
      new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(-55), VIEW_RANGE_M));
    viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
  };
  home();

  const sites = new Cesium.CustomDataSource("sites");
  const satelliteLayer = new Cesium.CustomDataSource("satellites");
  viewer.dataSources.add(sites);
  viewer.dataSources.add(satelliteLayer);
  let border = null;

  const drawState = (state) => {
    const context = state.context || {};
    drawRadar(context.radar, state.polled_utc);
    const image = context.satellite_image;
    if (image) satelliteImage.draw(image.time_utc, image.attribution);
    const landsat = context.landsat_image;
    if (landsat) landsatImage.draw(landsat.time_utc, landsat.attribution);
    const pass = context.radar_pass;
    if (pass) {
      s1Radar.draw(pass.time_utc, pass.attribution);
      s1Water.draw(pass.time_utc, pass.attribution);
      s1Wetness.draw(pass.time_utc, pass.attribution);
    }
    weather.refresh(context.weather);
    if (context.border && !border) {
      border = Cesium.GeoJsonDataSource.load(context.border, { stroke: color("#2979ff"), strokeWidth: 3, fill: color("#2979ff", 0.04),
        clampToGround: true }).then((source) => viewer.dataSources.add(source));
    }
    sites.entities.removeAll();
    const point = (lat, lon, hex, size, name, description, target = sites) => target.entities.add({
      name: escapeText(name), description: escapeText(description), position: Cesium.Cartesian3.fromDegrees(lon, lat),
      point: { pixelSize: size, color: color(hex), outlineColor: color("#ffffff"), outlineWidth: 2,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, disableDepthTestDistance: Number.POSITIVE_INFINITY },
    });
    sources.stations.entities.removeAll();
    sources.firms.entities.removeAll();
    sources.levels.entities.removeAll();
    for (const sensor of context.level_sensors || []) {
      sources.levels.entities.add({
        name: escapeText(`${sensor.name} (simulerad)`), description: escapeText(levelText(sensor)),
        position: Cesium.Cartesian3.fromDegrees(sensor.longitude, sensor.latitude),
        point: { pixelSize: 10, color: color(sensor.alarm ? STATION_MARKS.alarm : STATION_MARKS.normal), outlineColor: color(LEVEL_RING),
          outlineWidth: 2, heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, disableDepthTestDistance: Number.POSITIVE_INFINITY },
      });
    }
    for (const flow of context.flows || []) {
      const mark = alarming(state, `flow-${flow.station}`) ? STATION_MARKS.alarm : STATION_MARKS.normal;
      if (flow.latitude != null) point(flow.latitude, flow.longitude, mark, 12, `Vattenföring ${flow.name}`,
        `${flow.value} m³/s, ${flow.time_utc} – SMHI`, sources.stations);
    }
    for (const station of context.weather_stations || []) {
      const mark = alarming(state, `rain-${station.station}`) ? STATION_MARKS.alarm : STATION_MARKS.normal;
      point(station.latitude, station.longitude, mark, 12, `SMHI ${station.name}`, stationText(station), sources.stations);
    }
    for (const fire of context.firms || []) {
      point(fire.latitude, fire.longitude, "#ff6d00", 8, `FIRMS ${fire.satellite}`, `${fire.instrument} ${fire.time_utc} – NASA FIRMS`, sources.firms);
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
  setInterval(() => getJson("/api/view").then((body) => {
    if (body.view === "2d") window.location.assign("/2d.html");
    else {
      weather.show(body.layers || {}, home);
      applyLayers(body.layers || {});
    }
  }).catch(() => null), VIEW_MS);

  const data = await getJson("/api/satellites");
  credit(data.available ? `${data.label}. ${data.attribution}` : data.note);
  if (!data.available) return;
  const lib = await import("/vendor/satellite.js-7.1.0/index.js");
  const entries = new Map();
  const drawSatellites = () => {
    const now = new Date();
    document.getElementById("clock").textContent = clockText.format(now);
    // A geostationary satellite (Meteosat) stays over 0 degrees, far outside the globe's view of the area.
    for (const item of data.satellites.filter((satellite) => !satellite.geostationary)) {
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
