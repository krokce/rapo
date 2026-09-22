<template>
  <q-page>
    <div>
      <h2 class="row">
        <q-chip size="xl" text-color="white" class="bg-blue-grey-7 text-weight-bold"> KPI </q-chip>
        &nbsp;
        {{ previousKpiType ? previousKpiType : "New KPI type" }}
      </h2>

      <q-card>
        <q-tabs
          v-model="tab"
          class="text-white bg-blue-grey-7"
          active-color="light-blue-1"
          indicator-color="light-blue-1"
          align="left"
          inline-label
          narrow-indicator
          no-caps>
          <q-tab name="main" label="Main" icon="fas fa-window-maximize" />
          <q-tab name="controls" :label="controlsTabLabel" icon="fas fa-chart-line" />
        </q-tabs>

        <q-separator />

        <q-form @submit="validateAndSave" @reset="cancel" ref="myForm">
          <q-tab-panels v-model="tab" animated keep-alive>
            <q-tab-panel name="main">
              <div class="q-ma-lg q-gutter-y-md">
                <div class="row q-gutter-md">
                  <q-input
                    class="col-2"
                    outlined
                    v-model="kpiType.kpi_type"
                    label="Code"
                    maxlength="20"
                    @keyup="kpiType.kpi_type && (kpiType.kpi_type = kpiType.kpi_type.toUpperCase())" />

                  <q-input class="col" outlined v-model="kpiType.kpi_type_desc" label="Description" maxlength="4000" />

                  <q-input class="col-1" outlined v-model="kpiType.kpi_value_unit" label="Unit" maxlength="10" />

                  <q-input class="col-1" outlined type="number" v-model.number="kpiType.kpi_priority" label="Priority" />

                  <q-input class="col-2" outlined type="number" v-model.number="kpiType.kpi_decimal_places" label="Decimal places" />
                </div>

                <div class="text-caption text-grey-7">
                  The code identifies the KPI everywhere and is stored upper case. Priority orders the KPIs of a control, lowest first. Decimal places
                  are how the value is rounded for the dashboard.
                </div>

                <div v-for="statement in statements" :key="statement.field">
                  <code-box :label="statement.label" v-model="kpiType[statement.field]">
                    <template v-slot:actions>
                      <q-btn class="col-auto" flat size="sm" label="Check" :loading="checking === statement.field" @click="checkStatement(statement)" />
                    </template>
                  </code-box>
                  <div class="text-caption text-grey-7 q-mt-xs">
                    Binds <span class="text-weight-medium">{{ statement.bind }}</span
                    >. Must return a single numeric column. {{ statement.empty }}
                  </div>
                  <div v-if="checks[statement.field]" class="text-caption q-mt-xs" :class="checks[statement.field].color">
                    {{ checks[statement.field].message }}
                  </div>
                </div>

                <div class="row q-my-md q-gutter-md">
                  <q-btn label="Save" type="submit" color="primary" :loading="saving" />
                  <q-btn label="Cancel" type="reset" color="primary" flat class="q-ml-sm" />
                </div>
              </div>
            </q-tab-panel>

            <q-tab-panel name="controls">
              <div class="q-ma-lg q-gutter-y-md">
                <q-markup-table flat dense>
                  <thead>
                    <tr class="bg-blue-grey-2">
                      <th class="text-center sortable" style="width: 50px" @click="toggleSort(sort, 'control_type')">
                        Type
                        <q-icon v-if="sort.key === 'control_type'" :name="sortIcon(sort)" size="12px" />
                      </th>
                      <th class="text-left sortable" @click="toggleSort(sort, 'control_name')">
                        Name
                        <q-icon v-if="sort.key === 'control_name'" :name="sortIcon(sort)" size="12px" />
                      </th>
                      <th class="text-left sortable" @click="toggleSort(sort, 'control_description')">
                        Description
                        <q-icon v-if="sort.key === 'control_description'" :name="sortIcon(sort)" size="12px" />
                      </th>
                      <th class="text-left">
                        <span class="text-left sortable" @click="toggleSort(sort, 'schedule_days')"> Periods back</span>
                        <q-icon v-if="sort.key === 'schedule_days'" :name="sortIcon(sort)" size="12px" /> /
                        <span class="text-left sortable" @click="toggleSort(sort, 'schedule_time')"> Schedule</span>
                        <q-icon v-if="sort.key === 'schedule_time'" :name="sortIcon(sort)" size="12px" />
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="!usedControls.length">
                      <td colspan="4" class="text-grey-7">No control uses this KPI type.</td>
                    </tr>

                    <!-- The rows follow racs_kpi_config, so one naming a control that is gone is still listed, by name only. -->
                    <tr
                      v-for="row in sortedUsedControls"
                      :key="row.control.control_name"
                      :class="{ 'clickable-row': !row.missing }"
                      @click="!row.missing && $router.push({ name: 'edit-control', params: { controlId: row.control.control_id } })">
                      <td>
                        <q-chip
                          v-if="!row.missing"
                          size="12px"
                          text-color="white"
                          :class="'bg-' + controlTypeColor(row.control.control_type)"
                          class="text-weight-bold">
                          {{ row.control.control_type }}
                        </q-chip>
                      </td>
                      <td class="text-left" style="width: 300px">
                        <div class="text-weight-bold text-grey-9" style="font-size: 16px">
                          {{ row.control.control_name }}
                        </div>
                        <div v-if="!row.missing">
                          <small class="text-indigo-4"> v.{{ toDateTimeString(row.control.updated_date) }} </small>
                        </div>
                        <div v-else>
                          <small class="text-red-4"> No control of that name </small>
                        </div>
                      </td>

                      <td class="text-left" style="width: 100%">
                        <div style="white-space: normal; word-wrap: break-word">
                          {{ row.control.control_description }}
                        </div>

                        <div class="row justify-start items-center">
                          <q-chip v-if="!row.missing && row.control.status !== 'Y'" size="sm" color="red-4" text-color="white" icon="fas fa-clock">
                            Scheduler inactive
                          </q-chip>

                          <q-chip v-if="!row.missing && row.control.need_postrun_hook != 'Y'" size="sm" color="red-4" text-color="white" icon="fas fa-bolt">
                            No Post-run hook
                          </q-chip>

                          <q-chip v-if="row.control.prerequisite_sql" size="sm" color="indigo-4" text-color="white" icon="fas fa-database">
                            Prerequisite SQL
                          </q-chip>

                          <q-chip v-if="row.control.preparation_sql" size="sm" color="indigo-4" text-color="white" icon="fas fa-database">
                            Preparation SQL
                          </q-chip>

                          <q-chip v-if="row.control.completion_sql" size="sm" color="indigo-4" text-color="white" icon="fas fa-database">
                            Completion SQL
                          </q-chip>

                          <q-chip v-if="row.control.need_prerun_hook === 'Y'" size="sm" color="indigo-4" text-color="white" icon="fas fa-bolt">
                            Pre-run hook
                          </q-chip>

                          <q-chip v-if="row.control.case_config" size="sm" color="indigo-4" text-color="white" icon="fas fa-tag"> Case definition </q-chip>

                          <q-chip v-if="iterationCount(row.control) > 0" size="sm" color="indigo-4" text-color="white" icon="fas fa-history">
                            +{{ iterationCount(row.control) }} Iteration{{ iterationCount(row.control) > 1 ? "s" : "" }}
                          </q-chip>

                          <q-chip
                            v-if="row.control.source_type_a"
                            color="green-8"
                            text-color="white"
                            size="sm"
                            icon-right="fas fa-plug fa-rotate-270"
                            style="align-items: center">
                            {{ row.control.source_type_a }}
                          </q-chip>
                          <q-icon v-if="row.control.source_type_a && row.control.source_type_b" name="fas fa-wave-square" size="9px" color="green-8" />
                          <q-chip
                            v-if="row.control.source_type_b"
                            color="green-8"
                            text-color="white"
                            size="sm"
                            icon="fas fa-plug fa-rotate-90"
                            style="align-items: center">
                            {{ row.control.source_type_b }}
                          </q-chip>
                        </div>
                      </td>
                      <td style="width: 100px">
                        <div v-if="!row.missing" class="row justify-start items-center">
                          <schedule-present-box
                            :schedule="row.control.schedule_config"
                            :period_back="row.control.period_back"
                            :period_type="row.control.period_type"></schedule-present-box>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </q-markup-table>

                <div class="row q-my-md q-gutter-md">
                  <q-btn label="Save" type="submit" color="primary" :loading="saving" />
                  <q-btn label="Cancel" type="reset" color="primary" flat class="q-ml-sm" />
                </div>
              </div>
            </q-tab-panel>
          </q-tab-panels>
        </q-form>
      </q-card>
    </div>
  </q-page>
</template>

<script>
import { mapActions, mapState } from "vuex";
import CodeBox from "./CodeBox.vue";
import SchedulePresentBox from "./SchedulePresentBox.vue";
import { api, notifyError } from "../api";
import { controlTypeColor } from "../constants";
import { toDateTimeString } from "../utils/format";
import { sortIcon, sortRows, toggleSort } from "../utils/sort";

// The two statements RACS_KPI_PKG falls back to when a control leaves its own column NULL: the KPI value for a
// run, then the alarm level for that value.
const STATEMENTS = [
  {
    field: "default_kpi_sql_statement",
    label: "Default KPI SQL statement",
    bind: ":v_processid",
    empty: "Left empty, only the controls that bring their own statement get a value for this KPI.",
  },
  {
    field: "default_alarm_sql_statement",
    label: "Default alarm SQL statement",
    bind: ":v_kpi_value",
    empty: "Left empty, only the controls that bring their own statement get an alarm level for this KPI.",
  },
];

// The statements are empty strings rather than null, so the editor always has something to bind; the server
// turns a blank one back into NULL, which is what "this type ships no default" means.
function emptyKpiType() {
  return {
    kpi_type: "",
    kpi_type_desc: "",
    kpi_value_unit: "",
    kpi_priority: null,
    kpi_decimal_places: null,
    default_kpi_sql_statement: "",
    default_alarm_sql_statement: "",
  };
}

// One row of racs_kpi_type. The code is the primary key, so an edit that changes it is a rename: the controls
// that use the type are moved over by the server, which is what the confirmation before saving is about.
export default {
  components: { CodeBox, SchedulePresentBox },
  props: ["kpiCode"],
  data() {
    return {
      statements: STATEMENTS,
      tab: "main",
      kpiType: emptyKpiType(),
      previousKpiType: null,
      usage: [],
      checks: {},
      checking: null,
      saving: false,
      sort: {
        key: null,
        dir: "asc",
      },
    };
  },
  computed: {
    ...mapState(["kpiTypes", "controlCatalogue"]),
    controlsTabLabel() {
      return this.usedControls.length ? "Controls (" + this.usedControls.length + ")" : "Controls";
    },
    // One row per racs_kpi_config row of this type, so the table and the tab count can never disagree. A
    // configuration naming a control that does not exist any more keeps its name and nothing else.
    usedControls() {
      return this.usage
        .filter((item) => item.kpi_type === this.previousKpiType)
        .map((item) => {
          const control = this.controlCatalogue.find((entry) => entry.control_id === item.control_id);
          return control ? { control, missing: false } : { control: { control_name: item.processname }, missing: true };
        });
    },
    sortedUsedControls() {
      const key = this.sort.key;
      if (!key) {
        return this.usedControls;
      }
      return sortRows(this.usedControls, (row) => this.sortValue(row, key), this.sort.dir);
    },
    // The controls of the type as it was loaded, which a rename would move over.
    usedByControls() {
      return this.usage.filter((item) => item.kpi_type === this.previousKpiType).map((item) => item.processname);
    },
  },
  methods: {
    ...mapActions(["updateKpiTypes", "updateControlCatalogue"]),
    controlTypeColor,
    toDateTimeString,
    sortIcon,
    toggleSort,
    // A malformed iteration_config must not break rendering of the whole table.
    iterationCount(control) {
      try {
        return control.iteration_config ? JSON.parse(control.iteration_config).length || 0 : 0;
      } catch (err) {
        return 0;
      }
    },
    // Periods back in days, and the scheduled time of day in seconds, as the catalogue page sorts them.
    sortValue(row, key) {
      if (row.missing) {
        return key === "control_name" ? row.control.control_name : null;
      }
      const control = row.control;
      if (key === "schedule_days") {
        return control.period_back == null ? null : control.period_back * ({ W: 7, M: 30 }[control.period_type] || 1);
      }
      if (key === "schedule_time") {
        try {
          const schedule = JSON.parse(control.schedule_config);
          const [hour, min, sec] = [schedule.hour, schedule.min, schedule.sec].map((value) => {
            const match = String(value ?? "").match(/\d+/);
            return match ? Number(match[0]) : null;
          });
          return hour != null && min != null ? hour * 3600 + min * 60 + (sec || 0) : null;
        } catch (err) {
          return null;
        }
      }
      return control[key];
    },
    loadKpiType(data) {
      this.kpiType = { ...emptyKpiType(), ...JSON.parse(JSON.stringify(data)) };
      for (const statement of STATEMENTS) {
        this.kpiType[statement.field] = this.kpiType[statement.field] || "";
      }
      this.previousKpiType = data.kpi_type;
    },
    // Every validated field lives on the Main tab, so a complaint about one switches back to it.
    validateAndSave() {
      const code = (this.kpiType.kpi_type || "").trim().toUpperCase();
      const unit = (this.kpiType.kpi_value_unit || "").trim();
      // The unit column holds 10 bytes, not 10 characters, and units like the euro sign take three of them.
      const bytes = new TextEncoder().encode(unit).length;
      const numbersAreWhole = ["kpi_priority", "kpi_decimal_places"].every((field) => {
        const value = this.kpiType[field];
        return value === null || value === "" || (Number.isInteger(value) && value >= 0);
      });

      let error = null;
      if (!code) {
        error = "Please enter a KPI code.";
      } else if (code.length > 20) {
        error = "KPI code is longer than 20 characters.";
      } else if (this.kpiTypes.some((item) => item.kpi_type === code && item.kpi_type !== this.previousKpiType)) {
        error = "KPI type " + code + " already exists.";
      } else if (bytes > 10) {
        error = "Unit is too long (" + bytes + " of 10 bytes).";
      } else if (!numbersAreWhole) {
        error = "Priority and decimal places must be whole numbers, zero or more.";
      }

      if (error) {
        this.$q.notify({ type: "negative", message: error });
        this.tab = "main";
        return;
      }

      this.kpiType.kpi_type = code;
      this.kpiType.kpi_value_unit = unit;

      if (this.previousKpiType && this.previousKpiType !== code) {
        this.confirmRename();
      } else {
        this.save();
      }
    },
    // A rename moves the racs_kpi_config rows of the controls along with the type, so it is worth naming them.
    confirmRename() {
      const names = this.usedByControls;
      const message = names.length
        ? names.length + " control(s) use " + this.previousKpiType + " and will be moved to " + this.kpiType.kpi_type + ": " + names.join(", ") + "."
        : "No control uses " + this.previousKpiType + ".";
      this.$q
        .dialog({
          title: "Rename " + this.previousKpiType + " to " + this.kpiType.kpi_type + "?",
          message: message,
          cancel: true,
          persistent: true,
        })
        .onOk(() => this.save());
    },
    async save() {
      this.saving = true;
      try {
        await api("save-kpi-type", { method: "POST", body: { ...this.kpiType, previous_kpi_type: this.previousKpiType } });
      } catch (error) {
        // Stay on the page so unsaved edits are not lost.
        this.saving = false;
        notifyError("KPI type was not saved.", error);
        return;
      }
      // Nothing watches racs_kpi_type, so the catalogue in the store is reloaded here.
      await this.updateKpiTypes({ force: true }).catch((error) => notifyError("Failed to reload KPI types.", error));
      this.$q.notify({ type: "positive", message: "KPI type " + this.kpiType.kpi_type + " was saved successfully." });
      this.$router.push({ name: "kpi-types" });
    },
    cancel() {
      this.$q.notify({ type: "warning", message: "Changes discarded" });
      this.$router.push({ name: "kpi-types" });
    },
    // Parses the statement on the server without executing it, and never blocks saving: a default statement may
    // well name a table that only some controls have.
    async checkStatement(statement) {
      this.checking = statement.field;
      try {
        const result = await api("validate-kpi-sql", {
          method: "POST",
          body: { statement: this.kpiType[statement.field] },
          loadingBar: false,
        });
        if (!result.valid) {
          this.checks[statement.field] = { message: result.error, color: "text-negative" };
        } else if (result.warning) {
          this.checks[statement.field] = { message: result.warning, color: "text-warning" };
        } else {
          const column = result.columns[0];
          this.checks[statement.field] = { message: `OK — 1 column, ${column.type}`, color: "text-positive" };
        }
      } catch (error) {
        notifyError("Statement was not checked.", error);
      } finally {
        this.checking = null;
      }
    },
  },
  async mounted() {
    try {
      // Forced, because this page is where the catalogue is edited and the store caches it for the session.
      // The control catalogue feeds the Controls tab, and SchedulePresentBox reads it to name a cascade trigger.
      const [types] = await Promise.all([this.updateKpiTypes({ force: true }), this.updateControlCatalogue()]);
      this.usage = await api("get-kpi-type-usage", { loadingBar: false });
      if (this.kpiCode === "new") {
        return;
      }
      const data = types.find((item) => item.kpi_type === this.kpiCode);
      if (!data) {
        this.$q.notify({ type: "negative", message: "There is no KPI type " + this.kpiCode + "." });
        this.$router.push({ name: "kpi-types" });
        return;
      }
      this.loadKpiType(data);
    } catch (error) {
      notifyError("Failed to load the KPI type.", error);
    }
  },
};
</script>

<style scoped>
.sortable {
  cursor: pointer;
  user-select: none;
}

.clickable-row {
  cursor: pointer;
}

.clickable-row:hover {
  background: rgba(0, 0, 0, 0.03);
}
</style>
