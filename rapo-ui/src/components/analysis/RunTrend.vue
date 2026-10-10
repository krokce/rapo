<template>
  <q-card flat bordered class="run-trend">
    <q-card-section class="q-py-xs">
      <div class="row items-center text-caption text-grey-7">
        <span>{{ caption }}</span>
        <q-space />
        <span v-if="trend && trend.runs.length > 1" class="legend row items-center no-wrap">
          <span class="swatch" :style="{ background: barColor }" />{{ barLabel }}
          <template v-if="lineLabel"><span class="swatch swatch--line q-ml-md" :style="{ background: lineColor }" />{{ lineLabel }}</template>
        </span>
      </div>
      <q-skeleton v-if="!trend && !failed" type="rect" :height="`${height}px`" />
      <div v-else-if="!trend" class="row items-center q-gutter-sm text-grey-7 trend-note" :style="{ height: `${height}px` }">
        <q-icon name="fas fa-exclamation-triangle" color="red-6" />
        <div>The run trend could not be loaded.</div>
        <q-btn flat dense no-caps color="primary" label="Retry" @click="load" />
      </div>
      <div v-else-if="trend.runs.length < 2" class="row items-center text-grey-7 trend-note" :style="{ height: `${height}px` }">
        <q-icon name="fas fa-history" class="q-mr-sm" />No finished run of the control for another day.
      </div>
      <e-chart v-else :option="option" :height="height" @select="select" />
    </q-card-section>
  </q-card>
</template>

<script>
import { Dark } from "quasar";
import EChart from "./EChart.vue";
import { api, notifyError } from "../../api";
import { formatNumber, toDateTimeString } from "../../utils/format";
import { baseOption, formatPct, valueAxis } from "../../utils/analysis";

const DAYS = 30;

// The counts of the dataset's side over the control's last 30 days, one bar per day (per window) by its last finished
// run, from the run log only; the run itself is marked. `target` data: what was fetched, with the discrepancies as a
// line; discrepancy: the discrepancies, with their rate of the fetched records. A click opens the same view of that run.
export default {
  name: "RunTrend",
  components: { EChart },
  props: {
    processId: { type: Number, required: true },
    dataset: { type: String, required: true },
    reportOnly: { type: Boolean, default: false },
    target: { type: String, default: "data" },
    height: { type: Number, default: 96 },
  },
  data() {
    return { trend: null, failed: false };
  },
  computed: {
    discrepancyTarget() {
      return this.target === "discrepancy";
    },
    caption() {
      if (!this.trend || this.trend.runs.length < 2) {
        return `Last ${DAYS} days`;
      }
      return `Last ${this.trend.runs.length} days${this.trend.side ? `, side ${this.trend.side}` : ""}`;
    },
    barLabel() {
      return this.discrepancyTarget ? "Discrepancies" : "Fetched";
    },
    lineLabel() {
      if (this.reportOnly && !this.discrepancyTarget) {
        return "";
      }
      return this.discrepancyTarget ? "Rate of fetched" : "Discrepancies";
    },
    barColor() {
      return this.discrepancyTarget ? "var(--rapo-disc)" : "var(--rapo-normal)";
    },
    lineColor() {
      return this.discrepancyTarget ? "var(--rapo-strong)" : "var(--rapo-disc)";
    },
    option() {
      const dark = Dark.isActive;
      const disc = dark ? "#ef5350" : "#e53935";
      const normal = dark ? "#78909c" : "#90a4ae";
      const strong = dark ? "#cfd8dc" : "#455a64";
      const runs = this.trend.runs;
      const current = runs.findIndex((run) => run.process_id === this.processId);
      const mark = (value, index, color) => (index === current ? { value, itemStyle: { color, borderColor: dark ? "#eceff1" : "#263238", borderWidth: 2 } } : value);
      const rate = (run) => (run.fetched ? Math.round(((run.discrepancies || 0) * 10000) / run.fetched) / 100 : null);
      const series = this.discrepancyTarget
        ? [
            { name: "Discrepancies", type: "bar", data: runs.map((run, index) => mark(run.discrepancies || 0, index, disc)), itemStyle: { color: disc }, cursor: "pointer" },
            { name: "Rate", type: "line", yAxisIndex: 1, data: runs.map(rate), itemStyle: { color: strong }, lineStyle: { width: 1.5 }, symbolSize: 4, cursor: "pointer" },
          ]
        : [{ name: "Fetched", type: "bar", data: runs.map((run, index) => mark(run.fetched || 0, index, normal)), itemStyle: { color: normal }, cursor: "pointer" }];
      if (!this.discrepancyTarget && !this.reportOnly) {
        series.push({ name: "Discrepancies", type: "line", yAxisIndex: 1, data: runs.map((run) => run.discrepancies || 0), itemStyle: { color: disc }, lineStyle: { width: 1.5 }, symbolSize: 4, cursor: "pointer" });
      }
      return baseOption({
        grid: { left: 4, right: 4, top: 8, bottom: 2 },
        tooltip: {
          trigger: "axis",
          formatter: (items) => {
            const run = runs[items[0].dataIndex];
            const lines = [`PID ${run.process_id}`, `${toDateTimeString(run.date_from)} – ${toDateTimeString(run.date_to)}`, `Fetched <b>${formatNumber(run.fetched || 0)}</b>`];
            if (!this.reportOnly) {
              lines.push(`Discrepancies <b>${formatNumber(run.discrepancies || 0)}</b>${run.fetched ? ` (${formatPct(rate(run))})` : ""}`);
            }
            return lines.join("<br/>");
          },
        },
        xAxis: { type: "category", data: runs.map((run) => this.runLabel(run)), axisLabel: { fontSize: 10, hideOverlap: true }, axisTick: { show: false } },
        yAxis: [
          valueAxis({ axisLabel: { show: false }, splitLine: { show: false } }),
          valueAxis({ axisLabel: { show: false }, splitLine: { show: false } }),
        ],
        series,
      });
    },
  },
  watch: {
    processId: {
      immediate: true,
      handler() {
        this.load();
      },
    },
  },
  methods: {
    async load() {
      this.failed = false;
      try {
        this.trend = await api("get-control-trend", {
          params: { process_id: this.processId, dataset: this.dataset, limit: DAYS },
          loadingBar: false,
        });
      } catch (error) {
        this.failed = true;
        notifyError("The run trend could not be loaded.", error);
      }
    },
    runLabel(run) {
      const from = toDateTimeString(run.date_from);
      const to = toDateTimeString(run.date_to);
      return from.substring(0, 10) === to.substring(0, 10) ? from.substring(5, 10) : `${from.substring(5, 10)}–${to.substring(5, 10)}`;
    },
    select(event) {
      const run = this.trend.runs[event.dataIndex];
      if (!run || run.process_id === this.processId) {
        return;
      }
      if (this.discrepancyTarget) {
        this.$router.push({ name: "discrepancy-analysis", params: { processId: run.process_id, side: this.dataset.split("_")[1] } });
      } else {
        this.$router.push({ name: "data-analysis", params: { processId: run.process_id, dataset: this.dataset } });
      }
    },
  },
};
</script>

<style scoped>
.legend {
  gap: 4px;
}

.swatch {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  margin-right: 4px;
}

.swatch--line {
  height: 2px;
}

.trend-note {
  font-size: 13px;
}
</style>
