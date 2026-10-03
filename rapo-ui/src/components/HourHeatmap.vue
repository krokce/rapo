<template>
  <div class="hour-heatmap">
    <!-- Positioned inside the padding a page may give the heatmap, which the markers' positions leave out. -->
    <div class="hour-heatmap__body">
      <!-- Markers over the columns, a line through the hours under a label in the day row; not clickable, so the cells
         under them keep their clicks and tooltips. Midnight of a rolling window: in the gap before its column, grey,
         with the day it turns to (only its icon next to the Now label). The present: at the minute, under a clock
         and "Now HH:mm". -->
      <template v-for="(slot, index) in columns" :key="`day-${index}`">
        <div v-if="slot.divider" class="hour-heatmap__marker hour-heatmap__marker--day" :style="{ '--at': index }">
          <div class="hour-heatmap__marker-label" :title="`Midnight: ${slot.dividerLabel}`">
            <q-icon name="fas fa-calendar-day" size="10px" />
            <span v-if="now === null || Math.abs(now - index) > 2.5">{{ slot.dividerLabel }}</span>
          </div>
          <div class="hour-heatmap__marker-line"></div>
        </div>
      </template>
      <div v-if="now !== null" class="hour-heatmap__marker hour-heatmap__marker--now" :style="{ '--at': now }">
        <div class="hour-heatmap__marker-label" :class="{ 'hour-heatmap__marker-label--end': now > 12 }" :title="`Now ${nowLabel}`">
          <span v-if="now > 12">Now {{ nowLabel }}</span>
          <q-icon name="fas fa-clock" size="10px" />
          <span v-if="now <= 12">Now {{ nowLabel }}</span>
        </div>
        <div class="hour-heatmap__marker-line"></div>
      </div>
      <!-- The row the marker labels sit in. -->
      <div v-if="now !== null || columns.some((slot) => slot.divider)" class="hour-heatmap__row hour-heatmap__days"></div>
      <div class="hour-heatmap__row hour-heatmap__hours">
        <div class="hour-heatmap__label"></div>
        <div v-for="(slot, index) in columns" :key="index" class="hour-heatmap__hour" :class="{ 'hour-heatmap__hour--selected': selected === index }">
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
  </div>
</template>

<script>
// Counts per hour of the day: one row per group and a Total, colored by count on a square-root scale up to the busiest
// cell. A cell with errors has a red outline; its corner marks errors (red) or warnings (amber). A click picks the hour
// (the index of its column), a second clears it. Used for files (Files, file log), runs (Results) and the scheduler's
// rolling 24 hours (columns from `slots`, green for the future). `now` marks the present (utils/clock.js).
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
    // column (midnight of a rolling window) has a grey marker line before it under its dividerLabel.
    slots: { type: Array, default: null },
    // The hue of the scale: blue (199) for the past, a green for what is still to come.
    hue: { type: Number, default: 199 },
    // Where the present falls: the column plus the share of its hour gone (utils/clock.js), null for none; nowLabel
    // is its time (HH:mm). The page passes both, by the clock its hours are counted in.
    now: { type: Number, default: null },
    nowLabel: { type: String, default: "" },
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
.hour-heatmap__body {
  position: relative;
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
.hour-heatmap__days {
  height: 14px;
  line-height: 14px;
}
/* The columns start after the label (110px) and a gap, and each is 1/24 of the rest with its gap: --at columns in.
   The day marker takes the 2px gap before its column, the Now marker is centered on its minute. */
.hour-heatmap__marker {
  position: absolute;
  top: 0;
  bottom: 0;
  left: calc(112px + (100% - 110px) * var(--at) / 24 - 2px);
  width: 2px;
  z-index: 1;
  pointer-events: none;
  color: var(--rapo-label);
}
.hour-heatmap__marker--now {
  left: calc(112px + (100% - 110px) * var(--at) / 24 - 1px);
  z-index: 2;
  color: var(--rapo-now);
  font-weight: bold;
}
.hour-heatmap__marker-line {
  position: absolute;
  top: 12px;
  bottom: -2px;
  left: 0;
  width: 2px;
  border-radius: 1px;
  background: currentColor;
}
.hour-heatmap__marker-label {
  position: absolute;
  top: 0;
  left: -4px;
  height: 14px;
  line-height: 14px;
  display: flex;
  align-items: center;
  gap: 3px;
  white-space: nowrap;
  pointer-events: auto;
}
.hour-heatmap__marker-label--end {
  left: auto;
  right: -4px;
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
