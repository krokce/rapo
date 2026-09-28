<template>
  <div class="column no-wrap">
    <!-- Laid out like Results: the title with the day and the filter badge, the day's totals and status chips on the right,
         the active filters under it, then the filter row with the day buttons, and the table. -->
    <div class="row items-end" :class="activeFilters.length ? 'q-mb-sm' : embedded ? 'q-mb-md' : 'q-mb-lg'">
      <component :is="embedded ? 'div' : 'h2'" class="row items-center no-wrap text-no-wrap q-gutter-lg q-mb-none" :class="{ 'text-h6': embedded }">
        <slot name="title" />
        <div class="text-grey-6" :class="{ 'results-day': !embedded }">{{ dayTitle }}</div>
        <slot name="after-day" />
        <div v-if="activeFilters.length" class="row items-center">
          <filter-badge :filters="activeFilters" :shown="`${formatNumber(shownFiles.length)} of ${formatNumber(files.length)} files`" @clear="clearFilters" />
        </div>
        <div v-if="loading">
          <q-avatar :size="embedded ? 'md' : 'lg'" color="grey-5">
            <q-icon name="fas fa-sync fa-spin" />
          </q-avatar>
        </div>
      </component>
      <q-space />

      <!-- The day's totals, whatever the filters; a status chip filters by it. -->
      <div class="row items-center justify-end q-gutter-x-md text-blue-grey-8">
        <div v-if="files.length">
          {{ formatNumber(files.length) }} files &middot; {{ compactNumber(totals.read) }} read &middot; {{ compactNumber(totals.written) }} written
          <span :class="{ 'text-red-6': totals.rejected }">&middot; {{ compactNumber(totals.rejected) }} rejected</span>
          <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">
            Records read {{ formatNumber(totals.read) }}, written {{ formatNumber(totals.written) }}, rejected {{ formatNumber(totals.rejected) }}
          </q-tooltip>
        </div>
        <div v-if="statusCounts.length || duplicateCount">
          <q-chip v-for="entry in statusCounts" :key="entry.status" clickable @click="addStatus(entry.status)">
            <q-avatar :icon="fileStatus(entry.status).icon" :color="fileStatus(entry.status).color" text-color="white" />
            <span class="text-weight-bold q-mr-xs">{{ fileStatus(entry.status).label }}</span>({{ formatNumber(entry.count) }})
          </q-chip>
          <q-chip v-if="duplicateCount" clickable @click="duplicate = 'Y'">
            <q-avatar icon="fas fa-clone" color="purple-3" text-color="white" />
            <span class="text-weight-bold q-mr-xs">Duplicate</span>({{ formatNumber(duplicateCount) }})
            <q-tooltip>Files PDI Core flagged as duplicates (DUPLICATE = 1): show only them</q-tooltip>
          </q-chip>
        </div>
      </div>
    </div>
    <filter-chips :filters="activeFilters" class="q-mb-md" />

    <!-- Files per hour, as on the Files page: one row per status and a total, following the other filters. -->
    <file-heatmap v-if="!embedded && files.length" :rows="heatmap" :selected="hour" class="q-mt-sm q-mb-md" @select="(value) => (hour = value)" />

    <div class="row items-center" :class="{ 'q-mb-sm': !embedded }">
      <q-btn class="q-mb-md q-mr-xs day-btn" outline color="primary" padding="0 4px" icon="fas fa-chevron-left" :disable="!day" @click="shiftDay(-1)">
        <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 10]"> Previous day </q-tooltip>
      </q-btn>

      <q-input v-model="search" clearable class="col q-mb-md q-pa-sm name-filter" outlined debounce="200" label="File name" maxlength="200" />

      <q-select
        v-model="statuses"
        class="col-3 q-mb-md q-pa-sm"
        outlined
        options-dense
        emit-value
        map-options
        multiple
        use-chips
        :options="statusOptions"
        label="File status">
      </q-select>

      <q-select
        v-model="duplicate"
        class="col-2 q-mb-md q-pa-sm"
        clearable
        outlined
        options-dense
        emit-value
        map-options
        :options="[
          { label: 'Duplicates', value: 'Y' },
          { label: 'Not duplicates', value: 'N' },
        ]"
        label="Duplicate">
      </q-select>

      <q-space />
      <q-btn v-if="day && day < today" class="q-mb-md day-btn" outline color="primary" padding="0 4px" icon="fas fa-chevron-right" @click="shiftDay(1)">
        <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 10]"> Next day </q-tooltip>
      </q-btn>
      <q-btn v-if="day && day < today" class="q-mb-md q-ml-xs day-btn" flat color="primary" padding="0 4px" icon="fas fa-step-forward" @click="load(null)">
        <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 10]"> Today </q-tooltip>
      </q-btn>
    </div>
    <div v-if="truncated" class="text-orange-9 q-mb-sm">Only the latest {{ formatNumber(files.length) }} files of the day are listed.</div>

    <!-- The actions, while files are selected: each counts the selected files it would change. -->
    <div v-if="selectable && selected.size" class="row items-center q-gutter-sm q-mb-sm selection-bar">
      <span class="text-weight-medium">{{ formatNumber(selected.size) }} selected</span>
      <q-btn flat dense no-caps color="primary" label="Clear" @click="selected = new Set()" />
      <q-space />
      <q-btn
        v-if="canDownload"
        outline
        no-caps
        :color="downloadAction.color"
        :icon="downloadAction.icon"
        :loading="downloading"
        :label="`${downloadAction.label} (${formatNumber(eligibleDownload.length)})`"
        :disable="!eligibleDownload.length"
        @click="download">
        <q-tooltip max-width="360px">{{ downloadAction.text }} {{ actionScope(downloadAction) }}</q-tooltip>
      </q-btn>
      <template v-if="canAct">
        <q-btn
          v-for="(action, status) in actions"
          :key="status"
          :outline="status !== 'DELETE'"
          :unelevated="status === 'DELETE'"
          no-caps
          :color="action.color"
          :icon="action.icon"
          :label="`${action.label} (${formatNumber(eligible(status).length)})`"
          :disable="!eligible(status).length"
          @click="confirmAction(status)">
          <q-tooltip max-width="360px">{{ action.text }} {{ actionScope(action) }}</q-tooltip>
        </q-btn>
      </template>
    </div>

    <q-virtual-scroll
      ref="scroll"
      type="table"
      class="list-table file-log-table"
      :class="{ 'file-log-table--selectable': selectable }"
      :style="{ maxHeight }"
      :items="sortedFiles"
      :virtual-scroll-item-size="41"
      :virtual-scroll-sticky-size-start="33"
      :table-colspan="selectable ? 11 : 10">
      <template #before>
        <thead>
          <tr class="bg-blue-grey-2">
            <th v-if="selectable" class="text-center">
              <q-checkbox :model-value="allShownSelected" :indeterminate-value="null" :disable="!shownFiles.length" dense @update:model-value="toggleAllShown">
                <q-tooltip>Select or unselect every file shown ({{ formatNumber(shownFiles.length) }})</q-tooltip>
              </q-checkbox>
            </th>
            <th v-for="column in columns" :key="column.key" :class="['text-' + column.align, 'sortable']" @click="toggleSort(sort, column.key)">
              {{ column.label }}
              <q-icon v-if="sort.key === column.key" :name="sortIcon(sort)" size="12px" />
            </th>
          </tr>
        </thead>
      </template>
      <template #default="{ item: file }">
        <tr :key="file.id" class="clickable-row" :class="{ 'file-row--highlight': file.id === highlightId, 'file-row--selected': selected.has(file.id) }" @click="openLog(file)">
          <td v-if="selectable" class="text-center" @click.stop>
            <q-checkbox :model-value="selected.has(file.id)" dense @update:model-value="toggle(file.id)" />
          </td>
          <td class="text-left" @click.stop>
            <q-chip clickable class="q-my-none" @click="addStatus(file.filestatus)">
              <q-avatar :icon="fileStatus(file.filestatus).icon" :color="fileStatus(file.filestatus).color" text-color="white" />
              {{ fileStatus(file.filestatus).label }}
            </q-chip>
          </td>
          <td class="text-left ellipsis" :title="file.inputfullfilename">
            <q-icon v-if="file.outfiledeleted" name="fas fa-archive" color="grey-5" size="12px" class="q-mr-xs" title="The archived file is deleted" />{{ file.inputfilename }}
          </td>
          <td class="text-right">{{ formatBytes(file.filesize) }}</td>
          <!-- Dates like the Start column of Results: the day bold, the time small beside it. -->
          <td class="text-left">
            <div v-if="file.filedate" class="text-blue-grey-7">
              <strong>{{ toDateString(file.filedate) }}</strong>
              <small class="text-grey-7 q-px-sm">{{ toTimeString(file.filedate) }}</small>
            </div>
          </td>
          <td class="text-left">
            <div v-if="file.startloaddate" class="text-blue-grey-7">
              <strong>{{ toDateString(file.startloaddate) }}</strong>
              <small class="text-grey-7 q-px-sm">{{ toTimeString(file.startloaddate) }}</small>
            </div>
          </td>
          <td class="text-right">{{ file.runtime != null ? `${file.runtime} s` : "" }}</td>
          <td class="text-right number-cell">{{ formatNumber(file.recordsread || 0) }}</td>
          <td class="text-right number-cell">{{ formatNumber(file.recordswrite || 0) }}</td>
          <td class="text-right number-cell" :class="{ 'text-red-6 text-weight-bold': file.recordsreject > 0 }">{{ formatNumber(file.recordsreject || 0) }}</td>
          <td class="text-center" @click.stop>
            <q-icon v-if="file.duplicate" name="fas fa-clone" color="purple-3" size="16px" class="cursor-pointer" @click="duplicate = 'Y'">
              <q-tooltip>Duplicate: click to show only the duplicates</q-tooltip>
            </q-icon>
          </td>
        </tr>
      </template>
      <template #after>
        <tbody v-if="!shownFiles.length">
          <tr>
            <td :colspan="selectable ? 11 : 10" class="text-center text-grey-7 q-pa-lg">
              {{ loading ? "Loading..." : files.length ? "No file matches the filters" : "No files loaded on this day" }}
            </td>
          </tr>
        </tbody>
      </template>
    </q-virtual-scroll>

    <q-dialog v-model="logVisible">
      <q-card class="column no-wrap" style="width: 1200px; max-width: 95vw; max-height: 85vh">
        <q-card-section class="row items-center q-py-sm">
          <q-icon v-if="logFile" :name="fileStatus(logFile.filestatus).icon" :color="fileStatus(logFile.filestatus).color" size="20px" class="q-mr-sm" />
          <div class="text-h6 ellipsis col">{{ logFile && logFile.inputfilename }}</div>
          <q-btn flat round dense icon="fas fa-copy" :disable="!logText" @click="copyLog">
            <q-tooltip>Copy the log</q-tooltip>
          </q-btn>
          <q-btn flat round icon="close" v-close-popup />
        </q-card-section>
        <q-separator />
        <q-card-section v-if="logFile" class="q-py-sm text-caption file-facts">
          <div><span>Input</span>{{ logFile.inputfullfilename }}</div>
          <div><span>Output</span>{{ logFile.outputfullfilename }}{{ logFile.outfiledeleted ? " (deleted)" : "" }}</div>
          <div><span>Loaded</span>{{ toDateTimeString(logFile.startloaddate) }} &ndash; {{ toDateTimeString(logFile.endloaddate) }}</div>
          <div><span>MD5</span>{{ logFile.md5 }}</div>
          <div><span>File ID</span>{{ logFile.id }}</div>
          <div><span>Server</span>{{ logFile.server }}</div>
        </q-card-section>
        <q-separator />
        <q-card-section class="col scroll">
          <template v-if="logLoading">
            <q-skeleton v-for="line in 6" :key="line" type="text" />
          </template>
          <pre v-else class="log-text">{{ logText || "No log text." }}</pre>
        </q-card-section>
      </q-card>
    </q-dialog>
  </div>
</template>

<script>
import FileHeatmap from "./FileHeatmap.vue";
import FilterBadge from "./FilterBadge.vue";
import FilterChips from "./FilterChips.vue";
import { api, notifyError } from "../api";
import { FILE_ACTIONS, FILE_DOWNLOAD, fileStatus } from "../constants";
import { date as quasarDate } from "quasar";
import { liveRefetch } from "../socket";
import { compactNumber } from "../utils/files";
import { listFilter, valueFilter } from "../utils/filters";
import { copyText, escapeHtml, formatNumber, toDateString, toDateTimeString, toTimeString } from "../utils/format";
import { formatBytes } from "../utils/datasources";
import { sortIcon, sortRows, toggleSort } from "../utils/sort";
import persistFilters from "../mixins/persistFilters";

// The files one datasource loaded on one day (get-ds-file-log, the database's day), newest first. A row opens the log
// text PDI Core wrote for it. With `selectable` (the Files page), files can be picked and asked to be recycled, reloaded
// or deleted (set-file-status), and PDI Core does the work, or downloaded (download-ds-files). The search and the status
// and duplicate filters are kept for the browser session, like the filters of the list pages, and stay while the day
// changes; `initialFilters` (a link from the Files page) replaces them, and every change is emitted as `filters`.
// The columns after the checkbox, sortable by their key (a file log column, or `status` by its label).
const COLUMNS = [
  { key: "status", label: "Status", align: "left" },
  { key: "inputfilename", label: "File", align: "left" },
  { key: "filesize", label: "Size", align: "right" },
  { key: "filedate", label: "File date", align: "left" },
  { key: "startloaddate", label: "Load start", align: "left" },
  { key: "runtime", label: "Runtime", align: "right" },
  { key: "recordsread", label: "Read", align: "right" },
  { key: "recordswrite", label: "Written", align: "right" },
  { key: "recordsreject", label: "Rejected", align: "right" },
  { key: "duplicate", label: "Duplicate", align: "center" },
];

function emptyHours() {
  return Array.from({ length: 24 }, () => ({ files: 0, errors: 0 }));
}

export default {
  name: "FileLogTable",
  mixins: [persistFilters("file_log", ["search", "statuses", "duplicate", "sort"])],
  components: { FileHeatmap, FilterBadge, FilterChips },
  props: {
    datasourceId: { type: Number, required: true },
    // YYYY-MM-DD to start with; null for the database's today.
    initialDay: { type: String, default: null },
    selectable: { type: Boolean, default: false },
    // The tables of the datasource, named in the confirmation of an action.
    tables: { type: Array, default: () => [] },
    // A file to scroll to and mark, e.g. one found by name.
    highlightId: { type: Number, default: null },
    maxHeight: { type: String, default: "60vh" },
    // Inside another page (the datasource editor): a smaller title.
    embedded: { type: Boolean, default: false },
    // Filters to start with instead of the kept ones, {statuses, hour, duplicate}; the file name search is cleared.
    initialFilters: { type: Object, default: null },
  },
  emits: ["day", "loaded", "filters"],
  data() {
    return {
      loading: false,
      day: null,
      today: null,
      files: [],
      truncated: false,
      search: "",
      statuses: [],
      duplicate: null,
      columns: COLUMNS,
      // No key: the order of the file log, newest load first.
      sort: { key: null, dir: "asc" },
      // The hour of the day picked in the heatmap (load start, the database's clock), or null.
      hour: null,
      selected: new Set(),
      actions: FILE_ACTIONS,
      downloadAction: FILE_DOWNLOAD,
      downloading: false,
      logVisible: false,
      logFile: null,
      logText: null,
      logLoading: false,
    };
  },
  computed: {
    statusCounts() {
      const counts = new Map();
      this.files.forEach((file) => counts.set(file.filestatus, (counts.get(file.filestatus) || 0) + 1));
      return [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([status, count]) => ({ status, count }));
    },
    // The statuses of the day's files, and a kept one the day has none in, so it can be removed.
    statusOptions() {
      const statuses = this.statusCounts.map((entry) => entry.status);
      (this.statuses || []).forEach((status) => statuses.includes(status) || statuses.push(status));
      return statuses.map((value) => ({ label: fileStatus(value).label, value }));
    },
    duplicateCount() {
      return this.files.filter((file) => file.duplicate).length;
    },
    totals() {
      return this.files.reduce(
        (totals, file) => {
          totals.read += file.recordsread || 0;
          totals.written += file.recordswrite || 0;
          totals.rejected += file.recordsreject || 0;
          return totals;
        },
        { read: 0, written: 0, rejected: 0 }
      );
    },
    dayTitle() {
      return this.day ? quasarDate.formatDate(quasarDate.extractDate(this.day, "YYYY-MM-DD"), "DD.MM.YYYY") : "";
    },
    activeFilters() {
      return [
        ...valueFilter("search", "File name", this.search, () => (this.search = null), { text: true }),
        ...listFilter("status", "Status", this.statuses, (value) => (this.statuses = this.statuses.filter((item) => item !== value)), (value) => fileStatus(value).label),
        ...valueFilter("duplicate", "Duplicate", this.duplicate, () => (this.duplicate = null), { label: this.duplicate === "Y" ? "Duplicates" : "Not duplicates" }),
        ...valueFilter("hour", "Hour", this.hour, () => (this.hour = null), {
          label: this.hour === null ? null : `${String(this.hour).padStart(2, "0")}:00–${String(this.hour + 1).padStart(2, "0")}:00`,
        }),
      ];
    },
    // The files that pass every filter but the hour, which the heatmap picks.
    filesButHour() {
      const needle = (this.search || "").toLowerCase();
      const statuses = this.statuses || [];
      return this.files.filter(
        (file) =>
          (!statuses.length || statuses.includes(file.filestatus)) &&
          (!this.duplicate || Boolean(file.duplicate) === (this.duplicate === "Y")) &&
          (!needle || (file.inputfilename || "").toLowerCase().includes(needle))
      );
    },
    heatmap() {
      const rows = new Map();
      const total = { key: "total", label: "Total", cells: emptyHours() };
      this.filesButHour.forEach((file) => {
        const hour = Number(String(file.startloaddate || "").slice(11, 13));
        if (!Number.isInteger(hour) || hour < 0 || hour > 23) {
          return;
        }
        if (!rows.has(file.filestatus)) {
          const info = fileStatus(file.filestatus);
          rows.set(file.filestatus, { key: `status-${file.filestatus}`, label: info.label, color: info.color, cells: emptyHours() });
        }
        [rows.get(file.filestatus), total].forEach((row) => {
          row.cells[hour].files += 1;
          if (file.filestatus === "ERROR") {
            row.cells[hour].errors += 1;
          }
        });
      });
      const list = [...rows.values()].sort((a, b) => b.cells.reduce((n, c) => n + c.files, 0) - a.cells.reduce((n, c) => n + c.files, 0));
      return list.length > 1 ? [...list, total] : list.length ? list : [total];
    },
    shownFiles() {
      if (this.hour === null) {
        return this.filesButHour;
      }
      return this.filesButHour.filter((file) => Number(String(file.startloaddate || "").slice(11, 13)) === this.hour);
    },
    sortedFiles() {
      const key = this.sort.key;
      if (!key) {
        return this.shownFiles;
      }
      const valueOf = key === "status" ? (file) => fileStatus(file.filestatus).label : (file) => file[key];
      return sortRows(this.shownFiles, valueOf, this.sort.dir);
    },
    allShownSelected() {
      if (!this.selected.size) {
        return false;
      }
      const all = this.shownFiles.every((file) => this.selected.has(file.id));
      return all ? true : null;
    },
    canAct() {
      const info = this.$store.getters.getEnvInfo;
      return Boolean(info && info.datasources_file_actions);
    },
    filesById() {
      return new Map(this.files.map((file) => [file.id, file]));
    },
    canDownload() {
      const info = this.$store.getters.getEnvInfo;
      return Boolean(info && info.datasources_file_download);
    },
    eligibleDownload() {
      return this.eligibleFor(FILE_DOWNLOAD, null);
    },
    // The filters a link to this view carries (the Files page mirrors them into its URL).
    linkFilters() {
      return { statuses: [...(this.statuses || [])], hour: this.hour, duplicate: this.duplicate || null };
    },
  },
  watch: {
    // Another link's filters (Back, or another count of the Files page); the ones this table emitted come back equal.
    initialFilters(value) {
      if (!value) {
        return;
      }
      const wanted = { statuses: [...(value.statuses || [])], hour: value.hour ?? null, duplicate: value.duplicate || null };
      if (JSON.stringify(wanted) !== JSON.stringify(this.linkFilters)) {
        this.applyInitialFilters();
      }
    },
    linkFilters(value, previous) {
      if (JSON.stringify(value) !== JSON.stringify(previous)) {
        this.$emit("filters", value);
      }
    },
    datasourceId() {
      this.load(null);
    },
    initialDay(value) {
      if (value !== this.day) {
        this.load(value);
      }
    },
  },
  methods: {
    compactNumber,
    fileStatus,
    sortIcon,
    toggleSort,
    addStatus(status) {
      if (!this.statuses.includes(status)) {
        this.statuses = [...this.statuses, status];
      }
    },
    applyInitialFilters() {
      const filters = this.initialFilters;
      if (!filters) {
        return;
      }
      this.search = null;
      this.statuses = [...(filters.statuses || [])];
      this.duplicate = filters.duplicate || null;
      this.hour = filters.hour ?? null;
      this.keepHour = this.hour !== null;
    },
    clearFilters() {
      this.search = null;
      this.statuses = [];
      this.duplicate = null;
      this.hour = null;
    },
    formatBytes,
    formatNumber,
    toDateString,
    toDateTimeString,
    toTimeString,
    async load(day, quiet = false) {
      this.loading = !quiet;
      try {
        const result = await api("get-ds-file-log", { params: { id: this.datasourceId, date: day }, loadingBar: false });
        // An hour picked on one day means nothing on another; one of the initial filters is for the first day loaded.
        const keepHour = this.keepHour && (day || null) === (this.initialDay || null);
        if (result.date !== this.day && !keepHour) {
          this.hour = null;
        }
        this.keepHour = false;
        this.day = result.date;
        this.today = result.today;
        this.files = Object.freeze(result.files.map(Object.freeze));
        this.truncated = result.truncated;
        if (!quiet) {
          this.selected = new Set();
        }
        this.$emit("day", result.date === result.today ? null : result.date);
        this.$emit("loaded", this.files);
        this.scrollToHighlight();
      } catch (error) {
        notifyError("The file log could not be loaded.", error);
      } finally {
        this.loading = false;
      }
    },
    scrollToHighlight() {
      if (!this.highlightId) {
        return;
      }
      const index = this.sortedFiles.findIndex((file) => file.id === this.highlightId);
      if (index >= 0) {
        this.$nextTick(() => this.$refs.scroll && this.$refs.scroll.scrollTo(index, "center"));
      }
    },
    shiftDay(days) {
      const date = new Date(`${this.day}T12:00:00`);
      date.setDate(date.getDate() + days);
      const pad = (value) => String(value).padStart(2, "0");
      this.load(`${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`);
    },
    toggle(id) {
      const selected = new Set(this.selected);
      if (selected.has(id)) {
        selected.delete(id);
      } else {
        selected.add(id);
      }
      this.selected = selected;
    },
    toggleAllShown() {
      const selected = new Set(this.selected);
      if (this.allShownSelected === true) {
        this.shownFiles.forEach((file) => selected.delete(file.id));
      } else {
        this.shownFiles.forEach((file) => selected.add(file.id));
      }
      this.selected = selected;
    },
    // Which files an action takes, for its tooltip.
    actionScope(action) {
      if (!action.from) {
        return "Files of any status.";
      }
      return `Only ${action.from.join(" or ")} files${action.needsFile ? " whose archived file is kept" : ""}.`;
    },
    // The selected files an action would change: those of its `from` statuses (RECYCLE: SUCCESS or ERROR, RELOAD: SUCCESS)
    // with their archived file, for DELETE any not in DELETE already.
    eligible(status) {
      return this.eligibleFor(FILE_ACTIONS[status], status);
    },
    // The selected files of an action's `from` statuses and, with `needsFile`, an archived file; none already in `status`.
    eligibleFor({ from, needsFile }, status) {
      const files = [];
      this.selected.forEach((id) => {
        const file = this.filesById.get(id);
        if (!file || (status && file.filestatus === status)) {
          return;
        }
        if ((!from || from.includes(file.filestatus)) && !(needsFile && file.outfiledeleted)) {
          files.push(file);
        }
      });
      return files;
    },
    confirmAction(status) {
      const action = FILE_ACTIONS[status];
      const files = this.eligible(status);
      const skipped = this.selected.size - files.length;
      const tables = this.tables.length ? this.tables.map(escapeHtml).join(", ") : "the table named like the datasource (no tables are linked)";
      const parts = [
        `${escapeHtml(action.text)}`,
        `<br><br>Tables: ${tables}.`,
        skipped
          ? `<br><br>${skipped} of the selected files are left alone: ${
              action.from ? `not ${action.from.join(" or ")}, or their archived file is deleted` : `already ${status}`
            }.`
          : "",
        action.warning ? `<br><br><b class="text-negative">${escapeHtml(action.warning)}</b>` : "",
      ];
      this.$q
        .dialog({
          title: `${action.label} ${formatNumber(files.length)} file(s)?`,
          message: parts.join(""),
          html: true,
          cancel: true,
          persistent: true,
          ok: { label: `${action.label} ${formatNumber(files.length)} file(s)`, color: action.color === "negative" ? "negative" : "primary" },
        })
        .onOk(() => this.applyAction(status, files));
    },
    async applyAction(status, files) {
      try {
        const result = await api("set-file-status", { method: "POST", body: { ids: files.map((file) => file.id), status } });
        const reasons = [...new Set(result.skipped.map((item) => item.reason))].join(", ");
        this.$q.notify({
          type: result.changed ? "positive" : "warning",
          message: `${formatNumber(result.changed)} file(s) set to ${status}${result.skipped.length ? `, ${result.skipped.length} left alone (${reasons})` : ""}. PDI Core picks them up.`,
        });
      } catch (error) {
        notifyError(`The files were not set to ${status}.`, error);
      }
      await this.load(this.day === this.today ? null : this.day);
    },
    // The files arrive as one Blob (one file as it is, several as a ZIP), saved under the name the server gives.
    async download() {
      const files = this.eligibleDownload;
      this.downloading = true;
      try {
        const response = await api("download-ds-files", { method: "POST", body: { ids: files.map((file) => file.id) }, raw: true });
        const disposition = response.headers.get("Content-Disposition") || "";
        const match = /filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i.exec(disposition);
        const name = match ? decodeURIComponent(match[1] || match[2]) : files.length === 1 ? files[0].inputfilename : "files.zip";
        const skipped = Number(response.headers.get("X-Rapo-Skipped") || 0);
        const url = URL.createObjectURL(await response.blob());
        const link = document.createElement("a");
        link.href = url;
        link.download = name;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        if (skipped) {
          this.$q.notify({
            type: "warning",
            message: `${formatNumber(skipped)} of ${formatNumber(files.length)} file(s) were left out${files.length - skipped > 1 ? " (named in MISSING.txt of the ZIP)" : ""}.`,
          });
        }
      } catch (error) {
        notifyError("The files were not downloaded.", error);
      } finally {
        this.downloading = false;
      }
    },
    async openLog(file) {
      this.logFile = file;
      this.logText = null;
      this.logVisible = true;
      this.logLoading = true;
      try {
        const result = await api("get-ds-file-log-text", { params: { file_id: file.id }, loadingBar: false });
        this.logText = result.log;
      } catch (error) {
        notifyError("The log text could not be loaded.", error);
      } finally {
        this.logLoading = false;
      }
    },
    async copyLog() {
      try {
        await copyText(this.logText);
        this.$q.notify({ message: "Log copied", timeout: 1000 });
      } catch (error) {
        notifyError("The log was not copied.", error);
      }
    },
  },
  // After persistFilters restored the kept filters, which a link's filters replace.
  created() {
    this.applyInitialFilters();
  },
  mounted() {
    this.load(this.initialDay);
    // Today's files change while PDI Core loads; a past day's only by an action, which reloads itself.
    this.stopLiveUpdates = liveRefetch("datasources:changed", () => this.day === this.today && this.load(null, true), {
      filter: (payload) => payload.kind === "files",
      interval: 15000,
    });
  },
  unmounted() {
    if (this.stopLiveUpdates) {
      this.stopLiveUpdates();
    }
  },
};
</script>

<style scoped>
.clickable-row {
  cursor: pointer;
}
.sortable {
  cursor: pointer;
  user-select: none;
}
.clickable-row:hover {
  background: rgba(0, 0, 0, 0.03);
}
.file-row--selected {
  background: #e3f2fd;
}
.file-row--highlight > td {
  background: #fff8e1;
}
.selection-bar {
  min-height: 40px;
  padding: 2px 8px;
  background: #e3f2fd;
  border-radius: 4px;
}
/* The day buttons are as tall as the inputs beside them, as on Results. */
.day-btn {
  height: 51px;
  min-width: 0;
}
.name-filter {
  min-width: 200px;
}
.results-day {
  font-size: 0.6em;
}
.file-log-table :deep(table) {
  table-layout: fixed;
  min-width: 1200px;
}
.file-log-table th:nth-child(1) { width: 140px; }
.file-log-table th:nth-child(3) { width: 80px; }
.file-log-table th:nth-child(4) { width: 170px; }
.file-log-table th:nth-child(5) { width: 170px; }
.file-log-table th:nth-child(6) { width: 80px; }
.file-log-table th:nth-child(7) { width: 110px; }
.file-log-table th:nth-child(8) { width: 110px; }
.file-log-table th:nth-child(9) { width: 90px; }
.file-log-table th:nth-child(10) { width: 80px; }
/* With the checkbox column first, every width moves one column to the right. */
.file-log-table--selectable th:nth-child(1) { width: 44px; }
.file-log-table--selectable th:nth-child(2) { width: 140px; }
.file-log-table--selectable th:nth-child(3) { width: auto; }
.file-log-table--selectable th:nth-child(4) { width: 80px; }
.file-log-table--selectable th:nth-child(5) { width: 170px; }
.file-log-table--selectable th:nth-child(6) { width: 170px; }
.file-log-table--selectable th:nth-child(7) { width: 80px; }
.file-log-table--selectable th:nth-child(8) { width: 110px; }
.file-log-table--selectable th:nth-child(9) { width: 110px; }
.file-log-table--selectable th:nth-child(10) { width: 90px; }
.file-log-table--selectable th:nth-child(11) { width: 80px; }
/* Whole numbers in a monospace font, right-aligned, so their digits line up (as on the Files page). */
.number-cell {
  font-family: "Roboto Mono", Menlo, Consolas, monospace;
  font-size: 13px;
}
.log-text {
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
}
.file-facts {
  font-family: monospace;
  word-break: break-all;
}
.file-facts span {
  display: inline-block;
  width: 70px;
  color: #757575;
}
</style>
