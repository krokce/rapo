<template>
  <!-- One segmented pill: previous day | the day | next day | today; the last two only on a day before today. -->
  <div class="day-nav" role="group" aria-label="Day">
    <q-btn flat square class="day-nav__seg" icon="fas fa-chevron-left" :aria-label="`Previous day: ${label(previous)}`" :disable="!day" @click="$emit('go', previous)">
      <q-tooltip anchor="bottom middle" self="top middle" :offset="[0, 8]">Previous day: {{ label(previous) }}</q-tooltip>
    </q-btn>
    <div class="day-nav__day">{{ label(day) }}</div>
    <template v-if="day && !isToday">
      <q-btn flat square class="day-nav__seg" icon="fas fa-chevron-right" :aria-label="`Next day: ${label(next)}`" @click="$emit('go', next)">
        <q-tooltip anchor="bottom middle" self="top middle" :offset="[0, 8]">Next day: {{ label(next) }}</q-tooltip>
      </q-btn>
      <q-btn flat square class="day-nav__seg" icon="fas fa-step-forward" :aria-label="`Today: ${label(today)}`" @click="$emit('go', today)">
        <q-tooltip anchor="bottom middle" self="top middle" :offset="[0, 8]">Today: {{ label(today) }}</q-tooltip>
      </q-btn>
    </template>
  </div>
</template>

<script>
import { dayLabel, shiftDay } from "../utils/format";

// The day navigator of the day pages (Results, Files), in their title: emits go(day) with a YYYY-MM-DD day; the page
// decides the route (today is its plain path).
export default {
  name: "DayNavigator",
  props: {
    // The day shown and the server's today, YYYY-MM-DD.
    day: { type: String, default: null },
    today: { type: String, default: null },
  },
  emits: ["go"],
  computed: {
    previous() {
      return shiftDay(this.day, -1);
    },
    next() {
      return shiftDay(this.day, 1);
    },
    isToday() {
      return !this.today || this.day >= this.today;
    },
  },
  methods: {
    label: dayLabel,
  },
};
</script>

<style scoped>
.day-nav {
  display: inline-flex;
  align-items: stretch;
  height: 40px;
  border: 1px solid var(--rapo-panel-border);
  border-radius: 20px;
  background: var(--rapo-surface);
  overflow: hidden;
  font-size: 20px;
  line-height: 1;
  letter-spacing: normal;
  /* Lower than centered on the title's tall line, nearer its baseline. */
  position: relative;
  top: 5px;
}
.day-nav__day {
  display: flex;
  align-items: center;
  padding: 0 16px;
  color: var(--rapo-strong);
  font-weight: 400;
  white-space: nowrap;
}
.day-nav__seg {
  min-width: 40px;
  min-height: 0;
  padding: 0 12px;
  color: var(--rapo-teal);
  font-size: 12px;
}
.day-nav > * + * {
  border-left: 1px solid var(--rapo-panel-border);
}
</style>
