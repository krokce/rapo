<template>
  <q-card flat bordered>
    <q-card-section class="row items-center q-py-sm">
      <div class="text-subtitle1 text-blue-grey-9">Run trend</div>
      <div class="text-caption text-grey-7 q-ml-md">
        {{ caption }}
      </div>
      <q-space />
      <q-btn-toggle v-model="limit" dense no-caps unelevated size="sm" toggle-color="blue-grey-7" color="grey-3" text-color="grey-8" :options="limitOptions" />
    </q-card-section>
    <q-card-section class="q-pt-none">
      <q-skeleton v-if="!trend" type="rect" height="200px" />
      <div v-else-if="trend.runs.length < 2" class="text-grey-7 q-pa-md">The control has no finished run for another day.</div>
      <e-chart v-else :option="option" :height="220" @select="select" />
    </q-card-section>
  </q-card>
</template>

<script>
import EChart from "./EChart.vue";
import { api, notifyError } from "../../api";
import { formatNumber, toDateTimeString } from "../../utils/format";

// The counts of the dataset's side over the control's latest days, one point per day (per window) by its last
// finished run, from the run log only. A click on a run opens the same dataset of that run.
export default {
  name: "RunTrend",
  components: { EChart },
  props: {
    processId: { type: Number, required: true },
    dataset: { type: String, required: true },
    reportOnly: { type: Boolean, default: false },
  },
  data() {
    return { trend: null, limit: 30 };
  },
  computed: {
    limitOptions() {
      return [10, 30, 90].map((value) => ({ label: `${value} days`, value }));
    },
    caption() {
      if (!this.trend) {
        return "";
      }
      const side = this.trend.side ? ` of side ${this.trend.side}` : "";
      return `Fetched and discrepancy counts${side} of the last ${this.trend.runs.length} days, each by its last finished run. Click a run to analyse it.`;
    },
    option() {
      const runs = this.trend.runs;
      const labels = runs.map((run) => this.runLabel(run));
      const current = runs.findIndex((run) => run.process_id === this.processId);
      const highlight = (value, index) => (index === current ? { value, itemStyle: { color: "#009688" } } : value);
      const series = [
        { name: "Fetched", type: "bar", data: runs.map((run, index) => highlight(run.fetched, index)), itemStyle: { color: "#90a4ae" }, cursor: "pointer" },
      ];
      if (!this.reportOnly) {
        series.push({
          name: "Discrepancies",
          type: "line",
          yAxisIndex: 1,
          data: runs.map((run) => run.discrepancies),
          itemStyle: { color: "#e53935" },
          symbolSize: 7,
          cursor: "pointer",
        });
      }
      return {
        animation: false,
        grid: { left: 8, right: 8, top: 30, bottom: 4, containLabel: true },
        legend: { top: 0, left: "center", textStyle: { fontSize: 11 } },
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "shadow" },
          formatter: (items) => {
            const run = runs[items[0].dataIndex];
            const level = run.error_level === null || run.error_level === undefined ? "" : `<br/>Error level ${formatNumber(run.error_level, 2)}%`;
            return (
              `PID ${run.process_id}<br/>${toDateTimeString(run.date_from)} – ${toDateTimeString(run.date_to)}<br/>` +
              `Fetched <b>${formatNumber(run.fetched || 0)}</b>` +
              (this.reportOnly ? "" : `<br/>Discrepancies <b>${formatNumber(run.discrepancies || 0)}</b>${level}`)
            );
          },
        },
        xAxis: { type: "category", data: labels, axisLabel: { fontSize: 10, hideOverlap: true } },
        yAxis: [
          { type: "value", axisLabel: { fontSize: 10, color: "#78909c" }, splitLine: { lineStyle: { color: "#eceff1" } } },
          { type: "value", axisLabel: { fontSize: 10, color: "#e53935" }, splitLine: { show: false } },
        ],
        series,
      };
    },
  },
  watch: {
    processId: {
      immediate: true,
      handler() {
        this.load();
      },
    },
    limit() {
      this.load();
    },
  },
  methods: {
    async load() {
      try {
        this.trend = await api("get-control-trend", {
          params: { process_id: this.processId, dataset: this.dataset, limit: this.limit },
          loadingBar: false,
        });
      } catch (error) {
        notifyError("The run trend could not be loaded.", error);
      }
    },
    runLabel(run) {
      const from = toDateTimeString(run.date_from);
      const to = toDateTimeString(run.date_to);
      return from.substring(0, 10) === to.substring(0, 10) ? from.substring(0, 10) : `${from.substring(5, 10)}–${to.substring(5, 10)}`;
    },
    select(event) {
      const run = this.trend.runs[event.dataIndex];
      if (run && run.process_id !== this.processId) {
        this.$router.push({ name: "data-analysis", params: { processId: run.process_id, dataset: this.dataset } });
      }
    },
  },
};
</script>
