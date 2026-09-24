// The answer of check-control-schema, summarized for the editor's footer and SchemaDiffDialog.

import { formatNumber, toDateString, toTimeString } from "./format";

// Column statuses of a result table compared with the schema its configuration would create.
export const SCHEMA_STATUSES = {
  ok: { label: "OK", color: "grey-5", title: "Holds every value of the datasource (it may be wider than the datasource column)" },
  added: { label: "Added", color: "positive", title: "Missing in the table, Update schema adds it" },
  widened: { label: "Widened", color: "primary", title: "Too narrow for the datasource, Update schema widens it" },
  nullable: { label: "Nullable", color: "blue-grey", title: "NOT NULL in the table only, Update schema makes it nullable" },
  not_output: { label: "Not output", color: "grey-7", title: "No longer filled by the control, kept with its history" },
  incompatible: { label: "Incompatible", color: "negative", title: "Its type cannot be converted in a table with data, only Recreate schema fixes it" },
};

// Update schema applies these; not_output only when the column is NOT NULL (then it is made nullable).
export function isSafeChange(column) {
  return Boolean(column.ddl);
}

export function summarizeSchema(check) {
  const summary = { tables: [], orphans: [], safe: 0, incompatible: 0, notOutput: 0, missing: 0, errors: [], renamed: false, level: "ok" };
  if (!check) {
    return summary;
  }
  if (check.error) {
    summary.errors.push(check.error);
  }
  // Result tables of the control that runs no longer write, e.g. side B of a reconciliation whose B output was
  // unticked: flagged for an explicit drop, never dropped by Update schema.
  summary.orphans = check.orphans || [];
  for (const table of check.tables || []) {
    const counts = { safe: 0, incompatible: 0, notOutput: 0 };
    for (const column of table.columns) {
      if (isSafeChange(column)) counts.safe++;
      if (column.status === "incompatible") counts.incompatible++;
      if (column.status === "not_output") counts.notOutput++;
    }
    if (table.error) {
      summary.errors.push(`${table.target.toUpperCase()}: ${table.error}`);
    }
    if (!table.exists) {
      summary.missing++;
    } else {
      summary.safe += counts.safe;
      summary.incompatible += counts.incompatible;
      summary.notOutput += counts.notOutput;
    }
    if (table.exists && table.table !== table.target) {
      summary.renamed = true;
    }
    summary.tables.push({ ...table, ...counts });
  }
  if (summary.errors.length) {
    summary.level = "error";
  } else if (summary.incompatible) {
    summary.level = "recreate";
  } else if (summary.orphans.length) {
    summary.level = "orphaned";
  } else if (summary.safe) {
    summary.level = "update";
  }
  return summary;
}

// The tables Recreate schema recreates: those that drifted (column changes, or the datasource of their side changed),
// e.g. only side B of a reconciliation; when none did, all the control writes, to start them anew.
export function recreateTargets(check) {
  if (!check) {
    return [];
  }
  const tables = (check.tables || []).filter((table) => !table.error);
  const changed = check.source_changed || [];
  const sourceChanged = (target) => {
    const side = { rapo_resa_: "A", rapo_resb_: "B" }[target.slice(0, 10)];
    return side ? changed.includes(side) : changed.length > 0;
  };
  const drifted = tables.filter((table) => (table.exists && table.columns.some((column) => column.ddl || column.status === "incompatible")) || sourceChanged(table.target));
  return (drifted.length ? drifted : tables).map((table) => table.target);
}

// The rows of a result table: exact once counted on request (count-control-table-rows), otherwise the optimizer
// statistics estimate, since a count(*) scans the whole table.
export function rowsText(table, exact) {
  if (exact) {
    return `${formatNumber(exact.rows || 0)} rows (counted at ${toTimeString(exact.counted)})`;
  }
  if (table.rows === null || table.rows === undefined) {
    return "row count unknown (no statistics)";
  }
  return `≈ ${formatNumber(table.rows)} rows (statistics of ${toDateString(table.rows_analyzed)})`;
}

// The line of an orphaned table in a confirmation: what dropping it deletes.
export function describeOrphan(orphan, exact) {
  const oldest = orphan.oldest ? `, results since ${toDateString(orphan.oldest)}` : "";
  return `${orphan.table.toUpperCase()}: ${rowsText(orphan, exact)}${oldest} will be dropped`;
}

// The line of a table in a confirmation: what Update schema changes, or what Recreate schema deletes.
export function describeTable(table, action, exact) {
  if (!table.exists) {
    return `${table.target.toUpperCase()}: does not exist yet`;
  }
  if (action === "recreate") {
    const oldest = table.oldest ? `, results since ${toDateString(table.oldest)}` : "";
    return `${table.table.toUpperCase()}: ${rowsText(table, exact)}${oldest} will be deleted`;
  }
  const parts = [];
  const count = (status) => table.columns.filter((column) => column.status === status && column.ddl).length;
  if (count("added")) parts.push(`${count("added")} added`);
  if (count("widened")) parts.push(`${count("widened")} widened`);
  const nullable = count("nullable") + count("not_output");
  if (nullable) parts.push(`${nullable} made nullable`);
  if (table.incompatible) parts.push(`${table.incompatible} incompatible left (needs Recreate schema)`);
  return `${table.table.toUpperCase()}: ${parts.length ? parts.join(", ") : "no change"}`;
}
