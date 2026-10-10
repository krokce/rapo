// Filters a link from another page (the Dashboard) puts into the query, e.g. /results?status=E&name=REC_X. The page
// takes them over in place of its own filters, then drops them from the URL, so its filters (persistFilters) stay the
// only state and Back or a reload does not apply them again.

// The keys of `keys` present in the route's query, as {key: value}; null when none is.
export function takeRouteFilters(route, keys) {
  const present = keys.filter((key) => route.query[key] !== undefined && route.query[key] !== null);
  if (!present.length) {
    return null;
  }
  return Object.fromEntries(present.map((key) => [key, String(route.query[key])]));
}

// The route without those keys, other query values and the hash kept.
export function dropRouteFilters(router, route, keys) {
  const query = { ...route.query };
  keys.forEach((key) => delete query[key]);
  return router.replace({ query, hash: route.hash });
}

// A comma list of a query value, e.g. "E,C".
export function listParam(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}
