<template>
  <!-- The scheduler at a glance, on the page title row: state, scheduling server, heartbeat, slots, next fire and the
       last 24 hours; details in tooltips, the slots, next fire and counters open their tab. -->
  <div v-if="status" class="row items-center status-bar">
    <q-chip class="status-chip">
      <q-avatar :color="state.color" text-color="white">
        <span class="state-dot" :class="{ 'state-dot--live': status.state === 'running' }" />
      </q-avatar>
      <span class="text-weight-bold">{{ state.label }}</span>
      <q-tooltip anchor="bottom middle" self="top middle" :offset="[0, 8]">{{ state.description }}</q-tooltip>
    </q-chip>

    <q-chip class="status-chip">
      <q-avatar icon="fas fa-server" :color="holder.alive ? 'blue-grey-6' : 'grey-5'" text-color="white" />
      <span class="text-weight-bold ellipsis chip-name">{{ holder.server || "No server" }}</span>
      <span v-if="holder.alive && holder.start_date" class="text-grey-7 q-ml-xs">&middot; up {{ age(holder.start_date) }}</span>
      <span v-else-if="holder.stop_date" class="text-grey-7 q-ml-xs">&middot; stopped {{ age(holder.stop_date) }} ago</span>
      <q-tooltip anchor="bottom middle" self="top middle" :offset="[0, 8]">
        <div v-if="holder.server">Scheduling server {{ holder.server }}</div>
        <div>
          {{ status.leader ? "This server schedules" : holder.alive ? "Another server schedules; this one takes over if it stops" : "No server holds the lease" }}
        </div>
        <div v-if="holder.pid">PID {{ holder.pid }}<template v-if="holder.username">, user {{ holder.username }}</template></div>
        <div v-if="holder.start_date">Since {{ toDateTimeString(holder.start_date) }}</div>
        <div v-if="status.next_maintenance">Next maintenance {{ toDateTimeString(status.next_maintenance) }} (in {{ age(status.next_maintenance, true) }})</div>
      </q-tooltip>
    </q-chip>

    <q-chip v-if="holder.heartbeat" class="status-chip">
      <q-avatar :color="heartbeatColor" text-color="white">
        <q-icon :key="holder.heartbeat" name="fas fa-heartbeat" size="14px" class="heart" />
      </q-avatar>
      <span class="text-weight-bold">{{ age(holder.heartbeat) }}</span>
      <q-tooltip anchor="bottom middle" self="top middle" :offset="[0, 8]">
        Last heartbeat {{ toTimeString(holder.heartbeat) }}; another server takes over after {{ status.lease_timeout }} s without one
      </q-tooltip>
    </q-chip>

    <q-chip clickable class="status-chip" @click="$emit('open', 'running')">
      <q-avatar color="transparent">
        <q-circular-progress
          :value="slotShare"
          size="24px"
          :thickness="0.32"
          :color="slotsFull ? 'deep-orange' : 'teal'"
          track-color="blue-grey-2" />
      </q-avatar>
      <span class="text-weight-bold">{{ runner.running.length }}/{{ runner.capacity }}</span>
      <span v-if="runner.queued.length" class="text-grey-7 q-ml-xs">+{{ runner.queued.length }}</span>
      <q-tooltip anchor="bottom middle" self="top middle" :offset="[0, 8]">
        {{ runner.running.length }} of {{ runner.capacity }} slots running, {{ runner.queued.length }} queued on this server: show them
      </q-tooltip>
    </q-chip>

    <q-chip v-if="nextFire" clickable class="status-chip" @click="$emit('open', 'upcoming')">
      <q-avatar :icon="triggerIcon(nextFire.trigger_type)" :color="status.disabled ? 'grey-5' : 'teal'" text-color="white" />
      <span class="text-weight-bold ellipsis chip-name" :class="{ 'text-grey-6': status.disabled }">{{ nextFire.control_name }}</span>
      <span class="text-grey-7 q-ml-xs">in {{ age(nextFire.scheduled_time, true) }}</span>
      <q-tooltip anchor="bottom middle" self="top middle" :offset="[0, 8]">
        <div>Next fire: {{ nextFire.control_name }} at {{ toDateTimeString(nextFire.scheduled_time) }}{{ status.disabled ? ", not run while the scheduler is stopped" : "" }}</div>
        <div>{{ fireCount }} fires in the next 24 hours<template v-if="status.scheduled_controls !== null">, {{ status.scheduled_controls }} scheduled controls</template></div>
        <div v-if="status.last_fire">Last fire {{ toDateTimeString(status.last_fire) }} ({{ age(status.last_fire) }} ago)</div>
        <div>Show the upcoming fires</div>
      </q-tooltip>
    </q-chip>

    <q-chip class="status-chip">
      <span class="text-grey-7 q-mr-xs">24 h</span>
      <span
        v-for="item in counters"
        :key="item.type"
        class="counter"
        :class="{ 'counter--zero': !item.count }"
        v-keyboard:button
        :aria-label="`${item.count} ${item.label.toLowerCase()} in the last 24 hours`"
        @click="$emit('open', 'history', item.type)">
        <q-icon :name="item.icon" :color="item.count ? item.color : 'grey-5'" size="13px" class="q-mr-xs" />
        <span class="text-weight-bold">{{ item.count }}</span>
        <q-tooltip anchor="bottom middle" self="top middle" :offset="[0, 8]">{{ item.label }} in the last 24 hours: show them</q-tooltip>
      </span>
    </q-chip>

    <scheduler-toggle-button class="q-ml-xs" />
  </div>
  <div v-else class="row items-center q-gutter-sm">
    <q-skeleton v-for="index in 5" :key="index" type="QChip" width="110px" />
  </div>
</template>

<script>
import SchedulerToggleButton from "./SchedulerToggleButton.vue";
import { TRIGGER_TYPES, schedulerEventType, schedulerState } from "../constants";
import { toDateTimeString, toMillis, toTimeString } from "../utils/format";

const COUNTED = ["STARTED", "MISSED", "FAILED"];

export default {
  name: "SchedulerStatusBar",
  components: { SchedulerToggleButton },
  props: {
    // scheduler-status, or null while it loads.
    status: { type: Object, default: null },
    // Server clock minus browser clock (ms), and the browser's now, ticking.
    clockOffset: { type: Number, default: 0 },
    now: { type: Number, required: true },
    // The first upcoming fire, or null; and the number of fires in the next 24 hours.
    nextFire: { type: Object, default: null },
    fireCount: { type: Number, default: 0 },
    // Events of the last 24 hours by event type.
    counts: { type: Object, default: () => ({}) },
  },
  emits: ["open"],
  computed: {
    state() {
      return schedulerState(this.status.state);
    },
    holder() {
      return this.status.holder || {};
    },
    runner() {
      return this.status.runner || { running: [], queued: [], capacity: 0 };
    },
    slotShare() {
      return this.runner.capacity ? Math.min(100, (100 * this.runner.running.length) / this.runner.capacity) : 0;
    },
    slotsFull() {
      return this.runner.capacity > 0 && this.runner.running.length >= this.runner.capacity;
    },
    // Green while fresh, amber past half the lease, red once another server may take over.
    heartbeatColor() {
      const seconds = this.seconds(this.holder.heartbeat);
      const lease = this.status.lease_timeout || 60;
      return seconds < lease / 2 ? "green-6" : seconds < lease ? "amber-8" : "red-6";
    },
    counters() {
      return COUNTED.map((type) => ({ type, count: this.counts[type] || 0, ...schedulerEventType(type) }));
    },
  },
  methods: {
    toDateTimeString,
    toTimeString,
    triggerIcon(type) {
      return (TRIGGER_TYPES[type] || TRIGGER_TYPES.SCHEDULE).icon;
    },
    // Seconds from a naive server datetime to now (or from now to it, ahead), on the server's clock.
    seconds(value, ahead = false) {
      const delta = (toMillis(value) - (this.now + this.clockOffset)) / 1000;
      return Math.max(0, Math.round(ahead ? delta : -delta));
    },
    // "4 s", "12 min", "3 h 12 min", "2 d 5 h".
    age(value, ahead = false) {
      const seconds = this.seconds(value, ahead);
      if (seconds < 60) return `${seconds} s`;
      const minutes = Math.floor(seconds / 60);
      if (minutes < 60) return `${minutes} min`;
      const hours = Math.floor(minutes / 60);
      if (hours < 24) return `${hours} h${minutes % 60 ? ` ${minutes % 60} min` : ""}`;
      return `${Math.floor(hours / 24)} d${hours % 24 ? ` ${hours % 24} h` : ""}`;
    },
  },
};
</script>

<style scoped>
.status-bar {
  flex-wrap: wrap;
  justify-content: flex-end;
  /* A little lower than centered on the title's tall line. */
  position: relative;
  top: 4px;
  font-size: 14px;
  letter-spacing: normal;
  line-height: normal;
}
.status-chip {
  margin: 2px 3px;
}
/* Long server and control names are cut; the tooltips name them in full. */
.chip-name {
  max-width: 170px;
}
.state-dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: currentColor;
}
.state-dot--live {
  animation: state-pulse 1.8s ease-out infinite;
}
@keyframes state-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.9);
  }
  70% {
    box-shadow: 0 0 0 7px rgba(255, 255, 255, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(255, 255, 255, 0);
  }
}
/* Re-created on each heartbeat (keyed), so it beats once. */
.heart {
  animation: heart-beat 0.7s ease-in-out 1;
}
@keyframes heart-beat {
  0%,
  100% {
    transform: scale(1);
  }
  25% {
    transform: scale(1.35);
  }
  50% {
    transform: scale(0.95);
  }
  70% {
    transform: scale(1.2);
  }
}
.counter {
  display: inline-flex;
  align-items: center;
  margin-right: 8px;
  cursor: pointer;
}
.counter:last-child {
  margin-right: 0;
}
.counter:hover .text-weight-bold {
  text-decoration: underline;
}
.counter--zero {
  color: var(--rapo-muted);
}
@media (prefers-reduced-motion: reduce) {
  .state-dot--live,
  .heart {
    animation: none;
  }
}
</style>
