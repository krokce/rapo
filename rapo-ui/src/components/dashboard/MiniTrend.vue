<template>
  <div class="mini-trend" :class="{ 'mini-trend--fill': fill }">
    <div class="mini-trend__head row no-wrap items-baseline">
      <span v-if="headline" class="mini-trend__value dash-value">{{ headline }}</span>
      <span v-if="caption" class="mini-trend__caption dash-note ellipsis">{{ caption }}</span>
      <q-space />
      <span v-for="item in legend ? series : []" :key="item.key" class="mini-trend__key dash-note row no-wrap items-center">
        <span class="mini-trend__swatch" :class="{ 'mini-trend__swatch--line': item.type === 'line' }" :style="{ background: color(item.color) }" />{{ item.label }}
      </span>
      <slot name="actions" />
    </div>
    <div v-if="fill" class="mini-trend__chart" :style="{ minHeight: `${height}px` }">
      <q-resize-observer @resize="onResize" />
      <dashboard-chart :option="option" :height="Math.max(height, chartHeight)" @select="select" />
    </div>
    <dashboard-chart v-else :option="option" :height="height" @select="select" />
  </div>
</template>

<script>
import DashboardChart from "./DashboardChart.vue";
import { bucketAxis, bucketTitle } from "../../utils/dashboard";
import { escapeHtml, formatNumber } from "../../utils/format";
import { paletteColor } from "../../utils/palette";

// A small trend over the buckets of a span: a headline (a total, the last value) and the series as an area, a line or
// thin bars, without value axes; a series on axis 1 has its own scale (a rate beside a volume). Gaps (null) stay gaps.
// A click picks the bucket.
export default {
  name: "MiniTrend",
  components: { DashboardChart },
  props: {
    buckets: { type: Array, required: true },
    unit: { type: String, default: "day" },
    // [{key, label, color (Quasar name), values, type: area|line|bar, axis: 0|1, format?}]
    series: { type: Array, required: true },
    headline: { type: String, default: "" },
    caption: { type: String, default: "" },
    // The chart's height, or its least with `fill`: then it takes the height its parent leaves it (a flex item).
    height: { type: Number, default: 72 },
    fill: { type: Boolean, default: false },
    // The series' keys in the head; off when something else names them (a select).
    legend: { type: Boolean, default: true },
    // A last line of the tooltip of a bucket (its index), e.g. a rate of two series.
    note: { type: Function, default: null },
  },
  emits: ["pick"],
  data() {
    return { chartHeight: 0 };
  },
  computed: {
    // paletteColor reads the theme, so the colors follow it.
    option() {
      const second = this.series.some((item) => item.axis === 1);
      const axis = { type: "value", show: false, min: 0 };
      return {
        animation: false,
        grid: { left: 2, right: 2, top: 4, bottom: 16 },
        tooltip: { trigger: "axis", confine: true, axisPointer: { type: "line" }, formatter: this.tooltip },
        xAxis: {
          type: "category",
          data: this.buckets.map((bucket) => bucketAxis(bucket, this.unit)),
          boundaryGap: this.series.some((item) => item.type === "bar"),
          axisTick: { show: false },
          axisLine: { show: false },
          axisLabel: { fontSize: 10, hideOverlap: true, margin: 4, alignMinLabel: "left", alignMaxLabel: "right" },
        },
        yAxis: second ? [axis, { ...axis }] : [axis],
        series: this.series.map((item) => {
          const color = paletteColor(item.color);
          const common = { name: item.label, data: item.values, yAxisIndex: item.axis === 1 ? 1 : 0, itemStyle: { color }, cursor: "pointer" };
          if (item.type === "bar") {
            return { ...common, type: "bar", barMaxWidth: 10 };
          }
          return {
            ...common,
            type: "line",
            // Each bucket a point of its own while there are few (no slope across a gap of days).
            showSymbol: this.buckets.length <= 31,
            symbolSize: 5,
            lineStyle: { width: item.type === "area" ? 1.5 : 2 },
            areaStyle: item.type === "area" ? { opacity: item.opacity || 0.18 } : undefined,
          };
        }),
      };
    },
  },
  methods: {
    color: paletteColor,
    tooltip(items) {
      const index = items[0].dataIndex;
      const lines = [`<b>${escapeHtml(bucketTitle(this.buckets[index], this.unit))}</b>`];
      this.series.forEach((item) => {
        const value = item.values[index];
        const text = value === null || value === undefined ? "no data" : (item.format || formatNumber)(value);
        lines.push(`${escapeHtml(item.label)} <b>${escapeHtml(text)}</b>`);
      });
      const note = this.note && this.note(index);
      if (note) {
        lines.push(escapeHtml(note));
      }
      return lines.join("<br/>");
    },
    onResize({ height }) {
      this.chartHeight = Math.floor(height);
    },
    select(event) {
      this.$emit("pick", { index: event.dataIndex, bucket: this.buckets[event.dataIndex] });
    },
  },
};
</script>

<style scoped>
.mini-trend--fill {
  display: flex;
  flex-direction: column;
}

/* The chart over the whole space left, out of the flow, so its height never feeds back into the space. */
.mini-trend__chart {
  position: relative;
  flex: 1 1 0;
}

.mini-trend__chart > .dashboard-chart {
  position: absolute;
  inset: 0 0 auto;
}

.mini-trend__head {
  gap: 8px;
  min-height: 30px;
}

.mini-trend__value {
  white-space: nowrap;
}

.mini-trend__caption {
  min-width: 0;
}

.mini-trend__key {
  gap: 4px;
  white-space: nowrap;
}

.mini-trend__swatch {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 2px;
}

.mini-trend__swatch--line {
  height: 2px;
}
</style>
