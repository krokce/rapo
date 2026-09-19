// Type-to-filter column pickers for components with datasourceAColumns/datasourceBColumns props:
// bind :options="datasourceAList" and @filter="filterFieldListA" (and B) on a q-select with use-input.
function filterColumns(columns, needle) {
  return (columns || []).filter((column) => column.toLowerCase().includes(needle.toLowerCase()));
}

export default {
  data() {
    return {
      datasourceAList: null,
      datasourceBList: null,
    };
  },
  methods: {
    filterFieldListA(val, update) {
      update(() => {
        this.datasourceAList = filterColumns(this.datasourceAColumns, val);
      });
    },
    filterFieldListB(val, update) {
      update(() => {
        this.datasourceBList = filterColumns(this.datasourceBColumns, val);
      });
    },
    // Default for a new row: the first column of the side, or null while columns are not loaded yet.
    firstColumn(columns) {
      return (columns || [])[0] ?? null;
    },
  },
};
