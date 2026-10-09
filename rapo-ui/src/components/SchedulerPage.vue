<template>
  <q-page class="column no-wrap" :style-fn="fillViewportToBottom">
    <h2 class="row items-center no-wrap text-no-wrap q-gutter-lg q-mb-md">
      <div>Scheduler</div>
      <div class="col justify-end">
        <scheduler-status-bar
          :status="status"
          :clock-offset="clockOffset"
          :now="now"
          :next-fire="upcoming[0] || null"
          :fire-count="upcoming.length"
          :counts="eventCounts"
          @open="openSegment" />
      </div>
    </h2>

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
        <q-tab name="running" :icon="runner.running.length ? 'fas fa-sync fa-spin' : 'fas fa-sync'" label="Running">
          <q-badge v-if="activeJobs.length" color="teal" text-color="white" class="q-ml-sm" :title="`${runner.running.length} running, ${runner.queued.length} queued`">
            {{ runner.running.length }}<template v-if="runner.queued.length"> + {{ runner.queued.length }}</template>
          </q-badge>
        </q-tab>
        <q-tab name="upcoming" icon="fas fa-calendar-alt" label="Upcoming">
          <q-badge v-if="upcomingFilters.length" color="orange-10" rounded floating title="Filtered" />
        </q-tab>
        <q-tab name="history" icon="fas fa-history" label="History">
          <q-badge v-if="historyFilters.length" color="orange-10" rounded floating title="Filtered" />
        </q-tab>
      </q-tabs>

      <q-separator />

      <q-tab-panels v-model="tab" keep-alive class="fill-panels">
        <q-tab-panel name="running" class="q-pb-none">
          <div class="q-mx-lg q-mt-md q-gutter-y-sm fill-column">
            <div class="text-grey-7 text-caption q-px-sm">
              The runs of this server<span v-if="status && status.runner"> ({{ status.runner.runner }})</span>, running first, then those waiting for a free
              slot (or for a run of their own control, as its instance limit allows); other servers run their own.
            </div>
            <!-- The columns of History, so the two tables read alike: Queued and Started stand for Recorded and Scheduled for,
                 the state for the event. -->
            <q-virtual-scroll
              type="table"
              dense
              flat
              class="list-table running-table"
              :items="activeJobs"
              :virtual-scroll-item-size="41"
              :virtual-scroll-sticky-size-start="28"
              :table-colspan="11">
              <template #before>
                <thead>
                  <tr class="bg-blue-grey-2">
                    <th title="The control type: ANL analysis, REC reconciliation, CMP comparison, REP report" class="text-left">Type</th>
                    <th title="When the run was queued" class="text-left">Queued</th>
                    <th title="When the run's worker process started" class="text-left">Started</th>
                    <th title="The process ID of the run (rapo_log)" class="text-center">PID</th>
                    <th title="The control running now; &quot;for&quot; names the control whose job it runs in (chain upstream or cascade)" class="text-left">Control</th>
                    <th title="The start of the run's data window" class="text-left">Run from</th>
                    <th title="The end of the run's data window" class="text-left">Run to</th>
                    <th title="What started the run: schedule, manual, catch-up, iteration, cascade or chain" class="text-left">Trigger</th>
                    <th title="Running, queued for a free slot (control_parallelism), or held in the queue while its control already runs as many jobs as its instance limit on this server" class="text-left">State</th>
                    <th title="The operating system's process ID of the worker running it" class="text-center">OS PID</th>
                    <th></th>
                  </tr>
                </thead>
              </template>
              <template #default="{ item: job }">
                <tr :key="job.event_id">
                  <td>
                    <q-chip v-if="job.control_type" size="11px" :title="controlType(job.control_type).label">
                      <q-avatar :icon="controlType(job.control_type).icon" :color="controlType(job.control_type).color" text-color="white" />
                      {{ job.control_type }}
                    </q-chip>
                  </td>
                  <td><date-time-text :value="job.queued" /></td>
                  <td><date-time-text :value="job.started" /></td>
                  <td class="text-center text-weight-bold text-blue-grey-7 number-cell">{{ job.process_id }}</td>
                  <!-- The run the job performs now: a chain source or a cascade child runs in the job of another control. -->
                  <td class="control-cell">
                    <span class="text-weight-bold" :class="'text-' + controlTypeColor(job.control_type)">{{ job.control_name }}</span>
                    <span v-if="job.job_control_name && job.job_control_name !== job.control_name" class="text-grey-7 q-ml-sm">
                      for
                      <router-link v-if="controlIds.has(job.job_control_name)" :to="editLink(job.job_control_name)" class="control-ref">{{ job.job_control_name }}</router-link>
                      <template v-else>{{ job.job_control_name }}</template>
                      <q-tooltip>Runs in the job of {{ job.job_control_name }}, as its chain source or cascade</q-tooltip>
                    </span>
                  </td>
                  <td class="text-weight-bold text-blue-grey-7">{{ toDateString(job.date_from) }}</td>
                  <td class="text-weight-bold text-blue-grey-7">{{ toDateString(job.date_to) }}</td>
                  <td class="text-no-wrap"><q-icon :name="triggerType(job.trigger_type).icon" color="blue-grey-5" class="q-mr-xs" /> {{ triggerType(job.trigger_type).label }}</td>
                  <td>
                    <q-chip dense>
                      <q-avatar
                        :icon="job.state === 'running' ? 'fas fa-sync fa-spin' : 'fas fa-hourglass-half'"
                        :color="job.state === 'running' ? 'blue' : 'indigo'"
                        text-color="white" />
                      {{ job.state === "running" ? "Running" : "Queued" }}
                    </q-chip>
                    <span v-if="job.held === 'instance_limit'" class="text-grey-7 text-no-wrap" title="Its control already runs as many jobs as its instance limit on this server; the run takes a slot when one of them ends">· instance limit</span>
                  </td>
                  <td class="text-center text-blue-grey-7 number-cell">{{ job.pid }}</td>
                  <td>
                    <q-btn aria-label="Cancel run" size="sm" color="grey-7" round flat icon="fas fa-times" @click="cancelRun(job, refreshAll)">
                      <q-tooltip>Cancel run</q-tooltip>
                    </q-btn>
                  </td>
                </tr>
              </template>
              <template #after>
                <tbody v-if="!status">
                  <skeleton-rows :rows="4" :columns="['QChip', 'text', 'text', 'text', 'text', 'text', 'text', 'text', 'QChip', 'text', null]" />
                </tbody>
                <tbody v-else-if="!activeJobs.length">
                  <tr>
                    <td colspan="11" class="text-grey-7 text-center">Nothing running or queued on this server</td>
                  </tr>
                </tbody>
              </template>
            </q-virtual-scroll>
          </div>
        </q-tab-panel>

        <q-tab-panel name="upcoming" class="q-pb-none">
          <div class="q-mx-lg q-mt-md q-gutter-y-sm fill-column">
            <!-- The next 24 whole hours: counts of all their fires (each filters), the warning of a stopped scheduler. -->
            <div class="row items-center no-wrap q-px-sm">
              <div v-if="status && status.disabled" class="text-grey-7">
                <q-icon name="fas fa-exclamation-triangle" color="deep-orange" /> The scheduler is stopped, these fires will not run until it is started.
              </div>
              <q-space />
              <div class="row items-center justify-end">
                <q-chip v-for="chip in upcomingChips" :key="chip.key" clickable @click="chip.apply()">
                  <q-avatar :icon="chip.icon" :color="chip.color" text-color="white" />
                  <span class="text-weight-bold q-mr-xs">{{ chip.label }}</span>({{ chip.count }})
                  <q-tooltip v-if="chip.title" anchor="top middle" self="bottom middle" :offset="[0, 8]">{{ chip.title }}</q-tooltip>
                </q-chip>
              </div>
            </div>
            <filter-chips :filters="upcomingFilters" :shown="`${filteredUpcoming.length} of ${upcoming.length} fires`" class="q-px-sm" @clear="clearUpcomingFilters" />
            <hour-heatmap
              v-if="loaded"
              :rows="upcomingHeatmap"
              :slots="upcomingSlots"
              :hue="150"
              :now="nowPosition(upcomingStart)"
              :now-label="nowLabel"
              unit="fire(s)"
              :selected="slotIndex(upcomingFilter.hour, upcomingStart)"
              class="q-px-sm"
              @select="(index) => (upcomingFilter.hour = slotTime(index, upcomingStart))" />
            <q-virtual-scroll
              type="table"
              dense
              flat
              class="list-table upcoming-table"
              :items="filteredUpcoming"
              :virtual-scroll-item-size="41"
              :virtual-scroll-sticky-size-start="28"
              :table-colspan="8">
              <template #before>
                <thead>
                  <tr class="bg-blue-grey-2">
                    <th title="The control type: ANL analysis, REC reconciliation, CMP comparison, REP report" class="text-left">Type</th>
                    <th title="The scheduled time of the fire" class="text-left">Scheduled for</th>
                    <th title="How long until the fire" class="text-right">Next fire</th>
                    <th title="The control the scheduler will run" class="text-left">Control</th>
                    <th
                      title="Why it runs: its own schedule, a cascade of the control it names, or a chain source pulled by it (both start after that control's fire); click to filter by it"
                      class="text-left">
                      Trigger
                    </th>
                    <th title="The start of the data window the run will read" class="text-left">Run from</th>
                    <th title="The end of the data window the run will read" class="text-left">Run to</th>
                    <th title="The control's group" class="text-left">Group</th>
                  </tr>
                </thead>
              </template>
              <template #default="{ item: fire, index }">
                <tr :key="fire.control_id + fire.scheduled_time + fire.trigger_type + (fire.via || '')">
                  <td :class="{ 'new-day-separator': newDay(filteredUpcoming, index, 'scheduled_time') }">
                    <q-chip size="11px" :title="controlType(fire.control_type).label">
                      <q-avatar :icon="controlType(fire.control_type).icon" :color="controlType(fire.control_type).color" text-color="white" />
                      {{ fire.control_type }}
                    </q-chip>
                  </td>
                  <td :class="{ 'new-day-separator': newDay(filteredUpcoming, index, 'scheduled_time') }">
                    <date-time-text :value="fire.scheduled_time" />
                  </td>
                  <td class="text-right text-grey-8 number-cell" :class="{ 'new-day-separator': newDay(filteredUpcoming, index, 'scheduled_time') }">
                    {{ fromNow(fire.scheduled_time) }}
                  </td>
                  <td class="text-weight-bold" :class="{ 'new-day-separator': newDay(filteredUpcoming, index, 'scheduled_time') }">
                    <router-link :to="{ name: 'edit-control', params: { controlId: fire.control_id }, query: { tab: 'scheduler' } }" :class="'text-' + controlTypeColor(fire.control_type)">
                      {{ fire.control_name }}
                    </router-link>
                  </td>
                  <td class="text-no-wrap ellipsis" :class="{ 'new-day-separator': newDay(filteredUpcoming, index, 'scheduled_time') }">
                    <span class="cursor-pointer" @click="toggleTrigger(upcomingFilter, fire.trigger_type)">
                      <q-icon :name="triggerType(fire.trigger_type).icon" color="blue-grey-5" class="q-mr-xs" /> {{ triggerType(fire.trigger_type).label }}
                    </span>
                    <span v-if="fire.via" class="text-grey-6 q-ml-xs" :title="viaTitle(fire)"
                      >via
                      <router-link v-if="controlIds.has(fire.via)" :to="editLink(fire.via)" class="control-ref">{{ fire.via }}</router-link>
                      <template v-else>{{ fire.via }}</template>
                    </span>
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
                  <skeleton-rows :rows="6" :columns="['QChip', 'text', 'text', 'text', 'text', 'text', 'text', 'text']" />
                </tbody>
                <tbody v-else-if="!filteredUpcoming.length">
                  <tr>
                    <td colspan="8" class="text-grey-7 text-center">{{ upcoming.length ? "No fires match the filters" : "No fires in the next 24 hours" }}</td>
                  </tr>
                </tbody>
              </template>
            </q-virtual-scroll>
          </div>
        </q-tab-panel>

        <q-tab-panel name="history" class="q-pb-none">
          <div class="q-mx-lg q-mt-md q-gutter-y-sm fill-column">
            <!-- The last 24 whole hours: counts of all their events (each filters), older missed fires never caught up. -->
            <div class="row items-center no-wrap q-px-sm">
              <q-chip v-if="olderMissed.length" clickable outline color="amber-9" class="q-ml-none" @click="missedDialog = true">
                <q-avatar icon="fas fa-exclamation-triangle" color="amber-9" text-color="white" />
                <span class="text-weight-bold q-mr-xs">Older missed</span>({{ olderMissed.length }}{{ olderMissed.length >= 500 ? "+" : "" }})
                <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">Fires missed before the last 24 hours and never run for their moment: click to see and run them</q-tooltip>
              </q-chip>
              <small v-if="events.length >= eventLimit" class="text-deep-orange q-ml-md">Only the latest {{ eventLimit }} events of the last 24 hours</small>
              <q-space />
              <div class="row items-center justify-end">
                <q-chip v-for="chip in historyChips" :key="chip.key" clickable @click="chip.apply()">
                  <q-avatar :icon="chip.icon" :color="chip.color" text-color="white" />
                  <span class="text-weight-bold q-mr-xs">{{ chip.label }}</span>({{ chip.count }})
                  <q-tooltip v-if="chip.title" anchor="top middle" self="bottom middle" :offset="[0, 8]">{{ chip.title }}</q-tooltip>
                </q-chip>
              </div>
            </div>
            <filter-chips :filters="historyFilters" :shown="`${filteredEvents.length} of ${events.length} events`" class="q-px-sm" @clear="clearFilters" />
            <hour-heatmap
              v-if="loaded"
              :rows="historyHeatmap"
              :slots="historySlots"
              :now="nowPosition(historyStart)"
              :now-label="nowLabel"
              unit="event(s)"
              corner="warnings"
              :selected="slotIndex(filter.hour, historyStart)"
              class="q-px-sm"
              @select="(index) => (filter.hour = slotTime(index, historyStart))" />
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

                    <th title="The control type: ANL analysis, REC reconciliation, CMP comparison, REP report" class="text-left">Type</th>
                    <th title="When the scheduler recorded the event" class="text-left">Recorded</th>
                    <th title="The scheduled time the event is for (none for manual runs)" class="text-left">Scheduled for</th>
                    <th title="The process ID of the run, once it started" class="text-center">PID</th>
                    <th title="The control; click it to open its schedule" class="text-left">Control</th>
                    <th title="The start of the run's data window" class="text-left">Run from</th>
                    <th title="The end of the run's data window" class="text-left">Run to</th>
                    <th title="What started the run: schedule, manual, catch-up, iteration, cascade or chain; click to filter by it" class="text-left">Trigger</th>
                    <th title="What happened: queued, started, missed, failed or canceled; click to filter by it" class="text-left">Event</th>
                    <th title="The status of the run the event started; click to filter by it" class="text-left">Run</th>
                    <th title="Details, such as why a fire was missed or failed" class="text-left">Message</th>
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
                  <td class="text-center text-weight-bold text-blue-grey-7 number-cell" :class="{ 'new-day-separator': newDay(filteredEvents, index, 'event_time') }">
                    {{ event.process_id }}
                  </td>
                  <td class="text-weight-bold" :class="{ 'new-day-separator': newDay(filteredEvents, index, 'event_time') }">
                    <router-link
                      v-if="event.control_name"
                      :to="{ name: 'edit-control', params: { controlId: event.control_id }, query: { tab: 'scheduler' } }"
                      :class="'text-' + controlTypeColor(event.control_type)">
                      {{ event.control_name }}
                    </router-link>
                    <span v-else class="text-grey-7">Deleted control {{ event.control_id }}</span>
                  </td>
                  <td class="text-weight-bold text-blue-grey-7" :class="{ 'new-day-separator': newDay(filteredEvents, index, 'event_time') }">
                    {{ toDateString(event.date_from) }}
                  </td>
                  <td class="text-weight-bold text-blue-grey-7" :class="{ 'new-day-separator': newDay(filteredEvents, index, 'event_time') }">
                    {{ toDateString(event.date_to) }}
                  </td>
                  <td class="text-no-wrap" :class="{ 'new-day-separator': newDay(filteredEvents, index, 'event_time') }">
                    <span class="cursor-pointer" @click="toggleTrigger(filter, event.trigger_type)">
                      <q-icon :name="triggerType(event.trigger_type).icon" color="blue-grey-5" class="q-mr-xs" /> {{ triggerType(event.trigger_type).label }}
                    </span>
                  </td>
                  <td :class="{ 'new-day-separator': newDay(filteredEvents, index, 'event_time') }">
                    <q-chip dense clickable @click="filter.event_type = event.event_type">
                      <q-avatar :icon="schedulerEventType(event.event_type).icon" :color="schedulerEventType(event.event_type).color" text-color="white" />
                      {{ schedulerEventType(event.event_type).label }}
                    </q-chip>
                  </td>
                  <td :class="{ 'new-day-separator': newDay(filteredEvents, index, 'event_time') }">
                    <q-chip v-if="event.process_id" dense clickable @click="filter.status = event.status">
                      <q-avatar :icon="runStatus(event.status).icon" :color="runStatus(event.status).color" text-color="white" />
                      {{ runStatus(event.status).label }}
                    </q-chip>
                  </td>
                  <td class="text-grey-8 message" :class="{ 'new-day-separator': newDay(filteredEvents, index, 'event_time') }">{{ event.message }}</td>
                  <td :class="{ 'new-day-separator': newDay(filteredEvents, index, 'event_time') }">
                    <q-btn aria-label="Run for this moment" v-if="event.event_type === 'MISSED' && event.control_name" size="sm" color="teal" round flat icon="fas fa-play" @click="runMissed(event)">
                      <q-tooltip>Run for this moment</q-tooltip>
                    </q-btn>
                  </td>
                </tr>
              </template>
              <template #after>
                <tbody v-if="!loaded">
                  <skeleton-rows :rows="6" :columns="['QChip', 'text', 'text', 'text', 'text', 'text', 'text', 'text', 'QChip', 'QChip', 'text', null]" />
                </tbody>
                <tbody v-else-if="!filteredEvents.length">
                  <tr>
                    <td colspan="12" class="text-grey-7 text-center">{{ events.length ? "No events match the filters" : "No events in the last 24 hours" }}</td>
                  </tr>
                </tbody>
              </template>
            </q-virtual-scroll>
          </div>
        </q-tab-panel>
      </q-tab-panels>
    </q-card>

    <!-- Missed fires older than the History window that were never run for their moment. -->
    <q-dialog v-model="missedDialog">
      <q-card style="width: 900px; max-width: 95vw">
        <q-card-section class="row items-center">
          <div class="text-h6">Older missed fires</div>
          <q-space />
          <q-btn aria-label="Close" icon="fas fa-times" flat round dense v-close-popup />
        </q-card-section>
        <q-card-section class="q-pt-none">
          <q-markup-table dense flat class="missed-table">
            <thead>
              <tr class="bg-blue-grey-1">
                <th title="The control type: ANL analysis, REC reconciliation, CMP comparison, REP report" class="text-left">Type</th>
                <th title="The control whose fire was missed" class="text-left">Control</th>
                <th title="The scheduled time of the missed fire" class="text-left">Scheduled for</th>
                <th title="When the scheduler recorded it as missed" class="text-left">Recorded</th>
                <th title="Why the fire was missed" class="text-left">Message</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="event in olderMissed" :key="event.event_id">
                <td>
                  <q-chip v-if="event.control_type" size="11px" :title="controlType(event.control_type).label">
                    <q-avatar :icon="controlType(event.control_type).icon" :color="controlType(event.control_type).color" text-color="white" />
                    {{ event.control_type }}
                  </q-chip>
                </td>
                <td class="text-weight-bold">
                  <span v-if="event.control_name" :class="'text-' + controlTypeColor(event.control_type)">{{ event.control_name }}</span>
                  <span v-else class="text-grey-7">Deleted control {{ event.control_id }}</span>
                </td>
                <td><date-time-text :value="event.scheduled_time" /></td>
                <td><date-time-text :value="event.event_time" /></td>
                <td class="text-grey-8 message">{{ event.message }}</td>
                <td>
                  <q-btn aria-label="Run for this moment" v-if="event.control_name" size="sm" color="teal" round flat icon="fas fa-play" @click="runMissed(event)">
                    <q-tooltip>Run for this moment</q-tooltip>
                  </q-btn>
                </td>
              </tr>
            </tbody>
          </q-markup-table>
        </q-card-section>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script>
import { mapActions, mapGetters, mapState } from "vuex";
import DateTimeText from "./DateTimeText.vue";
import FilterChips from "./FilterChips.vue";
import HourHeatmap from "./HourHeatmap.vue";
import SchedulerStatusBar from "./SchedulerStatusBar.vue";
import SkeletonRows from "./SkeletonRows.vue";
import { api, notifyError } from "../api";
import { TRIGGER_TYPES, controlType, controlTypeColor, runStatus, schedulerEventType } from "../constants";
import { cancelRun } from "../runActions";
import { liveRefetch } from "../socket";
import { toDateString, toDateTimeString, toMillis } from "../utils/format";
import { clockLabel, windowPosition } from "../utils/clock";
import { searchFilter, valueFilter } from "../utils/filters";
import { runMatchesSearch } from "../utils/runs";
import { ORDERS, countBy, historyHeatmapRows, rollingSlots, upcomingHeatmapRows, windowStart } from "../utils/scheduler";
import { fillViewportToBottom, textWidth } from "../utils/layout";
import persistFilters from "../mixins/persistFilters";

export default {
  mixins: [persistFilters("scheduler", ["filter", "upcomingFilter"])],
  components: {
    DateTimeText,
    FilterChips,
    HourHeatmap,
    SchedulerStatusBar,
    SkeletonRows,
  },
  data() {
    return {
      loaded: false,
      tab: "upcoming",
      upcoming: [],
      // The filters of each tab; `hour` is the start (ms) of the hour picked in its heatmap, so it stays the same hour
      // while the window rolls on (and is ignored once it left it).
      upcomingFilter: {
        type: null,
        trigger_type: null,
        hour: null,
      },
      events: [],
      eventLimit: 5000,
      olderMissed: [],
      missedDialog: false,
      filter: {
        type: null,
        trigger_type: null,
        event_type: null,
        status: null,
        hour: null,
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
    runner() {
      return (this.status && this.status.runner) || { running: [], queued: [], capacity: 0 };
    },
    // Events of the last 24 hours by type, for the status bar.
    eventCounts() {
      return this.events.reduce((counts, event) => ({ ...counts, [event.event_type]: (counts[event.event_type] || 0) + 1 }), {});
    },
    activeJobs() {
      return [...this.runner.running.map((job) => ({ ...job, state: "running" })), ...this.runner.queued.map((job) => ({ ...job, state: "queued" }))];
    },
    ...mapGetters(["getSearch"]),
    ...mapGetters({ controlIds: "controlIdsByName" }),
    // The first hour (ms) of each tab's window: Upcoming from the current hour of the server, History up to it.
    upcomingStart() {
      return windowStart(this.now + this.clockOffset);
    },
    historyStart() {
      return windowStart(this.now + this.clockOffset, -23);
    },
    // The server's time of the Now marker of both heatmaps.
    nowLabel() {
      return clockLabel(this.now + this.clockOffset);
    },
    upcomingSlots() {
      return rollingSlots(this.upcomingStart);
    },
    historySlots() {
      return rollingSlots(this.historyStart);
    },
    upcomingFilters() {
      const filter = this.upcomingFilter;
      return [
        ...valueFilter("type", "Type", filter.type, () => (filter.type = null)),
        ...valueFilter("trigger", "Trigger", filter.trigger_type, () => (filter.trigger_type = null), { label: this.triggerType(filter.trigger_type).label }),
        ...this.hourFilter(filter, this.upcomingStart),
        ...searchFilter(this.$store),
      ];
    },
    historyFilters() {
      const filter = this.filter;
      return [
        ...valueFilter("type", "Type", filter.type, () => (filter.type = null)),
        ...valueFilter("trigger", "Trigger", filter.trigger_type, () => (filter.trigger_type = null), { label: this.triggerType(filter.trigger_type).label }),
        ...valueFilter("event", "Event", filter.event_type, () => (filter.event_type = null), { label: schedulerEventType(filter.event_type).label }),
        ...valueFilter("status", "Run", filter.status, () => (filter.status = null), { label: runStatus(filter.status).label }),
        ...this.hourFilter(filter, this.historyStart),
        ...searchFilter(this.$store),
      ];
    },
    // The fires that pass every filter but the hour, which the heatmap picks.
    unhouredUpcoming() {
      const search = this.getSearch ? this.getSearch.trim().toUpperCase() : null;
      const filter = this.upcomingFilter;
      return this.upcoming.filter(
        (fire) =>
          (!search || fire.control_name.toUpperCase().includes(search)) &&
          (!filter.type || fire.control_type === filter.type) &&
          (!filter.trigger_type || fire.trigger_type === filter.trigger_type)
      );
    },
    filteredUpcoming() {
      const index = this.slotIndex(this.upcomingFilter.hour, this.upcomingStart);
      return index === null ? this.unhouredUpcoming : this.unhouredUpcoming.filter((fire) => this.slotOfTime(fire.scheduled_time, this.upcomingStart) === index);
    },
    upcomingHeatmap() {
      return upcomingHeatmapRows(this.unhouredUpcoming, this.upcomingStart);
    },
    upcomingChips() {
      const filter = this.upcomingFilter;
      return [
        ...countBy(this.upcoming, "control_type", ORDERS.type).map((item) => this.typeChip(item, () => (filter.type = item.key))),
        ...countBy(this.upcoming, "trigger_type", ORDERS.trigger).map((item) => this.triggerChip(item, () => this.toggleTrigger(filter, item.key))),
      ];
    },
    unhouredEvents() {
      const filter = this.filter;
      return this.events.filter(
        (event) =>
          runMatchesSearch(event, this.getSearch) &&
          (!filter.type || event.control_type === filter.type) &&
          (!filter.event_type || event.event_type === filter.event_type) &&
          (!filter.trigger_type || event.trigger_type === filter.trigger_type) &&
          (!filter.status || event.status === filter.status)
      );
    },
    filteredEvents() {
      const index = this.slotIndex(this.filter.hour, this.historyStart);
      return index === null ? this.unhouredEvents : this.unhouredEvents.filter((event) => this.slotOfTime(event.event_time, this.historyStart) === index);
    },
    historyHeatmap() {
      return historyHeatmapRows(this.unhouredEvents, this.historyStart);
    },
    historyChips() {
      const filter = this.filter;
      return [
        ...countBy(this.events, "control_type", ORDERS.type).map((item) => this.typeChip(item, () => (filter.type = item.key))),
        ...countBy(this.events, "trigger_type", ORDERS.trigger).map((item) => this.triggerChip(item, () => this.toggleTrigger(filter, item.key))),
        ...countBy(this.events, "event_type", ORDERS.event).map((item) => {
          const type = schedulerEventType(item.key);
          return { key: `event-${item.key}`, icon: type.icon, color: type.color, label: type.label, count: item.count, title: "Events of this kind", apply: () => (filter.event_type = item.key) };
        }),
        ...countBy(this.events, "status", ORDERS.status).map((item) => {
          const status = runStatus(item.key);
          return { key: `status-${item.key}`, icon: status.icon, color: status.color, label: status.label, count: item.count, title: "Events whose run has this status", apply: () => (filter.status = item.key) };
        }),
      ];
    },
  },
  methods: {
    ...mapActions(["updateSchedulerStatus", "updateControlCatalogue"]),
    // The editor of a control the page names (via, for), on its Scheduler tab.
    editLink(controlName) {
      return { name: "edit-control", params: { controlId: this.controlIds.get(controlName) }, query: { tab: "scheduler" } };
    },
    controlType,
    controlTypeColor,
    runStatus,
    schedulerEventType,
    toDateString,
    cancelRun,
    triggerType(type) {
      return TRIGGER_TYPES[type] || { label: type, icon: "fas fa-question" };
    },
    typeChip(item, apply) {
      const type = controlType(item.key);
      return { key: `type-${item.key}`, icon: type.icon, color: type.color, label: item.key, count: item.count, title: type.label, apply };
    },
    // Where the present falls in a window starting at `start`.
    nowPosition(start) {
      return windowPosition(this.now + this.clockOffset, start);
    },
    // A click on a trigger filters by it, a click on the trigger already filtered by clears it.
    toggleTrigger(filter, type) {
      filter.trigger_type = filter.trigger_type === type ? null : type;
    },
    triggerChip(item, apply) {
      const trigger = this.triggerType(item.key);
      return { key: `trigger-${item.key}`, icon: trigger.icon, color: "blue-grey-5", label: trigger.label, count: item.count, title: "Started by this trigger", apply };
    },
    viaTitle(fire) {
      return fire.trigger_type === "CASCADE"
        ? `Cascade of ${fire.via}: runs after its fire of this time`
        : `Pulled by ${fire.via}: runs first when ${fire.via} runs at this time`;
    },
    // The column of a picked hour (its start, ms) in a window, or null; and the start of a column.
    slotIndex(hour, start) {
      if (hour === null || hour === undefined) {
        return null;
      }
      const index = Math.round((hour - start) / 3600000);
      return index >= 0 && index < 24 ? index : null;
    },
    slotTime(index, start) {
      return index === null ? null : start + index * 3600000;
    },
    slotOfTime(value, start) {
      return Math.floor((toMillis(value) - start) / 3600000);
    },
    hourFilter(filter, start) {
      const index = this.slotIndex(filter.hour, start);
      const slots = start === this.upcomingStart ? this.upcomingSlots : this.historySlots;
      return index === null ? [] : valueFilter("hour", "Hour", filter.hour, () => (filter.hour = null), { label: slots[index].title });
    },
    fillViewportToBottom,
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
    // A link of the status bar: a tab, for History with an event filter.
    openSegment(tab, eventType) {
      this.tab = tab;
      if (eventType) {
        this.filter.event_type = eventType;
      }
    },
    // Every filter of the tab and the header search.
    clearFilters() {
      Object.keys(this.filter).forEach((key) => (this.filter[key] = null));
      this.$store.commit("updateSearch", "");
    },
    clearUpcomingFilters() {
      Object.keys(this.upcomingFilter).forEach((key) => (this.upcomingFilter[key] = null));
      this.$store.commit("updateSearch", "");
    },
    async refreshStatus() {
      const status = await this.updateSchedulerStatus();
      this.clockOffset = toMillis(status.server_time) - Date.now();
    },
    // With the catalogue, which the links of the controls a fire runs via are looked up in.
    async refreshUpcoming() {
      const [upcoming] = await Promise.all([api("scheduler-upcoming", { params: { hours: 24 } }), this.updateControlCatalogue().catch(() => null)]);
      this.upcoming = upcoming;
    },
    async refreshEvents() {
      const [events, missed] = await Promise.all([
        api("scheduler-events", { params: { hours: 24, limit: this.eventLimit } }),
        api("get-missed-fires", { params: { hours: 24 } }),
      ]);
      this.events = events;
      this.olderMissed = missed;
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
      this.$q.dialog({
        title: event.control_name,
        message: `Run for the missed fire of ${toDateTimeString(event.scheduled_time)}? The run gets the date range of that moment.`,
        cancel: true,
        persistent: true,
      }).onOk(async () => {
        try {
          await api("run-missed", { method: "POST", params: { event_id: event.event_id } });
          this.missedDialog = false;
          this.$q.notify({ type: "positive", message: `Control ${event.control_name} queued for execution` });
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
    // A new hour moves both windows: refetched, so Upcoming gains its last hour and History drops its first.
    this.clock = setInterval(() => {
      const start = this.upcomingStart;
      this.now = Date.now();
      if (this.upcomingStart !== start) {
        this.refreshAll();
      } else if (this.upcoming.length && toMillis(this.upcoming[0].scheduled_time) < this.now + this.clockOffset) {
        this.refreshUpcoming().catch(onError);
      }
    }, 1000);
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

/* A control named beside another (via, for): in the grey of its text. */
.control-ref {
  color: inherit;
  font-weight: 500;
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
.history-table,
.running-table {
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
.upcoming-table th:nth-child(5) { width: 260px; }
.upcoming-table th:nth-child(6),
.upcoming-table th:nth-child(7) { width: 95px; }
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

/* The Running table in History's widths, column for column. */
.running-table :deep(table) {
  table-layout: fixed;
  min-width: 1200px;
}
.running-table th:nth-child(1) { width: 84px; }
.running-table th:nth-child(2) { width: 145px; }
.running-table th:nth-child(3) { width: 140px; }
.running-table th:nth-child(4) { width: 95px; }
.running-table th:nth-child(6),
.running-table th:nth-child(7) { width: 95px; }
.running-table th:nth-child(8) { width: 100px; }
.running-table th:nth-child(9) { width: 110px; }
.running-table th:nth-child(10) { width: 80px; }
.running-table th:nth-child(11) { width: 50px; }
.running-table td.control-cell { white-space: normal; overflow-wrap: anywhere; }
</style>
