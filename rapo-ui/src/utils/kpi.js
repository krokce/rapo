import { api } from "../api";

// Parses a KPI or alarm statement (`statement.kind` is "kpi" or "alarm") on the server without executing it. The result
// is informative only: a control that never ran has no result table yet, and a type's default may name a table that
// only some controls have, so it never blocks saving.
export function checkKpiStatement(statement, text) {
  return api("validate-kpi-sql", { method: "POST", body: { statement: text, kind: statement.kind }, loadingBar: false });
}
