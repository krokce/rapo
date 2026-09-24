<template>
  <q-page class="column no-wrap" :style-fn="fillViewportToBottom">
    <h2 class="row q-gutter-lg q-mb-lg">
      <div v-if="showSkeleton">Controls</div>
      <div v-else>{{ filteredControlCatalogueLen }} Control<span v-if="filteredControlCatalogueLen != 1">s</span></div>
      <div v-if="refreshing && !showSkeleton">
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
        :options="controlTypeOptions"
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
        :options="['Preparation SQL', 'Prerequisite SQL', 'Completion SQL', 'Iterations', 'Case definition', 'Pre-run hook', 'No Post-run hook', 'Email']"
        label="Control attributes">
      </q-select>

      <q-btn flat round color="grey" class="q-mb-md q-pa-sm" icon="fas fa-times-circle" @click="clearFilters">
        <q-tooltip anchor="top left" self="bottom left" :offset="[15, 10]"> Clear filters </q-tooltip>
      </q-btn>
    </div>

    <q-virtual-scroll
      type="table"
      class="list-table catalogue-table"
      :style="{ '--name-column-width': nameColumnWidth + 'px' }"
      :items="sortedControlCatalogue"
      :virtual-scroll-item-size="90"
      :virtual-scroll-sticky-size-start="48"
      :table-colspan="5">
      <template #before>
        <thead>
          <tr class="bg-blue-grey-2">
            <th class="text-center sortable" @click="toggleSort(sort, 'control_type')">
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
            <th class="text-left"></th>
          </tr>
        </thead>
      </template>
      <template #default="{ item: control }">
        <tr :key="control.control_id">
          <td>
            <q-chip clickable :title="controlType(control.control_type).label" @click="filter.type = control.control_type">
              <q-avatar :icon="controlType(control.control_type).icon" :color="controlType(control.control_type).color" text-color="white" />
              {{ control.control_type }}
            </q-chip>
          </td>
          <td class="text-left">
            <div class="text-weight-bold text-grey-9 control-name">
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

          <td class="text-left">
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
                @click="addAttributeFilter('No Post-run hook')">
                No Post-run hook
              </q-chip>

              <q-chip
                clickable
                v-if="control.prerequisite_sql"
                size="sm"
                color="indigo-4"
                text-color="white"
                icon="fas fa-database"
                @click="addAttributeFilter('Prerequisite SQL')">
                Prerequisite SQL
              </q-chip>

              <q-chip
                clickable
                v-if="control.preparation_sql"
                size="sm"
                color="indigo-4"
                text-color="white"
                icon="fas fa-database"
                @click="addAttributeFilter('Preparation SQL')">
                Preparation SQL
              </q-chip>

              <q-chip
                clickable
                v-if="control.completion_sql"
                size="sm"
                color="indigo-4"
                text-color="white"
                icon="fas fa-database"
                @click="addAttributeFilter('Completion SQL')">
                Completion SQL
              </q-chip>

              <q-chip
                clickable
                v-if="sendsEmail(control)"
                size="sm"
                color="indigo-4"
                text-color="white"
                icon="fas fa-envelope"
                @click="addAttributeFilter('Email')">
                Email
              </q-chip>

              <q-chip
                clickable
                v-if="control.need_prerun_hook === 'Y'"
                size="sm"
                color="indigo-4"
                text-color="white"
                icon="fas fa-bolt"
                @click="addAttributeFilter('Pre-run hook')">
                Pre-run hook
              </q-chip>

              <q-chip
                clickable
                v-if="control.case_config"
                size="sm"
                color="indigo-4"
                text-color="white"
                icon="fas fa-tag"
                @click="addAttributeFilter('Case definition')">
                Case definition
              </q-chip>

              <q-chip
                clickable
                v-if="iterationCount(control) > 0"
                size="sm"
                color="indigo-4"
                text-color="white"
                icon="fas fa-history"
                @click="addAttributeFilter('Iterations')">
                +{{ iterationCount(control) }} Iteration{{ iterationCount(control) > 1 ? "s" : "" }}
              </q-chip>

              <q-chip
                v-if="control.source_type_a"
                clickable
                color="green-8"
                text-color="white"
                size="sm"
                icon-right="fas fa-plug fa-rotate-270"
                @click="filter.system = control.source_type_a"
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
                @click="filter.system = control.source_type_b"
                style="align-items: center">
                {{ control.source_type_b }}
              </q-chip>
              
            </div>
          </td>
          <td>
            <div class="row justify-start items-center">
              <schedule-present-box :schedule="control.schedule_config" :period_back="control.period_back" :period_type="control.period_type"></schedule-present-box>
            </div>
          </td>

          <td>
            <q-btn size="sm" color="grey-7" round flat icon="fas fa-ellipsis-v" @click="openRowMenu($event, control)" />
          </td>
        </tr>
      </template>
      <template #after>
        <tbody v-if="showSkeleton">
          <skeleton-rows v-if="!loadError" :columns="['QChip', 'text', 'text', 'QChip', null]" />
          <tr v-else>
            <td colspan="5" class="text-center text-grey-7 q-pa-lg">Controls could not be loaded</td>
          </tr>
        </tbody>
        <tbody v-else-if="!sortedControlCatalogue.length">
          <tr>
            <td colspan="5" class="text-center text-grey-7 q-pa-lg">No controls match the filters</td>
          </tr>
        </tbody>
      </template>
    </q-virtual-scroll>
    <q-menu ref="rowMenu" :target="menuTarget" no-parent-event>
      <q-list v-if="menuRow" dense class="text-no-wrap">
        <run-control-dialog :control_name="menuRow.control_name">
          <q-item dense clickable class="col items-center">
            <q-item-section> Run </q-item-section>
          </q-item>
        </run-control-dialog>
        <q-separator />
        <q-item
          clickable
          :to="{
            name: 'edit-control',
            params: { controlId: menuRow.control_id },
          }">
          <q-item-section> Edit control </q-item-section>
        </q-item>
        <q-item
          clickable
          :to="{
            name: 'edit-control',
            params: { controlId: menuRow.control_id },
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
          :argument="menuRow.control_name">
          <q-item dense clickable>
            <q-item-section> Recreate schema </q-item-section>
          </q-item>
        </confirm-dialog>
        <confirm-dialog
          icon="fas fa-trash-alt"
          text="Do you really want to delete this control?"
          :action="deleteControl"
          :argument="menuRow.control_id">
          <q-item dense clickable>
            <q-item-section> Delete control </q-item-section>
          </q-item>
        </confirm-dialog>
      </q-list>
    </q-menu>
  </q-page>
</template>

<script>
import { mapActions, mapGetters, mapState } from "vuex";
import SchedulePresentBox from "./SchedulePresentBox.vue";
import SkeletonRows from "./SkeletonRows.vue";
import RunControlDialog from "./RunControlDialog.vue";
import ConfirmDialog from "./ConfirmDialog.vue";
import { api, notifyError } from "../api";
import { CONTROL_TYPE_OPTIONS, controlType } from "../constants";
import { liveRefetch } from "../socket";
import { sendsEmail } from "../utils/email";
import { toDateTimeString } from "../utils/format";
import { fillViewportToBottom, textWidth } from "../utils/layout";
import { sortIcon, sortRows, toggleSort } from "../utils/sort";

// Kept alive (App.vue), so it is built once; activated/deactivated start and stop its live refresh.
export default {
  name: "ControlCatalogue",
  components: {
    RunControlDialog,
    ConfirmDialog,
    SchedulePresentBox,
    SkeletonRows,
  },
  data() {
    return {
      controlTypeOptions: CONTROL_TYPE_OPTIONS,
      loaded: false,
      refreshing: false,
      loadError: false,
      // The one row menu of the table, opened at the kebab button of the row it acts on.
      menuTarget: false,
      menuControlId: null,
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
    ...mapActions(["updateControlCatalogue"]),
    controlType,
    toDateTimeString,
    sortIcon,
    toggleSort,
    fillViewportToBottom,
    async refreshControlCatalogue() {
      this.refreshing = true;
      this.loadError = false;
      try {
        await this.updateControlCatalogue();
        this.loaded = true;
      } catch (error) {
        this.loadError = true;
        notifyError("Failed to load controls.", error);
      } finally {
        this.refreshing = false;
      }
    },
    openRowMenu(event, row) {
      this.menuTarget = event.currentTarget;
      this.menuControlId = row.control_id;
      this.$nextTick(() => this.$refs.rowMenu.show());
    },
    async deleteControl(control_id) {
      try {
        await api("delete-control", { method: "DELETE", params: { control_id } });
        await this.updateControlCatalogue();
      } catch (error) {
        notifyError("Control was not deleted.", error);
      }
    },
    async recreateSchema(control_name) {
      try {
        await api("recreate-control-schema", { method: "POST", params: { name: control_name } });
        this.$q.notify({ type: "positive", message: "Result tables of " + control_name + " were recreated." });
      } catch (error) {
        notifyError("Recreating the result tables of " + control_name + " failed.", error);
      }
    },
    addAttributeFilter(attr) {
      if (!this.filter.other_attributes.includes(attr)) {
        this.filter.other_attributes.push(attr);
      }
    },
    iterationCount(control) {
      // A malformed iteration_config must not break rendering of the whole catalogue.
      try {
        return control.iteration_config ? JSON.parse(control.iteration_config).length || 0 : 0;
      } catch (err) {
        return 0;
      }
    },
    sendsEmail,
    clearFilters() {
      this.filter.control_name = null;
      this.filter.type = null;
      this.filter.status = null;
      this.filter.other_attributes = [];
      this.filter.system = null;
      this.sort.key = null;
      this.sort.dir = "asc";
    },
    // Periods back in days, and the scheduled time of day in seconds (first value of lists/steps like "8,15").
    scheduleSortValue(item, key) {
      if (key === "schedule_days") {
        return item.period_back == null ? null : item.period_back * ({ W: 7, M: 30 }[item.period_type] || 1);
      }
      try {
        const schedule = JSON.parse(item.schedule_config);
        const [hour, min, sec] = [schedule.hour, schedule.min, schedule.sec].map((value) => {
          const match = String(value ?? "").match(/\d+/);
          return match ? Number(match[0]) : null;
        });
        return hour != null && min != null ? hour * 3600 + min * 60 + (sec || 0) : null;
      } catch (err) {
        return null;
      }
    },
  },
  computed: {
    ...mapState(["controlCatalogue"]),
    ...mapGetters(["getSearch"]),
    // Skeleton rows only while nothing is known yet; a catalogue already in the store is shown at once.
    showSkeleton() {
      return !this.loaded && !this.controlCatalogue.length;
    },
    // The Name column fits the longest control name (bold 16px, plus padding), within limits.
    nameColumnWidth() {
      const width = textWidth(
        this.controlCatalogue.map((control) => control.control_name),
        "bold 16px Roboto, sans-serif"
      );
      return Math.min(Math.max(width + 36, 200), 360);
    },
    // Looked up by ID, so an open menu follows live updates of its control.
    menuRow() {
      return this.controlCatalogue.find((control) => control.control_id === this.menuControlId) || null;
    },
    sortedControlCatalogue() {
      const key = this.sort.key;
      if (!key) {
        return this.filteredControlCatalogue;
      }
      const valueOf = key.startsWith("schedule_") ? (item) => this.scheduleSortValue(item, key) : (item) => item[key];
      return sortRows(this.filteredControlCatalogue, valueOf, this.sort.dir);
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
            (attr === "Iterations" && this.iterationCount(item) > 0) ||
            (attr === "Case definition" && item.case_config) ||
            (attr === "Pre-run hook" && item.need_prerun_hook === "Y") ||
            (attr === "No Post-run hook" && item.need_postrun_hook !== "Y") ||
            (attr === "Email" && sendsEmail(item))
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
  // Also runs after the first mount.
  activated() {
    this.stopLiveUpdates = liveRefetch("controls:changed", this.updateControlCatalogue);
    this.refreshControlCatalogue();
  },
  deactivated() {
    this.stopLiveUpdates();
  },
};
</script>

<style scoped>
.sortable {
  cursor: pointer;
  user-select: none;
}

/* Fixed columns, so rows swapped in while scrolling don't resize them; Description takes the rest. */
.catalogue-table :deep(table) {
  table-layout: fixed;
  min-width: calc(586px + var(--name-column-width));
}
.catalogue-table th:nth-child(1) { width: 114px; }
.catalogue-table th:nth-child(2) { width: var(--name-column-width); }
.catalogue-table th:nth-child(4) { width: 320px; }
.catalogue-table th:nth-child(5) { width: 62px; }
.catalogue-table td:nth-child(4) { white-space: normal; }
.control-name {
  font-size: 16px;
  white-space: normal;
  overflow-wrap: anywhere;
}
</style>
