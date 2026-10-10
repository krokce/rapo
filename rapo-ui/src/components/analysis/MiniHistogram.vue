<template>
  <div class="mini-histogram row no-wrap">
    <div v-if="before" class="edge-slot column">
      <div class="column-slot edge-bar" :class="{ 'cursor-pointer column-slot--link': clickable }" :style="{ height: height + 'px' }" :title="before.title" @click="clickable && $emit('select', 'before')">
        <div class="column-bar column-bar--faint" :style="{ height: barHeight(before.count), background: color }" />
      </div>
    </div>
    <div class="col">
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
      <div v-if="ticks" class="ticks text-grey-7">
        <span v-for="tick in ticks" :key="tick.index" class="tick" :class="tickClass(tick)" :style="{ left: (tick.index * 100) / bars.length + '%' }">{{ tick.label }}</span>
      </div>
      <div v-else class="row no-wrap axis text-grey-7">
        <div class="ellipsis">{{ start }}</div>
        <q-space />
        <div class="ellipsis text-right">{{ end }}</div>
      </div>
    </div>
    <div v-if="after" class="edge-slot column">
      <div class="column-slot edge-bar" :class="{ 'cursor-pointer column-slot--link': clickable }" :style="{ height: height + 'px' }" :title="after.title" @click="clickable && $emit('select', 'after')">
        <div class="column-bar column-bar--faint" :style="{ height: barHeight(after.count), background: color }" />
      </div>
    </div>
  </div>
</template>

<script>
// A histogram drawn with CSS: one column per bin, its title the bin and its count; under it the first and last edge,
// or `ticks` [{index, label}] placed at a bin edge (a whole index) or a bin's middle (index + 0.5). `before` and
// `after` ({count, title}) are faded columns set apart at the ends, for records outside the bins. A click on a
// non-empty bin emits its index, on an end column "before" or "after".
export default {
  name: "MiniHistogram",
  props: {
    // [{count, title}]
    bars: { type: Array, required: true },
    start: { type: String, default: "" },
    end: { type: String, default: "" },
    ticks: { type: Array, default: null },
    before: { type: Object, default: null },
    after: { type: Object, default: null },
    color: { type: String, default: "var(--rapo-hist)" },
    height: { type: Number, default: 60 },
    clickable: { type: Boolean, default: true },
  },
  emits: ["select"],
  computed: {
    top() {
      return Math.max(1, ...this.bars.map((bar) => bar.count), this.before ? this.before.count : 0, this.after ? this.after.count : 0);
    },
  },
  methods: {
    // A bin with records stays visible however small it is next to the largest.
    barHeight(count) {
      return count ? `${Math.max((count * 100) / this.top, 4)}%` : "0";
    },
    // The first and last labels stay inside the chart.
    tickClass(tick) {
      if (tick.index <= 0) {
        return "tick--first";
      }
      return tick.index >= this.bars.length ? "tick--last" : "";
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

.column-bar--faint {
  opacity: 0.35;
}

.edge-slot {
  width: 10px;
  margin: 0 5px;
}

.edge-bar {
  border-bottom: 1px dashed var(--rapo-grid);
}

.axis {
  font-size: 11px;
  gap: 8px;
  padding-top: 2px;
}

.ticks {
  position: relative;
  height: 16px;
  font-size: 11px;
}

.tick {
  position: absolute;
  top: 2px;
  transform: translateX(-50%);
  white-space: nowrap;
}

.tick--first {
  transform: none;
}

.tick--last {
  transform: translateX(-100%);
}
</style>
