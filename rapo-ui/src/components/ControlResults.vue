<template>
  <q-page class="column no-wrap" :style-fn="fillViewportToBottom">
    <div class="row items-end" :class="activeFilters.length ? 'q-mb-sm' : 'q-mb-lg'">
      <h2 class="row items-center no-wrap text-no-wrap q-gutter-lg q-mb-none">
        <div>Control results</div>
        <div><day-navigator :day="day" :today="serverToday" @go="goToDay" /></div>
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

    <filter-chips v-if="hasDay" :filters="activeFilters" :shown="`${filteredControlResults.length} of ${controlResults.length} runs`" class="q-mb-sm" @clear="clearFilters" />

    <!-- Runs per hour, following every filter but the hour, which a click picks. -->
    <hour-heatmap v-if="hasDay" :rows="heatmap" :selected="filter.hour" unit="run(s)" corner="warnings" class="q-mb-md" @select="(hour) => (filter.hour = hour)" />

    <run-table
      :runs="filteredControlResults"
      :sort="sort"
      :columns="{ type: true, name: true }"
      filterable
      :refresh="refreshControlResults"
      :loading="!hasDay && !loadError"
      :error="!hasDay && loadError"
      :empty-text="controlResults.length ? 'No runs match the filters' : `No runs on ${dayTitle}`"
      :filtered-name="filter.control_name"
      :has-kpis="kpiControlIds ? (run) => kpiControlIds.has(run.control_id) : null"
      @filter="applyRowFilter"
      @calculate-kpis="openKpiCalculate">
      <!-- A process ID searched for that is not on this day: its day is looked up on request. -->
      <template v-if="searchedProcessId" #empty>
        <span v-if="missingRun === searchedProcessId">No run {{ searchedProcessId }}</span>
        <span v-else>
          Run {{ searchedProcessId }} is not on {{ dayTitle }} &middot;
          <a href="#" class="text-teal-8 text-weight-bold" @click.prevent="goToRunDay(searchedProcessId)">Go to its day</a>
        </span>
      </template>
    </run-table>
    <kpi-calculate-dialog ref="kpiCalculate" />
  </q-page>
</template>

<script>
import { mapActions, mapGetters, mapState } from "vuex";
import DayNavigator from "./DayNavigator.vue";
import FilterChips from "./FilterChips.vue";
import HourHeatmap from "./HourHeatmap.vue";
import KpiCalculateDialog from "./KpiCalculateDialog.vue";
import RunSummary from "./RunSummary.vue";
import RunTable from "./RunTable.vue";
import { api, notifyError } from "../api";
import { runStatus } from "../constants";
import { liveRefetch } from "../socket";
import { dayTitle, toDateString } from "../utils/format";
import { hourRange } from "../utils/files";
import { runHeatmapRows, runHour, runMatchesSearch } from "../utils/runs";
import { fillViewportToBottom } from "../utils/layout";
import { listFilter, searchFilter, valueFilter } from "../utils/filters";
import persistFilters from "../mixins/persistFilters";

// Kept alive (App.vue), so it is built once; activated/deactivated start and stop its live refresh.
export default {
  name: "ControlResults",
  mixins: [persistFilters("results", ["filter", "sort"])],
  components: {
    DayNavigator,
    FilterChips,
    HourHeatmap,
    KpiCalculateDialog,
    RunSummary,
    RunTable,
  },
  data() {
    return {
      active: false,
      refreshing: false,
      loadError: false,
      filter: {
        control_name: null,
        type: null,
        status: [],
        warnings: null,
        hour: null,
      },
      // The process ID found to have no run by "Go to its day".
      missingRun: null,
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
    // The day a searched process ID ran on, opened with the search kept; a run that does not exist says so instead.
    async goToRunDay(processId) {
      try {
        const run = await api("get-control-run", { params: { process_id: processId } });
        const day = toDateString(run.start_date || run.added);
        if (day && day !== this.day) {
          this.goToDay(day);
        }
      } catch (error) {
        if (error.status === 404) {
          this.missingRun = processId;
        } else {
          notifyError(`Failed to find run ${processId}.`, error);
        }
      }
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
      // The magnifier of the name filtered by clears it.
      if (control_name) this.filter.control_name = this.filter.control_name === control_name ? null : control_name;
    },
    // Every filter and the header search; the sort stays.
    clearFilters() {
      this.filter.control_name = null;
      this.filter.type = null;
      this.filter.status = [];
      this.filter.warnings = null;
      this.filter.hour = null;
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
        ...valueFilter("hour", "Hour", filter.hour, () => (filter.hour = null), { label: filter.hour === null ? null : hourRange(filter.hour) }),
        ...searchFilter(this.$store),
      ];
    },
    // The runs that pass every filter but the hour, which the heatmap picks.
    unhouredControlResults() {
      const name = this.filter.control_name ? this.filter.control_name.toUpperCase() : null;
      // Until the requested day has loaded, the store still holds the previous one.
      if (!this.hasDay) {
        return [];
      }
      return this.controlResults.filter(
        (item) =>
          runMatchesSearch(item, this.getSearch) &&
          (!name || (item.control_name || "").toUpperCase() === name) &&
          (!this.filter.type || item.control_type === this.filter.type) &&
          (this.filter.status.length === 0 || this.filter.status.includes(item.status)) &&
          (!this.filter.warnings || item.has_warning)
      );
    },
    filteredControlResults() {
      const hour = this.filter.hour;
      return hour === null ? this.unhouredControlResults : this.unhouredControlResults.filter((item) => runHour(item) === hour);
    },
    heatmap() {
      return runHeatmapRows(this.unhouredControlResults);
    },
    // The header search when it is a process ID; only then can an empty table be a run of another day.
    searchedProcessId() {
      const search = (this.getSearch || "").trim();
      return /^\d+$/.test(search) ? search : null;
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
        this.filter.hour = null;
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
