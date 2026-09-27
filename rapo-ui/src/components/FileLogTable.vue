<template>
  <div class="column no-wrap">
    <div class="row items-center q-gutter-sm q-mb-sm">
      <q-btn flat dense round icon="fas fa-chevron-left" @click="shiftDay(-1)">
        <q-tooltip>Previous day</q-tooltip>
      </q-btn>
      <div class="text-subtitle1 text-weight-medium">{{ day || "Today" }}</div>
      <q-btn flat dense round icon="fas fa-chevron-right" :disable="!day || day >= today" @click="shiftDay(1)">
        <q-tooltip>Next day</q-tooltip>
      </q-btn>
      <q-btn v-if="day && day !== today" flat dense no-caps label="Today" color="primary" @click="load(null)" />
      <q-btn flat dense round icon="fas fa-sync" :loading="loading" @click="load(day)">
        <q-tooltip>Reload</q-tooltip>
      </q-btn>
      <q-space />
      <q-chip
        v-for="entry in statusCounts"
        :key="entry.status"
        clickable
        :outline="statusFilter !== entry.status"
        :title="fileStatus(entry.status).label"
        @click="statusFilter = statusFilter === entry.status ? null : entry.status">
        <q-avatar :icon="fileStatus(entry.status).icon" :color="fileStatus(entry.status).color" text-color="white" />
        {{ entry.count }}
      </q-chip>
      <q-input v-model="search" dense outlined clearable debounce="200" placeholder="Search file name" style="width: 260px" />
    </div>
    <div v-if="truncated" class="text-orange-9 q-mb-sm">Only the latest {{ files.length }} files of the day are listed.</div>

    <q-virtual-scroll
      type="table"
      class="list-table file-log-table"
      style="max-height: 60vh"
      :items="shownFiles"
      :virtual-scroll-item-size="33"
      :virtual-scroll-sticky-size-start="33"
      :table-colspan="11">
      <template #before>
        <thead>
          <tr class="bg-blue-grey-2">
            <th class="text-center">Status</th>
            <th class="text-left">File</th>
            <th class="text-right">Size</th>
            <th class="text-left">File date</th>
            <th class="text-left">Load start</th>
            <th class="text-right">Runtime</th>
            <th class="text-right">Read</th>
            <th class="text-right">Written</th>
            <th class="text-right">Rejected</th>
            <th class="text-center">Dup.</th>
            <th class="text-left">Server</th>
          </tr>
        </thead>
      </template>
      <template #default="{ item: file }">
        <tr :key="file.id" class="clickable-row" @click="openLog(file)">
          <td class="text-center">
            <q-icon :name="fileStatus(file.filestatus).icon" :color="fileStatus(file.filestatus).color" size="16px" :title="fileStatus(file.filestatus).label" />
          </td>
          <td class="text-left ellipsis" :title="file.inputfullfilename">{{ file.inputfilename }}</td>
          <td class="text-right">{{ formatBytes(file.filesize) }}</td>
          <td class="text-left">{{ toDateTimeString(file.filedate) }}</td>
          <td class="text-left">{{ toDateTimeString(file.startloaddate) }}</td>
          <td class="text-right">{{ file.runtime != null ? `${file.runtime} s` : "" }}</td>
          <td class="text-right">{{ formatNumber(file.recordsread || 0) }}</td>
          <td class="text-right">{{ formatNumber(file.recordswrite || 0) }}</td>
          <td class="text-right" :class="{ 'text-red-6 text-weight-bold': file.recordsreject > 0 }">{{ formatNumber(file.recordsreject || 0) }}</td>
          <td class="text-center">
            <q-icon v-if="file.duplicate" name="fas fa-clone" color="purple-3" size="14px" title="Duplicate" />
          </td>
          <td class="text-left ellipsis">{{ file.server }}</td>
        </tr>
      </template>
      <template #after>
        <tbody v-if="!shownFiles.length">
          <tr>
            <td colspan="11" class="text-center text-grey-7 q-pa-lg">{{ loading ? "Loading..." : "No files loaded on this day" }}</td>
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
          <div><span>Output</span>{{ logFile.outputfullfilename }}</div>
          <div><span>Loaded</span>{{ toDateTimeString(logFile.startloaddate) }} &ndash; {{ toDateTimeString(logFile.endloaddate) }}</div>
          <div><span>MD5</span>{{ logFile.md5 }}</div>
          <div><span>File ID</span>{{ logFile.id }}</div>
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
import { api, notifyError } from "../api";
import { fileStatus } from "../constants";
import { copyText, formatNumber, toDateTimeString } from "../utils/format";
import { formatBytes } from "../utils/datasources";

// The files one datasource loaded on one day (get-ds-file-log, the database's day), newest first. A row opens the log
// text PDI Core wrote for it.
export default {
  name: "FileLogTable",
  props: {
    datasourceId: { type: Number, required: true },
  },
  data() {
    return {
      loading: false,
      day: null,
      today: null,
      files: [],
      truncated: false,
      search: "",
      statusFilter: null,
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
      return [...counts.entries()].map(([status, count]) => ({ status, count }));
    },
    shownFiles() {
      const needle = (this.search || "").toLowerCase();
      return this.files.filter(
        (file) => (!this.statusFilter || file.filestatus === this.statusFilter) && (!needle || (file.inputfilename || "").toLowerCase().includes(needle))
      );
    },
  },
  watch: {
    datasourceId() {
      this.load(null);
    },
  },
  methods: {
    fileStatus,
    formatBytes,
    formatNumber,
    toDateTimeString,
    async load(day) {
      this.loading = true;
      try {
        const result = await api("get-ds-file-log", { params: { id: this.datasourceId, date: day }, loadingBar: false });
        this.day = result.date;
        this.today = result.today;
        this.files = Object.freeze(result.files.map(Object.freeze));
        this.truncated = result.truncated;
        this.statusFilter = null;
      } catch (error) {
        notifyError("The file log could not be loaded.", error);
      } finally {
        this.loading = false;
      }
    },
    shiftDay(days) {
      const date = new Date(`${this.day}T12:00:00`);
      date.setDate(date.getDate() + days);
      const pad = (value) => String(value).padStart(2, "0");
      this.load(`${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`);
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
  mounted() {
    this.load(null);
  },
};
</script>

<style scoped>
.clickable-row {
  cursor: pointer;
}
.clickable-row:hover {
  background: rgba(0, 0, 0, 0.03);
}
.file-log-table :deep(table) {
  table-layout: fixed;
  min-width: 1100px;
}
.file-log-table th:nth-child(1) { width: 60px; }
.file-log-table th:nth-child(3) { width: 80px; }
.file-log-table th:nth-child(4) { width: 150px; }
.file-log-table th:nth-child(5) { width: 150px; }
.file-log-table th:nth-child(6) { width: 80px; }
.file-log-table th:nth-child(7) { width: 80px; }
.file-log-table th:nth-child(8) { width: 80px; }
.file-log-table th:nth-child(9) { width: 80px; }
.file-log-table th:nth-child(10) { width: 50px; }
.file-log-table th:nth-child(11) { width: 160px; }
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
