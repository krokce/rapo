<template>
  <q-dialog v-model="visible" @hide="onHide">
    <q-card class="column no-wrap kpi-calculate" @keydown.ctrl.enter.prevent="calculate" @keydown.meta.enter.prevent="calculate">
      <q-card-section class="row items-center q-py-sm no-wrap">
        <div class="text-h6 ellipsis">Calculate KPIs</div>
        <q-chip dense class="q-ml-sm" :title="draft ? 'The statements as edited in the KPIs tab, saved or not' : 'The statements saved for the control'">
          {{ draft ? "Draft" : "Saved" }}
        </q-chip>
        <div class="text-weight-bold text-teal-8 ellipsis q-ml-xs" :title="controlName">{{ controlName }}</div>
        <q-space />
        <q-btn aria-label="Close" flat round icon="fas fa-times" v-close-popup />
      </q-card-section>
      <q-separator />

      <q-card-section class="row items-end q-gutter-sm q-py-sm">
        <q-select
          v-model="processId"
          :options="runOptions"
          emit-value
          map-options
          outlined
          dense
          options-dense
          label="Run"
          class="run-select"
          :loading="runsLoading"
          :disable="mode == 'backtest'">
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
            <span>
              <q-icon :name="runStatus(scope.opt.status).icon" :color="runStatus(scope.opt.status).color" size="xs" class="q-mr-xs" />
              <span class="text-mono">{{ scope.opt.value }}</span>
              <span class="text-grey-7 q-ml-sm">{{ scope.opt.window }}</span>
            </span>
          </template>
        </q-select>
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
        <q-input
          v-if="mode == 'backtest'"
          v-model.number="backtestCount"
          type="number"
          outlined
          dense
          label="Runs"
          :min="1"
          :max="MAX_BACKTEST"
          style="width: 80px">
          <q-tooltip>How many of the latest runs ended D to calculate (at most {{ MAX_BACKTEST }})</q-tooltip>
        </q-input>
        <q-space />
        <q-btn color="primary" icon="fas fa-sync" label="Recalculate" :disable="!canCalculate" :loading="busy" @click="calculate">
          <q-tooltip>Calculate again with the statements as they are now (Ctrl+Enter)</q-tooltip>
        </q-btn>
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
      </q-card-section>
      <q-separator />

      <div class="col scroll q-pa-md q-gutter-y-md">
        <div v-if="!kpis.length" class="text-grey-7">{{ kpisLoading ? "Loading KPIs..." : "The control has no KPIs." }}</div>
        <div v-else-if="!runs.length && !runsLoading" class="text-grey-7">The control has no runs to calculate the KPIs of.</div>

        <q-card v-for="{ kpi, cell, stored, rows } in cards" :key="kpi.kpi_type" flat bordered class="q-pa-sm">
          <div class="row items-center no-wrap q-gutter-x-sm">
            <q-chip class="q-ml-none kpi-code" :title="typeUnit(kpi.kpi_type) || 'No unit'">
              <q-avatar :icon="kpiIcon" :color="kpiUnitColor(typeUnit(kpi.kpi_type))" text-color="white" />
              {{ kpi.kpi_type }}
            </q-chip>
            <div class="col ellipsis text-grey-8" :title="typeDescription(kpi.kpi_type)">{{ typeDescription(kpi.kpi_type) }}</div>
          </div>

          <!-- One run: the value, its alarm and what the package stored for the run. -->
          <template v-if="calculatedMode == 'run'">
            <div v-if="!cell || cell.pending" class="row items-center q-pa-sm">
                <q-spinner v-if="cell" color="teal" size="1.5em" />
                <span v-else class="text-grey-7">Not calculated</span>
              </div>
              <template v-else>
                <q-banner v-if="cell.error" dense class="bg-red-1 text-red-9 q-mt-xs">
                  <template v-slot:avatar><q-icon name="fas fa-exclamation-circle" color="red-7" size="xs" /></template>
                  <div class="text-weight-medium">{{ cell.result && cell.result.stage == "alarm" ? "Alarm statement failed" : "KPI statement failed" }}</div>
                  <pre class="error-text text-mono">{{ cell.error }}</pre>
                </q-banner>
                <div v-if="cell.result" class="row items-center q-gutter-x-md q-mt-xs">
                  <div class="kpi-value text-mono" :title="String(cell.result.value)">
                    {{ formatKpiValue(cell.result.value, cell.result.kpi_decimal_places) }}
                    <span class="text-grey-7 kpi-unit">{{ cell.result.kpi_value_unit }}</span>
                  </div>
                  <q-chip>
                    <q-avatar :icon="alarmLevel(cell.result.alarm_level).icon" :color="alarmLevel(cell.result.alarm_level).color" text-color="white" />
                    {{ alarmLevel(cell.result.alarm_level).label }}
                  </q-chip>
                  <div class="text-caption text-grey-7">
                    {{ timing(cell.result) }}
                  </div>
                </div>
                <div v-if="cell.result" class="text-caption text-grey-7 q-mt-xs">
                  <div v-for="note in notes(cell.result)" :key="note">{{ note }}</div>
                </div>
                <stored-line :stored="stored" :result="cell.result" />
                <q-expansion-item v-if="cell.result" dense dense-toggle switch-toggle-side label="SQL" header-class="text-grey-8 q-px-none" class="q-mt-xs">
                  <div v-if="cell.result.kpi_sql" class="text-caption text-grey-7">KPI statement ({{ sourceLabel(cell.result.kpi_source) }}), :v_processid = '{{ cell.result.process_id }}'</div>
                  <pre v-if="cell.result.kpi_sql" class="sql-text text-mono">{{ cell.result.kpi_sql }}</pre>
                  <div v-if="cell.result.alarm_sql" class="text-caption text-grey-7">Alarm statement ({{ sourceLabel(cell.result.alarm_source) }}), :v_kpi_value = {{ cell.result.value }}</div>
                  <pre v-if="cell.result.alarm_sql" class="sql-text text-mono">{{ cell.result.alarm_sql }}</pre>
                </q-expansion-item>
              </template>
          </template>

          <!-- Last runs: how often each level fires, then one row per run. -->
          <template v-else-if="calculatedMode == 'backtest'">
            <div class="row items-center q-gutter-x-xs q-mt-xs">
              <q-chip v-for="level in levelCounts(kpi.kpi_type)" :key="level.label" dense class="q-ml-none">
                <q-avatar :icon="level.icon" :color="level.color" text-color="white" />
                {{ level.count }} × {{ level.label }}
              </q-chip>
            </div>
            <table class="backtest-table q-mt-xs">
              <thead>
                <tr>
                  <th class="text-left" title="The run the KPI is calculated for">Run</th>
                  <th class="text-left" title="The date or period the run covered">Window</th>
                  <th class="text-right" title="The KPI value calculated now, as the package rounds it">Value</th>
                  <th class="text-left" title="The alarm level calculated now from that value">Alarm</th>
                  <th class="text-right" title="The KPI value RACS_KPI_PKG stored for the run">Stored</th>
                  <th class="text-left" title="The alarm level RACS_KPI_PKG stored for the run">Stored alarm</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in rows" :key="row.run.process_id">
                  <td class="number-cell text-left">{{ row.run.process_id }}</td>
                  <td>{{ windowOf(row.run) }}</td>
                  <td v-if="!row.cell || row.cell.pending" colspan="2"><q-spinner v-if="row.cell" color="teal" size="1em" /></td>
                  <td v-else-if="row.cell.error" colspan="2" class="text-red-9 ellipsis error-cell" :title="row.cell.error">{{ row.cell.error }}</td>
                  <template v-else>
                    <td class="number-cell" :class="{ 'text-orange-9 text-weight-bold': differs(row.cell.result, row.stored, 'value') }">
                      {{ formatKpiValue(row.cell.result.value, row.cell.result.kpi_decimal_places) }}
                    </td>
                    <td>
                      <q-icon :name="alarmLevel(row.cell.result.alarm_level).icon" :color="alarmLevel(row.cell.result.alarm_level).color" size="xs" class="q-mr-xs" />
                      <span :class="{ 'text-orange-9 text-weight-bold': differs(row.cell.result, row.stored, 'alarm') }">
                        {{ alarmLevel(row.cell.result.alarm_level).label }}
                      </span>
                    </td>
                  </template>
                  <td class="number-cell">{{ row.stored ? formatKpiValue(row.stored.kpi_value, typeDecimals(kpi.kpi_type)) : "" }}</td>
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
          </template>
        </q-card>
      </div>
    </q-card>
  </q-dialog>
</template>

<script>
import { h } from "vue";
import { mapActions, mapState } from "vuex";
import { QIcon } from "quasar";
import { api, notifyError } from "../api";
import { KPI_ICON, kpiUnitColor, runStatus } from "../constants";
import { alarmLevel, calculateKpi, formatKpiValue, sameKpiValue } from "../utils/kpi";
import { toDateString, toDateTimeString } from "../utils/format";

const CONCURRENCY = 2;
const MAX_BACKTEST = 30;
const RUN_LIMIT = 200;
const SOURCE_LABELS = { draft: "as edited", saved: "saved", default: "type default" };

// What RACS_KPI_PKG stored for the run, next to the value calculated now.
const StoredLine = {
  props: { stored: Object, result: Object },
  setup(props) {
    return () => {
      const { stored, result } = props;
      if (!result) return null;
      if (!stored) return h("div", { class: "text-caption text-grey-7 q-mt-xs" }, "Stored: nothing for this run");
      const level = alarmLevel(stored.alarm_level);
      const valueDiffers = !sameKpiValue(result.value, stored.kpi_value);
      const alarmDiffers = Number(result.alarm_level || 0) !== Number(stored.alarm_level || 0);
      return h("div", { class: "q-mt-xs" }, [
        h("div", { class: "text-caption text-grey-7 row items-center q-gutter-x-xs" }, [
          h("span", "Stored:"),
          h("span", { class: ["text-mono", valueDiffers ? "text-orange-9 text-weight-bold" : ""] }, formatKpiValue(stored.kpi_value, result.kpi_decimal_places)),
          h(QIcon, { name: level.icon, color: level.color, size: "xs" }),
          h("span", { class: alarmDiffers ? "text-orange-9 text-weight-bold" : "" }, level.label),
          h("span", `· ${stored.status || ""} · ${toDateTimeString(stored.created)}`),
          valueDiffers || alarmDiffers ? h("span", { class: "text-orange-9 text-weight-bold" }, "· differs from the calculation") : null,
        ]),
        stored.status == "ERROR" && stored.kpi_sql_log ? h("pre", { class: "sql-text text-mono text-red-9" }, stored.kpi_sql_log) : null,
      ]);
    };
  },
};

// Calculates the KPIs of a control for one run, or for its latest runs, without storing anything (calculate-kpi),
// and shows them next to what RACS_KPI_PKG stored. The editor opens it with its draft, Results with the saved
// statements.
export default {
  components: { StoredLine },
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
      only: null,
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
    shownKpis() {
      return this.only ? this.kpis.filter((kpi) => kpi.kpi_type === this.only) : this.kpis;
    },
    // One card per KPI: the cell of the calculated run, or one row per run of the last runs.
    cards() {
      return this.shownKpis.map((kpi) => ({
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
      return this.shownKpis.length > 0 && (this.mode === "backtest" ? this.doneRuns.length > 0 : this.processId !== null);
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
    // options: { controlName, draft: () => rows | null, only, processId, reingestReason: string | () => string }
    async open(options) {
      this.generation++;
      this.controlName = options.controlName;
      this.draft = options.draft || null;
      this.only = options.only || null;
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
      const latest = this.doneRuns[0] || this.runs[0];
      this.processId = wanted ? wanted.process_id : latest ? latest.process_id : null;
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
      const kpis = this.shownKpis.map((kpi) => ({ ...kpi }));
      const runs =
        this.mode === "backtest"
          ? this.doneRuns.slice(0, Math.max(1, Math.min(MAX_BACKTEST, Number(this.backtestCount) || 10)))
          : [this.selectedRun];
      this.calculatedMode = this.mode;
      this.calculatedRun = this.processId;
      this.calculatedRuns = runs;
      this.cells = {};
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
    notes(result) {
      const notes = [];
      if (!result.kpi_source) notes.push("No KPI statement, own or default: the package stores 0.");
      if (result.no_rows) notes.push("The KPI statement returned no row: the package stores 0.");
      if (result.value === null) notes.push("The KPI statement returned NULL.");
      if (!result.alarm_source) notes.push("No alarm statement, own or default: the alarm level is 0.");
      return notes;
    },
    timing(result) {
      return [result.kpi_ms !== null ? `KPI ${result.kpi_ms} ms` : null, result.alarm_ms !== null ? `alarm ${result.alarm_ms} ms` : null]
        .filter(Boolean)
        .join(" · ");
    },
    sourceLabel(source) {
      return SOURCE_LABELS[source] || source;
    },
    windowOf(run) {
      const from = toDateString(run.date_from);
      const to = toDateString(run.date_to);
      return to && to !== from ? `${from} – ${to}` : from;
    },
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
.kpi-calculate
  width: 960px
  max-width: 95vw
  height: 90vh
.run-select
  min-width: 300px
.kpi-value
  font-size: 22px
.kpi-unit
  font-size: 14px
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
  width: 100%
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
  .error-cell
    max-width: 260px
</style>
