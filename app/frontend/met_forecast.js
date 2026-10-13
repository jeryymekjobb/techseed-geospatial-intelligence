// MET Norway's weather forecast at the scenario clock, as issued then (/api/met-forecast,
// met_forecast.py): the panel's chart and summary. Pure functions; panel.js uses them, the tests
// run them in Node. The satellite monitor's lines for a new run are in satlog.js.

const MET_CHART_WIDTH = 300;
const MET_CHART_HEIGHT = 80;
const MET_WIND_SCALE_MS = 10;  // the chart's wind axis reaches at least this

function metDecimal(value) {
  return String(Math.round(value * 10) / 10).replace(".", ",");
}

// The run's hours as an SVG chart, 300 x 80: precipitation as blue bars, the wind as a navy line
// and the gust as a dashed orange one, a red line for the clock, and a date at each local midnight.
// `formatDay(ms)` gives a midnight's label, or null for any other hour.
function metForecastChart(hours, clockMs, formatDay) {
  const width = MET_CHART_WIDTH;
  const height = MET_CHART_HEIGHT;
  if (!hours.length) return "";
  const start = Date.parse(hours[0].time_utc);
  const end = Date.parse(hours[hours.length - 1].time_utc);
  const xOf = (ms) => ((ms - start) / Math.max(1, end - start)) * width;
  const windMax = Math.max(MET_WIND_SCALE_MS, ...hours.map((item) => item.gust_ms || 0));
  const rainMax = Math.max(2, ...hours.map((item) => item.precipitation_mm || 0));
  const plot = height - 14;
  const yWind = (value) => plot - (value / windMax) * (plot - 8);
  const step = width / Math.max(1, hours.length - 1);
  const parts = [];
  for (const item of hours) {
    if (!item.precipitation_mm) continue;
    const barHeight = (item.precipitation_mm / rainMax) * (plot - 8);
    parts.push(`<rect class="met-rain" x="${xOf(Date.parse(item.time_utc)) - step / 2}" y="${plot - barHeight}" width="${Math.max(1, step - 0.5)}" height="${barHeight}"></rect>`);
  }
  const line = (key) => hours.map((item, index) => `${index ? "L" : "M"}${xOf(Date.parse(item.time_utc)).toFixed(1)},${yWind(item[key] || 0).toFixed(1)}`).join(" ");
  parts.push(`<path class="met-gust" d="${line("gust_ms")}"></path>`, `<path class="met-wind" d="${line("wind_ms")}"></path>`);
  for (const item of hours) {
    const label = formatDay(Date.parse(item.time_utc));
    if (label) parts.push(`<text x="${xOf(Date.parse(item.time_utc)) + 1}" y="${height - 3}">${label}</text>`);
  }
  if (clockMs >= start && clockMs <= end) {
    const x = xOf(clockMs);
    parts.push(`<line class="rain-now" x1="${x}" x2="${x}" y1="0" y2="${plot}"></line>`);
  }
  parts.push(`<text x="${width - 2}" y="9" text-anchor="end">vind och byvind upp till ${metDecimal(windMax)} m/s, regn upp till ${metDecimal(rainMax)} mm/h</text>`);
  return parts.join("");
}

// The panel's summary rows: for each window ahead, its label and value.
function metSummaryRows(summaries) {
  return (summaries || []).map((item) => [
    `${item.hours} h`,
    `${item.wind_from} ${metDecimal(item.wind_ms)} m/s, byar ${metDecimal(item.gust_max_ms)}, regn ${metDecimal(item.precipitation_mm)} mm, `
      + `fukt ned till ${item.humidity_min_pct} %`,
  ]);
}

if (typeof module !== "undefined") {
  module.exports = { metForecastChart, metSummaryRows, MET_CHART_HEIGHT };
}
