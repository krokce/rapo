<template>
  <div v-if="!missing">
    <q-skeleton type="rect" height="240px" class="q-mb-md" />
    <q-skeleton type="rect" height="300px" />
  </div>
  <div v-else-if="!withMissing.length" class="column items-center q-pa-xl text-grey-7">
    <q-icon name="fas fa-check-circle" color="green-6" size="40px" class="q-mb-md" />
    No column of the sample has missing values.
  </div>
  <div v-else>
    <div class="text-subtitle1 text-blue-grey-9">Missing values per column</div>
    <div class="text-caption text-grey-7 q-mb-sm">
      {{ withMissing.length }} of {{ missing.columns.length }} columns have missing values. Click a bar to see those rows.
    </div>
    <e-chart :option="barOption" :height="barHeight" @select="selectBar" />

    <div class="text-subtitle1 text-blue-grey-9 q-mt-lg">Nullity matrix</div>
    <div class="text-caption text-grey-7 q-mb-sm">
      The sample in its order, split into {{ missing.buckets }} parts: the darker a cell, the more values of the column are missing in that
      part. Columns without missing values are left out.
    </div>
    <e-chart :option="matrixOption" :height="matrixHeight" />
  </div>
</template>

<script>
import EChart from "./EChart.vue";
import { formatNumber } from "../../utils/format";
import { formatPct } from "../../utils/analysis";

export default {
  name: "AnalysisMissing",
  components: { EChart },
  props: {
    missing: { type: Object, default: null },
  },
  emits: ["show-rows"],
  computed: {
    withMissing() {
      return this.missing.columns.filter((column) => column.missing > 0);
    },
    barHeight() {
      return Math.min(80 + this.withMissing.length * 22, 900);
    },
    barOption() {
      const columns = [...this.withMissing].reverse();
      return {
        animation: false,
        grid: { left: 8, right: 60, top: 8, bottom: 24, containLabel: true },
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "shadow" },
          formatter: (items) => {
            const column = columns[items[0].dataIndex];
            return `${column.name.toUpperCase()}<br/><b>${formatNumber(column.missing)}</b> missing (${formatPct(column.missing_pct)})`;
          },
        },
        xAxis: { type: "value", max: 100, axisLabel: { formatter: "{value}%", fontSize: 10 }, splitLine: { lineStyle: { color: "#eceff1" } } },
        yAxis: { type: "category", data: columns.map((column) => column.name.toUpperCase()), axisLabel: { fontSize: 11 } },
        series: [
          {
            type: "bar",
            data: columns.map((column) => column.missing_pct),
            itemStyle: { color: "#ef6c00" },
            label: { show: true, position: "right", fontSize: 10, formatter: (item) => formatPct(item.value) },
            cursor: "pointer",
          },
        ],
      };
    },
    matrixColumns() {
      return this.missing.columns.map((column, index) => ({ ...column, index })).filter((column) => column.missing > 0);
    },
    matrixHeight() {
      return Math.min(90 + this.matrixColumns.length * 22, 900);
    },
    matrixOption() {
      const columns = this.matrixColumns;
      const data = [];
      columns.forEach((column, y) => {
        this.missing.matrix[column.index].forEach((share, x) => data.push([x, y, share]));
      });
      return {
        animation: false,
        grid: { left: 8, right: 16, top: 8, bottom: 56, containLabel: true },
        tooltip: {
          formatter: (item) => `${columns[item.value[1]].name.toUpperCase()}, part ${item.value[0] + 1}<br/><b>${formatPct(item.value[2] * 100)}</b> missing`,
        },
        xAxis: { type: "category", data: Array.from({ length: this.missing.buckets }, (item, index) => index + 1), axisLabel: { show: false }, axisTick: { show: false }, name: "" },
        yAxis: { type: "category", data: columns.map((column) => column.name.toUpperCase()), axisLabel: { fontSize: 11 } },
        visualMap: {
          min: 0,
          max: 1,
          calculable: false,
          orient: "horizontal",
          left: "center",
          bottom: 0,
          itemHeight: 120,
          inRange: { color: ["#eceff1", "#37474f"] },
          text: ["all missing", "none missing"],
          textStyle: { fontSize: 10 },
        },
        series: [{ type: "heatmap", data, progressive: 0 }],
      };
    },
  },
  methods: {
    selectBar(event) {
      const columns = [...this.withMissing].reverse();
      const column = columns[event.dataIndex];
      if (column) {
        this.$emit("show-rows", [{ column: column.name, op: "null" }]);
      }
    },
  },
};
</script>
