<template>
  <q-page class="column no-wrap" :style-fn="fillViewportToBottom">
    <div class="row items-end q-mb-md">
      <h2 class="row items-center no-wrap text-no-wrap q-gutter-md q-mb-none">
        <div>Data analysis</div>
        <div class="text-grey-6 analysis-subtitle">{{ datasetLabel(meta) || datasetTitle }}</div>
      </h2>
      <q-space />
      <div v-if="meta" class="row items-center justify-end q-gutter-x-md text-blue-grey-8">
        <q-chip>
          <q-avatar :icon="controlType(meta.control_type).icon" :color="controlType(meta.control_type).color" text-color="white" />
          {{ meta.control_type }}
          <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">{{ controlType(meta.control_type).label }}</q-tooltip>
        </q-chip>
        <router-link class="control-link text-weight-bold" :to="{ name: 'edit-control', params: { controlId: meta.control_id } }">
          {{ meta.control_name }}
        </router-link>
        <div>
          PID <strong>{{ meta.process_id }}</strong>
        </div>
        <div>
          {{ windowText }}
        </div>
        <q-chip>
          <q-avatar :icon="runStatus(meta.status).icon" :color="runStatus(meta.status).color" text-color="white" />
          {{ runStatus(meta.status).label }}
        </q-chip>
        <q-btn flat dense round size="sm" color="blue-grey-7" icon="fas fa-link" @click="copyLink">
          <q-tooltip anchor="top middle" self="bottom middle">Copy a link to this view</q-tooltip>
        </q-btn>
      </div>
    </div>

    <q-banner v-if="startError" class="bg-red-1 text-red-9 q-mb-md" rounded>
      <template #avatar><q-icon name="fas fa-exclamation-triangle" color="red-7" /></template>
      {{ startError }}
      <template #action>
        <q-btn v-if="pushdown" flat color="red-9" label="Without the database filter" @click="startWith(null)" />
        <q-btn flat color="red-9" label="Try again" @click="start" />
        <q-btn flat color="red-9" label="Back to results" :to="{ name: 'results' }" />
      </template>
    </q-banner>

    <q-banner v-if="ended" class="bg-amber-1 text-brown-9 q-mb-md" rounded>
      <template #avatar><q-icon name="fas fa-hourglass-end" color="amber-9" /></template>
      {{ endedMessage }}
      <template #action>
        <q-btn flat color="brown-9" label="Start again" @click="start" />
      </template>
    </q-banner>

    <q-banner v-if="meta && meta.stale" dense class="bg-orange-1 text-orange-10 q-mb-md" rounded>
      <template #avatar><q-icon name="fas fa-history" color="orange-8" /></template>
      The control was changed after this run. The data is selected with its current configuration for the run's window, so it
      may differ from what the run fetched.
    </q-banner>

    <!-- The sample: how much of the dataset is loaded, the step in progress, and Extend. -->
    <q-card v-if="session || starting" flat bordered class="q-mb-md sample-bar">
      <q-card-section class="row items-center q-py-sm q-gutter-x-md">
        <q-icon name="fas fa-database" color="blue-grey-6" size="18px" />
        <div class="text-blue-grey-9">
          <template v-if="state.rows || state.version">
            Sample <strong>{{ formatNumber(state.rows) }}</strong> rows
            <template v-if="totalRows !== null">
              of <strong>{{ formatNumber(totalRows) }}</strong>
              <span v-if="!meta.total_exact && !state.exhausted" class="text-grey-7"> (at run time)</span>
            </template>
            <span class="text-grey-7"> · first rows</span>
          </template>
          <template v-else>Loading the sample…</template>
        </div>
        <q-chip
          v-if="pushdown"
          dense
          removable
          color="indigo-1"
          text-color="indigo-10"
          icon="fas fa-database"
          class="pushdown-chip"
          :title="pushdownText"
          @remove="startWith(null)">
          <span class="ellipsis">Filtered in the database: {{ pushdownText }}</span>
        </q-chip>
        <q-chip v-if="state.exhausted" dense color="green-1" text-color="green-9" icon="fas fa-check">All rows loaded</q-chip>
        <q-chip v-else-if="state.limited === 'rows'" dense color="amber-1" text-color="brown-9" icon="fas fa-ban">
          Row limit {{ formatNumber(options.max_rows) }} reached
        </q-chip>
        <q-chip v-else-if="state.limited === 'memory'" dense color="amber-1" text-color="brown-9" icon="fas fa-memory">
          Memory limit {{ formatNumber(options.max_memory_mb) }} MB reached
        </q-chip>
        <q-chip v-else-if="state.version && !state.cursor_open" dense color="grey-3" text-color="grey-8" icon="fas fa-unlink">
          The dataset can no longer be extended
        </q-chip>
        <div v-if="busy" class="col row items-center no-wrap q-gutter-x-sm busy-step">
          <q-spinner-dots color="primary" size="20px" />
          <div class="text-grey-8 text-no-wrap">{{ state.step || "Working" }}{{ progressText }}</div>
          <q-linear-progress v-if="progressValue !== null" class="col" rounded size="6px" :value="progressValue" color="primary" />
        </div>
        <q-space v-else />
        <div v-if="state.error && !busy && !ended" class="text-red-8 ellipsis error-text" :title="state.error">
          <q-icon name="fas fa-exclamation-circle" /> {{ state.error }}
        </div>
        <q-btn v-if="busy" flat dense no-caps color="red-7" icon="fas fa-stop-circle" label="Cancel" :disable="!session" @click="cancel" />
        <q-btn
          v-else-if="!state.exhausted"
          outline
          dense
          no-caps
          class="q-px-sm"
          color="primary"
          icon="fas fa-plus"
          :label="`Extend by ${formatNumber(extendRows)}`"
          :disable="!canExtend"
          @click="extend">
          <q-tooltip anchor="top middle" self="bottom middle">Fetch the next rows of the dataset into the sample</q-tooltip>
        </q-btn>
        <q-btn flat dense round size="sm" color="blue-grey-7" icon="fas fa-code" :disable="!session" @click="$refs.sqlFilter.open(pushdown && pushdown.where)">
          <q-tooltip anchor="top middle" self="bottom middle">SQL filter, applied by the database</q-tooltip>
        </q-btn>
        <q-btn flat dense round size="sm" color="blue-grey-7" icon="fas fa-copy" :disable="!meta" @click="copySql">
          <q-tooltip anchor="top middle" self="bottom middle">Copy SQL to clipboard</q-tooltip>
        </q-btn>
      </q-card-section>
    </q-card>
    <counterpart-dialog v-if="session" ref="counterpart" :session-id="session.session_id" :columns="state.columns || []" :side="meta.side || 'A'" />
    <sql-filter-dialog ref="sqlFilter" :process-id="$route.params.processId" :dataset="$route.params.dataset" :columns="state.columns || []" @apply="applyWhere" />

    <template v-if="session">
      <q-tabs v-model="tab" dense align="left" class="text-blue-grey-8" active-color="primary" indicator-color="primary" no-caps>
        <q-tab name="overview" icon="fas fa-clipboard-list" label="Overview" />
        <q-tab name="columns" icon="fas fa-columns" label="Columns" />
        <q-tab name="correlations" icon="fas fa-project-diagram" label="Correlations" />
        <q-tab name="missing" icon="fas fa-th" label="Missing values" />
        <q-tab name="duplicates" icon="fas fa-clone" label="Duplicates" />
        <q-tab name="compare" icon="fas fa-balance-scale" label="Compare">
          <q-badge v-if="compare.target" color="deep-orange-5" floating>B</q-badge>
        </q-tab>
        <q-tab name="data" icon="fas fa-table" label="Data">
          <q-badge v-if="view.filters.length || view.search" color="primary" floating>{{ view.filters.length + (view.search ? 1 : 0) }}</q-badge>
        </q-tab>
      </q-tabs>
      <q-separator />
      <!-- A profile of filtered rows: says which rows, and goes back to the whole sample. -->
      <div v-if="scope && tab !== 'data'" class="row items-center q-gutter-sm q-pt-sm scope-bar">
        <q-icon name="fas fa-filter" color="teal-8" />
        <span class="text-teal-10">Profile of the rows matching</span>
        <q-chip v-for="(filter, index) in scope.filters" :key="index" dense color="teal-1" text-color="teal-10">{{ describeFilter(filter) }}</q-chip>
        <q-chip v-if="scope.search" dense color="teal-1" text-color="teal-10">contains "{{ scope.search }}"</q-chip>
        <q-btn flat dense no-caps color="primary" icon="fas fa-times" label="Whole sample" @click="scope = null" />
      </div>
      <q-tab-panels v-model="tab" class="col analysis-panels" keep-alive>
        <q-tab-panel name="overview" class="scroll-panel">
          <run-trend class="q-mb-lg" :process-id="Number($route.params.processId)" :dataset="$route.params.dataset" :report-only="meta.control_type === 'REP'" />
          <result-breakdown v-if="hasBreakdown" class="q-mb-lg" :breakdown="sectionData('breakdown')" @show-rows="showRows" />
          <analysis-overview :overview="sectionData('overview')" @show-rows="showRows" @show-column="showColumn" />
        </q-tab-panel>
        <q-tab-panel name="columns" class="scroll-panel">
          <analysis-columns ref="columns" :columns="sectionData('columns')" :types="state.columns || []" @show-rows="showRows" />
        </q-tab-panel>
        <q-tab-panel name="correlations" class="scroll-panel">
          <analysis-correlations :correlations="sectionData('correlations')" />
        </q-tab-panel>
        <q-tab-panel name="missing" class="scroll-panel">
          <analysis-missing :missing="sectionData('missing')" @show-rows="showRows" />
        </q-tab-panel>
        <q-tab-panel name="duplicates" class="scroll-panel">
          <analysis-duplicates :duplicates="sectionData('duplicates')" :kinds="columnKinds" @show-rows="showRows" />
        </q-tab-panel>
        <q-tab-panel name="compare" class="scroll-panel">
          <compare-tab
            :session-id="session.session_id"
            :meta="meta"
            :state-a="state"
            :label-a="datasetLabel(meta)"
            :compare="compare"
            @start-target="startCompare"
            @close-target="closeCompare"
            @extend-target="extendCompare"
            @show-rows="showRows" />
        </q-tab-panel>
        <q-tab-panel name="data" class="column no-wrap q-pa-none q-pt-md data-panel">
          <data-viewer
            :session-id="session.session_id"
            :columns="state.columns || []"
            :version="state.version"
            :sample-rows="state.rows"
            :view="view"
            :profiles="sampleColumns"
            :storage-key="storageKey"
            :export-name="exportName"
            :row-action="meta.control_type === 'REC' ? { icon: 'fas fa-exchange-alt', label: 'Find the counterpart on the other side' } : null"
            @profile-rows="profileRows"
            @pushdown="pushFilters"
            @row="(row) => $refs.counterpart.open(row)" />
        </q-tab-panel>
      </q-tab-panels>
    </template>
    <div v-else-if="starting" class="col q-pa-md">
      <q-skeleton type="rect" height="40px" class="q-mb-md" />
      <q-skeleton type="rect" height="220px" />
    </div>
  </q-page>
</template>

<script>
import { Dialog, Notify } from "quasar";
import socket from "../../socket";
import { api, notifyError } from "../../api";
import store from "../../store";
import { controlType, runStatus } from "../../constants";
import { copyText, formatNumber, toDateTimeString } from "../../utils/format";
import { fillViewportToBottom } from "../../utils/layout";
import { DATASETS, datasetLabel, describeFilter } from "../../utils/analysis";
import AnalysisColumns from "./AnalysisColumns.vue";
import AnalysisCorrelations from "./AnalysisCorrelations.vue";
import AnalysisDuplicates from "./AnalysisDuplicates.vue";
import AnalysisMissing from "./AnalysisMissing.vue";
import AnalysisOverview from "./AnalysisOverview.vue";
import CompareTab from "./CompareTab.vue";
import CounterpartDialog from "./CounterpartDialog.vue";
import DataViewer from "./DataViewer.vue";
import ResultBreakdown from "./ResultBreakdown.vue";
import RunTrend from "./RunTrend.vue";
import SqlFilterDialog from "./SqlFilterDialog.vue";

const TABS = ["overview", "columns", "correlations", "missing", "duplicates", "compare", "data"];
const BREAKDOWN_COLUMNS = ["rapo_result_type", "rapo_result_value", "rapo_discrepancy_description"];

// Closes a session without waiting, also while the tab is being closed (keepalive).
function closeSession(sessionId) {
  fetch(`/api/analysis-close?session_id=${encodeURIComponent(sessionId)}`, {
    method: "POST",
    keepalive: true,
    headers: { Authorization: `Bearer ${store.getters.getToken}` },
  }).catch(() => {});
}

function parseQuery(value, fallback) {
  if (!value) {
    return fallback;
  }
  try {
    return JSON.parse(value);
  } catch (error) {
    return fallback;
  }
}

// One analysis session per page: the sample lives in a worker process on the server, and every tab asks it.
// Kept alive (App.vue), so the sample survives a visit to another page; opening another dataset, closing the
// browser tab, or [ANALYSIS] idle_minutes without a request ends the session.
// The view (tab, viewer filters, search, sort, group-by, profile scope, database filter) is kept in the URL query,
// so a copied link opens the same view on a new sample.
export default {
  name: "DataAnalysis",
  components: {
    AnalysisColumns,
    AnalysisCorrelations,
    AnalysisDuplicates,
    AnalysisMissing,
    AnalysisOverview,
    CompareTab,
    CounterpartDialog,
    DataViewer,
    ResultBreakdown,
    RunTrend,
    SqlFilterDialog,
  },
  data() {
    return {
      session: null,
      sessionKey: null,
      state: {},
      starting: false,
      startError: null,
      tab: "overview",
      // Loaded sections by the key the worker names them with; sectionKeys maps a section to its key in the scope.
      sections: {},
      sectionKeys: {},
      requested: {},
      loading: {},
      scopeId: 0,
      view: { filters: [], search: "", sort: [], group: null },
      // Filtered rows the profile tabs describe, or null for the whole sample.
      scope: null,
      // {filters, search, where} applied by the database, or null.
      pushdown: null,
      // The sample compared with (B): {target: {key, label, process_id, dataset}, session, state, error}.
      compare: { target: null, session: null, state: {}, error: null },
      compareRequest: 0,
    };
  },
  computed: {
    routeKey() {
      return `${this.$route.params.processId}/${this.$route.params.dataset}`;
    },
    fullKey() {
      return `${this.routeKey}|${this.$route.query.pd || ""}`;
    },
    meta() {
      return this.session ? this.session.meta : null;
    },
    options() {
      return (this.session && this.session.options) || {};
    },
    datasetTitle() {
      const dataset = DATASETS[this.$route.params.dataset];
      return dataset ? `${dataset.kind === "fetched" ? "Fetched" : "Discrepancies"} ${dataset.side}` : "";
    },
    windowText() {
      if (!this.meta) {
        return "";
      }
      const from = toDateTimeString(this.meta.date_from);
      const to = toDateTimeString(this.meta.date_to);
      return from.substring(0, 10) === to.substring(0, 10) && from.endsWith("00:00:00") && to.endsWith("23:59:59") ? from.substring(0, 10) : `${from} – ${to}`;
    },
    // Once the cursor is exhausted the sample is the whole dataset, whatever the run counted.
    totalRows() {
      if (this.state.exhausted) {
        return this.state.rows;
      }
      return this.meta && this.meta.total !== null && this.meta.total !== undefined ? this.meta.total : null;
    },
    pushdownText() {
      const pushdown = this.pushdown || {};
      const parts = (pushdown.filters || []).map(describeFilter);
      if (pushdown.search) {
        parts.push(`contains "${pushdown.search}"`);
      }
      if (pushdown.where) {
        parts.push(pushdown.where.replace(/\s+/g, " "));
      }
      return parts.join(" and ");
    },
    busy() {
      return ["starting", "fetching", "profiling"].includes(this.state.status);
    },
    // The session can not go on: its worker is gone, or nothing was loaded before a cancel or an error.
    ended() {
      return ["lost", "expired"].includes(this.state.status) || (["canceled", "error"].includes(this.state.status) && !this.state.version);
    },
    endedMessage() {
      switch (this.state.status) {
        case "expired":
          return "This analysis was closed after it was not used for a while, which frees the server's memory.";
        case "canceled":
          return "Loading the sample was canceled.";
        case "error":
          return `The dataset could not be read: ${this.state.error}`;
        default:
          return "The analysis worker stopped, e.g. because the server was restarted.";
      }
    },
    extendRows() {
      const left = (this.options.max_rows || 0) - (this.state.rows || 0);
      return Math.max(0, Math.min(this.options.extend_rows || 0, left));
    },
    canExtend() {
      return Boolean(this.session) && !this.busy && !this.ended && this.state.cursor_open && !this.state.exhausted && this.extendRows > 0;
    },
    progressValue() {
      const progress = this.state.progress;
      return progress && progress.total ? Math.min(1, progress.done / progress.total) : null;
    },
    progressText() {
      const progress = this.state.progress;
      if (!progress || !progress.total) {
        return "";
      }
      return this.state.status === "fetching" ? ` ${formatNumber(progress.done)} of ${formatNumber(progress.total)}` : ` ${progress.done} of ${progress.total}`;
    },
    columnKinds() {
      const kinds = {};
      (this.state.columns || []).forEach((column) => (kinds[column.name] = column.kind));
      return kinds;
    },
    hasBreakdown() {
      return (this.state.columns || []).some((column) => BREAKDOWN_COLUMNS.includes(column.name));
    },
    // The columns profile of the whole sample, for the viewer's filter menus.
    sampleColumns() {
      const section = this.sections.columns;
      return section ? section.data : null;
    },
    tabSections() {
      const sections = {
        overview: this.hasBreakdown ? ["overview", "breakdown"] : ["overview"],
        columns: ["columns"],
        correlations: ["correlations"],
        missing: ["missing"],
        duplicates: ["duplicates"],
        data: [],
      };
      return sections[this.tab] || [];
    },
    storageKey() {
      return this.meta ? `rapo_analysis_columns_${this.meta.control_name}_${this.meta.dataset}` : null;
    },
    exportName() {
      return this.meta ? `${this.meta.control_name}_${this.meta.process_id}_${this.meta.dataset}` : "data";
    },
    // The view as URL query parameters, the defaults left out.
    viewQuery() {
      const query = {};
      if (this.tab !== "overview") query.tab = this.tab;
      if (this.view.filters.length) query.f = JSON.stringify(this.view.filters);
      if (this.view.search) query.q = this.view.search;
      if (this.view.sort.length) query.s = JSON.stringify(this.view.sort);
      if (this.view.group) query.g = JSON.stringify(this.view.group);
      if (this.scope) query.sc = JSON.stringify(this.scope);
      if (this.pushdown) query.pd = JSON.stringify(this.pushdown);
      if (this.compare.target) query.cmp = JSON.stringify(this.compare.target);
      return query;
    },
  },
  watch: {
    fullKey() {
      if (this.active && this.$route.name === "data-analysis" && this.fullKey !== this.sessionKey) {
        this.start();
      }
    },
    tab() {
      this.syncSections();
    },
    scope() {
      this.scopeId += 1;
      this.sectionKeys = {};
      this.syncSections();
    },
    viewQuery(query) {
      if (!this.active || this.$route.name !== "data-analysis") {
        return;
      }
      clearTimeout(this.queryTimer);
      this.queryTimer = setTimeout(() => {
        if (JSON.stringify(query) !== JSON.stringify(this.$route.query)) {
          this.sessionKey = `${this.routeKey}|${query.pd || ""}`;
          this.$router.replace({ query });
        }
      }, 300);
    },
  },
  created() {
    this.onProgress = (payload) => {
      if (this.session && payload.session_id === this.session.session_id) {
        this.applyState(payload.state);
      } else if (this.compare.session && payload.session_id === this.compare.session.session_id) {
        this.compare.state = payload.state || {};
      }
    };
    // pagehide, unlike beforeunload, also fires when a mobile browser discards the tab.
    this.onUnload = () => {
      if (this.session) {
        closeSession(this.session.session_id);
        this.session = null;
      }
      this.closeCompare();
    };
    // A reconnect may have missed state changes.
    this.onConnect = () => this.refreshState();
    socket.on("analysis:progress", this.onProgress);
    socket.on("connect", this.onConnect);
    window.addEventListener("pagehide", this.onUnload);
  },
  activated() {
    this.active = true;
    if (this.sessionKey !== this.fullKey || !this.session) {
      this.start();
    } else {
      this.refreshState();
    }
  },
  deactivated() {
    this.active = false;
  },
  unmounted() {
    socket.off("analysis:progress", this.onProgress);
    socket.off("connect", this.onConnect);
    window.removeEventListener("pagehide", this.onUnload);
    this.onUnload();
  },
  methods: {
    controlType,
    runStatus,
    formatNumber,
    datasetLabel,
    describeFilter,
    fillViewportToBottom,
    // Starts the session of the route, with the view of its query.
    async start() {
      const query = this.$route.query;
      this.tab = TABS.includes(query.tab) ? query.tab : "overview";
      this.view = {
        filters: parseQuery(query.f, []),
        search: query.q || "",
        sort: parseQuery(query.s, []),
        group: parseQuery(query.g, null),
      };
      this.scope = parseQuery(query.sc, null);
      this.pushdown = parseQuery(query.pd, null);
      const target = parseQuery(query.cmp, null);
      await this.open();
      if (target && this.session) {
        this.startCompare(target);
      }
    },
    // Starts a new sample with another database filter, keeping the rest of the view.
    async startWith(pushdown) {
      this.pushdown = pushdown && (pushdown.filters?.length || pushdown.search || pushdown.where) ? pushdown : null;
      await this.open();
    },
    async open() {
      // The tabs are unmounted with the old session before it is closed, so nothing asks it any more.
      const previous = this.session;
      const { processId, dataset } = this.$route.params;
      const key = `${this.routeKey}|${this.pushdown ? JSON.stringify(this.pushdown) : ""}`;
      this.session = null;
      if (previous) {
        closeSession(previous.session_id);
      }
      this.closeCompare();
      this.sessionKey = key;
      this.state = {};
      this.sections = {};
      this.sectionKeys = {};
      this.requested = {};
      this.loading = {};
      this.startError = null;
      this.starting = true;
      try {
        const session = await api("analysis-start", {
          method: "POST",
          params: { process_id: processId, dataset },
          body: this.pushdown || undefined,
        });
        if (this.sessionKey !== key) {
          closeSession(session.session_id);
          return;
        }
        this.session = session;
        this.applyState(session.state);
      } catch (error) {
        this.startError = `The analysis could not be started: ${error.message}`;
      } finally {
        this.starting = false;
      }
    },
    // Starts B's session, replacing the one compared before. A counter, not the target object, tells whether the
    // answer is still wanted: Vue hands the stored target back as a reactive proxy.
    async startCompare(target) {
      this.closeCompare();
      const request = ++this.compareRequest;
      this.compare = { target, session: null, state: { status: "starting" }, error: null };
      try {
        const session = await api("analysis-start", { method: "POST", params: { process_id: target.process_id, dataset: target.dataset } });
        if (request !== this.compareRequest) {
          closeSession(session.session_id);
          return;
        }
        this.compare.session = session;
        this.compare.state = session.state;
      } catch (error) {
        if (request === this.compareRequest) {
          this.compare.error = `${target.label} could not be loaded: ${error.message}`;
          this.compare.state = {};
        }
      }
    },
    closeCompare() {
      this.compareRequest = (this.compareRequest || 0) + 1;
      if (this.compare.session) {
        closeSession(this.compare.session.session_id);
      }
      this.compare = { target: null, session: null, state: {}, error: null };
    },
    async extendCompare() {
      try {
        const result = await api("analysis-extend", { method: "POST", params: { session_id: this.compare.session.session_id }, loadingBar: false });
        this.compare.state = result.state;
      } catch (error) {
        notifyError("The sample B could not be extended.", error);
      }
    },
    applyState(state) {
      this.state = state || {};
      this.syncSections();
    },
    async refreshState() {
      if (!this.session) {
        return;
      }
      try {
        const session = await api("analysis-status", { params: { session_id: this.session.session_id }, loadingBar: false });
        this.applyState(session.state);
      } catch (error) {
        if (error.status === 404) {
          this.state = { ...this.state, status: "expired", step: null, progress: null };
        }
      }
    },
    // A section of the previous sample stays shown until the new one is ready.
    sectionData(name) {
      const key = this.sectionKeys[name] || (this.scope ? null : name);
      const section = key && this.sections[key];
      return section ? section.data : null;
    },
    // Loads the sections the open tab shows for the current sample and scope. A section not computed yet is started
    // by the request, and fetched again once the state lists its key as ready.
    syncSections() {
      if (!this.session || !this.state.version) {
        return;
      }
      this.tabSections.forEach((name) => this.ensureSection(name));
    },
    async ensureSection(name) {
      const version = this.state.version;
      const scopeId = this.scopeId;
      const key = this.sectionKeys[name];
      const have = key && this.sections[key];
      const ready = (this.state.sections || []).includes(key);
      if ((have && have.version === version) || this.loading[name] || (key && this.requested[key] === version && !ready)) {
        return;
      }
      this.loading[name] = true;
      try {
        const result = await api("analysis-profile", {
          params: {
            session_id: this.session.session_id,
            section: name,
            filters: this.scope && this.scope.filters.length ? JSON.stringify(this.scope.filters) : null,
            search: (this.scope && this.scope.search) || null,
          },
          loadingBar: false,
        });
        if (scopeId === this.scopeId) {
          this.sectionKeys = { ...this.sectionKeys, [name]: result.key };
          this.requested[result.key] = result.version;
          if (result.ready) {
            this.sections = { ...this.sections, [result.key]: { version: result.version, data: Object.freeze(result.data) } };
          }
        }
      } catch (error) {
        notifyError(`The ${name} could not be loaded.`, error);
      } finally {
        this.loading[name] = false;
      }
      const current = this.sectionKeys[name];
      const loaded = current && this.sections[current] && this.sections[current].version === this.state.version;
      if (scopeId !== this.scopeId || (!loaded && (this.state.version !== version || (this.state.sections || []).includes(current)))) {
        this.syncSections();
      }
    },
    async extend() {
      try {
        const result = await api("analysis-extend", { method: "POST", params: { session_id: this.session.session_id }, loadingBar: false });
        this.applyState(result.state);
      } catch (error) {
        notifyError("The sample could not be extended.", error);
      }
    },
    async cancel() {
      try {
        await api("analysis-cancel", { method: "POST", params: { session_id: this.session.session_id }, loadingBar: false });
      } catch (error) {
        notifyError("The step could not be canceled.", error);
      }
    },
    async copySql() {
      try {
        await copyText(this.meta.sql);
        Notify.create({ type: "positive", message: `${datasetLabel(this.meta)} SQL statement copied to clipboard` });
      } catch (error) {
        notifyError("Failed to copy SQL to clipboard.", error);
      }
    },
    async copyLink() {
      try {
        await copyText(window.location.href);
        Notify.create({ type: "positive", message: "Link to this view copied to clipboard" });
      } catch (error) {
        notifyError("Failed to copy the link.", error);
      }
    },
    // A profile link: the viewer opens on the rows it stands for.
    showRows(filters) {
      this.view.filters = filters;
      this.view.search = "";
      this.view.group = null;
      this.tab = "data";
    },
    showColumn(name) {
      this.tab = "columns";
      this.$nextTick(() => this.$refs.columns && this.$refs.columns.focus(name));
    },
    // The profile tabs describe the rows the viewer shows.
    profileRows() {
      this.scope = { filters: this.view.filters.map((filter) => ({ ...filter })), search: this.view.search || "" };
      this.tab = "overview";
    },
    // The viewer's filters and search move into the database: a new sample of the matching records only.
    pushFilters() {
      const previous = this.pushdown || {};
      const pushdown = {
        filters: [...(previous.filters || []), ...this.view.filters],
        search: this.view.search || previous.search || "",
        where: previous.where || "",
      };
      Dialog.create({
        title: "Load from the database",
        message:
          "Fetch a new sample from the records that match the filters, applied by the database. The current sample is " +
          "replaced; the filters then apply to the whole dataset instead of the rows loaded so far.",
        cancel: true,
      }).onOk(() => {
        this.view.filters = [];
        this.view.search = "";
        this.scope = null;
        this.startWith(pushdown);
      });
    },
    applyWhere(where) {
      const previous = this.pushdown || {};
      this.scope = null;
      this.startWith({ filters: previous.filters || [], search: previous.search || "", where });
    },
  },
};
</script>

<style scoped>
.analysis-subtitle {
  font-size: 0.6em;
}

.control-link {
  color: #009688;
  text-decoration: none;
}

.control-link:hover {
  text-decoration: underline;
}

.sample-bar {
  flex: 0 0 auto;
}

.busy-step {
  min-width: 200px;
}

.error-text {
  max-width: 480px;
}

.pushdown-chip {
  max-width: 520px;
}

.scope-bar {
  flex: 0 0 auto;
}

.analysis-panels {
  min-height: 0;
  background: transparent;
}

.scroll-panel {
  height: 100%;
  overflow-y: auto;
  padding: 16px 4px;
}

.data-panel {
  height: 100%;
}
</style>
