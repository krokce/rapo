// Shared helpers of the analysis pages: dataset names and chips, value formatting, viewer filters, chart options and
// the colors of lifts, strengths and result types.
import store from "../store";
import { formatNumber, toDateTimeString } from "./format";

// Closes an analysis session without waiting, also while the tab is being closed (keepalive).
export function closeAnalysisSession(sessionId) {
  fetch(`/api/analysis-close?session_id=${encodeURIComponent(sessionId)}`, {
    method: "POST",
    keepalive: true,
    headers: { Authorization: `Bearer ${store.getters.getToken}` },
  }).catch(() => {});
}

// The number of a Results row each dataset stands for. A REP saves what it fetched, so its fetched number is its
// result table (the server resolves that).
export const DATASETS = {
  fetched_a: { kind: "fetched", side: "A", field: "fetched_number_a" },
  fetched_b: { kind: "fetched", side: "B", field: "fetched_number_b" },
  result_a: { kind: "result", side: "A", field: "error_number_a" },
  result_b: { kind: "result", side: "B", field: "error_number_b" },
};

export const KIND_ICONS = {
  numeric: { icon: "fas fa-hashtag", color: "blue-7", label: "Numeric" },
  datetime: { icon: "fas fa-calendar-alt", color: "purple-6", label: "Date/time" },
  categorical: { icon: "fas fa-tags", color: "orange-8", label: "Categorical" },
  text: { icon: "fas fa-font", color: "teal-7", label: "Text" },
};

// The order of the column cards by the profile's `group`: what partitions the records first.
export const GROUP_ORDER = ["category", "number", "date", "text"];

// The engine's own columns of a result table (RAPO_RESULT_TYPE, ...), lower case as the sample names them.
export const METADATA_PREFIX = "rapo_";

// The result types of a reconciliation, as the Results colors have them: avatar icon and color, and the bar color.
export const RESULT_TYPES = {
  Loss: { icon: "fas fa-unlink", color: "red-7", bar: "var(--rapo-type-loss)" },
  Discrepancy: { icon: "fas fa-not-equal", color: "orange-8", bar: "var(--rapo-type-discrepancy)" },
  Duplicate: { icon: "fas fa-clone", color: "purple-6", bar: "var(--rapo-type-duplicate)" },
  Match: { icon: "fas fa-check", color: "green-7", bar: "var(--rapo-type-match)" },
};

export function resultType(type) {
  return RESULT_TYPES[type] || { icon: "fas fa-tag", color: "blue-grey-5", bar: "var(--rapo-bar)" };
}

// The avatar of a dataset chip: what was fetched, the discrepancies, or a report's rows.
export function datasetAvatar(meta) {
  if (meta && meta.control_type === "REP") {
    return { icon: "fas fa-table", color: "teal-7" };
  }
  return meta && meta.kind === "fetched" ? { icon: "fas fa-database", color: "blue-grey-6" } : { icon: "fas fa-exclamation-triangle", color: "red-7" };
}

// The avatar color of a relation's strength (|r| or Cramér's V).
export function strengthColor(value) {
  const strength = Math.abs(value);
  return strength >= 0.9 ? "red-7" : strength >= 0.7 ? "orange-8" : "amber-8";
}

export function kindInfo(column) {
  const key = column && column.categorical ? "categorical" : column && column.kind;
  return KIND_ICONS[key] || KIND_ICONS.text;
}

// "Discrepancies A", "Fetched B", "Report rows"; the side is left out where the type has one side only.
export function datasetLabel(meta) {
  if (!meta) {
    return "";
  }
  if (meta.kind === "file") {
    return meta.table_name;
  }
  const sided = meta.control_type === "REC" || meta.control_type === "CMP";
  if (meta.control_type === "REP") {
    return "Report rows";
  }
  const base = meta.kind === "fetched" ? "Fetched" : "Discrepancies";
  return sided && meta.side ? `${base} ${meta.side}` : base;
}

// A value as the viewer shows it: date-times without the T, whole days without the time when asked, numbers as sent.
export function formatValue(value, kind, dateOnly = false) {
  if (value === null || value === undefined) {
    return "";
  }
  if (kind === "datetime") {
    const text = toDateTimeString(value);
    return dateOnly ? text.substring(0, 10) : text;
  }
  return String(value);
}

// A statistic for the profile cards: numbers grouped, up to `decimals` places.
export function formatStat(value, decimals = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "–";
  }
  if (typeof value !== "number") {
    return String(value);
  }
  if (Math.abs(value) >= 1e15 || (value !== 0 && Math.abs(value) < 1e-4)) {
    return value.toExponential(3);
  }
  const places = Number.isInteger(value) ? 0 : decimals;
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: places });
}

export function formatPct(value) {
  if (value === null || value === undefined) {
    return "–";
  }
  if (value > 0 && value < 0.1) {
    return "<0.1%";
  }
  return `${formatNumber(value, value >= 10 || Number.isInteger(value) ? 0 : 1)}%`;
}

function quote(value) {
  if (value === null || value === undefined) {
    return "empty";
  }
  return typeof value === "string" ? `"${value}"` : String(value);
}

// The chip text of a viewer filter.
export function describeFilter(filter) {
  const column = filter.column ? filter.column.toUpperCase() : "";
  const value = filter.value;
  switch (filter.op) {
    case "duplicated":
      return "Duplicate rows";
    case "null":
      return `${column} is empty`;
    case "notnull":
      return `${column} is not empty`;
    case "eq":
      return value === null ? `${column} is empty` : `${column} = ${quote(value)}`;
    case "ne":
      return `${column} ≠ ${quote(value)}`;
    case "in":
      return value.length > 3 ? `${column} in ${value.length} values` : `${column} in (${value.map(quote).join(", ")})`;
    case "contains":
      return `${column} contains ${quote(value)}`;
    case "starts":
      return `${column} starts with ${quote(value)}`;
    case "range": {
      const low = value.min !== null && value.min !== undefined ? `≥ ${formatValue(value.min, filter.kind)}` : "";
      const high = value.max !== null && value.max !== undefined ? `${value.max_inclusive === false ? "<" : "≤"} ${formatValue(value.max, filter.kind)}` : "";
      return `${column} ${[low, high].filter(Boolean).join(" and ")}`;
    }
    default:
      return column;
  }
}

// The filter selecting one value of a column, as clicked in a profile.
export function valueFilter(column, value) {
  return value === null || value === undefined ? { column, op: "null" } : { column, op: "eq", value };
}

// The filter selecting one histogram bin: [edge i, edge i+1), the last bin including its upper edge.
export function binFilter(column, kind, edges, index) {
  const last = index === edges.length - 2;
  return { column, kind, op: "range", value: { min: edges[index], max: edges[index + 1], max_inclusive: last } };
}

const WEEKDAY_INITIALS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
const WEEKDAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTH_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

// The parts of a naive ISO date-time edge ("2026-10-09T14:00:00"), read from the text, so no time zone applies.
function edgeParts(edge) {
  const year = Number(edge.slice(0, 4));
  const month = Number(edge.slice(5, 7));
  const day = Number(edge.slice(8, 10));
  return { year, month, day, hour: Number(edge.slice(11, 13) || 0), weekday: new Date(Date.UTC(year, month - 1, day)).getUTCDay() };
}

// The text of a bucket of a date histogram (profile `unit`): "2026-10-09 14:00 – 14:59", "Fri 2026-10-09",
// "October 2026", "2026".
export function bucketLabel(edge, unit) {
  const parts = edgeParts(edge);
  const hour = edge.slice(11, 13);
  switch (unit) {
    case "hour":
      return `${edge.slice(0, 10)} ${hour}:00 – ${hour}:59`;
    case "day":
      return `${WEEKDAY_NAMES[parts.weekday]} ${edge.slice(0, 10)}`;
    case "month":
      return `${MONTH_LONG[parts.month - 1]} ${parts.year}`;
    default:
      return String(parts.year);
  }
}

// A bucket edge as text: the day, with the time unless it is midnight.
export function edgeText(edge) {
  return edge.slice(11, 19) === "00:00:00" ? edge.slice(0, 10) : edge.slice(0, 16).replace("T", " ");
}

// The labels under a date histogram: hours every 6 (00 06 12 18 24, the day at a midnight inside), weekdays or every
// 7th day, months every 1, 3 or 6, years every 1 or 5; [{index, label}] at an edge or a bucket's middle (+ 0.5).
export function timeTicks(edges, unit) {
  const bins = edges.length - 1;
  const ticks = [];
  if (unit === "hour") {
    const step = bins <= 48 ? 6 : 12;
    edges.forEach((edge, index) => {
      const { hour } = edgeParts(edge);
      if (hour % step === 0) {
        const midnight = hour === 0 && index > 0;
        ticks.push({ index, label: midnight ? (index === bins ? "24" : edge.slice(5, 10)) : edge.slice(11, 13) });
      }
    });
  } else if (unit === "day") {
    if (bins <= 14) {
      edges.slice(0, -1).forEach((edge, index) => ticks.push({ index: index + 0.5, label: WEEKDAY_INITIALS[edgeParts(edge).weekday] }));
    } else {
      edges.forEach((edge, index) => index % 7 === 0 && index < bins && ticks.push({ index, label: edge.slice(5, 10) }));
    }
  } else {
    const every = unit === "month" ? (bins <= 12 ? 1 : bins <= 36 ? 3 : 6) : bins <= 10 ? 1 : 5;
    edges.slice(0, -1).forEach((edge, index) => {
      const { year, month } = edgeParts(edge);
      if (unit === "month" && (month - 1) % every === 0) {
        ticks.push({ index: index + 0.5, label: month === 1 || !ticks.length ? `${MONTH_NAMES[month - 1]} ${String(year).slice(2)}` : MONTH_NAMES[month - 1] });
      } else if (unit === "year" && year % every === 0) {
        ticks.push({ index: index + 0.5, label: String(year) });
      }
    });
  }
  return ticks;
}

// The range a date histogram covers, from its first bucket to its last: "2026-10-09", "2026-10-03 – 2026-10-09",
// "Oct 2025 – Sep 2026", "2021 – 2026".
export function bucketRange(edges, unit) {
  const first = edges[0];
  const last = edges[edges.length - 2];
  const parts = [first, last].map(edgeParts);
  if (unit === "hour" || unit === "day") {
    return first.slice(0, 10) === last.slice(0, 10) ? first.slice(0, 10) : `${first.slice(0, 10)} – ${last.slice(0, 10)}`;
  }
  if (unit === "month") {
    return parts.map((item) => `${MONTH_NAMES[item.month - 1]} ${item.year}`).join(" – ");
  }
  return parts[0].year === parts[1].year ? String(parts[0].year) : `${parts[0].year} – ${parts[1].year}`;
}

// The colors ECharts cannot read from CSS variables: text, axis lines and grid lines of the light and dark themes. Explicit colors
// in an option (series, visual maps) win over these.
export function chartTheme(dark) {
  const text = dark ? "#b0b0b0" : "#616161";
  const axis = { axisLabel: { color: text }, axisLine: { lineStyle: { color: dark ? "#555" : "#ccc" } }, splitLine: { lineStyle: { color: dark ? "#2c3438" : "#eceff1" } } };
  return {
    textStyle: { color: text },
    legend: { textStyle: { color: text } },
    categoryAxis: axis,
    valueAxis: axis,
    tooltip: { backgroundColor: dark ? "#2b2b2b" : "#ffffff", borderColor: dark ? "#555" : "#ccc", textStyle: { color: dark ? "#e0e0e0" : "#333" } },
  };
}

// The options every chart shares: no animation, labels inside the grid, a shadow pointer on axis tooltips.
export function baseOption({ grid, tooltip, ...rest }) {
  const axisTooltip = tooltip && tooltip.trigger === "axis" ? { axisPointer: { type: "shadow" } } : {};
  return { animation: false, grid: { containLabel: true, ...grid }, tooltip: { ...axisTooltip, ...tooltip }, ...rest };
}

// A value axis with the small labels and the light grid lines of the charts; `axisLabel` extends the defaults.
export function valueAxis({ axisLabel, ...rest } = {}) {
  return { type: "value", axisLabel: { fontSize: 10, ...axisLabel }, ...rest };
}

const LIGHT_CHIP_COLORS = new Set(["orange-8", "amber-8", "blue-grey-4"]);

// The chip color of a lift (a share over another share; null when the other share is 0): red over-represented, blue
// under-represented.
export function liftColor(lift) {
  if (lift === null || lift === undefined || lift >= 2) {
    return "red-7";
  }
  if (lift >= 1.25) {
    return "orange-8";
  }
  if (lift <= 0.5) {
    return "blue-7";
  }
  return "blue-grey-4";
}

// "×2.35", "×12", "×99+"; `only` when the other share is 0.
export function liftText(lift, only) {
  if (lift === null || lift === undefined) {
    return only;
  }
  return lift >= 100 ? "×99+" : `×${formatNumber(lift, lift >= 10 ? 0 : 2)}`;
}

// Text color that stays readable on a Quasar chip color from the strength/lift scales.
export function chipTextColor(color) {
  return LIGHT_CHIP_COLORS.has(color) ? "grey-10" : "white";
}
