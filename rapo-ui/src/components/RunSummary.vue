<template>
  <!-- Totals of the runs: chips above (each filters by itself where clickable), the counts below. -->
  <div class="column items-end text-blue-grey-8">
    <div v-if="(showTypes && summary.types.length) || summary.statuses.length || summary.warnings" class="row items-center justify-end">
      <template v-if="showTypes">
        <q-chip v-for="item in summary.types" :key="item.key" :clickable="clickable" @click="clickable && $emit('filter-type', item.key)">
          <q-avatar :icon="controlType(item.key).icon" :color="controlType(item.key).color" text-color="white" />
          <span class="text-weight-bold q-mr-xs">{{ item.key }}</span>({{ item.count }})
          <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">{{ controlType(item.key).label }}</q-tooltip>
        </q-chip>
      </template>
      <q-chip v-for="item in summary.statuses" :key="String(item.key)" :clickable="clickable" @click="clickable && $emit('filter-status', item.key)">
        <q-avatar :icon="runStatus(item.key).icon" :color="runStatus(item.key).color" text-color="white" />
        <span class="text-weight-bold q-mr-xs">{{ runStatus(item.key).label }}</span>({{ item.count }})
      </q-chip>
      <q-chip v-if="summary.warnings" :clickable="clickable" @click="clickable && $emit('filter-warnings')">
        <q-avatar icon="fas fa-exclamation-triangle" color="amber-9" text-color="white" />
        <span class="text-weight-bold q-mr-xs">Warnings</span>({{ summary.warnings }})
        <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">Runs flagged with a warning about their results</q-tooltip>
      </q-chip>
    </div>
    <div class="q-mr-xs">
      <template v-if="showControls">{{ summary.controls }} {{ summary.controls === 1 ? "control" : "controls" }} &middot; </template>
      {{ summary.runs }}
      {{ summary.runs === 1 ? "run" : "runs" }}
      <span v-if="summary.triggers.length">
        &middot;
        <span v-for="item in summary.triggers" :key="String(item.key)" class="q-ml-xs q-mr-xs text-no-wrap">
          <q-icon :name="triggerOf({ trigger_type: item.key }).icon" size="11px" :class="item.key ? 'text-blue-grey-5' : 'text-grey-5'" />
          {{ item.count }}
          <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">
            {{ triggerOf({ trigger_type: item.key }).label }}: {{ item.count }} {{ item.count === 1 ? "run" : "runs" }}
          </q-tooltip>
        </span>
      </span>
      <span v-if="showControls && summary.failing.length" class="text-red-6">
        &middot; {{ summary.failing.length }} failing
        <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">
          Controls whose latest run ended in error: {{ summary.failing.slice(0, 10).join(", ") }}{{ summary.failing.length > 10 ? `, +${summary.failing.length - 10} more` : "" }}
        </q-tooltip>
      </span>
      <span>
        &middot; {{ compactNumber(summary.fetched) }} fetched
        <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">Records fetched by all runs: {{ formatNumber(summary.fetched) }}</q-tooltip>
      </span>
      <span>
        &middot; {{ formatDuration(summary.runtime) }} runtime
        <q-tooltip v-if="summary.longest" anchor="top middle" self="bottom middle" :offset="[0, 8]">
          The runtimes of the runs summed; the longest: {{ summary.longest.control_name }} ({{ formatDuration(summary.longest.duration_minutes * 60) }})
        </q-tooltip>
      </span>
    </div>
  </div>
</template>

<script>
import { controlType, runStatus } from "../constants";
import { compactNumber, formatDuration, formatNumber } from "../utils/format";
import { runSummary, triggerOf } from "../utils/runs";

// The totals of a list of runs, as the Results page and the editor's Run log show them above their RunTable: the
// type, status and warning chips, then the runs, their triggers, the failing controls, records fetched and runtime.
export default {
  props: {
    runs: { type: Array, required: true },
    // The type chips and the control counts (controls, failing), which say nothing about one control's runs.
    showTypes: { type: Boolean, default: false },
    showControls: { type: Boolean, default: false },
    // Chips emit filter-type, filter-status and filter-warnings when clicked.
    clickable: { type: Boolean, default: false },
  },
  emits: ["filter-type", "filter-status", "filter-warnings"],
  computed: {
    summary() {
      return runSummary(this.runs);
    },
  },
  methods: {
    compactNumber,
    controlType,
    formatDuration,
    formatNumber,
    runStatus,
    triggerOf,
  },
};
</script>
