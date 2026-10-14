<template>
  <div>
    <heat-strip :rows="shownRows" :columns="columns" :label-width="labelWidth" :cell-height="18" boxes class="kpi-heatmap" @pick="pick" @label-pick="pickLabel" />
    <q-btn v-if="rows.length > LIMIT" flat dense no-caps size="sm" color="primary" class="q-mt-xs" :icon="all ? 'fas fa-chevron-up' : 'fas fa-chevron-down'" :label="all ? 'Show fewer' : `Show ${rows.length - LIMIT} more control${rows.length - LIMIT > 1 ? 's' : ''}`" @click="toggle" />
  </div>
</template>

<script>
import HeatStrip from "./HeatStrip.vue";
import { bucketColumns } from "../../utils/dashboard";
import { alarmLevel, compactKpiValue, formatKpiValue } from "../../utils/kpi";

// The controls shown before "Show more", and where the browser keeps whether all are shown.
const LIMIT = 25;
const ALL_KEY = "rapo_dashboard_kpi_all";
// The color of no alarm, the run tables' KPI box.
const OK_COLOR = "var(--rapo-kpi-ok)";

function readAll() {
  try {
    return localStorage.getItem(ALL_KEY) === "1";
  } catch (error) {
    return false;
  }
}

// The highest KPI alarm level of each control per bucket: a compact row per control (the worst first) in the level
// colors (no alarm soft green, as the KPI boxes of Results), empty where it stored nothing; the first LIMIT, the others
// behind a button. A cell writes the value of its run's most important KPI at that level (any KPI without an alarm). A
// cell opens the control's run log on its run, as does a control's name without one.
export default {
  name: "KpiAlarmHeatmap",
  components: { HeatStrip },
  props: {
    // The kpis part of get-dashboard.
    data: { type: Object, required: true },
  },
  emits: ["pick", "open-log"],
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
      this.data.heatmap.cells.forEach((cell) => {
        const info = alarmLevel(cell.level);
        grid[cell.row][cell.column] = {
          count: 1,
          color: cell.level ? info.color : OK_COLOR,
          light: !cell.level,
          text: cell.kpi_type ? compactKpiValue(cell.value) : "",
          title: this.cellTitle(this.data.heatmap.controls[cell.row].control_name, cell, info),
        };
      });
      return this.data.heatmap.controls.map((control, index) => ({
        key: control.control_name,
        label: control.control_name,
        color: control.level ? alarmLevel(control.level).color : OK_COLOR,
        link: Boolean(control.control_id),
        title: `${control.control_name}: highest ${alarmLevel(control.level).label.toLowerCase()} in the span${control.control_id ? "; open its run log" : ""}`,
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
    // "NAME · run 1234567 · RATE_LOSS = 12.3456 % · Alarm 3 (+2 other KPIs alarmed)", "... · No alarm".
    cellTitle(name, cell, info) {
      const parts = [name, `run ${cell.process_id}`];
      if (cell.kpi_type) {
        parts.push(`${cell.kpi_type} = ${formatKpiValue(cell.value, cell.decimals)}${cell.unit ? ` ${cell.unit}` : ""}`);
      }
      const others = cell.others ? ` (+${cell.others} other KPI${cell.others > 1 ? "s" : ""} alarmed)` : "";
      parts.push(`${info.label}${others}`);
      return parts.join(" · ");
    },
    pick({ row, column }) {
      const control = this.data.heatmap.controls.find((item) => item.control_name === row);
      const index = this.data.heatmap.controls.indexOf(control);
      const cell = this.data.heatmap.cells.find((item) => item.row === index && item.column === column);
      this.$emit("pick", { key: row, control, bucket: this.data.buckets[column], processId: cell ? cell.process_id : null });
    },
    pickLabel({ row }) {
      const control = this.data.heatmap.controls.find((item) => item.control_name === row);
      if (control && control.control_id) {
        this.$emit("open-log", control);
      }
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
