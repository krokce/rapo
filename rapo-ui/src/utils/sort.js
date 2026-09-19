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
