<template>
  <div>
    <chart-legend v-if="legend.length > 1" :items="legend" :toggle="false" />
    <dashboard-chart :option="option" :height="rows.length * rowHeight + 8" @select="select" />
  </div>
</template>

<script>
import ChartLegend from "./ChartLegend.vue";
import DashboardChart from "./DashboardChart.vue";
import { escapeHtml, formatNumber } from "../../utils/format";
import { paletteColor, tokenColor } from "../../utils/palette";

// A ranking as horizontal bars, one row per name (top first), each bar made of segments (e.g. errors and the other
// runs) with a text at its end; a click on a bar picks its row.
export default {
  name: "BarList",
  components: { ChartLegend, DashboardChart },
  props: {
    // [{key, label, text, segments: [values in the order of `parts`], colors?: [Quasar names], title?}]
    rows: { type: Array, required: true },
    // [{key, label, color (Quasar name)}]: what the segments are.
    parts: { type: Array, required: true },
    rowHeight: { type: Number, default: 26 },
    labelWidth: { type: Number, default: 150 },
    format: { type: Function, default: (value) => formatNumber(value) },
  },
  emits: ["pick"],
  computed: {
    legend() {
      return this.parts.map((part) => ({ key: part.key, label: part.label, color: part.color }));
    },
    option() {
      const last = this.parts.length - 1;
      return {
        animation: false,
        grid: { left: 4, right: 64, top: 2, bottom: 2, containLabel: true },
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, confine: true, formatter: this.tooltip },
        xAxis: { type: "value", show: false },
        yAxis: {
          type: "category",
          inverse: true,
          data: this.rows.map((row) => row.label),
          axisTick: { show: false },
          axisLine: { show: false },
          axisLabel: { fontSize: 13, color: tokenColor("rapo-strong"), width: this.labelWidth, overflow: "truncate" },
        },
        series: this.parts.map((part, index) => ({
          name: part.label,
          type: "bar",
          stack: "row",
          barMaxWidth: 14,
          cursor: "pointer",
          itemStyle: { color: paletteColor(part.color), borderRadius: index === last ? [0, 3, 3, 0] : 0 },
          // A row may color its segments itself (`colors`), e.g. by control type.
          data: this.rows.map((row) => (row.colors && row.colors[index] ? { value: row.segments[index] || 0, itemStyle: { color: paletteColor(row.colors[index]) } } : row.segments[index] || 0)),
          label:
            index === last
              ? { show: true, position: "right", fontSize: 13, fontWeight: 600, color: tokenColor("rapo-header-text"), textBorderWidth: 0, formatter: (item) => this.rows[item.dataIndex].text }
              : { show: false },
        })),
      };
    },
  },
  methods: {
    tooltip(items) {
      const row = this.rows[items[0].dataIndex];
      const lines = [`<b>${escapeHtml(row.label)}</b>`];
      this.parts.forEach((part, index) => {
        if (row.segments[index]) {
          lines.push(`${escapeHtml(part.label)} <b>${escapeHtml(this.format(row.segments[index]))}</b>`);
        }
      });
      if (row.title) {
        lines.push(escapeHtml(row.title));
      }
      return lines.join("<br/>");
    },
    select(event) {
      const row = this.rows[event.dataIndex];
      if (row) {
        this.$emit("pick", { key: row.key });
      }
    },
  },
};
</script>
