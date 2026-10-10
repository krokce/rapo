<template>
  <div>
    <heat-strip :rows="rows" :columns="columns" :label-width="labelWidth" :cell-height="16" @pick="pick" />
    <div v-if="data.heatmap.more" class="text-caption text-grey-7 q-mt-xs">{{ data.heatmap.more }} more control{{ data.heatmap.more > 1 ? "s" : "" }} with lower levels not shown.</div>
  </div>
</template>

<script>
import HeatStrip from "./HeatStrip.vue";
import { bucketColumns } from "../../utils/dashboard";
import { alarmLevel } from "../../utils/kpi";

// The highest KPI alarm level of each control per bucket: a row per control (the worst first) in the level colors
// (no alarm a pale grey), empty where it stored nothing. A click opens the control's KPIs.
export default {
  name: "KpiAlarmHeatmap",
  components: { HeatStrip },
  props: {
    // The kpis part of get-dashboard.
    data: { type: Object, required: true },
  },
  emits: ["pick"],
  computed: {
    // The longest control name, up to 190 px.
    labelWidth() {
      const longest = Math.max(0, ...this.data.heatmap.controls.map((control) => control.control_name.length));
      return Math.min(190, Math.max(110, longest * 7 + 20));
    },
    columns() {
      return bucketColumns(this.data.buckets, this.data.unit);
    },
    rows() {
      const size = this.data.buckets.length;
      const grid = this.data.heatmap.controls.map(() => Array(size).fill(null));
      this.data.heatmap.cells.forEach(([row, column, level]) => {
        const info = alarmLevel(level);
        grid[row][column] = { count: 1, color: level ? info.color : "blue-grey-2", title: `${this.data.heatmap.controls[row].control_name}: ${info.label}` };
      });
      return this.data.heatmap.controls.map((control, index) => ({
        key: control.control_name,
        label: control.control_name,
        color: alarmLevel(control.level).color,
        title: `${control.control_name}: highest ${alarmLevel(control.level).label.toLowerCase()} in the span`,
        cells: grid[index].map((cell) => cell || { count: 0 }),
      }));
    },
  },
  methods: {
    pick({ row, column }) {
      const control = this.data.heatmap.controls.find((item) => item.control_name === row);
      this.$emit("pick", { key: row, control, bucket: this.data.buckets[column] });
    },
  },
};
</script>
