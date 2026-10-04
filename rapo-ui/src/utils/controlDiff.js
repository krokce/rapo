import { diffLines } from "diff";

// Not configuration: the audit columns of rapo_config_bak (never saved to rapo_config), the row stamps (set anew by
// every save), what the editor adds to a version for its selector, and the editor's own copies of the output
// columns, which are saved as output_table* (save-control drops keys that are no rapo_config column).
const IGNORED_FIELDS = [
  "output_table_columns",
  "output_table_a_columns",
  "output_table_b_columns",
  "audit_action",
  "audit_user",
  "audit_date",
  "updated_date",
  "updated_by",
  "created_date",
  "created_by",
  "label",
  "version_id",
];

// Lines kept around a change in a line diff; longer unchanged runs collapse into a gap.
const CONTEXT_LINES = 2;

// The object or array held by a JSON string (rule_config, schedule_config, output_table...), else undefined.
function parseJson(value) {
  if (typeof value !== "string" || !/^\s*[[{]/.test(value)) {
    return undefined;
  }
  try {
    const parsed = JSON.parse(value);
    return parsed !== null && typeof parsed === "object" ? parsed : undefined;
  } catch (error) {
    return undefined;
  }
}

function isEmpty(value) {
  return value === null || value === undefined || value === "";
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isMultiline(value) {
  return typeof value === "string" && value.includes("\n");
}

function same(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

// A unified line diff: [{ type: " " | "+" | "-" | "gap", text }], unchanged runs cut to CONTEXT_LINES around changes.
function lineDiff(oldText, newText) {
  const ending = (text) => (text && !text.endsWith("\n") ? text + "\n" : text || "");
  const lines = [];
  diffLines(ending(oldText), ending(newText)).forEach((part) => {
    const type = part.added ? "+" : part.removed ? "-" : " ";
    part.value.replace(/\n$/, "").split("\n").forEach((text) => lines.push({ type, text }));
  });
  const near = lines.map((line, index) =>
    lines.slice(Math.max(0, index - CONTEXT_LINES), index + CONTEXT_LINES + 1).some((other) => other.type !== " "),
  );
  const result = [];
  lines.forEach((line, index) => {
    if (near[index]) {
      result.push(line);
    } else if (!result.length || result[result.length - 1].type !== "gap") {
      result.push({ type: "gap", text: "" });
    }
  });
  return result;
}

// Adds the rows of the differences between two values under path: objects and arrays of objects by their keys and
// indexes, anything else (numbers, text, arrays of plain values) as one row.
function compare(path, oldValue, newValue, rows) {
  if (same(oldValue, newValue)) {
    return;
  }
  if (isObject(oldValue) && isObject(newValue)) {
    const keys = [...new Set([...Object.keys(oldValue), ...Object.keys(newValue)])];
    keys.forEach((key) => compare(`${path}.${key}`, oldValue[key], newValue[key], rows));
    return;
  }
  const nested = (value) => Array.isArray(value) && value.some((item) => item !== null && typeof item === "object");
  if (Array.isArray(oldValue) && Array.isArray(newValue) && (nested(oldValue) || nested(newValue))) {
    for (let index = 0; index < Math.max(oldValue.length, newValue.length); index++) {
      compare(`${path}[${index}]`, oldValue[index], newValue[index], rows);
    }
    return;
  }
  const kind = isEmpty(oldValue) ? "added" : isEmpty(newValue) ? "removed" : "changed";
  const row = { path, kind, old: oldValue, new: newValue };
  if (isMultiline(oldValue) || isMultiline(newValue)) {
    row.lines = lineDiff(typeof oldValue === "string" ? oldValue : "", typeof newValue === "string" ? newValue : "");
  }
  rows.push(row);
}

// A top-level value as compared: a JSON string decoded, and an empty side taking the shape of the other one, so that
// a rule_config filled for the first time lists its options rather than one long JSON text.
function decode(value, other) {
  const parsed = parseJson(value);
  if (parsed !== undefined) {
    return parsed;
  }
  const otherParsed = parseJson(other);
  if (isEmpty(value) && otherParsed !== undefined) {
    return Array.isArray(otherParsed) ? [] : {};
  }
  return value;
}

// The differences between the saved rapo_config row (savedJson, as ControlEdit keeps it) and the payload that
// Apply would save, one row per changed value: { path, kind: changed | added | removed, old, new, lines? }. Two
// versions compare the same way. IGNORED_FIELDS are left out.
export function diffControl(savedJson, payload) {
  const saved = savedJson ? JSON.parse(savedJson) : {};
  const rows = [];
  const keys = [...new Set([...Object.keys(saved), ...Object.keys(payload || {})])].filter((key) => !IGNORED_FIELDS.includes(key));
  keys.forEach((key) => {
    const oldValue = saved[key];
    const newValue = payload[key];
    compare(key, decode(oldValue, newValue), decode(newValue, oldValue), rows);
  });
  return rows;
}

// The differences of the KPIs (racs_kpi_config rows) by KPI type: added, removed, or their changed statements.
export function diffKpis(savedKpiJson, kpis) {
  if (savedKpiJson === null || savedKpiJson === undefined) {
    return [];
  }
  const byType = (items) => Object.fromEntries((items || []).map((item) => [item.kpi_type, item]));
  const saved = byType(JSON.parse(savedKpiJson));
  const current = byType(kpis);
  const rows = [];
  [...new Set([...Object.keys(saved), ...Object.keys(current)])].forEach((type) => {
    const path = `KPI ${type}`;
    if (!saved[type]) {
      rows.push({ path, kind: "added", old: null, new: null });
    } else if (!current[type]) {
      rows.push({ path, kind: "removed", old: null, new: null });
    } else {
      compare(path, saved[type], current[type], rows);
    }
  });
  return rows;
}

// A value with the keys of its objects sorted, so that two configurations differing only in key order are equal.
function sorted(value) {
  if (Array.isArray(value)) {
    return value.map(sorted);
  }
  if (isObject(value)) {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, sorted(value[key])]),
    );
  }
  return value;
}

// The configuration of a rapo_config(_bak) row as one string: IGNORED_FIELDS left out, JSON columns decoded, keys
// sorted. Two rows with the same key hold the same configuration.
function configKey(row) {
  const fields = Object.keys(row)
    .filter((key) => !IGNORED_FIELDS.includes(key))
    .sort()
    .map((key) => {
      const parsed = parseJson(row[key]);
      return [key, parsed !== undefined ? sorted(parsed) : isEmpty(row[key]) ? null : row[key]];
    });
  return JSON.stringify(fields);
}

// The version_ids of versions (newest first, as get-control-versions lists them) equal to the version just older than
// them: removing them keeps the oldest of each run of identical versions, and a later return to an earlier
// configuration stays, since it follows a different one.
export function consecutiveDuplicates(versions) {
  const duplicates = [];
  let previousKey = null;
  [...versions].reverse().forEach((version) => {
    const key = configKey(version);
    if (key === previousKey) {
      duplicates.push(version.version_id);
    }
    previousKey = key;
  });
  return duplicates;
}

// Payload fields that buildControlPayload derives from others: their rows cannot be reverted alone, and say what
// they follow instead.
export const DERIVED_FIELDS = {
  need_a: "rule_config.need_issues_a / need_recons_a",
  need_b: "rule_config.need_issues_b / need_recons_b",
};

// Payload fields set together by one form input: reverting one reverts the other.
const PAIRED_FIELDS = { with_deletion: "with_drop", with_drop: "with_deletion" };

// The keys and indexes of a diff row's path below its top-level field: "a.b[2].c" -> ["a", "b", 2, "c"].
function parsePath(path) {
  return [...path.matchAll(/\[(\d+)\]|([^.[\]]+)/g)].map((match) => (match[1] !== undefined ? Number(match[1]) : match[2]));
}

function clone(value) {
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
}

function valueAt(value, tokens) {
  return tokens.reduce((current, token) => (current !== null && typeof current === "object" ? current[token] : undefined), value);
}

// Sets the value at tokens inside target (an object or array), or removes it there when value is undefined: a key
// is deleted, an array item spliced out. A restored array item past the end is appended.
function setAt(target, tokens, value) {
  const parent = valueAt(target, tokens.slice(0, -1));
  const last = tokens[tokens.length - 1];
  if (parent === null || typeof parent !== "object") {
    return;
  }
  if (Array.isArray(parent)) {
    if (value === undefined) {
      parent.splice(last, 1);
    } else if (last >= parent.length) {
      parent.push(value);
    } else {
      parent[last] = value;
    }
  } else if (value === undefined) {
    delete parent[last];
  } else {
    parent[last] = value;
  }
}

// The payload with the value of one diffControl row path put back to the saved one (savedJson). A JSON column is
// decoded, changed at the path and encoded again; once it holds the saved configuration, the saved text itself is
// taken, so that the key order matches and the form is no longer dirty.
export function revertControlPath(savedJson, payload, path) {
  const saved = savedJson ? JSON.parse(savedJson) : {};
  const result = { ...payload };
  const [key, ...rest] = parsePath(path);
  const restore = (field) => {
    if (field in saved) {
      result[field] = saved[field];
    } else {
      delete result[field];
    }
  };
  if (!rest.length) {
    restore(key);
    if (PAIRED_FIELDS[key]) {
      restore(PAIRED_FIELDS[key]);
    }
    return result;
  }
  const savedValue = decode(saved[key], payload[key]);
  const current = clone(decode(payload[key], saved[key]));
  setAt(current, rest, clone(valueAt(savedValue, rest)));
  result[key] = same(sorted(current), sorted(savedValue)) ? saved[key] : JSON.stringify(current);
  return result;
}

// The KPI rows with one diffKpis row path put back to the saved rows (savedKpiJson): a whole KPI type re-added or
// removed, or one of its values. Back to the saved rows as a whole, the saved rows themselves are taken.
export function revertKpiPath(savedKpiJson, kpis, path) {
  const saved = JSON.parse(savedKpiJson);
  const current = clone(kpis || []);
  const type = [...saved, ...current].map((item) => item.kpi_type).find((code) => path === `KPI ${code}` || path.startsWith(`KPI ${code}.`));
  if (type === undefined) {
    return current;
  }
  const savedIndex = saved.findIndex((item) => item.kpi_type === type);
  const index = current.findIndex((item) => item.kpi_type === type);
  const rest = parsePath(path.slice(`KPI ${type}`.length));
  if (!rest.length || index < 0) {
    if (index >= 0) {
      current.splice(index, 1);
    } else if (savedIndex >= 0) {
      current.splice(Math.min(savedIndex, current.length), 0, clone(saved[savedIndex]));
    }
  } else {
    setAt(current[index], rest, clone(valueAt(saved[savedIndex], rest)));
  }
  return same(sorted(current), sorted(saved)) ? saved : current;
}
