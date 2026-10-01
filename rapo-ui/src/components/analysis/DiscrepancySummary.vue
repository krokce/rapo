<template>
  <div>
    <!-- The story: one sentence per finding; a driver opens its attribute, or its discrepancies. -->
    <q-card flat bordered class="q-mb-lg">
      <q-card-section class="q-py-sm header">
        <div class="text-subtitle1 text-blue-grey-9">What sets these discrepancies apart</div>
      </q-card-section>
      <q-separator />
      <q-card-section class="q-py-sm">
        <div v-for="(item, index) in report.story" :key="index" class="row no-wrap items-start q-py-xs story-line">
          <q-icon :name="storyIcon(item.kind).icon" :color="storyIcon(item.kind).color" size="16px" class="q-mr-sm story-icon" />
          <div class="col" :class="{ 'text-weight-medium text-blue-grey-10': item.kind === 'headline', 'text-grey-8': item.kind === 'note' }">
            {{ item.text }}
          </div>
          <template v-if="item.attribute">
            <q-btn flat dense no-caps size="sm" color="primary" icon="fas fa-chart-bar" label="Attribute" @click="$emit('show-attribute', item.attribute)">
              <q-tooltip anchor="top middle" self="bottom middle">The bins of this attribute</q-tooltip>
            </q-btn>
            <q-btn v-if="storyFilters(item).length" flat dense no-caps size="sm" color="primary" icon="fas fa-table" label="Records" @click="$emit('show-rows', { filters: storyFilters(item) })">
              <q-tooltip anchor="top middle" self="bottom middle">Open these discrepancies in Data analysis</q-tooltip>
            </q-btn>
          </template>
          <q-btn v-else-if="findingFilter(item)" flat dense no-caps size="sm" color="primary" icon="fas fa-table" label="Records" @click="$emit('show-rows', { filters: [findingFilter(item)] })">
            <q-tooltip anchor="top middle" self="bottom middle">Open these discrepancies in Data analysis</q-tooltip>
          </q-btn>
        </div>
      </q-card-section>
    </q-card>

    <div class="row q-col-gutter-md">
      <div class="col-12" :class="{ 'col-lg-8': typeSplit.length > 1 }">
        <q-card flat bordered class="full-height">
<q-card-section class="q-py-sm">
  <div class="text-subtitle2 text-blue-grey-9">Attributes by how much they tell discrepancies from normal records</div>
  <div class="text-caption text-grey-7">
    Explained: the share of the uncertainty about a record being a discrepancy that the attribute removes (Theil's U, 0 to 100%). φK: the
    phik correlation of the attribute with being a discrepancy (0 to 1). The best binning of each column; click a bar for its bins.
  </div>
</q-card-section>
<q-card-section class="q-pt-none">
  <e-chart v-if="ranking.length" :option="rankingOption" :height="Math.max(120, ranking.length * 26 + 40)" @select="selectBar" />
  <div v-else class="state-notice">
    <q-icon name="fas fa-info-circle" />
    <div>No attribute could be scored.</div>
  </div>
</q-card-section>
        </q-card>
      </div>
      <div v-if="typeSplit.length > 1" class="col-12 col-lg-4">
        <q-card flat bordered class="full-height">
<q-card-section class="q-py-sm">
  <div class="text-subtitle2 text-blue-grey-9">Result type</div>
  <div class="text-caption text-grey-7">Loss: no counterpart on the other side. Discrepancy: a counterpart with different values. Click to analyse one type.</div>
</q-card-section>
<q-card-section class="q-pt-none">
  <div
    v-for="item in typeSplit"
    :key="item.type"
    class="row no-wrap items-center breakdown-row cursor-pointer"
    :title="`Analyse the ${item.type} records only`"
    v-keyboard:button
    @click="$emit('result-type', item.type)">
    <div class="breakdown-label ellipsis">{{ item.type }}</div>
    <div class="col bar-cell">
      <div class="bar" :style="{ width: Math.max(item.pct, 0.5) + '%', background: typeColor(item.type) }" />
    </div>
    <div class="breakdown-count text-right">{{ formatNumber(item.count) }}</div>
    <div class="breakdown-pct text-right text-grey-7">{{ formatPct(item.pct) }}</div>
  </div>
</q-card-section>
        </q-card>
      </div>
    </div>
  </div>
</template>

<script>
import EChart from "./EChart.vue";
import { escapeHtml, formatNumber } from "../../utils/format";
import { baseOption, formatPct, valueAxis } from "../../utils/analysis";

const STORY_ICONS = {
  headline: { icon: "fas fa-info-circle", color: "blue-grey-6" },
  types: { icon: "fas fa-tags", color: "blue-grey-6" },
  driver: { icon: "fas fa-bullseye", color: "red-7" },
  time: { icon: "fas fa-clock", color: "purple-6" },
  unrelated: { icon: "fas fa-minus-circle", color: "grey-6" },
  none: { icon: "fas fa-question-circle", color: "blue-grey-6" },
  note: { icon: "fas fa-exclamation-triangle", color: "orange-8" },
  combination: { icon: "fas fa-link", color: "deep-orange-6" },
  magnitude: { icon: "fas fa-ruler-horizontal", color: "orange-8" },
};
// As ResultBreakdown.
const TYPE_COLORS = { Loss: "#e53935", Discrepancy: "#fb8c00", Duplicate: "#8e24aa" };
const SHOWN = 15;

// The story of a discrepancy analysis, its attributes ranked, and the split by result type of a reconciliation.
export default {
  name: "DiscrepancySummary",
  components: { EChart },
  props: {
    report: { type: Object, required: true },
  },
  emits: ["show-attribute", "show-rows", "result-type"],
  computed: {
    // The best feature of each column, strongest first.
    ranking() {
      const seen = new Set();
      return this.report.attributes.filter((item) => !seen.has(item.column) && seen.add(item.column)).slice(0, SHOWN);
    },
    rankingOption() {
      const items = [...this.ranking].reverse();
      const label = (item) => (["value", "decile"].includes(item.feature) ? item.column : `${item.column} · ${item.feature_label.toLowerCase()}`);
      return baseOption({
        grid: { left: 8, right: 24, top: 24, bottom: 4 },
        legend: { top: 0, textStyle: { fontSize: 11 } },
        tooltip: {
trigger: "axis",
formatter: (points) => {
  const item = items[points[0].dataIndex];
  const special = item.special.length ? `<br/>${item.special.length} over-represented bin${item.special.length > 1 ? "s" : ""}` : "";
  return `<b>${escapeHtml(label(item))}</b><br/>Explained ${formatPct(item.score * 100)}<br/>φK ${item.phik === null ? "–" : item.phik.toFixed(2)}${special}`;
},
        },
        xAxis: valueAxis({ max: (value) => Math.max(0.1, Math.ceil(value.max * 10) / 10) }),
        yAxis: { type: "category", data: items.map(label), axisLabel: { fontSize: 11 } },
        series: [
{ name: "Explained", type: "bar", data: items.map((item) => item.score), itemStyle: { color: "#e53935" }, cursor: "pointer", barGap: "10%" },
{ name: "φK", type: "bar", data: items.map((item) => item.phik), itemStyle: { color: "#90a4ae" }, cursor: "pointer" },
        ],
      });
    },
    typeSplit() {
      const split = this.report.type_split || [];
      const total = split.reduce((sum, item) => sum + item.count, 0);
      return split.map((item) => ({ ...item, pct: total ? (item.count / total) * 100 : 0 }));
    },
  },
  methods: {
    formatNumber,
    formatPct,
    storyIcon(kind) {
      return STORY_ICONS[kind] || STORY_ICONS.headline;
    },
    typeColor(type) {
      return TYPE_COLORS[type] || "#90a4ae";
    },
    // The filters of the bins a sentence names.
    storyFilters(item) {
      const attribute = this.report.attributes.find((candidate) => candidate.id === item.attribute);
      if (!attribute) {
        return [];
      }
      return attribute.bins.filter((bin) => (item.codes || []).includes(bin.code) && bin.filter && bin.filter.result).map((bin) => bin.filter);
    },
    // The filter of the finding (a combination) a sentence is about.
    findingFilter(item) {
      if (!item.finding) {
        return null;
      }
      const finding = (this.report.findings || []).find((candidate) => candidate.id === item.finding);
      if (finding) {
        return finding.filter;
      }
      const combination = (this.report.combinations || []).find((candidate) => candidate.id === item.finding);
      return combination ? combination.filter : null;
    },
    selectBar(event) {
      const items = [...this.ranking].reverse();
      const item = items[event.dataIndex];
      if (item) {
        this.$emit("show-attribute", item.id);
      }
    },
  },
};
</script>

<style scoped>
.header {
  background: var(--rapo-surface-alt);
}

.story-line {
  font-size: 14px;
  line-height: 1.5;
}

.story-icon {
  margin-top: 3px;
}

.breakdown-row {
  font-size: 13px;
  height: 24px;
  border-radius: 3px;
}

.breakdown-row:hover {
  background: var(--rapo-teal-soft);
}

.breakdown-label {
  width: 35%;
  padding-right: 8px;
}

.bar-cell {
  height: 12px;
}

.bar {
  height: 100%;
  border-radius: 2px;
}

.breakdown-count {
  width: 64px;
}

.breakdown-pct {
  width: 56px;
}
</style>
