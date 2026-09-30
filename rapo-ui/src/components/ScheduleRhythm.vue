<template>
  <span v-if="rhythm" class="rhythm row no-wrap" :title="title">
    <span v-for="(on, index) in rhythm.slots" :key="index" class="tick" :class="on ? `bg-${color}` : 'off'" />
  </span>
</template>

<script>
import { scheduleRhythm } from "../utils/schedule";

// A strip of where the fires of a schedule fall: the hours of a day, the days of a week or of a month.
export default {
  props: {
    scheduleConfig: { type: String, default: null },
    color: { type: String, default: "grey-6" },
  },
  computed: {
    rhythm() {
      return scheduleRhythm(this.scheduleConfig);
    },
    title() {
      return { day: "Hours of the day it runs in (0–23)", week: "Week days it runs on (Mon–Sun)", month: "Days of the month it runs on (1–31)" }[this.rhythm.scale];
    },
  },
};
</script>

<style scoped>
/* One width for every scale: the 24, 7 or 31 ticks share it. */
.rhythm {
  flex: none;
  width: 72px;
  gap: 1px;
  height: 10px;
  align-items: stretch;
}
.tick {
  flex: 1 1 0;
  min-width: 0;
  border-radius: 1px;
}
.tick.off {
  background: var(--rapo-border-soft);
}
</style>
