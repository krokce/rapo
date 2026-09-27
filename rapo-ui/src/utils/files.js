// The Files page: the file log of one day as aggregates (get-files-day `cells`: one per datasource, hour and status), turned
// into its table rows, header totals and heatmap, all in the browser so that every filter applies at once.

import { datasourceLane } from "../constants";

// Files, records read, written and rejected, duplicates and runtime (s) of a set of cells.
function emptyTotals() {
  return { files: 0, read: 0, written: 0, rejected: 0, duplicates: 0, runtime: 0, statuses: {} };
}

function add(totals, cell) {
  totals.files += cell.files;
  totals.read += cell.read || 0;
  totals.written += cell.written || 0;
  totals.rejected += cell.rejected || 0;
  totals.duplicates += cell.duplicates || 0;
  totals.runtime += cell.runtime || 0;
  totals.statuses[cell.status] = (totals.statuses[cell.status] || 0) + cell.files;
}

// The order of the status columns; a status not listed comes after them, alphabetically.
const STATUS_ORDER = ["SUCCESS", "ERROR", "DUPLICATE", "RECYCLE", "RELOAD", "DELETE", "RECYCLED", "RELOADED", "DELETED", "WAITING", "STARTED", "PROCESSING"];

// The statuses the day has files in, whatever the filters, in column order.
export function dayStatuses(cells) {
  const present = [...new Set((cells || []).map((cell) => cell.status))];
  const rank = (status) => (STATUS_ORDER.includes(status) ? STATUS_ORDER.indexOf(status) : STATUS_ORDER.length);
  return present.sort((a, b) => rank(a) - rank(b) || String(a).localeCompare(String(b)));
}

// Totals by status over all cells (the header chips count the whole day, like Results).
export function statusTotals(cells) {
  const totals = emptyTotals();
  (cells || []).forEach((cell) => add(totals, cell));
  return totals;
}

// The rows of the table: one per datasource with files that pass the filters, plus the active datasources without any
// file that day while no hour or status is picked (so a silent one can be seen). `datasources` is the catalogue by id,
// `keep(cell)` the cell filter, `keepRow(row)` the row filter.
export function datasourceRows(day, datasources, keep, keepRow, withoutFiles) {
  const byId = new Map();
  const rowOf = (id) => {
    if (!byId.has(id)) {
      const datasource = datasources.get(id);
      byId.set(id, {
        id,
        sourcename: datasource ? datasource.sourcename : (day.names || {})[id] || `#${id}`,
        isactive: datasource ? datasource.isactive : null,
        known: Boolean(datasource),
        loggedName: (day.names || {})[id] || null,
        ...emptyTotals(),
        dayFiles: 0,
      });
    }
    return byId.get(id);
  };
  (day.cells || []).forEach((cell) => {
    const row = rowOf(cell.sourceid);
    row.dayFiles += cell.files;
    if (keep(cell)) {
      add(row, cell);
    }
  });
  if (withoutFiles) {
    datasources.forEach((datasource) => {
      if (datasource.isactive) {
        rowOf(datasource.id);
      }
    });
  }
  const rows = [];
  byId.forEach((row) => {
    if (!row.files && !(withoutFiles && !row.dayFiles)) {
      return;
    }
    const perf = (day.perf || {})[row.id] || null;
    row.perf = perf;
    row.lastSuccess = perf ? perf.last_success : null;
    row.weekBefore = (day.week_before || {})[row.id] || 0;
    row.change = row.weekBefore ? (row.dayFiles - row.weekBefore) / row.weekBefore : null;
    row.issues = issuesOf(row);
    if (keepRow(row)) {
      rows.push(Object.freeze(row));
    }
  });
  return rows;
}

// Silent: active and no file this day, though some on the same weekday a week earlier. Drop: less than half of them
// (from 10 files a week earlier, so that a small datasource is not flagged by chance). Errors: files ended in ERROR.
// Log name differs: the file log gives the SOURCEID another SOURCENAME than PDI_CORE_DS_CONFIG, so the files shown may
// belong to another datasource (an ID reused, or the configuration copied from another environment).
export const FILE_ISSUES = [
  { key: "silent", label: "Silent", color: "red-5", icon: "fas fa-volume-mute" },
  { key: "drop", label: "Drop", color: "orange-8", icon: "fas fa-arrow-down" },
  { key: "errors", label: "Errors", color: "red-5", icon: "fas fa-exclamation-circle" },
  { key: "mismatch", label: "Log name differs", color: "orange-8", icon: "fas fa-not-equal" },
];

function issuesOf(row) {
  const issues = [];
  const add = (key, title) => issues.push({ ...FILE_ISSUES.find((issue) => issue.key === key), title });
  if (row.isactive && !row.dayFiles && row.weekBefore) {
    add("silent", `No file this day, ${row.weekBefore} a week earlier`);
  } else if (row.isactive && row.weekBefore >= 10 && row.dayFiles < row.weekBefore / 2) {
    add("drop", `${row.dayFiles} file(s), ${row.weekBefore} a week earlier`);
  }
  if (row.statuses.ERROR) {
    add("errors", `${row.statuses.ERROR} file(s) ended in ERROR`);
  }
  if (row.known && row.loggedName && row.loggedName !== row.sourcename) {
    add("mismatch", `The file log names SOURCEID ${row.id} ${row.loggedName}: its files may belong to another datasource`);
  }
  return issues;
}

// Files per hour: one row per lane of the datasources shown and a Total row, 24 cells each with files and errors.
export function heatmapRows(day, datasources, keep) {
  const lanes = new Map();
  const total = { key: "total", label: "Total", cells: emptyHours() };
  (day.cells || []).forEach((cell) => {
    if (!keep(cell)) {
      return;
    }
    const datasource = datasources.get(cell.sourceid);
    const lane = datasource ? datasource.isactive : null;
    if (!lanes.has(lane)) {
      const info = lane === null ? { label: "Unknown", color: "grey-5" } : datasourceLane(lane);
      lanes.set(lane, { key: `lane-${lane}`, lane, label: info.label, color: info.color, cells: emptyHours() });
    }
    [lanes.get(lane), total].forEach((row) => {
      const hour = row.cells[cell.hour];
      hour.files += cell.files;
      if (cell.status === "ERROR") {
        hour.errors += cell.files;
      }
    });
  });
  const rows = [...lanes.values()].sort((a, b) => (a.lane ?? 99) - (b.lane ?? 99));
  return rows.length > 1 ? [...rows, total] : rows.length ? rows : [total];
}

function emptyHours() {
  return Array.from({ length: 24 }, () => ({ files: 0, errors: 0 }));
}

// 1234 → 1.2k, 1234567 → 1.2M; the exact number goes to a tooltip.
export function compactNumber(value) {
  const number = Number(value || 0);
  const units = [
    [1e9, "G"],
    [1e6, "M"],
    [1e3, "k"],
  ];
  for (const [size, unit] of units) {
    if (Math.abs(number) >= size) {
      const scaled = number / size;
      return `${scaled.toFixed(scaled < 10 ? 1 : 0)}${unit}`;
    }
  }
  return String(Math.round(number));
}

// A throughput in k records per second, with the precision it needs.
export function formatRate(value) {
  if (value === null || value === undefined) {
    return "";
  }
  return value >= 100 ? value.toFixed(0) : value >= 10 ? value.toFixed(1) : value.toFixed(2);
}
