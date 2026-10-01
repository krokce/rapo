<template>
  <div>
    <div class="text-caption text-grey-7 q-mb-sm">
      The share of the discrepancies each finding held in the previous finished runs of the control still in its result table (the fetched records
      are not read again). New: it stands out in this run only; growing: more than before; not new: about as before. Click a run for its analysis.
    </div>
    <div v-if="!history || !history.runs.length" class="state-notice">
      <q-icon name="fas fa-history" />
      <div>{{ history && history.error ? `The previous runs could not be read: ${history.error}` : "There is no previous run to compare with." }}</div>
    </div>
    <template v-else>
      <q-card flat bordered class="q-mb-md">
        <q-card-section>
          <e-chart :option="option" :height="280" @select="openRun" />
        </q-card-section>
      </q-card>
      <q-markup-table dense flat bordered class="history-table">
        <thead>
          <tr class="bg-blue-grey-2">
            <th title="The finding: a bin of an attribute, or a pair of bins" class="text-left">Finding</th>
            <th title="Share of this run's discrepancies in it" class="text-right">This run</th>
            <th title="Average share in the previous runs" class="text-right">Before</th>
            <th title="New, growing or not new" class="text-left">Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(finding, index) in history.findings" :key="finding.finding">
            <td>
              <span class="legend-dot" :style="{ background: color(index) }" />
              <a class="attribute-link" v-keyboard:button @click="$emit('show-attribute', finding.attribute)">{{ finding.label }}</a>
            </td>
            <td class="text-right number-cell">{{ formatPct(finding.shares[finding.shares.length - 1] * 100) }}</td>
            <td class="text-right number-cell">{{ finding.before === null ? "–" : formatPct(finding.before * 100) }}</td>
            <td>
              <q-chip dense square size="sm" :color="status(finding).color" :text-color="chipTextColor(status(finding).color)" class="text-weight-bold">
                {{ status(finding).label }}
              </q-chip>
              <span v-if="finding.since && finding.since !== currentPid" class="text-caption text-grey-7">since PID {{ finding.since }}</span>
            </td>
          </tr>
        </tbody>
      </q-markup-table>
    </template>
  </div>
</template>

<script>
import EChart from "./EChart.vue";
import { escapeHtml, formatNumber, toDateTimeString } from "../../utils/format";
import { baseOption, chipTextColor, formatPct, valueAxis } from "../../utils/analysis";

const COLORS = ["#e53935", "#8e24aa", "#1e88e5", "#fb8c00", "#43a047"];
const STATUSES = {
  new: { label: "New", color: "red-7" },
  growing: { label: "Growing", color: "orange-8" },
  chronic: { label: "Not new", color: "blue-grey-4" },
  single: { label: "No history", color: "blue-grey-4" },
};

// The findings of a discrepancy analysis over the control's previous runs: their share of each run's discrepancies.
export default {
  name: "DiscrepancyHistory",
  components: { EChart },
  props: {
    report: { type: Object, required: true },
  },
  emits: ["show-attribute", "open-run"],
  computed: {
    history() {
      return this.report.history;
    },
    currentPid() {
      return this.report.meta.process_id;
    },
    option() {
      const runs = this.history.runs;
      const labels = runs.map((run) => `${toDateTimeString(run.date_from).substring(0, 10)}\n${run.process_id}`);
      return baseOption({
        grid: { left: 8, right: 24, top: 16, bottom: 4 },
        tooltip: {
          trigger: "axis",
          formatter: (points) => {
            const run = runs[points[0].dataIndex];
            const lines = points.map((point) => {
              const finding = this.history.findings[point.seriesIndex];
              return `${point.marker}${escapeHtml(finding.label)}: <b>${formatPct(point.value)}</b> (${formatNumber(finding.counts[point.dataIndex])})`;
            });
            return `PID ${run.process_id} · ${formatNumber(run.total)} discrepancies<br/>${lines.join("<br/>")}`;
          },
        },
        xAxis: { type: "category", data: labels, axisLabel: { fontSize: 10 } },
        yAxis: valueAxis({ axisLabel: { formatter: "{value}%" } }),
        series: this.history.findings.map((finding, index) => ({
          name: finding.label,
          type: "line",
          data: finding.shares.map((share) => Math.round(share * 1000) / 10),
          itemStyle: { color: this.color(index) },
          symbolSize: (value, params) => (runs[params.dataIndex].process_id === this.currentPid ? 10 : 5),
          cursor: "pointer",
        })),
      });
    },
  },
  methods: {
    formatPct,
    chipTextColor,
    color(index) {
      return COLORS[index % COLORS.length];
    },
    status(finding) {
      return STATUSES[finding.status] || STATUSES.single;
    },
    openRun(event) {
      const run = this.history.runs[event.dataIndex];
      if (run && run.process_id !== this.currentPid) {
        this.$emit("open-run", run.process_id);
      }
    },
  },
};
</script>

<style scoped>
.history-table {
  max-width: 1100px;
}

.legend-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 6px;
}

.attribute-link {
  color: var(--rapo-teal);
  cursor: pointer;
}

.attribute-link:hover {
  text-decoration: underline;
}
</style>
