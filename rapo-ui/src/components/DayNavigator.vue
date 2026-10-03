<template>
  <!-- One segmented pill: previous day | the day | next day | today; the last two only on a day before today. -->
  <div class="day-nav" role="group" aria-label="Day">
    <q-btn flat square class="day-nav__seg" icon="fas fa-chevron-left" :aria-label="`Previous day: ${label(previous)}`" :disable="!day" @click="$emit('go', previous)">
      <q-tooltip anchor="bottom middle" self="top middle" :offset="[0, 8]">Previous day: {{ label(previous) }}</q-tooltip>
    </q-btn>
    <div v-if="!calendar" class="day-nav__day">{{ label(day) }}</div>
    <!-- The day opens a calendar: days with activity have a dot (red with errors), later days cannot be picked. -->
    <div v-else class="day-nav__day day-nav__day--pick" v-keyboard:button aria-haspopup="dialog" aria-label="Pick a day">
      {{ label(day) }}
      <q-icon name="fas fa-caret-down" size="12px" class="q-ml-sm day-nav__caret" />
      <q-popup-proxy ref="popup" transition-show="scale" transition-hide="scale" @before-show="openCalendar">
        <div class="day-nav__calendar">
          <q-date
            :model-value="pickerValue"
            minimal
            flat
            color="teal"
            first-day-of-week="1"
            :options="(date) => date <= pickerToday"
            :events="(date) => Boolean(marker(date))"
            :event-color="(date) => (marker(date) && marker(date).errors ? 'red-6' : 'teal')"
            @navigation="loadMonth"
            @update:model-value="pick" />
          <div class="row items-center q-px-md q-pb-sm day-nav__legend">
            <span class="legend-dot bg-teal" />{{ legend.count }}
            <span class="legend-dot bg-red-6 q-ml-md" />{{ legend.errors }}
            <q-space />
            <q-spinner v-if="loading" size="14px" color="teal" />
          </div>
        </div>
      </q-popup-proxy>
    </div>
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
    // (month "YYYY-MM") => Promise of {"YYYY-MM-DD": {count, errors}}: the dots of the calendar; without it the day is
    // plain text.
    calendar: { type: Function, default: null },
    // The legend under the calendar.
    legend: { type: Object, default: () => ({ count: "runs", errors: "errors" }) },
  },
  data() {
    return {
      // The markers of the months loaded since the calendar was opened, by YYYY-MM.
      markers: {},
      loading: false,
    };
  },
  emits: ["go"],
  computed: {
    previous() {
      return shiftDay(this.day, -1);
    },
    next() {
      return shiftDay(this.day, 1);
    },
    pickerValue() {
      return (this.day || "").replace(/-/g, "/");
    },
    pickerToday() {
      return (this.today || "9999-12-31").replace(/-/g, "/");
    },
    isToday() {
      return !this.today || this.day >= this.today;
    },
  },
  methods: {
    label: dayLabel,
    // q-date's YYYY/MM/DD → the marker of that day, if it had any activity.
    marker(date) {
      const day = date.replace(/\//g, "-");
      const month = this.markers[day.slice(0, 7)];
      return month ? month[day] : null;
    },
    // Fresh markers each time it opens, so today's dot is current.
    openCalendar() {
      this.markers = {};
      const month = (this.day || this.today || "").slice(0, 7);
      if (month) {
        this.loadMonth({ year: Number(month.slice(0, 4)), month: Number(month.slice(5, 7)) });
      }
    },
    async loadMonth({ year, month }) {
      const key = `${year}-${String(month).padStart(2, "0")}`;
      if (this.markers[key]) {
        return;
      }
      this.loading = true;
      try {
        this.markers = { ...this.markers, [key]: await this.calendar(key) };
      } catch (error) {
        // No dots then; the calendar still picks days.
        // eslint-disable-next-line no-console
        console.error("Calendar markers failed:", error);
      } finally {
        this.loading = false;
      }
    },
    pick(date) {
      if (date) {
        this.$refs.popup.hide();
        this.$emit("go", date.replace(/\//g, "-"));
      }
    },
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
.day-nav__day--pick {
  cursor: pointer;
  padding-right: 12px;
}
.day-nav__day--pick:hover {
  background: var(--rapo-teal-soft);
}
.day-nav__caret {
  color: var(--rapo-label);
}
.day-nav__calendar {
  background: var(--rapo-surface);
}
.day-nav__legend {
  font-size: 12px;
  color: var(--rapo-muted);
}
.legend-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  margin-right: 5px;
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
