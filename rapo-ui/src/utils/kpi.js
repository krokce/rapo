import { api } from "../api";

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
