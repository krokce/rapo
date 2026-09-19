<template>
  <q-page>
    <h2 class="row q-gutter-lg">
      <div>{{ filteredControlCatalogueLen }} Control<span v-if="filteredControlCatalogueLen != 1">s</span></div>
      <div v-if="controlCatalogue.length === 0">
        <q-avatar size="lg" color="grey-5">
          <q-icon name="fas fa-sync fa-spin" />
        </q-avatar>
      </div>
    </h2>

    <div class="row items-center q-mb-md">
      <q-btn
        class="col-2 q-mb-md q-pa-sm"
        size="lg"
        color="primary"
        icon="fas fa-plus-circle"
        label="New control"
        :to="{ name: 'edit-control', params: { controlId: 'new' } }" />

      <q-select
        v-model="filter.type"
        class="col-2 q-mb-md q-pa-sm"
        clearable
        outlined
        options-dense
        emit-value
        map-options
        :options="[
          { label: 'ANL - Analysis', value: 'ANL' },
          { label: 'REC - Reconciliation', value: 'REC' },
          { label: 'CMP - Comparison', value: 'CMP' },
          { label: 'REP - Reporting', value: 'REP' },
        ]"
        label="Control type">
      </q-select>

      <q-input clearable class="col q-mb-md q-pa-sm" outlined v-model="filter.control_name" label="Control name" maxlength="45" />

      <q-input clearable class="col q-mb-md q-pa-sm" outlined v-model="filter.system" label="System" maxlength="45" />

      <q-select
        v-model="filter.status"
        class="col q-mb-md q-pa-sm"
        clearable
        outlined
        options-dense
        emit-value
        map-options
        :options="[
          { label: 'Active', value: 'Y' },
          { label: 'Inactive', value: 'N' },
        ]"
        label="Scheduler status">
      </q-select>

      <q-select
        v-model="filter.other_attributes"
        class="col-3 q-mb-md q-pa-sm"
        outlined
        options-dense
        emit-value
        map-options
        multiple
        use-chips
        :options="['Preparation SQL', 'Prerequisite SQL', 'Completion SQL', 'Iterations', 'Case definition', 'Pre-run hook', 'No Post-run hook']"
        label="Control attributes">
      </q-select>

      <q-btn flat round color="grey" class="q-mb-md q-pa-sm" icon="fas fa-times-circle" @click="clearFilters">
        <q-tooltip anchor="top left" self="bottom left" :offset="[15, 10]"> Clear filters </q-tooltip>
      </q-btn>
    </div>

    <div>
      <q-markup-table>
        <thead>
          <tr class="bg-blue-grey-2">
            <th class="text-center sortable" style="width: 50px" @click="setSort('control_type')">
              Type
              <q-icon v-if="sort.key === 'control_type'" :name="sort.dir === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'" size="12px" />
            </th>
            <th class="text-left sortable" @click="setSort('control_name')">
              Name
              <q-icon v-if="sort.key === 'control_name'" :name="sort.dir === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'" size="12px" />
            </th>
            <th class="text-left sortable" @click="setSort('control_description')">
              Description
              <q-icon v-if="sort.key === 'control_description'" :name="sort.dir === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'" size="12px" />
            </th>

            <th class="text-left">
              <span class="text-left sortable" @click="setSort('schedule_days')"> Periods back</span> 
              <q-icon v-if="sort.key === 'schedule_days'" :name="sort.dir === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'" size="12px" /> / 
              <span class="text-left sortable" @click="setSort('schedule_time')"> Schedule</span>
              <q-icon v-if="sort.key === 'schedule_time'" :name="sort.dir === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'" size="12px" />
            </th>
            <th class="text-left"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="control in sortedControlCatalogue" :key="control.control_id">
            <td>
              <q-chip
                size="12px"
                text-color="white"
                clickable
                :class="{
                  'bg-pink-8': control.control_type === 'ANL',
                  'bg-teal-8': control.control_type === 'REC',
                  'bg-lime-8': control.control_type === 'CMP',
                  'bg-indigo-6': control.control_type === 'REP',
                }"
                class="text-weight-bold"
                @click="this.filter.type = control.control_type">
                {{ control.control_type }}
              </q-chip>
            </td>
            <td class="text-left" style="width: 300px">
              <div class="text-weight-bold text-grey-9" style="font-size: 16px">
                {{ control.control_name }}
              </div>
              <router-link
                :to="{
                  name: 'edit-control',
                  params: { controlId: control.control_id },
                }"
                style="text-decoration: none">
                <div>
                  <small class="text-indigo-4"> v.{{ toDateTimeString(control.updated_date) }} </small>
                </div>
              </router-link>
            </td>

            <td class="text-left" style="width: 100%">
              <div style="white-space: normal; word-wrap: break-word">
                {{ control.control_description }}
              </div>

              <div class="row justify-start items-center">
                <q-chip v-if="control.status !== 'Y'" clickable size="sm" color="red-4" text-color="white" icon="fas fa-clock" @click="filter.status = 'N'">
                  Scheduler inactive
                </q-chip>

                <q-chip
                  clickable
                  v-if="control.need_postrun_hook != 'Y'"
                  size="sm"
                  color="red-4"
                  text-color="white"
                  icon="fas fa-bolt"
                  @click="this.filter.other_attributes.push('No Post-run hook')">
                  No Post-run hook
                </q-chip>

                <q-chip
                  clickable
                  v-if="control.prerequisite_sql"
                  size="sm"
                  color="indigo-4"
                  text-color="white"
                  icon="fas fa-database"
                  @click="this.filter.other_attributes.push('Prerequisite SQL')">
                  Prerequisite SQL
                </q-chip>

                <q-chip
                  clickable
                  v-if="control.preparation_sql"
                  size="sm"
                  color="indigo-4"
                  text-color="white"
                  icon="fas fa-database"
                  @click="this.filter.other_attributes.push('Preparation SQL')">
                  Preparation SQL
                </q-chip>

                <q-chip
                  clickable
                  v-if="control.completion_sql"
                  size="sm"
                  color="indigo-4"
                  text-color="white"
                  icon="fas fa-database"
                  @click="this.filter.other_attributes.push('Completion SQL')">
                  Completion SQL
                </q-chip>

                <q-chip
                  clickable
                  v-if="control.need_prerun_hook === 'Y'"
                  size="sm"
                  color="indigo-4"
                  text-color="white"
                  icon="fas fa-bolt"
                  @click="this.filter.other_attributes.push('Pre-run hook')">
                  Pre-run hook
                </q-chip>

                <q-chip
                  clickable
                  v-if="control.case_config"
                  size="sm"
                  color="indigo-4"
                  text-color="white"
                  icon="fas fa-tag"
                  @click="this.filter.other_attributes.push('Case definition')">
                  Case definition
                </q-chip>

                <q-chip
                  clickable
                  v-if="control.iteration_config && JSON.parse(control.iteration_config).length > 0"
                  size="sm"
                  color="indigo-4"
                  text-color="white"
                  icon="fas fa-history"
                  @click="this.filter.other_attributes.push('Iterations')">
                  +{{ JSON.parse(control.iteration_config).length }} Iteration{{ JSON.parse(control.iteration_config).length > 1 ? "s" : "" }}
                </q-chip>

                <q-chip
                  v-if="control.source_type_a"
                  clickable
                  color="green-8"
                  text-color="white"
                  size="sm"
                  icon-right="fas fa-plug fa-rotate-270"
                  @click="this.filter.system = control.source_type_a"
                  style="align-items: center">
                  {{ control.source_type_a }}
                </q-chip>
                <q-icon v-if="control.source_type_a && control.source_type_b" name="fas fa-wave-square" size="9px" color="green-8" />
                <q-chip
                  v-if="control.source_type_b"
                  clickable
                  color="green-8"
                  text-color="white"
                  size="sm"
                  icon="fas fa-plug fa-rotate-90"
                  @click="this.filter.system = control.source_type_b"
                  style="align-items: center">
                  {{ control.source_type_b }}
                </q-chip>
                
              </div>
            </td>
            <td style="width: 100px">
              <div class="row justify-start items-center">
                <schedule-present-box :schedule="control.schedule_config" :period_back="control.period_back" :period_type="control.period_type"></schedule-present-box>
              </div>
            </td>

            <td>
              <q-btn size="sm" color="grey-7" round flat icon="fas fa-ellipsis-v">
                <q-menu>
                  <q-list dense class="text-no-wrap">
                    <run-control-dialog :control_name="control.control_name">
                      <q-item dense clickable class="col items-center">
                        <q-item-section> Run </q-item-section>
                      </q-item>
                    </run-control-dialog>
                    <q-separator />
                    <q-item
                      clickable
                      :to="{
                        name: 'edit-control',
                        params: { controlId: control.control_id },
                      }">
                      <q-item-section> Edit control </q-item-section>
                    </q-item>
                    <q-item
                      clickable
                      :to="{
                        name: 'edit-control',
                        params: { controlId: control.control_id },
                        query: { clone: true },
                      }"
                      v-close-popup>
                      <q-item-section> Clone control</q-item-section>
                    </q-item>
                    <q-separator />
                    <confirm-dialog
                      icon="fas fa-trash-alt"
                      text="Recreate result tables? Past discrepancies will be deleted!"
                      :action="recreateSchema"
                      :argument="control.control_name">
                      <q-item dense clickable>
                        <q-item-section> Recreate schema </q-item-section>
                      </q-item>
                    </confirm-dialog>
                    <confirm-dialog
                      icon="fas fa-trash-alt"
                      text="Do you really want to delete this control?"
                      :action="deleteControl"
                      :argument="control.control_id">
                      <q-item dense clickable>
                        <q-item-section> Delete control </q-item-section>
                      </q-item>
                    </confirm-dialog>
                  </q-list>
                </q-menu>
              </q-btn>
            </td>
          </tr>
        </tbody>
      </q-markup-table>
    </div>
  </q-page>
</template>

<script>
import { mapActions, mapGetters } from "vuex";
import SchedulePresentBox from "./SchedulePresentBox.vue";
import RunControlDialog from "./RunControlDialog.vue";
import ConfirmDialog from "./ConfirmDialog.vue";
import { useQuasar } from "quasar";

export default {
  components: {
    RunControlDialog,
    ConfirmDialog,
    SchedulePresentBox,
  },
  data() {
    return {
      isHovered: false,
      confirmDialog: false,
      $q: useQuasar(),
      controlCatalogue: [],
      filter: {
        control_name: "",
        type: null,
        status: null,
        other_attributes: [],
        system: null,
      },
      sort: {
        key: null,
        dir: "asc",
      },
    };
  },
  methods: {
    ...mapActions(["updateControlCatalogue", "updateSearch"]),
    async deleteControl(control_id) {
      this.$q.loadingBar.start();

      const response = await fetch("/api/delete-control?control_id=" + control_id, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${this.$store.getters.getToken}`, "Content-Type": "application/json" },
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      this.controlCatalogue = await this.updateControlCatalogue();
      this.$q.loadingBar.stop();
      this.$router.push({ name: "controls" });
    },
    recreateSchema(control_name) {
      this.$q.loadingBar.start();

      fetch("/api/delete-control-output-tables?name=" + control_name, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${this.$store.getters.getToken}`, "Content-Type": "application/json" },
      })
        .then((response) => {
          if (response.ok) {
            this.$q.notify({ type: "positive", message: "Schema for " + control_name + " was deleted. It will be recreated on the next run." });
          } else {
            this.$q.notify({ type: "negative", message: "Schema deletion for " + control_name + "' failed" });
          }
        })
        .then(() => {
          this.$q.loadingBar.stop();
        });
    },
    toDateTimeString(val) {
      var ret = new Date(val).toISOString("de-DE").substring(0, 19).replace("T", " ");
      return ret;
    },
    clearFilters() {
      this.filter.control_name = null;
      this.filter.type = null;
      this.filter.status = null;
      this.filter.other_attributes = [];
      this.filter.system = null;
      this.sort.key = null;
      this.sort.dir = "asc";
      // this.updateSearch("");
    },
    setSort(key) {
      if (this.sort.key === key) {
        this.sort.dir = this.sort.dir === "asc" ? "desc" : "asc";
        return;
      }
      this.sort.key = key;
      this.sort.dir = "asc";
    },
    parseScheduleNumber(val) {
      if (val == null) return null;
      if (Array.isArray(val)) {
        return this.parseScheduleNumber(val[0]);
      }
      if (typeof val === "number") {
        return Number.isFinite(val) ? val : null;
      }
      const match = String(val).match(/-?\d+/);
      return match ? Number(match[0]) : null;
    },
    getScheduleSortValues(item) {
      const periodBack = item.period_back ?? null;
      const periodType = item.period_type ?? null;
      let periodBackDays = null;
      if (periodBack != null) {
        const multiplier = periodType === "W" ? 7 : periodType === "M" ? 30 : 1;
        periodBackDays = periodBack * multiplier;
      }
      if (!item.schedule_config) {
        return { periodBack, periodBackDays, minutes: null };
      }
      try {
        const schedule = JSON.parse(item.schedule_config);
        const hour = this.parseScheduleNumber(schedule?.hour);
        const min = this.parseScheduleNumber(schedule?.min);
        const sec = this.parseScheduleNumber(schedule?.sec);
        const seconds =
          hour != null && min != null && sec != null
            ? hour * 3600 + min * 60 + sec
            : hour != null && min != null
            ? hour * 3600 + min * 60
            : null;
        return { periodBack, periodBackDays, minutes: seconds };
      } catch (err) {
        return { periodBack, periodBackDays, minutes: null };
      }
    },
    getSortValue(item) {
      if (this.sort.key === "schedule_days") {
        return this.getScheduleSortValues(item).periodBackDays;
      }
      if (this.sort.key === "schedule_time") {
        return this.getScheduleSortValues(item).minutes;
      }
      return item[this.sort.key] ?? "";
    },
  },
  computed: {
    ...mapGetters(["getSearch"]),
    sortedControlCatalogue() {
      if (!this.sort.key) {
        return this.filteredControlCatalogue;
      }
      const dir = this.sort.dir === "asc" ? 1 : -1;
      return [...this.filteredControlCatalogue].sort((a, b) => {
        if (this.sort.key === "schedule_days") {
          const aVal = this.getSortValue(a);
          const bVal = this.getSortValue(b);

          if (aVal === bVal) return 0;
          if (aVal == null) return 1 * dir;
          if (bVal == null) return -1 * dir;

          return (aVal - bVal) * dir;
        }

        if (this.sort.key === "schedule_time") {
          const aSchedule = this.getScheduleSortValues(a);
          const bSchedule = this.getScheduleSortValues(b);

          if (aSchedule.minutes === bSchedule.minutes) return 0;
          if (aSchedule.minutes == null) return 1 * dir;
          if (bSchedule.minutes == null) return -1 * dir;
          return (aSchedule.minutes - bSchedule.minutes) * dir;
        }

        const aVal = this.getSortValue(a);
        const bVal = this.getSortValue(b);

        if (aVal === bVal) return 0;
        if (aVal == null) return 1 * dir;
        if (bVal == null) return -1 * dir;

        if (typeof aVal === "number" && typeof bVal === "number") {
          return (aVal - bVal) * dir;
        }
        return String(aVal).localeCompare(String(bVal)) * dir;
      });
    },
    filteredControlCatalogue() {
      const s = this.getSearch;
      var data = this.controlCatalogue;
      if (s || this.filter.control_name || this.filter.type || this.filter.status || this.filter.system || (this.filter.other_attributes && this.filter.other_attributes.length > 0)) {
        data = this.controlCatalogue.filter((item) => {
          const matchesSearch = s ? item.control_name?.toUpperCase().includes(s.toUpperCase()) : true;
          const matchesControlName = this.filter.control_name ? item.control_name?.toUpperCase().includes(this.filter.control_name.toUpperCase()) : true;
          const matchesType = this.filter.type ? item.control_type === this.filter.type : true;
          const matchesStatus = this.filter.status ? item.status === this.filter.status : true;
          const matchesSystem = this.filter.system
        ? item.source_type_a?.toUpperCase().includes(this.filter.system.toUpperCase()) ||
          item.source_type_b?.toUpperCase().includes(this.filter.system.toUpperCase())
        : true;
          const matchesAttributes =
        this.filter.other_attributes && this.filter.other_attributes.length > 0
          ? this.filter.other_attributes.some((attr) => {
          return (
            (attr === "Preparation SQL" && item.preparation_sql) ||
            (attr === "Prerequisite SQL" && item.prerequisite_sql) ||
            (attr === "Completion SQL" && item.completion_sql) ||
            (attr === "Iterations" && item.iteration_config && JSON.parse(item.iteration_config).length > 0) ||
            (attr === "Case definition" && item.case_config) ||
            (attr === "Pre-run hook" && item.need_prerun_hook === "Y") ||
            (attr === "No Post-run hook" && item.need_postrun_hook !== "Y")
          );
            })
          : true;

          return matchesSearch && matchesControlName && matchesType && matchesStatus && matchesSystem && matchesAttributes;
        });
      }

      return data;
    },
    filteredControlCatalogueLen() {
      return this.filteredControlCatalogue.length;
    },
  },
  async mounted() {
    this.controlCatalogue = await this.updateControlCatalogue();
  },
};
</script>

<style scoped>
.sortable {
  cursor: pointer;
  user-select: none;
}
</style>
