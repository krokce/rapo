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
      <run-summary
        v-if="hasDay"
        :runs="controlResults"
        show-types
        show-controls
        clickable
        @filter-type="(type) => (filter.type = type)"
        @filter-status="addStatusFilter"
        @filter-warnings="filter.warnings = true" />
    </div>

    <filter-chips v-if="hasDay" :filters="activeFilters" :shown="`${filteredControlResults.length} of ${controlResults.length} runs`" class="q-mb-md" @clear="clearFilters" />

    <div class="row items-center q-mb-md">
      <q-btn aria-label="Previous day" class="q-mb-md q-mr-xs day-btn" outline color="primary" padding="0 4px" icon="fas fa-chevron-left" :disable="!day" @click="goToDay(previousDay)">
        <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 10]"> Previous day </q-tooltip>
      </q-btn>
      <q-btn class="col-2 q-mb-md q-pa-sm" size="lg" color="primary" icon="fas fa-play-circle" label="Run control" @click="$refs.runControlDialog.open()" />
      <run-control-dialog ref="runControlDialog" :hook="refreshControlResults" />

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

    <run-table
      :runs="filteredControlResults"
      :sort="sort"
      :columns="{ type: true, name: true }"
      filterable
      :refresh="refreshControlResults"
      :loading="!hasDay && !loadError"
      :error="!hasDay && loadError"
      :empty-text="controlResults.length ? 'No runs match the filters' : `No runs on ${day}`"
      :has-kpis="kpiControlIds ? (run) => kpiControlIds.has(run.control_id) : null"
      @filter="applyRowFilter"
      @calculate-kpis="openKpiCalculate" />
    <kpi-calculate-dialog ref="kpiCalculate" />
  </q-page>
</template>

<script>
import { mapActions, mapGetters, mapState } from "vuex";
import FilterChips from "./FilterChips.vue";
import KpiCalculateDialog from "./KpiCalculateDialog.vue";
import RunControlDialog from "./RunControlDialog.vue";
import RunSummary from "./RunSummary.vue";
import RunTable from "./RunTable.vue";
import { api, notifyError } from "../api";
import { CONTROL_TYPE_OPTIONS, RUN_STATUS_OPTIONS, runStatus } from "../constants";
import { liveRefetch } from "../socket";
import { dayTitle, shiftDay } from "../utils/format";
import { fillViewportToBottom } from "../utils/layout";
import { listFilter, searchFilter, valueFilter } from "../utils/filters";
import persistFilters from "../mixins/persistFilters";

// Kept alive (App.vue), so it is built once; activated/deactivated start and stop its live refresh.
export default {
  name: "ControlResults",
  mixins: [persistFilters("results", ["filter", "sort"])],
  components: {
    FilterChips,
    KpiCalculateDialog,
    RunControlDialog,
    RunSummary,
    RunTable,
  },
  data() {
    return {
      controlTypeOptions: CONTROL_TYPE_OPTIONS,
      runStatusOptions: RUN_STATUS_OPTIONS,
      active: false,
      refreshing: false,
      loadError: false,
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
      // The ids of the controls with KPIs, which the row menu offers Calculate KPIs for; null without KPI tables.
      kpiControlIds: null,
    };
  },
  methods: {
    ...mapActions(["updateControlResults"]),
    async refreshKpiControls() {
      if (!(this.getEnvInfo && this.getEnvInfo.kpi_available)) {
        this.kpiControlIds = null;
        return;
      }
      try {
        const usage = await api("get-kpi-type-usage", { loadingBar: false });
        this.kpiControlIds = new Set(usage.map((item) => item.control_id).filter((id) => id != null));
      } catch (error) {
        console.error("KPI usage check failed:", error);
      }
    },
    // The saved statements, in a modal: Results has no draft.
    openKpiCalculate(run) {
      this.$refs.kpiCalculate.open({ controlName: run.control_name, processId: run.process_id });
    },
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
    // The server's today is plain /results, so the menu link and redirects always land on today.
    goToDay(day) {
      this.$router.push({ name: "results", query: day && day !== this.serverToday ? { date: day } : {} });
    },
    addStatusFilter(status) {
      if (!this.filter.status.includes(status)) {
        this.filter.status.push(status);
      }
    },
    // A type or status chip, or the name's magnifier, clicked in the table.
    applyRowFilter({ type, status, control_name }) {
      if (type) this.filter.type = type;
      if (status) this.addStatusFilter(status);
      if (control_name) this.filter.control_name = control_name;
    },
    // Every filter and the header search; the sort stays.
    clearFilters() {
      this.filter.control_name = null;
      this.filter.type = null;
      this.filter.status = [];
      this.filter.warnings = null;
      this.$store.commit("updateSearch", "");
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
    ...mapGetters(["getSearch", "getEnvInfo"]),
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
    // The instance details can arrive after the page was opened.
    "getEnvInfo.kpi_available"() {
      this.refreshKpiControls();
    },
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
    this.stopKpiUpdates = liveRefetch("controls:changed", () => this.refreshKpiControls());
    this.refreshControlResults();
    this.refreshKpiControls();
  },
  deactivated() {
    this.active = false;
    this.stopLiveUpdates();
    this.stopKpiUpdates();
  },
};
</script>
