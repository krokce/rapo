// PDI Core datasources (pdi_core_ds_config and its pdi_core_ds_tables rows), shared by the Datasources list and editor.

// A new datasource: the column defaults of pdi_core_ds_config.
export function emptyDatasource() {
  return {
    id: null,
    sourcename: "",
    input_directory: "",
    archive_directory: "",
    error_directory: "",
    duplicate_directory: "",
    isactive: 0,
    files_mask: ".*",
    files_retention_days: 14,
    files_max_per_cycle: 1000,
    files_dup_handling: "PREVENT",
    leave_input_zipped: 0,
    files_load_parallel: 1,
    max_recordsreject: 0,
    input_scan_subdirs: 0,
    input_clean_files_mask: null,
    links: [],
  };
}

export function emptyLink() {
  return { table_name: "", partition_key: null, partition_days_to_retain: null, partition_days_in_advance: null };
}

// The columns of a datasource as saved (save-ds-config), in DDL order.
export const DATASOURCE_FIELDS = Object.keys(emptyDatasource()).filter((key) => key !== "links");

// PDI Core separates the paths of INPUT_DIRECTORY by "|".
export function splitDirectories(value) {
  return String(value || "")
    .split("|")
    .map((part) => part.trim())
    .filter(Boolean);
}

// The payload of save-ds-config, and what the editor compares to know it is dirty.
export function datasourcePayload(datasource) {
  const payload = {};
  DATASOURCE_FIELDS.forEach((key) => {
    const value = datasource[key];
    payload[key] = value === "" && key === "input_clean_files_mask" ? null : value;
  });
  payload.links = (datasource.links || []).map((link) => ({
    table_name: link.table_name ? String(link.table_name).trim().toUpperCase() : "",
    partition_key: link.partition_key || null,
    partition_days_to_retain: link.partition_days_to_retain === "" ? null : link.partition_days_to_retain ?? null,
    partition_days_in_advance: link.partition_days_in_advance === "" ? null : link.partition_days_in_advance ?? null,
  }));
  return payload;
}

// A datasource as utils/controlDiff.js compares it: the tables keyed by name, so a removed one is not a shift of all.
export function diffShape(datasource) {
  if (!datasource) {
    return {};
  }
  const shape = datasourcePayload(datasource);
  shape.links = Object.fromEntries(shape.links.map(({ table_name, ...rest }) => [table_name, rest]));
  return shape;
}

// What the list flags beside a datasource's name: {key, label, color, icon, title}. status is the datasource's entry
// of get-ds-status, undefined until the first scan. Red is what keeps files from loading, orange what is incomplete.
export const ISSUES = [
  { key: "no_tables", label: "No tables", color: "orange-8", icon: "fas fa-table" },
  { key: "no_retention", label: "No retention", color: "orange-8", icon: "fas fa-history" },
  { key: "dir_missing", label: "Input dir missing", color: "red-5", icon: "fas fa-folder-minus" },
  { key: "dir_unreadable", label: "Input dir unreadable", color: "red-5", icon: "fas fa-lock" },
  { key: "other_missing", label: "Archive dir missing", color: "orange-8", icon: "fas fa-folder-minus" },
  { key: "invalid_mask", label: "Invalid pattern", color: "red-5", icon: "fas fa-exclamation-triangle" },
  { key: "stalled", label: "Stalled", color: "red-5", icon: "fas fa-hourglass-end" },
  { key: "errors", label: "Errors 24h", color: "red-5", icon: "fas fa-exclamation-circle" },
];

export function issuesOf(row, status, stalledMinutes = 60) {
  const issues = [];
  const add = (key, title) => issues.push({ ...ISSUES.find((issue) => issue.key === key), title });
  if (!row.table_count) {
    add("no_tables", "No table is linked on the Retention tab, so a RECYCLE or DELETE cleans only the table named like the datasource");
  } else if (!row.retention_count) {
    add("no_retention", `None of its ${row.table_count} table(s) has a partition key, so no partition is created or dropped`);
  }
  if (!status) {
    return issues;
  }
  if (status.missing && status.missing.length) {
    add("dir_missing", `Missing on this server: ${status.missing.join(", ")}`);
  }
  if (status.unreadable && status.unreadable.length) {
    add("dir_unreadable", `Not readable by rapo: ${status.unreadable.join(", ")}`);
  }
  if (status.missing_other && status.missing_other.length) {
    add("other_missing", `Missing on this server: ${status.missing_other.map((name) => name.toUpperCase()).join(", ")}`);
  }
  if (status.mask_error || status.clean_mask_error) {
    add("invalid_mask", [status.mask_error && `File name pattern: ${status.mask_error}`, status.clean_mask_error && `Clean-up file pattern: ${status.clean_mask_error}`].filter(Boolean).join("; "));
  }
  if (status.stalled) {
    add("stalled", `Active, and its oldest incoming file has waited longer than ${stalledMinutes} minutes`);
  }
  if (status.log && status.log.errors) {
    add("errors", `${status.log.errors} file(s) ended in ERROR in the last 24 hours`);
  }
  return issues;
}

export function formatBytes(bytes) {
  if (bytes === null || bytes === undefined) {
    return "";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = Number(bytes);
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${unit ? value.toFixed(value < 10 ? 1 : 0) : value} ${units[unit]}`;
}

// "45 s", "12 min", "3 h", "2 d".
export function formatAge(seconds) {
  if (seconds === null || seconds === undefined) {
    return "";
  }
  const value = Math.max(Number(seconds), 0);
  if (value < 60) return `${Math.round(value)} s`;
  if (value < 3600) return `${Math.floor(value / 60)} min`;
  if (value < 86400) return `${Math.floor(value / 3600)} h ${Math.floor((value % 3600) / 60)} min`;
  return `${Math.floor(value / 86400)} d ${Math.floor((value % 86400) / 3600)} h`;
}

// Seconds between two naive ISO datetimes of the same clock.
export function secondsBetween(earlier, later) {
  if (!earlier || !later) {
    return null;
  }
  return (new Date(later) - new Date(earlier)) / 1000;
}

// A row of a file list as CSV, the separator and quotes escaped.
export function toCsv(rows, columns) {
  const escape = (value) => {
    const text = value === null || value === undefined ? "" : String(value);
    return /[",;\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  return [columns.map((column) => escape(column.label)).join(";"), ...rows.map((row) => columns.map((column) => escape(column.value(row))).join(";"))].join("\n");
}

export function downloadText(text, filename, type = "text/csv") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
