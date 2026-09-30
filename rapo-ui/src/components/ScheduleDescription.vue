<template>
  <div class="schedule-description">
    <div class="description-text ellipsis" :class="{ 'text-grey-7': dim }">{{ text }}</div>
    <div v-if="hasRhythm || window" class="details row no-wrap items-center">
      <schedule-rhythm :schedule-config="scheduleConfig" :color="color" />
      <span v-if="window" class="window-chip" :title="windowTitle"><q-icon name="fas fa-history" size="9px" /> {{ window }}</span>
    </div>
  </div>
</template>

<script>
import ScheduleRhythm from "./ScheduleRhythm.vue";
import { describeSchedule, scheduleRhythm } from "../utils/schedule";

const PERIOD_NAMES = { D: "day", W: "week", M: "month" };

// A schedule in words, then the strip of where its fires fall and the data window of a run. Lines 2 and 3 of
// ScheduleSummary; the control editor shows it live under the schedule fields.
export default {
  components: { ScheduleRhythm },
  props: {
    scheduleConfig: { type: String, default: null },
    // The name of the control a cascade follows.
    triggerName: { type: String, default: null },
    // Controls that pull this one while it has no schedule of its own; shown instead of "Not scheduled".
    pulledBy: { type: Array, default: () => [] },
    periodBack: { type: [Number, String], default: null },
    periodNumber: { type: [Number, String], default: null },
    periodType: { type: String, default: null },
    color: { type: String, default: "grey-6" },
    dim: { type: Boolean, default: false },
  },
  computed: {
    hasRhythm() {
      return !!scheduleRhythm(this.scheduleConfig);
    },
    text() {
      const text = describeSchedule(this.scheduleConfig, this.triggerName);
      if (this.pulledBy.length && ["Not scheduled", "Never fires"].includes(text)) {
        return `Pulled by ${this.pulledBy.join(", ")}`;
      }
      return text;
    },
    // "1 day back", or "7 days, 1 back" for a window of several periods; null without a period type.
    window() {
      const name = PERIOD_NAMES[this.periodType];
      if (!name) {
        return null;
      }
      const back = Number(this.periodBack) || 0;
      const number = this.periodNumber == null || this.periodNumber === "" ? 1 : Number(this.periodNumber);
      const plural = (count) => `${count} ${name}${count === 1 ? "" : "s"}`;
      return number > 1 ? `${plural(number)}, ${back} back` : `${plural(back)} back`;
    },
    windowTitle() {
      return `Data window of a run: periods back ${this.periodBack ?? 0}, number of periods ${this.periodNumber ?? 1}, period type ${this.periodType}`;
    },
  },
};
</script>

<style scoped>
.schedule-description {
  font-size: 12px;
  line-height: 16px;
  min-width: 0;
}
.details {
  gap: 6px;
  margin-top: 2px;
}
.window-chip {
  flex: none;
  padding: 0 5px;
  border-radius: 8px;
  font-size: 11px;
  color: var(--rapo-muted);
  background: var(--rapo-surface-alt);
  border: 1px solid var(--rapo-border-soft);
  white-space: nowrap;
}
</style>
