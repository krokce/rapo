<template>
  <div class="mini-histogram">
    <div class="columns row no-wrap items-end" :style="{ height: height + 'px' }">
      <div
        v-for="(bar, index) in bars"
        :key="index"
        class="column-slot col"
        :class="{ 'cursor-pointer column-slot--link': clickable && bar.count }"
        :title="bar.title"
        @click="clickable && bar.count && $emit('select', index)">
        <div class="column-bar" :style="{ height: barHeight(bar.count), background: color }" />
      </div>
    </div>
    <div class="row no-wrap axis text-grey-7">
      <div class="ellipsis">{{ start }}</div>
      <q-space />
      <div class="ellipsis text-right">{{ end }}</div>
    </div>
  </div>
</template>

<script>
// A histogram drawn with CSS: one column per bin, its title the bin and its count, the first and last edge under it.
// A click on a non-empty bin emits its index.
export default {
  name: "MiniHistogram",
  props: {
    // [{count, title}]
    bars: { type: Array, required: true },
    start: { type: String, default: "" },
    end: { type: String, default: "" },
    color: { type: String, default: "var(--rapo-hist)" },
    height: { type: Number, default: 60 },
    clickable: { type: Boolean, default: true },
  },
  emits: ["select"],
  computed: {
    top() {
      return Math.max(1, ...this.bars.map((bar) => bar.count));
    },
  },
  methods: {
    // A bin with records stays visible however small it is next to the largest.
    barHeight(count) {
      return count ? `${Math.max((count * 100) / this.top, 4)}%` : "0";
    },
  },
};
</script>

<style scoped>
.columns {
  gap: 2px;
  border-bottom: 1px solid var(--rapo-grid);
}

.column-slot {
  height: 100%;
  display: flex;
  align-items: flex-end;
  border-radius: 2px 2px 0 0;
}

.column-slot--link:hover {
  background: var(--rapo-teal-soft);
}

.column-bar {
  width: 100%;
  border-radius: 2px 2px 0 0;
}

.axis {
  font-size: 11px;
  gap: 8px;
  padding-top: 2px;
}
</style>
