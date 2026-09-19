<template>
  <span>
    <q-chip size="12px" class="row items-center period-chip" color="grey-6" icon="fas fa-history" text-color="white">
      {{ period }}
    </q-chip>
    <q-chip
      size="12px"
      class="row items-center"
      :class="{
        'bg-blue-grey-7': schedule_type === 'D',
        'bg-blue-grey-5': schedule_type === 'W',
        'bg-blue-grey-4': schedule_type === 'M',
        'bg-deep-purple-3': schedule_type === 'C',
        'bg-deep-purple-2 text-grey-9': schedule_type === 'X',
        'bg-grey-5': !schedule_type,
      }"
      text-color="white"
      icon="alarm">
      {{ schedule_text }}
    </q-chip>
  </span>
</template>

<script>
import { mapState } from "vuex";
import { parseSchedule, scheduleType, scheduleTime } from "../utils/schedule";

export default {
  props: ["schedule", "period_back", "period_type"],
  computed: {
    ...mapState(["controlCatalogue"]),
    // Computed from the prop so live catalogue updates are reflected; null when not scheduled or invalid.
    schedule_object() {
      try {
        return this.schedule ? parseSchedule(this.schedule) : null;
      } catch (err) {
        return null;
      }
    },
    period() {
      const back = Number(this.period_back);
      const isPlural = !Number.isNaN(back) ? back !== 1 : String(this.period_back) !== "1";
      const type =
        this.period_type === "D"
          ? "Day"
          : this.period_type === "W"
          ? "Week"
          : this.period_type === "M"
          ? "Month"
          : String(this.period_type || "");
      return `${this.period_back} ${type}${isPlural && type ? "s" : ""}`;
    },
    schedule_type() {
      return this.schedule_object ? scheduleType(this.schedule_object) : null;
    },
    schedule_text() {
      const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
      const schedule = this.schedule_object;

      if (!schedule) {
        return "Not scheduled";
      } else if (this.schedule_type === "X") {
        const filteredSchedule = Object.fromEntries(Object.entries(schedule).filter(([, value]) => value !== null));
        return JSON.stringify(filteredSchedule);
      } else if (this.schedule_type === "C") {
        const trigger = this.controlCatalogue.find((control) => control.control_id === Number(schedule.trigger_id));
        if (!schedule.trigger_id) {
          return "Cascade (no trigger)";
        }
        return "Cascade after " + (trigger ? trigger.control_name : "control_id " + schedule.trigger_id);
      } else if (this.schedule_type === "M") {
        return "Monthly (" + schedule.mday.join(", ") + ") @ " + scheduleTime(schedule);
      } else if (this.schedule_type === "W") {
        return "Weekly (" + schedule.wday.map((day) => days[day]).join(", ") + ") @ " + scheduleTime(schedule);
      } else {
        return "Daily @ " + scheduleTime(schedule);
      }
    },
  },
};
</script>

<style scoped>
.period-chip {
  width: 80px;
  min-width: 50px;
  display: inline-flex;
  justify-content: center;
}
</style>
