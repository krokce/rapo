<template>
  <div>
    <!-- What this sample is compared with. -->
    <q-card flat bordered class="q-mb-md">
      <q-card-section class="q-py-sm">
        <div class="row items-center q-gutter-sm">
          <div class="text-subtitle1 text-blue-grey-9 q-mr-sm">Compare with</div>
          <q-btn
            v-for="target in targets"
            :key="target.key"
            :outline="!isTarget(target)"
            :unelevated="isTarget(target)"
            no-caps
            dense
            class="q-px-sm"
            color="primary"
            :icon="targetIcon(target.key)"
            :label="target.label"
            @click="$emit('start-target', target)" />
          <q-btn :outline="!customOpen" :unelevated="customOpen" no-caps dense class="q-px-sm" color="blue-grey-7" icon="fas fa-search" label="Other run or control" @click="customOpen = !customOpen" />
        </div>
        <div v-if="customOpen" class="row items-center q-gutter-sm q-mt-sm">
          <q-select
            v-model="custom.control"
            class="col-12 col-md-4"
            dense
            outlined
            use-input
            input-debounce="0"
            label="Control"
            :options="controlOptions"
            @filter="filterControls"
            @update:model-value="loadRuns" />
          <q-select
            v-model="custom.run"
            class="col-12 col-md-3"
            dense
            outlined
            emit-value
            map-options
            label="Run"
            :options="runOptions"
            :disable="!custom.control"
            :loading="runsLoading" />
          <q-select v-model="custom.dataset" class="col-12 col-md-2" dense outlined emit-value map-options label="Dataset" :options="datasetOptions" :disable="!custom.run" />
          <q-btn unelevated no-caps color="primary" icon="fas fa-balance-scale" label="Compare" :disable="!custom.run || !custom.dataset" @click="startCustom" />
        </div>
      </q-card-section>
    </q-card>

    <div v-if="!compare.target" class="column items-center q-pa-xl text-grey-7 text-center">
      <q-icon name="fas fa-balance-scale" size="40px" color="blue-grey-3" class="q-mb-md" />
      Choose what to compare this sample with: e.g. the discrepancies against what the run fetched, to find the values that are
      over-represented in them, or a run against the previous one, to see what changed.
    </div>

    <template v-else>
      <!-- A against B, with the state of B's sample. -->
      <div class="row items-center q-gutter-md q-mb-md text-blue-grey-9">
        <q-chip color="teal-1" text-color="teal-10" class="text-weight-medium">A</q-chip>
        <div>
          <strong>{{ labelA }}</strong> · {{ formatNumber(stateA.rows || 0) }} rows
        </div>
        <q-icon name="fas fa-arrows-alt-h" color="grey-6" />
        <q-chip color="deep-orange-1" text-color="deep-orange-10" class="text-weight-medium">B</q-chip>
        <div>
          <strong>{{ compare.target.label }}</strong>
          <span v-if="compare.session"> · PID {{ compare.session.meta.process_id }} · {{ formatNumber(compare.state.rows || 0) }} rows</span>
        </div>
        <q-spinner-dots v-if="targetBusy" color="primary" size="20px" />
        <span v-if="targetBusy" class="text-grey-7">{{ compare.state.step || "Loading" }}</span>
        <q-space />
        <q-btn
          v-if="compare.session && !targetBusy && compare.state.cursor_open && !compare.state.exhausted"
          outline
          dense
          no-caps
          class="q-px-sm"
          color="primary"
          icon="fas fa-plus"
          label="Extend B"
          @click="$emit('extend-target')" />
        <q-btn flat dense no-caps color="grey-7" icon="fas fa-times" label="Stop comparing" @click="$emit('close-target')" />
      </div>
      <q-banner v-if="compare.error" class="bg-red-1 text-red-9 q-mb-md" rounded>{{ compare.error }}</q-banner>
      <q-banner v-else-if="['lost', 'expired'].includes(compare.state.status)" class="bg-amber-1 text-brown-9 q-mb-md" rounded>
        The sample B was closed, after it was not used for a while or by a server restart.
        <template #action>
          <q-btn flat color="brown-9" label="Load it again" @click="$emit('start-target', compare.target)" />
        </template>
      </q-banner>

      <!-- Column pairs. -->
      <q-expansion-item v-if="mapping" v-model="mappingOpen" dense switch-toggle-side class="mapping q-mb-md" header-class="text-blue-grey-9">
        <template #header>
          <q-item-section>
            <div>
              Column pairs <q-badge color="blue-grey-5">{{ pairs.length }}</q-badge>
              <span v-if="mapping.unmatched_a.length || mapping.unmatched_b.length" class="text-caption text-grey-7 q-ml-sm">
                {{ unmatchedA.length }} columns of A and {{ unmatchedB.length }} of B are not compared
              </span>
            </div>
          </q-item-section>
        </template>
        <div class="q-pa-sm">
          <div v-for="(pair, index) in pairs" :key="index" class="row items-center q-gutter-sm q-mb-xs">
            <q-select v-model="pair.a" dense outlined options-dense class="col" :options="columnsA" label="A" />
            <q-icon name="fas fa-arrows-alt-h" color="grey-6" />
            <q-select v-model="pair.b" dense outlined options-dense class="col" :options="columnsB" label="B" />
            <q-chip v-if="pair.source === 'criteria'" dense size="sm" color="teal-1" text-color="teal-9" title="From the reconciliation's criteria">criteria</q-chip>
            <q-btn flat dense round size="sm" color="grey-7" icon="fas fa-trash" @click="removePair(index)" />
          </div>
          <div class="row q-gutter-sm q-mt-sm">
            <q-btn flat dense no-caps color="primary" icon="fas fa-plus" label="Add a pair" @click="addPair" />
            <q-btn flat dense no-caps color="grey-7" icon="fas fa-undo" label="Default pairs" @click="resetPairs" />
          </div>
          <div v-if="unmatchedA.length || unmatchedB.length" class="text-caption text-grey-7 q-mt-sm">
            <div v-if="unmatchedA.length">Not compared in A: {{ unmatchedA.map((name) => name.toUpperCase()).join(", ") }}</div>
            <div v-if="unmatchedB.length">Not compared in B: {{ unmatchedB.map((name) => name.toUpperCase()).join(", ") }}</div>
          </div>
        </div>
      </q-expansion-item>

      <!-- The ranking, and the detail of the chosen column. -->
      <div v-if="loading && !result" class="q-pa-md"><q-skeleton type="rect" height="240px" /></div>
      <template v-else-if="result">
        <div class="text-caption text-grey-7 q-mb-sm">
          Columns by divergence (Population Stability Index): below 0.1 stable, 0.1 to 0.25 moderate, above 0.25 major. Key-like columns, almost
          unique in both samples, are not ranked. Click a column for its values.
        </div>
        <q-markup-table dense flat bordered class="ranking q-mb-md">
          <thead>
            <tr class="bg-blue-grey-2">
              <th class="text-left">Column A</th>
              <th class="text-left">Column B</th>
              <th class="text-left">Kind</th>
              <th class="text-left" style="width: 260px">Divergence</th>
              <th class="text-right">Missing A / B</th>
              <th class="text-right">Distinct A / B</th>
              <th class="text-right">Median A / B</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="column in result.columns" :key="column.a + '|' + column.b" class="cursor-pointer" :class="{ selected: selectedKey === keyOf(column) }" @click="select(column)">
              <td class="text-weight-medium">{{ column.a.toUpperCase() }}</td>
              <td>{{ column.b.toUpperCase() }}</td>
              <td class="text-grey-8">{{ kindLabel(column.kind) }}</td>
              <td>
                <div v-if="column.level === 'unique'" class="text-grey-6 text-italic">key-like, not ranked</div>
                <div v-else class="row items-center no-wrap">
                  <div class="psi-bar" :style="{ width: psiWidth(column.psi) + 'px', background: levelColor(column.level) }" />
                  <span class="q-ml-sm text-weight-medium" :style="{ color: levelColor(column.level) }">{{ formatStat(column.psi, 3) }}</span>
                  <span class="q-ml-xs text-caption text-grey-7">{{ column.level }}</span>
                </div>
              </td>
              <td class="text-right">{{ formatPct(column.missing_pct[0]) }} / {{ formatPct(column.missing_pct[1]) }}</td>
              <td class="text-right">{{ formatNumber(column.distinct[0]) }} / {{ formatNumber(column.distinct[1]) }}</td>
              <td class="text-right">{{ medianText(column) }}</td>
            </tr>
          </tbody>
        </q-markup-table>

        <q-card v-if="selected && selected.level !== 'unique'" flat bordered>
          <q-card-section class="q-pb-none">
            <div class="text-subtitle1 text-blue-grey-9">{{ selected.a.toUpperCase() }} <span class="text-grey-6">vs</span> {{ selected.b.toUpperCase() }}</div>
            <div class="text-caption text-grey-7">
              Share of the rows in each {{ selected.mode === "bins" ? "range" : "value" }}. Lift is the share in A divided by the share in B: above
              1 the value is over-represented in A.
            </div>
          </q-card-section>
          <q-card-section class="row q-col-gutter-lg">
            <div class="col-12 col-lg-7">
              <e-chart :option="detailOption" :height="300" />
            </div>
            <div class="col-12 col-lg-5">
              <q-markup-table dense flat class="lift-table">
                <thead>
                  <tr>
                    <th class="text-left">{{ selected.mode === "bins" ? "Range" : "Value" }}</th>
                    <th class="text-right">A</th>
                    <th class="text-right">B</th>
                    <th class="text-right">Lift</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in liftRows" :key="item.index">
                    <td class="ellipsis lift-label" :title="bucketLabel(item)" :class="{ 'text-italic text-grey-6': item.missing || item.other }">{{ bucketLabel(item) }}</td>
                    <td class="text-right">{{ formatPct(item.share_a) }}</td>
                    <td class="text-right">{{ formatPct(item.share_b) }}</td>
                    <td class="text-right">
                      <q-chip dense square size="sm" :color="liftColor(item)" text-color="white" class="text-weight-bold">{{ liftText(item) }}</q-chip>
                    </td>
                    <td class="text-right">
                      <q-btn v-if="!item.other && item.count_a" flat dense round size="xs" color="primary" icon="fas fa-table" @click="showRowsA(item)">
                        <q-tooltip>Show these rows of A</q-tooltip>
                      </q-btn>
                    </td>
                  </tr>
                </tbody>
              </q-markup-table>
            </div>
          </q-card-section>
        </q-card>
      </template>
    </template>
  </div>
</template>

<script>
import EChart from "./EChart.vue";
import { api, notifyError } from "../../api";
import { formatNumber, toDateTimeString } from "../../utils/format";
import { KIND_ICONS, formatPct, formatStat, formatValue } from "../../utils/analysis";

const LEVEL_COLORS = { stable: "#43a047", moderate: "#fb8c00", major: "#e53935" };
const TARGET_ICONS = { source: "fas fa-database", previous: "fas fa-history", other_side: "fas fa-exchange-alt" };
const DATASET_LABELS = { fetched_a: "Fetched A", fetched_b: "Fetched B", result_a: "Discrepancies A", result_b: "Discrepancies B" };

// Compares this sample (A) with another (B) held by a second session of the page: the columns are paired (by name,
// and for the two sides of a reconciliation by its criteria), and the server compares the shares of their values.
// `compare` is the page's {target, session, state, error}; the page starts and ends B's session.
export default {
  name: "CompareTab",
  components: { EChart },
  props: {
    sessionId: { type: String, required: true },
    meta: { type: Object, required: true },
    stateA: { type: Object, required: true },
    labelA: { type: String, default: "This sample" },
    compare: { type: Object, required: true },
  },
  emits: ["start-target", "close-target", "extend-target", "show-rows"],
  data() {
    return {
      targets: [],
      customOpen: false,
      custom: { control: null, run: null, dataset: null },
      controlNeedle: "",
      runs: [],
      runsLoading: false,
      mapping: null,
      pairs: [],
      mappingOpen: false,
      result: null,
      loading: false,
      selectedKey: null,
      token: 0,
    };
  },
  computed: {
    targetSessionId() {
      return this.compare.session ? this.compare.session.session_id : null;
    },
    targetBusy() {
      return !this.compare.session || ["starting", "fetching", "profiling"].includes(this.compare.state.status);
    },
    ready() {
      return Boolean(this.targetSessionId) && this.stateA.version > 0 && this.compare.state.version > 0;
    },
    controlOptions() {
      const names = this.$store.state.controlCatalogue.map((control) => control.control_name).sort();
      const needle = this.controlNeedle.toLowerCase();
      return names.filter((name) => !needle || name.toLowerCase().includes(needle)).slice(0, 200);
    },
    customType() {
      const control = this.$store.state.controlCatalogue.find((item) => item.control_name === this.custom.control);
      return control ? control.control_type : null;
    },
    runOptions() {
      return this.runs.map((run) => {
        const from = toDateTimeString(run.date_from);
        const to = toDateTimeString(run.date_to);
        const window = from.substring(0, 10) === to.substring(0, 10) ? from.substring(0, 10) : `${from.substring(0, 10)} – ${to.substring(0, 10)}`;
        return { label: `${window} · PID ${run.process_id}`, value: run.process_id };
      });
    },
    datasetOptions() {
      const type = this.customType;
      const keys = type === "REP" ? ["fetched_a"] : type === "ANL" ? ["fetched_a", "result_a"] : ["fetched_a", "fetched_b", "result_a", "result_b"];
      return keys.map((key) => ({ label: type === "REP" ? "Report rows" : type === "ANL" ? DATASET_LABELS[key].replace(/ A$/, "") : DATASET_LABELS[key], value: key }));
    },
    columnsA() {
      return (this.stateA.columns || []).map((column) => column.name);
    },
    columnsB() {
      return (this.compare.state.columns || []).map((column) => column.name);
    },
    unmatchedA() {
      return this.columnsA.filter((name) => !this.pairs.some((pair) => pair.a === name));
    },
    unmatchedB() {
      return this.columnsB.filter((name) => !this.pairs.some((pair) => pair.b === name));
    },
    requestKey() {
      return JSON.stringify([this.targetSessionId, this.stateA.version, this.compare.state.version, this.pairs]);
    },
    selected() {
      return this.result ? this.result.columns.find((column) => this.keyOf(column) === this.selectedKey) || null : null;
    },
    liftRows() {
      return [...this.selected.lifts].sort((first, second) => second.share_a - second.share_b - (first.share_a - first.share_b));
    },
    detailOption() {
      const column = this.selected;
      const labels = column.labels.map((label) => this.plainLabel(label, column)).concat(["(missing)", "(other)"]);
      const keep = labels.map((label, index) => column.shares_a[index] || column.shares_b[index]);
      const shown = labels.filter((label, index) => keep[index]);
      const pick = (shares) => shares.filter((share, index) => keep[index]);
      return {
        animation: false,
        grid: { left: 8, right: 16, top: 30, bottom: 8, containLabel: true },
        legend: { top: 0, textStyle: { fontSize: 11 } },
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (value) => formatPct(value) },
        xAxis: { type: "category", data: shown, axisLabel: { fontSize: 10, hideOverlap: true, rotate: column.mode === "values" ? 30 : 0 } },
        yAxis: { type: "value", axisLabel: { fontSize: 10, formatter: "{value}%" }, splitLine: { lineStyle: { color: "#eceff1" } } },
        series: [
          { name: `A: ${this.labelA}`, type: "bar", data: pick(column.shares_a), itemStyle: { color: "#26a69a" } },
          { name: `B: ${this.compare.target.label}`, type: "bar", data: pick(column.shares_b), itemStyle: { color: "#ff7043" } },
        ],
      };
    },
  },
  watch: {
    "meta.process_id": {
      immediate: true,
      handler() {
        this.loadTargets();
      },
    },
    // A new B: its default pairs, once its columns are known.
    targetSessionId() {
      this.mapping = null;
      this.pairs = [];
      this.result = null;
      this.selectedKey = null;
      this.loadMapping();
    },
    ready() {
      this.loadMapping();
    },
    requestKey() {
      clearTimeout(this.timer);
      this.timer = setTimeout(() => this.run(), 300);
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
    async loadTargets() {
      try {
        this.targets = await api("get-analysis-targets", { params: { process_id: this.meta.process_id, dataset: this.meta.dataset }, loadingBar: false });
      } catch (error) {
        this.targets = [];
      }
    },
    async loadMapping() {
      if (!this.ready || this.mapping) {
        return;
      }
      try {
        this.mapping = await api("analysis-compare-mapping", { params: { session_id: this.sessionId, other_id: this.targetSessionId }, loadingBar: false });
        this.pairs = this.mapping.pairs.map((pair) => ({ ...pair }));
        this.mappingOpen = !this.pairs.length;
      } catch (error) {
        notifyError("The columns could not be paired.", error);
      }
    },
    async run() {
      if (!this.ready || !this.mapping) {
        return;
      }
      const pairs = this.pairs.filter((pair) => pair.a && pair.b);
      if (!pairs.length) {
        this.result = null;
        return;
      }
      const token = ++this.token;
      this.loading = true;
      try {
        const result = await api("analysis-compare", {
          method: "POST",
          params: { session_id: this.sessionId, other_id: this.targetSessionId },
          body: { pairs },
          loadingBar: false,
        });
        if (token === this.token) {
          this.result = Object.freeze(result);
          if (!this.selected) {
            const first = result.columns.find((column) => column.level !== "unique");
            this.selectedKey = first ? this.keyOf(first) : null;
          }
        }
      } catch (error) {
        if (token === this.token && error.status !== 404) {
          notifyError("The comparison failed.", error);
        }
      } finally {
        if (token === this.token) {
          this.loading = false;
        }
      }
    },
    isTarget(target) {
      const current = this.compare.target;
      return Boolean(current) && current.process_id === target.process_id && current.dataset === target.dataset;
    },
    targetIcon(key) {
      return TARGET_ICONS[key] || "fas fa-balance-scale";
    },
    filterControls(text, update) {
      if (!this.$store.state.controlCatalogue.length) {
        this.$store.dispatch("updateControlCatalogue").catch(() => {});
      }
      update(() => (this.controlNeedle = text || ""));
    },
    async loadRuns(name) {
      this.custom.run = null;
      this.custom.dataset = null;
      this.runs = [];
      if (!name) {
        return;
      }
      this.runsLoading = true;
      try {
        this.runs = await api("get-control-done-runs", { params: { control_name: name, limit: 100 }, loadingBar: false });
        this.custom.dataset = this.meta.dataset;
        if (!this.datasetOptions.some((option) => option.value === this.custom.dataset)) {
          this.custom.dataset = this.datasetOptions[0].value;
        }
      } catch (error) {
        notifyError("The runs could not be loaded.", error);
      } finally {
        this.runsLoading = false;
      }
    },
    startCustom() {
      const option = this.datasetOptions.find((item) => item.value === this.custom.dataset);
      const run = this.runs.find((item) => item.process_id === this.custom.run);
      const day = run ? toDateTimeString(run.date_from).substring(0, 10) : "";
      this.$emit("start-target", {
        key: "custom",
        process_id: this.custom.run,
        dataset: this.custom.dataset,
        label: `${this.custom.control} ${option ? option.label : ""}, ${day}`,
      });
    },
    addPair() {
      this.pairs.push({ a: this.unmatchedA[0] || null, b: this.unmatchedB[0] || null, source: "manual" });
    },
    removePair(index) {
      this.pairs.splice(index, 1);
    },
    resetPairs() {
      this.pairs = this.mapping.pairs.map((pair) => ({ ...pair }));
    },
    keyOf(column) {
      return `${column.a}|${column.b}`;
    },
    select(column) {
      this.selectedKey = this.keyOf(column);
    },
    kindLabel(kind) {
      return (KIND_ICONS[kind] || KIND_ICONS.text).label;
    },
    psiWidth(psi) {
      return Math.max(3, Math.min(160, (psi || 0) * 320));
    },
    levelColor(level) {
      return LEVEL_COLORS[level] || "#90a4ae";
    },
    medianText(column) {
      const median = column.stats && column.stats.median;
      if (!median) {
        return "–";
      }
      return column.kind === "datetime" ? `${toDateTimeString(median[0])} / ${toDateTimeString(median[1])}` : `${formatStat(median[0])} / ${formatStat(median[1])}`;
    },
    plainLabel(label, column) {
      if (Array.isArray(label)) {
        return column.kind === "datetime" ? toDateTimeString(label[0]).substring(0, 16) : `${formatStat(label[0])}–${formatStat(label[1])}`;
      }
      return label === "" ? "(blank)" : String(label);
    },
    bucketLabel(item) {
      if (item.missing) {
        return "(missing)";
      }
      if (item.other) {
        return "(other values)";
      }
      const label = item.label;
      if (Array.isArray(label)) {
        return this.selected.kind === "datetime"
          ? `${toDateTimeString(label[0])} – ${toDateTimeString(label[1])}`
          : `${formatStat(label[0], 4)} – ${formatStat(label[1], 4)}`;
      }
      return label === "" ? "(blank)" : formatValue(label, this.selected.kind === "datetime" ? "text" : this.selected.kind);
    },
    liftText(item) {
      if (item.lift === null) {
        return "A only";
      }
      return item.lift >= 100 ? "×99+" : `×${item.lift.toFixed(item.lift >= 10 ? 0 : 2)}`;
    },
    liftColor(item) {
      if (item.lift === null || item.lift >= 2) {
        return "red-7";
      }
      if (item.lift >= 1.25) {
        return "orange-8";
      }
      if (item.lift <= 0.5) {
        return "blue-7";
      }
      return "blue-grey-4";
    },
    // The rows of A in a value or a range, in the viewer.
    showRowsA(item) {
      const column = this.selected.a;
      if (item.missing) {
        this.$emit("show-rows", [{ column, op: "null" }]);
      } else if (Array.isArray(item.label)) {
        const last = item.index === this.selected.labels.length - 1;
        this.$emit("show-rows", [{ column, kind: this.selected.kind, op: "range", value: { min: item.label[0], max: item.label[1], max_inclusive: last } }]);
      } else {
        this.$emit("show-rows", [{ column, op: "eq", value: item.label }]);
      }
    },
  },
};
</script>

<style scoped>
.ranking tbody tr:hover {
  background: #e0f2f1;
}

.ranking tbody tr.selected {
  background: #b2dfdb;
}

.psi-bar {
  height: 10px;
  border-radius: 2px;
}

.lift-label {
  max-width: 220px;
}

.mapping {
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background: white;
}
</style>
