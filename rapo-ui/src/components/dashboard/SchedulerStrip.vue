<template>
  <div>
    <div class="scheduler-strip__head row items-center q-mb-xs">
      <q-chip dense class="q-ml-none" :title="state.description">
        <q-avatar :color="state.color" text-color="white"><q-icon name="fas fa-clock" size="11px" /></q-avatar>
        <span class="text-weight-bold">{{ state.label }}</span>
      </q-chip>
      <template v-if="status">
        <span class="scheduler-strip__fact" :title="holder.server ? `Server holding the scheduler's lease` : ''">
          <q-icon name="fas fa-server" size="11px" class="q-mr-xs" />{{ holder.server || "No server" }}
        </span>
        <span v-if="holder.heartbeat" class="scheduler-strip__fact" :class="{ 'text-negative': !holder.alive }" title="Last heartbeat of the scheduling server">
          <q-icon name="fas fa-heartbeat" size="11px" class="q-mr-xs" />{{ age(holder.heartbeat) }}
        </span>
        <span class="scheduler-strip__fact" title="Runs in the slots of this server, and queued">
          <q-icon name="fas fa-sync" size="11px" class="q-mr-xs" />{{ runner.running.length }}/{{ runner.capacity }} slots<template v-if="runner.queued.length"> · {{ runner.queued.length }} queued</template>
        </span>
      </template>
      <q-space />
      <q-chip v-if="data.missed_total" dense clickable class="q-mr-none" title="Fires lost while no scheduler ran, never run since: show them" @click="$emit('open', { path: '/scheduler', query: { missed: '1' } })">
        <q-avatar color="amber-8" text-color="white" icon="fas fa-exclamation-triangle" />
        {{ data.missed_total }}{{ data.missed_capped ? "+" : "" }} missed
      </q-chip>
    </div>
    <heat-strip :rows="rows" :columns="columns" :label-width="112" :cell-height="20" unit="" numbers @pick="pick" />
  </div>
</template>

<script>
import HeatStrip from "./HeatStrip.vue";
import { schedulerEventType, schedulerState } from "../../constants";
import { dayLabel, toMillis } from "../../utils/format";

// The rows of the last 24 hours, in this order; types without events in them are left out but Started.
const PAST_ROWS = ["STARTED", "MISSED", "FAILED", "CANCELED"];

// The scheduler around now: its state, server, heartbeat and slots in one line, then one strip of 48 hours, the last 24
// (what it did, by event type) and the next 24 (the fires to come) on each side of Now. Missed fires never caught up are
// a chip that opens them.
export default {
  name: "SchedulerStrip",
  components: { HeatStrip },
  props: {
    // The scheduler part of get-dashboard.
    data: { type: Object, required: true },
    // scheduler-status (the store's), and the browser's now (ms), ticking.
    status: { type: Object, default: null },
    now: { type: Number, required: true },
  },
  emits: ["open"],
  computed: {
    state() {
      return schedulerState(this.status && this.status.state);
    },
    holder() {
      return (this.status && this.status.holder) || {};
    },
    runner() {
      return (this.status && this.status.runner) || { running: [], queued: [], capacity: 0 };
    },
    hours() {
      return [...this.data.past.hours, ...this.data.upcoming.hours];
    },
    columns() {
      const past = this.data.past.hours.length;
      return this.hours.map((hour, index) => {
        const text = hour.slice(11, 13);
        const future = index >= past;
        return {
          // Every 3rd hour, but next to Now (its label takes their room).
          label: index === past ? "Now" : Number(text) % 3 === 0 && (index < past - 1 || index > past + 2) ? text : "",
          title: `${future ? "Next" : "Last"} 24 h · ${dayLabel(hour.slice(0, 10))} ${text}:00`,
          divider: index === past,
        };
      });
    },
    rows() {
      const past = this.data.past.hours.length;
      const future = this.data.upcoming.hours.length;
      const events = Object.fromEntries(this.data.past.events.map((item) => [item.code, item.counts]));
      const rows = PAST_ROWS.filter((code) => code === "STARTED" || events[code]).map((code) => {
        const info = schedulerEventType(code);
        const counts = events[code] || Array(past).fill(0);
        return {
          key: code,
          label: info.label,
          color: info.color,
          total: counts.reduce((sum, value) => sum + value, 0),
          cells: [...counts.map((count) => ({ count })), ...Array(future).fill(null)],
        };
      });
      rows.push({
        key: "UPCOMING",
        label: "Scheduled",
        color: "teal-7",
        title: "Fires of the next 24 hours: own schedules, cascades and chain sources",
        total: this.data.upcoming.counts.reduce((sum, value) => sum + value, 0),
        cells: [...Array(past).fill(null), ...this.data.upcoming.counts.map((count) => ({ count }))],
      });
      return rows;
    },
    // The server's clock minus the browser's.
    offset() {
      return this.status && this.status.server_time ? toMillis(this.status.server_time) - Date.now() : 0;
    },
  },
  methods: {
    age(value) {
      const seconds = Math.max(0, Math.round((this.now + this.offset - toMillis(value)) / 1000));
      if (seconds < 60) return `${seconds} s`;
      const minutes = Math.floor(seconds / 60);
      return minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
    },
    pick({ row }) {
      if (row === "UPCOMING") {
        this.$emit("open", { path: "/scheduler", query: { tab: "upcoming" } });
      } else {
        this.$emit("open", { path: "/scheduler", query: { tab: "history", event: row } });
      }
    },
  },
};
</script>

<style scoped>
.scheduler-strip__head {
  gap: 4px 12px;
  font-size: var(--rapo-dash-note);
}

.scheduler-strip__fact {
  color: var(--rapo-strong);
  white-space: nowrap;
}
</style>
