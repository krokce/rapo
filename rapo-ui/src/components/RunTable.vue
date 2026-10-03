<template>
  <div class="run-table column no-wrap">
    <q-virtual-scroll
      type="table"
      dense
      class="list-table runs-table"
      :class="{ 'with-name': columns.name }"
      :style="{ '--name-column-width': nameColumnWidth + 'px' }"
      :items="sortedRuns"
      :virtual-scroll-item-size="45"
      :virtual-scroll-sticky-size-start="28"
      :table-colspan="colspan">
      <template #before>
        <thead>
          <tr class="bg-blue-grey-2">
            <th v-if="columns.type" :title="filterable ? 'The control type: ANL analysis, REC reconciliation, CMP comparison, REP report; click a type to filter by it' : 'The control type: ANL analysis, REC reconciliation, CMP comparison, REP report'" class="col-type text-left sortable" @click="toggleSort(sort, 'control_type')" v-keyboard :aria-sort="ariaSort(sort, 'control_type')">
              Type
              <q-icon v-if="sort.key === 'control_type'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th title="When the run started, and what started it: hover its icon" class="col-start text-left sortable" @click="toggleSort(sort, 'start_date')" v-keyboard :aria-sort="ariaSort(sort, 'start_date')">
              Start
              <q-icon v-if="sort.key === 'start_date'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th title="How long the run took, in minutes" class="col-runtime text-right sortable" @click="toggleSort(sort, 'duration_minutes')" v-keyboard :aria-sort="ariaSort(sort, 'duration_minutes')">
              Runtime
              <q-icon v-if="sort.key === 'duration_minutes'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th title="The process ID of the run" class="col-pid text-center sortable" @click="toggleSort(sort, 'process_id')" v-keyboard :aria-sort="ariaSort(sort, 'process_id')">
              PID
              <q-icon v-if="sort.key === 'process_id'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th v-if="columns.name" :title="filterable ? 'The control the run belongs to: its name opens the control, the magnifier filters by it (again: clears the filter)' : 'The control the run belongs to: its name opens the control'" class="col-name text-left sortable" @click="toggleSort(sort, 'control_name')" v-keyboard :aria-sort="ariaSort(sort, 'control_name')">
              Processname
              <q-icon v-if="sort.key === 'control_name'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th title="The start of the data window the run read" class="col-date text-left sortable" @click="toggleSort(sort, 'date_from')" v-keyboard :aria-sort="ariaSort(sort, 'date_from')">
              Run from
              <q-icon v-if="sort.key === 'date_from'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th title="The end of the data window the run read" class="col-date text-left sortable" @click="toggleSort(sort, 'date_to')" v-keyboard :aria-sort="ariaSort(sort, 'date_to')">
              Run to
              <q-icon v-if="sort.key === 'date_to'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th title="Records fetched from datasource A; click the number for its SQL or data analysis" class="col-fetched text-right sortable" @click="toggleSort(sort, 'fetched_number_a')" v-keyboard :aria-sort="ariaSort(sort, 'fetched_number_a')">
              Fetched A
              <q-icon v-if="sort.key === 'fetched_number_a'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th title="Records fetched from datasource B; click the number for its SQL or data analysis" class="col-fetched text-right sortable" @click="toggleSort(sort, 'fetched_number_b')" v-keyboard :aria-sort="ariaSort(sort, 'fetched_number_b')">
              Fetched B
              <q-icon v-if="sort.key === 'fetched_number_b'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th title="Discrepancies found on side A (the result rows of ANL, CMP and REP); click the number for its SQL or data analysis" class="col-discr text-right sortable" @click="toggleSort(sort, 'error_number_a')" v-keyboard :aria-sort="ariaSort(sort, 'error_number_a')">
              Discr. A
              <q-icon v-if="sort.key === 'error_number_a'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th title="Discrepancies found on side B; click the number for its SQL or data analysis" class="col-discr text-right sortable" @click="toggleSort(sort, 'error_number_b')" v-keyboard :aria-sort="ariaSort(sort, 'error_number_b')">
              Discr. B
              <q-icon v-if="sort.key === 'error_number_b'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th title="Discrepancies of side A as a percentage of the records fetched from A" class="col-level text-right sortable" @click="toggleSort(sort, 'error_level_a')" v-keyboard :aria-sort="ariaSort(sort, 'error_level_a')">
              Err. lvl A [%]
              <q-icon v-if="sort.key === 'error_level_a'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th title="Discrepancies of side B as a percentage of the records fetched from B" class="col-level text-right sortable" @click="toggleSort(sort, 'error_level_b')" v-keyboard :aria-sort="ariaSort(sort, 'error_level_b')">
              Err. lvl B [%]
              <q-icon v-if="sort.key === 'error_level_b'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th title="Prerequisite value: what the Prerequisite SQL returned; 0 stops the run" class="col-pv text-right sortable" @click="toggleSort(sort, 'prerequisite_value')" v-keyboard :aria-sort="ariaSort(sort, 'prerequisite_value')">
              PV
              <q-icon v-if="sort.key === 'prerequisite_value'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th :title="filterable ? 'The status of the run; click a status to filter by it' : 'The status of the run'" class="col-status text-left sortable" @click="toggleSort(sort, 'status')" v-keyboard :aria-sort="ariaSort(sort, 'status')">
              Status
              <q-icon v-if="sort.key === 'status'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="col-menu text-left"></th>
          </tr>
        </thead>
      </template>
      <template #default="{ item: run, index }">
        <tr :key="run.process_id" :class="{ 'new-day-separator': separatorRows && startsNewDay(sortedRuns, index) }">
          <td v-if="columns.type" class="text-center">
            <q-chip :clickable="filterable" :title="controlType(run.control_type).label" @click="filterable && $emit('filter', { type: run.control_type })">
              <q-avatar :icon="controlType(run.control_type).icon" :color="controlType(run.control_type).color" text-color="white" />
              {{ run.control_type }}
            </q-chip>
          </td>
          <td class="text-left">
            <div class="text-blue-grey-7 no-wrap row items-center">
              <strong>{{ toDateString(run.start_date) }}</strong>
              <small class="text-grey-7 q-px-sm">{{ toTimeString(run.start_date) }}</small>
              <q-icon :name="triggerOf(run).icon" size="11px" :class="run.trigger_type ? 'text-blue-grey-4' : 'text-grey-4'" :title="triggerTitle(run)" />
            </div>
          </td>
          <td class="text-right number-cell">{{ round(run.duration_minutes, 1) }} min</td>
          <td class="text-center text-weight-bold text-blue-grey-7 number-cell">{{ run.process_id }}</td>
          <td v-if="columns.name" class="text-left text-weight-bold text-teal-8 ellipsis" :title="run.control_name">
            <q-btn
              v-if="filterable"
              :aria-label="isFilteredName(run) ? 'Clear the filter by this control' : 'Filter by this control'"
              :aria-pressed="isFilteredName(run)"
              size="7px"
              :color="isFilteredName(run) ? 'teal-8' : 'grey-5'"
              round
              flat
              icon="fas fa-search"
              @click.stop="$emit('filter', { control_name: run.control_name })" />
            <router-link :to="{ name: 'edit-control', params: { controlId: run.control_id } }">
              <span class="col cursor-pointer" style="font-size: 13px" :class="'text-' + controlTypeColor(run.control_type)">
                {{ run.control_name }}
              </span>
            </router-link>
          </td>
          <td class="text-left text-weight-bold text-blue-grey-7">
            {{ toDateString(run.date_from) }}
          </td>
          <td class="text-left text-weight-bold text-blue-grey-7">
            {{ toDateString(run.date_to) }}
          </td>
          <td class="text-right number-cell">
            <span v-if="run.fetched_number_a > 0" class="cursor-pointer number-link" v-keyboard:button @click="openNumberMenu($event, run, 'fetched_a')" @contextmenu.prevent="openNumberMenu($event, run, 'fetched_a')">
              {{ formatNumber(run.fetched_number_a) }}
            </span>
            <span v-else>{{ formatNumber(run.fetched_number_a) }}</span>
          </td>
          <td class="text-right number-cell">
            <span v-if="run.fetched_number_b > 0" class="cursor-pointer number-link" v-keyboard:button @click="openNumberMenu($event, run, 'fetched_b')" @contextmenu.prevent="openNumberMenu($event, run, 'fetched_b')">
              {{ formatNumber(run.fetched_number_b) }}
            </span>
            <span v-else>{{ formatNumber(run.fetched_number_b) }}</span>
          </td>
          <td class="text-right number-cell">
            <span v-if="run.error_number_a > 0" class="cursor-pointer text-red" v-keyboard:button @click="openNumberMenu($event, run, 'result_a')" @contextmenu.prevent="openNumberMenu($event, run, 'result_a')">
              {{ formatNumber(run.error_number_a) }}
            </span>
            <span v-else>{{ formatNumber(run.error_number_a) }}</span>
          </td>
          <td class="text-right number-cell">
            <span v-if="run.error_number_b > 0" class="cursor-pointer text-red" v-keyboard:button @click="openNumberMenu($event, run, 'result_b')" @contextmenu.prevent="openNumberMenu($event, run, 'result_b')">
              {{ formatNumber(run.error_number_b) }}
            </span>
            <span v-else>{{ formatNumber(run.error_number_b) }}</span>
          </td>
          <td class="text-right number-cell">
            <span v-if="run.error_level_a > 0" class="cursor-pointer text-red" v-keyboard:button @click="openNumberMenu($event, run, 'result_a')" @contextmenu.prevent="openNumberMenu($event, run, 'result_a')">
              {{ formatNumber(run.error_level_a, 2) }}%
            </span>
            <span v-else> {{ formatNumber(run.error_level_a, 2) }}% </span>
          </td>
          <td class="text-right number-cell">
            <span v-if="run.error_level_b > 0" class="cursor-pointer text-red" v-keyboard:button @click="openNumberMenu($event, run, 'result_b')" @contextmenu.prevent="openNumberMenu($event, run, 'result_b')">
              {{ formatNumber(run.error_level_b, 2) }}%
            </span>
            <span v-else> {{ formatNumber(run.error_level_b, 2) }}% </span>
          </td>
          <td class="text-right">
            <q-icon v-if="run.prerequisite_value == 0" class="cursor-pointer text-red" name="fas fa-stop" title="Prerequisite SQL value is 0" />
            <q-icon v-if="run.prerequisite_value" class="cursor-pointer text-green" name="fas fa-play" :title="`Prerequisite SQL value is ${run.prerequisite_value}`" />
          </td>
          <td class="text-left text-no-wrap">
            <q-chip :clickable="filterable" :class="{ 'cursor-pointer': filterable }" @click="filterable && $emit('filter', { status: run.status })">
              <q-avatar :icon="runStatus(run.status).icon" :color="runStatus(run.status).color" text-color="white" />
              {{ runStatus(run.status).label }}
            </q-chip>
            <q-icon
              v-if="run.has_warning"
              class="cursor-pointer"
              name="fas fa-exclamation-triangle"
              color="amber-9"
              size="16px"
              title="Finished with warnings: click for the run details"
              @click="$refs.runLogDialog.open(run)" />
          </td>
          <td class="text-left">
            <q-btn aria-label="Row actions" size="sm" color="grey-7" round flat icon="fas fa-ellipsis-v" @click="openRowMenu($event, run)" />
          </td>
        </tr>
      </template>
      <template #after>
        <tbody v-if="loading || error">
          <skeleton-rows v-if="!error" :columns="skeletonColumns" />
          <tr v-else>
            <td :colspan="colspan" class="text-center text-grey-7 q-pa-lg">Runs could not be loaded</td>
          </tr>
        </tbody>
        <tbody v-else-if="!sortedRuns.length">
          <tr>
            <td :colspan="colspan" class="text-center text-grey-7 q-pa-lg">
              <slot name="empty">{{ emptyText }}</slot>
            </td>
          </tr>
        </tbody>
      </template>
    </q-virtual-scroll>
    <run-dataset-menu ref="numberMenu" />
    <run-log-dialog ref="runLogDialog" />
    <q-menu ref="rowMenu" :target="menuTarget" no-parent-event>
      <q-list v-if="menuRow" dense class="text-no-wrap">
        <q-item dense clickable :disable="!!runDisabled" @click="reRun(menuRow, refresh)" v-close-popup>
          <q-item-section> Re-run </q-item-section>
          <q-tooltip v-if="runDisabled">{{ runDisabled }}</q-tooltip>
        </q-item>
        <run-control-dialog v-if="!runDisabled" :control_name="menuRow.control_name" :hook="refresh">
          <q-item dense clickable class="col items-center">
            <q-item-section> Run </q-item-section>
          </q-item>
        </run-control-dialog>
        <q-item v-else dense disable>
          <q-item-section> Run </q-item-section>
          <q-tooltip>{{ runDisabled }}</q-tooltip>
        </q-item>
        <template v-if="editLink">
          <q-separator />
          <q-item dense clickable :to="{ name: 'edit-control', params: { controlId: menuRow.control_id } }">
            <q-item-section> Edit control </q-item-section>
          </q-item>
        </template>
        <q-separator />
        <q-item v-if="menuRow.status != 'X'" dense clickable class="col items-center" @click="revokeRun(menuRow, refresh)" v-close-popup>
          <q-item-section> Revoke run </q-item-section>
        </q-item>
        <q-item v-if="activeRunStatuses.includes(menuRow.status)" dense clickable class="col items-center" @click="cancelRun(menuRow, refresh)" v-close-popup>
          <q-item-section> Cancel run </q-item-section>
        </q-item>
        <q-item dense clickable class="col items-center" @click="$refs.runLogDialog.open(menuRow)" v-close-popup>
          <q-item-section> Show full log </q-item-section>
        </q-item>
        <q-item v-if="hasKpis && hasKpis(menuRow)" dense clickable class="col items-center" @click="$emit('calculate-kpis', menuRow)" v-close-popup>
          <q-item-section> Calculate KPIs </q-item-section>
        </q-item>
        <q-item v-if="menuRow.status == 'D' && menuRowSendsEmail" dense clickable class="col items-center" @click="sendEmail(menuRow)" v-close-popup>
          <q-item-section> Send email </q-item-section>
        </q-item>
      </q-list>
    </q-menu>
  </div>
</template>

<script>
import { mapGetters } from "vuex";
import RunControlDialog from "./RunControlDialog.vue";
import RunDatasetMenu from "./RunDatasetMenu.vue";
import RunLogDialog from "./RunLogDialog.vue";
import SkeletonRows from "./SkeletonRows.vue";
import { ACTIVE_RUN_STATUSES, controlType, controlTypeColor, runStatus } from "../constants";
import { cancelRun, reRun, revokeRun, sendEmail } from "../runActions";
import { EMAIL_CONTROL_TYPES, sendsEmail } from "../utils/email";
import { formatNumber, round, toDateString, toTimeString } from "../utils/format";
import { textWidth } from "../utils/layout";
import { runSortValue, startsNewDay, triggerOf, triggerTitle } from "../utils/runs";
import { ariaSort, sortIcon, sortRows, toggleSort } from "../utils/sort";

// A table of runs (get-control-runs rows), shared by the Results page and the editor's Run log: sortable columns,
// the trigger icon, the number menus (RunDatasetMenu), one row menu for the whole table and the full log dialog.
// A virtual scroll: the parent sizes it, and the table scrolls inside with its header kept in view.
export default {
  components: { RunControlDialog, RunDatasetMenu, RunLogDialog, SkeletonRows },
  props: {
    runs: { type: Array, required: true },
    // { key, dir }, changed in place by the headers.
    sort: { type: Object, required: true },
    // Optional columns: the type and the control's name.
    columns: { type: Object, default: () => ({ type: true, name: true }) },
    // The row menu's Edit control (not inside the editor itself).
    editLink: { type: Boolean, default: true },
    // Type and status chips and the name's magnifier emit filter ({ type } / { status } / { control_name }).
    filterable: { type: Boolean, default: false },
    // A day separator line while the runs are sorted by time.
    separators: { type: Boolean, default: false },
    // Why Re-run and Run are not offered now (e.g. unsaved changes), or null.
    runDisabled: { type: String, default: null },
    // Called after a run action changed a run.
    refresh: { type: Function, default: () => {} },
    loading: { type: Boolean, default: false },
    error: { type: Boolean, default: false },
    emptyText: { type: String, default: "No runs" },
    // The control name filtered by, whose magnifiers are highlighted (a click clears it), or null.
    filteredName: { type: String, default: null },
    // Whether a run's control has KPIs; the row menu's Calculate KPIs emits calculate-kpis (run).
    hasKpis: { type: Function, default: null },
  },
  emits: ["filter", "calculate-kpis"],
  data() {
    return {
      activeRunStatuses: ACTIVE_RUN_STATUSES,
      // The one row menu of the table, opened at the kebab button of the row it acts on.
      menuTarget: false,
      menuProcessId: null,
    };
  },
  computed: {
    ...mapGetters(["controlCatalogueById"]),
    sortedRuns() {
      return sortRows(this.runs, (run) => runSortValue(run, this.sort.key), this.sort.dir);
    },
    separatorRows() {
      return this.separators && ["start_date", "process_id"].includes(this.sort.key);
    },
    colspan() {
      return 14 + ["type", "name"].filter((column) => this.columns[column]).length;
    },
    skeletonColumns() {
      return [
        ...(this.columns.type ? ["QChip"] : []),
        "text",
        "text",
        "text",
        ...(this.columns.name ? ["text"] : []),
        ...Array(8).fill("text"),
        null,
        "QChip",
        null,
      ];
    },
    // The Processname column fits the longest name (bold 13px, plus the search button and padding).
    nameColumnWidth() {
      return this.columns.name ? Math.min(textWidth(this.runs.map((row) => row.control_name), "bold 13px Roboto, sans-serif") + 40, 400) : 0;
    },
    // Looked up by PID, so an open menu follows live updates of its run.
    menuRow() {
      return this.runs.find((row) => row.process_id === this.menuProcessId) || null;
    },
    // The email configuration is in the catalogue. Until it is loaded, every type that can send one is offered.
    menuRowSendsEmail() {
      const control = this.menuRow && this.controlCatalogueById(this.menuRow.control_id);
      return control ? sendsEmail(control) : Boolean(this.menuRow) && EMAIL_CONTROL_TYPES.includes(this.menuRow.control_type);
    },
  },
  methods: {
    isFilteredName(run) {
      return Boolean(this.filteredName) && (run.control_name || "").toUpperCase() === this.filteredName.toUpperCase();
    },
    ariaSort,
    cancelRun,
    controlType,
    controlTypeColor,
    formatNumber,
    reRun,
    revokeRun,
    round,
    runStatus,
    sendEmail,
    sortIcon,
    startsNewDay,
    toDateString,
    toTimeString,
    toggleSort,
    triggerOf,
    triggerTitle,
    openNumberMenu(event, row, dataset) {
      this.$refs.numberMenu.open(event, row, dataset);
    },
    openRowMenu(event, row) {
      this.menuTarget = event.currentTarget;
      this.menuProcessId = row.process_id;
      this.$nextTick(() => this.$refs.rowMenu.show());
    },
  },
};
</script>

<style lang="css" scoped>
.run-table {
  flex: 0 1 auto;
  min-height: 0;
}

/* Override the default link styles */
a {
  color: var(--rapo-teal);
  text-decoration: none;
}
a:hover {
  text-decoration: underline;
}
a:visited {
  color: var(--rapo-teal);
}
.number-link:hover {
  color: var(--rapo-teal);
  text-decoration: underline;
}

/* Fixed columns, so rows swapped in while scrolling don't resize them. With Processname (Results) it takes the
   rest, but at least the width of the longest name (nameColumnWidth), else the table scrolls sideways; the Start
   column's trigger icon (18px) is taken from it, as min-width leaves it out. Without it the Status column takes the
   rest. */
.runs-table :deep(table) {
  table-layout: fixed;
  min-width: 1290px;
}
.runs-table.with-name :deep(table) {
  min-width: calc(1290px + var(--name-column-width));
}
.runs-table .col-type { width: 114px; }
.runs-table .col-start { width: 162px; }
.runs-table .col-runtime { width: 66px; }
.runs-table .col-pid { width: 92px; }
.runs-table .col-date { width: 87px; }
.runs-table .col-fetched { width: 92px; }
.runs-table .col-discr { width: 84px; }
.runs-table .col-level { width: 80px; }
.runs-table .col-pv { width: 34px; }
.runs-table.with-name .col-status { width: 128px; }
.runs-table .col-menu { width: 50px; }
</style>
