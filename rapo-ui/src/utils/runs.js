// Runs as get-control-runs answers them, shared by the Results page and the editor's Run log (RunTable, RunSummary).
import { CONTROL_TYPES, RUN_STATUSES, TRIGGER_TYPES } from "../constants";
import { toDateString, toDateTimeString } from "./format";

// What started the run (rapo_scheduler_event), a question mark when the run manager did not start it.
export function triggerOf(run) {
  return TRIGGER_TYPES[run.trigger_type] || { label: run.trigger_type || "Trigger not recorded", icon: "fas fa-question" };
}

export function triggerTitle(run) {
  if (!run.trigger_type) {
    return "Trigger not recorded";
  }
  const details = [
    run.scheduled_time && (run.trigger_type === "SCHEDULE" || run.trigger_type === "CATCHUP") ? `scheduled for ${toDateTimeString(run.scheduled_time)}` : null,
    run.trigger_message,
  ].filter(Boolean);
  return `Started by: ${triggerOf(run).label}${details.length ? ` (${details.join("; ")})` : ""}`;
}

// The controls whose latest run (the highest process ID) ended in error, by name.
function failingControls(rows) {
  const latest = new Map();
  rows.forEach((row) => {
    const seen = latest.get(row.control_id);
    if (!seen || row.process_id > seen.process_id) latest.set(row.control_id, row);
  });
  return [...latest.values()]
    .filter((row) => row.status === "E")
    .map((row) => row.control_name)
    .sort();
}

// Totals of runs, in the order of the type, status and trigger constants (a trigger not recorded last).
export function runSummary(rows) {
  const sum = (value) => rows.reduce((total, row) => total + (Number(value(row)) || 0), 0);
  const countBy = (field, order) => {
    const counts = new Map();
    rows.forEach((row) => counts.set(row[field], (counts.get(row[field]) || 0) + 1));
    return [...counts.keys()].sort((a, b) => order.indexOf(a) - order.indexOf(b)).map((key) => ({ key, count: counts.get(key) }));
  };
  return {
    controls: new Set(rows.map((row) => row.control_id)).size,
    runs: rows.length,
    types: countBy("control_type", Object.keys(CONTROL_TYPES)),
    statuses: countBy("status", Object.keys(RUN_STATUSES)),
    triggers: countBy("trigger_type", [...Object.keys(TRIGGER_TYPES), null]),
    warnings: rows.filter((row) => row.has_warning).length,
    failing: failingControls(rows),
    fetched: sum((row) => row.fetched_number_a + row.fetched_number_b),
    runtime: sum((row) => row.duration_minutes) * 60,
    longest: rows.reduce((longest, row) => (row.duration_minutes > (longest ? longest.duration_minutes : 0) ? row : longest), null),
  };
}

// The hour a run started (get-control-runs' start_date, which is the added date of a run that never started, as for
// the day it is listed on), or null.
export function runHour(run) {
  const hour = Number(String(run.start_date || "").slice(11, 13));
  return run.start_date && Number.isInteger(hour) && hour >= 0 && hour <= 23 ? hour : null;
}

// Runs per hour for HourHeatmap: one row of 24 cells with the runs, those in error and those flagged with a warning,
// and the runs per type for the tooltip.
export function runHeatmapRows(runs) {
  const types = Object.keys(CONTROL_TYPES);
  const cells = Array.from({ length: 24 }, () => ({ count: 0, errors: 0, warnings: 0, types: {} }));
  runs.forEach((run) => {
    const hour = runHour(run);
    if (hour === null) {
      return;
    }
    const cell = cells[hour];
    cell.count += 1;
    cell.types[run.control_type] = (cell.types[run.control_type] || 0) + 1;
    if (run.status === "E") cell.errors += 1;
    if (run.has_warning) cell.warnings += 1;
  });
  cells.forEach((cell) => {
    cell.breakdown = Object.keys(cell.types)
      .sort((a, b) => types.indexOf(a) - types.indexOf(b))
      .map((type) => `${type} ${cell.types[type]}`)
      .join(" · ");
  });
  return [{ key: "total", label: "Runs", cells }];
}

// Whether a run matches the header search: its name contains the text or, for digits only, its process ID starts with it.
export function runMatchesSearch(run, search) {
  if (!search) {
    return true;
  }
  const text = search.trim().toUpperCase();
  return (run.control_name || "").toUpperCase().includes(text) || (/^\d+$/.test(text) && String(run.process_id).startsWith(text));
}

function numeric(value) {
  if (value == null) return null;
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  const match = String(value).match(/-?\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : null;
}

// The value a run table sorts a column by: dates as time, error levels as numbers.
export function runSortValue(run, key) {
  const value = run[key];
  if (["start_date", "end_date", "date_from", "date_to"].includes(key)) {
    return value ? new Date(value).getTime() : null;
  }
  if (key === "error_level_a" || key === "error_level_b") {
    return numeric(value);
  }
  return value ?? null;
}

// Whether a run starts another day than the run before it, for the separator line of a list sorted by time.
export function startsNewDay(runs, index) {
  return index > 0 && toDateString(runs[index - 1].start_date) !== toDateString(runs[index].start_date);
}
