<template>
  <div class="column no-wrap relative-position" @dragenter="dragEnter" @dragover="dragOverPage" @dragleave="dragLeave" @drop="dropFiles">
    <!-- Laid out like Results and Files: the title with the day navigator, the day's status chips (filters, toggled) and
         Upload on the right with the day's totals under them, then the active filters (led by the Filter badge). The page
         searches with the header search; the datasource editor, which has none, with its own File name box. -->
    <div class="row items-end" :class="activeFilters.length || sortChip ? 'q-mb-sm' : embedded ? 'q-mb-md' : 'q-mb-lg'">
      <component :is="embedded ? 'div' : 'h2'" class="row items-center no-wrap text-no-wrap q-gutter-lg q-mb-none" :class="{ 'text-h6': embedded }">
        <slot name="title" />
        <div><day-navigator :day="day" :today="today" @go="goToDay" /></div>
        <slot name="after-day" />
        <div v-if="loading">
          <q-avatar :size="embedded ? 'md' : 'lg'" color="grey-5">
            <q-icon name="fas fa-sync fa-spin" />
          </q-avatar>
        </div>
      </component>
      <q-input v-if="embedded" v-model="search" dense clearable outlined debounce="200" label="File name" maxlength="200" class="q-ml-lg name-filter" />
      <q-space />

      <!-- The day's totals, whatever the filters; a status chip filters by it. -->
      <div class="column items-end text-blue-grey-8">
        <div v-if="statusCounts.length || duplicateCount || canUpload" class="row items-center justify-end">
          <q-chip
            v-for="entry in statusCounts"
            :key="entry.status"
            clickable
            :class="{ 'chip-selected': statuses.includes(entry.status) }"
            @click="toggleStatus(entry.status)">
            <q-avatar :icon="fileStatus(entry.status).icon" :color="fileStatus(entry.status).color" text-color="white" />
            <span class="text-weight-bold q-mr-xs">{{ fileStatus(entry.status).label }}</span>({{ formatNumber(entry.count) }})
          </q-chip>
          <q-chip v-if="duplicateCount" clickable :class="{ 'chip-selected': duplicate === 'Y' }" @click="duplicate = duplicate === 'Y' ? null : 'Y'">
            <q-avatar icon="fas fa-clone" color="purple-3" text-color="white" />
            <span class="text-weight-bold q-mr-xs">Duplicate</span>({{ formatNumber(duplicateCount) }})
            <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">Files PDI Core flagged as duplicates (DUPLICATE = 1): show only them</q-tooltip>
          </q-chip>
          <q-btn v-if="canUpload" class="q-ml-sm" outline dense no-caps color="primary" icon="fas fa-upload" label="Upload" padding="4px 10px" @click="openUpload([])">
            <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">Upload files into the input directory of the datasource (or drop them here)</q-tooltip>
          </q-btn>
        </div>
        <div v-if="files.length" class="q-mr-xs">
          {{ formatNumber(files.length) }} files &middot; {{ compactNumber(totals.read) }} read &middot; {{ compactNumber(totals.written) }} written
          <span :class="{ 'text-red-6': totals.rejected }">&middot; {{ compactNumber(totals.rejected) }} rejected</span>
          <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">
            Records read {{ formatNumber(totals.read) }}, written {{ formatNumber(totals.written) }}, rejected {{ formatNumber(totals.rejected) }}
          </q-tooltip>
        </div>
      </div>
    </div>
    <filter-chips :filters="activeFilters" :sort="sortChip" :shown="`${formatNumber(shownFiles.length)} of ${formatNumber(files.length)} files`" class="q-mb-md" @clear="clearFilters" />

    <!-- Files per hour, as on the Files page: one row per status and a total, following the other filters. -->
    <hour-heatmap
      v-if="!embedded && files.length"
      :rows="heatmap"
      :selected="hour"
      :now="nowPosition"
      :now-label="nowLabel"
      class="q-mt-sm q-mb-md"
      @select="(value) => (hour = value)" />

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
      :virtual-scroll-sticky-size-start="28"
      :table-colspan="selectable ? 11 : 10">
      <template #before>
        <thead>
          <tr class="bg-blue-grey-2">
            <th v-if="selectable" title="Select all the files shown" class="text-center">
              <q-checkbox :model-value="allShownSelected" :indeterminate-value="null" :disable="!shownFiles.length" dense @update:model-value="toggleAllShown">
                <q-tooltip>Select or unselect every file shown ({{ formatNumber(shownFiles.length) }})</q-tooltip>
              </q-checkbox>
            </th>
            <th v-for="column in columns" :key="column.key" :title="column.title" :class="['text-' + column.align, 'sortable']" @click="toggleSort(sort, column.key)" v-keyboard :aria-sort="ariaSort(sort, column.key)">
              {{ column.label }}
              <q-icon v-if="sort.key === column.key" :name="sortIcon(sort)" size="12px" />
            </th>
          </tr>
        </thead>
      </template>
      <template #default="{ item: file }">
        <tr :key="file.id" class="clickable-row" :class="{ 'file-row--highlight': file.id === highlightId, 'file-row--selected': selected.has(file.id) }" v-keyboard @click="openLog(file)">
          <td v-if="selectable" class="text-center" @click.stop>
            <q-checkbox :model-value="selected.has(file.id)" dense @update:model-value="toggle(file.id)" />
          </td>
          <td class="text-left" @click.stop>
            <q-chip clickable class="q-my-none" @click="addStatus(file.filestatus)">
              <q-avatar :icon="fileStatus(file.filestatus).icon" :color="fileStatus(file.filestatus).color" text-color="white" />
              {{ fileStatus(file.filestatus).label }}
            </q-chip>
          </td>
          <td class="text-left text-mono file-name-cell" :title="file.inputfullfilename">
            <div class="row no-wrap items-center">
              <span class="col ellipsis">
                <q-icon v-if="file.outfiledeleted" name="fas fa-archive" color="grey-5" size="12px" class="q-mr-xs" title="The archived file is deleted" />{{ file.inputfilename }}
              </span>
              <q-btn
                v-if="canView(file)"
                aria-label="View the file"
                flat
                round
                dense
                size="sm"
                color="blue-grey-6"
                icon="fas fa-eye"
                class="view-btn"
                @click.stop="openViewer(file, 'file')">
                <q-tooltip>View the archived file</q-tooltip>
              </q-btn>
              <q-btn
                v-if="hasRecords(file)"
                aria-label="Show the loaded records"
                flat
                round
                dense
                size="sm"
                color="blue-grey-6"
                icon="fas fa-database"
                class="view-btn"
                @click.stop="openViewer(file, 'db')">
                <q-tooltip>Show the records loaded in the database</q-tooltip>
              </q-btn>
            </div>
          </td>
          <td class="text-right number-cell">{{ formatBytes(file.filesize) }}</td>
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
          <td class="text-right number-cell">{{ file.runtime != null ? `${file.runtime} s` : "" }}</td>
          <td class="text-right number-cell">{{ formatNumber(file.recordsread || 0) }}</td>
          <td class="text-right number-cell">{{ formatNumber(file.recordswrite || 0) }}</td>
          <td class="text-right number-cell" :class="{ 'text-red-6 text-weight-bold': file.recordsreject > 0 }">{{ formatNumber(file.recordsreject || 0) }}</td>
          <td class="text-center" @click.stop>
            <q-icon v-if="file.duplicate" name="fas fa-clone" color="purple-3" size="16px" class="cursor-pointer" aria-label="Show duplicates only" v-keyboard:button @click="duplicate = 'Y'">
              <q-tooltip>Duplicate: click to show only the duplicates</q-tooltip>
            </q-icon>
          </td>
        </tr>
      </template>
      <template #after>
        <tbody v-if="!shownFiles.length">
          <tr>
            <td :colspan="selectable ? 11 : 10" class="text-center text-grey-7 q-pa-lg">
              <!-- A file ID or name prefix searched for that is not on this day: the datasource's other days are looked up. -->
              <template v-if="!loading && otherDayKey">
                <span v-if="!otherDayReady">Searching the other days of the file log...</span>
                <span v-else-if="!otherDayFiles.length">{{ searchMode.kind === "id" ? `No file ${searchMode.value} of this datasource` : `No file of this datasource starts with '${searchMode.value}'` }}</span>
                <template v-else-if="searchMode.kind === 'id'">
                  File {{ searchMode.value }} is on {{ dayLabel(fileDay(otherDayFiles[0])) }} &middot;
                  <a href="#" class="text-teal-8 text-weight-bold" @click.prevent="openOtherDay(otherDayFiles[0])">Go to its day</a>
                </template>
                <a v-else href="#" class="text-teal-8 text-weight-bold" @click.prevent>
                  {{ otherDayFiles.length >= fileSearchLimit ? `The newest ${fileSearchLimit} files` : `${formatNumber(otherDayFiles.length)} file(s)` }} of other days
                  starting with '{{ searchMode.value }}'
                  <q-icon name="fas fa-caret-down" size="14px" class="q-ml-xs" />
                  <q-menu fit :offset="[0, 4]" max-height="400px">
                    <q-list dense style="min-width: 480px">
                      <q-item v-for="file in otherDayFiles" :key="file.id" clickable v-close-popup @click="openOtherDay(file)">
                        <q-item-section avatar>
                          <q-icon :name="fileStatus(file.filestatus).icon" :color="fileStatus(file.filestatus).color" size="16px" />
                        </q-item-section>
                        <q-item-section class="text-left">
                          <q-item-label class="ellipsis">{{ file.inputfilename }}</q-item-label>
                          <q-item-label caption>#{{ file.id }} &middot; {{ toDateTimeString(file.startloaddate) }}</q-item-label>
                        </q-item-section>
                      </q-item>
                    </q-list>
                  </q-menu>
                </a>
              </template>
              <template v-else>{{ loading ? "Loading..." : files.length ? "No file matches the filters" : "No files loaded on this day" }}</template>
            </td>
          </tr>
        </tbody>
      </template>
    </q-virtual-scroll>

    <file-viewer-dialog ref="viewer" />
    <file-upload-dialog ref="upload" />
    <div v-if="dragging" class="absolute-full drop-overlay column items-center justify-center">
      <q-icon name="fas fa-cloud-upload-alt" size="40px" class="q-mb-sm" />
      <div class="text-h6">Drop the files to upload them into the input directory</div>
    </div>

    <q-dialog v-model="logVisible">
      <q-card class="column no-wrap" style="width: 1200px; max-width: 95vw; max-height: 85vh">
        <q-card-section class="row items-center q-py-sm">
          <q-icon v-if="logFile" :name="fileStatus(logFile.filestatus).icon" :color="fileStatus(logFile.filestatus).color" size="20px" class="q-mr-sm" />
          <div class="text-h6 ellipsis col">{{ logFile && logFile.inputfilename }}</div>
          <q-btn aria-label="Copy the log" flat round dense icon="fas fa-copy" :disable="!logText" @click="copyLog">
            <q-tooltip>Copy the log</q-tooltip>
          </q-btn>
          <q-btn aria-label="Close" flat round icon="fas fa-times" v-close-popup />
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
import { mapGetters } from "vuex";
import DayNavigator from "./DayNavigator.vue";
import HourHeatmap from "./HourHeatmap.vue";
import FilterChips from "./FilterChips.vue";
import FileUploadDialog from "./FileUploadDialog.vue";
import FileViewerDialog from "./FileViewerDialog.vue";
import { api, notifyError } from "../api";
import { FILE_ACTIONS, FILE_DOWNLOAD, fileStatus } from "../constants";
import { liveRefetch } from "../socket";
import { copyAndNotify } from "../runActions";
import { downloadFiles } from "../utils/datasources";
import { FILE_SEARCH_LIMIT, datasourceMatchesSearch, fileMatchesSearch, hourRange, loadHour, parseSearch, statusHeatmapRows } from "../utils/files";
import { listFilter, searchFilter, valueFilter } from "../utils/filters";
import { compactNumber, dayLabel, escapeHtml, formatBytes, formatNumber, toDateString, toDateTimeString, toTimeString } from "../utils/format";
import { ariaSort, sortChip, sortIcon, sortRows, toggleSort } from "../utils/sort";
import { clockLabel, clockOffset, dayPosition } from "../utils/clock";
import persistFilters from "../mixins/persistFilters";

// The files one datasource loaded on one day (get-ds-file-log, the database's day), newest first. A row opens the log
// text PDI Core wrote for it. With `selectable` (the Files page), files can be picked and asked to be recycled, reloaded
// or deleted (set-file-status), and PDI Core does the work, or downloaded (download-ds-files). The status and duplicate
// filters are kept for the browser session, like the filters of the list pages, and stay while the day changes;
// `initialFilters` (a link from the Files page) replaces them, and every change is emitted as `filters`. The page reads
// the header search as the Files page does (?<name prefix>, #<file ID>, else a name); a name of its datasource, as the
// Files page searched it, filters nothing. A file ID or name prefix of another day is looked up and offered (`open-file`).
// Embedded (the datasource editor, no header search) it has its own File name box, kept for the session.
// The columns after the checkbox, sortable by their key (a file log column, or `status` by its label).
const COLUMNS = [
  { key: "status", label: "Status", align: "left", title: "The status of the file in PDI Core's file log" },
  { key: "inputfilename", label: "File", align: "left", title: "The input file's name; click a row for the log PDI Core wrote for it, the eye to view the archived file, the database icon for the records loaded from it" },
  { key: "filesize", label: "Size", align: "right", title: "The size of the input file" },
  { key: "filedate", label: "File date", align: "left", title: "The date of the input file" },
  { key: "startloaddate", label: "Load start", align: "left", title: "When PDI Core started loading the file" },
  { key: "runtime", label: "Runtime", align: "right", title: "How long loading the file took (h:mm:ss)" },
  { key: "recordsread", label: "Read", align: "right", title: "Records read from the file" },
  { key: "recordswrite", label: "Written", align: "right", title: "Records written to the tables of the datasource" },
  { key: "recordsreject", label: "Rejected", align: "right", title: "Records rejected while loading" },
  { key: "duplicate", label: "Duplicate", align: "center", title: "Whether PDI Core flagged the file as a duplicate" },
];

// No column: the server's order, newest load first.
const DEFAULT_SORT = { key: null, dir: "asc" };

export default {
  name: "FileLogTable",
  mixins: [persistFilters("file_log", ["search", "statuses", "duplicate", "sort"])],
  components: { DayNavigator, HourHeatmap, FilterChips, FileUploadDialog, FileViewerDialog },
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
    // Filters to start with instead of the kept ones, {statuses, hour, duplicate: 'Y'|null}; the File name box is cleared.
    initialFilters: { type: Object, default: null },
    // The datasource's name, which a header search carried over from the Files page may be.
    sourceName: { type: String, default: null },
  },
  emits: ["day", "loaded", "filters", "open-file"],
  data() {
    return {
      loading: false,
      day: null,
      today: null,
      // The database's clock minus the browser's, and the browser's time moved on every minute: the Now marker.
      clockOffset: 0,
      now: Date.now(),
      files: [],
      truncated: false,
      search: "",
      statuses: [],
      // "Y" for only the duplicates, else null.
      duplicate: null,
      columns: COLUMNS,
      // No key: the order of the file log, newest load first.
      sort: { ...DEFAULT_SORT },
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
      dragging: false,
      // The files of other days found for the header search (search-files of this datasource), and the search they are for.
      otherDayFiles: [],
      otherDayFor: null,
      fileSearchLimit: FILE_SEARCH_LIMIT,
    };
  },
  computed: {
    // The present by the database's clock, which stamps the file log: marked on today's heatmap only.
    nowPosition() {
      return dayPosition(this.now + this.clockOffset, this.day);
    },
    nowLabel() {
      return clockLabel(this.now + this.clockOffset);
    },
    ...mapGetters(["getEnvInfo", "getSearch"]),
    // The header search on the page, the File name box in the editor; a name of the datasource itself filters nothing.
    searchMode() {
      if (this.embedded) {
        return { kind: "name", value: (this.search || "").trim() };
      }
      const mode = parseSearch(this.getSearch);
      return mode.kind === "name" && mode.value && datasourceMatchesSearch(this.sourceName, this.datasourceId, mode.value) ? { kind: "name", value: "" } : mode;
    },
    // What search-files is asked for while no file of the day passes the filters, or null.
    otherDayKey() {
      const { kind, value } = this.searchMode;
      if (this.embedded || this.shownFiles.length) {
        return null;
      }
      if ((kind === "file" && value.length >= 3) || (kind === "id" && /^\d+$/.test(value))) {
        return `${this.datasourceId}:${kind}:${value}`;
      }
      return null;
    },
    otherDayReady() {
      return Boolean(this.otherDayKey) && this.otherDayFor === this.otherDayKey;
    },
    statusCounts() {
      const counts = new Map();
      this.files.forEach((file) => counts.set(file.filestatus, (counts.get(file.filestatus) || 0) + 1));
      return [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([status, count]) => ({ status, count }));
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
    sortChip() {
      return sortChip(this.sort, DEFAULT_SORT, Object.fromEntries(this.columns.map((column) => [column.key, column.label])), "newest load first");
    },
    activeFilters() {
      return [
        ...(this.embedded ? valueFilter("search", "File name", this.search, () => (this.search = null), { text: true }) : searchFilter(this.$store)),
        ...listFilter("status", "Status", this.statuses, (value) => (this.statuses = this.statuses.filter((item) => item !== value)), (value) => fileStatus(value).label),
        ...valueFilter("duplicate", "Duplicate", this.duplicate, () => (this.duplicate = null), { label: "Duplicates" }),
        ...valueFilter("hour", "Hour", this.hour, () => (this.hour = null), {
          label: this.hour === null ? null : hourRange(this.hour),
        }),
      ];
    },
    // The files that pass every filter but the hour, which the heatmap picks.
    filesButHour() {
      const statuses = this.statuses || [];
      const search = this.searchMode;
      return this.files.filter(
        (file) => (!statuses.length || statuses.includes(file.filestatus)) && (!this.duplicate || Boolean(file.duplicate)) && fileMatchesSearch(file, search)
      );
    },
    heatmap() {
      return statusHeatmapRows(this.filesButHour);
    },
    shownFiles() {
      if (this.hour === null) {
        return this.filesButHour;
      }
      return this.filesButHour.filter((file) => loadHour(file) === this.hour);
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
      return Boolean(this.getEnvInfo && this.getEnvInfo.datasources_file_actions);
    },
    filesById() {
      return new Map(this.files.map((file) => [file.id, file]));
    },
    canDownload() {
      return Boolean(this.getEnvInfo && this.getEnvInfo.datasources_file_download);
    },
    logAvailable() {
      return Boolean(this.getEnvInfo && this.getEnvInfo.datasources_log);
    },
    canUpload() {
      return Boolean(this.getEnvInfo && this.getEnvInfo.datasources_file_upload);
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
    highlightId() {
      this.scrollToHighlight();
    },
    otherDayKey(key) {
      clearTimeout(this.otherDayTimer);
      if (key && key !== this.otherDayFor) {
        this.otherDayTimer = setTimeout(this.searchOtherDays, 400);
      }
    },
  },
  methods: {
    compactNumber,
    fileStatus,
    sortIcon,
    ariaSort,
    toggleSort,
    dayLabel,
    addStatus(status) {
      if (!this.statuses.includes(status)) {
        this.statuses = [...this.statuses, status];
      }
    },
    toggleStatus(status) {
      this.statuses = this.statuses.includes(status) ? this.statuses.filter((item) => item !== status) : [...this.statuses, status];
    },
    // The day of a file of the log (its load start, the database's clock).
    fileDay(file) {
      return String(file.startloaddate || "").slice(0, 10);
    },
    // A file of another day: the parent opens its day (null for today) with the file picked.
    openOtherDay(file) {
      const day = this.fileDay(file);
      this.$emit("open-file", file, day && day < this.today ? day : null);
    },
    // Asks search-files for the header search's file ID or name prefix in this datasource, minus the files of the day.
    async searchOtherDays() {
      const key = this.otherDayKey;
      if (!key || key === this.otherDayFor) {
        return;
      }
      const { kind, value } = this.searchMode;
      try {
        const files = await api("search-files", { params: { ...(kind === "id" ? { id: value } : { text: value }), source_id: this.datasourceId }, loadingBar: false });
        if (key === this.otherDayKey) {
          this.otherDayFiles = Object.freeze(files.filter((file) => !this.filesById.has(file.id)));
          this.otherDayFor = key;
        }
      } catch (error) {
        notifyError("The file log could not be searched.", error);
      }
    },
    applyInitialFilters() {
      const filters = this.initialFilters;
      if (!filters) {
        return;
      }
      this.search = null;
      this.statuses = [...(filters.statuses || [])];
      this.duplicate = filters.duplicate === "Y" ? "Y" : null;
      this.hour = filters.hour ?? null;
      this.keepHour = this.hour !== null;
    },
    clearFilters() {
      this.search = null;
      if (!this.embedded) {
        this.$store.commit("updateSearch", "");
      }
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
        this.clockOffset = clockOffset(result.database_time);
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
    goToDay(day) {
      this.load(day && day < this.today ? day : null);
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
        const skipped = await downloadFiles(
          files.map((file) => file.id),
          files.length === 1 ? files[0].inputfilename : "files.zip",
        );
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
    // A file a download would send: its status, an archived file kept.
    canView(file) {
      return this.canDownload && FILE_DOWNLOAD.from.includes(file.filestatus) && !file.outfiledeleted;
    },
    // Records PDI Core wrote or rejected, in the tables of the datasource.
    hasRecords(file) {
      return this.logAvailable && this.tables.length > 0 && (file.recordswrite > 0 || file.recordsreject > 0);
    },
    openViewer(file, layout) {
      this.$refs.viewer.open(file, { datasourceId: this.datasourceId, layout, viewable: this.canView(file), hasTables: this.tables.length > 0 });
    },
    openUpload(files) {
      this.$refs.upload.open(this.datasourceId, files);
    },
    // Files dragged from the desktop over the file log: an overlay, and a drop opens the upload dialog with them.
    draggingFiles(event) {
      return this.canUpload && event.dataTransfer && [...event.dataTransfer.types].includes("Files");
    },
    dragEnter(event) {
      if (this.draggingFiles(event)) {
        this.dragDepth = (this.dragDepth || 0) + 1;
        this.dragging = true;
      }
    },
    dragOverPage(event) {
      if (this.draggingFiles(event)) {
        event.preventDefault();
      }
    },
    dragLeave(event) {
      if (this.draggingFiles(event)) {
        this.dragDepth = Math.max((this.dragDepth || 1) - 1, 0);
        this.dragging = this.dragDepth > 0;
      }
    },
    dropFiles(event) {
      if (!this.draggingFiles(event)) {
        return;
      }
      event.preventDefault();
      this.dragDepth = 0;
      this.dragging = false;
      if (event.dataTransfer.files.length) {
        this.openUpload([...event.dataTransfer.files]);
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
      await copyAndNotify(this.logText, "Log", "The log was not copied.");
    },
  },
  // After persistFilters restored the kept filters, which a link's filters replace.
  created() {
    // "Not duplicates" (N) is no filter any more.
    if (this.duplicate !== "Y") {
      this.duplicate = null;
    }
    this.applyInitialFilters();
  },
  mounted() {
    this.load(this.initialDay);
    this.clock = setInterval(() => (this.now = Date.now()), 60000);
    // Today's files change while PDI Core loads; a past day's only by an action, which reloads itself.
    this.stopLiveUpdates = liveRefetch("datasources:changed", () => this.day === this.today && this.load(null, true), {
      filter: (payload) => payload.kind === "files",
      interval: 15000,
    });
  },
  unmounted() {
    clearInterval(this.clock);
    clearTimeout(this.otherDayTimer);
    if (this.stopLiveUpdates) {
      this.stopLiveUpdates();
    }
  },
};
</script>

<style scoped>
.file-row--selected {
  background: var(--rapo-selected);
}
.file-row--highlight > td {
  background: var(--rapo-highlight);
}
.selection-bar {
  min-height: 40px;
  padding: 2px 8px;
  background: var(--rapo-selected);
  border-radius: 4px;
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
.file-name-cell .view-btn {
  margin: -4px 0;
}
.name-filter {
  min-width: 200px;
}
.log-text {
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
}
.file-facts {
  font-family: var(--rapo-font-mono);
  word-break: break-all;
}
.file-facts span {
  display: inline-block;
  width: 70px;
  color: var(--rapo-muted);
}
</style>
