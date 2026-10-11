<template>
  <div>
    <heat-strip :rows="shownRows" :columns="columns" :label-width="labelWidth" :cell-height="18" class="kpi-heatmap" @pick="pick" />
    <q-btn v-if="rows.length > LIMIT" flat dense no-caps size="sm" color="primary" class="q-mt-xs" :icon="all ? 'fas fa-chevron-up' : 'fas fa-chevron-down'" :label="all ? 'Show fewer' : `Show ${rows.length - LIMIT} more control${rows.length - LIMIT > 1 ? 's' : ''}`" @click="toggle" />
  </div>
</template>

<script>
import HeatStrip from "./HeatStrip.vue";
import { bucketColumns } from "../../utils/dashboard";
import { alarmLevel } from "../../utils/kpi";

// The controls shown before "Show more", and where the browser keeps whether all are shown.
const LIMIT = 25;
const ALL_KEY = "rapo_dashboard_kpi_all";

function readAll() {
  try {
    return localStorage.getItem(ALL_KEY) === "1";
  } catch (error) {
    return false;
  }
}

// The highest KPI alarm level of each control per bucket: a compact row per control (the worst first) in the level
// colors (no alarm a pale grey), empty where it stored nothing; the first LIMIT, the others behind a button. A click
// opens the control's KPIs.
export default {
  name: "KpiAlarmHeatmap",
  components: { HeatStrip },
  props: {
    // The kpis part of get-dashboard.
    data: { type: Object, required: true },
  },
  emits: ["pick"],
  data() {
    return { LIMIT, all: readAll() };
  },
  computed: {
    // The longest control name (13px text), up to 260 px.
    labelWidth() {
      const longest = Math.max(0, ...this.data.heatmap.controls.map((control) => control.control_name.length));
      return Math.min(260, Math.max(110, longest * 8 + 28));
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
    shownRows() {
      return this.all ? this.rows : this.rows.slice(0, LIMIT);
    },
  },
  methods: {
    toggle() {
      this.all = !this.all;
      try {
        localStorage.setItem(ALL_KEY, this.all ? "1" : "0");
      } catch (error) {
        // Not remembered, which is all a failure costs.
      }
    },
    pick({ row, column }) {
      const control = this.data.heatmap.controls.find((item) => item.control_name === row);
      this.$emit("pick", { key: row, control, bucket: this.data.buckets[column] });
    },
  },
};
</script>

<style scoped>
/* Compact but readable rows: 18px cells, 4px apart. */
.kpi-heatmap.heat-strip {
  gap: 4px;
}
</style>
