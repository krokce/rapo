<template>
  <div class="col q-gutter-y-md">
    <q-card class="q-pa-sm" flat bordered>
      <q-item-section class="q-ma-xs">
        <q-item-label>KPIs</q-item-label>
      </q-item-section>

      <q-card-section class="q-gutter-xs">
        <div class="row q-gutter-xs items-center" v-for="(item, index) in kpiConfigObject" v-bind:key="item.kpi_type">
          <q-input outlined readonly class="col-1" :model-value="item.kpi_type" label="KPI" />
          <q-input outlined readonly class="col-4" :model-value="typeDescription(item.kpi_type)" label="Description" />
          <q-input outlined readonly class="col-1" :model-value="typeUnit(item.kpi_type)" label="Unit" />
          <q-input
            outlined
            class="col-2"
            type="number"
            v-model.number="kpiConfigObject[index].rerun_on_alarm_days_back"
            label="Rerun on alarm">
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
            class="col-2"
            type="number"
            v-model.number="kpiConfigObject[index].rerun_on_new_data_days_back"
            label="Rerun on new data">
            <template v-slot:prepend>
              <q-icon name="fas fa-database" @click.stop.prevent />
            </template>
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
              Run the control again when its source grew, for runs of the last so many days.
              <br />Leave empty or 0 to never rerun.
            </q-tooltip>
          </q-input>
          <q-btn size="sm" color="primary" flat round icon="fas fa-minus" @click="removeKpi(index)" />
          <q-btn
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
                    <q-item-label>{{ type.kpi_type }} &mdash; {{ type.kpi_type_desc }}</q-item-label>
                  </q-item-section>
                </q-item>
              </q-list>
            </q-menu>
          </q-btn>
        </div>

        <q-btn v-if="kpiConfigObject.length == 0" size="md" color="primary" icon="fas fa-plus" label="Add KPI" :disable="unusedTypes.length == 0">
          <q-menu>
            <q-list dense class="text-no-wrap">
              <q-item clickable v-close-popup v-for="type in unusedTypes" :key="type.kpi_type">
                <q-item-section @click="addKpi(type.kpi_type)">
                  <q-item-label>{{ type.kpi_type }} &mdash; {{ type.kpi_type_desc }}</q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </q-menu>
        </q-btn>
      </q-card-section>
    </q-card>

    <q-card v-if="kpiConfigObject.length > 0" class="q-pa-sm" flat bordered>
      <q-tabs v-model="kpiTab" dense align="left" active-color="primary" indicator-color="primary" narrow-indicator>
        <q-tab v-for="item in kpiConfigObject" :key="item.kpi_type" :name="item.kpi_type" :label="item.kpi_type">
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
import { api } from "../api";
import CodeBox from "./CodeBox.vue";
import { examplesFor } from "../utils/codeExamples";

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
  components: { CodeBox },
  props: {
    modelValue: { type: Array, required: true },
    controlName: String,
    controlType: String,
  },
  data() {
    return {
      statements: STATEMENTS,
      kpiTab: null,
      tableColumns: {},
      // Pending/finished get-datasource-columns requests by table name (see resultTableNames). Set here rather
      // than in created(): the resultTableNames watcher below is immediate, and immediate watchers run before
      // created() does, so this would still be undefined when the first fetch fires.
      columnRequests: {},
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
    },
    removeKpi(index) {
      const removed = this.kpiConfigObject[index].kpi_type;
      this.kpiConfigObject.splice(index, 1);
      if (this.kpiTab == removed) {
        const neighbour = this.kpiConfigObject[Math.min(index, this.kpiConfigObject.length - 1)];
        this.kpiTab = neighbour ? neighbour.kpi_type : null;
      }
    },
    statementExamples(item, statement) {
      const field = statement.field === "kpi_sql_statement" ? "kpi_sql" : "alarm_sql";
      return examplesFor({ field, controlType: this.controlType, controlName: this.controlName, kpiType: item.kpi_type });
    },
    // Parses the statement on the server without executing it. A control that has never run has no result
    // table yet, so a failure here is informative only and never blocks saving.
    checkStatement(statement, text) {
      return api("validate-kpi-sql", { method: "POST", body: { statement: text, kind: statement.kind }, loadingBar: false });
    },
  },
};
</script>

<style></style>
