<template>
  <q-dialog v-model="visible">
    <q-card class="column no-wrap" style="width: 1400px; max-width: 95vw; height: 85vh">
      <q-card-section class="row items-center q-py-sm q-gutter-sm">
        <div class="text-h6">{{ title }}</div>
        <q-btn-toggle
          v-model="kind"
          dense
          no-caps
          unelevated
          toggle-color="primary"
          color="grey-3"
          text-color="grey-9"
          :options="kindOptions"
          @update:model-value="load" />
        <q-space />
        <q-btn aria-label="Read the directories again" flat round dense icon="fas fa-sync" :loading="loading" @click="load">
          <q-tooltip>Read the directories again</q-tooltip>
        </q-btn>
        <q-btn aria-label="Download the listed files as CSV" flat round dense icon="fas fa-file-csv" :disable="!sortedFiles.length" @click="exportCsv">
          <q-tooltip>Download the listed files as CSV</q-tooltip>
        </q-btn>
        <q-btn aria-label="Close" flat round icon="fas fa-times" v-close-popup />
      </q-card-section>
      <q-separator />

      <q-card-section class="q-py-sm">
        <div v-for="directory in result.directories" :key="directory.path" class="row items-center q-gutter-x-sm directory-line">
          <q-icon :name="directoryIcon(directory)" :color="directoryColor(directory)" size="14px" />
          <span class="text-mono">{{ directory.path }}</span>
          <span v-if="!directory.exists" class="text-red-6">does not exist on this server</span>
          <span v-else-if="!directory.readable" class="text-red-6">not readable: {{ directory.error }}</span>
          <span v-else-if="directory.capped" class="text-orange-10">read up to [DATASOURCES] scan_max_entries files</span>
        </div>
        <div class="row items-center q-gutter-x-md q-mt-xs text-grey-8">
          <span>{{ formatNumber(result.total) }} file(s) read</span>
          <span>{{ formatNumber(result.matched) }} matching FILES_MASK</span>
          <span>{{ formatNumber(result.clean) }} clean-up file(s) under {{ formatBytes(result.clean_max_bytes) }}</span>
          <span v-if="!result.subdirs">subdirectories not scanned</span>
          <span v-if="masksOverridden" class="text-orange-9">with the editor's unsaved masks</span>
          <span v-if="result.mask_error" class="text-red-6">FILES_MASK is not valid: {{ result.mask_error }}</span>
          <span v-if="result.clean_mask_error" class="text-red-6">INPUT_CLEAN_FILES_MASK is not valid: {{ result.clean_mask_error }}</span>
          <span v-if="result.truncated" class="text-orange-9">
            <q-icon name="fas fa-cut" size="12px" /> The list is cut, see [DATASOURCES] list_max_files and scan_max_entries
          </span>
        </div>
      </q-card-section>

      <q-card-section class="q-py-none">
        <q-input v-model="search" dense outlined clearable debounce="200" placeholder="Search name or subdirectory" style="max-width: 420px">
          <template #prepend><q-icon name="fas fa-search" size="14px" /></template>
        </q-input>
      </q-card-section>

      <q-card-section class="col q-pt-sm">
        <q-virtual-scroll
          type="table"
          class="list-table file-table fit"
          :items="sortedFiles"
          :virtual-scroll-item-size="33"
          :virtual-scroll-sticky-size-start="28"
          :table-colspan="8">
          <template #before>
            <thead>
              <tr class="bg-blue-grey-2">
                <th v-for="column in columns" :key="column.key" :title="column.title" :class="['text-' + column.align, { sortable: column.sort }]" @click="column.sort && toggleSort(sort, column.key)" v-keyboard="column.sort" :aria-sort="column.sort ? ariaSort(sort, column.key) : undefined">
                  {{ column.label }}
                  <q-icon v-if="sort.key === column.key" :name="sortIcon(sort)" size="12px" />
                </th>
                <th></th>
              </tr>
            </thead>
          </template>
          <template #default="{ item: file }">
            <tr :key="file.path" :class="{ 'text-grey-7': kind === 'all' && !file.matches }">
              <td class="text-left ellipsis text-mono" :title="file.path">
                <span v-if="file.subdir" class="text-grey-7">{{ file.subdir }}/</span>{{ file.name }}
              </td>
              <td class="text-right number-cell">{{ formatBytes(file.size) }}</td>
              <td class="text-left">{{ toDateTimeString(file.modified) }}</td>
              <td class="text-right number-cell">{{ formatAge(file.age) }}</td>
              <td class="text-left ellipsis">{{ file.owner }}:{{ file.group }}</td>
              <td class="text-left text-mono">{{ file.mode }}</td>
              <td class="text-left ellipsis">
                <q-badge v-if="file.young" color="amber-8" text-color="grey-10" class="q-mr-xs" :title="`Modified less than ${result.young_seconds} s ago: PDI Core skips it for now`">young</q-badge>
                <q-badge v-if="file.pdi_deletes" color="red-5" class="q-mr-xs" :title="`Under ${result.pdi_clean_bytes} bytes: the PDI Core clean-up deletes it`">
                  PDI deletes
                </q-badge>
                <q-badge v-else-if="file.clean" color="blue-grey-5" class="q-mr-xs" :title="`Matches INPUT_CLEAN_FILES_MASK, but PDI Core deletes only files under ${result.pdi_clean_bytes} bytes`">
                  clean mask
                </q-badge>
                <span v-if="kind === 'all'" class="text-caption">{{ file.reason }}</span>
              </td>
              <td class="text-right">
                <q-btn aria-label="Copy the path" flat round dense size="sm" icon="fas fa-copy" color="grey-7" @click="copyPath(file)">
                  <q-tooltip>Copy the path</q-tooltip>
                </q-btn>
              </td>
            </tr>
          </template>
          <template #after>
            <tbody v-if="!sortedFiles.length">
              <tr>
                <td colspan="8" class="text-center text-grey-7 q-pa-lg">{{ loading ? "Reading the directories..." : "No files" }}</td>
              </tr>
            </tbody>
          </template>
        </q-virtual-scroll>
      </q-card-section>
    </q-card>
  </q-dialog>
</template>

<script>
import { api, notifyError } from "../api";
import { copyAndNotify } from "../runActions";
import { formatBytes, formatNumber, toDateTimeString } from "../utils/format";
import { ariaSort, sortIcon, sortRows, toggleSort } from "../utils/sort";
import { downloadText, formatAge, toCsv } from "../utils/datasources";

const KINDS = {
  match: "Matching files",
  all: "All files",
  clean: "Clean-up files",
};

const COLUMNS = [
  { key: "name", label: "Name", align: "left", sort: true, title: "The file's name, under its subdirectory" },
  { key: "size", label: "Size", align: "right", sort: true, title: "The file's size" },
  { key: "modified", label: "Modified", align: "left", sort: true, title: "When the file was last modified" },
  { key: "age", label: "Age", align: "right", sort: true, title: "How long ago the file was last modified" },
  { key: "owner", label: "Owner", align: "left", sort: true, title: "The file's owner and group" },
  { key: "mode", label: "Mode", align: "left", sort: false, title: "The file's permissions" },
  { key: "reason", label: "Flags", align: "left", sort: true, title: "Why PDI Core skips or deletes the file, or why it does not match (All files)" },
];

// The files in the input directories of one saved datasource (get-ds-files), read-only: the files FILES_MASK picks
// up, every file with why it is not picked up, or the small files INPUT_CLEAN_FILES_MASK names. The editor passes its
// unsaved masks, so they can be tried before a save; the directories are always the saved ones.
export default {
  name: "FileListDialog",
  data() {
    return {
      visible: false,
      loading: false,
      datasource: null,
      kind: "match",
      overrides: {},
      search: "",
      sort: { key: null, dir: "asc" },
      result: emptyResult(),
      columns: COLUMNS,
    };
  },
  computed: {
    title() {
      return this.datasource ? this.datasource.sourcename : "Files";
    },
    kindOptions() {
      return Object.entries(KINDS).map(([value, label]) => ({ value, label }));
    },
    masksOverridden() {
      return Object.values(this.overrides).some((value) => value !== undefined && value !== null);
    },
    filteredFiles() {
      const needle = (this.search || "").toLowerCase();
      if (!needle) {
        return this.result.files;
      }
      return this.result.files.filter((file) => `${file.subdir}/${file.name}`.toLowerCase().includes(needle));
    },
    sortedFiles() {
      const key = this.sort.key;
      if (!key) {
        return this.filteredFiles;
      }
      const valueOf = key === "name" ? (file) => `${file.subdir}/${file.name}` : (file) => file[key];
      return sortRows(this.filteredFiles, valueOf, this.sort.dir);
    },
  },
  methods: {
    formatAge,
    formatBytes,
    formatNumber,
    sortIcon,
    toDateTimeString,
    ariaSort,
    toggleSort,
    // datasource is the saved row ({id, sourcename}); overrides the editor's {files_mask, clean_mask, subdirs}.
    open(datasource, kind = "match", overrides = {}) {
      this.datasource = datasource;
      this.kind = kind;
      this.overrides = overrides;
      this.search = "";
      this.result = emptyResult();
      this.visible = true;
      this.load();
    },
    async load() {
      this.loading = true;
      try {
        this.result = await api("get-ds-files", {
          params: { id: this.datasource.id, kind: this.kind, ...this.overrides },
        });
      } catch (error) {
        notifyError("The files could not be listed.", error);
      } finally {
        this.loading = false;
      }
    },
    directoryIcon(directory) {
      return !directory.exists ? "fas fa-folder-minus" : directory.readable ? "fas fa-folder-open" : "fas fa-lock";
    },
    directoryColor(directory) {
      return directory.exists && directory.readable ? "teal" : "red-5";
    },
    async copyPath(file) {
      await copyAndNotify(file.path, "Path", "The path was not copied.");
    },
    exportCsv() {
      const columns = [
        { label: "Directory", value: (file) => file.directory },
        { label: "Subdirectory", value: (file) => file.subdir },
        { label: "Name", value: (file) => file.name },
        { label: "Size", value: (file) => file.size },
        { label: "Modified", value: (file) => toDateTimeString(file.modified) },
        { label: "Age (s)", value: (file) => file.age },
        { label: "Owner", value: (file) => file.owner },
        { label: "Group", value: (file) => file.group },
        { label: "Mode", value: (file) => file.mode },
        { label: "Matches FILES_MASK", value: (file) => (file.matches ? "Y" : "N") },
        { label: "Clean-up file", value: (file) => (file.clean ? "Y" : "N") },
        { label: "Reason", value: (file) => file.reason },
      ];
      downloadText(toCsv(this.sortedFiles, columns), `${this.title}_${this.kind}_files.csv`);
    },
  },
};

function emptyResult() {
  return { files: [], directories: [], total: 0, matched: 0, clean: 0, truncated: false, subdirs: true };
}
</script>

<style scoped>
.directory-line {
  font-size: 13px;
}
.file-table :deep(table) {
  table-layout: fixed;
  min-width: 1000px;
}
.file-table th:nth-child(2) { width: 90px; }
.file-table th:nth-child(3) { width: 160px; }
.file-table th:nth-child(4) { width: 110px; }
.file-table th:nth-child(5) { width: 150px; }
.file-table th:nth-child(6) { width: 110px; }
.file-table th:nth-child(7) { width: 300px; }
.file-table th:nth-child(8) { width: 50px; }
</style>
