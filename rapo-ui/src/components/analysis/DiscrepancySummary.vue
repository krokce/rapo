<template>
  <div>
    <div class="row items-center q-mb-sm">
      <q-chip class="q-ml-none">
        <q-avatar icon="fas fa-exclamation-triangle" color="red-7" text-color="white" />
        <span class="text-weight-bold q-mr-xs">{{ formatNumber(meta.discrepancies) }}</span>{{ discrepancyNoun }}
        <span v-if="meta.fetched_total" class="text-grey-7 q-ml-xs">· {{ formatPct((meta.discrepancies * 100) / meta.fetched_total) }} of {{ formatNumber(meta.fetched_total) }} fetched</span>
      </q-chip>
      <q-chip
        v-for="option in typeOptions"
        :key="String(option.value)"
        clickable
        class="q-ml-none"
        :class="{ 'chip-selected': option.value === resultType }"
        :aria-pressed="option.value === resultType"
        @click="option.value !== resultType && $emit('result-type', option.value)">
        <q-avatar :icon="option.icon" :color="option.color" text-color="white" />
        <span class="text-weight-bold q-mr-xs">{{ option.label }}</span>({{ formatNumber(option.count) }})
        <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">{{ option.title }}</q-tooltip>
      </q-chip>
      <q-chip v-for="note in notes" :key="note.key" class="q-ml-none">
        <q-avatar :icon="note.icon" :color="note.color" text-color="white" />
        {{ note.label }}
        <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]" max-width="380px">{{ note.title }}</q-tooltip>
      </q-chip>
    </div>

    <run-trend class="q-mb-md" :process-id="meta.process_id" :dataset="meta.dataset" target="discrepancy" />

    <div v-if="emptyText" class="state-notice">
      <q-icon name="fas fa-info-circle" />
      <div>{{ emptyText }}</div>
    </div>
    <template v-else>
      <div class="row q-col-gutter-md">
        <div v-for="(finding, index) in report.findings" :key="finding.id" :class="index === 0 ? 'col-12 col-md-6' : 'col-12 col-sm-6 col-md-3'">
          <finding-card :finding="finding" :lead="index === 0" @open="$emit('open-attribute', $event.attribute)" @records="$emit('records', $event)" />
        </div>
      </div>
      <div v-if="report.unrelated.length" class="text-caption text-grey-7 q-mt-md">
        <q-icon name="fas fa-minus-circle" class="q-mr-xs" />Not related: <span class="text-blue-grey-8">{{ unrelatedText }}</span>
      </div>
    </template>
  </div>
</template>

<script>
import FindingCard from "./FindingCard.vue";
import RunTrend from "./RunTrend.vue";
import { formatNumber } from "../../utils/format";
import { formatPct, resultType as resultTypeStyle } from "../../utils/analysis";

const SAMPLES = { block: "random blocks", first: "the first records" };
const UNRELATED_SHOWN = 8;

// The first section of a discrepancy analysis: how many discrepancies (by result type for a reconciliation), notes on
// how they were counted, the trend of the last days, and the findings, the strongest first, as cards.
export default {
  name: "DiscrepancySummary",
  components: { FindingCard, RunTrend },
  props: {
    report: { type: Object, required: true },
    resultType: { type: String, default: null },
    // The split by result type of the run, kept from the report of all of them.
    typeSplit: { type: Array, default: null },
  },
  emits: ["result-type", "open-attribute", "records"],
  computed: {
    meta() {
      return this.report.meta;
    },
    discrepancyNoun() {
      const count = this.meta.discrepancies;
      if (this.meta.result_type) {
        return `${this.meta.result_type} ${count === 1 ? "record" : "records"}`;
      }
      return count === 1 ? "discrepancy" : "discrepancies";
    },
    // The result types of a reconciliation, each analysed alone on a click; All goes back once one is.
    typeOptions() {
      const split = this.typeSplit || [];
      if (this.meta.control_type !== "REC" || split.length < 2) {
        return [];
      }
      const total = split.reduce((sum, item) => sum + item.count, 0);
      const all = this.resultType ? [{ value: null, label: "All", count: total, icon: "fas fa-layer-group", color: "blue-grey-6", title: "Analyse every discrepancy" }] : [];
      return [...all, ...split.map((item) => ({ value: item.type, label: item.type, count: item.count, ...resultTypeStyle(item.type), title: `Analyse the ${item.type} records only` }))];
    },
    notes() {
      const meta = this.meta;
      const notes = [];
      if (meta.stage === "quick" || meta.stopped || meta.refine_error) {
        const sample = `A quick look at ${formatNumber(meta.sample_rows)} fetched records (${SAMPLES[meta.sample_method] || "all of them"}), scaled to the run's totals.`;
        const why = meta.stopped ? " Refining was stopped." : meta.refine_error ? ` Refining failed: ${meta.refine_error}.` : " Refining counts all records, or a random sample, and replaces it.";
        notes.push({ key: "quick", icon: "fas fa-bolt", color: "amber-9", label: "Preliminary", title: sample + why });
      } else if (meta.sample) {
        notes.push({
          key: "sample",
          icon: "fas fa-percentage",
          color: "amber-9",
          label: `Sampled ${formatPct(meta.sample * 100)}`,
          title: "The fetched records exceed [ANALYSIS] discrepancy_exact_rows, so they were counted on a random sample and scaled up.",
        });
      }
      if (meta.stale) {
        notes.push({
          key: "stale",
          icon: "fas fa-history",
          color: "orange-8",
          label: "Config changed",
          title: "The control was changed after this run. The fetched records are selected with its current configuration for the run's window, so they may differ from what the run fetched.",
        });
      }
      if (meta.drift) {
        notes.push({
          key: "drift",
          icon: "fas fa-exchange-alt",
          color: "orange-8",
          label: "Source changed",
          title: `The fetched records counted now (${formatNumber(meta.fetched_total)}) differ from what the run fetched (${formatNumber(meta.fetched_logged)}): the source data changed since.`,
        });
      }
      if (meta.clamped && meta.clamped.length) {
        notes.push({
          key: "clamped",
          icon: "fas fa-compress-alt",
          color: "amber-9",
          label: "Counts clamped",
          title: `Some bins hold more discrepancies than fetched records (${meta.clamped.slice(0, 5).join(", ")}), e.g. a key shared by several records, or source records changed since the run; their normal count is taken as 0.`,
        });
      }
      return notes;
    },
    emptyText() {
      if (!this.meta.discrepancies) {
        return "There are no discrepancies to explain.";
      }
      if (!this.meta.normal) {
        return "Every fetched record is a discrepancy, so there are no normal records to contrast them with.";
      }
      if (!this.report.findings.length) {
        return "No column sets these discrepancies apart: they are spread like the normal records. The cause is likely elsewhere, e.g. the other side, the matching rules or the timing of the load.";
      }
      return "";
    },
    unrelatedText() {
      const names = this.report.unrelated;
      const shown = names.slice(0, UNRELATED_SHOWN).join(", ");
      return names.length > UNRELATED_SHOWN ? `${shown} and ${names.length - UNRELATED_SHOWN} more` : shown;
    },
  },
  methods: {
    formatNumber,
    formatPct,
  },
};
</script>
