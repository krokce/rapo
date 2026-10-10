<template>
  <div class="mini-bars">
    <div
      v-for="item in items"
      :key="item.key"
      class="bar-row row no-wrap items-center"
      :class="{ 'cursor-pointer bar-row--link': clickable && item.filter !== false }"
      :title="item.title || `${item.label}: ${formatNumber(item.count)}${item.pct === undefined ? '' : ` (${formatPct(item.pct)})`}`"
      v-keyboard:button="clickable && item.filter !== false"
      @click="clickable && item.filter !== false && $emit('select', item)">
      <div class="bar-label ellipsis" :class="{ 'text-italic text-grey-7': item.muted }">{{ item.label }}</div>
      <div class="col bar-track">
        <div class="bar" :class="{ 'bar--muted': item.muted }" :style="{ width: Math.min(100, Math.max((item.count * 100) / top, 0.5)) + '%', background: item.color || 'var(--rapo-bar)' }" />
      </div>
      <div class="bar-count text-right number-cell">{{ formatNumber(item.count) }}</div>
      <div v-if="showPct" class="bar-pct text-right text-grey-7">{{ formatPct(item.pct) }}</div>
    </div>
  </div>
</template>

<script>
import { formatNumber } from "../../utils/format";
import { formatPct } from "../../utils/analysis";

// A list of values as horizontal bars (label, bar, count, share), drawn with CSS, so a page of them costs no charts.
// `items` are [{key, label, count, pct, muted, color, title, filter}]; a click emits the item, unless its `filter` is
// false.
export default {
  name: "MiniBars",
  props: {
    items: { type: Array, required: true },
    // The count of a full bar; the largest item by default.
    max: { type: Number, default: null },
    clickable: { type: Boolean, default: true },
    showPct: { type: Boolean, default: true },
  },
  emits: ["select"],
  computed: {
    top() {
      return this.max || Math.max(1, ...this.items.map((item) => item.count));
    },
  },
  methods: {
    formatNumber,
    formatPct,
  },
};
</script>

<style scoped>
.bar-row {
  font-size: 13px;
  height: 22px;
  border-radius: 3px;
}

.bar-row--link:hover {
  background: var(--rapo-teal-soft);
}

.bar-label {
  width: 38%;
  padding: 0 8px 0 2px;
}

.bar-track {
  height: 10px;
}

.bar {
  height: 100%;
  border-radius: 2px;
}

.bar--muted {
  opacity: 0.4;
}

.bar-count {
  width: 64px;
  padding-left: 6px;
}

.bar-pct {
  width: 48px;
  font-size: 12px;
}
</style>
