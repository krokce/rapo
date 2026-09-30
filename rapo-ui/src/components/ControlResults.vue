<template>
  <q-page class="column no-wrap" :style-fn="fillViewportToBottom">
    <div class="row items-end" :class="activeFilters.length ? 'q-mb-sm' : 'q-mb-lg'">
      <h2 class="row title-baseline items-center no-wrap text-no-wrap q-gutter-lg q-mb-none">
        <div>Control results</div>
        <div class="text-grey-7 page-subject">{{ dayTitle }}</div>
        <div v-if="refreshing && hasDay">
          <q-avatar size="lg" color="grey-5">
            <q-icon name="fas fa-sync fa-spin" />
          </q-avatar>
        </div>
      </h2>
      <q-space />

      <!-- The day's totals, whatever the filters: chips above (each filters by itself), the counts below, as on Files. -->
      <div v-if="hasDay" class="column items-end text-blue-grey-8">
        <div v-if="summary.types.length || summary.statuses.length || summary.warnings" class="row items-center justify-end">
          <q-chip v-for="item in summary.types" :key="item.key" clickable @click="filter.type = item.key">
            <q-avatar :icon="controlType(item.key).icon" :color="controlType(item.key).color" text-color="white" />
            <span class="text-weight-bold q-mr-xs">{{ item.key }}</span>({{ item.count }})
            <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">{{ controlType(item.key).label }}</q-tooltip>
          </q-chip>
          <q-chip v-for="item in summary.statuses" :key="String(item.key)" clickable @click="addStatusFilter(item.key)">
            <q-avatar :icon="runStatus(item.key).icon" :color="runStatus(item.key).color" text-color="white" />
            <span class="text-weight-bold q-mr-xs">{{ runStatus(item.key).label }}</span>({{ item.count }})
          </q-chip>
          <q-chip v-if="summary.warnings" clickable @click="filter.warnings = true">
            <q-avatar icon="fas fa-exclamation-triangle" color="amber-9" text-color="white" />
            <span class="text-weight-bold q-mr-xs">Warnings</span>({{ summary.warnings }})
            <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">Runs flagged with a warning about their results</q-tooltip>
          </q-chip>
        </div>
        <div class="q-mr-xs">
          {{ summary.controls }} {{ summary.controls === 1 ? "control" : "controls" }} &middot; {{ summary.runs }}
          {{ summary.runs === 1 ? "run" : "runs" }}
          <span v-if="summary.failing.length" class="text-red-6">
            &middot; {{ summary.failing.length }} failing
            <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">
              Controls whose latest run of the day ended in error: {{ summary.failing.slice(0, 10).join(", ") }}{{ summary.failing.length > 10 ? `, +${summary.failing.length - 10} more` : "" }}
            </q-tooltip>
          </span>
          <span>
            &middot; {{ compactNumber(summary.fetched) }} fetched
            <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">Records fetched by all runs: {{ formatNumber(summary.fetched) }}</q-tooltip>
          </span>
          <span>
            &middot; {{ formatDuration(summary.runtime) }} runtime
            <q-tooltip v-if="summary.longest" anchor="top middle" self="bottom middle" :offset="[0, 8]">
              The runtimes of the runs summed; the longest: {{ summary.longest.control_name }} ({{ formatDuration(summary.longest.duration_minutes * 60) }})
            </q-tooltip>
          </span>
        </div>
      </div>
    </div>

    <filter-chips v-if="hasDay" :filters="activeFilters" :shown="`${filteredControlResults.length} of ${controlResults.length} runs`" class="q-mb-md" @clear="clearFilters" />

    <div class="row items-center q-mb-md">
      <q-btn aria-label="Previous day" class="q-mb-md q-mr-xs day-btn" outline color="primary" padding="0 4px" icon="fas fa-chevron-left" :disable="!day" @click="goToDay(previousDay)">
        <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 10]"> Previous day </q-tooltip>
      </q-btn>
      <q-btn class="col-2 q-mb-md q-pa-sm" size="lg" color="primary" icon="fas fa-play-circle" label="Run control" @click="$refs.runControlDialog.open()" />
      <run-control-dialog ref="runControlDialog" :hook="refreshControlResults" />
      <run-log-dialog ref="runLogDialog" />

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

      <q-input clearable class="col q-mb-md q-pa-sm name-filter" outlined v-model="filter.control_name" label="Control name" maxlength="45" />

      <q-select
        v-model="filter.status"
        class="col-4 q-mb-md q-pa-sm"
        outlined
        options-dense
        emit-value
        map-options
        multiple
        use-chips
        :options="runStatusOptions"
        label="Run status">
      </q-select>


      <q-space />
      <q-btn aria-label="Next day" v-if="day && !isToday" class="q-mb-md day-btn" outline color="primary" padding="0 4px" icon="fas fa-chevron-right" @click="goToDay(nextDay)">
        <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 10]"> Next day </q-tooltip>
      </q-btn>
      <q-btn aria-label="Today" v-if="day && !isToday" class="q-mb-md q-ml-xs day-btn" flat color="primary" padding="0 4px" icon="fas fa-step-forward" @click="goToDay(serverToday)">
        <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 10]"> Today </q-tooltip>
      </q-btn>
    </div>

    <q-virtual-scroll
      type="table"
      dense
      class="list-table results-table"
      :style="{ '--name-column-width': nameColumnWidth + 'px' }"
      :items="sortedControlResults"
      :virtual-scroll-item-size="45"
      :virtual-scroll-sticky-size-start="28"
      :table-colspan="16">
      <template #before>
        <thead>
          <tr class="bg-blue-grey-2">
            <th class="text-left sortable" @click="toggleSort(sort, 'control_type')" v-keyboard :aria-sort="ariaSort(sort, 'control_type')">
              Type
              <q-icon v-if="sort.key === 'control_type'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-left sortable" @click="toggleSort(sort, 'start_date')" v-keyboard :aria-sort="ariaSort(sort, 'start_date')">
              Start
              <q-icon v-if="sort.key === 'start_date'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-right sortable" @click="toggleSort(sort, 'duration_minutes')" v-keyboard :aria-sort="ariaSort(sort, 'duration_minutes')">
              Runtime
              <q-icon v-if="sort.key === 'duration_minutes'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-center sortable" @click="toggleSort(sort, 'process_id')" v-keyboard :aria-sort="ariaSort(sort, 'process_id')">
              PID
              <q-icon v-if="sort.key === 'process_id'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-left sortable" @click="toggleSort(sort, 'control_name')" v-keyboard :aria-sort="ariaSort(sort, 'control_name')">
              Processname
              <q-icon v-if="sort.key === 'control_name'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-left sortable" @click="toggleSort(sort, 'date_from')" v-keyboard :aria-sort="ariaSort(sort, 'date_from')">
              Run from
              <q-icon v-if="sort.key === 'date_from'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-left sortable" @click="toggleSort(sort, 'date_to')" v-keyboard :aria-sort="ariaSort(sort, 'date_to')">
              Run to
              <q-icon v-if="sort.key === 'date_to'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-right sortable" @click="toggleSort(sort, 'fetched_number_a')" v-keyboard :aria-sort="ariaSort(sort, 'fetched_number_a')">
              Fetched A
              <q-icon v-if="sort.key === 'fetched_number_a'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-right sortable" @click="toggleSort(sort, 'fetched_number_b')" v-keyboard :aria-sort="ariaSort(sort, 'fetched_number_b')">
              Fetched B
              <q-icon v-if="sort.key === 'fetched_number_b'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-right sortable" @click="toggleSort(sort, 'error_number_a')" v-keyboard :aria-sort="ariaSort(sort, 'error_number_a')">
              Discr. A
              <q-icon v-if="sort.key === 'error_number_a'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-right sortable" @click="toggleSort(sort, 'error_number_b')" v-keyboard :aria-sort="ariaSort(sort, 'error_number_b')">
              Discr. B
              <q-icon v-if="sort.key === 'error_number_b'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-right sortable" @click="toggleSort(sort, 'error_level_a')" v-keyboard :aria-sort="ariaSort(sort, 'error_level_a')">
              Err. lvl A [%]
              <q-icon v-if="sort.key === 'error_level_a'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-right sortable" @click="toggleSort(sort, 'error_level_b')" v-keyboard :aria-sort="ariaSort(sort, 'error_level_b')">
              Err. lvl B [%]
              <q-icon v-if="sort.key === 'error_level_b'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-right sortable" @click="toggleSort(sort, 'prerequisite_value')" v-keyboard :aria-sort="ariaSort(sort, 'prerequisite_value')">
              PV
              <q-icon v-if="sort.key === 'prerequisite_value'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-left sortable" @click="toggleSort(sort, 'status')" v-keyboard :aria-sort="ariaSort(sort, 'status')">
              Status
              <q-icon v-if="sort.key === 'status'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-left"></th>
          </tr>
        </thead>
      </template>
      <template #default="{ item: control }">
        <tr :key="control.process_id">
          <td class="text-center">
            <q-chip clickable :title="controlType(control.control_type).label" @click="filter.type = control.control_type">
              <q-avatar :icon="controlType(control.control_type).icon" :color="controlType(control.control_type).color" text-color="white" />
              {{ control.control_type }}
            </q-chip>
          </td>
          <td class="text-left">
            <div class="text-blue-grey-7">
              <strong>{{ toDateString(control.start_date) }}</strong>
              <small class="text-grey-7 q-px-sm">{{ toTimeString(control.start_date) }}</small>
            </div>
          </td>
          <td class="text-right number-cell">{{ round(control.duration_minutes, 1) }} min</td>
          <td class="text-center text-weight-bold text-blue-grey-7 number-cell">{{ control.process_id }}</td>
          <td class="text-left text-weight-bold text-teal-8 ellipsis" :title="control.control_name">
            <q-btn aria-label="Filter by this control"
              v-if="!getSearch"
              size="7px"
              color="grey-5"
              round
              flat
              icon="fas fa-search"
              @click.stop="filter.control_name = control.control_name" />
            <router-link
              :to="{
                name: 'edit-control',
                params: { controlId: control.control_id },
              }">
              <span
                class="col cursor-pointer"
                style="font-size: 13px"
                :class="'text-' + controlTypeColor(control.control_type)">
                {{ control.control_name }}
              </span>
            </router-link>
          </td>
          <td class="text-left text-weight-bold text-blue-grey-7">
            {{ toDateString(control.date_from) }}
          </td>
          <td class="text-left text-weight-bold text-blue-grey-7">
            {{ toDateString(control.date_to) }}
          </td>
          <td class="text-right number-cell">
            <span v-if="control.fetched_number_a > 0" class="cursor-pointer number-link" v-keyboard:button @click="openNumberMenu($event, control, 'fetched_a')" @contextmenu.prevent="openNumberMenu($event, control, 'fetched_a')">
              {{ formatNumber(control.fetched_number_a) }}
            </span>
            <span v-else>{{ formatNumber(control.fetched_number_a) }}</span>
          </td>
          <td class="text-right number-cell">
            <span v-if="control.fetched_number_b > 0" class="cursor-pointer number-link" v-keyboard:button @click="openNumberMenu($event, control, 'fetched_b')" @contextmenu.prevent="openNumberMenu($event, control, 'fetched_b')">
              {{ formatNumber(control.fetched_number_b) }}
            </span>
            <span v-else>{{ formatNumber(control.fetched_number_b) }}</span>
          </td>
          <td class="text-right number-cell">
            <span v-if="control.error_number_a > 0" class="cursor-pointer text-red" v-keyboard:button @click="openNumberMenu($event, control, 'result_a')" @contextmenu.prevent="openNumberMenu($event, control, 'result_a')">
              {{ formatNumber(control.error_number_a) }}
            </span>
            <span v-else>{{ formatNumber(control.error_number_a) }}</span>
          </td>
          <td class="text-right number-cell">
            <span v-if="control.error_number_b > 0" class="cursor-pointer text-red" v-keyboard:button @click="openNumberMenu($event, control, 'result_b')" @contextmenu.prevent="openNumberMenu($event, control, 'result_b')">
              {{ formatNumber(control.error_number_b) }}
            </span>
            <span v-else>{{ formatNumber(control.error_number_b) }}</span>
          </td>
          <td class="text-right number-cell">
            <span v-if="control.error_level_a > 0" class="cursor-pointer text-red" v-keyboard:button @click="openNumberMenu($event, control, 'result_a')" @contextmenu.prevent="openNumberMenu($event, control, 'result_a')">
              {{ formatNumber(control.error_level_a, 2) }}%
            </span>
            <span v-else> {{ formatNumber(control.error_level_a, 2) }}% </span>
          </td>
          <td class="text-right number-cell">
            <span v-if="control.error_level_b > 0" class="cursor-pointer text-red" v-keyboard:button @click="openNumberMenu($event, control, 'result_b')" @contextmenu.prevent="openNumberMenu($event, control, 'result_b')">
              {{ formatNumber(control.error_level_b, 2) }}%
            </span>
            <span v-else> {{ formatNumber(control.error_level_b, 2) }}% </span>
          </td>
          <td class="text-right">
            <q-icon v-if="control.prerequisite_value == 0" class="cursor-pointer text-red" name="fas fa-stop" title="Prerequisite SQL value is 0" />
            <q-icon
              v-if="control.prerequisite_value"
              class="cursor-pointer text-green"
              name="fas fa-play"
              :title="`Prerequisite SQL value is ${control.prerequisite_value}`" />
          </td>
          <td class="text-left text-no-wrap">
            <q-chip clickable class="cursor-pointer" @click="!filter.status.includes(control.status) && filter.status.push(control.status)">
              <q-avatar :icon="runStatus(control.status).icon" :color="runStatus(control.status).color" text-color="white" />
              {{ runStatus(control.status).label }}
            </q-chip>
            <q-icon
              v-if="control.has_warning"
              class="cursor-pointer"
              name="fas fa-exclamation-triangle"
              color="amber-9"
              size="16px"
              title="Finished with warnings: click for the run details"
              @click="$refs.runLogDialog.open(control)" />
          </td>
          <td class="text-left">
            <q-btn aria-label="Row actions" size="sm" color="grey-7" round flat icon="fas fa-ellipsis-v" @click="openRowMenu($event, control)" />
          </td>
        </tr>
      </template>
      <template #after>
        <tbody v-if="!hasDay">
          <skeleton-rows v-if="!loadError" :columns="skeletonColumns" />
          <tr v-else>
            <td colspan="16" class="text-center text-grey-7 q-pa-lg">Runs could not be loaded</td>
          </tr>
        </tbody>
        <tbody v-else-if="!sortedControlResults.length">
          <tr>
            <td colspan="16" class="text-center text-grey-7 q-pa-lg">
              {{ controlResults.length ? "No runs match the filters" : `No runs on ${day}` }}
            </td>
          </tr>
        </tbody>
      </template>
    </q-virtual-scroll>
    <run-dataset-menu ref="numberMenu" />
    <q-menu ref="rowMenu" :target="menuTarget" no-parent-event>
        <q-list v-if="menuRow" dense class="text-no-wrap">
        <q-item dense clickable @click="reRun(menuRow, refreshControlResults)" v-close-popup>
          <q-item-section> Re-run </q-item-section>
        </q-item>
        <run-control-dialog :control_name="menuRow.control_name" :hook="refreshControlResults">
          <q-item dense clickable class="col items-center">
            <q-item-section> Run </q-item-section>
          </q-item>
        </run-control-dialog>
        <q-separator />
        <q-item dense clickable :to="{ name: 'edit-control', params: { controlId: menuRow.control_id } }">
          <q-item-section> Edit control </q-item-section>
        </q-item>
        <q-separator />
        <q-item v-if="menuRow.status != 'X'" dense clickable class="col items-center" @click="revokeRun(menuRow, refreshControlResults)" v-close-popup>
          <q-item-section> Revoke run </q-item-section>
        </q-item>
        <q-item
          v-if="activeRunStatuses.includes(menuRow.status)"
          dense
          clickable
          class="col items-center"
          @click="cancelRun(menuRow, refreshControlResults)"
          v-close-popup>
          <q-item-section> Cancel run </q-item-section>
        </q-item>
        <q-item dense clickable class="col items-center" @click="$refs.runLogDialog.open(menuRow)" v-close-popup>
          <q-item-section> Show full log </q-item-section>
        </q-item>
        <q-item v-if="menuRow.status == 'D' && menuRowSendsEmail" dense clickable class="col items-center" @click="sendEmail(menuRow)" v-close-popup>
          <q-item-section> Send email </q-item-section>
        </q-item>
      </q-list>
    </q-menu>
  </q-page>
</template>

<script>
import { mapActions, mapGetters, mapState } from "vuex";
import FilterChips from "./FilterChips.vue";
import RunControlDialog from "./RunControlDialog.vue";
import RunDatasetMenu from "./RunDatasetMenu.vue";
import RunLogDialog from "./RunLogDialog.vue";
import SkeletonRows from "./SkeletonRows.vue";
import { notifyError } from "../api";
import { ACTIVE_RUN_STATUSES, CONTROL_TYPES, CONTROL_TYPE_OPTIONS, RUN_STATUSES, RUN_STATUS_OPTIONS, controlType, controlTypeColor, runStatus } from "../constants";
import { cancelRun, reRun, revokeRun, sendEmail } from "../runActions";
import { EMAIL_CONTROL_TYPES, sendsEmail } from "../utils/email";
import { liveRefetch } from "../socket";
import { compactNumber, dayTitle, formatDuration, formatNumber, round, shiftDay, toDateString, toTimeString } from "../utils/format";
import { fillViewportToBottom, textWidth } from "../utils/layout";
import { listFilter, searchFilter, valueFilter } from "../utils/filters";
import { ariaSort, sortIcon, sortRows, toggleSort } from "../utils/sort";
import persistFilters from "../mixins/persistFilters";

// Kept alive (App.vue), so it is built once; activated/deactivated start and stop its live refresh.
export default {
  name: "ControlResults",
  mixins: [persistFilters("results", ["filter", "sort"])],
  components: {
    FilterChips,
    RunControlDialog,
    RunDatasetMenu,
    RunLogDialog,
    SkeletonRows,
  },
  data() {
    return {
      controlTypeOptions: CONTROL_TYPE_OPTIONS,
      runStatusOptions: RUN_STATUS_OPTIONS,
      activeRunStatuses: ACTIVE_RUN_STATUSES,
      skeletonColumns: ["QChip", "text", "text", "text", "text", "text", "text", "text", "text", "text", "text", "text", "text", null, "QChip", null],
      active: false,
      refreshing: false,
      loadError: false,
      // The one row menu of the table, opened at the kebab button of the row it acts on.
      menuTarget: false,
      menuProcessId: null,
      // The one menu of the fetched and discrepancy numbers, opened at the number it acts on.
      filter: {
        control_name: null,
        type: null,
        status: [],
        warnings: null,
      },
      sort: {
        key: "start_date",
        dir: "desc",
      },
    };
  },
  methods: {
    ...mapActions(["updateControlResults"]),
    compactNumber,
    controlType,
    controlTypeColor,
    formatDuration,
    runStatus,
    // The controls whose latest run of the day (the highest process ID) ended in error, by name.
    failingControls(rows) {
      const latest = new Map();
      rows.forEach((row) => {
        const seen = latest.get(row.control_id);
        if (!seen || row.process_id > seen.process_id) latest.set(row.control_id, row);
      });
      return [...latest.values()]
        .filter((row) => row.status === "E")
        .map((row) => row.control_name)
        .sort();
    },
    formatNumber,
    round,
    toDateString,
    toTimeString,
    reRun,
    cancelRun,
    revokeRun,
    sendEmail,
    sortIcon,
    ariaSort,
    toggleSort,
    fillViewportToBottom,
    async refreshControlResults() {
      this.refreshing = true;
      this.loadError = false;
      try {
        await this.updateControlResults(this.$route.query.date || null);
      } catch (error) {
        this.loadError = true;
        notifyError("Failed to load control runs.", error);
      } finally {
        this.refreshing = false;
      }
    },
    openNumberMenu(event, row, dataset) {
      this.$refs.numberMenu.open(event, row, dataset);
    },
    openRowMenu(event, row) {
      this.menuTarget = event.currentTarget;
      this.menuProcessId = row.process_id;
      this.$nextTick(() => this.$refs.rowMenu.show());
    },
    // The server's today is plain /results, so the menu link and redirects always land on today.
    goToDay(day) {
      this.$router.push({ name: "results", query: day && day !== this.serverToday ? { date: day } : {} });
    },
    addStatusFilter(status) {
      if (!this.filter.status.includes(status)) {
        this.filter.status.push(status);
      }
    },
    parseNumericSortValue(val) {
      if (val == null) return null;
      if (typeof val === "number") {
        return Number.isFinite(val) ? val : null;
      }
      const match = String(val).match(/-?\d+(?:\.\d+)?/);
      return match ? Number(match[0]) : null;
    },
    // Every filter and the header search; the sort stays.
    clearFilters() {
      this.filter.control_name = null;
      this.filter.type = null;
      this.filter.status = [];
      this.filter.warnings = null;
      this.$store.commit("updateSearch", "");
    },
    getSortValue(item) {
      const val = item[this.sort.key];
      if (this.sort.key === "start_date" || this.sort.key === "date_from" || this.sort.key === "date_to") {
        return val ? new Date(val).getTime() : null;
      }
      if (this.sort.key === "error_level_a" || this.sort.key === "error_level_b") {
        return this.parseNumericSortValue(val);
      }
      return val ?? null;
    },
  },
  computed: {
    ...mapState(["controlResults", "controlResultsDay", "serverToday"]),
    // The day shown: ?date=YYYY-MM-DD, or the server's today.
    day() {
      return this.$route.query.date || this.serverToday;
    },
    // The day shown, as DD.MM.YYYY for the page title.
    dayTitle() {
      return dayTitle(this.day);
    },
    previousDay() {
      return shiftDay(this.day, -1);
    },
    nextDay() {
      return shiftDay(this.day, 1);
    },
    isToday() {
      return this.day >= this.serverToday;
    },
    // Whether the store holds the runs of the day shown; until then the table shows skeleton rows.
    hasDay() {
      return Boolean(this.day) && this.controlResultsDay === this.day;
    },
    // The Processname column fits the longest name of the day (bold 13px, plus the search button and padding).
    nameColumnWidth() {
      return Math.min(textWidth(this.controlResults.map((row) => row.control_name), "bold 13px Roboto, sans-serif") + 40, 400);
    },
    // Looked up by PID, so an open menu follows live updates of its run.
    menuRow() {
      return this.controlResults.find((row) => row.process_id === this.menuProcessId) || null;
    },
    // The email configuration is in the catalogue. Until it is loaded, every type that can send one is offered.
    menuRowSendsEmail() {
      const control = this.menuRow && this.controlCatalogueById(this.menuRow.control_id);
      return control ? sendsEmail(control) : Boolean(this.menuRow) && EMAIL_CONTROL_TYPES.includes(this.menuRow.control_type);
    },
    // Totals of all runs of the day, whatever the filters, in the order of the type and status constants.
    summary() {
      const rows = this.hasDay ? this.controlResults : [];
      const sum = (list, value) => list.reduce((total, row) => total + (Number(value(row)) || 0), 0);
      const countBy = (field, order) => {
        const counts = new Map();
        rows.forEach((row) => counts.set(row[field], (counts.get(row[field]) || 0) + 1));
        return [...counts.keys()].sort((a, b) => order.indexOf(a) - order.indexOf(b)).map((key) => ({ key, count: counts.get(key) }));
      };
      return {
        controls: new Set(rows.map((row) => row.control_id)).size,
        runs: rows.length,
        types: countBy("control_type", Object.keys(CONTROL_TYPES)),
        statuses: countBy("status", Object.keys(RUN_STATUSES)),
        warnings: rows.filter((row) => row.has_warning).length,
        failing: this.failingControls(rows),
        fetched: sum(rows, (row) => row.fetched_number_a + row.fetched_number_b),
        runtime: sum(rows, (row) => row.duration_minutes) * 60,
        longest: rows.reduce((longest, row) => (row.duration_minutes > (longest ? longest.duration_minutes : 0) ? row : longest), null),
      };
    },
    ...mapGetters(["getSearch", "controlCatalogueById"]),
    activeFilters() {
      const filter = this.filter;
      return [
        ...valueFilter("type", "Type", filter.type, () => (filter.type = null)),
        ...valueFilter("name", "Name", filter.control_name, () => (filter.control_name = null), { text: true }),
        ...listFilter(
          "status",
          "Status",
          filter.status,
          (value) => (filter.status = filter.status.filter((item) => item !== value)),
          (value) => runStatus(value).label,
        ),
        ...valueFilter("warnings", "Warnings", filter.warnings || null, () => (filter.warnings = null), { label: "Flagged runs" }),
        ...searchFilter(this.$store),
      ];
    },
    sortedControlResults() {
      return sortRows(this.filteredControlResults, this.getSortValue, this.sort.dir);
    },
    filteredControlResults() {
      const s = this.getSearch ? this.getSearch.toUpperCase() : null;
      const name = this.filter.control_name ? this.filter.control_name.toUpperCase() : null;
      // Until the requested day has loaded, the store still holds the previous one.
      if (!this.hasDay) {
        return [];
      }
      return this.controlResults.filter(
        (item) =>
          (!s || (item.control_name || "").toUpperCase().includes(s)) &&
          (!name || (item.control_name || "").toUpperCase().includes(name)) &&
          (!this.filter.type || item.control_type === this.filter.type) &&
          (this.filter.status.length === 0 || this.filter.status.includes(item.status)) &&
          (!this.filter.warnings || item.has_warning)
      );
    },
  },
  watch: {
    // Day navigation only changes the query; the filters and the sort are kept. While the page is cached,
    // activated() refetches instead.
    "$route.query.date"() {
      if (this.active && this.$route.name === "results") {
        this.refreshControlResults();
      }
    },
  },
  // Also runs after the first mount. Rows already in the store are shown at once and refreshed behind them.
  activated() {
    this.active = true;
    this.stopLiveUpdates = liveRefetch("runs:changed", () => this.updateControlResults(this.$route.query.date || null));
    this.refreshControlResults();
  },
  deactivated() {
    this.active = false;
    this.stopLiveUpdates();
  },
};
</script>

<style lang="css" scoped>
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

/* Fixed columns, so rows swapped in while scrolling don't resize them. Processname takes the rest, but at least
   the width of the longest name of the day (nameColumnWidth), else the table scrolls sideways. */
.results-table :deep(table) {
  table-layout: fixed;
  min-width: calc(1198px + var(--name-column-width));
}
.results-table th:nth-child(1) { width: 114px; }
.results-table th:nth-child(2) { width: 144px; }
.results-table th:nth-child(3) { width: 66px; }
.results-table th:nth-child(4) { width: 92px; }
.results-table th:nth-child(6),
.results-table th:nth-child(7) { width: 87px; }
.results-table th:nth-child(8),
.results-table th:nth-child(9) { width: 72px; }
.results-table th:nth-child(10),
.results-table th:nth-child(11) { width: 58px; }
.results-table th:nth-child(12),
.results-table th:nth-child(13) { width: 80px; }
.results-table th:nth-child(14) { width: 34px; }
.results-table th:nth-child(15) { width: 128px; }
.results-table th:nth-child(16) { width: 50px; }
</style>
