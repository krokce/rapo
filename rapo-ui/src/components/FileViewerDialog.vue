<template>
  <q-dialog v-model="visible" @show="shown" @hide="close">
    <q-card class="column no-wrap file-viewer-card" :class="{ 'file-viewer-card--wide': layout !== 'file' }">
      <q-card-section class="row items-center no-wrap q-py-sm q-gutter-x-sm">
        <q-icon :name="layout === 'db' ? 'fas fa-database' : 'fas fa-file-alt'" color="blue-grey-6" size="20px" />
        <div class="text-h6 ellipsis" :title="file && file.inputfilename">{{ (info && info.name) || (file && file.inputfilename) }}</div>
        <div v-if="info && layout !== 'db'" class="text-caption text-grey-7 text-no-wrap">{{ facts }}</div>
        <q-space />
        <q-btn-toggle
          v-if="layoutOptions.length > 1"
          :model-value="layout"
          dense
          no-caps
          unelevated
          toggle-color="blue-grey-7"
          color="grey-3"
          text-color="grey-8"
          :options="layoutOptions"
          @update:model-value="setLayout" />
        <q-btn v-if="viewable" aria-label="Download the file" flat round dense icon="fas fa-download" :loading="downloading" @click="download">
          <q-tooltip>Download the file</q-tooltip>
        </q-btn>
        <q-btn aria-label="Close" flat round icon="fas fa-times" v-close-popup />
      </q-card-section>
      <q-separator />

      <!-- The file and the records it loaded, one above the other: the file pane stays in place (CodeMirror is never
           moved), the split only sizes the two. -->
      <div ref="panes" class="col column no-wrap viewer-panes">
        <div v-show="layout !== 'db'" class="column no-wrap file-pane" :style="filePaneStyle">
          <q-card-section class="row items-start q-gutter-sm q-py-sm">
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

          <div class="row items-center q-px-md q-pb-sm q-gutter-x-sm text-caption text-grey-8 viewer-status">
            <q-chip v-if="savedGrep" dense clickable color="orange-1" text-color="orange-10" icon="fas fa-arrow-left" class="q-ml-none" @click="backToResults">
              Back to results
              <q-tooltip>The search results, as they were</q-tooltip>
            </q-chip>
            <span>{{ statusText }}</span>
            <q-spinner v-if="loading" size="14px" color="primary" />
          </div>

          <div class="col relative-position viewer-body">
            <div v-if="!viewable" class="absolute-center text-grey-7 text-center">
              <q-icon name="fas fa-archive" size="32px" class="q-mb-sm" /><br />
              The archived file can not be shown.
            </div>
            <div ref="editor" class="file-viewer" />
            <div v-if="info && info.binary" class="absolute-center text-grey-7 text-center">
              <q-icon name="fas fa-file-excel" size="32px" class="q-mb-sm" /><br />
              A binary file: download it instead.
            </div>
          </div>

          <q-card-actions class="q-px-md">
            <span v-if="capped" class="text-orange-9 text-caption">
              The viewer keeps {{ formatNumber(maxLines) }} lines at most: search or download the file to see further.
            </span>
            <q-space />
            <template v-if="mode === 'head'">
              <q-btn outline no-caps color="primary" icon="fas fa-angle-double-down" :label="`Load ${formatNumber(BIG_STEP)} more`" :disable="!canLoadMore" :loading="loading" @click="loadMore(BIG_STEP)" />
            </template>
            <template v-else>
              <q-btn outline no-caps color="primary" icon="fas fa-search-plus" label="Find more" :disable="!canLoadMore" :loading="loading" @click="loadMore()" />
            </template>
          </q-card-actions>
        </div>
        <div v-if="layout === 'split'" class="split-handle" title="Drag to resize" @mousedown.prevent="startDrag" />
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
import { downloadFiles } from "../utils/datasources";
import { formatBytes, formatNumber } from "../utils/format";
import FileRecordsPane from "./FileRecordsPane.vue";

const BIG_STEP = 1000;
// Pixels from the bottom at which scrolling loads the next lines.
const NEAR_BOTTOM = 300;
const DEFAULT_MAX_LINES = 50000;
// The layout of the last viewer (whether split, and the file pane's share), and the delimiter of each datasource.
const SPLIT_KEY = "rapo_viewer_split";
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
  components: { FileRecordsPane },
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
      // file, db (the records) or split; the file pane's share of the height in split.
      layout: "file",
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
    };
  },
  computed: {
    ...mapGetters(["getEnvInfo"]),
    maxLines() {
      return (this.getEnvInfo && this.getEnvInfo.datasources_view_max_lines) || DEFAULT_MAX_LINES;
    },
    capped() {
      return this.count >= this.maxLines && !this.eof;
    },
    canLoadMore() {
      return Boolean(this.info && !this.info.binary && !this.eof && !this.capped && !this.loading);
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
    layoutOptions() {
      const options = [];
      if (this.viewable) {
        options.push({ value: "file", icon: "fas fa-file-alt", label: "File" });
      }
      if (this.viewable && this.hasTables) {
        options.push({ value: "split", icon: "fas fa-grip-lines", label: "Split" });
      }
      if (this.hasTables) {
        options.push({ value: "db", icon: "fas fa-database", label: "Database" });
      }
      return options.map((option) => ({ ...option, attrs: { title: option.value === "file" ? "The raw file" : option.value === "db" ? "The records loaded in the database" : "Show loaded records in Database below the file" } }));
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
    // A file of the file log ({id, inputfilename}), shown from its first line. `layout` file (or split, as last time)
    // or db; `viewable` whether the archived file can be read, `hasTables` whether the datasource has tables.
    open(file, { datasourceId = null, layout = "file", viewable = true, hasTables = false } = {}) {
      this.file = file;
      this.datasourceId = datasourceId;
      this.viewable = viewable;
      this.hasTables = hasTables;
      const split = readStorage(SPLIT_KEY) || {};
      this.ratio = Math.min(Math.max(Number(split.ratio) || 50, 15), 85);
      if (layout === "db" || !viewable) {
        this.layout = hasTables ? "db" : "file";
      } else {
        this.layout = split.split && hasTables ? "split" : "file";
      }
      this.recordsShown = this.layout !== "file";
      const saved = datasourceId !== null ? readStorage(LAYOUT_KEY + datasourceId) : null;
      this.layoutAuto = !saved || typeof saved.text !== "string";
      this.typedLayout = this.layoutAuto ? "" : saved.text;
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
      if (this.layout !== "db") {
        this.startFile();
      }
    },
    startFile() {
      if (this.view || !this.viewable) {
        return;
      }
      this.createEditor();
      this.showHead(0, 1);
    },
    setLayout(layout) {
      this.layout = layout;
      if (layout !== "file") {
        this.recordsShown = true;
      }
      if (layout !== "db") {
        writeStorage(SPLIT_KEY, { split: layout === "split", ratio: this.ratio });
        this.$nextTick(() => {
          this.startFile();
          if (this.view) {
            this.view.requestMeasure();
          }
        });
      }
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
        writeStorage(SPLIT_KEY, { split: true, ratio: Math.round(this.ratio) });
        if (this.view) {
          this.view.requestMeasure();
        }
      };
      move(event);
      window.addEventListener("mousemove", move);
      window.addEventListener("mouseup", stop);
    },
    // The Delimiter field as typed, remembered for the datasource.
    typeLayout(value) {
      this.layoutAuto = false;
      this.typedLayout = value || "";
      this.saveLayout();
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
      this.saveLayout();
    },
    saveLayout() {
      if (this.datasourceId !== null) {
        writeStorage(LAYOUT_KEY + this.datasourceId, this.layoutAuto ? null : { text: this.typedLayout });
      }
    },
    close() {
      this.request += 1;
      this.recordsShown = false;
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
  width: 1400px;
  max-width: 95vw;
  height: 90vh;
}
.file-viewer-card--wide {
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
.split-handle {
  flex: 0 0 8px;
  cursor: row-resize;
  border-top: 1px solid var(--rapo-panel-border);
  border-bottom: 1px solid var(--rapo-panel-border);
  background: var(--rapo-surface-alt);
}
.split-handle:hover {
  background: var(--rapo-teal-soft);
}
.viewer-delimiter {
  width: 220px;
}
.viewer-status {
  min-height: 28px;
}
.viewer-toggle {
  min-width: 30px;
  font-family: var(--rapo-font-mono);
  font-size: 13px;
  font-weight: 600;
}
.viewer-toggle--on {
  background: var(--rapo-selected);
}
.viewer-body {
  min-height: 0;
  padding: 0 16px;
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
