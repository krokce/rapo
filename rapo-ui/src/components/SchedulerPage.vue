<template>
  <q-page class="column no-wrap" :style-fn="fillViewport">
    <h2 class="row q-gutter-lg q-mb-lg">
      <div>Scheduler</div>
    </h2>

    <q-card class="q-mb-lg" v-if="status">
      <q-card-section>
        <div class="row items-center q-gutter-lg">
          <div class="column">
            <q-chip size="lg" text-color="white" :color="state.color" class="text-weight-bold q-ma-none">
              {{ state.label }}
            </q-chip>
            <small class="text-grey-7 q-mt-xs" style="max-width: 240px">{{ state.description }}</small>
          </div>
          <div class="status-item">
            <div class="status-label">Scheduling server</div>
            <div class="status-value">{{ status.holder.server || "N/A" }} <small v-if="status.holder.pid">PID {{ status.holder.pid }}</small></div>
            <div v-if="status.holder.alive"><small class="text-grey-7">since</small> <date-time-text :value="status.holder.start_date" /></div>
            <div v-else-if="status.holder.stop_date"><small class="text-grey-7">stopped</small> <date-time-text :value="status.holder.stop_date" /></div>
          </div>
          <div class="status-item">
            <div class="status-label">Heartbeat</div>
            <div class="status-value">{{ toTimeString(status.holder.heartbeat) || "N/A" }}</div>
            <small class="text-grey-7">lease timeout {{ status.lease_timeout }} s</small>
          </div>
          <div class="status-item">
            <div class="status-label">Execution slots</div>
            <div class="status-value">{{ runner.running.length }} / {{ runner.capacity }} running</div>
            <small class="text-grey-7">{{ runner.queued.length }} queued on this server</small>
          </div>
          <div class="status-item" v-if="status.leader">
            <div class="status-label">Scheduled controls</div>
            <div class="status-value">{{ status.scheduled_controls }}</div>
            <div v-if="status.last_fire"><small class="text-grey-7">last fire</small> <date-time-text :value="status.last_fire" /></div>
            <small v-else class="text-grey-7">last fire none yet</small>
          </div>
          <div class="status-item" v-if="status.next_maintenance">
            <div class="status-label">Next maintenance</div>
            <div class="status-value"><date-time-text :value="status.next_maintenance" /></div>
          </div>
          <q-space />
          <scheduler-toggle-button />
        </div>
      </q-card-section>

      <template v-if="activeJobs.length">
        <q-separator />
        <q-card-section>
          <q-markup-table dense flat>
            <thead>
              <tr class="bg-blue-grey-1">
                <th class="text-left">State</th>
                <th class="text-left">Control</th>
                <th class="text-left">Trigger</th>
                <th class="text-center">Run PID</th>
                <th class="text-center">OS PID</th>
                <th class="text-left">Queued</th>
                <th class="text-left">Started</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="job in activeJobs" :key="job.event_id">
                <td>
                  <q-icon :name="job.state === 'running' ? 'fas fa-sync fa-spin' : 'fas fa-hourglass-half'" :color="job.state === 'running' ? 'blue' : 'indigo'" class="q-mr-sm" />
                  {{ job.state === "running" ? "Running" : "Queued" }}
                </td>
                <td class="text-weight-bold text-teal">{{ job.control_name }}</td>
                <td><q-icon :name="triggerType(job.trigger_type).icon" color="blue-grey-5" class="q-mr-xs" /> {{ triggerType(job.trigger_type).label }}</td>
                <td class="text-center text-blue-grey-7">{{ job.process_id }}</td>
                <td class="text-center text-blue-grey-7">{{ job.pid }}</td>
                <td>{{ toTimeString(job.queued) }}</td>
                <td>{{ toTimeString(job.started) }}</td>
                <td style="width: 50px">
                  <q-btn size="sm" color="grey-7" round flat icon="fas fa-times" @click="cancelRun(job, refreshAll)">
                    <q-tooltip>Cancel run</q-tooltip>
                  </q-btn>
                </td>
              </tr>
            </tbody>
          </q-markup-table>
        </q-card-section>
      </template>
    </q-card>

    <q-card class="q-mb-lg" v-if="!status">
      <q-card-section class="row items-center q-gutter-lg">
        <q-skeleton type="QChip" width="120px" height="40px" />
        <div v-for="index in 4" :key="index" class="status-item">
          <q-skeleton type="text" width="110px" />
          <q-skeleton type="text" width="150px" height="24px" />
          <q-skeleton type="text" width="90px" />
        </div>
      </q-card-section>
    </q-card>

    <q-card class="tabs-card">
      <q-tabs
        v-model="tab"
        class="text-white bg-blue-grey-7"
        active-color="light-blue-1"
        indicator-color="light-blue-1"
        align="left"
        inline-label
        narrow-indicator
        no-caps>
        <q-tab name="upcoming" icon="fas fa-calendar-alt" label="Upcoming" />
        <q-tab name="history" icon="fas fa-history" label="History" />
      </q-tabs>

      <q-separator />

      <q-tab-panels v-model="tab" keep-alive class="fill-panels">
        <q-tab-panel name="upcoming">
          <div class="q-ma-lg q-gutter-y-md fill-column">
            <div class="row items-center">
              <q-select
                v-model="upcomingHours"
                class="col-2 q-pa-sm"
                outlined
                emit-value
                map-options
                options-dense
                :options="horizonOptions"
                label="Horizon"
                @update:model-value="refreshUpcoming" />
              <q-input clearable class="col-4 q-pa-sm" outlined v-model="upcomingFilter" label="Control name" maxlength="45" />
              <div class="col q-pa-sm text-grey-7" v-if="status && status.disabled">
                <q-icon name="fas fa-exclamation-triangle" color="deep-orange" /> The scheduler is stopped, these fires will not run until it is started.
              </div>
            </div>
            <q-virtual-scroll
              type="table"
              dense
              flat
              class="list-table upcoming-table"
              :items="filteredUpcoming"
              :virtual-scroll-item-size="41"
              :virtual-scroll-sticky-size-start="28"
              :table-colspan="7">
              <template #before>
                <thead>
                  <tr class="bg-blue-grey-2">

                    <th class="text-left">Type</th>
                    <th class="text-left">Scheduled for</th>
                    <th class="text-left">In</th>
                    <th class="text-left">Control</th>
                    <th class="text-left">Run from</th>
                    <th class="text-left">Run to</th>
                    <th class="text-left">Group</th>
                  </tr>
                </thead>
              </template>
              <template #default="{ item: fire, index }">
                <tr :key="fire.control_id + fire.scheduled_time">
                  <td :class="{ 'new-day-separator': newDay(filteredUpcoming, index, 'scheduled_time') }">
                    <q-chip size="11px" :title="controlType(fire.control_type).label">
                      <q-avatar :icon="controlType(fire.control_type).icon" :color="controlType(fire.control_type).color" text-color="white" />
                      {{ fire.control_type }}
                    </q-chip>
                  </td>
                  <td :class="{ 'new-day-separator': newDay(filteredUpcoming, index, 'scheduled_time') }">
                    <date-time-text :value="fire.scheduled_time" />
                  </td>
                  <td class="text-grey-8" :class="{ 'new-day-separator': newDay(filteredUpcoming, index, 'scheduled_time') }">{{ fromNow(fire.scheduled_time) }}</td>
                  <td class="text-weight-bold" :class="{ 'new-day-separator': newDay(filteredUpcoming, index, 'scheduled_time') }">
                    <router-link :to="{ name: 'edit-control', params: { controlId: fire.control_id } }" :class="'text-' + controlTypeColor(fire.control_type)">
                      {{ fire.control_name }}
                    </router-link>
                  </td>
                  <td class="text-weight-bold text-blue-grey-7" :class="{ 'new-day-separator': newDay(filteredUpcoming, index, 'scheduled_time') }">
                    {{ toDateString(fire.date_from) }}
                  </td>
                  <td class="text-weight-bold text-blue-grey-7" :class="{ 'new-day-separator': newDay(filteredUpcoming, index, 'scheduled_time') }">
                    {{ toDateString(fire.date_to) }}
                  </td>
                  <td class="text-grey-8" :class="{ 'new-day-separator': newDay(filteredUpcoming, index, 'scheduled_time') }">{{ fire.control_group }}</td>
                </tr>
              </template>
              <template #after>
                <tbody v-if="!loaded">
                  <skeleton-rows v-if="!loaded" :rows="6" :columns="['QChip', 'text', 'text', 'text', 'text', 'text', 'text']" />
                </tbody>
                <tbody v-else-if="!filteredUpcoming.length">
                  <tr>
                    <td colspan="7" class="text-grey-7 text-center">No fires within {{ upcomingHours }} hours</td>
                  </tr>
                </tbody>
              </template>
            </q-virtual-scroll>
          </div>
        </q-tab-panel>

        <q-tab-panel name="history">
          <div class="q-ma-lg q-gutter-y-md fill-column">
            <div class="row items-center">
              <q-input clearable class="col-3 q-pa-sm" outlined v-model="filter.control_name" label="Control name" maxlength="45" />
              <q-select
                v-model="filter.event_type"
                class="col-2 q-pa-sm"
                clearable
                outlined
                options-dense
                emit-value
                map-options
                :options="eventTypeOptions"
                label="Event" />
              <q-select
                v-model="filter.trigger_type"
                class="col-2 q-pa-sm"
                clearable
                outlined
                options-dense
                emit-value
                map-options
                :options="triggerTypeOptions"
                label="Trigger" />
              <q-btn flat round color="grey" class="q-pa-sm" icon="fas fa-times-circle" @click="clearFilters">
                <q-tooltip anchor="top left" self="bottom left" :offset="[15, 10]"> Clear filters </q-tooltip>
              </q-btn>
              <q-space />
              <small class="text-grey-7 q-pa-sm">Latest {{ events.length }} events</small>
            </div>
            <q-virtual-scroll
              type="table"
              dense
              flat
              class="list-table history-table"
              :style="{ '--name-column-width': eventNameWidth + 'px' }"
              :items="filteredEvents"
              :virtual-scroll-item-size="41"
              :virtual-scroll-sticky-size-start="28"
              :table-colspan="12">
              <template #before>
                <thead>
                  <tr class="bg-blue-grey-2">

                    <th class="text-left">Type</th>
                    <th class="text-left">Recorded</th>
                    <th class="text-left">Scheduled for</th>
                    <th class="text-center">PID</th>
                    <th class="text-left">Control</th>
                    <th class="text-left">Run from</th>
                    <th class="text-left">Run to</th>
                    <th class="text-left">Trigger</th>
                    <th class="text-left">Event</th>
                    <th class="text-left">Run</th>
                    <th class="text-left">Message</th>
                    <th></th>
                  </tr>
                </thead>
              </template>
              <template #default="{ item: event, index }">
                <tr :key="event.event_id">
                  <td :class="{ 'new-day-separator': newDay(filteredEvents, index, 'event_time') }">
                    <q-chip v-if="event.control_type" size="11px" :title="controlType(event.control_type).label">
                      <q-avatar :icon="controlType(event.control_type).icon" :color="controlType(event.control_type).color" text-color="white" />
                      {{ event.control_type }}
                    </q-chip>
                  </td>
                  <td :class="{ 'new-day-separator': newDay(filteredEvents, index, 'event_time') }">
                    <date-time-text :value="event.event_time" />
                  </td>
                  <td :class="{ 'new-day-separator': newDay(filteredEvents, index, 'event_time') }">
                    <date-time-text :value="event.scheduled_time" />
                  </td>
                  <td class="text-center text-weight-bold text-blue-grey-7" :class="{ 'new-day-separator': newDay(filteredEvents, index, 'event_time') }">
                    {{ event.process_id }}
                  </td>
                  <td class="text-weight-bold" :class="{ 'new-day-separator': newDay(filteredEvents, index, 'event_time') }">
                    <router-link
                      v-if="event.control_name"
                      :to="{ name: 'edit-control', params: { controlId: event.control_id } }"
                      :class="'text-' + controlTypeColor(event.control_type)">
                      {{ event.control_name }}
                    </router-link>
                    <span v-else class="text-grey-6">Deleted control {{ event.control_id }}</span>
                  </td>
                  <td class="text-weight-bold text-blue-grey-7" :class="{ 'new-day-separator': newDay(filteredEvents, index, 'event_time') }">
                    {{ toDateString(event.date_from) }}
                  </td>
                  <td class="text-weight-bold text-blue-grey-7" :class="{ 'new-day-separator': newDay(filteredEvents, index, 'event_time') }">
                    {{ toDateString(event.date_to) }}
                  </td>
                  <td class="text-no-wrap" :class="{ 'new-day-separator': newDay(filteredEvents, index, 'event_time') }">
                    <q-icon :name="triggerType(event.trigger_type).icon" color="blue-grey-5" class="q-mr-xs" /> {{ triggerType(event.trigger_type).label }}
                  </td>
                  <td :class="{ 'new-day-separator': newDay(filteredEvents, index, 'event_time') }">
                    <q-chip dense clickable @click="filter.event_type = event.event_type">
                      <q-avatar :icon="schedulerEventType(event.event_type).icon" :color="schedulerEventType(event.event_type).color" text-color="white" />
                      {{ schedulerEventType(event.event_type).label }}
                    </q-chip>
                  </td>
                  <td :class="{ 'new-day-separator': newDay(filteredEvents, index, 'event_time') }">
                    <q-chip v-if="event.process_id" dense>
                      <q-avatar :icon="runStatus(event.status).icon" :color="runStatus(event.status).color" text-color="white" />
                      {{ runStatus(event.status).label }}
                    </q-chip>
                  </td>
                  <td class="text-grey-8 message" :class="{ 'new-day-separator': newDay(filteredEvents, index, 'event_time') }">{{ event.message }}</td>
                  <td :class="{ 'new-day-separator': newDay(filteredEvents, index, 'event_time') }">
                    <q-btn v-if="event.event_type === 'MISSED' && event.control_name" size="sm" color="teal" round flat icon="fas fa-play" @click="runMissed(event)">
                      <q-tooltip>Run for this moment</q-tooltip>
                    </q-btn>
                  </td>
                </tr>
              </template>
              <template #after>
                <tbody v-if="!loaded">
                  <skeleton-rows v-if="!loaded" :rows="6" :columns="['QChip', 'text', 'text', 'text', 'text', 'text', 'text', 'text', 'QChip', 'QChip', 'text', null]" />
                </tbody>
                <tbody v-else-if="!filteredEvents.length">
                  <tr>
                    <td colspan="12" class="text-grey-7 text-center">No events</td>
                  </tr>
                </tbody>
              </template>
            </q-virtual-scroll>
          </div>
        </q-tab-panel>
      </q-tab-panels>
    </q-card>
  </q-page>
</template>

<script>
import { Dialog, Notify } from "quasar";
import { mapActions, mapState } from "vuex";
import DateTimeText from "./DateTimeText.vue";
import SchedulerToggleButton from "./SchedulerToggleButton.vue";
import SkeletonRows from "./SkeletonRows.vue";
import { api, notifyError } from "../api";
import { SCHEDULER_EVENT_TYPE_OPTIONS, TRIGGER_TYPES, TRIGGER_TYPE_OPTIONS, controlType, controlTypeColor, runStatus, schedulerEventType, schedulerState } from "../constants";
import { cancelRun } from "../runActions";
import { liveRefetch } from "../socket";
import { toDateString, toDateTimeString, toTimeString } from "../utils/format";
import { fillViewport, textWidth } from "../utils/layout";

// Naive server datetime string as milliseconds, read as local time like the server wrote it.
function toMillis(value) {
  return new Date(String(value).substring(0, 19)).getTime();
}

export default {
  components: {
    DateTimeText,
    SchedulerToggleButton,
    SkeletonRows,
  },
  data() {
    return {
      loaded: false,
      tab: "upcoming",
      upcoming: [],
      upcomingHours: 24,
      upcomingFilter: null,
      events: [],
      eventTypeOptions: SCHEDULER_EVENT_TYPE_OPTIONS,
      triggerTypeOptions: TRIGGER_TYPE_OPTIONS,
      horizonOptions: [
        { label: "6 hours", value: 6 },
        { label: "24 hours", value: 24 },
        { label: "3 days", value: 72 },
        { label: "7 days", value: 168 },
        { label: "31 days", value: 744 },
      ],
      filter: {
        control_name: null,
        event_type: null,
        trigger_type: null,
      },
      // Server clock minus browser clock, so "in 5 min" is right when their time zones differ.
      clockOffset: 0,
      now: Date.now(),
    };
  },
  computed: {
    // The History Control column fits the longest control name (bold 13px, plus padding), within limits.
    eventNameWidth() {
      const width = textWidth(
        this.events.map((event) => event.control_name || `Deleted control ${event.control_id}`),
        "bold 13px Roboto, sans-serif"
      );
      return Math.min(Math.max(width + 24, 140), 320);
    },
    ...mapState({ status: "schedulerStatus" }),
    state() {
      return schedulerState(this.status && this.status.state);
    },
    runner() {
      return (this.status && this.status.runner) || { running: [], queued: [], capacity: 0 };
    },
    activeJobs() {
      return [...this.runner.running.map((job) => ({ ...job, state: "running" })), ...this.runner.queued.map((job) => ({ ...job, state: "queued" }))];
    },
    filteredUpcoming() {
      const name = this.upcomingFilter ? this.upcomingFilter.toUpperCase() : null;
      return this.upcoming.filter((fire) => !name || fire.control_name.toUpperCase().includes(name));
    },
    filteredEvents() {
      const name = this.filter.control_name ? this.filter.control_name.toUpperCase() : null;
      return this.events.filter(
        (event) =>
          (!name || (event.control_name || "").toUpperCase().includes(name)) &&
          (!this.filter.event_type || event.event_type === this.filter.event_type) &&
          (!this.filter.trigger_type || event.trigger_type === this.filter.trigger_type)
      );
    },
  },
  methods: {
    ...mapActions(["updateSchedulerStatus"]),
    controlType,
    controlTypeColor,
    runStatus,
    schedulerEventType,
    toDateString,
    toTimeString,
    cancelRun,
    triggerType(type) {
      return TRIGGER_TYPES[type] || { label: type, icon: "fas fa-question" };
    },
    fillViewport,
    newDay(rows, index, key) {
      return index > 0 && toDateString(rows[index - 1][key]) !== toDateString(rows[index][key]);
    },
    fromNow(value) {
      const seconds = Math.round((toMillis(value) - this.now - this.clockOffset) / 1000);
      if (seconds < 60) {
        return seconds <= 0 ? "now" : `${seconds} s`;
      }
      const minutes = Math.floor(seconds / 60);
      const days = Math.floor(minutes / 1440);
      const hours = Math.floor((minutes % 1440) / 60);
      return [days && `${days} d`, hours && `${hours} h`, !days && `${minutes % 60} min`].filter(Boolean).join(" ");
    },
    clearFilters() {
      this.filter.control_name = null;
      this.filter.event_type = null;
      this.filter.trigger_type = null;
    },
    async refreshStatus() {
      const status = await this.updateSchedulerStatus();
      this.clockOffset = toMillis(status.server_time) - Date.now();
    },
    async refreshUpcoming() {
      this.upcoming = await api("scheduler-upcoming", { params: { hours: this.upcomingHours } });
    },
    async refreshEvents() {
      this.events = await api("scheduler-events", { params: { limit: 500 } });
    },
    async refreshAll() {
      try {
        await Promise.all([this.refreshStatus(), this.refreshUpcoming(), this.refreshEvents()]);
        this.loaded = true;
      } catch (error) {
        notifyError("Failed to load scheduler.", error);
      }
    },
    runMissed(event) {
      Dialog.create({
        title: event.control_name,
        message: `Run for the missed fire of ${toDateTimeString(event.scheduled_time)}? The run gets the date range of that moment.`,
        cancel: true,
        persistent: true,
      }).onOk(async () => {
        try {
          await api("run-missed", { method: "POST", params: { event_id: event.event_id } });
          Notify.create({ type: "positive", message: `Control ${event.control_name} queued for execution` });
          this.refreshAll();
        } catch (error) {
          notifyError(`Control ${event.control_name} failed to start.`, error);
        }
      });
    },
  },
  mounted() {
    const onError = (error) => notifyError("Failed to load scheduler.", error);
    this.stopLiveUpdates = [
      liveRefetch("scheduler:changed", () => Promise.all([this.refreshStatus(), this.refreshEvents()]).catch(onError), { interval: 2000 }),
      liveRefetch("runs:changed", () => Promise.all([this.refreshStatus(), this.refreshEvents()]).catch(onError)),
      liveRefetch("controls:changed", () => this.refreshUpcoming().catch(onError)),
    ];
    // Keeps "In" current and drops fires that passed from the upcoming list.
    this.clock = setInterval(() => {
      this.now = Date.now();
      if (this.upcoming.length && toMillis(this.upcoming[0].scheduled_time) < this.now + this.clockOffset) {
        this.refreshUpcoming().catch(onError);
      }
    }, 5000);
    this.refreshAll();
  },
  unmounted() {
    this.stopLiveUpdates.forEach((stop) => stop());
    clearInterval(this.clock);
  },
};
</script>

<style lang="css" scoped>
a {
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}

.new-day-separator {
  border-top: 2px solid #cfd8dc !important;
}

.status-item {
  min-width: 140px;
}

.status-label {
  font-size: 11px;
  text-transform: uppercase;
  color: #78909c;
}

.status-value {
  font-weight: 600;
  color: #455a64;
}

.message {
  white-space: normal;
}

/* The tabs card and its panel shrink to their table, which is as tall as its rows up to the rest of the page
   (list-table in App.vue), so a long list scrolls inside the table instead of the page. */
.tabs-card,
.fill-panels,
.fill-panels :deep(.q-panel),
.fill-panels :deep(.q-tab-panel),
.fill-column {
  display: flex;
  flex-direction: column;
  flex: 0 1 auto;
  min-height: 0;
}
.fill-panels :deep(.q-panel) {
  overflow: hidden;
}
.upcoming-table,
.history-table {
  min-height: 160px;
}

/* Fixed columns, so rows swapped in while scrolling don't resize them. */
.upcoming-table :deep(table),
.history-table :deep(table) {
  table-layout: fixed;
}
.upcoming-table th:nth-child(1) { width: 84px; }
.upcoming-table th:nth-child(2) { width: 170px; }
.upcoming-table th:nth-child(3) { width: 130px; }
.upcoming-table th:nth-child(5),
.upcoming-table th:nth-child(6) { width: 95px; }
.history-table :deep(table) {
  min-width: calc(1224px + var(--name-column-width));
}
.history-table th:nth-child(1) { width: 84px; }
.history-table th:nth-child(2) { width: 145px; }
.history-table th:nth-child(3) { width: 140px; }
.history-table th:nth-child(4) { width: 95px; }
.history-table th:nth-child(5) { width: var(--name-column-width); }
.history-table th:nth-child(6),
.history-table th:nth-child(7) { width: 95px; }
.history-table th:nth-child(8) { width: 100px; }
.history-table th:nth-child(9) { width: 110px; }
.history-table th:nth-child(10) { width: 105px; }
.history-table th:nth-child(12) { width: 50px; }
.history-table td:nth-child(5) { white-space: normal; overflow-wrap: anywhere; }
</style>
