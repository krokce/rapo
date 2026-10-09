<template>
  <div class="column no-wrap records-pane">
    <div class="row items-center q-gutter-sm q-pb-sm records-head">
      <q-select
        v-model="table"
        class="records-table"
        dense
        outlined
        options-dense
        emit-value
        map-options
        label="Table"
        :options="tableOptions"
        :loading="loadingTables"
        @update:model-value="reset">
        <template #option="scope">
          <q-item v-bind="scope.itemProps">
            <q-item-section>
              <q-item-label class="text-mono">{{ scope.opt.label }}</q-item-label>
              <q-item-label caption>{{ scope.opt.caption }}</q-item-label>
            </q-item-section>
          </q-item>
        </template>
      </q-select>
      <q-input v-model="search" class="records-search" dense outlined clearable debounce="400" placeholder="Search all columns" :disable="!table">
        <template #prepend><q-icon name="fas fa-search" size="14px" /></template>
      </q-input>
      <q-btn outline no-caps color="blue-grey-7" icon="fas fa-columns" :label="columnsLabel" class="records-columns" :disable="!columns.length">
        <q-menu anchor="bottom left" self="top left" @hide="columnFind = ''">
          <q-list dense style="min-width: 260px">
            <q-item>
              <q-item-section>
                <q-input v-model="columnFind" dense outlined clearable autofocus placeholder="Find a column" class="q-mb-xs">
                  <template #prepend><q-icon name="fas fa-search" size="12px" /></template>
                </q-input>
                <div class="row q-gutter-xs">
                  <q-btn flat dense size="sm" color="primary" no-caps :label="columnFind ? 'Show found' : 'Show all'" @click="setColumnsHidden(false)" />
                  <q-btn flat dense size="sm" color="primary" no-caps :label="columnFind ? 'Hide found' : 'Hide all'" @click="setColumnsHidden(true)" />
                  <q-btn flat dense size="sm" color="primary" no-caps label="Reset order" @click="resetColumns" />
                </div>
              </q-item-section>
            </q-item>
            <q-separator />
            <q-item v-if="!pickerColumns.length" dense>
              <q-item-section class="text-grey-7">No column matches</q-item-section>
            </q-item>
            <q-item v-for="{ column, position } in pickerColumns" :key="column.name" dense>
              <q-item-section side>
                <q-checkbox dense size="sm" :model-value="!hidden.includes(column.name)" @update:model-value="toggleColumn(column.name)" />
              </q-item-section>
              <q-item-section class="text-no-wrap">{{ column.name.toUpperCase() }}</q-item-section>
              <q-item-section side>
                <div class="row no-wrap">
                  <q-btn aria-label="Move up" flat dense round size="xs" icon="fas fa-arrow-up" :disable="Boolean(columnFind) || position === 0" @click="moveColumn(position, -1)" />
                  <q-btn
                    aria-label="Move down"
                    flat
                    dense
                    round
                    size="xs"
                    icon="fas fa-arrow-down"
                    :disable="Boolean(columnFind) || position === orderedColumns.length - 1"
                    @click="moveColumn(position, 1)" />
                </div>
              </q-item-section>
            </q-item>
          </q-list>
        </q-menu>
      </q-btn>
      <div v-if="current && current.count !== null" class="text-blue-grey-9">
        <strong>{{ formatNumber(current.count) }}</strong> rows of file {{ fileId }}
        <span v-if="file" :class="{ 'text-orange-9 text-weight-medium': mismatch }">
          · the file log: {{ formatNumber(file.recordswrite || 0) }} written<span :class="{ 'text-red-7': file.recordsreject && !mismatch }">, {{ formatNumber(file.recordsreject || 0) }} rejected</span>
          <q-icon v-if="mismatch" name="fas fa-exclamation-triangle" color="orange-8" />
          <q-tooltip v-if="mismatch" max-width="380px">
            The tables hold {{ formatNumber(tablesTotal) }} rows of this file in all, the file log counts {{ formatNumber(logTotal) }} written and rejected
          </q-tooltip>
        </span>
      </div>
      <q-space />
      <div v-if="total !== null" class="text-blue-grey-9">
        <template v-if="searchText">
          <strong>{{ formatNumber(total) }}</strong> of {{ formatNumber(current ? current.count : 0) }} rows
        </template>
        <template v-else>
          <strong>{{ formatNumber(total) }}</strong> rows
        </template>
      </div>
      <q-btn v-if="table && current && current.count" flat dense no-caps color="primary" icon="fas fa-chart-bar" label="Open in Data analysis" :to="analysisLink">
        <q-tooltip>These rows on the Data analysis page: overview, columns, missing values, duplicates, correlations</q-tooltip>
      </q-btn>
    </div>

    <q-banner v-if="error" dense rounded class="bg-red-1 text-red-9 q-mb-sm">
      {{ error }}
      <template #action>
        <q-btn flat dense color="red-9" label="Try again" @click="tables.length ? reset() : load()" />
      </template>
    </q-banner>

    <q-virtual-scroll
      v-if="table && !error"
      ref="scroll"
      type="table"
      dense
      class="col list-table records-grid"
      :style="{ '--table-width': tableWidth + 'px' }"
      :items-size="total || 0"
      :items-fn="rowsAt"
      :virtual-scroll-item-size="33"
      :virtual-scroll-sticky-size-start="28"
      :table-colspan="shownColumns.length + 1">
      <template #before>
        <thead>
          <tr class="bg-blue-grey-2">
            <th title="The row's number among the file's rows (in the order they were loaded)" class="text-right row-number">#</th>
            <th
              v-for="column in shownColumns"
              :key="column.name"
              :style="{ width: column.width + 'px' }"
              :class="column.kind === 'numeric' ? 'text-right' : 'text-left'"
              :title="`${column.name.toUpperCase()} (${column.kind})`">
              {{ column.name.toUpperCase() }}
            </th>
          </tr>
        </thead>
      </template>
      <template #default="{ item, index }">
        <tr :key="index">
          <td class="text-right text-grey-7 row-number number-cell">{{ formatNumber(index + 1) }}</td>
          <template v-if="item">
            <td
              v-for="column in shownColumns"
              :key="column.name"
              :class="[column.kind === 'numeric' ? 'text-right number-cell' : 'text-left', item[column.position] === null ? 'null-cell' : '']"
              :title="cellTitle(item[column.position], column)">
              {{ item[column.position] === null ? "∅" : formatValue(item[column.position], column.kind) }}
            </td>
          </template>
          <td v-else :colspan="shownColumns.length"><q-skeleton type="text" width="60%" animation="fade" /></td>
        </tr>
      </template>
      <template #after>
        <tbody v-if="total === 0">
          <tr>
            <td :colspan="shownColumns.length + 1" class="text-center text-grey-7 q-pa-lg">
              {{ searchText ? "No row matches the search" : "No rows of this file in the table" }}
            </td>
          </tr>
        </tbody>
      </template>
    </q-virtual-scroll>
    <div v-if="total === null && (table || loadingTables) && !error" class="col q-pa-sm">
      <q-skeleton v-for="line in 6" :key="line" type="text" class="q-mb-xs" />
    </div>
    <div v-else-if="!loadingTables && !error && !table" class="col column items-center justify-center text-grey-7">
      <q-icon name="fas fa-database" size="28px" class="q-mb-sm" />
      No table of the datasource can be read for this file.
    </div>
  </div>
</template>

<script>
import { api, notifyError } from "../api";
import { formatValue } from "../utils/analysis";
import { formatNumber } from "../utils/format";
import { textWidth } from "../utils/layout";

const PAGE_SIZE = 200;
const CELL_FONT = "13px Roboto, sans-serif";
const NUMBER_WIDTH = 64;

// The records PDI Core loaded from one file: the tables of its datasource (get-file-tables, rows by FILE_ID), and the
// rows of one of them as a plain table read page by page from the database (get-file-records, ROWID order), searched
// in all columns by the database. No analysis session: the full Data analysis page is one link away. The Columns menu
// keeps its choices under the key the Data tab uses for the table, so both show the same columns.
export default {
  name: "FileRecordsPane",
  props: {
    fileId: { type: Number, required: true },
  },
  data() {
    return {
      file: null,
      tables: [],
      table: null,
      loadingTables: false,
      error: null,
      search: "",
      columns: [],
      total: null,
      pages: {},
      widths: {},
      order: [],
      hidden: [],
      columnFind: "",
    };
  },
  computed: {
    searchText() {
      return (this.search || "").trim();
    },
    usable() {
      return this.tables.filter((item) => item.count !== null);
    },
    current() {
      return this.tables.find((item) => item.table_name === this.table) || null;
    },
    tableOptions() {
      return this.tables.map((item) => ({
        label: item.table_name,
        value: item.table_name,
        caption: item.count !== null ? `${formatNumber(item.count)} rows of this file` : item.reason,
        disable: item.count === null,
      }));
    },
    // The rows of the file in all its tables against what the file log says were written and rejected (a datasource
    // may keep its rejects in a table of its own).
    tablesTotal() {
      return this.usable.reduce((total, item) => total + item.count, 0);
    },
    logTotal() {
      return this.file ? (this.file.recordswrite || 0) + (this.file.recordsreject || 0) : 0;
    },
    mismatch() {
      return Boolean(this.file && this.usable.length && this.tablesTotal !== this.logTotal && this.tablesTotal !== (this.file.recordswrite || 0));
    },
    storageKey() {
      return this.table ? `rapo_analysis_columns_file_${this.table}` : null;
    },
    // The columns in the chosen order, each with its position in the rows the server sends.
    orderedColumns() {
      const positions = {};
      this.columns.forEach((column, position) => (positions[column.name] = position));
      const names = this.order.filter((name) => name in positions);
      this.columns.forEach((column) => !names.includes(column.name) && names.push(column.name));
      return names.map((name) => {
        const column = this.columns[positions[name]];
        return { ...column, position: positions[name], width: this.widths[name] || this.defaultWidth(column) };
      });
    },
    pickerColumns() {
      const find = (this.columnFind || "").toLowerCase();
      return this.orderedColumns.map((column, position) => ({ column, position })).filter(({ column }) => !find || column.name.includes(find));
    },
    shownColumns() {
      return this.orderedColumns.filter((column) => !this.hidden.includes(column.name));
    },
    columnsLabel() {
      return this.hidden.length ? `Columns ${this.shownColumns.length}/${this.columns.length}` : "Columns";
    },
    tableWidth() {
      return this.shownColumns.reduce((total, column) => total + column.width, NUMBER_WIDTH);
    },
    analysisLink() {
      const query = this.searchText ? { pd: JSON.stringify({ search: this.searchText }) } : {};
      return { name: "file-analysis", params: { fileId: this.fileId, table: this.table }, query };
    },
  },
  watch: {
    fileId() {
      this.load();
    },
    searchText() {
      this.reset();
    },
  },
  created() {
    this.token = 0;
    this.loading = {};
    this.load();
  },
  methods: {
    formatNumber,
    formatValue,
    // The tables and their counts; the first table with rows of the file is shown.
    async load() {
      this.loadingTables = true;
      this.error = null;
      this.table = null;
      try {
        const result = await api("get-file-tables", { params: { file_id: this.fileId }, loadingBar: false });
        this.file = result.file;
        this.tables = result.tables;
        const first = this.tables.find((item) => item.count) || this.usable[0];
        this.table = first ? first.table_name : null;
      } catch (error) {
        this.error = `The tables could not be read: ${error.message}`;
      } finally {
        this.loadingTables = false;
      }
      if (!this.error) {
        this.reset();
      }
    },
    // Another table or search: the pages are read anew, from the first.
    reset() {
      this.token += 1;
      this.pages = {};
      this.loading = {};
      this.total = null;
      this.error = null;
      if (this.$refs.scroll) {
        this.$refs.scroll.scrollTo(0);
      }
      if (this.table) {
        this.loadPage(0);
      }
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
      if (this.loading[page]) {
        return;
      }
      const token = this.token;
      const table = this.table;
      this.loading[page] = true;
      try {
        const result = await api("get-file-records", {
          params: { file_id: this.fileId, table, search: this.searchText || null, offset: page * PAGE_SIZE, limit: PAGE_SIZE, count: page === 0 },
          loadingBar: false,
        });
        if (token !== this.token) {
          return;
        }
        if (page === 0) {
          const columns = result.columns.map((column) => ({ name: column.name.toLowerCase(), kind: column.kind }));
          if (JSON.stringify(columns) !== JSON.stringify(this.columns)) {
            this.columns = columns;
            this.widths = {};
            this.loadPreferences();
          }
          this.total = result.total;
          this.sizeColumns(result.rows);
        }
        this.pages = { ...this.pages, [page]: Object.freeze(result.rows) };
      } catch (error) {
        if (token === this.token) {
          if (page === 0) {
            this.error = `The rows could not be read: ${error.message}`;
          } else {
            notifyError("Rows could not be loaded.", error);
          }
        }
      } finally {
        if (token === this.token) {
          this.loading[page] = false;
        }
      }
    },
    defaultWidth(column) {
      const header = textWidth([column.name.toUpperCase()], "bold 13px Roboto, sans-serif") + 32;
      if (column.kind === "numeric") {
        return Math.max(100, header);
      }
      if (column.kind === "datetime") {
        return Math.max(160, header);
      }
      return Math.max(110, header);
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
    cellTitle(value, column) {
      if (value === null) {
        return "Empty";
      }
      const text = formatValue(value, column.kind);
      return text.length > 20 ? text : undefined;
    },
    loadPreferences() {
      this.order = [];
      this.hidden = [];
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
    // Shows or hides every column, or only the found ones while the menu's search is set.
    setColumnsHidden(hide) {
      const names = this.pickerColumns.map(({ column }) => column.name);
      const others = this.hidden.filter((name) => !names.includes(name));
      this.hidden = hide ? others.concat(names) : others;
      this.savePreferences();
    },
    resetColumns() {
      this.order = [];
      this.hidden = [];
      this.savePreferences();
    },
  },
};
</script>

<style scoped>
.records-pane {
  height: 100%;
  min-height: 0;
}
.records-head {
  flex: 0 0 auto;
}
.records-table {
  min-width: 280px;
}
.records-search {
  width: 260px;
}
/* As tall as the dense fields beside it. */
.records-columns {
  height: 40px;
}
.records-grid :deep(table) {
  table-layout: fixed;
  width: max(100%, var(--table-width));
}
.records-grid th.row-number {
  width: 64px;
}
.records-grid td {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 13px;
}
.records-grid .row-number {
  font-size: 11px;
}
.records-grid .null-cell {
  color: var(--rapo-label);
}
</style>
