// The texts of SMHI's stations on both maps (map2d.js's tooltips, globe.js's info box): a title and
// one fact a line, so a long text does not run out of the map panel (the user's wish on 2026-11-05).

function decimal(value) {
  return String(value).replace(".", ",");
}

function utcTime(text) {
  return text ? `${text.slice(0, 16).replace("T", " ")} UTC` : null;
}

// Each function gives the lines [title, fact, ...]; a missing fact gives no line.
function flowLines(flow) {
  return [`Vattenföring ${flow.name}`, `Flöde: ${decimal(flow.value)} m³/s`,
    flow.limits ? `Högt flöde över: ${decimal(flow.limits.high)} m³/s` : null,
    flow.limits ? `Rekord: ${decimal(flow.limits.record)} m³/s` : null,
    flow.time_utc ? `Mätt: ${utcTime(flow.time_utc)}` : null, "Källa: SMHI"].filter(Boolean);
}

function silentLines(item) {
  return [`SMHI ${item.name} (${item.kind})`,
    item.last_utc ? `Inga värden sedan: ${item.last_utc.slice(0, 10)}` : "Har aldrig lämnat värden",
    "Kan vara ur funktion", "Källa: SMHI"];
}

function levelGaugeLines(gauge) {
  return [`Vattenstånd ${gauge.name}`, `Nivå: ${(gauge.value_cm / 100).toFixed(2).replace(".", ",")} m (höjdsystem ej angivet)`,
    gauge.record_cm != null ? `Högsta i arkivet: ${(gauge.record_cm / 100).toFixed(2).replace(".", ",")} m (${gauge.record_day})` : null,
    gauge.time_utc ? `Mätt: ${utcTime(gauge.time_utc)}` : null, "Källa: SMHI"].filter(Boolean);
}

function seaLines(gauge) {
  return [`Havsvattenstånd ${gauge.name}`, `Nivå: ${decimal(gauge.value_cm)} cm i RH2000`,
    gauge.limit_cm != null ? `Larm från: ${decimal(gauge.limit_cm)} cm` : null,
    gauge.time_utc ? `Mätt: ${utcTime(gauge.time_utc)}` : null, "Källa: SMHI"].filter(Boolean);
}

// A weather station's latest values, as SMHI gives them; a municipal rain gauge reports only hours with rain.
function stationLines(station) {
  const v = station.values;
  const time = Object.values(station.times).sort().pop();
  return [`SMHI ${station.name}`,
    v.temp_c !== undefined ? `Temperatur: ${decimal(v.temp_c)} °C` : null,
    v.wind_ms !== undefined ? `Vind: ${decimal(v.wind_ms)} m/s${v.wind_from_deg !== undefined ? ` från ${v.wind_from_deg}°` : ""}` : null,
    v.rain_1h_mm !== undefined ? `Regn senaste timmen: ${decimal(v.rain_1h_mm)} mm` : null,
    v.rain_day_mm !== undefined ? `Regn senaste dygnet (06–06): ${decimal(v.rain_day_mm)} mm` : null,
    v.rain_24h_mm !== undefined ? (v.rain_24h_mm ? `Regn senaste dygnet: ${decimal(v.rain_24h_mm)} mm` : "Inget regn uppmätt senaste dygnet") : null,
    time ? `Mätt: ${utcTime(time)}` : null, "Källa: SMHI"].filter(Boolean);
}
