<template>
  <div class="heat-strip" :class="{ 'heat-strip--boxes': boxes }" :style="{ '--label': `${labelWidth}px`, '--columns': columns.length, '--cell': `${cellHeight}px` }">
    <q-resize-observer v-if="numbers || hasText" @resize="onResize" />
    <div class="heat-strip__row heat-strip__head">
      <div class="heat-strip__label"></div>
      <div v-for="(column, index) in columns" :key="index" class="heat-strip__column" :class="{ 'heat-strip__column--divider': column.divider }">
        {{ column.label || "" }}
      </div>
    </div>
    <div v-for="row in rows" :key="row.key" class="heat-strip__row">
      <div
        class="heat-strip__label dash-text row no-wrap items-center"
        :class="{ 'heat-strip__label--link': row.link }"
        :title="row.title || row.label"
        v-keyboard:button="Boolean(row.link)"
        @click="row.link && $emit('label-pick', { row: row.key })">
        <span v-if="row.color" class="heat-strip__dot" :style="{ background: rowColor(row) }" />
        <span class="ellipsis col heat-strip__name">{{ row.label }}</span>
        <span v-if="row.total !== undefined && row.total !== null" class="heat-strip__total dash-text">{{ compactNumber(row.total) }}</span>
      </div>
      <div
        v-for="(cell, index) in row.cells"
        :key="index"
        class="heat-strip__cell"
        :class="{
          'heat-strip__cell--none': cell === null || cell.count === null || cell.count === undefined,
          'heat-strip__cell--errors': cell && cell.errors,
          'heat-strip__cell--divider': columns[index] && columns[index].divider,
          'heat-strip__cell--link': clickable && cell && cell.count,
          'heat-strip__cell--strong': (showNumbers && strong(row, cell)) || (showText && cell && cell.text && !cell.light),
          'heat-strip__cell--text': showText && cell && cell.text,
        }"
        :style="{ background: background(row, cell) }"
        :title="cellTitle(row, cell, index)"
        @click="clickable && cell && cell.count && $emit('pick', { row: row.key, column: index })">
        <template v-if="showText && cell && cell.text">{{ cell.text }}</template>
        <template v-else-if="showNumbers && cell && cell.count && !cell.color">{{ compactNumber(cell.count) }}</template>
      </div>
    </div>
  </div>
</template>

<script>
import { compactNumber, formatNumber } from "../../utils/format";
import { paletteColor, prefersStrongText } from "../../utils/palette";

// Counts over time as a strip per category: a row per status (or type, or control), a cell per hour or day, colored in
// the row's chip color, stronger the more it counts (square root of its share of the row's busiest cell, or of the whole
// strip's with `scale="all"`). An empty cell is the grid's grey, one without data (null) hatched, one with errors outlined
// red. A divider column (Now, midnight) has a line before it. A click on a cell with counts picks it, one on the label of a
// row with `link` picks the row (`label-pick`). A cell's own `text` (up to 4 characters, e.g. a KPI value) is written on
// its color when the cells are wide enough for it (dark on a `light` color); `boxes` writes it as the KPI boxes of the run
// tables do (mono, rounded). A color is a Quasar palette name, or a CSS color or var() as it is.
export default {
  name: "HeatStrip",
  props: {
    // [{key, label, color (Quasar name), title?, total?, link?, cells: [{count, errors?, title?, color?, text?, light?} | null]}]
    rows: { type: Array, required: true },
    // [{label?, title, divider?}], one per cell; label shown above (sparse).
    columns: { type: Array, required: true },
    labelWidth: { type: Number, default: 96 },
    // The height of a cell (px).
    cellHeight: { type: Number, default: 14 },
    scale: { type: String, default: "row" },
    // What a cell counts, for its tooltip.
    unit: { type: String, default: "" },
    clickable: { type: Boolean, default: true },
    // The count written in each cell (not 0, nor a cell with a color of its own), when the cells are wide enough.
    numbers: { type: Boolean, default: false },
    // Text cells as KPI value boxes (Roboto Mono, 3px corners).
    boxes: { type: Boolean, default: false },
  },
  data() {
    return { width: 0 };
  },
  emits: ["pick", "label-pick"],
  computed: {
    // A cell's width: the strip's less the label and the 2px gaps, by column.
    cellWidth() {
      return (this.width - this.labelWidth - 2 * this.columns.length) / Math.max(this.columns.length, 1);
    },
    showNumbers() {
      return this.numbers && this.cellWidth >= 18;
    },
    hasText() {
      return this.rows.some((row) => row.cells.some((cell) => cell && cell.text));
    },
    // Four characters of 10px text (mono in boxes).
    showText() {
      return this.hasText && this.cellWidth >= (this.boxes ? 28 : 26);
    },
    maxima() {
      const all = Math.max(1, ...this.rows.flatMap((row) => row.cells.map((cell) => (cell && cell.count) || 0)));
      return Object.fromEntries(this.rows.map((row) => [row.key, this.scale === "all" ? all : Math.max(1, ...row.cells.map((cell) => (cell && cell.count) || 0))]));
    },
  },
  methods: {
    compactNumber,
    onResize({ width }) {
      this.width = width;
    },
    // The strength of a cell's color (0.18 to 1), as `background` paints it.
    alpha(row, cell) {
      return 0.18 + 0.82 * Math.min(Math.sqrt(cell.count / this.maxima[row.key]), 1);
    },
    // Whether white text reads better than dark on the cell's blended color.
    strong(row, cell) {
      return Boolean(cell && cell.count) && prefersStrongText(this.color(row.color || "blue-6"), this.alpha(row, cell));
    },
    rowColor(row) {
      return this.color(row.color);
    },
    color(name) {
      return /^(#|var\(|rgb)/.test(name) ? name : paletteColor(name);
    },
    // A cell's own color (e.g. a KPI level) as it is, else the row's color in the strength of its count.
    background(row, cell) {
      if (!cell || cell.count === null || cell.count === undefined) {
        return null;
      }
      if (cell.color) {
        return this.color(cell.color);
      }
      if (!cell.count) {
        return "var(--rapo-grid)";
      }
      const color = this.color(row.color || "blue-6");
      const alpha = this.alpha(row, cell).toFixed(2);
      return color.startsWith("rgb(") ? color.replace("rgb(", "rgba(").replace(")", `, ${alpha})`) : color;
    },
    cellTitle(row, cell, index) {
      const column = this.columns[index] || {};
      if (!cell || cell.count === null || cell.count === undefined) {
        return `${column.title || ""}: no data`;
      }
      if (cell.title) {
        return cell.title;
      }
      return `${row.label} · ${column.title || ""}: ${formatNumber(cell.count)}${this.unit ? ` ${this.unit}` : ""}${cell.errors ? `, ${cell.errors} in error` : ""}`;
    },
  },
};
</script>

<style scoped>
.heat-strip {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 2px;
  user-select: none;
}

.heat-strip__row {
  display: grid;
  grid-template-columns: var(--label) repeat(var(--columns), minmax(0, 1fr));
  gap: 2px;
  align-items: center;
}

.heat-strip__head {
  color: var(--rapo-label);
  font-size: var(--rapo-dash-tick);
  line-height: 14px;
}

.heat-strip__column {
  white-space: nowrap;
  overflow: visible;
}

.heat-strip__column--divider {
  border-left: 2px solid var(--rapo-label);
  padding-left: 2px;
}

.heat-strip__label {
  min-width: 0;
  padding-right: 6px;
}

.heat-strip__dot {
  flex: none;
  width: 8px;
  height: 8px;
  border-radius: 2px;
  margin-right: 5px;
}

.heat-strip__total {
  margin-left: 4px;
  font-weight: 600;
  color: var(--rapo-header-text);
}

.heat-strip__cell {
  height: var(--cell);
  border-radius: 2px;
  box-sizing: border-box;
  overflow: hidden;
  font-size: var(--rapo-dash-tick);
  font-weight: 600;
  line-height: var(--cell);
  text-align: center;
  white-space: nowrap;
  color: var(--rapo-header-text);
  font-variant-numeric: tabular-nums;
}

.heat-strip__cell--strong {
  color: var(--rapo-on-strong);
}

.heat-strip__cell--none {
  background: repeating-linear-gradient(135deg, var(--rapo-grid) 0 2px, transparent 2px 5px);
}

.heat-strip__cell--errors {
  border: 2px solid var(--rapo-heat-error);
}

.heat-strip__cell--divider {
  box-shadow: -3px 0 0 -1px var(--rapo-label);
}

.heat-strip__cell--text {
  font-size: var(--rapo-dash-micro);
  letter-spacing: -0.2px;
}

.heat-strip--boxes .heat-strip__cell {
  border-radius: 3px;
}

.heat-strip--boxes .heat-strip__cell--text {
  font-family: var(--rapo-font-mono);
  font-weight: 500;
  letter-spacing: 0;
}

.heat-strip__label--link {
  cursor: pointer;
}

.heat-strip__label--link:hover .heat-strip__name {
  text-decoration: underline;
}

.heat-strip__cell--link {
  cursor: pointer;
}

.heat-strip__cell--link:hover {
  outline: 1px solid var(--rapo-strong);
}
</style>
