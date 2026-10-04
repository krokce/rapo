<template>
  <q-dialog v-model="visible" @hide="onHide">
    <q-card class="column no-wrap kpi-calculate" @keydown.ctrl.enter.prevent="calculate" @keydown.meta.enter.prevent="calculate">
      <q-card-section class="row items-center q-py-sm no-wrap">
        <div class="text-h6 text-no-wrap">Calculate KPIs</div>
        <div class="text-h6 text-weight-bold text-teal-8 ellipsis q-ml-sm" :title="controlName">{{ controlName }}</div>
        <q-chip dense class="q-ml-sm" :title="draft ? 'The statements as edited in the KPIs tab, saved or not' : 'The statements saved for the control'">
          {{ draft ? "Draft" : "Saved" }}
        </q-chip>
        <q-space />
        <q-btn aria-label="Close" flat round icon="fas fa-times" v-close-popup />
      </q-card-section>
      <q-separator />

      <div class="col column no-wrap q-pa-md q-gutter-y-md kpi-calculate__body">
        <!-- What to calculate: one run, or the latest runs ended D. -->
        <q-card flat bordered class="q-pa-sm">
          <div class="row items-center q-gutter-sm">
            <q-btn-toggle
              v-model="mode"
              no-caps
              unelevated
              toggle-color="primary"
              color="grey-3"
              text-color="grey-9"
              :options="[
                { label: 'This run', value: 'run' },
                { label: 'Last runs', value: 'backtest' },
              ]" />
            <q-select
              v-if="mode == 'run'"
              v-model="processId"
              :options="runOptions"
              emit-value
              map-options
              outlined
              dense
              options-dense
              label="Run"
              class="run-select"
              :loading="runsLoading">
              <template v-slot:option="scope">
                <q-item v-bind="scope.itemProps">
                  <q-item-section avatar>
                    <q-icon :name="runStatus(scope.opt.status).icon" :color="runStatus(scope.opt.status).color" size="xs" />
                  </q-item-section>
                  <q-item-section>
                    <q-item-label>
                      <span class="text-mono">{{ scope.opt.value }}</span>
                      <span class="text-grey-7 q-ml-sm">{{ scope.opt.window }}</span>
                    </q-item-label>
                  </q-item-section>
                </q-item>
              </template>
              <template v-slot:selected-item="scope">
                <span class="ellipsis">
                  <q-icon :name="runStatus(scope.opt.status).icon" :color="runStatus(scope.opt.status).color" size="xs" class="q-mr-xs" />
                  <span class="text-mono">{{ scope.opt.value }}</span>
                  <span class="text-grey-7 q-ml-sm">{{ scope.opt.window }}</span>
                </span>
              </template>
            </q-select>
            <template v-else>
              <q-input
                v-model.number="backtestCount"
                type="number"
                outlined
                dense
                label="Runs"
                class="count-input"
                :min="1"
                :max="MAX_BACKTEST">
                <q-tooltip>How many of the latest runs ended D to calculate (at most {{ MAX_BACKTEST }})</q-tooltip>
              </q-input>
              <span class="text-grey-7">latest runs ended D, {{ doneRuns.length }} available</span>
            </template>
            <q-space />
            <div class="row no-wrap q-gutter-x-sm">
            <q-btn
              v-if="mode == 'run' && selectedRun && selectedRun.status == 'D'"
              outline
              color="primary"
              icon="fas fa-file-import"
              label="Re-ingest"
              :disable="!!reingestBlocked || reingesting"
              :loading="reingesting"
              @click="confirmReingest">
              <q-tooltip v-if="reingestBlocked">{{ reingestBlocked }}</q-tooltip>
              <q-tooltip v-else>Store the saved KPIs of this run with RACS_KPI_PKG and post them to the dashboard</q-tooltip>
            </q-btn>
            <q-btn color="primary" icon="fas fa-sync" label="Recalculate" :disable="!canCalculate" :loading="busy" @click="calculate">
              <q-tooltip>Calculate again with the statements as they are now (Ctrl+Enter)</q-tooltip>
            </q-btn>
            </div>
          </div>
        </q-card>

        <div class="scroll kpi-calculate__list">
          <q-card v-if="!kpis.length || (!runs.length && !runsLoading)" flat bordered class="q-pa-md text-grey-7">
            <template v-if="!kpis.length">{{ kpisLoading ? "Loading KPIs..." : "The control has no KPIs." }}</template>
            <template v-else>The control has no runs to calculate the KPIs of.</template>
          </q-card>

          <!-- One run: a row per KPI with the value calculated now next to what the package stored. -->
          <q-card v-else-if="calculatedMode == 'run'" flat bordered class="q-pa-sm">
            <div class="kpi-grid kpi-grid--head text-caption">
              <div class="q-pl-xs" title="The KPI type and its description">KPI</div>
              <div></div>
              <div title="The KPI value calculated now, as the package rounds it, its unit and the alarm level calculated from it">Calculated</div>
              <div title="The KPI value and alarm level RACS_KPI_PKG stored for the run; orange where they differ from the calculation">Stored</div>
              <div class="kpi-time" title="How long the KPI and alarm statements took">Time</div>
              <div></div>
            </div>
            <div v-for="{ kpi, cell, stored } in cards" :key="kpi.kpi_type" class="kpi-row">
              <div class="kpi-grid">
                <q-chip class="q-ml-none kpi-code" :title="typeUnit(kpi.kpi_type) || 'No unit'">
                  <q-avatar :icon="kpiIcon" :color="kpiUnitColor(typeUnit(kpi.kpi_type))" text-color="white" />
                  {{ kpi.kpi_type }}
                </q-chip>
                <div class="ellipsis text-grey-8" :title="typeDescription(kpi.kpi_type)">{{ typeDescription(kpi.kpi_type) }}</div>
                <div>
                  <span v-if="!cell" class="text-grey-7 q-ml-sm">Not calculated</span>
                  <kpi-inline-result v-else :cell="cell" :run="calculatedRunRow" />
                </div>
                <div class="row items-center no-wrap stored-cell" :title="storedTitle(stored)">
                  <template v-if="cell && cell.result && !cell.pending">
                    <template v-if="stored">
                      <span class="text-mono q-mr-sm" :class="{ 'text-orange-9 text-weight-bold': differs(cell.result, stored, 'value') }">
                        {{ formatKpiValue(stored.kpi_value, cell.result.kpi_decimal_places) }}
                      </span>
                      <q-icon :name="alarmLevel(stored.alarm_level).icon" :color="alarmLevel(stored.alarm_level).color" size="xs" class="q-mr-xs" />
                      <span class="ellipsis" :class="{ 'text-orange-9 text-weight-bold': differs(cell.result, stored, 'alarm') }">
                        {{ alarmLevel(stored.alarm_level).label }}
                      </span>
                      <q-icon v-if="stored.status == 'ERROR'" name="fas fa-exclamation-circle" color="red-7" size="xs" class="q-ml-xs" />
                    </template>
                    <span v-else class="text-grey-6">Not stored</span>
                  </template>
                </div>
                <div class="kpi-time text-caption text-grey-7 ellipsis">{{ cell && cell.result && !cell.pending ? timing(cell.result) : "" }}</div>
                <q-btn
                  v-if="cell && !cell.pending && (cell.result || cell.error)"
                  aria-label="Details"
                  size="sm"
                  flat
                  round
                  color="grey-7"
                  :icon="expanded[kpi.kpi_type] ? 'fas fa-chevron-up' : 'fas fa-chevron-down'"
                  @click="expanded[kpi.kpi_type] = !expanded[kpi.kpi_type]">
                  <q-tooltip>{{ expanded[kpi.kpi_type] ? "Hide" : "Show" }} the error, notes and statements</q-tooltip>
                </q-btn>
              </div>

              <div v-if="expanded[kpi.kpi_type] && cell && !cell.pending" class="kpi-details q-mb-sm">
                <q-banner v-if="cell.error" dense class="bg-red-1 text-red-9 q-mb-xs">
                  <template v-slot:avatar><q-icon name="fas fa-exclamation-circle" color="red-7" size="xs" /></template>
                  <div class="text-weight-medium">{{ cell.result && cell.result.stage == "alarm" ? "Alarm statement failed" : "KPI statement failed" }}</div>
                  <pre class="error-text text-mono">{{ cell.error }}</pre>
                </q-banner>
                <template v-if="cell.result">
                  <div v-for="note in notes(cell.result)" :key="note" class="text-caption text-grey-7">{{ note }}</div>
                  <template v-if="stored">
                    <div class="text-caption text-grey-7">Stored {{ stored.status || "" }} at {{ toDateTimeString(stored.created) }}</div>
                    <pre v-if="stored.status == 'ERROR' && stored.kpi_sql_log" class="sql-text text-mono text-red-9">{{ stored.kpi_sql_log }}</pre>
                  </template>
                  <div v-if="cell.result.kpi_sql" class="text-caption text-grey-7 q-mt-xs">
                    KPI statement ({{ sourceLabel(cell.result.kpi_source) }}), :v_processid = '{{ cell.result.process_id }}'
                  </div>
                  <pre v-if="cell.result.kpi_sql" class="sql-text text-mono">{{ cell.result.kpi_sql }}</pre>
                  <div v-if="cell.result.alarm_sql" class="text-caption text-grey-7">
                    Alarm statement ({{ sourceLabel(cell.result.alarm_source) }}), :v_kpi_value = {{ cell.result.value }}
                  </div>
                  <pre v-if="cell.result.alarm_sql" class="sql-text text-mono">{{ cell.result.alarm_sql }}</pre>
                </template>
              </div>
            </div>
          </q-card>

          <!-- Last runs: per KPI, how often each level fires, then one row per run. -->
          <div v-else-if="calculatedMode == 'backtest'" class="q-gutter-y-md">
            <q-card v-for="{ kpi, rows } in cards" :key="kpi.kpi_type" flat bordered class="q-pa-sm">
              <div class="row items-center no-wrap q-gutter-x-sm">
                <q-chip class="q-ml-none kpi-code" :title="typeUnit(kpi.kpi_type) || 'No unit'">
                  <q-avatar :icon="kpiIcon" :color="kpiUnitColor(typeUnit(kpi.kpi_type))" text-color="white" />
                  {{ kpi.kpi_type }}
                </q-chip>
                <div class="col ellipsis text-grey-8" :title="typeDescription(kpi.kpi_type)">
                  {{ typeDescription(kpi.kpi_type) }}
                  <span v-if="typeUnit(kpi.kpi_type)" class="text-grey-6">({{ typeUnit(kpi.kpi_type) }})</span>
                </div>
                <q-chip v-for="level in levelCounts(kpi.kpi_type)" :key="level.label" dense>
                  <q-avatar :icon="level.icon" :color="level.color" text-color="white" />
                  {{ level.count }} × {{ level.label }}
                </q-chip>
              </div>
              <table class="backtest-table q-mt-xs">
                <thead>
                  <tr>
                    <th class="text-left col-run" title="The run the KPI is calculated for">Run</th>
                    <th class="text-left col-window" title="The date or period the run covered">Window</th>
                    <th class="text-right col-value" title="The KPI value calculated now, as the package rounds it">Value</th>
                    <th class="text-left col-alarm" title="The alarm level calculated now from that value">Alarm</th>
                    <th class="text-right col-value" title="The KPI value RACS_KPI_PKG stored for the run; orange where it differs">Stored</th>
                    <th class="text-left" title="The alarm level RACS_KPI_PKG stored for the run; orange where it differs">Stored alarm</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in rows" :key="row.run.process_id">
                    <td class="number-cell text-left">{{ row.run.process_id }}</td>
                    <td>{{ windowOf(row.run) }}</td>
                    <td v-if="!row.cell || row.cell.pending" colspan="2"><q-spinner v-if="row.cell" color="teal" size="1em" /></td>
                    <td v-else-if="row.cell.error" colspan="2" class="text-red-9 ellipsis error-cell" :title="row.cell.error">{{ row.cell.error }}</td>
                    <template v-else>
                      <td class="number-cell text-right value-cell" :class="{ 'text-orange-9 text-weight-bold': differs(row.cell.result, row.stored, 'value') }">
                        {{ formatKpiValue(row.cell.result.value, row.cell.result.kpi_decimal_places) }}
                      </td>
                      <td>
                        <q-icon :name="alarmLevel(row.cell.result.alarm_level).icon" :color="alarmLevel(row.cell.result.alarm_level).color" size="xs" class="q-mr-xs" />
                        <span :class="{ 'text-orange-9 text-weight-bold': differs(row.cell.result, row.stored, 'alarm') }">
                          {{ alarmLevel(row.cell.result.alarm_level).label }}
                        </span>
                      </td>
                    </template>
                    <td class="number-cell text-right">{{ row.stored ? formatKpiValue(row.stored.kpi_value, typeDecimals(kpi.kpi_type)) : "" }}</td>
                    <td>
                      <template v-if="row.stored">
                        <q-icon :name="alarmLevel(row.stored.alarm_level).icon" :color="alarmLevel(row.stored.alarm_level).color" size="xs" class="q-mr-xs" />
                        {{ alarmLevel(row.stored.alarm_level).label }}
                      </template>
                      <span v-else class="text-grey-6">Not stored</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </q-card>
          </div>
        </div>
      </div>
    </q-card>
  </q-dialog>
</template>

<script>
import { mapActions, mapState } from "vuex";
import { api, notifyError } from "../api";
import KpiInlineResult from "./KpiInlineResult.vue";
import { KPI_ICON, kpiUnitColor, runStatus } from "../constants";
import { alarmLevel, calculateKpi, defaultRunId, formatKpiValue, kpiNotes, kpiTiming, runWindow, sameKpiValue } from "../utils/kpi";
import { toDateTimeString } from "../utils/format";

const CONCURRENCY = 2;
const MAX_BACKTEST = 30;
const RUN_LIMIT = 200;
const SOURCE_LABELS = { draft: "as edited", saved: "saved", default: "type default" };

// Calculates the KPIs of a control for one run, or for its latest runs, without storing anything (calculate-kpi),
// and shows them next to what RACS_KPI_PKG stored. The editor opens it with its draft, Results with the saved
// statements.
export default {
  components: { KpiInlineResult },
  data() {
    return {
      MAX_BACKTEST,
      kpiIcon: KPI_ICON,
      visible: false,
      controlName: null,
      // A function giving the editor's KPI rows, or null for the saved ones.
      draft: null,
      // Why Re-ingest is not offered now, or null.
      reingestReason: null,
      savedKpis: [],
      kpisLoading: false,
      runs: [],
      runsLoading: false,
      processId: null,
      mode: "run",
      backtestCount: 10,
      // What the shown results were calculated for.
      calculatedMode: null,
      calculatedRun: null,
      calculatedRuns: [],
      // {kpi_type: {process_id: {pending, result, error}}}
      cells: {},
      // {kpi_type: true} for the rows whose details are shown.
      expanded: {},
      // {process_id: {kpi_type: stored row}}
      history: {},
      busy: false,
      reingesting: false,
      // Bumped by every calculation and on close, so late answers are dropped.
      generation: 0,
    };
  },
  computed: {
    ...mapState(["kpiTypes"]),
    kpis() {
      return this.draft ? this.draft() || [] : this.savedKpis;
    },
    // One card per KPI: the cell of the calculated run, or one row per run of the last runs.
    cards() {
      return this.kpis.map((kpi) => ({
        kpi,
        cell: this.cellOf(kpi.kpi_type, this.calculatedRun),
        stored: this.storedOf(kpi.kpi_type, this.calculatedRun),
        rows: this.calculatedRuns.map((run) => ({
          run,
          cell: this.cellOf(kpi.kpi_type, run.process_id),
          stored: this.storedOf(kpi.kpi_type, run.process_id),
        })),
      }));
    },
    calculatedRunRow() {
      return this.runs.find((run) => run.process_id === this.calculatedRun) || null;
    },
    selectedRun() {
      return this.runs.find((run) => run.process_id === this.processId) || null;
    },
    runOptions() {
      return this.runs.map((run) => ({ value: run.process_id, label: String(run.process_id), status: run.status, window: this.windowOf(run) }));
    },
    doneRuns() {
      return this.runs.filter((run) => run.status === "D");
    },
    canCalculate() {
      return this.kpis.length > 0 && (this.mode === "backtest" ? this.doneRuns.length > 0 : this.processId !== null);
    },
    reingestBlocked() {
      return typeof this.reingestReason === "function" ? this.reingestReason() : this.reingestReason;
    },
  },
  methods: {
    ...mapActions(["updateKpiTypes"]),
    runStatus,
    kpiUnitColor,
    alarmLevel,
    formatKpiValue,
    // options: { controlName, draft: () => rows | null, processId, reingestReason: string | () => string }
    async open(options) {
      this.generation++;
      this.controlName = options.controlName;
      this.draft = options.draft || null;
      this.reingestReason = options.reingestReason || null;
      this.mode = "run";
      this.cells = {};
      this.history = {};
      this.calculatedMode = null;
      this.runs = [];
      this.processId = null;
      this.savedKpis = [];
      this.visible = true;
      const generation = this.generation;
      this.updateKpiTypes().catch((error) => console.error("KPI types failed:", error));
      await Promise.all([this.loadRuns(options.processId), this.draft ? null : this.loadSavedKpis()]);
      if (generation === this.generation && this.canCalculate) this.calculate();
    },
    onHide() {
      this.generation++;
      this.busy = false;
    },
    async loadRuns(processId) {
      this.runsLoading = true;
      try {
        this.runs = await api("get-kpi-runs", { params: { control_name: this.controlName, limit: RUN_LIMIT }, loadingBar: false });
      } catch (error) {
        notifyError("Loading the runs failed", error);
      } finally {
        this.runsLoading = false;
      }
      const wanted = this.runs.find((run) => run.process_id === Number(processId));
      this.processId = wanted ? wanted.process_id : defaultRunId(this.runs);
    },
    async loadSavedKpis() {
      this.kpisLoading = true;
      try {
        this.savedKpis = await api("get-control-kpis", { params: { control_name: this.controlName }, loadingBar: false });
      } catch (error) {
        notifyError("Loading the KPIs failed", error);
      } finally {
        this.kpisLoading = false;
      }
    },
    async calculate() {
      if (!this.canCalculate) return;
      const generation = ++this.generation;
      const kpis = this.kpis.map((kpi) => ({ ...kpi }));
      const runs =
        this.mode === "backtest"
          ? this.doneRuns.slice(0, Math.max(1, Math.min(MAX_BACKTEST, Number(this.backtestCount) || 10)))
          : [this.selectedRun];
      this.calculatedMode = this.mode;
      this.calculatedRun = this.processId;
      this.calculatedRuns = runs;
      this.cells = {};
      this.expanded = {};
      const tasks = [];
      for (const kpi of kpis) {
        this.cells[kpi.kpi_type] = {};
        for (const run of runs) {
          this.cells[kpi.kpi_type][run.process_id] = { pending: true };
          tasks.push({ kpi, processId: run.process_id });
        }
      }
      this.busy = true;
      this.loadHistory(runs.map((run) => run.process_id), generation);
      const worker = async () => {
        while (tasks.length && generation === this.generation) {
          const { kpi, processId } = tasks.shift();
          let cell;
          try {
            const result = await calculateKpi(processId, kpi.kpi_type, this.draft ? kpi : null);
            cell = { result, error: result.error };
          } catch (error) {
            cell = { result: null, error: error.message };
          }
          if (generation === this.generation) this.cells[kpi.kpi_type][processId] = cell;
        }
      };
      await Promise.all(Array.from({ length: CONCURRENCY }, worker));
      if (generation === this.generation) this.busy = false;
    },
    async loadHistory(processIds, generation) {
      await Promise.all(
        processIds.map(async (processId) => {
          try {
            const rows = await api("get-kpi-history", { params: { process_id: processId }, loadingBar: false });
            if (generation === this.generation || generation === undefined) {
              this.history[processId] = Object.fromEntries(rows.map((row) => [row.kpi_type, row]));
            }
          } catch (error) {
            console.error("KPI history failed:", error);
          }
        })
      );
    },
    cellOf(kpiType, processId) {
      return (this.cells[kpiType] || {})[processId] || null;
    },
    storedOf(kpiType, processId) {
      return (this.history[processId] || {})[kpiType] || null;
    },
    differs(result, stored, what) {
      if (!result || !stored) return false;
      if (what === "value") return !sameKpiValue(result.value, stored.kpi_value);
      return Number(result.alarm_level || 0) !== Number(stored.alarm_level || 0);
    },
    levelCounts(kpiType) {
      const counts = {};
      for (const run of this.calculatedRuns) {
        const cell = this.cellOf(kpiType, run.process_id);
        if (!cell || cell.pending) continue;
        const level = cell.error ? { label: "Failed", icon: "fas fa-exclamation-circle", color: "red-9" } : alarmLevel(cell.result.alarm_level);
        counts[level.label] = counts[level.label] || { ...level, count: 0 };
        counts[level.label].count++;
      }
      return Object.values(counts).sort((a, b) => b.label.localeCompare(a.label));
    },
    toDateTimeString,
    storedTitle(stored) {
      return stored ? `Stored ${stored.status || ""} at ${toDateTimeString(stored.created)}` : "";
    },
    notes: kpiNotes,
    timing: kpiTiming,
    sourceLabel(source) {
      return SOURCE_LABELS[source] || source;
    },
    windowOf: runWindow,
    typeOf(kpiType) {
      return this.kpiTypes.find((type) => type.kpi_type === kpiType) || {};
    },
    typeDescription(kpiType) {
      return this.typeOf(kpiType).kpi_type_desc || "";
    },
    typeUnit(kpiType) {
      return this.typeOf(kpiType).kpi_value_unit || "";
    },
    typeDecimals(kpiType) {
      return this.typeOf(kpiType).kpi_decimal_places;
    },
    confirmReingest() {
      const run = this.selectedRun;
      this.$q
        .dialog({
          title: "Re-ingest KPIs",
          message:
            `RACS_KPI_PKG calculates the saved KPIs of run ${run.process_id} again, overwrites what it stored for the run ` +
            "and posts the run to the dashboard.",
          cancel: true,
          persistent: true,
        })
        .onOk(() => this.reingest(run.process_id));
    },
    async reingest(processId) {
      this.reingesting = true;
      try {
        const response = await api("reingest-kpis", { method: "POST", params: { process_id: processId } });
        this.history[processId] = Object.fromEntries((response.kpis || []).map((row) => [row.kpi_type, row]));
        const failed = (response.kpis || []).filter((row) => row.status === "ERROR").map((row) => row.kpi_type);
        this.$q.notify({
          type: failed.length ? "warning" : "positive",
          message: failed.length ? `KPIs re-ingested, ${failed.join(", ")} failed: see the stored log` : "KPIs re-ingested",
        });
      } catch (error) {
        notifyError("Re-ingesting the KPIs failed", error);
      } finally {
        this.reingesting = false;
      }
    },
  },
};
</script>

<style lang="sass" scoped>
/* As tall as its content, up to 90vh; the list then scrolls. */
.kpi-calculate
  width: 1100px
  max-width: 95vw
  max-height: 90vh
.kpi-calculate__body
  flex: 1 1 auto
  min-height: 0
.kpi-calculate__list
  flex: 1 1 auto
  min-height: 0
.run-select
  min-width: 320px
.count-input
  width: 90px
/* Code | description | calculated (KpiInlineResult) | stored | time | details: one template for the head and every row. */
.kpi-grid
  display: grid
  grid-template-columns: 6.5em minmax(80px, 1fr) 300px 190px 130px 32px
  align-items: center
  column-gap: 8px
  min-height: 40px
/* Narrow dialogs drop the timing column (it is also in the value's tooltip). */
@media (max-width: 1160px)
  .kpi-grid
    grid-template-columns: 6.5em minmax(80px, 1fr) 300px 190px 32px
  .kpi-time
    display: none
.kpi-grid--head
  min-height: 0
  color: var(--rapo-label)
  font-weight: 500
  padding-bottom: 2px
  border-bottom: 1px solid var(--rapo-border-soft)
.kpi-row + .kpi-row
  border-top: 1px solid var(--rapo-grid)
.kpi-code
  min-width: 6em
.stored-cell
  min-width: 0
.kpi-details
  margin-left: calc(6.5em + 8px)
.sql-text, .error-text
  white-space: pre-wrap
  word-break: break-word
  margin: 4px 0
  font-size: 12px
.sql-text
  border: 1px solid var(--rapo-border-soft)
  background: var(--rapo-surface-alt)
  padding: 4px 8px
  border-radius: 4px
.backtest-table
  border-collapse: collapse
  table-layout: fixed
  width: 100%
  .col-run
    width: 120px
  .col-window
    width: 200px
  .col-value
    width: 120px
  .col-alarm
    width: 150px
  font-size: 13px
  th
    color: var(--rapo-label)
    font-weight: 500
    border-bottom: 1px solid var(--rapo-border-soft)
    padding: 2px 6px
  td
    padding: 2px 6px
    border-bottom: 1px solid var(--rapo-grid)
    white-space: nowrap
  .value-cell
    background: var(--rapo-highlight)
  .error-cell
    max-width: 260px
</style>
