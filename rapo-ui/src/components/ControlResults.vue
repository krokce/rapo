<template>
  <q-page>
    <h2 class="row q-gutter-lg q-mb-lg">
      <div>Control results</div>
      <div v-if="!loaded">
        <q-avatar size="lg" color="grey-5">
          <q-icon name="fas fa-sync fa-spin" />
        </q-avatar>
      </div>
    </h2>

    <div v-if="loaded" class="row items-center q-gutter-x-md q-mb-sm text-blue-grey-8">
      <div>
        <strong>{{ summary.controls }}</strong> {{ summary.controls === 1 ? "control" : "controls" }} &middot; <strong>{{ summary.runs }}</strong>
        {{ summary.runs === 1 ? "run" : "runs" }}
      </div>
      <div v-if="summary.types.length">
        <q-chip
          v-for="item in summary.types"
          :key="item.key"
          clickable
          dense
          size="12px"
          text-color="white"
          :class="'bg-' + controlTypeColor(item.key)"
          class="text-weight-bold"
          @click="filter.type = item.key">
          {{ item.key }} {{ item.count }}
        </q-chip>
      </div>
      <div v-if="summary.statuses.length">
        <q-chip v-for="item in summary.statuses" :key="String(item.key)" clickable dense size="12px" @click="addStatusFilter(item.key)">
          <q-avatar :icon="runStatus(item.key).icon" :color="runStatus(item.key).color" text-color="white" />
          {{ runStatus(item.key).label }} {{ item.count }}
        </q-chip>
      </div>
    </div>

    <div class="row items-center q-mb-md">
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

      <q-input clearable class="col q-mb-md q-pa-sm" outlined v-model="filter.control_name" label="Control name" maxlength="45" />

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
    </div>

    <div v-if="day" class="row items-center no-wrap q-mb-sm">
      <div class="col row items-center justify-start no-wrap">
        <q-btn no-caps size="md" outline color="primary" icon="fas fa-chevron-left" :label="previousDay" @click="goToDay(previousDay)" />
      </div>
      <q-btn no-caps size="md" unelevated color="primary" icon="fas fa-calendar-alt" icon-right="fas fa-caret-down" :label="dayLabel">
        <q-popup-proxy ref="dayPicker" cover transition-show="scale" transition-hide="scale">
          <q-date :model-value="day" mask="YYYY-MM-DD" first-day-of-week="1" :options="isSelectableDay" @update:model-value="pickDay" />
        </q-popup-proxy>
      </q-btn>
      <div class="col row items-center justify-end no-wrap">
        <q-btn v-if="!isToday" no-caps size="md" outline color="primary" icon-right="fas fa-chevron-right" :label="nextDay" @click="goToDay(nextDay)" />
        <q-btn v-if="!isToday" no-caps size="md" flat class="q-ml-sm" color="primary" icon="fas fa-step-forward" @click="goToDay(serverToday)">
          <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 10]"> Today </q-tooltip>
        </q-btn>
      </div>
    </div>

    <div>
      <q-markup-table dense>
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
        <tbody>
          <tr v-if="loaded && !sortedControlResults.length">
            <td colspan="16" class="text-center text-grey-7 q-pa-lg">
              {{ controlResults.length ? "No runs match the filters" : `No runs on ${day}` }}
            </td>
          </tr>
          <tr v-for="control in sortedControlResults" :key="control.process_id">
            <td class="text-center">
              <q-chip
                clickable
                size="11px"
                text-color="white"
                :class="'bg-' + controlTypeColor(control.control_type)"
                class="text-weight-bold"
                @click="filter.type = control.control_type">
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
            <td class="text-left text-weight-bold text-teal">
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
              <q-icon v-if="control.prerequisite_value == 0" class="cursor-pointer text-red" name="fas fa-stop">
                <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]"> Prerequisite SQL value is 0 </q-tooltip>
              </q-icon>
              <q-icon v-if="control.prerequisite_value" class="cursor-pointer text-green" name="fas fa-play">
                <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]"> Prerequisite SQL value is {{ control.prerequisite_value }} </q-tooltip>
              </q-icon>
            </td>
            <td class="text-left">
              <q-chip clickable class="cursor-pointer" @click="!filter.status.includes(control.status) && filter.status.push(control.status)">
                <q-avatar :icon="runStatus(control.status).icon" :color="runStatus(control.status).color" text-color="white" />
                {{ runStatus(control.status).label }}
              </q-chip>
            </td>
            <td class="text-left" style="width: 50px">
              <q-btn size="sm" color="grey-7" round flat icon="fas fa-ellipsis-v">
                <q-menu>
                  <q-list dense class="text-no-wrap">
                    <q-item dense clickable @click="reRun(control, refreshControlResults)" v-close-popup>
                      <q-item-section> Re-run </q-item-section>
                    </q-item>
                    <run-control-dialog :control_name="control.control_name" :hook="refreshControlResults">
                      <q-item dense clickable class="col items-center">
                        <q-item-section> Run </q-item-section>
                      </q-item>
                    </run-control-dialog>
                    <q-separator />
                    <q-item dense clickable :to="{ name: 'edit-control', params: { controlId: control.control_id } }">
                      <q-item-section> Edit control </q-item-section>
                    </q-item>
                    <q-separator />
                    <q-item v-if="control.status != 'X'" dense clickable class="col items-center" @click="revokeRun(control, refreshControlResults)" v-close-popup>
                      <q-item-section> Revoke run </q-item-section>
                    </q-item>
                    <q-item
                      v-if="activeRunStatuses.includes(control.status)"
                      dense
                      clickable
                      class="col items-center"
                      @click="cancelRun(control, refreshControlResults)"
                      v-close-popup>
                      <q-item-section> Cancel run </q-item-section>
                    </q-item>
                    <q-item dense clickable class="col items-center" @click="$refs.runLogDialog.open(control)" v-close-popup>
                      <q-item-section> Show full log </q-item-section>
                    </q-item>
                    <q-item v-if="control.status == 'E'" dense clickable class="col items-center" @click="showErrorLog(control)" v-close-popup>
                      <q-item-section> Show error log </q-item-section>
                    </q-item>
                    <q-item dense clickable @click="dropTemporaryTables(control)" v-close-popup>
                      <q-item-section> Drop temporary tables </q-item-section>
                    </q-item>
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
import { date } from "quasar";
import { mapActions, mapGetters, mapState } from "vuex";
import RunControlDialog from "./RunControlDialog.vue";
import RunLogDialog from "./RunLogDialog.vue";
import { notifyError } from "../api";
import { ACTIVE_RUN_STATUSES, CONTROL_TYPES, CONTROL_TYPE_OPTIONS, RUN_STATUSES, RUN_STATUS_OPTIONS, controlTypeColor, runStatus } from "../constants";
import { cancelRun, copyResultsSql, dropTemporaryTables, reRun, revokeRun, showErrorLog } from "../runActions";
import { liveRefetch } from "../socket";
import { formatNumber, round, toDateString, toTimeString } from "../utils/format";
import { sortIcon, sortRows, toggleSort } from "../utils/sort";

export default {
  components: {
    RunControlDialog,
    RunLogDialog,
  },
  data() {
    return {
      controlTypeOptions: CONTROL_TYPE_OPTIONS,
      runStatusOptions: RUN_STATUS_OPTIONS,
      activeRunStatuses: ACTIVE_RUN_STATUSES,
      loaded: false,
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
    copyResultsSql,
    sortIcon,
    toggleSort,
    async refreshControlResults() {
      try {
        await this.updateControlResults(this.$route.query.date || null);
        this.loaded = true;
      } catch (error) {
        notifyError("Failed to load control runs.", error);
      }
    },
    // The server's today is plain /results, so the menu link and redirects always land on today.
    goToDay(day) {
      this.$router.push({ name: "results", query: day && day !== this.serverToday ? { date: day } : {} });
    },
    pickDay(day) {
      this.$refs.dayPicker.hide();
      if (day) {
        this.goToDay(day);
      }
    },
    // q-date passes days as YYYY/MM/DD.
    isSelectableDay(day) {
      return !this.serverToday || day <= this.serverToday.replaceAll("-", "/");
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
    dayLabel() {
      return date.formatDate(date.extractDate(this.day, "YYYY-MM-DD"), "ddd YYYY-MM-DD");
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
    // Counts of the listed (filtered) runs, in the order of the type and status constants.
    summary() {
      const rows = this.filteredControlResults;
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
    ...mapGetters(["getSearch"]),
    sortedControlResults() {
      return sortRows(this.filteredControlResults, this.getSortValue, this.sort.dir);
    },
    filteredControlResults() {
      const s = this.getSearch ? this.getSearch.toUpperCase() : null;
      const name = this.filter.control_name ? this.filter.control_name.toUpperCase() : null;
      // Until the requested day has loaded, the store still holds the previous one.
      if (this.controlResultsDay !== this.day) {
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
    // Day navigation only changes the query; the filters and the sort are kept.
    "$route.query.date"() {
      if (this.$route.name === "results") {
        this.loaded = false;
        this.refreshControlResults();
      }
    },
  },
  mounted() {
    this.stopLiveUpdates = liveRefetch("runs:changed", () => this.updateControlResults(this.$route.query.date || null));
    this.refreshControlResults();
  },
  unmounted() {
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

.sortable {
  cursor: pointer;
  user-select: none;
}
</style>
