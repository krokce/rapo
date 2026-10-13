// Runs as get-control-runs answers them, shared by the Results page and the editor's Run log (RunTable, RunSummary).
import { CONTROL_TYPES, RUN_STATUSES, TRIGGER_TYPES } from "../constants";
import { toDateString, toDateTimeString } from "./format";

// What started the run (rapo_scheduler_event), a question mark when the run manager did not start it.
export function triggerOf(run) {
  return TRIGGER_TYPES[run.trigger_type] || { label: run.trigger_type || "Trigger not recorded", icon: "fas fa-question", color: "grey-5" };
}

// The trigger a run is filtered by: its trigger_type, or NO_TRIGGER when none was recorded (null means no filter).
export const NO_TRIGGER = "NONE";

export function triggerKey(run) {
  return run.trigger_type || NO_TRIGGER;
}

// The trigger of a filter key, as triggerOf gives it.
export function triggerOfKey(key) {
  return triggerOf({ trigger_type: key === NO_TRIGGER ? null : key });
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

// The sort key of a KPI column of the Run log, and the KPI type of one.
export const KPI_SORT_PREFIX = "kpi:";

// The value a run table sorts a column by: dates as time, error levels as numbers, a KPI column by its value.
export function runSortValue(run, key) {
  if (key.startsWith(KPI_SORT_PREFIX)) {
    const kpi = run.kpis && run.kpis[key.slice(KPI_SORT_PREFIX.length)];
    return kpi ? numeric(kpi.value) : null;
  }
  const value = run[key];
  if (["start_date", "end_date", "date_from", "date_to"].includes(key)) {
    return value ? new Date(value).getTime() : null;
  }
  if (key === "error_level_a" || key === "error_level_b") {
    return numeric(value);
  }
  return value ?? null;
}

// Whether a run is on another day (of `key`: its start, or the start of its data window) than the run before it, for
// the separator line of a list sorted by time.
export function startsNewDay(runs, index, key = "start_date") {
  return index > 0 && toDateString(runs[index - 1][key]) !== toDateString(runs[index][key]);
}

// The runs of a table with the superseded ones (a later run of their period, any status: `superseded_by`, see
// reader.superseded_sql) folded under that run when it is among them, newest first, right under it whatever the sort;
// a superseded run whose newer run is not listed (another day, filtered out) stays in place. `expanded(processId)`
// says whether a run's earlier runs are shown. Answers {rows, earlier: Map(processId -> count), folded: Set(processId),
// versions: Map(processId -> its number among the runs of its period, the oldest 1) of the folded runs}.
export function groupRuns(runs, expanded) {
  const listed = new Set(runs.map((run) => run.process_id));
  const children = new Map();
  const top = [];
  for (const run of runs) {
    if (run.superseded_by && listed.has(run.superseded_by)) {
      if (!children.has(run.superseded_by)) children.set(run.superseded_by, []);
      children.get(run.superseded_by).push(run);
    } else {
      top.push(run);
    }
  }
  const rows = [];
  const earlier = new Map();
  const folded = new Set();
  const versions = new Map();
  for (const run of top) {
    rows.push(run);
    const kids = children.get(run.process_id);
    if (!kids) continue;
    const newest = [...kids].sort((a, b) => b.process_id - a.process_id);
    earlier.set(run.process_id, kids.length);
    newest.forEach((kid, index) => {
      folded.add(kid.process_id);
      versions.set(kid.process_id, kids.length - index);
    });
    if (expanded(run.process_id)) {
      rows.push(...newest);
    }
  }
  return { rows, earlier, folded, versions };
}

// The tooltip of a superseded run's mark.
export function supersededTitle(run) {
  return `Superseded by run ${run.superseded_by}${run.superseded_on ? ` of ${toDateString(run.superseded_on)}` : ""}: a later run of the same period`;
}

// RunTable's column headers by sort key, for the sort chip of the Results page.
export const RUN_SORT_LABELS = {
  control_type: "Type",
  start_date: "Start",
  duration_minutes: "Runtime",
  process_id: "PID",
  control_name: "Processname",
  date_from: "Run from",
  date_to: "Run to",
  fetched_number_a: "Fetched A",
  fetched_number_b: "Fetched B",
  error_number_a: "Discr. A",
  error_number_b: "Discr. B",
  error_level_a: "Err. lvl A [%]",
  error_level_b: "Err. lvl B [%]",
  prerequisite_value: "PV",
  status: "Status",
};
