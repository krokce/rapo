// Entries of a list page's activeFilters, shown by FilterBadge and FilterChips: {key, label, clear}, one per value.
// A sort hides no row, so it is not a filter.

// A single value (text, select), when set; `text` quotes a typed text.
export function valueFilter(key, name, value, clear, { text = false, label = null } = {}) {
  if (value === null || value === undefined || value === "") {
    return [];
  }
  const shown = label === null ? value : label;
  return [{ key, label: `${name}: ${text ? `"${shown}"` : shown}`, clear }];
}

// One entry per selected value of a multi-select, each removing only its value.
export function listFilter(key, name, values, remove, labelOf = (value) => value) {
  return (values || []).map((value) => ({ key: `${key}:${value}`, label: `${name}: ${labelOf(value)}`, clear: () => remove(value) }));
}

// The header's search box, shared by the pages that show it (Vuex `search`).
export function searchFilter(store) {
  const search = store.getters.getSearch;
  return valueFilter("search", "Search", search, () => store.commit("updateSearch", ""), { text: true });
}
