<template>
  <q-card flat bordered class="column-card full-height">
    <q-card-section class="row items-center no-wrap q-py-sm">
      <q-avatar size="24px" :icon="kind.icon" :color="kind.color" text-color="white" font-size="12px" class="q-mr-sm" :title="kind.label" />
      <div class="text-weight-bold text-blue-grey-10 ellipsis column-name" :title="`${column.name.toUpperCase()} (${dbType || kind.label})`">{{ column.name.toUpperCase() }}</div>
      <q-space />
      <div class="row no-wrap items-center facts">
        <q-chip
          v-for="fact in facts"
          :key="fact.key"
          dense
          square
          size="12px"
          :color="fact.color"
          :text-color="fact.textColor"
          :clickable="Boolean(fact.filters)"
          :title="fact.title"
          @click="fact.filters && $emit('show-rows', fact.filters)">
          {{ fact.label }}
        </q-chip>
      </div>
    </q-card-section>
    <q-card-section class="q-pt-none q-pb-sm">
      <mini-bars v-if="column.visual === 'top'" :items="topItems" :max="topMax" @select="(item) => $emit('show-rows', [item.filter])" />
      <mini-histogram v-else-if="column.visual === 'histogram'" :bars="histogramBars" :start="edgeText(0)" :end="edgeText(column.histogram.edges.length - 1)" @select="selectBin" />
      <div v-else class="text-caption text-grey-7">No value repeats in the sample.</div>
      <div v-if="caption" class="text-caption text-grey-7 q-mt-xs">{{ caption }}</div>
    </q-card-section>
  </q-card>
</template>

<script>
import MiniBars from "./MiniBars.vue";
import MiniHistogram from "./MiniHistogram.vue";
import { formatNumber, toDateTimeString } from "../../utils/format";
import { binFilter, formatPct, formatStat, formatValue, kindInfo, valueFilter } from "../../utils/analysis";

// The share from which missing values are worth a warning.
const MISSING_WARN = 5;
// The share of zeros a histogram is worth a note for.
const ZEROS_NOTE = 10;

// One column of the sample: its kind, a few facts as chips, and one visual the profile chose for it (`visual`): its
// most frequent values, or a histogram of its numbers or dates. Every bar and chip that stands for records shows them.
export default {
  name: "ColumnCard",
  components: { MiniBars, MiniHistogram },
  props: {
    column: { type: Object, required: true },
    dbType: { type: String, default: "" },
  },
  emits: ["show-rows"],
  computed: {
    kind() {
      return kindInfo(this.column);
    },
    dateOnly() {
      return Boolean(this.column.stats && this.column.stats.date_only);
    },
    facts() {
      const c = this.column;
      const s = c.stats || {};
      const facts = [{ key: "distinct", label: `${formatNumber(c.distinct)} ${c.distinct === 1 ? "value" : "values"}`, color: "grey-3", textColor: "grey-8", title: "Distinct values in the sample" }];
      if (c.missing) {
        const warn = c.missing_pct >= MISSING_WARN;
        facts.push({
          key: "missing",
          label: `missing ${formatPct(c.missing_pct)}`,
          color: warn ? "orange-1" : "grey-3",
          textColor: warn ? "orange-10" : "grey-8",
          title: `${formatNumber(c.missing)} empty values: show these records`,
          filters: [{ column: c.name, op: "null" }],
        });
      }
      if (s.blank) {
        facts.push({ key: "blank", label: `blank ${formatPct(s.blank_pct)}`, color: "grey-3", textColor: "grey-8", title: `${formatNumber(s.blank)} values of spaces only` });
      }
      if (c.visual === "histogram" && s.zeros_pct >= ZEROS_NOTE) {
        facts.push({
          key: "zeros",
          label: `zeros ${formatPct(s.zeros_pct)}`,
          color: "grey-3",
          textColor: "grey-8",
          title: `${formatNumber(s.zeros)} zeros: show these records`,
          filters: [valueFilter(c.name, 0)],
        });
      }
      return facts;
    },
    topItems() {
      const c = this.column;
      const items = c.top.map((item, index) => ({
        key: `v${index}`,
        label: item.value === "" ? "(blank)" : formatValue(item.value, c.kind, this.dateOnly),
        count: item.count,
        pct: item.pct,
        filter: valueFilter(c.name, item.value),
      }));
      if (c.other_count) {
        const values = c.distinct - c.top.length;
        items.push({ key: "other", label: `${formatNumber(values)} other ${values === 1 ? "value" : "values"}`, count: c.other_count, pct: (c.other_count * 100) / c.count, muted: true, filter: false });
      }
      return items;
    },
    topMax() {
      return Math.max(1, ...this.column.top.map((item) => item.count));
    },
    histogramBars() {
      const { counts } = this.column.histogram;
      return counts.map((count, index) => ({ count, title: `${this.binText(index)}: ${formatNumber(count)} ${count === 1 ? "record" : "records"}` }));
    },
    caption() {
      const c = this.column;
      if (c.visual === "histogram" && c.kind === "numeric") {
        return `median ${formatStat(c.stats.median)}`;
      }
      return "";
    },
  },
  methods: {
    edgeText(index) {
      const edge = this.column.histogram.edges[index];
      if (this.column.kind === "datetime") {
        const text = toDateTimeString(edge);
        return this.dateOnly ? text.substring(0, 10) : text.substring(0, 16);
      }
      return formatStat(edge);
    },
    binText(index) {
      return `${this.edgeText(index)} – ${this.edgeText(index + 1)}`;
    },
    selectBin(index) {
      this.$emit("show-rows", [binFilter(this.column.name, this.column.kind, this.column.histogram.edges, index)]);
    },
  },
};
</script>

<style scoped>
.column-name {
  font-size: 14px;
  min-width: 0;
}

.facts {
  margin-left: 8px;
  flex-shrink: 0;
}

.facts .q-chip {
  margin: 0 0 0 4px;
}
</style>
