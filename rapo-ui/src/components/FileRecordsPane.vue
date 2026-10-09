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
        @update:model-value="tableChanged">
        <template #option="scope">
          <q-item v-bind="scope.itemProps">
            <q-item-section>
              <q-item-label class="text-mono">{{ scope.opt.label }}</q-item-label>
              <q-item-label caption>{{ scope.opt.caption }}</q-item-label>
            </q-item-section>
          </q-item>
        </template>
      </q-select>
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
      <q-chip v-if="pushdown" dense removable color="indigo-1" text-color="indigo-10" icon="fas fa-database" class="pushdown-chip" :title="pushdownText" @remove="restart(null)">
        <span class="ellipsis">Filtered in the database: {{ pushdownText }}</span>
      </q-chip>
      <q-space />
      <template v-if="session">
        <div v-if="busy" class="row items-center no-wrap q-gutter-x-xs text-grey-8">
          <q-spinner-dots color="primary" size="18px" />
          <span>{{ state.step || "Loading" }}</span>
        </div>
        <div v-else class="text-caption text-grey-8">Sample {{ formatNumber(state.rows || 0) }}{{ state.exhausted ? " (all rows)" : "" }}</div>
        <q-btn v-if="!busy && !state.exhausted && state.cursor_open" outline dense no-caps color="primary" icon="fas fa-plus" class="q-px-sm" label="Extend" @click="extend">
          <q-tooltip>Fetch the next rows into the sample</q-tooltip>
        </q-btn>
      </template>
      <q-btn v-if="table && current && current.count" flat dense no-caps color="primary" icon="fas fa-chart-bar" label="Open in Data analysis" :to="analysisLink">
        <q-tooltip>These rows on the Data analysis page: overview, columns, missing values, duplicates, correlations</q-tooltip>
      </q-btn>
    </div>

    <q-banner v-if="error" dense rounded class="bg-red-1 text-red-9 q-mb-sm">
      {{ error }}
      <template #action>
        <q-btn flat dense color="red-9" label="Try again" @click="restart(pushdown)" />
      </template>
    </q-banner>

    <data-viewer
      v-if="session && state.columns"
      class="col"
      :session-id="session.session_id"
      :columns="state.columns || []"
      :version="state.version"
      :sample-rows="state.rows"
      :view="view"
      :storage-key="storageKey"
      :export-name="session.meta.export_name"
      @pushdown="pushFilters" />
    <div v-else-if="starting || busy || loadingTables" class="col q-pa-sm">
      <q-skeleton type="rect" height="40px" class="q-mb-sm" />
      <q-skeleton type="rect" class="col" height="160px" />
    </div>
    <div v-else-if="!loadingTables && !error && !usable.length" class="col column items-center justify-center text-grey-7">
      <q-icon name="fas fa-database" size="28px" class="q-mb-sm" />
      No table of the datasource can be read for this file.
    </div>
  </div>
</template>

<script>
import socket from "../socket";
import { api, notifyError } from "../api";
import { closeAnalysisSession, describeFilter } from "../utils/analysis";
import { formatNumber } from "../utils/format";
import DataViewer from "./analysis/DataViewer.vue";

// The records PDI Core loaded from one file: the tables of its datasource (get-file-tables, rows by FILE_ID), and the
// rows of one of them in the Data tab of Data analysis (an analysis session, analysis-start-file, on the first rows
// as the index returns them). The session is closed when another table is chosen, the pane goes, or the page is left.
export default {
  name: "FileRecordsPane",
  components: { DataViewer },
  props: {
    fileId: { type: Number, required: true },
  },
  data() {
    return {
      file: null,
      tables: [],
      table: null,
      loadingTables: false,
      session: null,
      state: {},
      starting: false,
      error: null,
      view: { filters: [], search: "", sort: [], group: null },
      // {filters, search} applied by the database, or null.
      pushdown: null,
    };
  },
  computed: {
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
    busy() {
      return ["starting", "fetching", "profiling"].includes(this.state.status);
    },
    pushdownText() {
      const pushdown = this.pushdown || {};
      const parts = (pushdown.filters || []).map(describeFilter);
      if (pushdown.search) {
        parts.push(`contains "${pushdown.search}"`);
      }
      return parts.join(" and ");
    },
    storageKey() {
      return this.table ? `rapo_analysis_columns_file_${this.table}` : null;
    },
    analysisLink() {
      const query = this.pushdown ? { pd: JSON.stringify(this.pushdown) } : {};
      return { name: "file-analysis", params: { fileId: this.fileId, table: this.table }, query };
    },
  },
  watch: {
    fileId() {
      this.load();
    },
  },
  created() {
    this.request = 0;
    this.onProgress = (payload) => {
      if (this.session && payload.session_id === this.session.session_id) {
        this.state = payload.state || {};
      }
    };
    this.onConnect = () => this.refreshState();
    this.onUnload = () => this.closeSession();
    socket.on("analysis:progress", this.onProgress);
    socket.on("connect", this.onConnect);
    window.addEventListener("pagehide", this.onUnload);
    this.load();
  },
  unmounted() {
    socket.off("analysis:progress", this.onProgress);
    socket.off("connect", this.onConnect);
    window.removeEventListener("pagehide", this.onUnload);
    this.closeSession();
  },
  methods: {
    formatNumber,
    // The tables and their counts; the first table with rows of the file is shown.
    async load() {
      this.closeSession();
      this.loadingTables = true;
      this.error = null;
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
      if (this.table) {
        this.restart(null);
      }
    },
    tableChanged() {
      this.view = { filters: [], search: "", sort: [], group: null };
      this.restart(null);
    },
    closeSession() {
      this.request += 1;
      if (this.session) {
        closeAnalysisSession(this.session.session_id);
      }
      this.session = null;
      this.state = {};
    },
    // A new sample of the chosen table, with the filters the database applies, or none.
    async restart(pushdown) {
      this.closeSession();
      this.pushdown = pushdown;
      this.error = null;
      if (!this.table) {
        return;
      }
      const request = this.request;
      this.starting = true;
      try {
        const session = await api("analysis-start-file", {
          method: "POST",
          params: { file_id: this.fileId, table: this.table, random: false },
          body: pushdown || undefined,
          loadingBar: false,
        });
        if (request !== this.request) {
          closeAnalysisSession(session.session_id);
          return;
        }
        this.session = session;
        this.state = session.state || {};
        // A small sample is ready before this answer arrives, and its progress was pushed while no session was known.
        if (this.busy) {
          this.refreshState();
        }
      } catch (error) {
        if (request === this.request) {
          this.error = `The rows could not be loaded: ${error.message}`;
        }
      } finally {
        if (request === this.request) {
          this.starting = false;
        }
      }
    },
    async refreshState() {
      if (!this.session) {
        return;
      }
      try {
        const session = await api("analysis-status", { params: { session_id: this.session.session_id }, loadingBar: false });
        this.state = session.state || {};
      } catch (error) {
        if (error.status === 404) {
          this.session = null;
          this.error = "The rows were closed after they were not used for a while.";
        }
      }
    },
    async extend() {
      try {
        const result = await api("analysis-extend", { method: "POST", params: { session_id: this.session.session_id }, loadingBar: false });
        this.state = result.state || {};
      } catch (error) {
        notifyError("The sample could not be extended.", error);
      }
    },
    // The viewer's filters and search move into the database: a new sample of the matching rows of the file only.
    pushFilters() {
      const previous = this.pushdown || {};
      const pushdown = {
        filters: [...(previous.filters || []), ...this.view.filters],
        search: this.view.search || previous.search || "",
      };
      this.view.filters = [];
      this.view.search = "";
      this.restart(pushdown);
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
.pushdown-chip {
  max-width: 420px;
}
</style>
