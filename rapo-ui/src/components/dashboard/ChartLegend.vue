<template>
  <div class="chart-legend row items-center">
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      class="chart-legend__item row no-wrap items-center"
      :class="{ 'chart-legend__item--off': hidden.includes(item.key) }"
      :title="toggle ? `${hidden.includes(item.key) ? 'Show' : 'Hide'} ${item.label}` : item.title || item.label"
      :disabled="!toggle"
      @click="$emit('toggle', item.key)">
      <span class="chart-legend__swatch" :class="{ 'chart-legend__swatch--line': item.line }" :style="{ background: color(item.color) }" />
      <span>{{ item.label }}</span>
      <span v-if="item.value !== undefined && item.value !== null" class="chart-legend__value">{{ item.value }}</span>
    </button>
  </div>
</template>

<script>
import { paletteColor } from "../../utils/palette";

// The legend of a Dashboard chart: a swatch per series in its chip color, its total; a click shows or hides it.
export default {
  name: "ChartLegend",
  props: {
    // [{key, label, color (Quasar name), value?, line?, title?}]
    items: { type: Array, required: true },
    hidden: { type: Array, default: () => [] },
    toggle: { type: Boolean, default: true },
  },
  emits: ["toggle"],
  methods: {
    color(name) {
      return name && name.startsWith("var(") ? name : paletteColor(name);
    },
  },
};
</script>

<style scoped>
.chart-legend {
  gap: 2px 10px;
  font-size: var(--rapo-dash-note);
  color: var(--rapo-strong);
  margin-bottom: 4px;
}

.chart-legend__item {
  gap: 4px;
  padding: 1px 2px;
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  cursor: pointer;
  border-radius: 3px;
}

.chart-legend__item:disabled {
  cursor: default;
}

.chart-legend__item:not(:disabled):hover {
  background: var(--rapo-row-hover);
}

.chart-legend__item--off {
  opacity: 0.4;
  text-decoration: line-through;
}

.chart-legend__swatch {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 2px;
}

.chart-legend__swatch--line {
  height: 2px;
}

.chart-legend__value {
  color: var(--rapo-label);
}
</style>
