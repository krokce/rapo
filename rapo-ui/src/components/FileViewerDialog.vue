<template>
  <q-dialog v-model="visible" @show="shown" @hide="close">
    <q-card class="column no-wrap file-viewer-card">
      <!-- The file and its facts as the file log has them, then what is shown: the file as text or ASN.1, and the
           records it loaded (below it, or alone). -->
      <q-card-section class="q-pt-sm q-pb-xs">
        <div class="row items-center no-wrap q-gutter-x-md">
          <q-icon name="fas fa-file-alt" color="blue-grey-6" size="20px" />
          <div class="text-h6 ellipsis file-title" :title="file && file.inputfilename">{{ (info && info.name) || (file && file.inputfilename) }}</div>
          <div v-if="file" class="row items-center no-wrap q-gutter-x-md text-blue-grey-8 header-facts">
            <router-link v-if="file.sourcename" class="viewer-link text-weight-bold" :to="{ name: 'edit-datasource', params: { id: datasourceId !== null ? datasourceId : file.sourceid } }">
              {{ file.sourcename }}
              <q-tooltip anchor="top middle" self="bottom middle">Edit the datasource</q-tooltip>
            </router-link>
            <div class="text-no-wrap">
              File ID <strong>{{ file.id }}</strong>
            </div>
            <q-chip v-if="file.filestatus" class="q-my-none q-mr-none">
              <q-avatar :icon="fileStatus(file.filestatus).icon" :color="fileStatus(file.filestatus).color" text-color="white" />
              {{ fileStatus(file.filestatus).label }}
            </q-chip>
            <div v-if="headerFacts" class="text-no-wrap">{{ headerFacts }}</div>
          </div>
          <q-space />
          <q-btn v-if="file && file.outputfullfilename" aria-label="Copy the path of the file" flat round dense color="grey-7" icon="fas fa-copy" @click="copyPath">
            <q-tooltip anchor="top middle" self="bottom middle" max-width="600px">Copy the path: {{ file.outputfullfilename }}</q-tooltip>
          </q-btn>
          <q-btn v-if="viewable" aria-label="Download the file" flat round dense color="grey-7" icon="fas fa-download" :loading="downloading" @click="download">
            <q-tooltip anchor="top middle" self="bottom middle">Download the file</q-tooltip>
          </q-btn>
          <q-btn aria-label="Close" flat round icon="fas fa-times" v-close-popup />
        </div>
        <div class="row items-center q-mt-xs">
          <q-chip
            v-for="chip in viewChips"
            :key="chip.value"
            clickable
            class="q-ml-none q-mr-sm"
            :class="{ 'chip-selected': chip.on }"
            :aria-pressed="chip.on"
            @click="chip.value === 'records' ? toggleRecords() : pickView(chip.value)">
            <q-avatar :icon="chip.icon" :color="chip.color" text-color="white" />
            <span class="text-weight-bold">{{ chip.label }}</span><span v-if="chip.count != null" class="q-ml-xs">({{ formatNumber(chip.count) }})</span>
            <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]" max-width="360px">{{ chip.title }}</q-tooltip>
          </q-chip>
        </div>
      </q-card-section>
      <q-separator />

      <!-- The file and the records it loaded, one above the other: the file pane stays in place (CodeMirror is never
           moved), the split only sizes the two. -->
      <div ref="panes" class="col column no-wrap viewer-panes">
        <div v-show="layout !== 'db'" class="column no-wrap file-pane" :style="filePaneStyle">
          <asn1-pane v-if="viewAs === 'asn1' && asn1Shown" :key="`${file.id}|${settingsVersion}`" class="col" :file-id="file.id" :datasource-id="datasourceId" :saved="settings.asn1 || null" @saved="settingsSaved" @facts="asn1Facts = $event" />
          <q-card-section v-show="viewAs === 'text'" class="row items-start q-gutter-sm q-py-sm">
            <q-input
              v-model="search"
              class="col"
              dense
              outlined
              clearable
              debounce="500"
              label="Search the whole file"
              :error="Boolean(searchError)"
              :error-message="searchError"
              hide-bottom-space
              @keyup.enter="startSearch">
              <template #prepend><q-icon name="fas fa-search" size="16px" /></template>
              <template #append>
                <q-btn aria-label="Match case" flat dense no-caps class="viewer-toggle" :color="matchCase ? 'primary' : 'grey-8'" :class="{ 'viewer-toggle--on': matchCase }" label="Aa" @click="matchCase = !matchCase">
                  <q-tooltip>Match case</q-tooltip>
                </q-btn>
                <q-btn aria-label="Regular expression" flat dense no-caps class="viewer-toggle" :color="regex ? 'primary' : 'grey-8'" :class="{ 'viewer-toggle--on': regex }" label=".*" @click="regex = !regex">
                  <q-tooltip>Regular expression (Python's re)</q-tooltip>
                </q-btn>
              </template>
            </q-input>
            <q-input
              :model-value="layoutText"
              class="viewer-delimiter"
              dense
              outlined
              label="Delimiter"
              :error="Boolean(parsedLayout.error)"
              :error-message="parsedLayout.error"
              hide-bottom-space
              input-class="text-mono"
              @update:model-value="typeLayout">
              <template #append>
                <q-btn
                  v-if="layoutUnsaved"
                  aria-label="Save the delimiter for the datasource"
                  flat
                  dense
                  round
                  size="sm"
                  icon="fas fa-save"
                  :color="layoutLocalOnly ? 'orange-9' : 'primary'"
                  :loading="savingLayout"
                  @click="saveLayout">
                  <q-tooltip max-width="320px">{{ layoutLocalOnly ? "Saved only in this browser: save it for the datasource (for everyone)" : "Save for the datasource: its files open with this delimiter (for everyone)" }}</q-tooltip>
                </q-btn>
                <q-badge v-if="layoutAuto" color="blue-grey-6" text-color="white" label="auto" class="q-mr-xs">
                  <q-tooltip>Detected from the first lines; type to change it</q-tooltip>
                </q-badge>
                <q-btn v-else aria-label="Detect the delimiter" flat dense round size="sm" icon="fas fa-undo" @click="resetLayout">
                  <q-tooltip>Detect the delimiter again</q-tooltip>
                </q-btn>
                <q-btn aria-label="Delimiter presets" flat dense round size="sm" icon="fas fa-caret-down">
                  <q-menu anchor="bottom right" self="top right">
                    <q-list dense style="min-width: 220px">
                      <q-item v-for="preset in presets" :key="preset.label" clickable v-close-popup @click="pickLayout(preset.text)">
                        <q-item-section>{{ preset.label }}</q-item-section>
                        <q-item-section side class="text-mono">{{ preset.text }}</q-item-section>
                      </q-item>
                      <q-item clickable v-close-popup @click="pickWidths">
                        <q-item-section>
                          <q-item-label>Fixed widths…</q-item-label>
                          <q-item-label caption>Column widths in characters, e.g. 10,5,8</q-item-label>
                        </q-item-section>
                      </q-item>
                      <q-item clickable v-close-popup @click="pickLayout('')">
                        <q-item-section>None</q-item-section>
                        <q-item-section side>plain text</q-item-section>
                      </q-item>
                      <q-separator />
                      <q-item clickable v-close-popup @click="resetLayout">
                        <q-item-section>Detect</q-item-section>
                        <q-item-section side class="text-mono">{{ detectedText || "none" }}</q-item-section>
                      </q-item>
                    </q-list>
                  </q-menu>
                </q-btn>
              </template>
              <q-tooltip anchor="top middle" self="bottom middle" :delay="600" max-width="360px">
                Any delimiter (several characters too, \t for a tab), or column widths in characters separated by commas (10,5,8)
              </q-tooltip>
            </q-input>
          </q-card-section>

          <!-- What the lines are, and the button reading more of them (scrolling to the end does it too). -->
          <div v-show="viewAs === 'text'" class="row items-center no-wrap q-px-md q-pb-sm q-gutter-x-sm text-caption text-grey-8 viewer-status">
            <q-chip v-if="savedGrep" dense clickable color="orange-1" text-color="orange-10" icon="fas fa-arrow-left" class="q-ml-none" @click="backToResults">
              Back to results
              <q-tooltip>The search results, as they were</q-tooltip>
            </q-chip>
            <span class="ellipsis">{{ statusText }}</span>
            <q-spinner v-if="loading" size="14px" color="primary" />
            <span v-if="capped" class="text-orange-9 ellipsis">The viewer keeps {{ formatNumber(maxLines) }} lines at most: search or download the file to see further.</span>
            <q-space />
            <q-btn
              v-if="mode === 'head'"
              outline
              dense
              no-caps
              color="primary"
              icon="fas fa-angle-double-down"
              padding="4px 10px"
              :label="`Load ${formatNumber(BIG_STEP)} more`"
              :disable="!canLoadMore"
              :loading="loading"
              @click="loadMore(BIG_STEP)" />
            <q-btn v-else outline dense no-caps color="primary" icon="fas fa-search-plus" padding="4px 10px" label="Find more" :disable="!canLoadMore" :loading="loading" @click="loadMore()" />
          </div>

          <div v-show="viewAs === 'text'" class="col relative-position viewer-body">
            <div v-if="!viewable" class="absolute-center text-grey-7 text-center">
              <q-icon name="fas fa-archive" size="32px" class="q-mb-sm" /><br />
              The archived file can not be shown.
            </div>
            <div ref="editor" class="file-viewer" />
            <div v-if="info && info.binary" class="absolute-center text-grey-7 text-center">
              <q-icon name="fas fa-file-excel" size="32px" class="q-mb-sm" /><br />
              A binary file that does not start as ASN.1.
              <div class="q-mt-md">
                <q-btn outline dense no-caps color="primary" icon="fas fa-sitemap" padding="4px 10px" label="Decode as ASN.1" @click="pickView('asn1')">
                  <q-tooltip max-width="320px">Read it as BER anyway, e.g. after a header: set the start offset there</q-tooltip>
                </q-btn>
              </div>
            </div>
          </div>

        </div>
        <div v-if="layout === 'split'" class="viewer-split-handle" title="Drag to resize" @mousedown.prevent="startDrag" />
        <div v-if="recordsShown" v-show="layout !== 'file'" class="col q-px-md q-pt-sm q-pb-md records-wrap">
          <file-records-pane :file-id="file.id" />
        </div>
      </div>
    </q-card>
  </q-dialog>
</template>

<script>
import { Dark } from "quasar";
import { mapGetters } from "vuex";
import { EditorState } from "@codemirror/state";
import { EditorView, lineNumbers, highlightSpecialChars } from "@codemirror/view";
import { api, notifyError } from "../api";
import { darkExtensions } from "../utils/codeTheme";
import { columnColors, DELIMITER_PRESETS, delimiterText, detectDelimiter, headerNames, matchMarks, parseLayout, refreshDecorations, searchExpression } from "../utils/csvView";
import { fileStatus } from "../constants";
import { downloadFiles } from "../utils/datasources";
import { formatBytes, formatNumber } from "../utils/format";
import { copyAndNotify } from "../runActions";
import FileRecordsPane from "./FileRecordsPane.vue";
import Asn1Pane from "./asn1/Asn1Pane.vue";

const BIG_STEP = 1000;
// Pixels from the bottom at which scrolling loads the next lines.
const NEAR_BOTTOM = 300;
const DEFAULT_MAX_LINES = 50000;
// The file pane's share of the height when the records are shown below it; the view last picked for the files of a
// datasource ({view: text|asn1, records}); the delimiter each datasource had in this browser before the server kept it
// (get-viewer-settings), only read to offer saving it.
const SPLIT_KEY = "rapo_viewer_split";
const VIEW_KEY = "rapo_viewer_view_";
const LAYOUT_KEY = "rapo_viewer_layout_";

function readStorage(key) {
  try {
    const value = localStorage.getItem(key);
    return value ? JSON.parse(value) : null;
  } catch {
    return null;
  }
}

function writeStorage(key, value) {
  try {
    if (value === null) {
      localStorage.removeItem(key);
    } else {
      localStorage.setItem(key, JSON.stringify(value));
    }
  } catch {
    // Storage off: nothing is remembered.
  }
}

// Shows a file of the file log a few lines at a time (view-ds-file), or the lines matching a search of the whole file
// (grep-ds-file). The server keeps nothing: each request goes on from the `next_offset` (an uncompressed byte offset)
// and `next_line` of the previous one. The lines are a read-only CodeMirror whose line numbers are the file's; the
// rows behind them are kept outside Vue's reactivity, as are the editor and its view.
export default {
  name: "FileViewerDialog",
  components: { Asn1Pane, FileRecordsPane },
  data() {
    return {
      BIG_STEP,
      visible: false,
      file: null,
      info: null,
      // head: the file from a line; grep: the lines matching `search`.
      mode: "head",
      search: "",
      matchCase: false,
      regex: false,
      searchError: null,
      // The Delimiter field: detected (auto) or as typed; detected is the delimiter found in the first lines.
      layoutAuto: true,
      typedLayout: "",
      detected: null,
      presets: DELIMITER_PRESETS,
      datasourceId: null,
      // The archived file can be read, and the datasource has tables (the records).
      viewable: true,
      hasTables: false,
      // What is shown: the file (as viewAs) and the records it loaded (below it, or alone); the file pane's share of
      // the height with both. recordsShown: the records pane was built (it stays once it was).
      fileShown: true,
      recordsOn: false,
      ratio: 50,
      recordsShown: false,
      loading: false,
      downloading: false,
      count: 0,
      nextOffset: 0,
      nextLine: 1,
      eof: false,
      // grep: the lines and bytes read so far, and whether the last request stopped at its time budget.
      scannedLines: 0,
      scannedBytes: 0,
      stopped: null,
      // The search results left by clicking a line, restored by Back to results.
      savedGrep: null,
      // text: the lines; asn1: the nodes (Asn1Pane). Picked by the user, else by the file: asn1 when it looks like BER,
      // else as last picked for the datasource, else asn1 when the datasource has a saved decoding.
      viewAs: "text",
      viewChosen: false,
      rememberedView: null,
      asn1Shown: false,
      // The ASN.1 pane's facts (uncompressed size, compression) for the header.
      asn1Facts: "",
      // The datasource's viewer settings ({layout, asn1}), and a delimiter only this browser remembered.
      settings: {},
      settingsVersion: 0,
      localLayout: null,
      savingLayout: false,
    };
  },
  computed: {
    ...mapGetters(["getEnvInfo"]),
    // file: the file pane alone; split: the records below it; db: the records alone.
    layout() {
      return !this.fileShown ? "db" : this.recordsOn ? "split" : "file";
    },
    // The chips of what is shown: Text and ASN.1 read the file one way or the other, Records toggles the loaded rows.
    viewChips() {
      const chips = [];
      if (this.viewable) {
        chips.push(
          { value: "text", label: "Text", icon: "fas fa-file-alt", color: "blue-grey-6", on: this.fileShown && this.viewAs === "text", title: "The file as lines of text" },
          { value: "asn1", label: "ASN.1", icon: "fas fa-sitemap", color: "indigo-6", on: this.fileShown && this.viewAs === "asn1", title: "The file as ASN.1 (BER, DER, CER) nodes" }
        );
      }
      if (this.hasTables) {
        const count = this.file && this.file.recordswrite != null ? this.file.recordswrite : null;
        chips.push({
          value: "records",
          label: "Records",
          icon: "fas fa-database",
          color: "teal-7",
          count,
          on: this.recordsOn,
          title: `The rows this file loaded into the datasource's tables, below the file or alone${count != null ? ` (the file log counts ${formatNumber(count)} written)` : ""}`,
        });
      }
      return chips;
    },
    // The size, compression and encoding of what the file pane reads, else the file log's size.
    headerFacts() {
      if (this.fileShown && this.viewAs === "asn1" && this.asn1Facts) {
        return this.asn1Facts;
      }
      if (this.fileShown && this.viewAs === "text" && this.info) {
        return this.facts;
      }
      return this.file && this.file.filesize != null ? formatBytes(this.file.filesize) : "";
    },
    // The delimiter as it would be saved: null when detected.
    layoutValue() {
      return this.layoutAuto ? null : this.typedLayout;
    },
    layoutUnsaved() {
      return this.datasourceId !== null && this.layoutValue !== (this.settings.layout === undefined ? null : this.settings.layout);
    },
    layoutLocalOnly() {
      return this.localLayout !== null && this.layoutValue === this.localLayout && this.settings.layout === undefined;
    },
    maxLines() {
      return (this.getEnvInfo && this.getEnvInfo.datasources_view_max_lines) || DEFAULT_MAX_LINES;
    },
    capped() {
      return this.count >= this.maxLines && !this.eof;
    },
    canLoadMore() {
      return Boolean(this.viewAs === "text" && this.info && !this.info.binary && !this.eof && !this.capped && !this.loading);
    },
    detectedText() {
      return delimiterText(this.detected);
    },
    layoutText() {
      return this.layoutAuto ? this.detectedText : this.typedLayout;
    },
    parsedLayout() {
      return parseLayout(this.layoutText);
    },
    headerNames() {
      return headerNames(this.info && this.info.header, this.parsedLayout);
    },
    filePaneStyle() {
      return this.layout === "split" ? { flex: `0 0 ${this.ratio}%` } : { flex: "1 1 auto" };
    },
    facts() {
      const info = this.info;
      const kind = info.compression === "gzip" ? "gzip" : info.compression.startsWith("zip:") ? `ZIP, ${info.compression.slice(4)}` : "plain";
      return `${formatBytes(info.size)} · ${kind} · ${info.encoding === "utf-8" ? "UTF-8" : "Latin-1"}`;
    },
    statusText() {
      if (!this.info || this.info.binary) {
        return "";
      }
      if (this.mode === "grep") {
        const where = this.eof ? "in the whole file" : `in the first ${formatNumber(this.scannedLines)} lines (${formatBytes(this.scannedBytes)})`;
        const paused = !this.eof && this.stopped === "time" ? " · the search paused, find more to go on" : "";
        return `${formatNumber(this.count)} matching line${this.count === 1 ? "" : "s"} ${where}${paused}`;
      }
      if (!this.count) {
        return this.eof ? "The file is empty." : "";
      }
      const first = this.rows[0].no;
      const last = this.rows[this.count - 1].no;
      return `Lines ${formatNumber(first)}–${formatNumber(last)}${this.eof ? " · end of file" : ""}`;
    },
  },
  watch: {
    search(value) {
      if (this.visible) {
        this.searchChanged(value);
      }
    },
    matchCase() {
      this.searchChanged(this.search);
    },
    regex() {
      this.searchChanged(this.search);
    },
    parsedLayout() {
      this.refresh();
    },
    headerNames() {
      this.refresh();
    },
  },
  created() {
    this.rows = [];
    this.request = 0;
  },
  methods: {
    formatNumber,
    fileStatus,
    // A file of the file log row ({id, inputfilename, sourcename, filestatus, ...}), shown from its first line. `layout`
    // db shows its records alone (the file log's database button), else the file with the records as last picked for
    // the datasource; `viewable` whether the archived file can be read, `hasTables` whether the datasource has tables.
    open(file, { datasourceId = null, layout = "file", viewable = true, hasTables = false } = {}) {
      this.file = file;
      this.datasourceId = datasourceId;
      this.viewable = viewable;
      this.hasTables = hasTables;
      const split = readStorage(SPLIT_KEY) || {};
      this.ratio = Math.min(Math.max(Number(split.ratio) || 50, 15), 85);
      const remembered = datasourceId !== null ? readStorage(VIEW_KEY + datasourceId) : null;
      this.rememberedView = remembered && (remembered.view === "text" || remembered.view === "asn1") ? remembered.view : null;
      if ((layout === "db" || !viewable) && hasTables) {
        this.fileShown = false;
        this.recordsOn = true;
      } else {
        this.fileShown = true;
        this.recordsOn = hasTables && Boolean(remembered && remembered.records);
      }
      this.recordsShown = this.recordsOn;
      const local = datasourceId !== null ? readStorage(LAYOUT_KEY + datasourceId) : null;
      this.localLayout = local && typeof local.text === "string" ? local.text : null;
      this.layoutAuto = this.localLayout === null;
      this.typedLayout = this.localLayout || "";
      this.settings = {};
      this.viewAs = "text";
      this.viewChosen = false;
      this.asn1Shown = false;
      this.asn1Facts = "";
      if (this.rememberedView === "asn1") {
        this.showAsn1();
      }
      this.loadSettings();
      this.info = null;
      this.search = "";
      this.matchCase = false;
      this.regex = false;
      this.searchError = null;
      this.detected = null;
      this.savedGrep = null;
      this.visible = true;
    },
    // After the opening transition: an editor measured while the dialog still scales opens scrolled. The file is read
    // once its pane is shown.
    shown() {
      this.dialogShown = true;
      if (this.fileShown) {
        this.startFile();
      }
    },
    // The datasource's delimiter and ASN.1 decoding: they replace what the viewer started with, unless already changed.
    async loadSettings() {
      const datasourceId = this.datasourceId;
      if (datasourceId === null) {
        return;
      }
      try {
        const result = await api("get-viewer-settings", { params: { sourceid: datasourceId }, loadingBar: false });
        if (datasourceId !== this.datasourceId || !this.visible) {
          return;
        }
        this.settings = result.settings || {};
        this.settingsVersion += 1;
        if (typeof this.settings.layout === "string" && (this.layoutAuto || this.typedLayout === this.localLayout)) {
          this.layoutAuto = false;
          this.typedLayout = this.settings.layout;
        }
        // A view picked last time for the datasource comes first.
        if (this.settings.asn1 && !this.viewChosen && !this.rememberedView) {
          this.showAsn1();
        }
      } catch (error) {
        // Without the settings the viewer works as before (e.g. the table is not created yet).
        this.settings = {};
      }
    },
    // Text or ASN.1: shows the file that way; the one already shown, with the records on, leaves the records alone.
    pickView(value) {
      if (!this.viewable) {
        return;
      }
      if (this.fileShown && this.viewAs === value) {
        if (this.recordsOn) {
          this.fileShown = false;
          this.remember();
        }
        return;
      }
      this.viewChosen = true;
      this.fileShown = true;
      if (value === "asn1") {
        this.showAsn1();
      } else {
        this.viewAs = "text";
      }
      this.remember();
      this.filePaneChanged();
    },
    // The records below the file, or not; never nothing shown: without them the file comes back.
    toggleRecords() {
      if (!this.hasTables || (this.recordsOn && !this.viewable)) {
        return;
      }
      this.recordsOn = !this.recordsOn;
      if (this.recordsOn) {
        this.recordsShown = true;
      } else {
        this.fileShown = true;
      }
      this.remember();
      this.filePaneChanged();
    },
    remember() {
      if (this.datasourceId !== null) {
        writeStorage(VIEW_KEY + this.datasourceId, { view: this.viewAs, records: this.recordsOn });
      }
    },
    // The file pane was shown or resized: its text is read once, and CodeMirror measures its new height.
    filePaneChanged() {
      this.$nextTick(() => {
        if (this.fileShown && this.viewAs === "text") {
          this.startFile();
        }
        if (this.view) {
          this.view.requestMeasure();
        }
      });
    },
    showAsn1() {
      this.viewAs = "asn1";
      this.asn1Shown = true;
    },
    settingsSaved(settings) {
      this.settings = settings || {};
    },
    startFile() {
      if (this.view || !this.viewable) {
        return;
      }
      this.createEditor();
      this.showHead(0, 1);
    },
    // Dragging the bar between the panes: the file pane's share, 15 to 85%.
    startDrag(event) {
      const box = this.$refs.panes.getBoundingClientRect();
      const move = (moved) => {
        this.ratio = Math.min(Math.max(((moved.clientY - box.top) / box.height) * 100, 15), 85);
      };
      const stop = () => {
        window.removeEventListener("mousemove", move);
        window.removeEventListener("mouseup", stop);
        writeStorage(SPLIT_KEY, { ratio: Math.round(this.ratio) });
        if (this.view) {
          this.view.requestMeasure();
        }
      };
      move(event);
      window.addEventListener("mousemove", move);
      window.addEventListener("mouseup", stop);
    },
    // The Delimiter field as typed; Save keeps it for the datasource.
    typeLayout(value) {
      this.layoutAuto = false;
      this.typedLayout = value || "";
    },
    pickLayout(text) {
      this.typeLayout(text);
    },
    // Widths that split line 1 as its delimiter does, as a start to edit.
    pickWidths() {
      const header = (this.info && this.info.header) || "";
      const layout = this.parsedLayout;
      let widths = [];
      if (layout.kind === "delimiter" && header) {
        widths = header.split(layout.delimiter).map((part) => part.length + layout.delimiter.length);
      }
      this.typeLayout(widths.length > 1 ? widths.join(",") : "10,10");
    },
    resetLayout() {
      this.layoutAuto = true;
      this.typedLayout = "";
    },
    async copyPath() {
      await copyAndNotify(this.file.outputfullfilename, "Path", "The path was not copied.");
    },
    async saveLayout() {
      this.savingLayout = true;
      try {
        const result = await api("save-viewer-settings", { method: "POST", body: { sourceid: this.datasourceId, layout: this.layoutValue } });
        this.settings = result.settings || {};
        writeStorage(LAYOUT_KEY + this.datasourceId, null);
        this.localLayout = null;
        this.$q.notify({ type: "positive", message: "The datasource's files open with this delimiter now." });
      } catch (error) {
        notifyError("The delimiter was not saved.", error);
      } finally {
        this.savingLayout = false;
      }
    },
    close() {
      this.request += 1;
      this.recordsShown = false;
      this.asn1Shown = false;
      this.viewAs = "text";
      this.dialogShown = false;
      if (this.view) {
        this.view.destroy();
        this.view = null;
      }
      this.rows = [];
    },
    createEditor() {
      if (this.view) {
        this.view.destroy();
      }
      const source = {
        rows: () => this.rows,
        layout: () => this.parsedLayout,
        header: () => this.headerNames,
        highlight: () => (this.mode === "head" ? searchExpression(this.search, { regex: this.regex, matchCase: this.matchCase }) : null),
      };
      const extensions = [
        lineNumbers({ formatNumber: (number) => (this.rows[number - 1] ? String(this.rows[number - 1].no) : "") }),
        highlightSpecialChars(),
        EditorState.readOnly.of(true),
        columnColors(source),
        matchMarks(source),
        EditorView.domEventHandlers({ click: (event, view) => this.lineClicked(event, view) }),
      ];
      if (Dark.isActive) {
        extensions.push(...darkExtensions);
      }
      this.view = new EditorView({ state: EditorState.create({ doc: "", extensions }), parent: this.$refs.editor });
      this.view.scrollDOM.addEventListener("scroll", () => this.scrolled(), { passive: true });
    },
    // Replaces the lines, or appends to them.
    setRows(rows, append) {
      const view = this.view;
      if (!view) {
        return;
      }
      const text = rows.map((row) => row.text).join("\n");
      if (append && this.rows.length) {
        this.rows = this.rows.concat(rows);
        view.dispatch({ changes: { from: view.state.doc.length, insert: "\n" + text } });
      } else {
        this.rows = rows;
        view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text }, selection: { anchor: 0 }, scrollIntoView: true });
        view.scrollDOM.scrollTop = 0;
      }
      this.count = this.rows.length;
    },
    refresh() {
      if (this.view) {
        this.view.dispatch({ effects: refreshDecorations.of(null) });
      }
    },
    // The file from a line (an offset of a line start): its first lines replace the shown ones.
    async showHead(offset, line) {
      this.mode = "head";
      this.resetCursor(offset, line);
      await this.fetch(false);
    },
    resetCursor(offset, line) {
      this.request += 1;
      this.nextOffset = offset;
      this.nextLine = line;
      this.eof = false;
      this.stopped = null;
      this.scannedLines = 0;
      this.scannedBytes = 0;
      this.loading = false;
    },
    searchChanged(value) {
      this.savedGrep = null;
      if (value && value.trim()) {
        this.startSearch();
      } else if (this.mode === "grep" || this.searchError) {
        this.searchError = null;
        this.showHead(0, 1);
      } else {
        this.refresh();
      }
    },
    async startSearch() {
      if (!this.search || !this.search.trim() || !this.view) {
        return;
      }
      this.savedGrep = null;
      this.mode = "grep";
      this.resetCursor(0, 1);
      this.setRows([], false);
      await this.fetch(false);
    },
    loadMore(lines) {
      if (this.canLoadMore) {
        this.fetch(true, lines);
      }
    },
    scrolled() {
      const scroller = this.view && this.view.scrollDOM;
      if (scroller && scroller.scrollTop + scroller.clientHeight > scroller.scrollHeight - NEAR_BOTTOM) {
        this.loadMore();
      }
    },
    // One request from the cursor; a request of an earlier view (another search, a jump, the dialog closed) is ignored.
    async fetch(append, lines) {
      const request = this.request;
      const grep = this.mode === "grep";
      this.loading = true;
      try {
        const params = { id: this.file.id, offset: this.nextOffset, line: this.nextLine };
        const result = grep
          ? await api("grep-ds-file", { params: { ...params, pattern: this.search, regex: this.regex, case: this.matchCase }, loadingBar: false })
          : await api("view-ds-file", { params: { ...params, lines: Math.min(lines || 0, this.maxLines - this.count) || undefined }, loadingBar: false });
        if (request !== this.request) {
          return;
        }
        this.searchError = null;
        this.info = result;
        if (result.binary && result.asn1 && !this.viewChosen) {
          this.showAsn1();
        }
        const rows = grep ? result.matches : result.lines;
        const room = this.maxLines - (append ? this.count : 0);
        this.setRows(rows.slice(0, room), append);
        if (this.detected === null && !grep && result.lines.length) {
          this.detected = detectDelimiter([result.header, ...result.lines.map((row) => row.text)]);
        }
        this.nextOffset = result.next_offset;
        this.nextLine = result.next_line;
        this.eof = result.eof;
        if (grep) {
          this.scannedLines += result.scanned_lines;
          this.scannedBytes += result.scanned_bytes;
          this.stopped = result.stopped;
        }
        this.loading = false;
        // A short page or few matches leave no scroll bar: go on while the editor is not full.
        this.$nextTick(() => this.scrolled());
      } catch (error) {
        if (request !== this.request) {
          return;
        }
        this.loading = false;
        if (grep && error.status === 400) {
          this.searchError = error.message;
        } else {
          notifyError(grep ? "The file was not searched." : "The file was not read.", error);
        }
      }
    },
    // A click on a search result (not the end of a selection) shows the file from that line.
    lineClicked(event, view) {
      if (this.mode !== "grep" || !view.state.selection.main.empty) {
        return false;
      }
      const position = view.posAtCoords({ x: event.clientX, y: event.clientY });
      if (position === null) {
        return false;
      }
      const row = this.rows[view.state.doc.lineAt(position).number - 1];
      if (!row) {
        return false;
      }
      this.savedGrep = {
        rows: this.rows,
        cursor: { nextOffset: this.nextOffset, nextLine: this.nextLine, eof: this.eof, stopped: this.stopped },
        scanned: { scannedLines: this.scannedLines, scannedBytes: this.scannedBytes },
        scrollTop: view.scrollDOM.scrollTop,
      };
      const saved = this.savedGrep;
      this.showHead(row.offset, row.no).then(() => (this.savedGrep = saved));
      return true;
    },
    backToResults() {
      const saved = this.savedGrep;
      if (!saved) {
        return;
      }
      this.savedGrep = null;
      this.mode = "grep";
      this.request += 1;
      this.loading = false;
      this.setRows(saved.rows, false);
      Object.assign(this, saved.cursor, saved.scanned);
      this.$nextTick(() => {
        if (this.view) {
          this.view.scrollDOM.scrollTop = saved.scrollTop;
        }
      });
    },
    async download() {
      this.downloading = true;
      try {
        await downloadFiles([this.file.id], this.file.inputfilename);
      } catch (error) {
        notifyError("The file was not downloaded.", error);
      } finally {
        this.downloading = false;
      }
    },
  },
};
</script>

<style scoped>
.file-viewer-card {
  width: 98vw;
  max-width: 98vw;
  height: 95vh;
  max-height: 95vh;
}
.viewer-panes {
  min-height: 0;
}
.file-pane {
  min-height: 0;
}
.records-wrap {
  min-height: 0;
}
/* The name takes what the facts leave, and is cut first. */
.file-title {
  min-width: 120px;
  flex: 0 1 auto;
}
.header-facts {
  flex: 0 1 auto;
  min-width: 0;
}
.viewer-link {
  color: var(--rapo-teal);
  text-decoration: none;
  white-space: nowrap;
}
.viewer-link:hover {
  text-decoration: underline;
}
.viewer-delimiter {
  width: 220px;
}
.viewer-status {
  min-height: 28px;
}
.viewer-body {
  min-height: 0;
  padding: 0 16px 12px;
}
.file-viewer {
  height: 100%;
}
.file-viewer :deep(.cm-editor) {
  height: 100%;
  max-height: none;
  border: 1px solid var(--rapo-code-border);
  border-radius: 0.25em;
}
.file-viewer :deep(.cm-editor.cm-focused) {
  outline: none;
}
.file-viewer :deep(.cm-cursor) {
  display: none !important;
}
.file-viewer :deep(.cm-content) {
  font-size: 12px;
}
.file-viewer :deep(.cm-gutters) {
  font-size: 12px;
}
</style>
