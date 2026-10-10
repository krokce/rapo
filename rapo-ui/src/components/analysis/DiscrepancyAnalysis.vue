<template>
  <q-page>
    <analysis-header title="Discrepancy analysis" :subject="subject" :options="sideOptions" :model-value="$route.params.side" :meta="meta" @update:model-value="switchSide" @copy-link="copyLink">
      <q-btn v-if="meta" outline dense no-caps color="primary" icon="fas fa-chart-bar" padding="4px 10px" label="Data analysis" :to="dataLink()">
        <q-tooltip anchor="top middle" self="bottom middle">Profile these discrepancies record by record</q-tooltip>
      </q-btn>
      <q-btn v-if="job && !busy" outline dense no-caps color="primary" icon="fas fa-redo" padding="4px 10px" label="Recompute" @click="start(true)">
        <q-tooltip anchor="top middle" self="bottom middle">
          Count the records again, e.g. after the source data changed<template v-if="job.finished"> (counted {{ toDateTimeString(job.finished) }})</template>
        </q-tooltip>
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

    <!-- The step in progress. -->
    <div v-if="busy || starting" class="row items-center no-wrap q-gutter-x-sm q-mb-md">
      <q-spinner-dots color="primary" size="20px" />
      <div class="text-grey-8 ellipsis" :title="stepText">{{ stepText }}</div>
      <q-linear-progress v-if="progressValue !== null" class="col progress" rounded size="6px" :value="progressValue" color="primary" />
      <q-space v-else />
      <q-btn v-if="busy && report" flat dense no-caps color="red-7" icon="fas fa-stop-circle" label="Stop refining" @click="stop">
        <q-tooltip anchor="top middle" self="bottom middle">Keep the preliminary results and free the database</q-tooltip>
      </q-btn>
    </div>

    <analysis-layout v-if="report" ref="layout" :sections="railSections">
      <analysis-section id="summary" title="Summary" icon="fas fa-clipboard-list">
        <discrepancy-summary :report="report" :result-type="resultType" :type-split="typeSplit" @result-type="setResultType" @open-attribute="openAttribute" @records="showFinding" />
      </analysis-section>
      <analysis-section v-if="report.attributes.length" id="attributes" title="Attributes" icon="fas fa-bullseye">
        <discrepancy-attributes ref="attributes" :report="report" :expanded="attribute" @expand="(id) => (attribute = id)" @show-rows="showRows" />
      </analysis-section>
      <analysis-section v-if="report.magnitude" id="differences" title="Differences" icon="fas fa-ruler-horizontal">
        <template #facts>value discrepancies by field</template>
        <discrepancy-magnitude :magnitude="report.magnitude" />
      </analysis-section>
      <div v-if="meta.excluded.length" class="text-caption text-grey-7 q-mb-lg">
        <q-icon name="fas fa-eye-slash" class="q-mr-xs" />{{ meta.excluded.length }} {{ meta.excluded.length === 1 ? "column" : "columns" }} not analysed:
        <span v-for="(item, index) in shownExcluded" :key="item.column">
          <span class="text-weight-medium text-blue-grey-8" :title="item.reason">{{ item.column }}</span><span v-if="index < shownExcluded.length - 1">, </span>
        </span>
        <span v-if="meta.excluded.length > shownExcluded.length" :title="meta.excluded.slice(shownExcluded.length).map((item) => item.column).join(', ')">
          and {{ meta.excluded.length - shownExcluded.length }} more
        </span>
      </div>
    </analysis-layout>
    <div v-else-if="busy || starting" class="q-pa-md">
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
import { datasetAvatar } from "../../utils/analysis";
import AnalysisHeader from "./AnalysisHeader.vue";
import AnalysisLayout from "./AnalysisLayout.vue";
import AnalysisSection from "./AnalysisSection.vue";
import DiscrepancyAttributes from "./DiscrepancyAttributes.vue";
import DiscrepancyMagnitude from "./DiscrepancyMagnitude.vue";
import DiscrepancySummary from "./DiscrepancySummary.vue";

const RESULT_TYPES = ["Loss", "Discrepancy", "Duplicate"];
// The sections the tabs of earlier versions stand for, so their links still open the right place.
const TAB_SECTIONS = { summary: "summary", drivers: "attributes", combinations: "summary", time: "attributes", differences: "differences", records: "summary", excluded: "attributes" };
const EXCLUDED_SHOWN = 6;

// What sets the discrepancies of one side of a run apart from its normal records (fetched less discrepancies). The
// server counts every attribute's bins in both datasets and scores them in a job of its own; the report is kept in its
// memory, so reopening is instant until Recompute or a restart. A quick look at a sample is shown as soon as it is
// ready, marked preliminary, while refining counts the bins again. One scrolling page (AnalysisLayout): the summary
// with the findings as cards, the attributes ranked, and the differences of REC value discrepancies. Kept alive
// (App.vue); the result type and the open attribute are kept in the URL query (`t`, `attr`), the section in its hash.
export default {
  name: "DiscrepancyAnalysis",
  components: {
    AnalysisHeader,
    AnalysisLayout,
    AnalysisSection,
    DiscrepancyAttributes,
    DiscrepancyMagnitude,
    DiscrepancySummary,
  },
  data() {
    return {
      job: null,
      jobKey: null,
      starting: false,
      startError: null,
      resultType: null,
      attribute: null,
      // The sides of the last report, kept while another side or result type is analysed.
      sides: [],
      controlType: null,
      typeSplit: null,
      // The section to scroll to once the report is shown (the link's hash, or the open attribute), once per load.
      pendingSection: null,
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
    // The sides of the run with their discrepancy counts; one side (ANL) shows as the subject alone.
    sideOptions() {
      return this.sides.map((item) => ({
        ...datasetAvatar({ kind: "result" }),
        text: `Discrepancies ${item.side}`,
        count: item.count === null || item.count === undefined ? "" : formatNumber(item.count),
        value: item.side.toLowerCase(),
        hidden: !item.count,
      }));
    },
    stepText() {
      const job = this.job;
      if (job && job.progress && job.progress.step) {
        return job.progress.step;
      }
      return job && job.state === "queued" ? "Waiting for another analysis to end" : "Starting";
    },
    progressValue() {
      const progress = this.job && this.job.progress;
      return progress && progress.total ? Math.min(1, progress.done / progress.total) : null;
    },
    relatedCount() {
      const unrelated = new Set(this.report.unrelated || []);
      return new Set(this.report.attributes.map((item) => item.column).filter((column) => !unrelated.has(column))).size;
    },
    railSections() {
      const sections = [{ id: "summary", label: "Summary", icon: "fas fa-clipboard-list" }];
      if (this.report.attributes.length) {
        sections.push({ id: "attributes", label: "Attributes", icon: "fas fa-bullseye", count: this.relatedCount });
      }
      if (this.report.magnitude) {
        sections.push({ id: "differences", label: "Differences", icon: "fas fa-ruler-horizontal" });
      }
      return sections;
    },
    shownExcluded() {
      return this.meta.excluded.slice(0, EXCLUDED_SHOWN);
    },
    viewQuery() {
      const query = {};
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
        this.$router.replace({ query, hash: this.$route.hash });
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
    toDateTimeString,
    // Reads the view of the route's query and asks for its job.
    load() {
      const query = this.$route.query;
      this.resultType = RESULT_TYPES.includes(query.t) ? query.t : null;
      this.attribute = query.attr || null;
      const hash = (this.$route.hash || "").replace(/^#/, "");
      this.pendingSection = hash || TAB_SECTIONS[query.tab] || (this.attribute ? "attributes" : null);
      if (query.tab) {
        const rest = { ...query };
        delete rest.tab;
        this.$router.replace({ query: rest, hash: `#${TAB_SECTIONS[query.tab] || "summary"}` });
      }
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
        this.scrollToPending();
      }
    },
    // The section (or the open attribute) of the link, once the report is drawn.
    scrollToPending() {
      const section = this.pendingSection;
      this.pendingSection = null;
      if (!section) {
        return;
      }
      setTimeout(() => {
        if (section === "attributes" && this.attribute && this.$refs.attributes) {
          this.$refs.attributes.reveal(this.attribute);
        } else if (this.$refs.layout) {
          this.$refs.layout.scrollTo(section, false);
        }
      }, 50);
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
    // A finding's card: its attribute opens below.
    openAttribute(id) {
      this.attribute = id;
      if (this.$refs.attributes) {
        this.$refs.attributes.reveal(id);
      }
    },
    // Ends refining; the job finishes with the preliminary report.
    async stop() {
      try {
        await api("stop-discrepancy-analysis", { method: "POST", params: this.params() });
      } catch (error) {
        notifyError("The analysis could not be stopped", error);
      }
    },
    // Data analysis of the discrepancies (or the fetched records) matching a condition, filtered by the database; with
    // a condition it opens at its records.
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
      return { name: "data-analysis", params: { processId: this.$route.params.processId, dataset }, query, hash: where ? "#records" : "" };
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
    showFinding(finding) {
      this.showRows({ filters: [finding.filter] });
    },
    async copyLink() {
      await copyAndNotify(window.location.href, "Link to this view", "Failed to copy the link.");
    },
  },
};
</script>

<style scoped>
.progress {
  max-width: 480px;
}
</style>
