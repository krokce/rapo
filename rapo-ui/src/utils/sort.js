// Table sorting shared by the Controls and Results pages. `sort` is { key, dir: "asc" | "desc" }.

// Sort rows by valueOf(row), computed once per row: numbers numerically, anything else as text.
// Missing values (null/undefined) always go last.
export function sortRows(rows, valueOf, dir) {
  const sign = dir === "desc" ? -1 : 1;
  return rows
    .map((row) => [valueOf(row), row])
    .sort(([a], [b]) => {
      if (a === b) return 0;
      if (a == null) return 1;
      if (b == null) return -1;
      if (typeof a === "number" && typeof b === "number") return (a - b) * sign;
      return String(a).localeCompare(String(b)) * sign;
    })
    .map(([, row]) => row);
}

// Clicking the current column flips the direction, another column sorts it ascending.
export function toggleSort(sort, key) {
  if (sort.key === key) {
    sort.dir = sort.dir === "asc" ? "desc" : "asc";
  } else {
    sort.key = key;
    sort.dir = "asc";
  }
}

export function sortIcon(sort) {
  return sort.dir === "asc" ? "fas fa-sort-up" : "fas fa-sort-down";
}

// The aria-sort value of a column header for a `sort` of { key, dir }.
export function ariaSort(sort, key) {
  return sort.key === key ? (sort.dir === "asc" ? "ascending" : "descending") : "none";
}

// The sort chip of a list's FilterChips: null while `sort` is the page's `defaultSort` (or names a column not in
// `labels`, which the page ignores), else { label, icon, title, clear }. `clear()` puts the default back in place.
export function sortChip(sort, defaultSort, labels, defaultText) {
  if (sort.key === defaultSort.key && (sort.key == null || sort.dir === defaultSort.dir)) {
    return null;
  }
  const label = labels[sort.key];
  if (!label) {
    return null;
  }
  return {
    label,
    icon: sortIcon(sort),
    title: `Sorted by ${label}, ${sort.dir === "asc" ? "ascending" : "descending"}; remove to restore the default order (${defaultText})`,
    clear() {
      sort.key = defaultSort.key;
      sort.dir = defaultSort.dir;
    },
  };
}
