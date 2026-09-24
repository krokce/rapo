<template>
  <div class="column no-wrap group-panel">
    <div class="row items-start q-gutter-sm q-mb-sm settings">
      <q-select
        v-model="groupColumns"
        class="col-12 col-md-4"
        dense
        outlined
        multiple
        use-chips
        emit-value
        map-options
        options-dense
        label="Group by"
        use-input
        input-debounce="0"
        :options="shownColumnOptions"
        @filter="filterColumns" />
      <q-select
        v-for="item in dateKeys"
        :key="item.column"
        :model-value="item.bucket || null"
        class="bucket-select"
        dense
        outlined
        emit-value
        map-options
        options-dense
        :label="`${item.column.toUpperCase()} by`"
        :options="bucketOptions"
        @update:model-value="setBucket(item.column, $event)" />
      <q-select
        v-model="aggregateKeys"
        class="col"
        dense
        outlined
        multiple
        use-chips
        emit-value
        map-options
        options-dense
        label="Aggregates"
        use-input
        input-debounce="0"
        :options="shownAggregateOptions"
        @filter="filterAggregates" />
    </div>

    <div class="row items-center q-mb-sm text-blue-grey-8">
      <template v-if="result">
        <strong>{{ formatNumber(result.total_groups) }}</strong>&nbsp;{{ result.total_groups === 1 ? "group" : "groups" }}&nbsp;of&nbsp;
        <strong>{{ formatNumber(result.total_rows) }}</strong>&nbsp;rows
        <span v-if="result.rows.length < result.total_groups" class="text-grey-7">&nbsp;· the first {{ formatNumber(result.rows.length) }} shown</span>
        <span class="text-grey-7">&nbsp;· click a group to see its rows</span>
      </template>
      <span v-else-if="!group.by.length" class="text-grey-7">Choose the columns to group the rows by.</span>
      <q-space />
      <q-spinner v-if="loading" color="primary" size="18px" />
    </div>

    <div class="col groups-scroll">
      <table v-if="result && result.rows.length" class="groups-table">
        <thead>
          <tr>
            <th v-for="(name, index) in result.by" :key="'k' + index" class="text-left sortable" @click="toggleSort(name)">
              {{ name.toUpperCase() }}<span v-if="bucketOf(name)" class="text-grey-7"> ({{ bucketOf(name) }})</span>
              <q-icon v-if="sortIcon(name)" :name="sortIcon(name)" size="12px" />
            </th>
            <th class="text-right sortable count-col" @click="toggleSort('count')">
              Count <q-icon v-if="sortIcon('count')" :name="sortIcon('count')" size="12px" />
            </th>
            <th class="share-col">Share</th>
            <th v-for="label in result.aggregates" :key="label" class="text-right sortable" @click="toggleSort(label)">
              {{ aggregateLabel(label) }} <q-icon v-if="sortIcon(label)" :name="sortIcon(label)" size="12px" />
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in result.rows" :key="index" class="cursor-pointer" @click="drill(row)">
            <td v-for="(key, position) in row.keys" :key="position" :class="{ 'text-grey-5 text-italic': key === null }">
              {{ key === null ? "(missing)" : formatKey(key, position) }}
            </td>
            <td class="text-right text-weight-medium">{{ formatNumber(row.count) }}</td>
            <td>
              <div class="row no-wrap items-center">
                <div class="share-bar" :style="{ width: Math.max((row.count * 100) / maxCount, 0.5) + '%' }" />
                <span class="text-caption text-grey-7 q-ml-xs">{{ formatPct((row.count * 100) / result.total_rows) }}</span>
              </div>
            </td>
            <td v-for="(value, position) in row.values" :key="'v' + position" class="text-right">{{ formatStat(value) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="result" class="text-grey-7 q-pa-md">No rows match the filters.</div>
    </div>
  </div>
</template>

<script>
import { api, notifyError } from "../../api";
import { formatNumber, toDateTimeString } from "../../utils/format";
import { formatPct, formatStat, valueFilter } from "../../utils/analysis";

const BUCKETS = [
  { label: "Exact value", value: null },
  { label: "Hour", value: "hour" },
  { label: "Day", value: "day" },
  { label: "Month", value: "month" },
  { label: "Year", value: "year" },
];
function matches(label, needle) {
  const text = label.toLowerCase();
  return (needle || "")
    .toLowerCase()
    .split(/\s+/)
    .every((word) => text.includes(word));
}

const FUNCTIONS = { sum: "Sum", mean: "Mean", min: "Min", max: "Max", nunique: "Distinct" };

// Group-by of the viewed rows (the viewer's filters and search apply), computed by the analysis worker. `group` is
// the page's {by: [{column, bucket}], aggregates: [{column, fn}], sort}, edited in place and kept in the URL.
export default {
  name: "GroupByPanel",
  props: {
    sessionId: { type: String, required: true },
    columns: { type: Array, required: true },
    version: { type: Number, default: 0 },
    view: { type: Object, required: true },
    group: { type: Object, required: true },
  },
  emits: ["drill"],
  data() {
    return { result: null, loading: false, token: 0, bucketOptions: BUCKETS, columnNeedle: "", aggregateNeedle: "" };
  },
  computed: {
    state() {
      return this.group;
    },
    kinds() {
      const kinds = {};
      this.columns.forEach((column) => (kinds[column.name] = column.kind));
      return kinds;
    },
    columnOptions() {
      return this.columns.map((column) => ({ label: column.name.toUpperCase(), value: column.name }));
    },
    groupColumns: {
      get() {
        return this.group.by.map((item) => item.column);
      },
      set(names) {
        const current = {};
        this.group.by.forEach((item) => (current[item.column] = item));
        this.state.by = names.map((name) => current[name] || { column: name, bucket: this.kinds[name] === "datetime" ? "day" : null });
      },
    },
    // The options matching what is typed in the select, every word anywhere in the label.
    shownColumnOptions() {
      return this.columnOptions.filter((option) => matches(option.label, this.columnNeedle));
    },
    shownAggregateOptions() {
      return this.aggregateOptions.filter((option) => matches(option.label, this.aggregateNeedle));
    },
    dateKeys() {
      return this.group.by.filter((item) => this.kinds[item.column] === "datetime");
    },
    aggregateOptions() {
      const options = [];
      this.columns.forEach((column) => {
        const functions = column.kind === "numeric" ? ["sum", "mean", "min", "max", "nunique"] : column.kind === "datetime" ? ["min", "max", "nunique"] : ["nunique"];
        functions.forEach((fn) => options.push({ label: `${FUNCTIONS[fn]} of ${column.name.toUpperCase()}`, value: `${fn}:${column.name}` }));
      });
      return options;
    },
    aggregateKeys: {
      get() {
        return this.group.aggregates.map((item) => `${item.fn}:${item.column}`);
      },
      set(keys) {
        this.state.aggregates = keys.map((key) => {
          const [fn, ...rest] = key.split(":");
          return { fn, column: rest.join(":") };
        });
      },
    },
    maxCount() {
      return Math.max(1, ...this.result.rows.map((row) => row.count));
    },
    requestKey() {
      return JSON.stringify([this.sessionId, this.version, this.view.filters, this.view.search, this.group]);
    },
  },
  watch: {
    requestKey: {
      immediate: true,
      handler() {
        clearTimeout(this.timer);
        this.timer = setTimeout(() => this.load(), 250);
      },
    },
  },
  beforeUnmount() {
    this.token += 1;
    clearTimeout(this.timer);
  },
  methods: {
    formatNumber,
    formatPct,
    formatStat,
    filterColumns(text, update) {
      update(() => (this.columnNeedle = text));
    },
    filterAggregates(text, update) {
      update(() => (this.aggregateNeedle = text));
    },
    async load() {
      if (!this.group.by.length || !this.version) {
        this.result = null;
        return;
      }
      const token = ++this.token;
      this.loading = true;
      try {
        const result = await api("analysis-groups", {
          params: {
            session_id: this.sessionId,
            by: JSON.stringify(this.group.by),
            aggregates: this.group.aggregates.length ? JSON.stringify(this.group.aggregates) : null,
            filters: this.view.filters.length ? JSON.stringify(this.view.filters) : null,
            search: this.view.search || null,
            sort: this.group.sort ? JSON.stringify(this.group.sort) : null,
            limit: 1000,
          },
          loadingBar: false,
        });
        if (token === this.token) {
          this.result = Object.freeze(result);
        }
      } catch (error) {
        if (token === this.token && error.status !== 404) {
          notifyError("The groups could not be computed.", error);
        }
      } finally {
        if (token === this.token) {
          this.loading = false;
        }
      }
    },
    setBucket(column, bucket) {
      this.state.by = this.group.by.map((item) => (item.column === column ? { ...item, bucket } : item));
    },
    bucketOf(name) {
      const item = this.group.by.find((entry) => entry.column === name);
      return item && item.bucket ? item.bucket : null;
    },
    formatKey(value, position) {
      const name = this.result.by[position];
      if (this.kinds[name] !== "datetime") {
        return String(value);
      }
      const bucket = this.bucketOf(name);
      const text = toDateTimeString(value);
      return { hour: text.substring(0, 13) + ":00", day: text.substring(0, 10), month: text.substring(0, 7), year: text.substring(0, 4) }[bucket] || text;
    },
    aggregateLabel(label) {
      const match = label.match(/^(\w+)\((.*)\)$/);
      return match ? `${FUNCTIONS[match[1]] || match[1]} ${match[2].toUpperCase()}` : label;
    },
    sortIcon(column) {
      const sort = this.group.sort || { column: "count", desc: true };
      if (sort.column !== column) {
        return null;
      }
      return sort.desc ? "fas fa-sort-down" : "fas fa-sort-up";
    },
    toggleSort(column) {
      const sort = this.group.sort || { column: "count", desc: true };
      this.state.sort = sort.column === column ? { column, desc: !sort.desc } : { column, desc: column === "count" || column.includes("(") };
    },
    // The rows of a group: one filter per key, a date bucket as its range.
    drill(row) {
      const filters = row.keys.map((key, position) => {
        const column = this.result.by[position];
        const end = row.ends[position];
        if (end && key !== null) {
          return { column, kind: "datetime", op: "range", value: { min: key, max: end, max_inclusive: false } };
        }
        return valueFilter(column, key);
      });
      this.$emit("drill", filters);
    },
  },
};
</script>

<style scoped>
.group-panel {
  height: 100%;
  min-height: 0;
}

.settings {
  flex: 0 0 auto;
}

.bucket-select {
  min-width: 170px;
}

.groups-scroll {
  min-height: 0;
  overflow: auto;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background: white;
}

.groups-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.groups-table th {
  position: sticky;
  top: 0;
  background: #cfd8dc;
  padding: 6px 8px;
  font-weight: 600;
  white-space: nowrap;
  z-index: 1;
}

.groups-table td {
  padding: 5px 8px;
  border-bottom: 1px solid #eceff1;
  white-space: nowrap;
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.groups-table tbody tr:hover {
  background: #e0f2f1;
}

.sortable {
  cursor: pointer;
  user-select: none;
}

.count-col {
  width: 90px;
}

.share-col {
  width: 200px;
}

.share-bar {
  height: 10px;
  max-width: 120px;
  background: #90a4ae;
  border-radius: 2px;
}
</style>
