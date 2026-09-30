<template>
  <div class="schedule-summary row no-wrap items-center" :class="{ compact }" :title="title">
    <router-link :to="editLink" class="summary-link row no-wrap items-center">
      <q-avatar :size="compact ? '22px' : '28px'" :color="avatarColor" text-color="white" :icon="avatarIcon" class="summary-avatar" />
    </router-link>
    <div class="col summary-lines">
      <router-link :to="editLink" class="summary-link next-line row no-wrap items-baseline">
        <template v-if="fire">
          <span class="next-time" :class="{ 'text-grey-7': !schedulerActive }"><span v-if="fire.source !== 'schedule'">≈ </span>{{ fireLabel }}</span>
          <span class="countdown">({{ countdown }})</span>
        </template>
        <span v-else class="text-grey-7">{{ idleLabel }}</span>
      </router-link>
      <schedule-description
        :schedule-config="control.schedule_config"
        :trigger-name="triggerName"
        :pulled-by="pulledBy"
        :period-back="control.period_back"
        :period-number="control.period_number"
        :period-type="control.period_type"
        :color="control.status === 'Y' || fire ? frequencyColor : 'grey-5'"
        :dim="control.status !== 'Y'" />
    </div>
  </div>
</template>

<script>
import ScheduleDescription from "./ScheduleDescription.vue";
import { FIRE_SOURCES, scheduleFrequencyStyle } from "../constants";
import { scheduleFrequency, describeSchedule } from "../utils/schedule";
import { toDateTimeString } from "../utils/format";

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const pad = (value) => String(value).padStart(2, "0");

// Naive server datetime string as a local Date, read like the server wrote it.
function toDate(value) {
  return new Date(String(value).substring(0, 19));
}

// A data window bound without the midnight or end-of-day time.
function windowBound(value) {
  return toDateTimeString(value).replace(/ (00:00:00|23:59:59)$/, "");
}

// The Controls schedule column: when the control runs next (get-next-fires: scheduled, after the control it
// cascades from, or pulled by a control reading its results) and in how long, then the schedule in words. The
// avatar is colored by how often it runs and shows what starts the next run; it links to the editor's Scheduler tab.
export default {
  components: { ScheduleDescription },
  props: {
    control: { type: Object, required: true },
    // The control's get-next-fires entry ({ fires, invalid }), undefined while not loaded.
    next: { type: Object, default: undefined },
    // Server time in milliseconds, advanced by the page's ticker.
    now: { type: Number, required: true },
    schedulerActive: { type: Boolean, default: true },
    triggerName: { type: String, default: null },
    compact: { type: Boolean, default: false },
  },
  computed: {
    fires() {
      return (this.next && this.next.fires) || [];
    },
    fire() {
      return this.fires[0] || null;
    },
    pulledBy() {
      return [...new Set(this.fires.filter((fire) => fire.source === "chain").map((fire) => fire.via))];
    },
    frequency() {
      const frequency = scheduleFrequency(this.control.schedule_config);
      return frequency === "none" && this.pulledBy.length ? "chain" : frequency;
    },
    frequencyColor() {
      return scheduleFrequencyStyle(this.frequency).color;
    },
    avatarColor() {
      return this.control.status !== "Y" && !this.fire ? "grey-5" : this.frequencyColor;
    },
    avatarIcon() {
      if (this.fire && !this.schedulerActive) return "fas fa-pause";
      if (this.fire) return FIRE_SOURCES[this.fire.source].icon;
      if (this.control.status !== "Y") return "fas fa-power-off";
      return this.frequency === "cascade" ? FIRE_SOURCES.cascade.icon : "fas fa-minus";
    },
    idleLabel() {
      if (this.next === undefined) return "…";
      if (this.next.invalid) return "Invalid schedule";
      if (this.control.status !== "Y") return "Inactive";
      return this.frequency === "cascade" ? "No run ahead" : "Not scheduled";
    },
    // Today 14:20, Tomorrow 08:15, Thu 02.10 08:15, 01.11 18:15 (seconds only when set, the year only when another).
    fireLabel() {
      const at = toDate(this.fire.time);
      const today = new Date(this.now);
      const days = Math.round((new Date(at.getFullYear(), at.getMonth(), at.getDate()) - new Date(today.getFullYear(), today.getMonth(), today.getDate())) / 86400000);
      const time = `${pad(at.getHours())}:${pad(at.getMinutes())}${at.getSeconds() ? `:${pad(at.getSeconds())}` : ""}`;
      const date = `${pad(at.getDate())}.${pad(at.getMonth() + 1)}${at.getFullYear() !== today.getFullYear() ? `.${at.getFullYear()}` : ""}`;
      if (days <= 0) return `Today ${time}`;
      if (days === 1) return `Tomorrow ${time}`;
      if (days < 7) return `${WEEKDAYS[at.getDay()]} ${date} ${time}`;
      return `${date} ${time}`;
    },
    // in 45s, in 23m, in 17h 55m, in 2d 3h, in 31d.
    countdown() {
      const seconds = Math.round((toDate(this.fire.time).getTime() - this.now) / 1000);
      if (seconds <= 0) return "now";
      if (seconds < 60) return "in <1m";
      const minutes = Math.floor(seconds / 60);
      const days = Math.floor(minutes / 1440);
      const hours = Math.floor((minutes % 1440) / 60);
      if (days >= 7) return `in ${days}d`;
      if (days) return `in ${days}d${hours ? ` ${hours}h` : ""}`;
      if (hours) return `in ${hours}h ${minutes % 60}m`;
      return `in ${minutes}m`;
    },
    editLink() {
      return { name: "edit-control", params: { controlId: this.control.control_id }, query: { tab: "scheduler" } };
    },
    // One title for the whole cell (no per-row tooltip component): the schedule, then the next runs with their data.
    title() {
      const lines = [`${scheduleFrequencyStyle(this.frequency).label}: ${describeSchedule(this.control.schedule_config, this.triggerName)}`];
      if (this.fires.length) {
        if (!this.schedulerActive) {
          lines.push("The scheduler is stopped, so these runs wait for it to start.");
        }
        lines.push("", "Next runs (data window):");
        this.fires.forEach((fire) => {
          const source = fire.source === "schedule" ? "" : ` — ${FIRE_SOURCES[fire.source].label.toLowerCase()} ${fire.via}`;
          const window = fire.date_from ? `${windowBound(fire.date_from)} – ${windowBound(fire.date_to)}` : "invalid period";
          lines.push(`${toDateTimeString(fire.time)}${source} (${window})`);
        });
      }
      lines.push("", "Click to open the control's Scheduler tab.");
      return lines.join("\n");
    },
  },
};
</script>

<style scoped>
.schedule-summary {
  gap: 8px;
  min-width: 0;
}
.summary-lines {
  min-width: 0;
}
.summary-link {
  color: inherit;
  text-decoration: none;
}
.next-line {
  width: 100%;
  gap: 6px;
  font-size: 13px;
  line-height: 18px;
}
.next-time {
  font-weight: 500;
  white-space: nowrap;
}
.countdown {
  color: var(--rapo-muted);
  white-space: nowrap;
}
.compact .next-line {
  font-size: 12px;
}
</style>
