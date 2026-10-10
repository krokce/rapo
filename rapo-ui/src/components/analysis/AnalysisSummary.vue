<template>
  <div>
    <div class="row items-center q-mb-sm">
      <q-chip class="q-ml-none" :title="samplingTitle">
        <q-avatar icon="fas fa-list" color="teal-7" text-color="white" />
        <template v-if="state.version">
          <span class="text-weight-bold q-mr-xs">{{ formatNumber(state.rows) }}</span>
          <template v-if="totalRows !== null && totalRows !== state.rows">of {{ formatNumber(totalRows) }}&nbsp;</template>
          {{ state.rows === 1 ? "record" : "records" }}<span class="text-grey-7 q-ml-xs">· {{ samplingText }}</span>
        </template>
        <template v-else>Loading the records…</template>
      </q-chip>
      <q-btn v-if="canExtend" outline dense no-caps color="primary" icon="fas fa-plus" padding="4px 10px" class="q-mr-sm" :label="extendLabel" @click="$emit('extend')">
        <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">{{ extendTitle }}</q-tooltip>
      </q-btn>
      <q-chip v-if="state.limited" outline color="amber-9" class="q-ml-none">
        <q-avatar :icon="state.limited === 'memory' ? 'fas fa-memory' : 'fas fa-ban'" color="amber-9" text-color="white" />
        {{ state.limited === "memory" ? `Memory limit ${formatNumber(options.max_memory_mb)} MB reached` : `Row limit ${formatNumber(options.max_rows)} reached` }}
      </q-chip>
      <template v-if="overview">
        <q-chip clickable class="q-ml-none" @click="$emit('go', 'columns')">
          <q-avatar icon="fas fa-columns" color="blue-grey-6" text-color="white" />
          <span class="text-weight-bold q-mr-xs">{{ formatNumber(overview.columns) }}</span>{{ overview.columns === 1 ? "column" : "columns" }}
        </q-chip>
        <q-chip v-if="overview.duplicate_rows" clickable class="q-ml-none" @click="$emit('show-rows', [{ op: 'duplicated' }])">
          <q-avatar icon="fas fa-clone" color="purple-6" text-color="white" />
          <span class="text-weight-bold q-mr-xs">{{ formatNumber(overview.duplicate_rows) }}</span>duplicate {{ overview.duplicate_rows === 1 ? "record" : "records" }}
          <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">
            {{ formatPct(overview.duplicate_pct) }} of the records repeat an earlier one in every column: show all of them
          </q-tooltip>
        </q-chip>
        <q-chip v-if="overview.missing_columns.length" clickable class="q-ml-none" @click="$emit('go', 'columns')">
          <q-avatar icon="fas fa-border-none" color="orange-8" text-color="white" />
          <span class="text-weight-bold q-mr-xs">{{ overview.missing_columns.length }}</span>{{ overview.missing_columns.length === 1 ? "column" : "columns" }} ≥ 5% missing
          <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">{{ names(overview.missing_columns) }}</q-tooltip>
        </q-chip>
        <q-chip v-if="overview.unusable.length" clickable class="q-ml-none" @click="$emit('go', 'columns')">
          <q-avatar icon="fas fa-eye-slash" color="grey-6" text-color="white" />
          <span class="text-weight-bold q-mr-xs">{{ overview.unusable.length }}</span>not profiled
          <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">Constant, empty or unique: {{ names(overview.unusable.map((item) => item.name)) }}</q-tooltip>
        </q-chip>
      </template>
      <q-chip v-if="meta.stale" class="q-ml-none">
        <q-avatar icon="fas fa-history" color="orange-8" text-color="white" />
        Config changed
        <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]" max-width="360px">
          The control was changed after this run. The records are selected with its current configuration for the run's window, so they may
          differ from what the run fetched.
        </q-tooltip>
      </q-chip>
    </div>

    <div v-if="pairs.length" class="row items-center q-mb-sm">
      <span class="text-grey-7 q-mr-sm">Related</span>
      <q-chip v-for="pair in pairs" :key="`${pair.a}|${pair.b}`" clickable class="q-ml-none" @click="$emit('group', pair)">
        <q-avatar icon="fas fa-link" :color="strengthColor(pair.value)" text-color="white" />
        {{ pair.a.toUpperCase() }} ↔ {{ pair.b.toUpperCase() }}<span class="text-weight-bold q-ml-xs">{{ pair.value.toFixed(2) }}</span>
        <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]" max-width="360px">
          {{ methodLabel(pair.method) }} {{ pair.value.toFixed(2) }} in the sample: the values of the two columns go together. Show the records grouped by both.
        </q-tooltip>
      </q-chip>
    </div>

    <run-trend v-if="trendDataset" class="q-mt-sm" :process-id="meta.process_id" :dataset="trendDataset" :report-only="meta.control_type === 'REP'" />
  </div>
</template>

<script>
import RunTrend from "./RunTrend.vue";
import { formatNumber } from "../../utils/format";
import { formatPct, strengthColor } from "../../utils/analysis";

const METHODS = { pearson: "Pearson", spearman: "Spearman", cramers: "Cramér's V" };
const SHOWN_PAIRS = 3;

// The first section of Data analysis: the records loaded (and Extend), the columns, the duplicates and missing values
// when there are any, the strongest relations between columns, and the run trend of a run's dataset.
export default {
  name: "AnalysisSummary",
  components: { RunTrend },
  props: {
    meta: { type: Object, required: true },
    state: { type: Object, required: true },
    options: { type: Object, default: () => ({}) },
    overview: { type: Object, default: null },
    relations: { type: Object, default: null },
    totalRows: { type: Number, default: null },
    canExtend: { type: Boolean, default: false },
    extendRows: { type: Number, default: 0 },
  },
  emits: ["show-rows", "group", "go", "extend"],
  computed: {
    pairs() {
      return this.relations ? this.relations.pairs.slice(0, SHOWN_PAIRS) : [];
    },
    bernoulli() {
      return this.state.sampling === "bernoulli";
    },
    samplingText() {
      if (this.state.exhausted) {
        return "all loaded";
      }
      return { first: "the first ones", all: "the first ones" }[this.state.sampling] || "random sample";
    },
    samplingTitle() {
      if (this.state.exhausted) {
        return "Every record of the dataset is loaded";
      }
      if (this.bernoulli) {
        return "A random sample: every record had the same chance to be read, and the database streams them without sorting";
      }
      if (this.state.sampling === "sorted") {
        return "A random sample: the database shuffled the records before the first ones arrived";
      }
      return "The first records as the database returns them";
    },
    extendLabel() {
      return this.bernoulli ? `Sample ${formatNumber((this.state.target || this.state.rows) + this.extendRows)}` : `Load ${formatNumber(this.extendRows)} more`;
    },
    extendTitle() {
      return this.bernoulli ? "Read a bigger random sample, which replaces this one" : "Fetch the next records of the dataset into the sample";
    },
    // The trend of a run's dataset; a REP's rows are its fetched ones.
    trendDataset() {
      if (this.meta.kind === "file" || !this.meta.process_id) {
        return null;
      }
      return this.meta.dataset;
    },
  },
  methods: {
    formatNumber,
    formatPct,
    strengthColor,
    methodLabel(method) {
      return METHODS[method] || method;
    },
    names(list) {
      const shown = list.slice(0, 12).map((name) => name.toUpperCase());
      return list.length > 12 ? `${shown.join(", ")} and ${list.length - 12} more` : shown.join(", ");
    },
  },
};
</script>
