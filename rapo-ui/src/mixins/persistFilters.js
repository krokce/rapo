// Keeps a list page's filters (and its sort) for the browser session: restored when the page is created, and
// saved on every change to sessionStorage, which lasts until the tab is closed and survives a reload.
// `fields` are data properties: an object is updated key by key (keys it no longer has are ignored, so a
// stored value of an older shape cannot break the page), anything else is replaced.
function sameKind(current, saved) {
  if (Array.isArray(current)) {
    return Array.isArray(saved);
  }
  return saved === null || current === null || current === undefined || typeof saved === typeof current;
}

export default function persistFilters(key, fields) {
  const storageKey = `rapo_filters_${key}`;
  return {
    created() {
      let saved = null;
      try {
        saved = JSON.parse(sessionStorage.getItem(storageKey) || "null");
      } catch (error) {
        saved = null;
      }
      if (saved && typeof saved === "object") {
        fields.forEach((field) => {
          if (!(field in saved)) {
            return;
          }
          const current = this[field];
          const value = saved[field];
          if (current && typeof current === "object" && !Array.isArray(current)) {
            if (value && typeof value === "object") {
              Object.keys(current).forEach((name) => {
                if (name in value && sameKind(current[name], value[name])) {
                  current[name] = value[name];
                }
              });
            }
          } else if (sameKind(current, value)) {
            this[field] = value;
          }
        });
      }
      this.$watch(
        () => fields.map((field) => this[field]),
        () => {
          try {
            sessionStorage.setItem(storageKey, JSON.stringify(Object.fromEntries(fields.map((field) => [field, this[field]]))));
          } catch (error) {
            // Not remembered, which is all a failure costs.
          }
        },
        { deep: true }
      );
    },
  };
}
