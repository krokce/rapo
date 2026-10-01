<template>
  <q-page class="column no-wrap" :style-fn="fillViewportToBottom">
    <analysis-header
      title="Discrepancy analysis"
      :subject="subject"
      :options="sideOptions"
      :model-value="$route.params.side"
      :meta="meta"
      @update:model-value="switchSide"
      @copy-link="copyLink">
      <q-btn v-if="meta" flat dense no-caps color="primary" icon="fas fa-chart-bar" label="Data analysis" :to="dataLink()">
        <q-tooltip anchor="top middle" self="bottom middle">Profile these discrepancies record by record</q-tooltip>
      </q-btn>
    </analysis-header>

    <q-banner v-if="startError" class="bg-red-1 text-red-9 q-mb-md" rounded>
      <template #avatar><q-icon name="fas fa-exclamation-triangle" color="red-7" /></template>
      {{ startError }}
      <template #action>
        <q-btn flat color="red-9" label="Try again" @click="start(false)" />
        <q-btn flat color="red-9" label="Back to results" :to="{ name: 'results' }" />
      </template>
    </q-banner>

    <q-banner v-if="job && job.state === 'error'" class="bg-amber-1 text-brown-9 q-mb-md" rounded>
      <template #avatar><q-icon name="fas fa-hourglass-end" color="amber-9" /></template>
      The discrepancies could not be analysed: {{ job.error }}
      <template #action>
        <q-btn flat color="brown-9" label="Start again" @click="start(true)" />
      </template>
    </q-banner>

    <q-banner v-if="meta && (meta.stopped || meta.refine_error)" dense class="bg-amber-1 text-brown-9 q-mb-md" rounded>
      <template #avatar><q-icon name="fas fa-hourglass-half" color="amber-9" /></template>
      {{ meta.stopped ? "Refining was stopped" : `Refining failed: ${meta.refine_error}` }}. These are the preliminary results of the quick look.
      <template #action>
        <q-btn flat color="brown-9" label="Refine again" @click="start(true)" />
      </template>
    </q-banner>

    <q-banner v-if="meta && meta.stale" dense class="bg-orange-1 text-orange-10 q-mb-md" rounded>
      <template #avatar><q-icon name="fas fa-history" color="orange-8" /></template>
      The control was changed after this run. The fetched records are selected with its current configuration for the run's window, so they may
      differ from what the run fetched.
    </q-banner>

    <!-- The job: what is contrasted, the step in progress, the result type and Recompute. -->
    <q-card v-if="(job && job.state !== 'error') || starting" flat bordered class="q-mb-md job-bar">
      <q-card-section class="row items-center q-py-sm q-gutter-x-md">
        <q-icon name="fas fa-search-plus" color="blue-grey-6" size="18px" />
        <div class="text-blue-grey-9">
          <template v-if="meta">
            <strong>{{ formatNumber(meta.discrepancies) }}</strong> discrepancies vs <strong>{{ formatNumber(meta.normal) }}</strong> normal records
            <span class="text-grey-7">of {{ formatNumber(meta.fetched_total) }} fetched</span>
          </template>
          <template v-else>Analysing the discrepancies…</template>
        </div>
        <q-btn-toggle
          v-if="typeOptions.length"
          :model-value="resultType"
          dense
          no-caps
          unelevated
          toggle-color="blue-grey-7"
          color="grey-3"
          text-color="grey-8"
          :disable="busy"
          title="Analyse every discrepancy, or the records of one result type"
          :options="typeOptions"
          @update:model-value="setResultType" />
        <q-chip v-if="meta && meta.stage === 'quick'" dense color="amber-1" text-color="brown-9" icon="fas fa-bolt">
          Preliminary: {{ formatNumber(meta.sample_rows) }} records read{{ meta.sample_method === "first" ? ", not a random sample" : "" }}
          <q-tooltip anchor="top middle" self="bottom middle">
            A quick look at {{ sampleText(meta.sample_method) }} of the fetched records, scaled to the run's totals. Refining counts the bins
            again with all records, or a random sample of [ANALYSIS] discrepancy_exact_rows, and replaces these results.
          </q-tooltip>
        </q-chip>
        <q-chip v-else-if="meta && meta.sample" dense color="amber-1" text-color="brown-9" icon="fas fa-percentage">
          Fetched records counted on a {{ formatPct(meta.sample * 100) }} sample
          <q-tooltip anchor="top middle" self="bottom middle">
            The fetched records exceed [ANALYSIS] discrepancy_exact_rows, so they were counted on a random sample and scaled up.
          </q-tooltip>
        </q-chip>
        <q-chip v-if="meta && meta.drift" dense color="amber-1" text-color="brown-9" icon="fas fa-exchange-alt">
          Fetched now {{ formatNumber(meta.fetched_total) }}, at run time {{ formatNumber(meta.fetched_logged) }}
        </q-chip>
        <div v-if="busy" class="col row items-center no-wrap q-gutter-x-sm busy-step">
          <q-spinner-dots color="primary" size="20px" />
          <div class="text-grey-8 ellipsis" :title="job && job.progress ? job.progress.step : ''">{{ (job && job.progress && job.progress.step) || (job && job.state === "queued" ? "Waiting for another analysis to end" : "Starting") }}</div>
          <q-linear-progress v-if="progressValue !== null" class="col" rounded size="6px" :value="progressValue" color="primary" />
        </div>
        <q-space v-else />
        <q-btn v-if="busy && report" flat dense no-caps color="red-7" icon="fas fa-stop-circle" label="Stop refining" @click="stop">
          <q-tooltip anchor="top middle" self="bottom middle">Keep the preliminary results and free the database</q-tooltip>
        </q-btn>
        <q-btn v-if="!busy" outline dense no-caps class="q-px-sm" color="primary" icon="fas fa-redo" label="Recompute" :disable="!job" @click="start(true)">
          <q-tooltip anchor="top middle" self="bottom middle">
            Count the records again, e.g. after the source data changed<template v-if="job && job.finished"> (analysed {{ toDateTimeString(job.finished) }})</template>
          </q-tooltip>
        </q-btn>
      </q-card-section>
    </q-card>

    <template v-if="report">
      <q-tabs v-model="tab" dense inline-label align="left" class="text-blue-grey-8" active-color="primary" indicator-color="primary" no-caps>
        <q-tab name="summary" icon="fas fa-book-open" label="Summary" />
        <q-tab name="drivers" icon="fas fa-bullseye" label="Attributes">
          <q-badge v-if="driverCount" color="red-7" floating>{{ driverCount }}</q-badge>
        </q-tab>
        <q-tab name="combinations" icon="fas fa-link" label="Combinations">
          <q-badge v-if="report.combinations.length" color="red-7" floating>{{ report.combinations.length }}</q-badge>
        </q-tab>
        <q-tab v-if="report.heatmaps.length" name="time" icon="fas fa-clock" label="Time bands" />
        <q-tab v-if="report.magnitude" name="differences" icon="fas fa-ruler-horizontal" label="Differences" />
        <q-tab name="records" icon="fas fa-table" label="Records" />
        <q-tab name="excluded" icon="fas fa-eye-slash" label="Not analysed">
          <q-badge v-if="meta.excluded.length" color="blue-grey-5" floating>{{ meta.excluded.length }}</q-badge>
        </q-tab>
      </q-tabs>
      <q-separator />
      <q-tab-panels v-model="tab" class="col analysis-panels" keep-alive>
        <q-tab-panel name="summary" class="scroll-panel">
          <discrepancy-summary :report="report" @show-attribute="showAttribute" @show-rows="showRows" @result-type="setResultType" />
        </q-tab-panel>
        <q-tab-panel name="drivers" class="scroll-panel">
          <discrepancy-drivers :report="report" :selected-id="attribute" @select="selectAttribute" @show-rows="showRows" />
        </q-tab-panel>
        <q-tab-panel name="combinations" class="scroll-panel">
          <discrepancy-combinations :report="report" @show-attribute="showAttribute" @show-rows="showRows" />
        </q-tab-panel>
        <q-tab-panel v-if="report.heatmaps.length" name="time" class="scroll-panel">
          <discrepancy-time-bands :report="report" />
        </q-tab-panel>
        <q-tab-panel v-if="report.magnitude" name="differences" class="scroll-panel">
          <discrepancy-magnitude :magnitude="report.magnitude" />
        </q-tab-panel>
        <q-tab-panel name="records" class="scroll-panel">
          <discrepancy-records :report="report" @show-rows="showRows" />
        </q-tab-panel>
        <q-tab-panel name="excluded" class="scroll-panel">
          <div class="text-caption text-grey-7 q-mb-sm">
            Columns of the discrepancies left out: constant or empty in the fetched records, unique per record without a prefix or length that groups
            them, of a type that can not be grouped, or not traced back to a fetched column (not listed).
          </div>
          <q-markup-table v-if="meta.excluded.length" dense flat bordered class="excluded-table">
            <thead>
              <tr class="bg-blue-grey-2">
                <th title="The column of the discrepancies" class="text-left">Column</th>
                <th title="Why it is not analysed" class="text-left">Reason</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in meta.excluded" :key="item.column">
                <td class="text-weight-medium">{{ item.column }}</td>
                <td class="text-grey-8">{{ item.reason }}</td>
              </tr>
            </tbody>
          </q-markup-table>
          <div v-else class="state-notice">
            <q-icon name="fas fa-check" />
            <div>Every column was analysed.</div>
          </div>
        </q-tab-panel>
      </q-tab-panels>
    </template>
    <div v-else-if="busy || starting" class="col q-pa-md">
      <q-skeleton type="rect" height="40px" class="q-mb-md" />
      <q-skeleton type="rect" height="220px" />
    </div>
  </q-page>
</template>

<script>
import socket from "../../socket";
import { api, notifyError } from "../../api";
import { copyAndNotify } from "../../runActions";
import { formatNumber, toDateTimeString } from "../../utils/format";
import { fillViewportToBottom } from "../../utils/layout";
import { formatPct } from "../../utils/analysis";
import AnalysisHeader from "./AnalysisHeader.vue";
import DiscrepancyCombinations from "./DiscrepancyCombinations.vue";
import DiscrepancyDrivers from "./DiscrepancyDrivers.vue";
import DiscrepancyMagnitude from "./DiscrepancyMagnitude.vue";
import DiscrepancyRecords from "./DiscrepancyRecords.vue";
import DiscrepancySummary from "./DiscrepancySummary.vue";
import DiscrepancyTimeBands from "./DiscrepancyTimeBands.vue";

const TABS = ["summary", "drivers", "combinations", "time", "differences", "records", "excluded"];
const RESULT_TYPES = ["Loss", "Discrepancy", "Duplicate"];

// What sets the discrepancies of one side of a run apart from its normal records (fetched less discrepancies). The
// server counts every attribute's bins in both datasets and scores them in a job of its own; the report is kept in its
// memory, so reopening is instant until Recompute or a restart. A quick look at a sample is shown as soon as it is
// ready, marked preliminary, while refining counts the bins again. Besides single attributes it shows pairs of them, the
// differences of REC value discrepancies and example records. Kept alive (App.vue);
// the tab, the result type and the chosen attribute are kept in the URL query (`tab`, `t`, `attr`).
export default {
  name: "DiscrepancyAnalysis",
  components: {
    AnalysisHeader,
    DiscrepancyCombinations,
    DiscrepancyDrivers,
    DiscrepancyMagnitude,
    DiscrepancyRecords,
    DiscrepancySummary,
    DiscrepancyTimeBands,
  },
  data() {
    return {
      job: null,
      jobKey: null,
      starting: false,
      startError: null,
      tab: "summary",
      resultType: null,
      attribute: null,
      // The sides of the last report, kept while another side or result type is analysed.
      sides: [],
      controlType: null,
      typeSplit: null,
    };
  },
  computed: {
    routeKey() {
      return `${this.$route.params.processId}/${this.$route.params.side}|${this.$route.query.t || ""}`;
    },
    // The refined report, or the quick look's while refining.
    report() {
      return this.job && ["running", "done"].includes(this.job.state) ? this.job.report || null : null;
    },
    meta() {
      return this.report ? this.report.meta : null;
    },
    busy() {
      return Boolean(this.job) && ["queued", "running"].includes(this.job.state);
    },
    subject() {
      return `Discrepancies ${(this.$route.params.side || "").toUpperCase()}`;
    },
    // The sides of the run with their discrepancy counts; one side (ANL) shows as a plain subject.
    sideOptions() {
      if (this.sides.length < 2) {
        return [];
      }
      return this.sides.map((item) => ({
        text: `Discrepancies ${item.side}`,
        count: item.count === null || item.count === undefined ? "" : formatNumber(item.count),
        slot: `side-${item.side}`,
        value: item.side.toLowerCase(),
        disable: !item.count && item.side.toLowerCase() !== this.$route.params.side,
      }));
    },
    typeOptions() {
      if (this.controlType !== "REC") {
        return [];
      }
      // The types the run saved, once a report told them.
      const present = this.typeSplit && this.typeSplit.map((item) => item.type);
      const disable = (type) => Boolean(present) && !present.includes(type) && type !== this.resultType;
      return [{ label: "All", value: null }, ...RESULT_TYPES.map((type) => ({ label: type, value: type, disable: disable(type) }))];
    },
    progressValue() {
      const progress = this.job && this.job.progress;
      return progress && progress.total ? Math.min(1, progress.done / progress.total) : null;
    },
    driverCount() {
      const columns = new Set(this.report.attributes.filter((item) => item.special.length).map((item) => item.column));
      return columns.size;
    },
    viewQuery() {
      const query = {};
      if (this.tab !== "summary") query.tab = this.tab;
      if (this.resultType) query.t = this.resultType;
      if (this.attribute) query.attr = this.attribute;
      return query;
    },
  },
  watch: {
    routeKey() {
      if (this.active && this.$route.name === "discrepancy-analysis" && this.routeKey !== this.jobKey) {
        this.load();
      }
    },
    viewQuery(query) {
      if (!this.active || this.$route.name !== "discrepancy-analysis") {
        return;
      }
      if (JSON.stringify(query) !== JSON.stringify(this.$route.query)) {
        this.jobKey = `${this.$route.params.processId}/${this.$route.params.side}|${query.t || ""}`;
        this.$router.replace({ query });
      }
    },
  },
  created() {
    this.onProgress = (payload) => {
      if (!this.job || !this.matches(payload)) {
        return;
      }
      const stage = this.job.report ? this.job.report.meta.stage : null;
      if (payload.state === "done" || payload.state === "error" || (payload.has_report && payload.stage !== stage)) {
        this.refresh();
      } else {
        this.job = { ...this.job, ...payload };
      }
    };
    // A reconnect may have missed the end of the job.
    this.onConnect = () => this.job && this.busy && this.refresh();
    socket.on("discrepancy:progress", this.onProgress);
    socket.on("connect", this.onConnect);
  },
  activated() {
    this.active = true;
    if (this.jobKey !== this.routeKey || !this.job) {
      this.load();
    } else if (this.busy) {
      this.refresh();
    }
  },
  deactivated() {
    this.active = false;
  },
  unmounted() {
    socket.off("discrepancy:progress", this.onProgress);
    socket.off("connect", this.onConnect);
  },
  methods: {
    formatNumber,
    formatPct,
    toDateTimeString,
    fillViewportToBottom,
    // Reads the view of the route's query and asks for its job.
    load() {
      const query = this.$route.query;
      this.tab = TABS.includes(query.tab) ? query.tab : "summary";
      this.resultType = RESULT_TYPES.includes(query.t) ? query.t : null;
      this.attribute = query.attr || null;
      this.start(false);
    },
    params() {
      const params = { process_id: this.$route.params.processId, side: this.$route.params.side };
      if (this.resultType) {
        params.result_type = this.resultType;
      }
      return params;
    },
    matches(payload) {
      const params = this.params();
      return String(payload.process_id) === String(params.process_id) && payload.side === params.side && (payload.result_type || null) === (params.result_type || null);
    },
    // Starts the job of the view, or gets the one the server holds; `recompute` replaces a finished one.
    async start(recompute) {
      const key = this.routeKey.replace(/\|.*$/, `|${this.resultType || ""}`);
      this.jobKey = key;
      this.startError = null;
      this.starting = true;
      if (!recompute) {
        this.job = null;
      }
      try {
        const job = await api("start-discrepancy-analysis", { method: "POST", params: { ...this.params(), recompute } });
        if (this.jobKey !== key) {
          return;
        }
        this.apply(job);
      } catch (error) {
        if (this.jobKey === key) {
          this.startError = `The discrepancy analysis could not be started: ${error.message}`;
        }
      } finally {
        this.starting = false;
      }
    },
    async refresh() {
      const key = this.jobKey;
      try {
        const job = await api("get-discrepancy-analysis", { params: this.params(), loadingBar: false });
        if (this.jobKey === key) {
          this.apply(job);
        }
      } catch (error) {
        // The job is gone (a server restart): start it again.
        if (this.jobKey === key) {
          this.start(false);
        }
      }
    },
    apply(job) {
      this.job = job;
      const report = job.report;
      if (report) {
        this.sides = report.meta.datasets || [];
        this.controlType = report.meta.control_type;
        if (!report.meta.result_type) {
          this.typeSplit = report.type_split;
        }
        if (this.attribute && !report.attributes.some((item) => item.id === this.attribute)) {
          this.attribute = null;
        }
        if ((this.tab === "time" && !report.heatmaps.length) || (this.tab === "differences" && !report.magnitude)) {
          this.tab = "summary";
        }
      }
    },
    switchSide(side) {
      if (side !== this.$route.params.side) {
        const query = { ...this.viewQuery };
        delete query.attr;
        this.$router.push({ name: "discrepancy-analysis", params: { processId: this.$route.params.processId, side }, query });
      }
    },
    setResultType(type) {
      if (type !== this.resultType) {
        this.resultType = type;
        this.attribute = null;
        this.start(false);
      }
    },
    showAttribute(id) {
      this.attribute = id;
      this.tab = "drivers";
    },
    // Ends refining; the job finishes with the preliminary report.
    async stop() {
      try {
        await api("stop-discrepancy-analysis", { method: "POST", params: this.params() });
      } catch (error) {
        notifyError("The analysis could not be stopped", error);
      }
    },
    sampleText(method) {
      return { block: "random blocks", first: "the first records" }[method] || "all";
    },
    selectAttribute(id) {
      this.attribute = id;
    },
    // Data analysis of the discrepancies (or the fetched records) matching a condition, filtered by the database.
    dataLink(where = null, fetched = false) {
      const meta = this.meta;
      const conditions = [];
      if (where) {
        conditions.push(where);
      }
      if (!fetched && meta && meta.result_type) {
        conditions.push(`RAPO_RESULT_TYPE = '${meta.result_type}'`);
      }
      const query = conditions.length ? { pd: JSON.stringify({ where: conditions.length > 1 ? conditions.map((item) => `(${item})`).join(" and ") : conditions[0] }) } : {};
      const dataset = fetched ? meta.fetched_dataset : meta ? meta.dataset : `result_${this.$route.params.side}`;
      return { name: "data-analysis", params: { processId: this.$route.params.processId, dataset }, query };
    },
    // `filters` are bins' filters ({result, fetched}), any of which selects a record.
    showRows({ filters, fetched }) {
      const conditions = filters.map((item) => (fetched ? item.fetched : item.result)).filter(Boolean);
      if (!conditions.length) {
        return;
      }
      const where = conditions.length > 1 ? conditions.map((item) => `(${item})`).join(" or ") : conditions[0];
      this.$router.push(this.dataLink(conditions.length > 1 ? `(${where})` : where, fetched));
    },
    async copyLink() {
      await copyAndNotify(window.location.href, "Link to this view", "Failed to copy the link.");
    },
  },
};
</script>

<style scoped>
.job-bar {
  flex: 0 0 auto;
}

.busy-step {
  min-width: 200px;
  overflow: hidden;
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

.excluded-table {
  max-width: 900px;
}
</style>
