// rapo_config.control_group: the groups in use are read from the control catalogue, so no route lists them.

// The Controls filter's value for controls without a group (valueFilter skips null and "").
export const NO_CONTROL_GROUP = "__none__";

// The distinct groups of the catalogue, trimmed, sorted ignoring case.
export function controlGroups(catalogue) {
  const groups = new Set((catalogue || []).map((row) => (row.control_group || "").trim()).filter(Boolean));
  return [...groups].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
}

// A typed group as it is stored: trimmed, empty is null, and a case-insensitive match takes the existing spelling.
export function normalizeControlGroup(value, groups) {
  const text = (value || "").trim();
  if (!text) {
    return null;
  }
  return (groups || []).find((group) => group.localeCompare(text, undefined, { sensitivity: "accent" }) === 0) || text;
}

// Options of a type-to-filter q-select: the groups containing the typed text, ignoring case.
export function filterControlGroups(groups, text) {
  const needle = (text || "").trim().toLowerCase();
  return needle ? groups.filter((group) => group.toLowerCase().includes(needle)) : groups;
}
