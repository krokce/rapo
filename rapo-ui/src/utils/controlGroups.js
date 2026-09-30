// rapo_config.control_group and source_type_a|b (systems): the values in use are read from the control catalogue, so
// no route lists them.

// The Controls filter's value for controls without a group (valueFilter skips null and "").
export const NO_CONTROL_GROUP = "__none__";

// The distinct values of the given fields over the catalogue, trimmed, sorted ignoring case.
function distinctValues(catalogue, fields) {
  const values = new Set();
  (catalogue || []).forEach((row) => fields.forEach((field) => values.add((row[field] || "").trim())));
  values.delete("");
  return [...values].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
}

// The groups in use.
export function controlGroups(catalogue) {
  return distinctValues(catalogue, ["control_group"]);
}

// The systems in use, of side A and B alike.
export function controlSystems(catalogue) {
  return distinctValues(catalogue, ["source_type_a", "source_type_b"]);
}

// A typed value as it is stored: trimmed, empty is null, and a case-insensitive match takes the existing spelling.
export function normalizeOption(value, options) {
  const text = (value || "").trim();
  if (!text) {
    return null;
  }
  return (options || []).find((option) => option.localeCompare(text, undefined, { sensitivity: "accent" }) === 0) || text;
}

// Options of a type-to-filter q-select: the values containing the typed text, ignoring case.
export function filterOptions(options, text) {
  const needle = (text || "").trim().toLowerCase();
  return needle ? options.filter((option) => option.toLowerCase().includes(needle)) : options;
}
