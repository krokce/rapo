<template>
  <div class="column no-wrap viewer">
    <div class="row items-center q-gutter-sm q-mb-sm toolbar">
      <q-input v-model="searchText" dense outlined clearable class="search-input" placeholder="Search all columns" debounce="400">
        <template #prepend><q-icon name="fas fa-search" size="14px" /></template>
      </q-input>
      <q-btn outline dense color="blue-grey-7" icon="fas fa-columns" no-caps :label="columnsLabel" class="q-px-sm">
        <q-menu anchor="bottom left" self="top left" class="columns-menu">
          <q-list dense style="min-width: 260px">
            <q-item>
              <q-item-section>
                <div class="row q-gutter-xs">
                  <q-btn flat dense size="sm" color="primary" no-caps label="Show all" @click="showAllColumns" />
                  <q-btn flat dense size="sm" color="primary" no-caps label="Reset order" @click="resetColumns" />
                </div>
              </q-item-section>
            </q-item>
            <q-separator />
            <q-item v-for="(column, position) in orderedColumns" :key="column.name" dense>
              <q-item-section side>
                <q-checkbox dense size="sm" :model-value="!hidden.includes(column.name)" @update:model-value="toggleColumn(column.name)" />
              </q-item-section>
              <q-item-section class="text-no-wrap">{{ column.name.toUpperCase() }}</q-item-section>
              <q-item-section side>
                <div class="row no-wrap">
                  <q-btn flat dense round size="xs" icon="fas fa-arrow-up" :disable="position === 0" @click="moveColumn(position, -1)" />
                  <q-btn flat dense round size="xs" icon="fas fa-arrow-down" :disable="position === orderedColumns.length - 1" @click="moveColumn(position, 1)" />
                </div>
              </q-item-section>
            </q-item>
          </q-list>
        </q-menu>
      </q-btn>
      <q-btn
        :outline="!view.group"
        :unelevated="Boolean(view.group)"
        dense
        no-caps
        class="q-px-sm"
        color="blue-grey-7"
        icon="fas fa-layer-group"
        label="Group by"
        @click="toggleGroup" />
      <q-btn-dropdown v-if="!view.group" outline dense color="blue-grey-7" icon="fas fa-file-export" no-caps label="Export" class="q-px-sm" :loading="exporting" :disable="!total">
        <q-list dense>
          <q-item v-close-popup clickable @click="exportRows('xlsx')">
            <q-item-section avatar><q-icon name="fas fa-file-excel" color="green-8" /></q-item-section>
            <q-item-section>Excel (.xlsx)</q-item-section>
          </q-item>
          <q-item v-close-popup clickable @click="exportRows('csv')">
            <q-item-section avatar><q-icon name="fas fa-file-csv" color="blue-grey-7" /></q-item-section>
            <q-item-section>CSV</q-item-section>
          </q-item>
        </q-list>
      </q-btn-dropdown>
      <q-chip
        v-for="(filter, index) in view.filters"
        :key="index"
        dense
        removable
        color="teal-1"
        text-color="teal-10"
        icon="fas fa-filter"
        class="filter-chip"
        :title="describeFilter(filter)"
        @remove="removeFilter(index)">
        <span class="ellipsis">{{ describeFilter(filter) }}</span>
      </q-chip>
      <q-btn v-if="view.filters.length || view.search" flat dense no-caps color="grey-7" icon="fas fa-times-circle" label="Clear" @click="clearAll" />
      <q-btn v-if="filtered" flat dense no-caps color="primary" icon="fas fa-chart-bar" label="Profile these rows" @click="$emit('profile-rows')">
        <q-tooltip>Show the profile tabs for the rows the filters and the search leave</q-tooltip>
      </q-btn>
      <q-btn v-if="filtered" flat dense no-caps color="indigo-8" icon="fas fa-database" label="Load from database" :disable="!pushable" @click="$emit('pushdown')">
        <q-tooltip>{{ pushable ? "Fetch a new sample of only the matching records, filtered by the database" : "The duplicate rows filter applies to the sample only" }}</q-tooltip>
      </q-btn>
      <q-space />
      <div class="text-blue-grey-8 text-no-wrap">
        <template v-if="total !== null">
          <strong>{{ formatNumber(total) }}</strong> {{ total === 1 ? "row" : "rows" }}
          <span v-if="filtered" class="text-grey-7">of {{ formatNumber(sampleRows) }} in the sample</span>
        </template>
      </div>
    </div>

    <group-by-panel v-if="view.group" class="col" :session-id="sessionId" :columns="columns" :version="version" :view="view" :group="view.group" @drill="drill" />
    <q-virtual-scroll
      v-show="!view.group"
      ref="scroll"
      type="table"
      dense
      class="list-table viewer-table"
      :style="{ '--table-width': tableWidth + 'px' }"
      :items-size="total || 0"
      :items-fn="rowsAt"
      :virtual-scroll-item-size="33"
      :virtual-scroll-sticky-size-start="30"
      :table-colspan="shownColumns.length + 1">
      <template #before>
        <thead>
          <tr class="bg-blue-grey-2">
            <th class="text-right row-number" :style="{ width: numberWidth + 'px' }">#</th>
            <th v-for="column in shownColumns" :key="column.name" :style="{ width: column.width + 'px' }" :class="column.kind === 'numeric' ? 'text-right' : 'text-left'">
              <div class="row no-wrap items-center" :class="{ 'justify-end': column.kind === 'numeric' }">
                <span class="ellipsis sortable" :title="`${column.name.toUpperCase()} (${column.db_type})`" @click="toggleSort(column.name)">
                  {{ column.name.toUpperCase() }}
                </span>
                <q-icon v-if="sortOf(column.name)" :name="sortOf(column.name).desc ? 'fas fa-sort-down' : 'fas fa-sort-up'" size="12px" class="q-ml-xs" />
                <q-btn
                  flat
                  dense
                  round
                  size="xs"
                  :color="hasFilter(column.name) ? 'teal-8' : 'grey-6'"
                  icon="fas fa-filter"
                  class="q-ml-xs filter-btn"
                  @click.stop="openFilter($event, column)" />
              </div>
            </th>
          </tr>
        </thead>
      </template>
      <template #default="{ item, index }">
        <tr :key="index">
          <td class="text-right text-grey-6 row-number">
            <q-btn v-if="rowAction && item" flat dense round size="xs" color="primary" :icon="rowAction.icon" class="row-action" @click="$emit('row', item)">
              <q-tooltip>{{ rowAction.label }}</q-tooltip>
            </q-btn>
            {{ formatNumber(index + 1) }}
          </td>
          <template v-if="item">
            <td
              v-for="column in shownColumns"
              :key="column.name"
              :class="[column.kind === 'numeric' ? 'text-right' : 'text-left', item[column.position] === null ? 'null-cell' : '']"
              :title="cellTitle(item[column.position], column)">
              {{ item[column.position] === null ? "∅" : formatValue(item[column.position], column.kind, column.dateOnly) }}
            </td>
          </template>
          <td v-else :colspan="shownColumns.length"><q-skeleton type="text" width="60%" animation="fade" /></td>
        </tr>
      </template>
      <template #after>
        <tbody v-if="total === null">
          <skeleton-rows :columns="skeletonColumns" :rows="10" />
        </tbody>
        <tbody v-else-if="total === 0">
          <tr>
            <td :colspan="shownColumns.length + 1" class="text-center text-grey-7 q-pa-lg">No rows match the filters</td>
          </tr>
        </tbody>
      </template>
    </q-virtual-scroll>

    <q-menu ref="filterMenu" :target="filterTarget" no-parent-event anchor="bottom left" self="top left">
      <q-card v-if="filterColumn" style="min-width: 300px; max-width: 380px">
        <q-card-section class="q-pb-sm">
          <div class="text-weight-bold text-blue-grey-9">{{ filterColumn.name.toUpperCase() }}</div>
          <div class="text-caption text-grey-7">{{ filterColumn.db_type }}</div>
        </q-card-section>
        <q-card-section class="q-pt-none q-gutter-sm">
          <q-select v-model="draft.op" dense outlined emit-value map-options options-dense :options="operatorOptions" label="Condition" />
          <template v-if="draft.op === 'range'">
            <q-input v-model="draft.min" dense outlined :label="filterColumn.kind === 'datetime' ? 'From (YYYY-MM-DD HH:MM:SS)' : 'Minimum'" clearable />
            <q-input v-model="draft.max" dense outlined :label="filterColumn.kind === 'datetime' ? 'To (YYYY-MM-DD HH:MM:SS)' : 'Maximum'" clearable />
          </template>
          <q-input v-else-if="['eq', 'ne', 'contains', 'starts'].includes(draft.op)" v-model="draft.value" dense outlined autofocus label="Value" @keyup.enter="applyFilter" />
          <div v-else-if="draft.op === 'in'" class="values-list">
            <div v-if="!topValues.length" class="text-grey-7 text-caption">The most frequent values appear once the columns are profiled.</div>
            <q-checkbox
              v-for="item in topValues"
              :key="String(item.value)"
              v-model="draft.values"
              dense
              size="sm"
              :val="item.value"
              class="full-width">
              <span class="ellipsis">{{ item.value === null ? "(missing)" : formatValue(item.value, filterColumn.kind) }}</span>
              <span class="text-grey-6 q-ml-xs">{{ formatNumber(item.count) }}</span>
            </q-checkbox>
          </div>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn v-if="hasFilter(filterColumn.name)" v-close-popup flat no-caps color="grey-7" label="Remove filter" @click="removeColumnFilters(filterColumn.name)" />
          <q-btn v-close-popup flat no-caps color="grey-8" label="Cancel" />
          <q-btn unelevated no-caps color="primary" label="Apply" :disable="!draftValid" @click="applyFilter" />
        </q-card-actions>
      </q-card>
    </q-menu>
  </div>
</template>

<script>
import { Notify } from "quasar";
import SkeletonRows from "../SkeletonRows.vue";
import GroupByPanel from "./GroupByPanel.vue";
import { api, notifyError } from "../../api";
import { formatNumber } from "../../utils/format";
import { textWidth } from "../../utils/layout";
import { describeFilter, formatValue } from "../../utils/analysis";

const PAGE_SIZE = 200;
const CELL_FONT = "13px Roboto, sans-serif";

const OPERATORS = {
  text: [
    { label: "Contains", value: "contains" },
    { label: "Equals", value: "eq" },
    { label: "Does not equal", value: "ne" },
    { label: "Starts with", value: "starts" },
    { label: "One of the frequent values", value: "in" },
    { label: "Is empty", value: "null" },
    { label: "Is not empty", value: "notnull" },
  ],
  numeric: [
    { label: "Between", value: "range" },
    { label: "Equals", value: "eq" },
    { label: "Does not equal", value: "ne" },
    { label: "One of the frequent values", value: "in" },
    { label: "Is empty", value: "null" },
    { label: "Is not empty", value: "notnull" },
  ],
  datetime: [
    { label: "Between", value: "range" },
    { label: "Equals", value: "eq" },
    { label: "Is empty", value: "null" },
    { label: "Is not empty", value: "notnull" },
  ],
};

// The rows of the sample, served by the analysis worker in windows of 200 as the table scrolls
// (q-virtual-scroll with items-fn): the filters, the search and the sort are applied by the server, so a sample of
// a million rows scrolls like one of a hundred. `view` is the page's {filters, search, sort}, edited in place.
export default {
  name: "DataViewer",
  components: { GroupByPanel, SkeletonRows },
  emits: ["profile-rows", "pushdown", "row"],
  props: {
    sessionId: { type: String, required: true },
    columns: { type: Array, required: true },
    version: { type: Number, default: 0 },
    sampleRows: { type: Number, default: 0 },
    view: { type: Object, required: true },
    profiles: { type: Array, default: null },
    storageKey: { type: String, default: null },
    exportName: { type: String, default: "data" },
    // {icon, label} of a button on every row, emitting "row" with its values.
    rowAction: { type: Object, default: null },
  },
  data() {
    return {
      total: null,
      pages: {},
      token: 0,
      widths: {},
      order: [],
      hidden: [],
      filterTarget: false,
      filterColumn: null,
      draft: { op: null, value: "", min: null, max: null, values: [] },
      exporting: false,
    };
  },
  computed: {
    // The page's view, edited in place like the editor boxes edit their configuration.
    state() {
      return this.view;
    },
    searchText: {
      get() {
        return this.state.search;
      },
      set(value) {
        this.state.search = value || "";
      },
    },
    viewKey() {
      return JSON.stringify([this.sessionId, this.version, this.state.filters, this.state.search, this.state.sort]);
    },
    filtered() {
      return this.state.filters.length > 0 || Boolean(this.state.search);
    },
    pushable() {
      return !this.state.filters.some((filter) => filter.op === "duplicated");
    },
    profileByName() {
      const map = {};
      (this.profiles || []).forEach((profile) => (map[profile.name] = profile));
      return map;
    },
    // The columns in the chosen order, each with its position in the rows the server sends.
    orderedColumns() {
      const positions = {};
      this.columns.forEach((column, position) => (positions[column.name] = position));
      const names = this.order.filter((name) => name in positions);
      this.columns.forEach((column) => !names.includes(column.name) && names.push(column.name));
      return names.map((name) => {
        const column = this.columns[positions[name]];
        const profile = this.profileByName[name];
        return {
          ...column,
          position: positions[name],
          dateOnly: Boolean(profile && profile.stats && profile.stats.date_only),
          width: this.widths[name] || this.defaultWidth(column),
        };
      });
    },
    shownColumns() {
      return this.orderedColumns.filter((column) => !this.hidden.includes(column.name));
    },
    columnsLabel() {
      return this.hidden.length ? `Columns ${this.shownColumns.length}/${this.columns.length}` : "Columns";
    },
    numberWidth() {
      return this.rowAction ? 88 : 64;
    },
    tableWidth() {
      return this.numberWidth + this.shownColumns.reduce((sum, column) => sum + column.width, 0);
    },
    skeletonColumns() {
      return ["text"].concat(this.shownColumns.map(() => "text"));
    },
    operatorOptions() {
      return this.filterColumn ? OPERATORS[this.filterColumn.kind] || OPERATORS.text : [];
    },
    topValues() {
      const profile = this.filterColumn && this.profileByName[this.filterColumn.name];
      if (!profile) {
        return [];
      }
      const values = profile.top.map((item) => ({ value: item.value, count: item.count }));
      if (profile.missing) {
        values.push({ value: null, count: profile.missing });
      }
      return values;
    },
    draftValid() {
      const op = this.draft.op;
      if (op === "range") {
        return Boolean(this.draft.min || this.draft.max);
      }
      if (op === "in") {
        return this.draft.values.length > 0;
      }
      if (["eq", "ne", "contains", "starts"].includes(op)) {
        return this.draft.value !== null && this.draft.value !== "";
      }
      return Boolean(op);
    },
  },
  watch: {
    viewKey: {
      immediate: true,
      handler() {
        this.reset();
      },
    },
    storageKey: {
      immediate: true,
      handler() {
        this.loadPreferences();
      },
    },
  },
  // Answers still on their way belong to a session that is being closed.
  beforeUnmount() {
    this.token += 1;
  },
  methods: {
    formatNumber,
    formatValue,
    describeFilter,
    defaultWidth(column) {
      if (column.kind === "numeric") {
        return Math.max(110, this.headerWidth(column.name));
      }
      if (column.kind === "datetime") {
        return Math.max(160, this.headerWidth(column.name));
      }
      return Math.max(120, this.headerWidth(column.name));
    },
    headerWidth(name) {
      return textWidth([name.toUpperCase()], "bold 13px Roboto, sans-serif") + 48;
    },
    // Text columns are sized once to the values of the first rows, so scrolling never resizes them.
    sizeColumns(rows) {
      const widths = { ...this.widths };
      this.columns.forEach((column, position) => {
        if (widths[column.name] || column.kind !== "text") {
          return;
        }
        const texts = rows.map((row) => (row[position] === null ? "" : String(row[position]).substring(0, 80)));
        widths[column.name] = Math.min(Math.max(this.defaultWidth(column), textWidth(texts, CELL_FONT) + 24), 360);
      });
      this.widths = widths;
    },
    reset() {
      this.token += 1;
      this.pages = {};
      this.loading = {};
      this.total = null;
      if (this.$refs.scroll) {
        this.$refs.scroll.scrollTo(0);
      }
      this.loadPage(0);
    },
    // items-fn of the virtual scroll: the rows it asks for, null where a page is still loading.
    rowsAt(from, size) {
      const rows = [];
      for (let index = from; index < from + size; index += 1) {
        const page = Math.floor(index / PAGE_SIZE);
        const loaded = this.pages[page];
        if (!loaded) {
          this.loadPage(page);
        }
        rows.push(loaded ? loaded[index - page * PAGE_SIZE] || null : null);
      }
      return rows;
    },
    async loadPage(page) {
      if (!this.version || this.loading[page]) {
        return;
      }
      const token = this.token;
      this.loading[page] = true;
      try {
        const result = await api("analysis-rows", {
          params: {
            session_id: this.sessionId,
            offset: page * PAGE_SIZE,
            limit: PAGE_SIZE,
            sort: this.state.sort.length ? JSON.stringify(this.state.sort) : null,
            search: this.state.search || null,
            filters: this.state.filters.length ? JSON.stringify(this.state.filters) : null,
          },
          loadingBar: false,
        });
        if (token !== this.token) {
          return;
        }
        if (page === 0 && result.rows.length) {
          this.sizeColumns(result.rows);
        }
        this.pages = { ...this.pages, [page]: Object.freeze(result.rows) };
        this.total = result.total;
      } catch (error) {
        // A closed or expired session is the page's to report.
        if (token === this.token && error.status !== 404) {
          this.total = this.total === null ? 0 : this.total;
          notifyError("Rows could not be loaded.", error);
        }
      } finally {
        if (token === this.token) {
          this.loading[page] = false;
        }
      }
    },
    cellTitle(value, column) {
      if (value === null) {
        return "Empty";
      }
      const text = formatValue(value, column.kind, column.dateOnly);
      return text.length > 20 ? text : undefined;
    },
    sortOf(name) {
      return this.state.sort.find((item) => item.column === name);
    },
    // Ascending, descending, unsorted.
    toggleSort(name) {
      const current = this.sortOf(name);
      if (!current) {
        this.state.sort = [{ column: name, desc: false }];
      } else if (!current.desc) {
        this.state.sort = [{ column: name, desc: true }];
      } else {
        this.state.sort = [];
      }
    },
    hasFilter(name) {
      return this.state.filters.some((filter) => filter.column === name);
    },
    openFilter(event, column) {
      const existing = this.state.filters.find((filter) => filter.column === column.name);
      const op = existing ? existing.op : column.kind === "text" ? "contains" : "range";
      this.draft = {
        op,
        value: existing && ["eq", "ne", "contains", "starts"].includes(existing.op) ? existing.value : "",
        min: existing && existing.op === "range" ? formatValue(existing.value.min, column.kind) : null,
        max: existing && existing.op === "range" ? formatValue(existing.value.max, column.kind) : null,
        values: existing && existing.op === "in" ? [...existing.value] : [],
      };
      this.filterColumn = column;
      this.filterTarget = event.currentTarget;
      this.$nextTick(() => this.$refs.filterMenu.show());
    },
    applyFilter() {
      if (!this.draftValid) {
        return;
      }
      const column = this.filterColumn;
      const op = this.draft.op;
      const filter = { column: column.name, kind: column.kind, op };
      const typed = (value) => {
        if (value === null || value === undefined || value === "") {
          return null;
        }
        if (column.kind === "numeric") {
          return Number(String(value).replace(",", "."));
        }
        return column.kind === "datetime" ? String(value).trim().replace(" ", "T") : value;
      };
      if (op === "range") {
        filter.value = { min: typed(this.draft.min), max: typed(this.draft.max), max_inclusive: true };
      } else if (op === "in") {
        filter.value = [...this.draft.values];
      } else if (["eq", "ne"].includes(op)) {
        filter.value = typed(this.draft.value);
      } else if (["contains", "starts"].includes(op)) {
        filter.value = this.draft.value;
      }
      if ((op === "eq" || op === "ne") && column.kind === "numeric" && Number.isNaN(filter.value)) {
        Notify.create({ type: "warning", message: `${this.draft.value} is not a number` });
        return;
      }
      this.state.filters = this.state.filters.filter((item) => item.column !== column.name).concat([filter]);
      this.$refs.filterMenu.hide();
    },
    removeFilter(index) {
      this.state.filters = this.state.filters.filter((item, position) => position !== index);
    },
    removeColumnFilters(name) {
      this.state.filters = this.state.filters.filter((item) => item.column !== name);
    },
    toggleGroup() {
      this.state.group = this.state.group ? null : { by: [], aggregates: [], sort: null };
    },
    // A group's rows: its keys become filters, and the rows are shown again.
    drill(filters) {
      const columns = filters.map((filter) => filter.column);
      this.state.filters = this.state.filters.filter((filter) => !columns.includes(filter.column)).concat(filters);
      this.state.group = null;
    },
    clearAll() {
      this.state.filters = [];
      this.state.search = "";
    },
    loadPreferences() {
      this.order = [];
      this.hidden = [];
      if (!this.storageKey) {
        return;
      }
      try {
        const saved = JSON.parse(localStorage.getItem(this.storageKey) || "null");
        if (saved) {
          this.order = Array.isArray(saved.order) ? saved.order : [];
          this.hidden = Array.isArray(saved.hidden) ? saved.hidden : [];
        }
      } catch (error) {
        // Storage may be unavailable or hold something else; the defaults apply.
      }
    },
    savePreferences() {
      if (!this.storageKey) {
        return;
      }
      try {
        localStorage.setItem(this.storageKey, JSON.stringify({ order: this.order, hidden: this.hidden }));
      } catch (error) {
        // Not remembered, which is all a failure costs.
      }
    },
    toggleColumn(name) {
      this.hidden = this.hidden.includes(name) ? this.hidden.filter((item) => item !== name) : this.hidden.concat([name]);
      this.savePreferences();
    },
    moveColumn(position, step) {
      const names = this.orderedColumns.map((column) => column.name);
      const [name] = names.splice(position, 1);
      names.splice(position + step, 0, name);
      this.order = names;
      this.savePreferences();
    },
    showAllColumns() {
      this.hidden = [];
      this.savePreferences();
    },
    resetColumns() {
      this.order = [];
      this.hidden = [];
      this.savePreferences();
    },
    // Downloads the rows as viewed: filters, search, sort, and the shown columns in their order.
    async exportRows(format) {
      this.exporting = true;
      try {
        const response = await api("analysis-export", {
          params: {
            session_id: this.sessionId,
            format,
            sort: this.state.sort.length ? JSON.stringify(this.state.sort) : null,
            search: this.state.search || null,
            filters: this.state.filters.length ? JSON.stringify(this.state.filters) : null,
            columns: JSON.stringify(this.shownColumns.map((column) => column.name)),
          },
          raw: true,
        });
        const blob = await response.blob();
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = `${this.exportName}.${format}`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(link.href), 10000);
        const cut = response.headers.get("X-Rapo-Cut");
        if (cut) {
          Notify.create({ type: "warning", message: `Excel holds at most ${formatNumber(Number(cut))} rows; the file was cut there. Use CSV for all rows.` });
        }
      } catch (error) {
        notifyError("The export failed.", error);
      } finally {
        this.exporting = false;
      }
    },
  },
};
</script>

<style scoped>
.viewer {
  height: 100%;
  min-height: 0;
}

.toolbar {
  flex: 0 0 auto;
}

.search-input {
  width: 260px;
}

.filter-chip {
  max-width: 320px;
}

.viewer-table :deep(table) {
  table-layout: fixed;
  width: max(100%, var(--table-width));
}

.viewer-table td {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 13px;
}

.viewer-table .row-number {
  font-size: 11px;
}

.row-action {
  float: left;
}

.viewer-table .null-cell {
  color: #b0bec5;
}

.sortable {
  cursor: pointer;
  user-select: none;
}

.filter-btn {
  opacity: 0.8;
}

.values-list {
  max-height: 260px;
  overflow-y: auto;
}
</style>
