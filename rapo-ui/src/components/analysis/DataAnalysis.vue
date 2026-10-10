<template>
  <q-page>
    <analysis-header
      title="Data analysis"
      :subject="datasetLabel(meta) || datasetTitle"
      :options="datasetOptions"
      :model-value="meta ? meta.dataset : null"
      :meta="meta"
      @update:model-value="switchDataset"
      @copy-link="copyLink">
      <q-btn v-if="discrepancyLink" outline dense no-caps color="primary" icon="fas fa-search-plus" padding="4px 10px" label="Discrepancy analysis" :to="discrepancyLink">
        <q-tooltip anchor="top middle" self="bottom middle">What sets these discrepancies apart from the normal records</q-tooltip>
      </q-btn>
      <q-btn v-if="session && !isFile" aria-label="SQL filter, applied by the database" flat dense round size="sm" color="grey-7" icon="fas fa-code" @click="$refs.sqlFilter.open(pushdown && pushdown.where)">
        <q-tooltip anchor="top middle" self="bottom middle">SQL filter, applied by the database</q-tooltip>
      </q-btn>
      <q-btn v-if="meta" aria-label="Copy SQL to clipboard" flat dense round size="sm" color="grey-7" icon="fas fa-copy" @click="copySql">
        <q-tooltip anchor="top middle" self="bottom middle">Copy SQL to clipboard</q-tooltip>
      </q-btn>
    </analysis-header>

    <!-- A filter applied by the database: every section describes the matching records only. -->
    <div v-if="pushdown" class="row items-center no-wrap q-mb-md">
      <q-icon name="fas fa-database" color="blue-grey-6" size="14px" class="q-mr-sm">
        <q-tooltip anchor="top middle" self="bottom middle">Filtered in the database: the page describes only the matching records</q-tooltip>
      </q-icon>
      <filter-chips :filters="pushdownFilters" @clear="startWith(null)" />
    </div>

    <q-banner v-if="startError" class="bg-red-1 text-red-9 q-mb-md" rounded>
      <template #avatar><q-icon name="fas fa-exclamation-triangle" color="red-7" /></template>
      {{ startError }}
      <template #action>
        <q-btn v-if="pushdown" flat color="red-9" label="Without the database filter" @click="startWith(null)" />
        <q-btn flat color="red-9" label="Try again" @click="start" />
        <q-btn v-if="isFile" flat color="red-9" label="Back" @click="$router.back()" />
        <q-btn v-else flat color="red-9" label="Back to results" :to="{ name: 'results' }" />
      </template>
    </q-banner>

    <q-banner v-if="ended" class="bg-amber-1 text-brown-9 q-mb-md" rounded>
      <template #avatar><q-icon name="fas fa-hourglass-end" color="amber-9" /></template>
      {{ endedMessage }}
      <template #action>
        <q-btn flat color="brown-9" label="Start again" @click="start" />
      </template>
    </q-banner>

    <!-- The step in progress, or the last one's error. -->
    <div v-if="busy || (state.error && !ended)" class="row items-center no-wrap q-gutter-x-sm q-mb-md">
      <template v-if="busy">
        <q-spinner-dots color="primary" size="20px" />
        <div class="text-grey-8 text-no-wrap">{{ state.step || "Working" }}{{ progressText }}</div>
        <q-linear-progress v-if="progressValue !== null" class="col progress" rounded size="6px" :value="progressValue" color="primary" />
        <q-space v-else />
        <q-btn flat dense no-caps color="red-7" icon="fas fa-stop-circle" label="Cancel" :disable="!session" @click="cancel" />
      </template>
      <div v-else class="text-red-8 ellipsis" :title="state.error"><q-icon name="fas fa-exclamation-circle" /> {{ state.error }}</div>
    </div>

    <analysis-layout v-if="session" ref="layout" :sections="railSections">
      <analysis-section id="summary" title="Summary" icon="fas fa-clipboard-list">
        <analysis-summary
          :meta="meta"
          :state="state"
          :options="options"
          :overview="sectionData('overview')"
          :relations="sectionData('relations')"
          :total-rows="totalRows"
          :can-extend="canExtend"
          :extend-rows="extendRows"
          @show-rows="showRows"
          @group="groupBy"
          @go="go"
          @extend="extend" />
        <section-error :error="sectionErrors.overview || sectionErrors.relations" @retry="retrySections" />
      </analysis-section>

      <analysis-section v-if="hasBreakdown" id="result-types" title="Result types" icon="fas fa-tags">
        <result-breakdown v-if="sectionData('breakdown')" :breakdown="sectionData('breakdown')" @show-rows="showRows" />
        <q-skeleton v-else-if="!sectionErrors.breakdown" type="rect" height="64px" />
        <section-error :error="sectionErrors.breakdown" @retry="retrySections" />
      </analysis-section>

      <analysis-section id="columns" title="Columns" icon="fas fa-columns">
        <analysis-columns :columns="sectionData('columns')" :types="state.columns || []" @show-rows="showRows" />
        <section-error :error="sectionErrors.columns" @retry="retrySections" />
      </analysis-section>

      <analysis-section id="records" title="Records" icon="fas fa-table">
        <div class="column no-wrap records-body">
          <data-viewer
            class="col"
            :session-id="session.session_id"
            :columns="state.columns || []"
            :version="state.version"
            :sample-rows="state.rows"
            :view="view"
            :profiles="sectionData('columns')"
            :storage-key="storageKey"
            :key-fields="meta.key_fields || []"
            :export-name="exportName"
            :row-action="meta.control_type === 'REC' ? { icon: 'fas fa-exchange-alt', label: 'Find the counterpart on the other side' } : null"
            @pushdown="pushFilters"
            @row="(row) => $refs.counterpart.open(row)" />
        </div>
      </analysis-section>
    </analysis-layout>
    <div v-else-if="starting" class="q-pa-md">
      <q-skeleton type="rect" height="40px" class="q-mb-md" />
      <q-skeleton type="rect" height="220px" />
    </div>

    <counterpart-dialog v-if="session" ref="counterpart" :session-id="session.session_id" :columns="state.columns || []" :side="meta.side || 'A'" />
    <sql-filter-dialog v-if="meta && !isFile" ref="sqlFilter" :process-id="meta.process_id" :dataset="meta.dataset" :columns="state.columns || []" @apply="applyWhere" />
  </q-page>
</template>

<script>
import socket from "../../socket";
import { api, notifyError } from "../../api";
import { copyAndNotify } from "../../runActions";
import { formatNumber } from "../../utils/format";
import { DATASETS, closeAnalysisSession as closeSession, datasetAvatar, datasetLabel, describeFilter } from "../../utils/analysis";
import FilterChips from "../FilterChips.vue";
import AnalysisColumns from "./AnalysisColumns.vue";
import AnalysisHeader from "./AnalysisHeader.vue";
import AnalysisLayout from "./AnalysisLayout.vue";
import AnalysisSection from "./AnalysisSection.vue";
import AnalysisSummary from "./AnalysisSummary.vue";
import CounterpartDialog from "./CounterpartDialog.vue";
import DataViewer from "./DataViewer.vue";
import ResultBreakdown from "./ResultBreakdown.vue";
import SectionError from "./SectionError.vue";
import SqlFilterDialog from "./SqlFilterDialog.vue";

// The routes of this page: a run's dataset, or the records a file loaded into a table.
const ROUTES = ["data-analysis", "file-analysis"];
const BREAKDOWN_COLUMNS = ["rapo_result_type", "rapo_result_value", "rapo_discrepancy_description"];
// The sections the tabs of earlier versions stand for, so their links still open the right place.
const TAB_SECTIONS = { overview: "summary", columns: "columns", data: "records", missing: "columns", correlations: "summary", duplicates: "summary", compare: "summary" };

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

// One analysis session per page: the sample lives in a worker process on the server, and every section asks it.
// Kept alive (App.vue), so the sample survives a visit to another page; opening another dataset, closing the
// browser tab, or [ANALYSIS] idle_minutes without a request ends the session.
// One scrolling page (AnalysisLayout): Summary, Result types (a result dataset), Columns and Records. A click on a
// value anywhere filters Records and scrolls there. The view (viewer filters, search, sort, group-by, database filter,
// first rows) is kept in the URL query and the section in its hash, so a copied link opens the same view on a new
// sample.
export default {
  name: "DataAnalysis",
  components: {
    AnalysisColumns,
    AnalysisHeader,
    AnalysisLayout,
    AnalysisSection,
    AnalysisSummary,
    CounterpartDialog,
    DataViewer,
    FilterChips,
    ResultBreakdown,
    SectionError,
    SqlFilterDialog,
  },
  data() {
    return {
      session: null,
      sessionKey: null,
      state: {},
      starting: false,
      startError: null,
      // Loaded sections by name: {version, data}.
      sections: {},
      requested: {},
      loading: {},
      sectionErrors: {},
      view: { filters: [], search: "", sort: [], group: null },
      // {filters, search, where} applied by the database, or null.
      pushdown: null,
      // A random sample (or the whole dataset when it is small), or the first rows as the database returns them.
      random: true,
      // The section to scroll to once the sample is profiled (the link's hash).
      pendingSection: null,
    };
  },
  computed: {
    // The records of a file (file-analysis) rather than a run's dataset: no other datasets, trend or SQL filter, and
    // the first rows by default.
    isFile() {
      return this.$route.name === "file-analysis";
    },
    routeKey() {
      const params = this.$route.params;
      return this.isFile ? `file/${params.fileId}/${params.table}` : `${params.processId}/${params.dataset}`;
    },
    // The route and the parts of the query that need a new sample: the database filter and the sampling.
    fullKey() {
      return `${this.routeKey}|${this.$route.query.pd || ""}|${this.$route.query.rnd || ""}`;
    },
    // The datasets of the run the page can switch to, with the run's counts; an empty one is left out.
    datasetOptions() {
      if (!this.meta || !this.meta.datasets) {
        return [];
      }
      return this.meta.datasets.map((item) => {
        const meta = { control_type: this.meta.control_type, kind: item.kind, side: item.side };
        const count = item.count === null || item.count === undefined ? "" : formatNumber(item.count);
        return { ...datasetAvatar(meta), text: datasetLabel(meta), count, value: item.dataset, hidden: !item.count };
      });
    },
    meta() {
      return this.session ? this.session.meta : null;
    },
    options() {
      return (this.session && this.session.options) || {};
    },
    datasetTitle() {
      if (this.isFile) {
        return this.$route.params.table;
      }
      const dataset = DATASETS[this.$route.params.dataset];
      return dataset ? `${dataset.kind === "fetched" ? "Fetched" : "Discrepancies"} ${dataset.side}` : "";
    },
    // The discrepancy analysis of the same side, from a discrepancies dataset (not a report's rows).
    discrepancyLink() {
      const meta = this.meta;
      if (!meta || meta.kind !== "result" || meta.control_type === "REP") {
        return null;
      }
      const side = meta.control_type === "REC" ? meta.dataset.split("_")[1] : "a";
      return { name: "discrepancy-analysis", params: { processId: meta.process_id, side } };
    },
    // Once the dataset is read whole, the sample is the whole dataset, whatever the run counted.
    totalRows() {
      if (this.state.exhausted) {
        return this.state.rows;
      }
      return this.meta && this.meta.total !== null && this.meta.total !== undefined ? this.meta.total : null;
    },
    pushdownFilters() {
      const pushdown = this.pushdown || {};
      const filters = (pushdown.filters || []).map((filter, index) => ({
        key: `f${index}`,
        label: describeFilter(filter),
        clear: () => this.startWith({ ...pushdown, filters: pushdown.filters.filter((item, position) => position !== index) }),
      }));
      if (pushdown.search) {
        filters.push({ key: "search", label: `Search: "${pushdown.search}"`, clear: () => this.startWith({ ...pushdown, search: "" }) });
      }
      if (pushdown.where) {
        filters.push({ key: "where", label: pushdown.where.replace(/\s+/g, " "), clear: () => this.startWith({ ...pushdown, where: "" }) });
      }
      return filters;
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
    // The records Extend adds; a Bernoulli sample grows from the size it was drawn for.
    extendRows() {
      const loaded = this.state.sampling === "bernoulli" ? this.state.target || this.state.rows || 0 : this.state.rows || 0;
      const left = (this.options.max_rows || 0) - loaded;
      return Math.max(0, Math.min(this.options.extend_rows || 0, left));
    },
    canExtend() {
      return Boolean(this.session) && !this.busy && !this.ended && Boolean(this.state.extendable) && this.extendRows > 0;
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
    hasBreakdown() {
      return (this.state.columns || []).some((column) => BREAKDOWN_COLUMNS.includes(column.name));
    },
    wantedSections() {
      return this.hasBreakdown ? ["columns", "overview", "relations", "breakdown"] : ["columns", "overview", "relations"];
    },
    railSections() {
      const sections = [{ id: "summary", label: "Summary", icon: "fas fa-clipboard-list" }];
      if (this.hasBreakdown) {
        sections.push({ id: "result-types", label: "Result types", icon: "fas fa-tags" });
      }
      sections.push({ id: "columns", label: "Columns", icon: "fas fa-columns" });
      sections.push({ id: "records", label: "Records", icon: "fas fa-table" });
      return sections;
    },
    storageKey() {
      if (!this.meta) {
        return null;
      }
      // The file viewer's records pane keeps the columns of a table under the same key.
      return this.meta.kind === "file" ? `rapo_analysis_columns_file_${this.meta.table_name}` : `rapo_analysis_columns_${this.meta.control_name}_${this.meta.dataset}`;
    },
    exportName() {
      if (!this.meta) {
        return "data";
      }
      return this.meta.export_name || `${this.meta.control_name}_${this.meta.process_id}_${this.meta.dataset}`;
    },
    // The view as URL query parameters, the defaults left out.
    viewQuery() {
      const query = {};
      if (this.view.filters.length) query.f = JSON.stringify(this.view.filters);
      if (this.view.search) query.q = this.view.search;
      if (this.view.sort.length) query.s = JSON.stringify(this.view.sort);
      if (this.view.group) query.g = JSON.stringify(this.view.group);
      if (this.pushdown) query.pd = JSON.stringify(this.pushdown);
      if (this.random !== !this.isFile) query.rnd = this.random ? "1" : "0";
      return query;
    },
  },
  watch: {
    fullKey() {
      if (this.active && ROUTES.includes(this.$route.name) && this.fullKey !== this.sessionKey) {
        this.start();
      }
    },
    viewQuery(query) {
      if (!this.active || !ROUTES.includes(this.$route.name)) {
        return;
      }
      clearTimeout(this.queryTimer);
      this.queryTimer = setTimeout(() => {
        if (JSON.stringify(query) !== JSON.stringify(this.$route.query)) {
          this.sessionKey = `${this.routeKey}|${query.pd || ""}|${query.rnd || ""}`;
          this.$router.replace({ query, hash: this.$route.hash });
        }
      }, 300);
    },
  },
  created() {
    this.onProgress = (payload) => {
      if (this.session && payload.session_id === this.session.session_id) {
        this.applyState(payload.state);
      }
    };
    // pagehide, unlike beforeunload, also fires when a mobile browser discards the tab.
    this.onUnload = () => {
      if (this.session) {
        closeSession(this.session.session_id);
        this.session = null;
      }
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
    formatNumber,
    datasetLabel,
    // Starts the session of the route, with the view of its query.
    async start() {
      const query = this.$route.query;
      this.view = {
        filters: parseQuery(query.f, []),
        search: query.q || "",
        sort: parseQuery(query.s, []),
        group: parseQuery(query.g, null),
      };
      this.pushdown = parseQuery(query.pd, null);
      this.random = query.rnd ? query.rnd !== "0" : !this.isFile;
      const hash = (this.$route.hash || "").replace(/^#/, "");
      this.pendingSection = hash || TAB_SECTIONS[query.tab] || null;
      if (query.tab) {
        const rest = { ...query };
        delete rest.tab;
        this.$router.replace({ query: rest, hash: this.pendingSection ? `#${this.pendingSection}` : "" });
      }
      await this.open();
    },
    // Opens another dataset of the run. Back returns to this one. The sampling, the search and the viewer's filters,
    // sort and group-by go along; those on a column the other dataset lacks are dropped once it is loaded. A database
    // filter belongs to this dataset.
    switchDataset(dataset) {
      if (!this.meta || dataset === this.meta.dataset) {
        return;
      }
      const query = { ...this.viewQuery };
      delete query.pd;
      this.$router.push({ name: "data-analysis", params: { processId: this.meta.process_id, dataset }, query, hash: this.$route.hash });
    },
    // Starts a new sample with another database filter, keeping the rest of the view.
    async startWith(pushdown) {
      this.pushdown = pushdown && (pushdown.filters?.length || pushdown.search || pushdown.where) ? pushdown : null;
      await this.open();
    },
    async open() {
      // The sections are unmounted with the old session before it is closed, so nothing asks it any more.
      const previous = this.session;
      const { processId, dataset, fileId, table } = this.$route.params;
      const rnd = this.random === !this.isFile ? "" : this.random ? "1" : "0";
      const key = `${this.routeKey}|${this.pushdown ? JSON.stringify(this.pushdown) : ""}|${rnd}`;
      this.session = null;
      if (previous) {
        closeSession(previous.session_id);
      }
      this.sessionKey = key;
      this.state = {};
      this.sections = {};
      this.requested = {};
      this.sectionErrors = {};
      this.loading = {};
      this.startError = null;
      this.starting = true;
      try {
        const session = this.isFile
          ? await api("analysis-start-file", {
              method: "POST",
              params: { file_id: fileId, table, random: this.random },
              body: this.pushdown || undefined,
            })
          : await api("analysis-start", {
              method: "POST",
              params: { process_id: processId, dataset, random: this.random },
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
    applyState(state) {
      this.state = state || {};
      this.pruneView();
      this.syncSections();
    },
    // Drops the viewer's filters, sort and group-by on columns the dataset does not have, e.g. carried over from
    // the other side.
    pruneView() {
      const columns = this.state.columns;
      if (!columns || !columns.length) {
        return;
      }
      const names = new Set(columns.map((column) => column.name));
      const known = (item) => !item.column || names.has(item.column);
      const filters = this.view.filters.filter(known);
      const sort = this.view.sort.filter(known);
      let group = this.view.group;
      if (group) {
        const by = (group.by || []).filter(known);
        group = by.length ? { ...group, by, aggregates: (group.aggregates || []).filter(known) } : null;
      }
      if (filters.length !== this.view.filters.length) {
        this.view.filters = filters;
      }
      if (sort.length !== this.view.sort.length) {
        this.view.sort = sort;
      }
      if (JSON.stringify(group) !== JSON.stringify(this.view.group)) {
        this.view.group = group;
      }
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
      const section = this.sections[name];
      return section ? section.data : null;
    },
    retrySections() {
      this.sectionErrors = {};
      this.syncSections();
    },
    // Loads the sections of the current sample. One not computed yet is started by the request, and fetched again
    // once the state lists it as ready.
    syncSections() {
      if (!this.session || !this.state.version) {
        return;
      }
      this.wantedSections.forEach((name) => this.ensureSection(name));
    },
    async ensureSection(name) {
      const version = this.state.version;
      const have = this.sections[name];
      const ready = (this.state.sections || []).includes(name);
      if ((have && have.version === version) || this.loading[name] || this.sectionErrors[name] || (this.requested[name] === version && !ready)) {
        return;
      }
      this.loading[name] = true;
      try {
        const result = await api("analysis-profile", { params: { session_id: this.session.session_id, section: name }, loadingBar: false });
        this.requested[name] = result.version;
        if (result.ready) {
          this.sections = { ...this.sections, [name]: { version: result.version, data: Object.freeze(result.data) } };
          if (name === "columns") {
            this.scrollToPending();
          }
        }
      } catch (error) {
        this.sectionErrors = { ...this.sectionErrors, [name]: error.message };
        notifyError(`The ${name} could not be loaded.`, error);
      } finally {
        this.loading[name] = false;
      }
      const loaded = this.sections[name] && this.sections[name].version === this.state.version;
      if (!loaded && !this.sectionErrors[name] && (this.state.version !== version || (this.state.sections || []).includes(name))) {
        this.syncSections();
      }
    },
    // The section of the link, once the columns (the tallest section above Records) are drawn.
    scrollToPending() {
      const section = this.pendingSection;
      if (!section) {
        return;
      }
      this.pendingSection = null;
      setTimeout(() => this.$refs.layout && this.$refs.layout.scrollTo(section, false), 50);
    },
    go(section) {
      if (this.$refs.layout) {
        this.$refs.layout.go(section);
      }
    },
    async extend() {
      try {
        const result = await api("analysis-extend", { method: "POST", params: { session_id: this.session.session_id, rows: this.extendRows || null }, loadingBar: false });
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
      await copyAndNotify(this.meta.sql, `${datasetLabel(this.meta)} SQL statement`, "Failed to copy SQL to clipboard.");
    },
    async copyLink() {
      await copyAndNotify(window.location.href, "Link to this view", "Failed to copy the link.");
    },
    // A value, bar or chip of a section: Records shows the rows it stands for.
    showRows(filters) {
      this.view.filters = filters;
      this.view.search = "";
      this.view.group = null;
      this.$nextTick(() => this.go("records"));
    },
    // A relation of two columns: Records grouped by both.
    groupBy(pair) {
      this.view.filters = [];
      this.view.search = "";
      this.view.group = { by: [{ column: pair.a }, { column: pair.b }], aggregates: [], sort: null };
      this.$nextTick(() => this.go("records"));
    },
    // The viewer's filters and search move into the database: a new sample of the matching records only.
    pushFilters() {
      const previous = this.pushdown || {};
      const pushdown = {
        filters: [...(previous.filters || []), ...this.view.filters],
        search: this.view.search || previous.search || "",
        where: previous.where || "",
      };
      this.$q.dialog({
        title: "Filter in the database",
        message:
          "Load a new sample from the records that match the filters, applied by the database. The current sample is " +
          "replaced, and the whole page then describes the matching records of the dataset, not only the ones loaded so far.",
        cancel: true,
      }).onOk(() => {
        this.view.filters = [];
        this.view.search = "";
        this.startWith(pushdown);
      });
    },
    applyWhere(where) {
      const previous = this.pushdown || {};
      this.startWith({ filters: previous.filters || [], search: previous.search || "", where });
    },
  },
};
</script>

<style scoped>
.progress {
  max-width: 480px;
}

/* One window tall, so Records fills the screen once a link scrolls it to the top. */
.records-body {
  height: calc(100vh - 136px);
  min-height: 420px;
}
</style>
