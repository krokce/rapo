<template>
  <q-dialog v-model="visible" @show="shown" @hide="close">
    <q-card class="column no-wrap file-viewer-card">
      <q-card-section class="row items-center no-wrap q-py-sm q-gutter-x-sm">
        <q-icon name="fas fa-file-alt" color="blue-grey-6" size="20px" />
        <div class="text-h6 ellipsis" :title="info && info.name">{{ (info && info.name) || (file && file.inputfilename) }}</div>
        <div v-if="info" class="text-caption text-grey-7 text-no-wrap">{{ facts }}</div>
        <q-space />
        <q-btn aria-label="Download the file" flat round dense icon="fas fa-download" :loading="downloading" @click="download">
          <q-tooltip>Download the file</q-tooltip>
        </q-btn>
        <q-btn aria-label="Close" flat round icon="fas fa-times" v-close-popup />
      </q-card-section>
      <q-separator />

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
        <q-select v-model="delimiterChoice" class="viewer-delimiter" dense outlined options-dense emit-value map-options :options="delimiterOptions" label="Columns" />
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
import { columnColors, DELIMITER_OPTIONS, delimiterLabel, detectDelimiter, matchMarks, refreshDecorations, searchExpression, splitFields } from "../utils/csvView";
import { downloadFiles } from "../utils/datasources";
import { formatBytes, formatNumber } from "../utils/format";

const BIG_STEP = 1000;
// Pixels from the bottom at which scrolling loads the next lines.
const NEAR_BOTTOM = 300;
const DEFAULT_MAX_LINES = 50000;

// Shows a file of the file log a few lines at a time (view-ds-file), or the lines matching a search of the whole file
// (grep-ds-file). The server keeps nothing: each request goes on from the `next_offset` (an uncompressed byte offset)
// and `next_line` of the previous one. The lines are a read-only CodeMirror whose line numbers are the file's; the
// rows behind them are kept outside Vue's reactivity, as are the editor and its view.
export default {
  name: "FileViewerDialog",
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
      delimiterChoice: "auto",
      detected: null,
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
    delimiter() {
      const choice = this.delimiterChoice;
      if (choice === "auto") {
        return this.detected;
      }
      return choice === "none" ? null : choice;
    },
    delimiterOptions() {
      return DELIMITER_OPTIONS.map((option) =>
        option.value === "auto" ? { ...option, label: `Auto (${this.detected ? delimiterLabel(this.detected) : "none"})` } : option,
      );
    },
    headerNames() {
      const header = this.info && this.info.header;
      if (!header || !this.delimiter) {
        return [];
      }
      return splitFields(header, this.delimiter).map(([start, end]) => header.slice(start, end).replace(/^"|"$/g, ""));
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
    delimiter() {
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
    // A file of the file log ({id, inputfilename}), shown from its first line.
    open(file) {
      this.file = file;
      this.info = null;
      this.search = "";
      this.matchCase = false;
      this.regex = false;
      this.searchError = null;
      this.delimiterChoice = "auto";
      this.detected = null;
      this.savedGrep = null;
      this.visible = true;
    },
    // After the opening transition: an editor measured while the dialog still scales opens scrolled.
    shown() {
      this.createEditor();
      this.showHead(0, 1);
    },
    close() {
      this.request += 1;
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
        delimiter: () => this.delimiter,
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
.viewer-delimiter {
  width: 170px;
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
