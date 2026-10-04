<template>
  <div class="col q-gutter-y-md">
    <q-card class="q-pa-sm" flat bordered>
      <div class="row items-center q-ma-xs">
        <q-item-label>KPIs</q-item-label>
        <q-space />
        <template v-if="calculable && kpiConfigObject.length">
          <span v-if="!runs.length && !runsLoading" class="text-grey-7">No runs to calculate the KPIs of</span>
          <q-select
            v-else
            v-model="processId"
            :options="runOptions"
            emit-value
            map-options
            outlined
            dense
            options-dense
            class="run-select"
            :loading="runsLoading"
            @popup-show="loadRuns">
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
            <q-tooltip anchor="top middle" self="bottom middle">The run the KPIs are calculated for, as edited and without storing them</q-tooltip>
          </q-select>
        </template>
      </div>

      <q-card-section class="q-gutter-xs">
        <div class="row no-wrap q-gutter-xs items-center" v-for="(item, index) in kpiConfigObject" v-bind:key="item.kpi_type">
          <div class="col-auto">
            <q-chip size="18px" class="kpi-code" clickable :title="`Show the statements of ${item.kpi_type} below`" @click="kpiTab = item.kpi_type">
              <q-avatar :icon="kpiIcon" :color="kpiUnitColor(typeUnit(item.kpi_type))" text-color="white" />
              {{ item.kpi_type }}
            </q-chip>
          </div>
          <q-input
            outlined
            readonly
            class="kpi-description"
            :model-value="typeDescription(item.kpi_type)"
            :suffix="typeUnit(item.kpi_type)"
            label="Description"
            :title="typeDescription(item.kpi_type)" />
          <q-input
            outlined
            class="kpi-rerun-alarm"
            type="number"
            v-model.number="kpiConfigObject[index].rerun_on_alarm_days_back"
            label="On alarm">
            <template v-slot:prepend>
              <q-icon name="fas fa-bell" @click.stop.prevent />
            </template>
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
              Run the control again when this KPI raised an alarm, for runs of the last so many days.
              <br />Leave empty or 0 to never rerun.
            </q-tooltip>
          </q-input>
          <q-input
            outlined
            class="kpi-rerun-data"
            type="number"
            v-model.number="kpiConfigObject[index].rerun_on_new_data_days_back"
            label="On new data">
            <template v-slot:prepend>
              <q-icon name="fas fa-database" @click.stop.prevent />
            </template>
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
              Run the control again when its source grew, for runs of the last so many days.
              <br />Leave empty or 0 to never rerun.
            </q-tooltip>
          </q-input>
          <q-btn aria-label="Remove row" size="sm" color="primary" flat round icon="fas fa-minus" @click="removeKpi(index)" />
          <!-- The slot is kept on every row, so the ▶ buttons stay in one column. -->
          <div class="kpi-button-slot">
          <q-btn aria-label="Add row"
            v-if="index == kpiConfigObject.length - 1"
            size="sm"
            color="primary"
            flat
            round
            icon="fas fa-plus"
            :disable="unusedTypes.length == 0">
            <q-menu>
              <q-list dense class="text-no-wrap">
                <q-item clickable v-close-popup v-for="type in unusedTypes" :key="type.kpi_type">
                  <q-item-section @click="addKpi(type.kpi_type)">
                    <q-item-label>
                    <q-chip size="12px" class="q-ml-none menu-code">
                      <q-avatar :icon="kpiIcon" :color="kpiUnitColor(type.kpi_value_unit)" text-color="white" />
                      {{ type.kpi_type }}
                    </q-chip>
                    {{ type.kpi_type_desc }}
                  </q-item-label>
                  </q-item-section>
                </q-item>
              </q-list>
            </q-menu>
          </q-btn>
          </div>
          <template v-if="calculable">
            <q-btn
              aria-label="Calculate this KPI"
              size="sm"
              color="primary"
              flat
              round
              icon="fas fa-play"
              :loading="!!(inline[item.kpi_type] && inline[item.kpi_type].pending)"
              :disable="processId === null"
              @click="calculateInline(item)">
              <q-tooltip>Calculate this KPI as edited for the run picked above, without storing it</q-tooltip>
            </q-btn>
            <kpi-inline-result class="kpi-result" :cell="inline[item.kpi_type]" :stale="isStale(item)" :run="runOf(inline[item.kpi_type])" />
          </template>
        </div>

        <q-btn v-if="kpiConfigObject.length == 0" size="md" color="primary" icon="fas fa-plus" label="Add KPI" :disable="unusedTypes.length == 0">
          <q-menu>
            <q-list dense class="text-no-wrap">
              <q-item clickable v-close-popup v-for="type in unusedTypes" :key="type.kpi_type">
                <q-item-section @click="addKpi(type.kpi_type)">
                  <q-item-label>
                    <q-chip size="12px" class="q-ml-none menu-code">
                      <q-avatar :icon="kpiIcon" :color="kpiUnitColor(type.kpi_value_unit)" text-color="white" />
                      {{ type.kpi_type }}
                    </q-chip>
                    {{ type.kpi_type_desc }}
                  </q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </q-menu>
        </q-btn>
      </q-card-section>
    </q-card>

    <q-card v-if="kpiConfigObject.length > 0" class="q-pa-sm" flat bordered>
      <q-tabs v-model="kpiTab" dense align="left" active-color="primary" indicator-color="primary" narrow-indicator>
        <q-tab v-for="item in kpiConfigObject" :key="item.kpi_type" :name="item.kpi_type">
          <div class="row items-center no-wrap q-gutter-x-xs">
            <q-icon :name="kpiIcon" :color="kpiUnitColor(typeUnit(item.kpi_type))" size="14px" />
            <span class="text-weight-medium">{{ item.kpi_type }}</span>
          </div>
          <q-tooltip>{{ typeDescription(item.kpi_type) }}</q-tooltip>
        </q-tab>
      </q-tabs>
      <q-separator />

      <q-tab-panels v-model="kpiTab" animated keep-alive>
        <q-tab-panel v-for="(item, index) in kpiConfigObject" :key="item.kpi_type" :name="item.kpi_type" class="q-gutter-y-md">
          <div v-for="statement in statements" :key="statement.field">
            <!-- Own statement: the column holds it and the engine runs it as it is. -->
            <code-box
              v-if="!usesDefault(item, statement)"
              :label="statement.label"
              :tables="statement.field === 'kpi_sql_statement' ? kpiSqlTables : null"
              :binds="[statement.bind.slice(1)]"
              :examples="statementExamples(item, statement)"
              :check="(text) => checkStatement(statement, text)"
              v-model="kpiConfigObject[index][statement.field]">
              <template v-slot:actions>
                <q-toggle
                  dense
                  size="sm"
                  :model-value="false"
                  @update:model-value="useDefault(index, statement, true)"
                  label="Use type default"
                  class="q-mr-sm" />
              </template>
            </code-box>

            <!-- The column is NULL, so the engine falls back to the statement of the KPI type. -->
            <code-box
              v-else-if="typeDefault(item.kpi_type, statement)"
              :label="statement.label"
              :model-value="typeDefault(item.kpi_type, statement)"
              readonly>
              <template v-slot:actions>
                <q-toggle
                  dense
                  size="sm"
                  :model-value="true"
                  @update:model-value="useDefault(index, statement, false)"
                  label="Use type default" />
              </template>
            </code-box>

            <!-- Neither side has a statement, so this half is skipped when the control runs. -->
            <div v-else>
              <div class="row items-center justify-between">
                <label>{{ statement.label }}</label>
                <q-toggle
                  dense
                  size="sm"
                  :model-value="true"
                  @update:model-value="useDefault(index, statement, false)"
                  label="Use type default" />
              </div>
              <div class="text-caption text-negative q-mt-xs">{{ statement.noDefault }}</div>
            </div>

            <div class="text-caption text-grey-7 q-mt-xs">
              Must return a single numeric column.
            </div>
          </div>
        </q-tab-panel>
      </q-tab-panels>
    </q-card>
  </div>
</template>

<script>
import { mapState } from "vuex";
import { api, notifyError } from "../api";
import CodeBox from "./CodeBox.vue";
import KpiInlineResult from "./KpiInlineResult.vue";
import { examplesFor } from "../utils/codeExamples";
import { calculateKpi, checkKpiStatement, defaultRunId, runWindow } from "../utils/kpi";
import { KPI_ICON, kpiUnitColor, runStatus } from "../constants";

const RUN_LIMIT = 200;

// What an inline result was calculated from, to dim it once the statements are edited.
function statementsKey(item) {
  return JSON.stringify([item.kpi_sql_statement, item.alarm_sql_statement]);
}

// The two statements of a KPI, as RACS_KPI_PKG runs them: the KPI value for a run, then the alarm level for
// that value. A NULL column means the type's default is used, which is what the "Use type default" toggle
// writes.
const STATEMENTS = [
  {
    field: "kpi_sql_statement",
    defaultField: "default_kpi_sql_statement",
    label: "KPI SQL statement",
    bind: ":v_processid",
    kind: "kpi",
    noDefault: "No default — no KPI value will be calculated.",
  },
  {
    field: "alarm_sql_statement",
    defaultField: "default_alarm_sql_statement",
    label: "Alarm SQL statement",
    bind: ":v_kpi_value",
    kind: "alarm",
    noDefault: "No default — no alarm level will be set.",
  },
];

// racs_kpi_config of a control: one row per KPI, linked to the control by name. modelValue is the parent's
// array and is edited in place, like the other editor boxes.
export default {
  components: { CodeBox, KpiInlineResult },
  props: {
    modelValue: { type: Array, required: true },
    controlName: String,
    controlType: String,
    // Whether the KPIs can be calculated for a past run (a saved control): each row shows its KPI calculated for the
    // run picked in the header, all of them once the runs are loaded, again with the row's ▶.
    calculable: { type: Boolean, default: false },
    // The saved name of the control, whose runs are offered (the form's name may be an unsaved rename).
    runsControlName: String,
  },
  data() {
    return {
      statements: STATEMENTS,
      kpiIcon: KPI_ICON,
      kpiTab: null,
      tableColumns: {},
      // Pending/finished get-datasource-columns requests by table name (see resultTableNames). Set here rather
      // than in created(): the resultTableNames watcher below is immediate, and immediate watchers run before
      // created() does, so this would still be undefined when the first fetch fires.
      columnRequests: {},
      // get-kpi-runs of the control, newest first, and the run a row's ▶ calculates for.
      runs: [],
      runsLoading: false,
      processId: null,
      // {kpi_type: {id, pending, result, error, processId, statements}}: the inline results of the ▶ buttons.
      inline: {},
      // Numbers the inline calculations, so a late answer for a superseded one is dropped.
      calculations: 0,
    };
  },
  computed: {
    ...mapState(["kpiTypes"]),
    kpiConfigObject() {
      return this.modelValue;
    },
    // A KPI type can be configured only once per control, so the ones already taken are not offered again.
    unusedTypes() {
      const used = this.kpiConfigObject.map((item) => item.kpi_type);
      return this.kpiTypes.filter((type) => !used.includes(type.kpi_type));
    },
    runOptions() {
      return this.runs.map((run) => ({ value: run.process_id, label: String(run.process_id), status: run.status, window: runWindow(run) }));
    },
    runsKey() {
      return this.calculable ? this.runsControlName || null : null;
    },
    // The uppercase result table(s) this control's own KPI SQL runs against: one RAPO_REST_ table, or a
    // RAPO_RESA_/RAPO_RESB_ pair for REC. Unquoted Oracle identifiers fold to uppercase, and get-datasource-columns
    // matches user_tab_cols.table_name exactly, so the name is uppercased here regardless of the control's own case.
    resultTableNames() {
      if (!this.controlName) return [];
      const name = this.controlName.toUpperCase();
      return this.controlType === "REC" ? [`RAPO_RESA_${name}`, `RAPO_RESB_${name}`] : [`RAPO_REST_${name}`];
    },
    // {tableName: columns} for the KPI SQL statement box's autocomplete. A control that has never run has no
    // result table yet, so a name with no fetched columns still offers the table itself, just no columns of it.
    kpiSqlTables() {
      const tables = {};
      this.resultTableNames.forEach((name) => {
        tables[name] = this.tableColumns[name] || [];
      });
      return tables;
    },
  },
  watch: {
    runsKey: {
      immediate: true,
      handler() {
        this.processId = null;
        this.runs = [];
        this.loadRuns();
      },
    },
    // Rows already calculated follow the run picked in the header.
    // Every KPI is calculated for the run picked: the default one once the runs are loaded (the box is built when the
    // tab first opens), then each run picked in the header.
    processId(processId) {
      if (processId === null) return;
      this.kpiConfigObject.forEach((item) => this.calculateInline(item));
    },
    // The parent swaps the array on load, clone and version switch.
    modelValue() {
      this.selectFirstTab();
    },
    resultTableNames: {
      immediate: true,
      handler(names) {
        names.forEach((name) => {
          if (this.tableColumns[name] || this.columnRequests[name]) return;
          this.columnRequests[name] = api("get-datasource-columns", { params: { datasource_name: name } })
            .then((columns) => {
              this.tableColumns[name] = columns.map((column) => column.column_name);
            })
            .catch(() => {
              delete this.columnRequests[name];
            });
        });
      },
    },
  },
  mounted() {
    this.selectFirstTab();
  },
  methods: {
    kpiUnitColor,
    runStatus,
    // Loads the runs (again when the menu opens, so new runs show up), keeping the picked one while it is listed.
    async loadRuns() {
      const name = this.runsKey;
      if (!name) return;
      this.runsLoading = true;
      try {
        const runs = await api("get-kpi-runs", { params: { control_name: name, limit: RUN_LIMIT }, loadingBar: false });
        if (name !== this.runsKey) return;
        this.runs = runs;
        if (!runs.some((run) => run.process_id === this.processId)) this.processId = defaultRunId(runs);
      } catch (error) {
        notifyError("Loading the runs failed", error);
      } finally {
        this.runsLoading = false;
      }
    },
    runOf(cell) {
      return cell ? this.runs.find((run) => run.process_id === cell.processId) || null : null;
    },
    isStale(item) {
      const cell = this.inline[item.kpi_type];
      return !!cell && cell.statements !== statementsKey(item);
    },
    // Calculates one KPI with its statements as edited for the picked run, without storing it.
    async calculateInline(item) {
      const processId = this.processId;
      if (processId === null) return;
      const id = ++this.calculations;
      const kpiType = item.kpi_type;
      const kpi = { ...item };
      this.inline[kpiType] = { id, pending: true, processId, statements: statementsKey(kpi) };
      let cell;
      try {
        const result = await calculateKpi(processId, kpiType, kpi);
        cell = { result, error: result.error };
      } catch (error) {
        cell = { result: null, error: error.message };
      }
      const current = this.inline[kpiType];
      if (current && current.id === id) this.inline[kpiType] = { ...current, ...cell, pending: false };
    },
    type(code) {
      return this.kpiTypes.find((type) => type.kpi_type == code) || {};
    },
    typeDescription(code) {
      return this.type(code).kpi_type_desc || "";
    },
    typeUnit(code) {
      return this.type(code).kpi_value_unit || "";
    },
    typeDefault(code, statement) {
      return this.type(code)[statement.defaultField] || "";
    },
    usesDefault(item, statement) {
      return item[statement.field] == null;
    },
    useDefault(index, statement, value) {
      // Turning the toggle off starts from a copy of the default, so it can be adjusted instead of retyped.
      const item = this.kpiConfigObject[index];
      item[statement.field] = value ? null : this.typeDefault(item.kpi_type, statement);
    },
    selectFirstTab() {
      const selected = this.kpiConfigObject.map((item) => item.kpi_type);
      if (!selected.includes(this.kpiTab)) {
        this.kpiTab = selected.length > 0 ? selected[0] : null;
      }
    },
    addKpi(code) {
      this.kpiConfigObject.push({
        kpi_type: code,
        kpi_sql_statement: null,
        alarm_sql_statement: null,
        rerun_on_alarm_days_back: null,
        rerun_on_new_data_days_back: null,
      });
      this.kpiTab = code;
      if (this.calculable) this.calculateInline(this.kpiConfigObject[this.kpiConfigObject.length - 1]);
    },
    removeKpi(index) {
      const removed = this.kpiConfigObject[index].kpi_type;
      this.kpiConfigObject.splice(index, 1);
      delete this.inline[removed];
      if (this.kpiTab == removed) {
        const neighbour = this.kpiConfigObject[Math.min(index, this.kpiConfigObject.length - 1)];
        this.kpiTab = neighbour ? neighbour.kpi_type : null;
      }
    },
    statementExamples(item, statement) {
      const field = statement.field === "kpi_sql_statement" ? "kpi_sql" : "alarm_sql";
      return examplesFor({ field, controlType: this.controlType, controlName: this.controlName, kpiType: item.kpi_type });
    },
    checkStatement: checkKpiStatement,
  },
};
</script>

<style scoped>
/* Fixed widths, so the ▶ buttons and the inline results line up from row to row; the description gives way first. */
.kpi-description {
  flex: 1 1 0;
  min-width: 80px;
}
.kpi-rerun-alarm,
.kpi-rerun-data {
  flex: none;
  width: 152px;
}
/* Days are typed, so the number inputs show no up/down arrows; numbers align right. */
.kpi-rerun-alarm :deep(input),
.kpi-rerun-data :deep(input) {
  text-align: right;
  -moz-appearance: textfield;
  appearance: textfield;
}
.kpi-rerun-alarm :deep(input::-webkit-outer-spin-button),
.kpi-rerun-alarm :deep(input::-webkit-inner-spin-button),
.kpi-rerun-data :deep(input::-webkit-outer-spin-button),
.kpi-rerun-data :deep(input::-webkit-inner-spin-button) {
  -webkit-appearance: none;
  margin: 0;
}
.kpi-button-slot {
  flex: none;
  width: 32px;
}
.kpi-result {
  flex: none;
  width: 290px;
}
.run-select {
  min-width: 260px;
}

/* Wide enough for a four-character code, so the rows stay aligned with the least gap before the description. */
.kpi-code {
  min-width: 6em;
}

/* Equal-width code chips, so the descriptions in the Add KPI menu line up. */
.menu-code {
  min-width: 76px;
}
</style>
