<template>
  <q-page class="column no-wrap" :style-fn="fillViewportToBottom">
    <div class="row items-end q-mb-lg">
      <h2 class="row items-center no-wrap text-no-wrap q-gutter-lg q-mb-none">
        <div>Control results</div>
        <div class="text-grey-6 results-day">{{ dayTitle }}</div>
        <div v-if="refreshing && hasDay">
          <q-avatar size="lg" color="grey-5">
            <q-icon name="fas fa-sync fa-spin" />
          </q-avatar>
        </div>
      </h2>
      <q-space />

      <div v-if="hasDay" class="row items-center justify-end q-gutter-x-md text-blue-grey-8">
        <div>
          <strong>{{ summary.controls }}</strong> {{ summary.controls === 1 ? "control" : "controls" }} &middot; <strong>{{ summary.runs }}</strong>
          {{ summary.runs === 1 ? "run" : "runs" }}
        </div>
        <div v-if="summary.types.length">
          <q-chip v-for="item in summary.types" :key="item.key" clickable @click="filter.type = item.key">
            <q-avatar :icon="controlType(item.key).icon" :color="controlType(item.key).color" text-color="white" />
            {{ item.key }} {{ item.count }}
            <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">{{ controlType(item.key).label }}</q-tooltip>
          </q-chip>
        </div>
        <div v-if="summary.statuses.length">
          <q-chip v-for="item in summary.statuses" :key="String(item.key)" clickable @click="addStatusFilter(item.key)">
            <q-avatar :icon="runStatus(item.key).icon" :color="runStatus(item.key).color" text-color="white" />
            {{ runStatus(item.key).label }} {{ item.count }}
          </q-chip>
        </div>
      </div>
    </div>

    <div class="row items-center q-mb-md">
      <q-btn class="q-mb-md q-mr-xs day-btn" outline color="primary" padding="0 4px" icon="fas fa-chevron-left" :disable="!day" @click="goToDay(previousDay)">
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

      <q-btn flat round color="grey" class="q-mb-md q-pa-sm" icon="fas fa-times-circle" @click="clearFilters">
        <q-tooltip anchor="top left" self="bottom left" :offset="[15, 10]"> Clear filters </q-tooltip>
      </q-btn>

      <q-space />
      <q-btn v-if="day && !isToday" class="q-mb-md day-btn" outline color="primary" padding="0 4px" icon="fas fa-chevron-right" @click="goToDay(nextDay)">
        <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 10]"> Next day </q-tooltip>
      </q-btn>
      <q-btn v-if="day && !isToday" class="q-mb-md q-ml-xs day-btn" flat color="primary" padding="0 4px" icon="fas fa-step-forward" @click="goToDay(serverToday)">
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
            <th class="text-left sortable" @click="toggleSort(sort, 'control_type')">
              Type
              <q-icon v-if="sort.key === 'control_type'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-left sortable" @click="toggleSort(sort, 'start_date')">
              Start
              <q-icon v-if="sort.key === 'start_date'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-right sortable" @click="toggleSort(sort, 'duration_minutes')">
              Runtime
              <q-icon v-if="sort.key === 'duration_minutes'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-center sortable" @click="toggleSort(sort, 'process_id')">
              PID
              <q-icon v-if="sort.key === 'process_id'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-left sortable" @click="toggleSort(sort, 'control_name')">
              Processname
              <q-icon v-if="sort.key === 'control_name'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-left sortable" @click="toggleSort(sort, 'date_from')">
              Run from
              <q-icon v-if="sort.key === 'date_from'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-left sortable" @click="toggleSort(sort, 'date_to')">
              Run to
              <q-icon v-if="sort.key === 'date_to'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-right sortable" @click="toggleSort(sort, 'fetched_number_a')">
              Fetched A
              <q-icon v-if="sort.key === 'fetched_number_a'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-right sortable" @click="toggleSort(sort, 'fetched_number_b')">
              Fetched B
              <q-icon v-if="sort.key === 'fetched_number_b'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-right sortable" @click="toggleSort(sort, 'error_number_a')">
              Discr. A
              <q-icon v-if="sort.key === 'error_number_a'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-right sortable" @click="toggleSort(sort, 'error_number_b')">
              Discr. B
              <q-icon v-if="sort.key === 'error_number_b'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-right sortable" @click="toggleSort(sort, 'error_level_a')">
              Err. lvl A [%]
              <q-icon v-if="sort.key === 'error_level_a'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-right sortable" @click="toggleSort(sort, 'error_level_b')">
              Err. lvl B [%]
              <q-icon v-if="sort.key === 'error_level_b'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-right sortable" @click="toggleSort(sort, 'prerequisite_value')">
              PV
              <q-icon v-if="sort.key === 'prerequisite_value'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-left sortable" @click="toggleSort(sort, 'status')">
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
            <q-chip clickable size="11px" :title="controlType(control.control_type).label" @click="filter.type = control.control_type">
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
          <td class="text-right">{{ round(control.duration_minutes, 1) }} min</td>
          <td class="text-center text-weight-bold text-blue-grey-7">{{ control.process_id }}</td>
          <td class="text-left text-weight-bold text-teal ellipsis" :title="control.control_name">
            <q-btn
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
          <td class="text-right">
            <span
              v-if="control.fetched_number_a > 0 && control.control_type === 'REP'"
              class="cursor-pointer text-red"
              @click="copyResultsSql(control, 'A')">
              {{ formatNumber(control.fetched_number_a) }}
            </span>
            <span v-else>
              {{ formatNumber(control.fetched_number_a) }}
            </span>
          </td>
          <td class="text-right">
            {{ formatNumber(control.fetched_number_b) }}
          </td>
          <td class="text-right">
            <span v-if="control.error_number_a > 0" class="cursor-pointer text-red" @click="copyResultsSql(control, 'A')">
              {{ formatNumber(control.error_number_a) }}
            </span>
            <span v-else>
              {{ formatNumber(control.error_number_a) }}
            </span>
          </td>
          <td class="text-right">
            <span v-if="control.error_number_b > 0" class="cursor-pointer text-red" @click="copyResultsSql(control, 'B')">
              {{ formatNumber(control.error_number_b) }}
            </span>
            <span v-else>
              {{ formatNumber(control.error_number_b) }}
            </span>
          </td>
          <td class="text-right">
            <span v-if="control.error_level_a > 0" class="cursor-pointer text-red" @click="copyResultsSql(control, 'A')">
              {{ formatNumber(control.error_level_a, 2) }}%
            </span>
            <span v-else> {{ formatNumber(control.error_level_a, 2) }}% </span>
          </td>
          <td class="text-right">
            <span v-if="control.error_level_b > 0" class="cursor-pointer text-red" @click="copyResultsSql(control, 'B')">
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
          <td class="text-left">
            <q-chip clickable class="cursor-pointer" @click="!filter.status.includes(control.status) && filter.status.push(control.status)">
              <q-avatar :icon="runStatus(control.status).icon" :color="runStatus(control.status).color" text-color="white" />
              {{ runStatus(control.status).label }}
            </q-chip>
          </td>
          <td class="text-left">
            <q-btn size="sm" color="grey-7" round flat icon="fas fa-ellipsis-v" @click="openRowMenu($event, control)" />
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
        <q-item v-if="menuRow.status == 'E'" dense clickable class="col items-center" @click="showErrorLog(menuRow)" v-close-popup>
          <q-item-section> Show error log </q-item-section>
        </q-item>
        <q-item v-if="menuRow.status == 'D' && menuRowSendsEmail" dense clickable class="col items-center" @click="sendEmail(menuRow)" v-close-popup>
          <q-item-section> Send email </q-item-section>
        </q-item>
        <q-item dense clickable @click="dropTemporaryTables(menuRow)" v-close-popup>
          <q-item-section> Drop temporary tables </q-item-section>
        </q-item>
      </q-list>
    </q-menu>
  </q-page>
</template>

<script>
import { date } from "quasar";
import { mapActions, mapGetters, mapState } from "vuex";
import RunControlDialog from "./RunControlDialog.vue";
import RunLogDialog from "./RunLogDialog.vue";
import SkeletonRows from "./SkeletonRows.vue";
import { notifyError } from "../api";
import { ACTIVE_RUN_STATUSES, CONTROL_TYPES, CONTROL_TYPE_OPTIONS, RUN_STATUSES, RUN_STATUS_OPTIONS, controlType, controlTypeColor, runStatus } from "../constants";
import { cancelRun, copyResultsSql, dropTemporaryTables, reRun, revokeRun, sendEmail, showErrorLog } from "../runActions";
import { EMAIL_CONTROL_TYPES, sendsEmail } from "../utils/email";
import { liveRefetch } from "../socket";
import { formatNumber, round, toDateString, toTimeString } from "../utils/format";
import { fillViewportToBottom, textWidth } from "../utils/layout";
import { sortIcon, sortRows, toggleSort } from "../utils/sort";

// Kept alive (App.vue), so it is built once; activated/deactivated start and stop its live refresh.
export default {
  name: "ControlResults",
  components: {
    RunControlDialog,
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
      filter: {
        control_name: null,
        type: null,
        status: [],
      },
      sort: {
        key: "start_date",
        dir: "desc",
      },
    };
  },
  methods: {
    ...mapActions(["updateControlResults"]),
    controlType,
    controlTypeColor,
    runStatus,
    formatNumber,
    round,
    toDateString,
    toTimeString,
    reRun,
    cancelRun,
    revokeRun,
    dropTemporaryTables,
    showErrorLog,
    sendEmail,
    copyResultsSql,
    sortIcon,
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
    openRowMenu(event, row) {
      this.menuTarget = event.currentTarget;
      this.menuProcessId = row.process_id;
      this.$nextTick(() => this.$refs.rowMenu.show());
    },
    // The server's today is plain /results, so the menu link and redirects always land on today.
    goToDay(day) {
      this.$router.push({ name: "results", query: day && day !== this.serverToday ? { date: day } : {} });
    },
    shiftDay(days) {
      return date.formatDate(date.addToDate(date.extractDate(this.day, "YYYY-MM-DD"), { days }), "YYYY-MM-DD");
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
    clearFilters() {
      this.filter.control_name = null;
      this.filter.type = null;
      this.filter.status = [];
      this.sort.key = "start_date";
      this.sort.dir = "desc";
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
      return this.day ? date.formatDate(date.extractDate(this.day, "YYYY-MM-DD"), "DD.MM.YYYY") : "";
    },
    previousDay() {
      return this.shiftDay(-1);
    },
    nextDay() {
      return this.shiftDay(1);
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
      };
    },
    ...mapGetters(["getSearch", "controlCatalogueById"]),
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
          (this.filter.status.length === 0 || this.filter.status.includes(item.status))
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
  color: #009688;
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}

a:visited {
  color: #009688;
}

/* The day buttons are as tall as the Run control button beside them, and no wider than their icon. */
.day-btn {
  height: 51px;
  min-width: 0;
}

.name-filter {
  min-width: 180px;
}

.results-day {
  font-size: 0.6em;
}

.sortable {
  cursor: pointer;
  user-select: none;
}

/* Fixed columns, so rows swapped in while scrolling don't resize them. Processname takes the rest, but at least
   the width of the longest name of the day (nameColumnWidth), else the table scrolls sideways. */
.results-table :deep(table) {
  table-layout: fixed;
  min-width: calc(1168px + var(--name-column-width));
}
.results-table th:nth-child(1) { width: 84px; }
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
.results-table th:nth-child(15) { width: 104px; }
.results-table th:nth-child(16) { width: 50px; }
</style>
