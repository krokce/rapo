<template>
  <div class="dashboard">
    <analysis-layout ref="layout" :sections="railSections" rail-row>
      <template #end>
        <span class="dashboard__asof q-mr-sm" :title="serverTime ? `Server time ${toDateTimeString(serverTime)}` : ''">
          <template v-if="serverTime">As of {{ toDateTimeString(serverTime).slice(11, 16) }}</template>
        </span>
        <q-chip
          v-for="item in spans"
          :key="item.value"
          clickable
          dense
          :class="{ 'chip-selected': span === item.value }"
          :title="item.title"
          class="dashboard__span"
          @click="setSpan(item.value)">
          {{ item.label }}
        </q-chip>
        <q-btn flat dense no-caps size="sm" color="grey-8" icon="fas fa-th-large" label="Panels" class="q-ml-sm" aria-label="Show or hide panels">
          <q-badge v-if="layout.hidden.length" color="blue-grey-5" floating rounded>{{ layout.hidden.length }}</q-badge>
          <q-menu anchor="bottom right" self="top right">
            <q-list dense style="min-width: 240px">
              <q-item-label header>Hidden panels</q-item-label>
              <q-item v-if="!hiddenPanels.length">
                <q-item-section class="text-grey-7">Every panel is shown.</q-item-section>
              </q-item>
              <q-item v-for="panel in hiddenPanels" :key="panel.id" clickable @click="show(panel.id)">
                <q-item-section avatar><q-icon name="fas fa-plus" size="12px" color="teal" /></q-item-section>
                <q-item-section>{{ panel.title }}</q-item-section>
                <q-item-section side class="text-caption">{{ sectionLabel(panel.section) }}</q-item-section>
              </q-item>
              <q-separator />
              <q-item v-close-popup clickable @click="resetLayout">
                <q-item-section avatar><q-icon name="fas fa-undo" size="12px" /></q-item-section>
                <q-item-section>Reset layout</q-item-section>
              </q-item>
            </q-list>
          </q-menu>
        </q-btn>
      </template>
      <analysis-section v-for="section in shownSections" :id="section.id" :key="section.id" :title="section.label" :icon="section.icon">
        <template #facts>
          <span v-for="fact in sectionFacts(section.id)" :key="fact.text" class="q-mr-md" :class="fact.class" :title="fact.title">{{ fact.text }}</span>
        </template>
        <template v-if="section.id === 'files' && summary" #actions>
          <q-btn flat dense round size="sm" color="grey-7" icon="fas fa-sync" :loading="refreshingSummary || summary.refreshing" aria-label="Refresh the file summary" @click="refreshSummary">
            <q-tooltip anchor="top middle" self="bottom middle" max-width="320px">
              Sum the file log's past days of this span again (the scheduler's maintenance does it for the last 7 days)
            </q-tooltip>
          </q-btn>
        </template>

        <div class="dashboard__grid">
          <dashboard-panel
            v-for="(panel, index) in sectionPanels(section.id)"
            :key="panel.id"
            :panel="panel"
            :first="index === 0"
            :last="index === sectionPanels(section.id).length - 1"
            :loading="isLoading(panel)"
            :error="panelError(panel)"
            :empty="panelEmpty(panel)"
            :empty-icon="panelEmptyIcon(panel)"
            :skeleton-height="panel.height ? panel.height - 52 : 130"
            @move="(delta) => move(panel.id, delta)"
            @hide="hide(panel.id)"
            @drop="(id) => drop(id, panel.id)">
            <template v-if="panel.id === 'files-loading' && parts.files && parts.files.throughput" #actions>
              <q-select
                v-model="loadingSource"
                :options="loadingOptions"
                emit-value
                map-options
                dense
                borderless
                options-dense
                use-input
                hide-selected
                fill-input
                input-debounce="0"
                class="dashboard__source dash-text"
                aria-label="Datasource of the Loading charts"
                @filter="filterSources" />
            </template>
            <template v-if="panel.id === 'files-datasources' && parts.files && parts.files.datasources && parts.files.datasources.scanned" #facts>
              <span title="Files in the input directories of the datasources, as last scanned">{{ formatNumber(parts.files.datasources.totals.waiting || 0) }} files waiting</span>
            </template>

            <stat-tiles v-if="panel.id === 'tiles'" :tiles="parts.tiles" :scheduler="schedulerStatus" :health="instanceHealth" :now="now" @open="openTile" />

            <heat-strip
              v-else-if="panel.id === 'run-timeline'"
              :rows="runTimelineRows"
              :columns="timelineColumns(parts.timeline)"
              :label-width="96"
              :cell-height="22"
              numbers
              unit="run(s)"
              @pick="pickRunCell" />
            <donut-chart v-else-if="panel.id === 'run-status'" :items="runStatusItems" center-label="runs" :height="150" @pick="pickStatus" />
            <donut-chart v-else-if="panel.id === 'run-types'" :items="runTypeItems" center-label="runs" :height="150" @pick="({ key }) => go({ path: '/results', query: { type: key } })" />
            <donut-chart v-else-if="panel.id === 'run-triggers'" :items="runTriggerItems" center-label="runs" :height="150" @pick="({ key }) => go({ path: '/results', query: { trigger: key } })" />
            <bar-list v-else-if="panel.id === 'run-slowest'" :rows="slowestRows" :parts="slowestParts" :format="minutesText" :row-height="20" :label-width="170" @pick="openControl" />
            <mini-trend
              v-else-if="panel.id === 'run-volume'"
              :buckets="parts.runs.buckets"
              :unit="parts.runs.unit"
              :series="volumeSeries"
              :note="volumeNote"
              :headline="compactNumber(volumeTotals.fetched)"
              :caption="`fetched · ${compactNumber(volumeTotals.discrepancies)} discrepancies`"
              :height="128"
              fill
              @pick="pickRuns" />
            <heat-strip
              v-else-if="panel.id === 'run-heatmap'"
              :rows="weekdayRows"
              :columns="hourColumns"
              :label-width="56"
              :cell-height="20"
              scale="all"
              :clickable="false"
              numbers />

            <scheduler-strip v-else-if="panel.id === 'scheduler'" :data="parts.scheduler" :status="schedulerStatus" :now="now" @open="go" />

            <heat-strip
              v-else-if="panel.id === 'files-timeline'"
              :rows="fileTimelineRows"
              :columns="timelineColumns(parts.files)"
              :label-width="96"
              :cell-height="22"
              numbers
              unit="file(s)"
              @pick="pickFileCell" />
            <div v-else-if="panel.id === 'files-top'" class="dashboard__pair">
              <div>
                <div class="dashboard__list-title">By records loaded</div>
                <donut-chart :items="topLoadedItems" center-label="records" :format="compactNumber" :height="150" @pick="openDatasource" />
              </div>
              <div>
                <div class="dashboard__list-title">By number of files</div>
                <donut-chart :items="topFileItems" center-label="files" :format="compactNumber" :height="150" @pick="openDatasource" />
              </div>
              <div>
                <div class="dashboard__list-title">By loading time</div>
                <donut-chart :items="topRuntimeItems" center-label="load time" :format="compactDuration" :exact-format="durationText" :center-format="compactDuration" :height="150" @pick="openDatasource" />
              </div>
            </div>
            <donut-chart v-else-if="panel.id === 'files-datasources'" :items="datasourceItems" center-label="datasources" :height="150" @pick="pickDatasourceState" />
            <files-loading v-else-if="panel.id === 'files-loading'" :data="parts.files" :source="loadingSource" @pick="({ bucket }) => go(filesLink(bucket, parts.files.unit, databaseToday))" />

            <kpi-alarm-heatmap v-else-if="panel.id === 'kpi-heatmap'" :data="parts.kpis" @pick="openKpis" @open-log="openControl({ key: $event.control_id })" />

            <health-mini-tiles v-else-if="panel.id === 'health-tiles'" :span="span" :active="active" @open="(group) => openHealth(group)" />
          </dashboard-panel>
        </div>
      </analysis-section>
    </analysis-layout>
  </div>
</template>

<script>
import { mapState } from "vuex";
import { api, notifyError } from "../../api";
import { FILE_STATUSES, controlType, runStatus } from "../../constants";
import { liveRefetch } from "../../socket";
import {
  DASHBOARD_PANELS,
  DASHBOARD_SECTIONS,
  DASHBOARD_SPANS,
  defaultLayout,
  dropPanel,
  filesLink,
  hidePanel,
  movePanel,
  neededParts,
  readLayout,
  bucketColumns,
  readSpan,
  resultsLink,
  saveLayout,
  saveSpan,
  sectionPanels,
  showPanel,
} from "../../utils/dashboard";
import { compactDuration, compactNumber, durationText, formatDuration, formatNumber, toDateTimeString } from "../../utils/format";
import { triggerOfKey } from "../../utils/runs";
import AnalysisLayout from "../analysis/AnalysisLayout.vue";
import AnalysisSection from "../analysis/AnalysisSection.vue";
import BarList from "./BarList.vue";
import DashboardPanel from "./DashboardPanel.vue";
import DonutChart from "./DonutChart.vue";
import FilesLoading, { ALL_SOURCES } from "./FilesLoading.vue";
import HealthMiniTiles from "./HealthMiniTiles.vue";
import HeatStrip from "./HeatStrip.vue";
import KpiAlarmHeatmap from "./KpiAlarmHeatmap.vue";
import MiniTrend from "./MiniTrend.vue";
import SchedulerStrip from "./SchedulerStrip.vue";
import StatTiles from "./StatTiles.vue";

// The parts that follow the span, and those asked for first (today, the runs by status).
const SPAN_PARTS = ["timeline", "runs", "files", "kpis"];
const FIRST_PARTS = ["tiles", "timeline"];
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
// The statuses of a request done, all grey on the Files page, told apart side by side.
const DONE_STATUS_COLORS = { RECYCLED: "blue-grey-4", RELOADED: "grey-6", DELETED: "blue-grey-7" };
// The slices of the top datasources (one each, the rest as Others).
const TOP_SLICES = 7;
// By datasource, the same in both donuts of Top datasources: enough for two different top lists.
const TOP_COLORS = ["teal-6", "blue-6", "indigo-4", "purple-4", "amber-8", "cyan-7", "light-green-7", "orange-7", "pink-4", "brown-4", "deep-purple-3", "lime-8", "green-9", "light-blue-8"];
// The datasources by state, each in one (rapo/dashboard/files.py _lanes).
const DATASOURCE_STATES = [
  { key: "stalled", label: "Stalled", color: "red-5", icon: "fas fa-hourglass-end", title: "Active datasources whose oldest waiting file waits too long (the last scan)" },
  { key: "delivering", label: "Delivering", color: "green", icon: "fas fa-check-circle", title: "Active datasources with files in the span" },
  { key: "silent", label: "Silent", color: "blue-grey-4", icon: "fas fa-moon", title: "Active datasources without any file in the span" },
  { key: "disabled", label: "Disabled", color: "grey-5", icon: "fas fa-ban", title: "Datasources on lane 0, which PDI Core does not load" },
];

// The Dashboard: what is going on in this instance, at a glance and live. Sections of panels (utils/dashboard.js) that
// fill the width, each panel showing a part of get-dashboard; the panels a browser hides are not fetched. The present
// (tiles, the runs per bucket) is asked for first, the rest beside it. Each live event refetches only the parts it
// changes.
export default {
  name: "DashboardPage",
  components: {
    AnalysisLayout,
    AnalysisSection,
    BarList,
    DashboardPanel,
    DonutChart,
    FilesLoading,
    HealthMiniTiles,
    HeatStrip,
    KpiAlarmHeatmap,
    MiniTrend,
    SchedulerStrip,
    StatTiles,
  },
  data() {
    return {
      active: false,
      span: readSpan(),
      spans: DASHBOARD_SPANS,
      layout: readLayout(),
      // get-dashboard by part (frozen), the error of a part that failed, and the span each was read for.
      parts: {},
      errors: {},
      serverTime: null,
      refreshingSummary: false,
      // The datasource of the Loading panel, and what is typed in its select.
      loadingSource: ALL_SOURCES,
      loadingSearch: "",
      now: Date.now(),
    };
  },
  computed: {
    ...mapState(["schedulerStatus", "instanceHealth", "envInfo"]),
    shownSections() {
      return DASHBOARD_SECTIONS.filter((section) => (!section.available || section.available(this.envInfo)) && this.sectionPanels(section.id).length);
    },
    railSections() {
      return this.shownSections.map((section) => ({ id: section.id, label: section.label, icon: section.icon }));
    },
    shownPanels() {
      return this.shownSections.flatMap((section) => this.sectionPanels(section.id));
    },
    needed() {
      return neededParts(this.shownPanels);
    },
    hiddenPanels() {
      return DASHBOARD_PANELS.filter((panel) => this.layout.hidden.includes(panel.id));
    },
    serverToday() {
      return this.serverTime ? this.serverTime.slice(0, 10) : null;
    },
    databaseToday() {
      const files = this.parts.files;
      return files && files.database_time ? String(files.database_time).slice(0, 10) : null;
    },
    summary() {
      return this.parts.files && this.parts.files.summary;
    },
    // The runs of the span by status, from the timeline's series.
    runStatusItems() {
      return (this.parts.timeline.status || []).map((item) => {
        const status = runStatus(item.code);
        return { key: item.code || "void", label: status.label, color: status.color, icon: status.icon, value: item.counts.reduce((sum, value) => sum + value, 0) };
      });
    },
    // A row per status over the buckets.
    runTimelineRows() {
      return (this.parts.timeline.status || []).map((item) => {
        const status = runStatus(item.code);
        return { key: item.code || "void", label: status.label, color: status.color, total: item.counts.reduce((sum, value) => sum + value, 0), cells: item.counts.map((count) => ({ count })) };
      });
    },
    fileTimelineRows() {
      return this.parts.files.status.map((item) => {
        const info = this.fileStatusInfo(item.code);
        return { key: item.code, label: info.label, color: info.color, total: item.counts.reduce((sum, value) => sum + (value || 0), 0), cells: item.counts.map((count) => ({ count })) };
      });
    },
    runTypeItems() {
      return Object.entries(this.parts.runs.by_type).map(([type, values]) => {
        const info = controlType(type);
        return { key: type, label: type, color: info.color, icon: info.icon, value: values.runs, title: `${info.label}: ${values.runs} runs, ${values.errors} in error` };
      });
    },
    runTriggerItems() {
      return Object.entries(this.parts.runs.by_trigger)
        .sort((a, b) => b[1] - a[1])
        .map(([key, value]) => {
          const info = triggerOfKey(key);
          return { key, label: info.label, color: info.color, icon: info.icon, value };
        });
    },
    slowestParts() {
      return [{ key: "avg", label: "Average run", color: "indigo-4" }];
    },
    slowestRows() {
      return this.parts.runs.slowest.map((row) => ({
        key: row.control_id,
        label: row.control_name,
        segments: [row.avg_minutes],
        colors: [controlType(row.control_type).color],
        text: formatDuration(row.avg_minutes * 60),
        title: `Longest ${formatDuration(row.max_minutes * 60)} · ${row.runs} runs done`,
      }));
    },
    volumeSeries() {
      const volume = this.parts.runs.volume;
      return [
        { key: "fetched", label: "Fetched", color: "blue-grey-5", values: volume.fetched, type: "area", format: compactNumber },
        { key: "discrepancies", label: "Discrepancies", color: "red-6", values: volume.discrepancies, type: "area", opacity: 0.4, format: compactNumber },
      ];
    },
    // The datasources of the Loading panel's select, filtered by what is typed.
    loadingOptions() {
      const sources = (this.parts.files && this.parts.files.throughput && this.parts.files.throughput.sources) || [];
      const all = [{ label: "All datasources", value: ALL_SOURCES }, ...sources.map((source) => ({ label: source.sourcename || String(source.sourceid), value: source.sourceid }))];
      const text = this.loadingSearch.toLowerCase();
      return text ? all.filter((option) => option.label.toLowerCase().includes(text)) : all;
    },
    volumeTotals() {
      const sum = (values) => values.reduce((total, value) => total + (value || 0), 0);
      return { fetched: sum(this.parts.runs.volume.fetched), discrepancies: sum(this.parts.runs.volume.discrepancies) };
    },
    // The runs by weekday and hour on one scale, the count in each cell; the errors only in its tooltip.
    weekdayRows() {
      const grid = this.parts.runs.hour_weekday;
      return WEEKDAYS.map((label, day) => ({
        key: label,
        label,
        color: "blue-6",
        cells: grid.count[day].map((count, hour) => {
          const errors = grid.errors[day][hour];
          const title = `${label} ${this.hourColumns[hour].title}: ${formatNumber(count)} run(s)${errors ? `, ${formatNumber(errors)} in error` : ""}`;
          return { count, title };
        }),
      }));
    },
    // The 24 hours, labeled every 3rd.
    hourColumns() {
      return Array.from({ length: 24 }, (_, hour) => {
        const text = String(hour).padStart(2, "0");
        return { label: hour % 3 === 0 ? text : "", title: `${text}:00–${String((hour + 1) % 24).padStart(2, "0")}:00` };
      });
    },
    topLoadedItems() {
      const files = this.parts.files;
      const total = files.records.write.reduce((sum, value) => sum + (value || 0), 0);
      return this.topItems(files.top_loaded, "records", total, (row) => `${row.sourcename || row.sourceid}: ${formatNumber(row.records)} records loaded, ${formatNumber(row.files)} files`);
    },
    // The files loaded (SUCCESS) of the span by datasource.
    topFileItems() {
      const files = this.parts.files;
      const success = files.status.find((item) => item.code === "SUCCESS");
      const total = success ? success.counts.reduce((sum, value) => sum + (value || 0), 0) : 0;
      return this.topItems(files.top_files, "success", total, (row) => `${row.sourcename || row.sourceid}: ${formatNumber(row.success)} files loaded, ${formatNumber(row.records)} records loaded`);
    },
    // The loader's time (RUNTIME of the files of every status) of the span by datasource.
    topRuntimeItems() {
      const files = this.parts.files;
      return this.topItems(files.top_runtime || [], "runtime", files.runtime_total || 0, (row) => `${row.sourcename || row.sourceid}: ${durationText(row.runtime)} loading, ${formatNumber(row.files)} files`);
    },
    // A color per datasource of any top list, the records' first.
    topColors() {
      const files = this.parts.files;
      const colors = {};
      for (const [rows, field] of [
        [files.top_loaded, "records"],
        [files.top_files, "success"],
        [files.top_runtime || [], "runtime"],
      ]) {
        rows
          .filter((row) => row[field])
          .slice(0, TOP_SLICES)
          .forEach((row) => {
            if (!(row.sourceid in colors)) {
              colors[row.sourceid] = TOP_COLORS[Object.keys(colors).length % TOP_COLORS.length];
            }
          });
      }
      return colors;
    },
    datasourceItems() {
      const states = (this.parts.files.datasources && this.parts.files.datasources.states) || {};
      return DATASOURCE_STATES.map((state) => ({ ...state, value: states[state.key] || 0 }));
    },
  },
  watch: {
    // A datasource no longer in the span falls back to all.
    "parts.files"(files) {
      const sources = (files && files.throughput && files.throughput.sources) || [];
      if (this.loadingSource !== ALL_SOURCES && !sources.some((source) => source.sourceid === this.loadingSource)) {
        this.loadingSource = ALL_SOURCES;
      }
    },
    // A panel shown again needs its part.
    needed(parts, previous) {
      const added = parts.filter((part) => !(previous || []).includes(part) && !this.parts[part]);
      if (this.active && added.length) {
        this.fetch(added);
      }
    },
  },
  activated() {
    this.active = true;
    const stops = [
      liveRefetch("runs:changed", () => {
        this.fetch(["tiles", "timeline", "runs", "kpis"], true);
        // RACS_KPI_PKG stores a run's KPIs after the run is done: read them again a little later.
        clearTimeout(this.kpiTimer);
        this.kpiTimer = setTimeout(() => this.fetch(["kpis", "tiles"], true), 15000);
      }),
      // The tiles carry the scheduler's next fire.
      liveRefetch("controls:changed", () => this.fetch(["tiles", "runs", "kpis", "scheduler"], true)),
      liveRefetch("scheduler:changed", () => this.fetch(["tiles", "scheduler"], true)),
      // The file log, its summary, the datasources' lanes and the last scan (files waiting, stalled).
      liveRefetch("datasources:changed", () => this.fetch(["files", "tiles"], true), {
        filter: (payload) => ["files", "summary", "config", "status"].includes(payload.kind),
        interval: 15000,
      }),
    ];
    this.stopLiveUpdates = () => stops.forEach((stop) => stop());
    this.loadAll();
    // The ages move on; a new hour moves the scheduler's 24 hours and the 24h span, a new day every span.
    this.clock = setInterval(() => {
      this.now = Date.now();
      const stamp = this.stamp();
      if (stamp !== this.lastStamp) {
        this.lastStamp = stamp;
        const spanParts = this.span === "24h" || stamp.slice(0, 10) !== this.lastDay ? SPAN_PARTS : [];
        this.fetch([...FIRST_PARTS, "scheduler", ...spanParts], true);
        this.lastDay = stamp.slice(0, 10);
      }
    }, 30000);
  },
  deactivated() {
    this.active = false;
    this.stopLiveUpdates();
    clearInterval(this.clock);
    clearTimeout(this.kpiTimer);
  },
  methods: {
    compactDuration,
    compactNumber,
    durationText,
    formatNumber,
    toDateTimeString,
    sectionPanels(section) {
      return sectionPanels(this.layout, section);
    },
    sectionLabel(id) {
      return DASHBOARD_SECTIONS.find((section) => section.id === id).label;
    },
    // The hour of the browser, which tells when the server's hour or day may have turned.
    stamp() {
      return new Date().toISOString().slice(0, 13);
    },
    // Everything: the present first, the span beside it.
    loadAll() {
      this.lastStamp = this.stamp();
      this.lastDay = this.lastStamp.slice(0, 10);
      const first = FIRST_PARTS.filter((part) => this.needed.includes(part));
      const rest = this.needed.filter((part) => !first.includes(part));
      Promise.all([this.fetch(first), this.fetch(rest)]).then(() => this.scrollToHash());
    },
    // Fetches parts (those shown only) for the current span; an answer to an older request of a part is dropped.
    async fetch(names, quiet = false) {
      const wanted = [...new Set(names)].filter((part) => this.needed.includes(part));
      if (!wanted.length) {
        return;
      }
      this.sequence = (this.sequence || 0) + 1;
      const sequence = this.sequence;
      this.latest = { ...(this.latest || {}), ...Object.fromEntries(wanted.map((part) => [part, sequence])) };
      try {
        const data = await api("get-dashboard", { params: { parts: wanted.join(","), span: this.span }, loadingBar: !quiet });
        this.serverTime = data.server_time;
        const parts = { ...this.parts };
        const errors = { ...this.errors };
        Object.entries(data.parts).forEach(([part, value]) => {
          if (this.latest[part] !== sequence) {
            return;
          }
          if (value && !Array.isArray(value) && value.error) {
            errors[part] = value.error;
          } else {
            parts[part] = Object.freeze(value);
            delete errors[part];
          }
        });
        this.parts = parts;
        this.errors = errors;
      } catch (error) {
        if (!quiet) {
          notifyError("Failed to load the dashboard.", error);
        }
        const errors = { ...this.errors };
        wanted.filter((part) => this.latest[part] === sequence && !this.parts[part]).forEach((part) => (errors[part] = error.message));
        this.errors = errors;
      }
    },
    scrollToHash() {
      const id = (this.$route.hash || "").slice(1);
      if (id && this.$refs.layout) {
        this.$nextTick(() => this.$refs.layout.scrollTo(id, false));
      }
    },
    setSpan(span) {
      if (span === this.span) {
        return;
      }
      this.span = span;
      saveSpan(span);
      this.fetch(SPAN_PARTS);
    },
    isLoading(panel) {
      return Boolean(panel.part) && !this.parts[panel.part] && !this.errors[panel.part];
    },
    panelError(panel) {
      return (panel.part && !this.parts[panel.part] && this.errors[panel.part]) || null;
    },
    // The note a panel shows instead of an empty chart.
    panelEmpty(panel) {
      const part = panel.part && this.parts[panel.part];
      if (!part) {
        return null;
      }
      const sum = (values) => (values || []).reduce((total, value) => total + (value || 0), 0);
      switch (panel.id) {
        case "run-status":
        case "run-timeline":
          return sum(part.total) ? null : "No run in this span.";
        case "run-types":
        case "run-triggers":
          return Object.keys(part.by_type).length ? null : "No run in this span.";
        case "run-slowest":
          return part.slowest.length ? null : "No run finished in this span.";
        case "run-volume":
          return sum(part.volume.fetched) ? null : "Nothing fetched in this span.";
        case "files-timeline":
        case "files-loading":
        case "files-top":
          if (part.available === false) return "The file log is not available.";
          return part.status.length ? null : "No file in this span.";
        case "files-datasources":
          if (part.available === false) return "The file log is not available.";
          return part.datasources.totals.datasources ? null : "No datasource configured.";
        case "kpi-heatmap":
          if (part.available === false) return "The KPI tables or their history are not available.";
          return part.heatmap.controls.length ? null : "No KPI value stored in this span.";
        default:
          return null;
      }
    },
    panelEmptyIcon() {
      return "fas fa-info-circle";
    },
    // The facts beside a section's title.
    sectionFacts(section) {
      const facts = [];
      const runs = this.parts.runs;
      const scheduler = this.parts.scheduler;
      const files = this.parts.files;
      const kpis = this.parts.kpis;
      if (section === "runs" && runs) {
        const total = Object.values(runs.by_type).reduce((sum, item) => sum + item.runs, 0);
        const errors = Object.values(runs.by_type).reduce((sum, item) => sum + item.errors, 0);
        facts.push({ text: `${formatNumber(total)} runs` });
        if (errors) facts.push({ text: `${formatNumber(errors)} in error (${formatNumber((errors * 100) / total, 1)}%)`, class: "text-negative" });
      }
      if (section === "scheduler" && scheduler) {
        const count = (code) => {
          const item = scheduler.past.events.find((event) => event.code === code);
          return item ? item.counts.reduce((sum, value) => sum + value, 0) : 0;
        };
        const next = scheduler.upcoming.counts.reduce((sum, value) => sum + value, 0);
        facts.push({ text: `${formatNumber(count("STARTED"))} started in 24 h · ${formatNumber(next)} to come`, title: "Whatever the span: the last and the next 24 hours" });
        if (count("FAILED")) facts.push({ text: `${formatNumber(count("FAILED"))} failed`, class: "text-negative" });
      }
      if (section === "files" && files && files.available !== false) {
        const total = files.status.reduce((sum, item) => sum + item.counts.reduce((all, value) => all + (value || 0), 0), 0);
        facts.push({ text: `${formatNumber(total)} files`, title: "Days of the database clock" });
        const missing = files.summary.missing_days.length;
        if (missing) {
          facts.push({
            text: `${missing} day${missing > 1 ? "s" : ""} not summed yet`,
            class: "dashboard__warn",
            title: files.summary.maintenance
              ? "The scheduler's maintenance sums the past days of the file log; Refresh does it now"
              : "No maintenance runs ([SCHEDULER] maintenance_interval is empty): Refresh sums the past days of the file log",
          });
        }
      }
      if (section === "kpis" && kpis && kpis.available) {
        facts.push({ text: `${formatNumber(kpis.alarms)} alarm${kpis.alarms === 1 ? "" : "s"} (level 2–3)`, class: kpis.alarms ? "dashboard__warn" : "" });
      }
      return facts;
    },
    go(location) {
      this.$router.push(location);
    },
    openTile(tile) {
      if (tile.action === "health") {
        this.openHealth("os");
      } else if (tile.section) {
        this.$refs.layout.go(tile.section);
      } else if (tile.link) {
        this.go(tile.link);
      }
    },
    openHealth(group) {
      this.$store.commit("openInstanceDialog", group === "db" ? "health-db" : "health-os");
    },
    openControl({ key }) {
      this.go({ path: `/edit-control/${key}`, query: { tab: "log" } });
    },
    openDatasource({ key }) {
      this.go({ path: `/files-log/${key}` });
    },
    // The first TOP_SLICES rows of a top list as slices, the rest of `total` as Others (opens nothing).
    topItems(rows, field, total, title) {
      const items = rows
        .filter((row) => row[field])
        .slice(0, TOP_SLICES)
        .map((row) => ({ key: row.sourceid, label: row.sourcename || String(row.sourceid), color: this.topColors[row.sourceid], value: row[field], title: title(row) }));
      const others = total - items.reduce((sum, item) => sum + item.value, 0);
      if (items.length && others > 0) {
        items.push({ key: "others", label: "Others", color: "blue-grey-3", value: others, pick: false, title: "The other datasources together" });
      }
      return items;
    },
    // A cell of KPI alarms by control: its KPIs with the cell's run picked.
    openKpis({ control, processId }) {
      const id = control && control.control_id;
      const query = processId ? { tab: "kpi", process_id: String(processId) } : { tab: "kpi" };
      this.go(id ? { path: `/edit-control/${id}`, query } : { path: "/kpi-types" });
    },
    pickStatus({ key }) {
      this.go({ path: "/results", query: key === "void" ? {} : { status: key } });
    },
    // A file status as its chip shows it, the statuses of a request done told apart.
    fileStatusInfo(code) {
      const info = FILE_STATUSES[code] || { label: code, color: "grey-6" };
      return { label: info.label, color: DONE_STATUS_COLORS[code] || info.color, icon: info.icon ? info.icon.replace(" fa-spin", "") : null, title: info.hint || info.label };
    },
    timelineColumns(part) {
      return bucketColumns(part.buckets, part.unit);
    },
    pickRunCell({ row, column }) {
      const filters = row === "void" ? {} : { status: row };
      this.go(resultsLink(this.parts.timeline.buckets[column], this.parts.timeline.unit, this.serverToday, filters));
    },
    pickFileCell({ row, column }) {
      const filters = FILE_STATUSES[row] ? { status: row } : {};
      this.go(filesLink(this.parts.files.buckets[column], this.parts.files.unit, this.databaseToday, filters));
    },
    // The discrepancies of a bucket, % of the records fetched.
    volumeNote(index) {
      const fetched = this.parts.runs.volume.fetched[index];
      const found = this.parts.runs.volume.discrepancies[index];
      return fetched ? `${formatNumber((found * 100) / fetched, 2)}% discrepancies` : "";
    },
    filterSources(text, update) {
      update(() => (this.loadingSearch = text));
    },
    pickRuns({ bucket }) {
      this.go(resultsLink(bucket, this.parts.runs.unit, this.serverToday));
    },
    pickDatasourceState({ key }) {
      const links = {
        stalled: { path: "/datasources", query: { issue: "stalled" } },
        disabled: { path: "/datasources", query: { lane: "0" } },
        delivering: { path: "/files" },
        silent: { path: "/datasources" },
      };
      this.go(links[key]);
    },
    filesLink,
    minutesText(value) {
      return formatDuration(value * 60);
    },
    async refreshSummary() {
      this.refreshingSummary = true;
      try {
        await api("refresh-file-summary", { method: "POST", params: { span: this.span } });
        this.$q.notify({ type: "info", message: "Summing the file log's past days again; the charts follow when it is done." });
      } catch (error) {
        notifyError("Failed to refresh the file summary.", error);
      } finally {
        this.refreshingSummary = false;
        this.fetch(["files"], true);
      }
    },
    setLayout(layout) {
      this.layout = layout;
      saveLayout(layout);
    },
    move(id, delta) {
      this.setLayout(movePanel(this.layout, id, delta));
    },
    drop(id, targetId) {
      this.setLayout(dropPanel(this.layout, id, targetId));
    },
    hide(id) {
      this.setLayout(hidePanel(this.layout, id));
    },
    show(id) {
      this.setLayout(showPanel(this.layout, id));
    },
    resetLayout() {
      this.setLayout(defaultLayout());
    },
  },
};
</script>

<style scoped>
.dashboard__asof {
  font-size: 11px;
  color: var(--rapo-label);
  white-space: nowrap;
}

.dashboard__span {
  min-width: 44px;
  justify-content: center;
}

/* The panels flow in rows and grow to fill them (DashboardPanel). */
.dashboard__grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.dashboard__pair {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 20px;
}

.dashboard__pair > div {
  flex: 1 1 260px;
  min-width: 0;
}

/* The datasource select in the Loading panel's head, as small as the head's text. */
.dashboard__source {
  width: 180px;
}

.dashboard__source :deep(.q-field__control),
.dashboard__source :deep(.q-field__native) {
  min-height: 22px;
  height: 22px;
  padding: 0;
}

.dashboard__source :deep(.q-field__marginal) {
  height: 22px;
}

.dashboard__warn {
  color: var(--rapo-warn);
}

.dashboard__list-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--rapo-strong);
  margin-bottom: 2px;
}
</style>
