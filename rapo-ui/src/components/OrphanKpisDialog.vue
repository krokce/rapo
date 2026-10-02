<template>
  <q-dialog v-model="visible">
    <q-card class="column no-wrap" style="width: 1100px; max-width: 95vw; max-height: 90vh">
      <q-card-section class="row items-center q-py-sm">
        <div class="text-h6">Orphaned KPIs</div>
        <q-space />
        <q-btn aria-label="Close" flat round icon="fas fa-times" v-close-popup />
      </q-card-section>
      <q-separator />

      <q-card-section class="col scroll">
        <div class="text-grey-7 q-mb-md">
          No control has the name these KPIs are configured for, so RACS_KPI_PKG never calculates them: their control was deleted, or renamed outside the
          application. Assign one to the control it belongs to, or delete it. The values already stored for past runs are kept either way.
        </div>
        <div v-if="!kpis.length" class="text-grey-7">None left.</div>
        <q-markup-table v-else dense flat bordered separator="horizontal">
          <thead>
            <tr>
              <th title="The control name the KPI is configured for (RACS_KPI_CONFIG.PROCESSNAME)" class="text-left">Process name</th>
              <th title="The KPI type" class="text-left">KPI</th>
              <th title="Whether the KPI has its own KPI and alarm statements or uses the type's defaults" class="text-left">Statements</th>
              <th title="The runs RACS_KPI_PKG stored a value of this KPI for (RACS_KPI_RUNHISTORY_ALL), and the latest" class="text-left">Stored</th>
              <th title="Why no control matches the name" class="text-left">Why</th>
              <th style="width: 260px"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="kpi in kpis" :key="kpi.processname + '|' + kpi.kpi_type">
              <td class="text-weight-bold">{{ kpi.processname }}</td>
              <td>
                <q-chip size="12px" class="q-ml-none" :title="typeDescription(kpi.kpi_type)">
                  <q-avatar :icon="kpiIcon" :color="kpiUnitColor(typeUnit(kpi.kpi_type))" text-color="white" />
                  {{ kpi.kpi_type }}
                </q-chip>
              </td>
              <td class="text-grey-8">{{ statementsText(kpi) }}</td>
              <td class="text-grey-8">{{ kpi.stored_runs ? `${kpi.stored_runs} run${kpi.stored_runs > 1 ? "s" : ""}, last ${toDateString(kpi.last_stored)}` : "none" }}</td>
              <td class="text-grey-8">
                <template v-if="kpi.case_match">differs only in case from control {{ kpi.case_match }}</template>
                <template v-else>no control of that name</template>
              </td>
              <td class="text-right">
                <q-btn flat dense no-caps size="sm" color="primary" label="Assign to control" :disable="busy" @click="startAssign(kpi)">
                  <q-menu v-model="assignOpen[keyOf(kpi)]" anchor="bottom right" self="top right">
                    <div class="q-pa-sm row items-center no-wrap q-gutter-x-sm" style="width: 420px">
                      <q-select
                        v-model="assignTarget"
                        :options="controlOptions"
                        use-input
                        input-debounce="0"
                        outlined
                        dense
                        options-dense
                        label="Control"
                        class="col"
                        @filter="filterControls" />
                      <q-btn dense no-caps color="primary" label="Assign" :disable="!assignTarget" @click="assign(kpi)" />
                    </div>
                  </q-menu>
                </q-btn>
                <q-btn flat dense no-caps size="sm" color="negative" label="Delete" :disable="busy" @click="remove(kpi, kpi.kpi_type)" />
                <q-btn v-if="countOf(kpi.processname) > 1" flat dense no-caps size="sm" color="negative" label="Delete all" :disable="busy" @click="remove(kpi, null)">
                  <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 5]">Delete every KPI of {{ kpi.processname }}</q-tooltip>
                </q-btn>
              </td>
            </tr>
          </tbody>
        </q-markup-table>
      </q-card-section>

      <q-separator />
      <q-card-actions align="right">
        <q-btn label="Close" flat color="primary" v-close-popup />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script>
import { mapActions, mapState } from "vuex";
import { api, notifyError } from "../api";
import { KPI_ICON, kpiUnitColor } from "../constants";
import { escapeHtml, toDateString } from "../utils/format";

// Open with this.$refs.<ref>.open(). The KPIs come from get-orphan-kpis: racs_kpi_config rows whose processname
// matches no control. After a change it emits "changed" so the page refetches them.
export default {
  name: "OrphanKpisDialog",
  props: {
    kpis: { type: Array, default: () => [] },
  },
  emits: ["changed"],
  data() {
    return { visible: false, busy: false, kpiIcon: KPI_ICON, assignOpen: {}, assignTarget: null, controlFilter: "" };
  },
  computed: {
    ...mapState(["controlCatalogue", "kpiTypes"]),
    controlOptions() {
      const needle = this.controlFilter.toUpperCase();
      return this.controlCatalogue
        .map((control) => control.control_name)
        .filter((name) => !needle || name.toUpperCase().includes(needle))
        .sort();
    },
  },
  methods: {
    ...mapActions(["updateKpiTypes"]),
    kpiUnitColor,
    toDateString,
    open() {
      this.visible = true;
      this.updateKpiTypes().catch((error) => console.error("KPI types failed:", error));
    },
    keyOf(kpi) {
      return `${kpi.processname}|${kpi.kpi_type}`;
    },
    countOf(processname) {
      return this.kpis.filter((kpi) => kpi.processname === processname).length;
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
    statementsText(kpi) {
      const kpiText = kpi.has_kpi_sql ? "own KPI" : "default KPI";
      const alarmText = kpi.has_alarm_sql ? "own alarm" : "default alarm";
      return `${kpiText}, ${alarmText}`;
    },
    filterControls(value, update) {
      update(() => (this.controlFilter = value || ""));
    },
    // The control it differs from only in case is the likely owner.
    startAssign(kpi) {
      this.assignTarget = kpi.case_match || null;
      this.controlFilter = "";
    },
    async assign(kpi) {
      const target = this.assignTarget;
      this.assignOpen = { ...this.assignOpen, [this.keyOf(kpi)]: false };
      this.busy = true;
      try {
        await api("reassign-orphan-kpi", { method: "POST", params: { processname: kpi.processname, kpi_type: kpi.kpi_type, control_name: target } });
        this.$q.notify({ type: "positive", message: `KPI ${kpi.kpi_type} was assigned to ${target}.` });
        this.$emit("changed");
      } catch (error) {
        notifyError(`Assigning KPI ${kpi.kpi_type} to ${target} failed.`, error);
      } finally {
        this.busy = false;
      }
    },
    // kpiType null deletes every KPI of the name.
    remove(kpi, kpiType) {
      const rows = kpiType ? [kpi] : this.kpis.filter((item) => item.processname === kpi.processname);
      const stored = rows.reduce((sum, row) => sum + (row.stored_runs || 0), 0);
      const what = kpiType ? `KPI ${kpiType} of ${kpi.processname}` : `the KPIs ${rows.map((row) => row.kpi_type).join(", ")} of ${kpi.processname}`;
      const kept = stored ? `<div class="q-mt-sm">The values stored for ${stored} past run${stored > 1 ? "s" : ""} are kept.</div>` : "";
      this.$q
        .dialog({
          title: kpiType ? "Delete orphaned KPI?" : "Delete orphaned KPIs?",
          message: `<div>${escapeHtml(`Delete ${what} from RACS_KPI_CONFIG?`)}</div>${kept}`,
          html: true,
          ok: { label: "Delete", color: "negative" },
          cancel: { label: "Cancel", flat: true },
          persistent: true,
        })
        .onOk(async () => {
          this.busy = true;
          try {
            await api("delete-orphan-kpis", { method: "DELETE", params: { processname: kpi.processname, kpi_type: kpiType } });
            this.$q.notify({ type: "positive", message: `Deleted ${what}.` });
            this.$emit("changed");
          } catch (error) {
            notifyError(`Deleting ${what} failed.`, error);
          } finally {
            this.busy = false;
          }
        });
    },
  },
};
</script>
