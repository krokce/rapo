<template>
  <div>
    <div class="text-caption text-grey-7 q-mb-sm">
      The share of the records that are discrepancies, per weekday and hour of each date column. Cells without records are blank; the discrepancy
      rate of the whole side is {{ formatPct(baseRate * 100) }}.
    </div>
    <div class="row q-col-gutter-md">
      <div v-for="heatmap in report.heatmaps" :key="heatmap.column" class="col-12 col-xl-6">
        <q-card flat bordered>
          <q-card-section class="q-py-sm">
            <div class="text-subtitle2 text-blue-grey-9">{{ heatmap.column }}</div>
          </q-card-section>
          <q-card-section class="q-pt-none">
            <e-chart :option="option(heatmap)" :height="260" />
          </q-card-section>
        </q-card>
      </div>
    </div>
  </div>
</template>

<script>
import { Dark } from "quasar";
import EChart from "./EChart.vue";
import { escapeHtml, formatNumber } from "../../utils/format";
import { HOURS, WEEKDAYS, baseOption, formatPct, liftText } from "../../utils/analysis";

// Weekday × hour heatmaps of the discrepancy rate of each date column of a discrepancy analysis.
export default {
  name: "DiscrepancyTimeBands",
  components: { EChart },
  props: {
    report: { type: Object, required: true },
  },
  computed: {
    baseRate() {
      const meta = this.report.meta;
      const total = (meta.discrepancies || 0) + (meta.normal || 0);
      return total ? meta.discrepancies / total : 0;
    },
  },
  methods: {
    formatPct,
    option(heatmap) {
      const cells = {};
      heatmap.cells.forEach((cell) => (cells[`${cell.weekday}|${cell.hour}`] = cell));
      const data = heatmap.cells.filter((cell) => cell.rate !== null).map((cell) => [cell.hour, cell.weekday, Math.round(cell.rate * 10000) / 100]);
      const top = Math.max(this.baseRate * 200, ...data.map((item) => item[2]), 1);
      const dark = Dark.isActive;
      return baseOption({
        grid: { left: 8, right: 16, top: 8, bottom: 56 },
        tooltip: {
          formatter: (item) => {
            const cell = cells[`${item.value[1]}|${item.value[0]}`];
            return (
              `${WEEKDAYS[cell.weekday]} ${HOURS[cell.hour]}:00 – ${HOURS[cell.hour]}:59<br/><b>${formatPct(cell.rate * 100)}</b> discrepancies` +
              `<br/>${formatNumber(cell.disc)} discrepancies, ${formatNumber(cell.normal)} normal<br/>Lift ${escapeHtml(liftText(cell.lift, "only discrepancies"))}`
            );
          },
        },
        xAxis: { type: "category", data: HOURS, splitArea: { show: true }, axisLabel: { fontSize: 10 } },
        yAxis: { type: "category", data: WEEKDAYS, inverse: true, splitArea: { show: true }, axisLabel: { fontSize: 10 } },
        visualMap: {
          min: 0,
          max: Math.min(100, Math.ceil(top)),
          calculable: true,
          orient: "horizontal",
          left: "center",
          bottom: 0,
          itemHeight: 160,
          inRange: { color: dark ? ["#2c3438", "#ef5350"] : ["#fafafa", "#c62828"] },
          text: ["more discrepancies", "fewer"],
          formatter: (value) => `${Math.round(value)}%`,
          textStyle: { fontSize: 10 },
        },
        series: [{ type: "heatmap", data, progressive: 0 }],
      });
    },
  },
};
</script>
