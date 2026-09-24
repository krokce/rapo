<template>
  <div v-if="!correlations">
    <q-skeleton type="rect" height="40px" class="q-mb-md" />
    <q-skeleton type="rect" height="420px" />
  </div>
  <div v-else>
    <div class="row items-center q-gutter-md q-mb-md">
      <q-btn-toggle v-model="method" no-caps unelevated toggle-color="blue-grey-7" color="grey-3" text-color="grey-8" :options="methodOptions" />
      <div class="text-caption text-grey-7 col">{{ methodHelp }}</div>
    </div>
    <div v-if="correlations.sampled" class="text-caption text-grey-7 q-mb-sm">
      Measured on the first {{ formatNumber(correlations.rows) }} rows of the sample.
    </div>
    <div class="row q-col-gutter-lg">
      <div class="col-12 col-lg-8">
        <div v-if="matrix.columns.length < 2" class="text-grey-7 q-pa-lg text-center">{{ emptyText }}</div>
        <e-chart v-else :option="heatmapOption" :height="heatmapHeight" />
      </div>
      <div class="col-12 col-lg-4">
        <div class="text-subtitle1 text-blue-grey-9 q-mb-sm">Strongest pairs</div>
        <div v-if="!correlations.pairs.length" class="text-grey-7">No pair of columns could be measured.</div>
        <q-list v-else dense bordered separator class="rounded-borders">
          <q-item v-for="(pair, index) in correlations.pairs" :key="index">
            <q-item-section>
              <q-item-label class="text-weight-medium">{{ pair.a.toUpperCase() }} · {{ pair.b.toUpperCase() }}</q-item-label>
              <q-item-label caption>{{ methodLabel(pair.method) }}</q-item-label>
            </q-item-section>
            <q-item-section side>
              <q-chip dense square :color="strengthColor(pair.value)" text-color="white" class="text-weight-bold">{{ pair.value.toFixed(2) }}</q-chip>
            </q-item-section>
          </q-item>
        </q-list>
      </div>
    </div>
  </div>
</template>

<script>
import EChart from "./EChart.vue";
import { formatNumber } from "../../utils/format";

const METHODS = {
  pearson: { label: "Pearson", help: "Linear relation between numeric columns, from -1 to 1." },
  spearman: { label: "Spearman", help: "Monotonic relation between numeric columns, by rank, from -1 to 1; robust to outliers." },
  cramers: {
    label: "Cramér's V",
    help: "Association between columns with few distinct values (2 to 50), from 0 to 1. Nearly unique columns are left out.",
  },
};

export default {
  name: "AnalysisCorrelations",
  components: { EChart },
  props: {
    correlations: { type: Object, default: null },
  },
  data() {
    return { method: "pearson" };
  },
  computed: {
    methodOptions() {
      return Object.entries(METHODS).map(([value, method]) => ({ label: `${method.label} (${this.correlations[value].columns.length})`, value }));
    },
    methodHelp() {
      return METHODS[this.method].help;
    },
    matrix() {
      return this.correlations[this.method];
    },
    emptyText() {
      return this.method === "cramers" ? "Fewer than two columns have a few distinct values." : "Fewer than two numeric columns vary in the sample.";
    },
    heatmapHeight() {
      return Math.min(Math.max(320, 120 + this.matrix.columns.length * 26), 1100);
    },
    heatmapOption() {
      const names = this.matrix.columns.map((name) => name.toUpperCase());
      const data = [];
      this.matrix.matrix.forEach((row, y) => row.forEach((value, x) => data.push([x, y, value === null ? "-" : value])));
      const signed = this.method !== "cramers";
      return {
        animation: false,
        grid: { left: 8, right: 16, top: 8, bottom: 60, containLabel: true },
        tooltip: {
          formatter: (item) => {
            const value = item.value[2];
            return `${names[item.value[1]]} · ${names[item.value[0]]}<br/><b>${value === "-" ? "not measured" : Number(value).toFixed(3)}</b>`;
          },
        },
        xAxis: { type: "category", data: names, axisLabel: { rotate: 45, fontSize: 10, interval: 0 }, splitArea: { show: true } },
        yAxis: { type: "category", data: names, axisLabel: { fontSize: 10, interval: 0 }, inverse: true, splitArea: { show: true } },
        visualMap: {
          min: signed ? -1 : 0,
          max: 1,
          calculable: true,
          orient: "horizontal",
          left: "center",
          bottom: 0,
          itemHeight: 160,
          inRange: { color: signed ? ["#1e88e5", "#f5f5f5", "#e53935"] : ["#f5f5f5", "#6a1b9a"] },
          textStyle: { fontSize: 10 },
        },
        series: [
          {
            type: "heatmap",
            data,
            label: { show: names.length <= 14, fontSize: 9, formatter: (item) => (item.value[2] === "-" ? "" : Number(item.value[2]).toFixed(2)) },
            progressive: 0,
          },
        ],
      };
    },
  },
  watch: {
    // Opens on the first method that has something to show.
    correlations: {
      immediate: true,
      handler(correlations) {
        if (correlations && correlations[this.method].columns.length < 2) {
          const method = Object.keys(METHODS).find((key) => correlations[key].columns.length >= 2);
          if (method) {
            this.method = method;
          }
        }
      },
    },
  },
  methods: {
    formatNumber,
    methodLabel(method) {
      return METHODS[method].label;
    },
    strengthColor(value) {
      const strength = Math.abs(value);
      return strength >= 0.9 ? "red-7" : strength >= 0.7 ? "orange-8" : strength >= 0.4 ? "amber-8" : "blue-grey-4";
    },
  },
};
</script>
