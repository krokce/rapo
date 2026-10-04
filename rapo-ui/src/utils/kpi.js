import { api } from "../api";
import { toDateString } from "./format";

// Parses a KPI or alarm statement (`statement.kind` is "kpi" or "alarm") on the server without executing it. The result
// is informative only: a control that never ran has no result table yet, and a type's default may name a table that
// only some controls have, so it never blocks saving.
export function checkKpiStatement(statement, text) {
  return api("validate-kpi-sql", { method: "POST", body: { statement: text, kind: statement.kind }, loadingBar: false });
}

// The alarm levels RACS_KPI_PKG stores and the dashboard shows: 3 red, 2 orange, 1 blue; 0 or none is no alarm.
const ALARM_LEVELS = {
  3: { color: "red-7", icon: "fas fa-bell", label: "Alarm 3" },
  2: { color: "orange-8", icon: "fas fa-bell", label: "Alarm 2" },
  1: { color: "blue-7", icon: "fas fa-bell", label: "Alarm 1" },
};
const NO_ALARM = { color: "blue-grey-3", icon: "fas fa-bell-slash", label: "No alarm" };

export function alarmLevel(level) {
  return ALARM_LEVELS[Number(level)] || NO_ALARM;
}

// A KPI value as the dashboard shows it: the type's decimal places, else the 4 the package rounds to.
export function formatKpiValue(value, decimals) {
  if (value === null || value === undefined) return "NULL";
  const places = decimals === null || decimals === undefined ? 4 : Number(decimals);
  return Number(value).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: places });
}

// Whether a calculated value equals the stored one, both rounded to 4 places by the package.
export function sameKpiValue(calculated, stored) {
  if (calculated === null || calculated === undefined || stored === null || stored === undefined) return calculated == stored;
  return Math.abs(Number(calculated) - Number(stored)) < 1e-9;
}

// Calculates one KPI of one run on the server without storing it. kpi is a racs_kpi_config row as edited, or null to
// use the saved one.
export function calculateKpi(processId, kpiType, kpi) {
  const body = { process_id: processId, kpi_type: kpiType, saved: !kpi };
  if (kpi) {
    body.kpi_sql_statement = kpi.kpi_sql_statement;
    body.alarm_sql_statement = kpi.alarm_sql_statement;
  }
  return api("calculate-kpi", { method: "POST", body, loadingBar: false });
}

// The notes under a calculated KPI: why the package would store 0, a NULL value, a missing alarm statement.
export function kpiNotes(result) {
  const notes = [];
  if (!result.kpi_source) notes.push("No KPI statement, own or default: the package stores 0.");
  if (result.no_rows) notes.push("The KPI statement returned no row: the package stores 0.");
  if (result.value === null) notes.push("The KPI statement returned NULL.");
  if (!result.alarm_source) notes.push("No alarm statement, own or default: the alarm level is 0.");
  return notes;
}

// How long the statements of a calculated KPI took, e.g. "KPI 12 ms · alarm 3 ms".
export function kpiTiming(result) {
  return [result.kpi_ms !== null ? `KPI ${result.kpi_ms} ms` : null, result.alarm_ms !== null ? `alarm ${result.alarm_ms} ms` : null]
    .filter(Boolean)
    .join(" · ");
}

// The date or period a run (a get-kpi-runs row) covered.
export function runWindow(run) {
  const from = toDateString(run.date_from);
  const to = toDateString(run.date_to);
  return to && to !== from ? `${from} – ${to}` : from;
}

// The run KPIs are calculated for by default: the newest one that ended D, else the newest one. runs are newest first.
export function defaultRunId(runs) {
  const run = runs.find((row) => row.status === "D") || runs[0];
  return run ? run.process_id : null;
}

// Points the result table names of a control in a statement to its new name: whole RAPO_REST_/RAPO_RESA_/RAPO_RESB_
// <oldName> names in any case, quoted or owner-qualified, never a longer name that starts with it. The prefix keeps
// its case, and the new name is written lower case where the old one was, unless quoted. Mirrors
// rename_table_references in rapo/kpi.py, which the server applies to a rename saved without KPIs: keep both in step.
export function renameTableReferences(text, oldName, newName) {
  if (!text || !oldName || !newName) return { text, count: 0 };
  const escaped = oldName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(`(?<![\\w$#])("?)(RAPO_RES[TAB]_)(${escaped})\\1(?![\\w$#])`, "gi");
  let count = 0;
  const result = text.replace(pattern, (match, quote, prefix, name) => {
    count++;
    return `${quote}${prefix}${!quote && name === name.toLowerCase() ? newName.toLowerCase() : newName}${quote}`;
  });
  return { text: result, count };
}

// Renames the table references in the statements of KPI rows, in place. Answers [{ kpi_type, field }] per statement
// changed.
export function renameKpiTables(kpis, oldName, newName) {
  const changes = [];
  for (const kpi of kpis) {
    for (const field of ["kpi_sql_statement", "alarm_sql_statement"]) {
      const { text, count } = renameTableReferences(kpi[field], oldName, newName);
      if (count) {
        kpi[field] = text;
        changes.push({ kpi_type: kpi.kpi_type, field });
      }
    }
  }
  return changes;
}
