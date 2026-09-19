<template>
  <q-page>
    <h2 class="row q-gutter-lg">
      <div>Last control result<span v-if="filteredControlResultsLen != 1">s</span></div>
      <div v-if="!loaded">
        <q-avatar size="lg" color="grey-5">
          <q-icon name="fas fa-sync fa-spin" />
        </q-avatar>
      </div>
    </h2>

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
          <tr v-for="(control, index) in sortedControlResults" :key="control.process_id">
            <td class="text-center" :class="{ 'new-day-separator': newDayRows.has(index) }">
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
            <td class="text-left" :class="{ 'new-day-separator': newDayRows.has(index) }">
              <div class="text-blue-grey-7">
                <strong>{{ toDateString(control.start_date) }}</strong>
                <small class="text-grey-7 q-px-sm">{{ toTimeString(control.start_date) }}</small>
              </div>
            </td>
            <td class="text-right" :class="{ 'new-day-separator': newDayRows.has(index) }">{{ round(control.duration_minutes, 1) }} min</td>
            <td class="text-center text-weight-bold text-blue-grey-7" :class="{ 'new-day-separator': newDayRows.has(index) }">{{ control.process_id }}</td>
            <td class="text-left text-weight-bold text-teal" :class="{ 'new-day-separator': newDayRows.has(index) }">
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
            <td class="text-left text-weight-bold text-blue-grey-7" :class="{ 'new-day-separator': newDayRows.has(index) }">
              {{ toDateString(control.date_from) }}
            </td>
            <td class="text-left text-weight-bold text-blue-grey-7" :class="{ 'new-day-separator': newDayRows.has(index) }">
              {{ toDateString(control.date_to) }}
            </td>
            <td class="text-right" :class="{ 'new-day-separator': newDayRows.has(index) }">
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
            <td class="text-right" :class="{ 'new-day-separator': newDayRows.has(index) }">
              {{ formatNumber(control.fetched_number_b) }}
            </td>
            <td class="text-right" :class="{ 'new-day-separator': newDayRows.has(index) }">
              <span v-if="control.error_number_a > 0" class="cursor-pointer text-red" @click="copyResultsSql(control, 'A')">
                {{ formatNumber(control.error_number_a) }}
              </span>
              <span v-else>
                {{ formatNumber(control.error_number_a) }}
              </span>
            </td>
            <td class="text-right" :class="{ 'new-day-separator': newDayRows.has(index) }">
              <span v-if="control.error_number_b > 0" class="cursor-pointer text-red" @click="copyResultsSql(control, 'B')">
                {{ formatNumber(control.error_number_b) }}
              </span>
              <span v-else>
                {{ formatNumber(control.error_number_b) }}
              </span>
            </td>
            <td class="text-right" :class="{ 'new-day-separator': newDayRows.has(index) }">
              <span v-if="control.error_level_a > 0" class="cursor-pointer text-red" @click="copyResultsSql(control, 'A')">
                {{ formatNumber(control.error_level_a, 2) }}%
              </span>
              <span v-else> {{ formatNumber(control.error_level_a, 2) }}% </span>
            </td>
            <td class="text-right" :class="{ 'new-day-separator': newDayRows.has(index) }">
              <span v-if="control.error_level_b > 0" class="cursor-pointer text-red" @click="copyResultsSql(control, 'B')">
                {{ formatNumber(control.error_level_b, 2) }}%
              </span>
              <span v-else> {{ formatNumber(control.error_level_b, 2) }}% </span>
            </td>
            <td class="text-right" :class="{ 'new-day-separator': newDayRows.has(index) }">
              <q-icon v-if="control.prerequisite_value == 0" class="cursor-pointer text-red" name="fas fa-stop">
                <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]"> Prerequisite SQL value is 0 </q-tooltip>
              </q-icon>
              <q-icon v-if="control.prerequisite_value" class="cursor-pointer text-green" name="fas fa-play">
                <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]"> Prerequisite SQL value is {{ control.prerequisite_value }} </q-tooltip>
              </q-icon>
            </td>
            <td class="text-left" :class="{ 'new-day-separator': newDayRows.has(index) }">
              <q-chip clickable class="cursor-pointer" @click="!filter.status.includes(control.status) && filter.status.push(control.status)">
                <q-avatar :icon="runStatus(control.status).icon" :color="runStatus(control.status).color" text-color="white" />
                {{ runStatus(control.status).label }}
              </q-chip>
            </td>
            <td class="text-left" :class="{ 'new-day-separator': newDayRows.has(index) }" style="width: 50px">
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
import { mapActions, mapGetters, mapState } from "vuex";
import RunControlDialog from "./RunControlDialog.vue";
import RunLogDialog from "./RunLogDialog.vue";
import { notifyError } from "../api";
import { ACTIVE_RUN_STATUSES, CONTROL_TYPE_OPTIONS, RUN_STATUS_OPTIONS, controlTypeColor, runStatus } from "../constants";
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
        await this.updateControlResults();
        this.loaded = true;
      } catch (error) {
        notifyError("Failed to load control runs.", error);
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
    ...mapState(["controlResults"]),
    ...mapGetters(["getSearch"]),
    sortedControlResults() {
      return sortRows(this.filteredControlResults, this.getSortValue, this.sort.dir);
    },
    // Indexes of rows whose start date differs from the previous row, drawn with a separator line.
    newDayRows() {
      const rows = this.sortedControlResults;
      return new Set(rows.map((row, index) => index).filter((index) => index > 0 && toDateString(rows[index - 1].start_date) !== toDateString(rows[index].start_date)));
    },
    filteredControlResults() {
      const s = this.getSearch ? this.getSearch.toUpperCase() : null;
      const name = this.filter.control_name ? this.filter.control_name.toUpperCase() : null;
      return this.controlResults.filter(
        (item) =>
          (!s || (item.control_name || "").toUpperCase().includes(s)) &&
          (!name || (item.control_name || "").toUpperCase().includes(name)) &&
          (!this.filter.type || item.control_type === this.filter.type) &&
          (this.filter.status.length === 0 || this.filter.status.includes(item.status))
      );
    },
    filteredControlResultsLen() {
      return this.filteredControlResults.length;
    },
  },
  mounted() {
    this.stopLiveUpdates = liveRefetch("runs:changed", this.updateControlResults);
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

.new-day-separator {
  border-top: 2px solid #cfd8dc !important;
}

.sortable {
  cursor: pointer;
  user-select: none;
}
</style>
