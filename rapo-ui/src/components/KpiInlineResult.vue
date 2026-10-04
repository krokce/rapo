<template>
  <div class="row items-center no-wrap kpi-inline" :class="{ 'kpi-inline--stale': stale && cell && !cell.pending }">
    <template v-if="cell">
      <q-spinner v-if="cell.pending" color="teal" size="1.5em" class="q-ml-sm" />

      <!-- A failing statement replaces the value, unit and alarm. -->
      <div v-else-if="cell.error" class="row items-center no-wrap kpi-inline__error cursor-pointer" @click="copyError">
        <q-icon name="fas fa-exclamation-circle" color="red-7" size="xs" class="q-mr-xs" />
        <span class="text-weight-bold text-red-9 q-mr-xs text-no-wrap">{{ failedLabel }}</span>
        <span class="text-red-9 ellipsis">{{ firstLine }}</span>
        <q-tooltip max-width="600px">
          <div v-if="stale" class="q-mb-xs">{{ STALE_NOTE }}</div>
          <pre class="kpi-inline__pre text-mono">{{ cell.error }}</pre>
          <div class="q-mt-xs">Click to copy</div>
        </q-tooltip>
      </div>

      <template v-else-if="cell.result">
        <!-- Value and unit share a baseline, so the smaller unit sits on the value's line. -->
        <div class="row items-baseline no-wrap">
        <div class="kpi-inline__value text-mono text-right">
          <q-icon v-if="cell.result.no_rows || cell.result.value === null" name="fas fa-info-circle" color="grey-6" size="xs" class="q-mr-xs" />
          {{ formatKpiValue(cell.result.value, cell.result.kpi_decimal_places) }}
          <q-tooltip max-width="600px">
            <div v-if="stale" class="q-mb-xs">{{ STALE_NOTE }}</div>
            <div class="text-mono">{{ String(cell.result.value) }}</div>
            <div v-if="run">Run {{ run.process_id }} · {{ runWindow(run) }}</div>
            <div v-for="note in kpiNotes(cell.result)" :key="note">{{ note }}</div>
            <div>{{ kpiTiming(cell.result) }}</div>
          </q-tooltip>
        </div>
        <div class="kpi-inline__unit text-grey-7 ellipsis" :title="cell.result.kpi_value_unit">{{ cell.result.kpi_value_unit }}</div>
        </div>
        <q-chip dense class="kpi-inline__alarm">
          <q-avatar :icon="alarmLevel(cell.result.alarm_level).icon" :color="alarmLevel(cell.result.alarm_level).color" text-color="white" />
          <span class="ellipsis">{{ alarmLevel(cell.result.alarm_level).label }}</span>
        </q-chip>
      </template>
    </template>
  </div>
</template>

<script>
import { copyAndNotify } from "../runActions";
import { alarmLevel, formatKpiValue, kpiNotes, kpiTiming, runWindow } from "../utils/kpi";

const STALE_NOTE = "Calculated before the statements changed: play again";

// The value, unit and alarm level of one KPI calculated in the KPIs tab (calculate-kpi), or its error. cell is
// { pending, result, error }, run the get-kpi-runs row it was calculated for; stale dims it.
export default {
  props: {
    cell: Object,
    run: Object,
    stale: Boolean,
  },
  data() {
    return { STALE_NOTE };
  },
  computed: {
    failedLabel() {
      return this.cell.result && this.cell.result.stage == "alarm" ? "Alarm failed" : "KPI failed";
    },
    firstLine() {
      return String(this.cell.error).split("\n")[0];
    },
  },
  methods: {
    alarmLevel,
    formatKpiValue,
    kpiNotes,
    kpiTiming,
    runWindow,
    copyError() {
      copyAndNotify(this.cell.error, "Error", "Failed to copy the error to clipboard.");
    },
  },
};
</script>

<style lang="sass" scoped>
.kpi-inline
  min-width: 0
.kpi-inline--stale
  opacity: 0.5
.kpi-inline__error
  min-width: 0
.kpi-inline__value
  width: 130px
  flex: none
  font-size: 18px
  padding: 0 6px
  border-radius: 4px
  background: var(--rapo-highlight)
.kpi-inline__unit
  width: 48px
  flex: none
  padding: 0 6px
/* One width for every level, so the chips line up from row to row. */
.kpi-inline__alarm
  width: 96px
  flex: none
  margin-left: 8px
.kpi-inline__pre
  white-space: pre-wrap
  word-break: break-word
  margin: 0
</style>
