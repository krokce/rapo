<template>
  <div class="hour-heatmap">
    <!-- The day a rolling window turns to, over its midnight column. -->
    <div v-if="columns.some((slot) => slot.dividerLabel)" class="hour-heatmap__row hour-heatmap__days">
      <div class="hour-heatmap__label"></div>
      <div v-for="(slot, index) in columns" :key="index" class="hour-heatmap__day" :class="{ 'hour-heatmap__divider': slot.divider }">{{ slot.dividerLabel }}</div>
    </div>
    <div class="hour-heatmap__row hour-heatmap__hours">
      <div class="hour-heatmap__label"></div>
      <div
        v-for="(slot, index) in columns"
        :key="index"
        class="hour-heatmap__hour"
        :class="{ 'hour-heatmap__hour--selected': selected === index, 'hour-heatmap__divider': slot.divider }">
        {{ String(slot.hour).padStart(2, "0") }}
      </div>
    </div>
    <div v-for="row in rows" :key="row.key" class="hour-heatmap__row">
      <div class="hour-heatmap__label ellipsis" :class="{ 'text-weight-bold': row.key === 'total' }">
        <q-icon v-if="row.color" name="fas fa-circle" :color="row.color" size="9px" class="q-mr-xs" />{{ row.label }}
      </div>
      <div
        v-for="(cell, hour) in row.cells"
        :key="hour"
        class="hour-heatmap__cell"
        :class="{
          'hour-heatmap__divider': columns[hour].divider,
          'hour-heatmap__cell--errors': cell.errors,
          'hour-heatmap__cell--corner-errors': corner === 'errors' && cell.errors,
          'hour-heatmap__cell--corner-warnings': corner === 'warnings' && cell.warnings,
          'hour-heatmap__cell--selected': selected === hour,
          'hour-heatmap__cell--dim': selected !== null && selected !== hour,
        }"
        :style="{ background: color(cell.count, row.key === 'total') }"
        v-keyboard:button
        :aria-pressed="selected === hour"
        :aria-label="`${columns[hour].title}, ${cell.count} ${unit}${cell.errors ? ', with errors' : ''}${cell.warnings ? ', with warnings' : ''}`"
        @click="$emit('select', selected === hour ? null : hour)">
        <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 6]">
          {{ columns[hour].title }}, {{ row.label }}: {{ cell.count.toLocaleString() }} {{ unit }}<span v-if="cell.breakdown"> &middot; {{ cell.breakdown }}</span
          ><span v-if="cell.errors">, {{ cell.errors }} error(s)</span><span v-if="cell.warnings">, {{ cell.warnings }} warning(s)</span>
        </q-tooltip>
      </div>
    </div>
  </div>
</template>

<script>
// Counts per hour of the day: one row per group and a Total, colored by count on a square-root scale up to the busiest
// cell. A cell with errors has a red outline; its corner marks errors (red) or warnings (amber). A click picks the hour
// (the index of its column), a second clears it. Used for files (Files, file log), runs (Results) and the scheduler's
// rolling 24 hours (columns from `slots`, green for the future).
import { Dark } from "quasar";
import { hourRange } from "../utils/files";

export default {
  name: "HourHeatmap",
  props: {
    // [{key, label, color, cells: [{count, errors, warnings?, breakdown?}] x 24}] (utils/files.js heatmapRows,
    // utils/runs.js runHeatmapRows).
    rows: { type: Array, required: true },
    selected: { type: Number, default: null },
    // What a cell counts, for the tooltip.
    unit: { type: String, default: "file(s)" },
    // What the corner triangle marks: "errors" (red) or "warnings" (amber).
    corner: { type: String, default: "errors" },
    // The columns in order, [{hour, title?, divider?, dividerLabel?}]; the hours 0..23 of one day by default. A divider
    // column (midnight of a rolling window) has a line before it and its dividerLabel above.
    slots: { type: Array, default: null },
    // The hue of the scale: blue (199) for the past, a green for what is still to come.
    hue: { type: Number, default: 199 },
  },
  emits: ["select"],
  computed: {
    columns() {
      return (this.slots || Array.from({ length: 24 }, (_, hour) => ({ hour }))).map((slot) => ({ ...slot, title: slot.title || hourRange(slot.hour) }));
    },
    // The busiest cell of the groups; the Total row is scaled on its own, else it would wash the groups out.
    maxima() {
      const groups = this.rows.filter((row) => row.key !== "total").flatMap((row) => row.cells.map((cell) => cell.count));
      const total = this.rows.filter((row) => row.key === "total").flatMap((row) => row.cells.map((cell) => cell.count));
      return { groups: Math.max(1, ...groups), total: Math.max(1, ...total) };
    },
  },
  methods: {
    color(count, total = false) {
      if (!count) {
        return "var(--rapo-grid)";
      }
      const share = Math.sqrt(count / (total ? this.maxima.total : this.maxima.groups));
      const lightness = Dark.isActive ? 20 + Math.min(share, 1) * 40 : 92 - Math.min(share, 1) * 55;
      return `hsl(${this.hue}, ${this.hue === 199 ? 80 : 55}%, ${lightness}%)`;
    },
  },
};
</script>

<style scoped>
.hour-heatmap {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11px;
  user-select: none;
}
.hour-heatmap__row {
  display: grid;
  grid-template-columns: 110px repeat(24, minmax(0, 1fr));
  gap: 2px;
  align-items: center;
}
.hour-heatmap__label {
  color: var(--rapo-strong);
  padding-right: 6px;
}
.hour-heatmap__hour {
  text-align: center;
  color: var(--rapo-label);
}
.hour-heatmap__day {
  color: var(--rapo-label);
  white-space: nowrap;
  overflow: visible;
  padding-left: 3px;
}
.hour-heatmap__divider {
  box-shadow: -2px 0 0 0 var(--rapo-label);
}
.hour-heatmap__hour--selected {
  color: var(--rapo-info);
  font-weight: bold;
}
.hour-heatmap__cell {
  height: 16px;
  border-radius: 2px;
  cursor: pointer;
  box-sizing: border-box;
  position: relative;
}
.hour-heatmap__cell--errors {
  border: 2px solid var(--rapo-heat-error);
}
.hour-heatmap__cell--corner-errors::after,
.hour-heatmap__cell--corner-warnings::after {
  content: "";
  position: absolute;
  top: 0;
  right: 0;
  border-style: solid;
  border-width: 0 7px 7px 0;
  border-color: transparent var(--rapo-heat-error) transparent transparent;
}
.hour-heatmap__cell--corner-warnings::after {
  border-color: transparent var(--rapo-heat-warning) transparent transparent;
}
.hour-heatmap__cell--selected {
  outline: 2px solid var(--rapo-info);
  outline-offset: 1px;
}
.hour-heatmap__cell--dim {
  opacity: 0.45;
}
</style>
