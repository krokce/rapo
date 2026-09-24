// Shared helpers of the data analysis page: dataset names, value formatting, viewer filters and chart options.
import { formatNumber, toDateTimeString } from "./format";

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

export function kindInfo(column) {
  const key = column && column.categorical ? "categorical" : column && column.kind;
  return KIND_ICONS[key] || KIND_ICONS.text;
}

// "Discrepancies A", "Fetched B", "Report rows"; the side is left out where the type has one side only.
export function datasetLabel(meta) {
  if (!meta) {
    return "";
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

export function formatBytes(value) {
  if (!value) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB"];
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${formatNumber(value, index ? 1 : 0)} ${units[index]}`;
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

function binLabel(low, high, kind) {
  if (kind === "datetime") {
    return toDateTimeString(low);
  }
  return `${formatStat(low)} – ${formatStat(high)}`;
}

// ECharts option of a histogram from {counts, edges}.
export function histogramOption(histogram, kind, color = "#5c6bc0") {
  const { counts, edges } = histogram;
  const labels = counts.map((count, index) => binLabel(edges[index], edges[index + 1], kind));
  return {
    animation: false,
    grid: { left: 8, right: 16, top: 12, bottom: 4, containLabel: true },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (items) => {
        const index = items[0].dataIndex;
        const range = kind === "datetime" ? `${toDateTimeString(edges[index])} – ${toDateTimeString(edges[index + 1])}` : labels[index];
        return `${range}<br/><b>${formatNumber(counts[index])}</b> rows`;
      },
    },
    xAxis: {
      type: "category",
      data: labels,
      axisLabel: { fontSize: 10, hideOverlap: true, formatter: (label) => (kind === "datetime" ? label.substring(0, 16) : label) },
      axisTick: { alignWithLabel: true },
    },
    yAxis: { type: "value", axisLabel: { fontSize: 10 }, splitLine: { lineStyle: { color: "#eceff1" } } },
    series: [{ type: "bar", data: counts, barCategoryGap: "8%", itemStyle: { color }, cursor: "pointer" }],
  };
}

// ECharts option of a small distribution over fixed labels (hours, weekdays).
export function distributionOption(labels, counts, color = "#7e57c2") {
  return {
    animation: false,
    grid: { left: 40, right: 8, top: 8, bottom: 24 },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, formatter: (items) => `${items[0].name}<br/><b>${formatNumber(items[0].value)}</b> rows` },
    xAxis: { type: "category", data: labels, axisLabel: { fontSize: 10 } },
    yAxis: { type: "value", axisLabel: { fontSize: 10 }, splitLine: { lineStyle: { color: "#eceff1" } } },
    series: [{ type: "bar", data: counts, itemStyle: { color } }],
  };
}

export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
export const HOURS = Array.from({ length: 24 }, (item, index) => String(index).padStart(2, "0"));
