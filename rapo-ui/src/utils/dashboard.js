// The Dashboard (DashboardPage.vue): its sections and panels, the layout a browser keeps of them and the links its charts
// open.
import { FILES_ICON, KPI_ICON } from "../constants";
import { dayLabel, formatNumber } from "./format";

// The order of the rail. `available` says when a section shows (info is get /info, health the store's health level).
export const DASHBOARD_SECTIONS = [
  { id: "overview", label: "Overview", icon: "fas fa-th-large" },
  { id: "runs", label: "Runs", icon: "fas fa-tasks" },
  { id: "scheduler", label: "Scheduler", icon: "fas fa-clock" },
  { id: "files", label: "Files", icon: FILES_ICON, available: (info) => Boolean(info && info.datasources_log) },
  { id: "kpis", label: "KPIs", icon: KPI_ICON, available: (info) => Boolean(info && info.kpi_available) },
  { id: "health", label: "Health", icon: "fas fa-heartbeat" },
];

// The height (px) of the panels that show the day and the instance in tiles (Today, Instance health): the same, so the two
// read as a pair; a panel's `height` is its minimum, so tiles that wrap to more rows still fit.
export const TALL_HEIGHT = 300;

// Every panel in its default order. `part`: the get-dashboard part it shows (null: data of its own); `height`: its minimum height in px, if any; `width`: its share
// of a row in sixths (2 a third, 4 two thirds, 6 the row); `minWidth` (px): below it the panel wraps to the next row.
// The panels of a row grow to fill it, so a row is always full, also beside a hidden panel.
export const DASHBOARD_PANELS = [
  { id: "tiles", section: "overview", title: "Today", part: "tiles", width: 6, height: TALL_HEIGHT },
  { id: "run-timeline", section: "runs", title: "Runs over time", part: "timeline", width: 6 },
  { id: "run-status", section: "runs", title: "Runs by status", part: "timeline", width: 2, minWidth: 300 },
  { id: "run-types", section: "runs", title: "Runs by type", part: "runs", width: 2, minWidth: 300 },
  { id: "run-triggers", section: "runs", title: "Runs by trigger", part: "runs", width: 2, minWidth: 300 },
  { id: "run-slowest", section: "runs", title: "Slowest controls", part: "runs", width: 2, minWidth: 300 },
  { id: "run-volume", section: "runs", title: "Records fetched and discrepancies", part: "runs", width: 2, minWidth: 300 },
  { id: "run-heatmap", section: "runs", title: "Runs by weekday and hour", part: "runs", width: 2, minWidth: 380 },
  { id: "scheduler", section: "scheduler", title: "Last and next 24 hours", part: "scheduler", width: 6 },
  { id: "files-timeline", section: "files", title: "Files over time", part: "files", width: 6 },
  { id: "files-status", section: "files", title: "Files by status", part: "files", width: 2, minWidth: 300 },
  { id: "files-top", section: "files", title: "Top datasources", part: "files", width: 4, minWidth: 560 },
  { id: "files-datasources", section: "files", title: "Datasources", part: "files", width: 2, minWidth: 300 },
  { id: "files-loading", section: "files", title: "Loading", part: "files", width: 4, minWidth: 560 },
  { id: "kpi-heatmap", section: "kpis", title: "KPI alarms by control", part: "kpis", width: 6 },
  { id: "health-tiles", section: "health", title: "Instance health", part: null, width: 6, height: TALL_HEIGHT },
];

export const PANELS_BY_ID = Object.fromEntries(DASHBOARD_PANELS.map((panel) => [panel.id, panel]));

// The spans of the header chips; the server's (rapo/dashboard/spans.py).
export const DASHBOARD_SPANS = [
  { value: "24h", label: "24h", title: "The last 24 hours, by hour" },
  { value: "7d", label: "7d", title: "The last 7 days, by day" },
  { value: "30d", label: "30d", title: "The last 30 days, by day" },
];

const SPAN_KEY = "rapo_dashboard_span";
const LAYOUT_KEY = "rapo_dashboard_layout";
const LAYOUT_VERSION = 1;

export function readSpan() {
  try {
    const span = localStorage.getItem(SPAN_KEY);
    return DASHBOARD_SPANS.some((item) => item.value === span) ? span : "7d";
  } catch (error) {
    return "7d";
  }
}

export function saveSpan(span) {
  try {
    localStorage.setItem(SPAN_KEY, span);
  } catch (error) {
    // Not remembered, which is all a failure costs.
  }
}

// The default layout: every panel shown, in the registry's order.
export function defaultLayout() {
  const order = {};
  DASHBOARD_PANELS.forEach((panel) => (order[panel.section] = [...(order[panel.section] || []), panel.id]));
  return { v: LAYOUT_VERSION, order, hidden: [] };
}

// The layout this browser keeps, merged with the registry: panels it does not know are dropped, panels added since
// are put at their default place.
export function readLayout() {
  const layout = defaultLayout();
  let saved = null;
  try {
    saved = JSON.parse(localStorage.getItem(LAYOUT_KEY) || "null");
  } catch (error) {
    saved = null;
  }
  if (!saved || saved.v !== LAYOUT_VERSION) {
    return layout;
  }
  Object.keys(layout.order).forEach((section) => {
    const known = layout.order[section];
    const kept = ((saved.order && saved.order[section]) || []).filter((id) => known.includes(id));
    known.forEach((id, index) => {
      if (!kept.includes(id)) {
        kept.splice(Math.min(index, kept.length), 0, id);
      }
    });
    layout.order[section] = kept;
  });
  layout.hidden = (saved.hidden || []).filter((id) => PANELS_BY_ID[id]);
  return layout;
}

export function saveLayout(layout) {
  try {
    localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout));
  } catch (error) {
    // Not remembered, which is all a failure costs.
  }
}

// The shown panels of a section, in the layout's order.
export function sectionPanels(layout, section) {
  return (layout.order[section] || []).filter((id) => !layout.hidden.includes(id)).map((id) => PANELS_BY_ID[id]);
}

// The layout with a panel moved by `delta` places among the shown panels of its section.
export function movePanel(layout, id, delta) {
  const panel = PANELS_BY_ID[id];
  const shown = sectionPanels(layout, panel.section).map((item) => item.id);
  const index = shown.indexOf(id);
  const target = shown[index + delta];
  return target ? dropPanel(layout, id, target) : layout;
}

// The layout with a panel put in the place of another of its section (dragged onto it).
export function dropPanel(layout, id, targetId) {
  const panel = PANELS_BY_ID[id];
  if (!panel || id === targetId || !PANELS_BY_ID[targetId] || PANELS_BY_ID[targetId].section !== panel.section) {
    return layout;
  }
  const order = [...layout.order[panel.section]];
  const from = order.indexOf(id);
  const to = order.indexOf(targetId);
  order.splice(from, 1);
  order.splice(to, 0, id);
  return { ...layout, order: { ...layout.order, [panel.section]: order } };
}

export function hidePanel(layout, id) {
  return { ...layout, hidden: [...new Set([...layout.hidden, id])] };
}

export function showPanel(layout, id) {
  return { ...layout, hidden: layout.hidden.filter((item) => item !== id) };
}

// The get-dashboard parts the shown panels need.
export function neededParts(panels) {
  return [...new Set(panels.map((panel) => panel.part).filter(Boolean))];
}

// The columns of a grid of `count` tiles in `width` px: the most of `choices` (at most `count`) whose tiles stay `min` px
// wide; the choices divide the usual counts, so the rows stay full (12 tiles: 6 x 2, 4 x 3, 3 x 4, 2 x 6).
export function gridColumns(width, count, { min = 150, gap = 6, choices = [6, 4, 3, 2, 1] } = {}) {
  const fitting = choices.filter((columns) => columns <= Math.max(count, 1) && (!width || (width - (columns - 1) * gap) / columns >= min));
  return fitting.length ? fitting[0] : choices[choices.length - 1];
}

// A bucket of a span as an axis label: "06.10" for a day, "14" for an hour.
export function bucketAxis(bucket, unit) {
  return unit === "hour" ? bucket.slice(11, 13) : `${bucket.slice(8, 10)}.${bucket.slice(5, 7)}`;
}

// The columns of a HeatStrip over a span's buckets: a label every day (every 5th of 30) or every 3rd hour, midnight
// marked in hours.
export function bucketColumns(buckets, unit) {
  const every = unit === "hour" ? 3 : buckets.length <= 10 ? 1 : 5;
  return buckets.map((bucket, index) => ({
    label: index % every === 0 ? bucketAxis(bucket, unit) : "",
    title: bucketTitle(bucket, unit),
    divider: unit === "hour" && index > 0 && bucket.slice(11, 13) === "00",
  }));
}

// A bucket in a tooltip: "Mon 06.10.2026", or "Mon 06.10.2026 14:00–15:00".
export function bucketTitle(bucket, unit) {
  const day = dayLabel(bucket.slice(0, 10));
  if (unit !== "hour") {
    return day;
  }
  const hour = Number(bucket.slice(11, 13));
  return `${day} ${String(hour).padStart(2, "0")}:00–${String((hour + 1) % 24).padStart(2, "0")}:00`;
}

// The Results page of a bucket (its day, and its hour for an hourly span), with more filters; no date for the server's
// today, so the page follows the day.
export function resultsLink(bucket, unit, today, filters = {}) {
  const query = { ...filters };
  const day = bucket ? bucket.slice(0, 10) : null;
  if (day && day !== today) {
    query.date = day;
  }
  if (bucket && unit === "hour") {
    query.hour = String(Number(bucket.slice(11, 13)));
  }
  return { path: "/results", query };
}

// The same for the Files page, on the database's clock.
export function filesLink(bucket, unit, today, filters = {}) {
  const link = resultsLink(bucket, unit, today, filters);
  return { ...link, path: "/files" };
}

// How a tile's value compares with last week's: {text, up, bad} or null. `badWhenUp` for errors, rejects, alarms.
export function tileDelta(tile, badWhenUp) {
  if (!tile || tile.today === null || tile.today === undefined || tile.last_week === null || tile.last_week === undefined) {
    return null;
  }
  const difference = Number(tile.today) - Number(tile.last_week);
  if (Math.abs(difference) < 1e-9) {
    return { text: "Same as last week", up: null, bad: false };
  }
  const up = difference > 0;
  const base = Number(tile.last_week);
  const relative = base ? ` (${up ? "+" : ""}${formatNumber((difference * 100) / base, 0)}%)` : "";
  return { text: `${up ? "▲" : "▼"} ${formatNumber(Math.abs(difference), Number.isInteger(difference) ? 0 : 2)}${relative} vs last week`, up, bad: badWhenUp ? up : !up };
}
