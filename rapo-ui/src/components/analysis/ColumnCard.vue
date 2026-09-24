<template>
  <q-card flat bordered class="column-card" :class="{ 'column-card--focus': focused }">
    <q-card-section class="row items-center no-wrap q-py-sm header">
      <q-avatar size="26px" :icon="kind.icon" :color="kind.color" text-color="white" font-size="13px" class="q-mr-sm" :title="kind.label" />
      <div class="text-weight-bold text-blue-grey-10 ellipsis column-name" :title="column.name.toUpperCase()">{{ column.name.toUpperCase() }}</div>
      <div class="text-caption text-grey-6 q-ml-sm text-no-wrap">{{ dbType }} · {{ kind.label }}</div>
      <q-space />
      <div class="row no-wrap q-gutter-xs alert-chips">
        <q-chip
          v-for="alert in column.alerts"
          :key="alert.code"
          dense
          square
          size="sm"
          :color="alert.level === 'warning' ? 'orange-1' : 'grey-3'"
          :text-color="alert.level === 'warning' ? 'orange-10' : 'grey-8'"
          :title="alert.message">
          {{ alertLabel(alert.code) }}
        </q-chip>
      </div>
    </q-card-section>
    <q-separator />
    <q-card-section class="row q-col-gutter-md q-py-sm">
      <div class="col-12 col-md-3">
        <table class="stat-table">
          <tbody>
            <tr v-for="item in summaryStats" :key="item.label" :class="{ 'cursor-pointer link-row': item.filters }" @click="item.filters && $emit('show-rows', item.filters)">
              <td class="text-grey-7">{{ item.label }}</td>
              <td class="text-right text-weight-medium" :class="item.warn ? 'text-orange-9' : 'text-blue-grey-9'">{{ item.value }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="col-12 col-md-5">
        <div class="text-caption text-grey-7">{{ chartTitle }}</div>
        <e-chart v-if="chartOption" :option="chartOption" :height="170" @select="selectBin" />
        <div v-else class="text-grey-5 q-pa-md text-center">No values to chart</div>
      </div>
      <div class="col-12 col-md-4">
        <div class="text-caption text-grey-7">Most frequent values</div>
        <div
          v-for="item in topValues"
          :key="item.key"
          class="freq-row row no-wrap items-center cursor-pointer"
          :title="`${item.label}: ${formatNumber(item.count)} (${formatPct(item.pct)})`"
          @click="$emit('show-rows', [item.filter])">
          <div class="freq-label ellipsis" :class="{ 'text-italic text-grey-6': item.muted }">{{ item.label }}</div>
          <div class="col freq-bar-cell">
            <div class="freq-bar" :class="item.muted ? 'bg-grey-4' : 'bg-blue-grey-3'" :style="{ width: Math.max(item.share, 0.5) + '%' }" />
          </div>
          <div class="freq-count text-right text-grey-8">{{ formatNumber(item.count) }}</div>
        </div>
        <div v-if="column.other_count" class="freq-row row no-wrap items-center text-grey-6 text-italic">
          <div class="freq-label">Other values ({{ formatNumber(column.distinct - column.top.length) }})</div>
          <div class="col" />
          <div class="freq-count text-right">{{ formatNumber(column.other_count) }}</div>
        </div>
      </div>
    </q-card-section>
    <q-expansion-item v-if="hasDetails" v-model="expanded" dense dense-toggle switch-toggle-side label="Details" header-class="text-grey-8 details-header">
      <q-card-section class="row q-col-gutter-lg q-pt-none">
        <template v-if="column.kind === 'numeric' && column.stats">
          <div class="col-12 col-md-3">
            <div class="text-caption text-grey-7">Quantiles</div>
            <table class="stat-table">
              <tbody>
                <tr v-for="item in quantiles" :key="item.label">
                  <td class="text-grey-7">{{ item.label }}</td>
                  <td class="text-right">{{ formatStat(item.value, 4) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="col-12 col-md-3">
            <div class="text-caption text-grey-7">Descriptive statistics</div>
            <table class="stat-table">
              <tbody>
                <tr v-for="item in descriptive" :key="item.label">
                  <td class="text-grey-7">{{ item.label }}</td>
                  <td class="text-right">{{ formatStat(item.value, 4) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="col-12 col-md-3">
            <div class="text-caption text-grey-7">Smallest values</div>
            <extreme-list :items="column.smallest" :column="column.name" @show-rows="$emit('show-rows', $event)" />
          </div>
          <div class="col-12 col-md-3">
            <div class="text-caption text-grey-7">Largest values</div>
            <extreme-list :items="column.largest" :column="column.name" @show-rows="$emit('show-rows', $event)" />
          </div>
        </template>
        <template v-if="column.kind === 'datetime' && column.stats">
          <div v-if="column.hours" class="col-12 col-md-6">
            <div class="text-caption text-grey-7">Hour of day</div>
            <e-chart :option="hoursOption" :height="150" />
          </div>
          <div class="col-12 col-md-6">
            <div class="text-caption text-grey-7">Day of week</div>
            <e-chart :option="weekdaysOption" :height="150" />
          </div>
        </template>
      </q-card-section>
    </q-expansion-item>
  </q-card>
</template>

<script>
import { h } from "vue";
import EChart from "./EChart.vue";
import { formatNumber } from "../../utils/format";
import {
  HOURS,
  WEEKDAYS,
  binFilter,
  distributionOption,
  formatPct,
  formatStat,
  formatValue,
  histogramOption,
  kindInfo,
  valueFilter,
} from "../../utils/analysis";

const ALERT_LABELS = {
  empty: "Empty",
  constant: "Constant",
  unique: "Unique",
  missing: "Missing",
  some_missing: "Missing",
  high_cardinality: "High cardinality",
  imbalanced: "Imbalanced",
  zeros: "Zeros",
  skewed: "Skewed",
  blank: "Blank",
};

// The smallest or largest values of a numeric column, each a link to its rows.
const ExtremeList = {
  props: { items: { type: Array, default: () => [] }, column: { type: String, required: true } },
  emits: ["show-rows"],
  render() {
    return h(
      "table",
      { class: "stat-table" },
      h(
        "tbody",
        this.items.map((item) =>
          h("tr", { class: "cursor-pointer link-row", onClick: () => this.$emit("show-rows", [valueFilter(this.column, item.value)]) }, [
            h("td", {}, formatStat(item.value, 4)),
            h("td", { class: "text-right text-grey-7" }, `× ${formatNumber(item.count)}`),
          ])
        )
      )
    );
  },
};

export default {
  name: "ColumnCard",
  components: { EChart, ExtremeList },
  props: {
    column: { type: Object, required: true },
    dbType: { type: String, default: "" },
    rows: { type: Number, default: 0 },
    focused: { type: Boolean, default: false },
  },
  emits: ["show-rows"],
  data() {
    return { expanded: false };
  },
  computed: {
    kind() {
      return kindInfo(this.column);
    },
    dateOnly() {
      return Boolean(this.column.stats && this.column.stats.date_only);
    },
    summaryStats() {
      const c = this.column;
      const s = c.stats || {};
      const items = [
        { label: "Distinct", value: `${formatNumber(c.distinct)} (${formatPct(c.distinct_pct)})` },
        {
          label: "Missing",
          value: `${formatNumber(c.missing)} (${formatPct(c.missing_pct)})`,
          warn: c.missing_pct >= 20,
          filters: c.missing ? [{ column: c.name, op: "null" }] : null,
        },
      ];
      if (c.kind === "numeric" && c.stats) {
        items.push(
          { label: "Mean", value: formatStat(s.mean) },
          { label: "Median", value: formatStat(s.median) },
          { label: "Minimum", value: formatStat(s.min) },
          { label: "Maximum", value: formatStat(s.max) },
          { label: "Zeros", value: `${formatNumber(s.zeros)} (${formatPct(s.zeros_pct)})`, filters: s.zeros ? [valueFilter(c.name, 0)] : null },
          {
            label: "Negative",
            value: `${formatNumber(s.negatives)} (${formatPct(s.negatives_pct)})`,
            filters: s.negatives ? [{ column: c.name, kind: "numeric", op: "range", value: { min: null, max: 0, max_inclusive: false } }] : null,
          }
        );
      } else if (c.kind === "datetime" && c.stats) {
        items.push(
          { label: "Minimum", value: formatValue(s.min, "datetime", this.dateOnly) },
          { label: "Maximum", value: formatValue(s.max, "datetime", this.dateOnly) },
          { label: "Range", value: `${formatStat(s.range_days, 2)} days` }
        );
      } else if (c.stats) {
        items.push(
          { label: "Length min / max", value: `${s.min_length} / ${s.max_length}` },
          { label: "Length mean", value: formatStat(s.mean_length, 1) },
          { label: "Blank", value: `${formatNumber(s.blank)} (${formatPct(s.blank_pct)})` }
        );
      }
      return items;
    },
    chartTitle() {
      if (this.column.kind === "text") {
        return "Length of the values";
      }
      return this.column.kind === "datetime" ? "Distribution over time" : "Histogram";
    },
    chartOption() {
      const histogram = this.column.histogram;
      if (!histogram || !histogram.counts.length) {
        return null;
      }
      const colors = { numeric: "#5c6bc0", datetime: "#8e24aa", text: "#26a69a" };
      return histogramOption(histogram, this.column.kind === "text" ? "numeric" : this.column.kind, colors[this.column.kind]);
    },
    topValues() {
      const c = this.column;
      const max = Math.max(...c.top.map((item) => item.count), c.missing, 1);
      const items = c.top.map((item, index) => ({
        key: `v${index}`,
        label: item.value === "" ? "(blank)" : formatValue(item.value, c.kind, this.dateOnly),
        count: item.count,
        pct: item.pct,
        share: (item.count * 100) / max,
        filter: valueFilter(c.name, item.value),
      }));
      if (c.missing) {
        items.push({
          key: "missing",
          label: "(missing)",
          muted: true,
          count: c.missing,
          pct: c.missing_pct,
          share: (c.missing * 100) / max,
          filter: { column: c.name, op: "null" },
        });
      }
      return items;
    },
    hasDetails() {
      return (this.column.kind === "numeric" || this.column.kind === "datetime") && Boolean(this.column.stats);
    },
    quantiles() {
      const s = this.column.stats;
      return [
        { label: "Minimum", value: s.min },
        { label: "5th percentile", value: s.q05 },
        { label: "Q1", value: s.q25 },
        { label: "Median", value: s.median },
        { label: "Q3", value: s.q75 },
        { label: "95th percentile", value: s.q95 },
        { label: "Maximum", value: s.max },
        { label: "Range", value: s.range },
        { label: "Interquartile range", value: s.iqr },
      ];
    },
    descriptive() {
      const s = this.column.stats;
      return [
        { label: "Mean", value: s.mean },
        { label: "Standard deviation", value: s.std },
        { label: "Coefficient of variation", value: s.cv },
        { label: "Median absolute deviation", value: s.mad },
        { label: "Skewness", value: s.skew },
        { label: "Kurtosis", value: s.kurtosis },
        { label: "Sum", value: s.sum },
      ];
    },
    hoursOption() {
      return distributionOption(HOURS, this.column.hours || []);
    },
    weekdaysOption() {
      return distributionOption(WEEKDAYS, this.column.weekdays || []);
    },
  },
  methods: {
    formatNumber,
    formatPct,
    formatStat,
    alertLabel(code) {
      return ALERT_LABELS[code] || code;
    },
    // A histogram bar selects its rows; text length bins have no filter.
    selectBin(event) {
      if (this.column.kind === "text" || !this.column.histogram) {
        return;
      }
      this.$emit("show-rows", [binFilter(this.column.name, this.column.kind, this.column.histogram.edges, event.dataIndex)]);
    },
  },
};
</script>

<style scoped>
.column-card {
  transition: box-shadow 0.3s;
}

.column-card--focus {
  box-shadow: 0 0 0 2px #009688;
}

.header {
  background: #f5f7f8;
}

.column-name {
  font-size: 15px;
  max-width: 45%;
}

.alert-chips {
  overflow: hidden;
}

.stat-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.stat-table :deep(td) {
  padding: 3px 4px;
  border-bottom: 1px solid #eceff1;
}

.stat-table :deep(.link-row:hover) {
  background: #e0f2f1;
}

.freq-row {
  font-size: 13px;
  height: 22px;
  border-radius: 3px;
}

.freq-row.cursor-pointer:hover {
  background: #e0f2f1;
}

.freq-label {
  width: 42%;
  padding: 0 6px 0 2px;
}

.freq-bar-cell {
  height: 12px;
}

.freq-bar {
  height: 100%;
  border-radius: 2px;
}

.freq-count {
  width: 64px;
  padding-left: 6px;
}

.details-header {
  font-size: 13px;
}
</style>
