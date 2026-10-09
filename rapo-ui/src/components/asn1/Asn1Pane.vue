<template>
  <div class="column no-wrap asn1-pane">
    <div class="row items-start q-gutter-sm q-px-md q-py-sm toolbar">
      <q-select
        :model-value="grammar"
        :options="grammarNames"
        dense
        outlined
        options-dense
        clearable
        label="Grammar"
        class="grammar-select"
        :loading="grammarsLoading"
        @update:model-value="pickGrammar">
        <template #no-option>
          <q-item><q-item-section class="text-grey-7">No grammar uploaded: Grammars… to add one</q-item-section></q-item>
        </template>
        <q-tooltip anchor="top middle" self="bottom middle" :delay="600">The ASN.1 modules that name the fields; none shows the tags only</q-tooltip>
      </q-select>
      <q-select
        v-if="grammar && grammarKind !== 'tagmap'"
        :model-value="shownTop"
        :options="topOptions"
        dense
        outlined
        options-dense
        use-input
        input-debounce="0"
        label="Type"
        class="col type-select"
        :loading="typesLoading"
        @filter="filterTops"
        @update:model-value="pickTop">
        <template #option="scope">
          <q-item v-bind="scope.itemProps">
            <q-item-section>
              <q-item-label class="text-mono">{{ scope.opt }}</q-item-label>
            </q-item-section>
            <q-item-section v-if="preferred.has(scope.opt)" side>
              <q-badge color="blue-grey-5" label="top" />
            </q-item-section>
          </q-item>
        </template>
        <q-tooltip anchor="top middle" self="bottom middle" :delay="600" max-width="360px">
          The type of each TLV of the file (e.g. GPRSRecord, DataInterChange); guessed from the first one when not picked
        </q-tooltip>
      </q-select>
      <q-input
        :model-value="startOffsetText"
        dense
        outlined
        label="Start offset"
        class="offset-input"
        input-class="text-mono"
        :error="Boolean(offsetError)"
        hide-bottom-space
        debounce="600"
        @update:model-value="typeOffset">
        <q-tooltip anchor="top middle" self="bottom middle" :delay="600" max-width="320px">
          Bytes to skip before the first TLV, e.g. a file header that is no ASN.1 (decimal, or hex as 0x…)
        </q-tooltip>
      </q-input>
      <q-input
        :model-value="recordHeaderText"
        dense
        outlined
        label="Record header"
        class="offset-input"
        input-class="text-mono"
        :error="recordHeaderError"
        hide-bottom-space
        debounce="600"
        @update:model-value="typeRecordHeader">
        <q-tooltip anchor="top middle" self="bottom middle" :delay="600" max-width="320px">
          Bytes before each record to skip, e.g. 4 for Huawei SBC files (shown grey in the bytes, part of the record)
        </q-tooltip>
      </q-input>
      <q-select :model-value="filler" :options="FILLERS" emit-value map-options dense outlined options-dense label="Filler" class="filler-select" @update:model-value="pickFiller">
        <q-tooltip anchor="top middle" self="bottom middle" :delay="600" max-width="340px">
          Padding bytes skipped between records. FF only when a record header may start with 00 (Huawei SBC)
        </q-tooltip>
      </q-select>
      <q-btn outline no-caps color="primary" icon="fas fa-book" label="Grammars…" class="toolbar-btn" @click="$refs.grammars.open()" />
      <q-btn
        v-if="canSave && changed"
        unelevated
        no-caps
        color="primary"
        icon="fas fa-save"
        label="Save for datasource"
        class="toolbar-btn"
        :loading="saving"
        @click="saveSettings">
        <q-tooltip max-width="320px">Open the files of this datasource with this grammar, type and start offset (for everyone)</q-tooltip>
      </q-btn>
      <q-space />
      <div v-if="meta" class="text-caption text-grey-7 facts">{{ factsText }}</div>
    </div>

    <div ref="panes" class="col row no-wrap panes">
      <div class="column no-wrap tree-side" :style="{ flex: `0 0 ${ratio}%` }">
        <asn1-search class="q-px-sm q-pb-xs" :file-id="fileId" :decoding="decoding" @reveal="revealHit" />
        <div v-if="rootError" class="q-pa-md text-red-7">{{ rootError }}</div>
        <asn1-tree ref="tree" class="col" :file-id="fileId" :decoding="decoding" :selected-offset="selected ? selected.offset : null" @select="select" @meta="gotMeta" />
      </div>
      <div class="split-handle-v" title="Drag to resize" @mousedown.prevent="startDrag" />
      <div class="col column no-wrap data-side">
        <q-tab-panels v-model="tab" class="col tab-body" keep-alive>
          <q-tab-panel name="hex" class="q-pa-none">
            <hex-pane ref="hex" :file-id="fileId" :data-size="meta ? meta.data_size : null" :ranges="ranges" @byte="byteClicked" />
          </q-tab-panel>
          <q-tab-panel name="xml" class="q-pa-none relative-position">
            <asn1-code-view :text="rendered.xml" language="xml" />
            <q-inner-loading :showing="rendering" />
          </q-tab-panel>
          <q-tab-panel name="text" class="q-pa-none relative-position">
            <asn1-code-view :text="rendered.text" language="text" />
            <q-inner-loading :showing="rendering" />
          </q-tab-panel>
        </q-tab-panels>
        <div class="row items-center no-wrap tab-bar">
          <q-tabs v-model="tab" dense no-caps inline-label align="left" active-color="primary" indicator-color="primary" class="text-grey-8">
            <q-tab name="hex" label="Hex" />
            <q-tab name="xml" label="XML" />
            <q-tab name="text" label="Text" />
          </q-tabs>
          <q-space />
          <template v-if="tab !== 'hex'">
            <span v-if="renderNote" class="text-caption text-orange-9 q-mr-sm">{{ renderNote }}</span>
            <q-btn flat dense round size="sm" icon="fas fa-copy" aria-label="Copy" :disable="!currentRendered" @click="copyRendered">
              <q-tooltip>Copy</q-tooltip>
            </q-btn>
            <q-btn flat dense round size="sm" icon="fas fa-download" aria-label="Download" :disable="!currentRendered" class="q-mr-sm" @click="downloadRendered">
              <q-tooltip>Download</q-tooltip>
            </q-btn>
          </template>
        </div>
        <q-separator />
        <div class="details-box q-px-md q-py-sm scroll">
          <asn1-details :node="selected" :detail="detail" />
        </div>
      </div>
    </div>
    <grammar-dialog ref="grammars" @changed="grammarsChanged" />
  </div>
</template>

<script>
import { api, notifyError } from "../../api";
import { copyText, downloadBlob, formatBytes, formatNumber } from "../../utils/format";
import { decodingParams, FILLERS, nodeName, nodeRanges } from "../../utils/asn1";
import Asn1CodeView from "./Asn1CodeView.vue";
import Asn1Details from "./Asn1Details.vue";
import Asn1Search from "./Asn1Search.vue";
import Asn1Tree from "./Asn1Tree.vue";
import GrammarDialog from "./GrammarDialog.vue";
import HexPane from "./HexPane.vue";

const RATIO_KEY = "rapo_viewer_asn1_ratio";

function readRatio() {
  try {
    const value = Number(localStorage.getItem(RATIO_KEY));
    return value >= 15 && value <= 85 ? value : 40;
  } catch {
    return 40;
  }
}

function parseOffset(text) {
  const value = String(text || "").trim();
  if (!value) {
    return 0;
  }
  const number = /^0x[0-9a-f]+$/i.test(value) ? parseInt(value, 16) : /^\d+$/.test(value) ? Number(value) : NaN;
  return Number.isFinite(number) && number >= 0 ? number : null;
}

// A file of the file log as ASN.1: the tree of its nodes with a search on the left, its bytes (or the selected node as
// XML or text) and the selected node's details on the right. `decoding` ({grammar, top, start_offset, record_header,
// filler}) is what the
// server reads the file with; it starts from the datasource's saved settings, and Save for datasource stores it.
export default {
  name: "Asn1Pane",
  components: { Asn1CodeView, Asn1Details, Asn1Search, Asn1Tree, GrammarDialog, HexPane },
  props: {
    fileId: { type: Number, required: true },
    datasourceId: { type: Number, default: null },
    // The datasource's saved decoding ({grammar, top, start_offset, record_header, filler}) or null.
    saved: { type: Object, default: null },
  },
  emits: ["saved"],
  data() {
    const saved = this.saved || {};
    return {
      FILLERS,
      grammar: saved.grammar || null,
      grammarKind: null,
      top: saved.top || null,
      startOffsetText: saved.start_offset ? String(saved.start_offset) : "",
      recordHeaderText: saved.record_header ? String(saved.record_header) : "",
      filler: saved.filler || "00ff",
      decoding: { grammar: saved.grammar || null, top: saved.top || null, start_offset: saved.start_offset || 0, record_header: saved.record_header || 0, filler: saved.filler || "00ff" },
      grammarNames: [],
      grammarsLoading: false,
      tops: [],
      topOptions: [],
      preferred: new Set(),
      typesLoading: false,
      meta: null,
      rootError: null,
      selected: null,
      detail: null,
      tab: "hex",
      rendered: { xml: "", text: "" },
      renderedKey: { xml: null, text: null },
      renderNote: null,
      rendering: false,
      ratio: readRatio(),
      saving: false,
    };
  },
  computed: {
    canSave() {
      return this.datasourceId !== null;
    },
    offsetError() {
      return parseOffset(this.startOffsetText) === null;
    },
    recordHeaderError() {
      const value = parseOffset(this.recordHeaderText);
      return value === null || value > 1024;
    },
    // The type shown: the picked one, else the one the server guessed.
    shownTop() {
      return this.top || (this.meta && this.meta.grammar === this.grammar ? this.meta.top : null);
    },
    current() {
      return {
        grammar: this.grammar || null,
        top: this.grammar && this.grammarKind !== "tagmap" ? this.shownTop || null : null,
        start_offset: this.decoding.start_offset || 0,
        record_header: this.decoding.record_header || 0,
        filler: this.decoding.filler || "00ff",
      };
    },
    changed() {
      const saved = this.saved || {};
      const current = this.current;
      return (
        (saved.grammar || null) !== current.grammar ||
        (saved.top || null) !== current.top ||
        (saved.start_offset || 0) !== current.start_offset ||
        (saved.record_header || 0) !== current.record_header ||
        (saved.filler || "00ff") !== current.filler
      );
    },
    ranges() {
      return nodeRanges(this.selected);
    },
    factsText() {
      const meta = this.meta;
      const size = meta.data_size != null ? `${formatBytes(meta.data_size)} uncompressed` : "uncompressed size unknown";
      return `${size} · ${meta.compression === "plain" ? "plain" : meta.compression.startsWith("zip:") ? "ZIP" : "gzip"}`;
    },
    currentRendered() {
      return this.tab === "xml" ? this.rendered.xml : this.tab === "text" ? this.rendered.text : "";
    },
  },
  watch: {
    tab() {
      this.renderSelected();
    },
  },
  mounted() {
    this.loadGrammars();
    if (this.grammar) {
      this.loadTypes(this.grammar);
    }
  },
  methods: {
    async loadGrammars() {
      this.grammarsLoading = true;
      try {
        this.grammarNames = (await api("get-asn1-grammars", { loadingBar: false })).grammars.map((grammar) => grammar.name);
      } catch (error) {
        notifyError("The grammars were not read.", error);
      } finally {
        this.grammarsLoading = false;
      }
    },
    async loadTypes(name) {
      this.typesLoading = true;
      this.tops = [];
      try {
        const result = await api("get-asn1-grammar-types", { params: { name }, loadingBar: false });
        if (name !== this.grammar) {
          return;
        }
        this.grammarKind = result.kind || "asn1";
        this.tops = result.tops;
        this.preferred = new Set(result.tops.slice(0, result.preferred));
        this.topOptions = this.tops;
      } catch (error) {
        notifyError(`The types of the grammar ${name} were not read.`, error);
      } finally {
        this.typesLoading = false;
      }
    },
    filterTops(text, update) {
      update(() => {
        const needle = (text || "").toLowerCase();
        this.topOptions = needle ? this.tops.filter((name) => name.toLowerCase().includes(needle)) : this.tops;
      });
    },
    pickGrammar(name) {
      this.grammar = name || null;
      this.grammarKind = null;
      this.top = null;
      this.tops = [];
      if (this.grammar) {
        this.loadTypes(this.grammar);
      }
      this.apply();
    },
    pickTop(name) {
      this.top = name || null;
      this.apply();
    },
    typeOffset(text) {
      this.startOffsetText = text || "";
      if (parseOffset(this.startOffsetText) !== null) {
        this.apply();
      }
    },
    typeRecordHeader(text) {
      this.recordHeaderText = text || "";
      if (!this.recordHeaderError) {
        this.apply();
      }
    },
    pickFiller(value) {
      this.filler = value || "00ff";
      this.apply();
    },
    // The decoding the tree and search read with: a change reads the file anew.
    apply() {
      const next = {
        grammar: this.grammar,
        top: this.grammar ? this.top : null,
        start_offset: parseOffset(this.startOffsetText) || 0,
        record_header: this.recordHeaderError ? this.decoding.record_header : parseOffset(this.recordHeaderText) || 0,
        filler: this.filler,
      };
      if (JSON.stringify(next) === JSON.stringify(this.decoding)) {
        return;
      }
      this.decoding = next;
      this.selected = null;
      this.detail = null;
      this.meta = null;
      this.rendered = { xml: "", text: "" };
      this.renderedKey = { xml: null, text: null };
    },
    gotMeta(meta, error) {
      this.meta = meta;
      this.rootError = error ? error.message : null;
    },
    grammarsChanged(name) {
      this.loadGrammars();
      if (name && name === this.grammar) {
        // Its files were replaced: read the file with them.
        this.loadTypes(name);
        this.decoding = { ...this.decoding };
      }
    },
    async select(node) {
      this.selected = node;
      this.detail = null;
      if (this.$refs.hex) {
        this.$refs.hex.scrollToOffset(node.offset);
      }
      const request = (this.detailRequest = (this.detailRequest || 0) + 1);
      try {
        const result = await api("get-ds-file-asn1-node", { params: { id: this.fileId, offset: node.offset, state: node.state || null, ...this.decodingParams() }, loadingBar: false });
        if (request === this.detailRequest) {
          this.detail = result.node;
        }
      } catch (error) {
        if (!node.undecodable && request === this.detailRequest) {
          notifyError("The node was not read.", error);
        }
      }
      this.renderSelected();
    },
    decodingParams() {
      return decodingParams(this.decoding);
    },
    async renderSelected() {
      const format = this.tab;
      const node = this.selected;
      if (format === "hex" || !node || node.undecodable) {
        if (format !== "hex" && !node) {
          this.rendered[format] = "";
        }
        return;
      }
      const key = `${node.offset}|${JSON.stringify(this.decoding)}`;
      if (this.renderedKey[format] === key) {
        return;
      }
      this.rendering = true;
      this.renderNote = null;
      try {
        const result = await api("render-ds-file-asn1", { params: { id: this.fileId, offset: node.offset, state: node.state || null, format, ...this.decodingParams() }, loadingBar: false });
        if (this.selected !== node) {
          return;
        }
        this.rendered[format] = result.text;
        this.renderedKey[format] = key;
        this.renderNote = result.truncated ? `First ${formatNumber(result.nodes)} nodes shown` : null;
      } catch (error) {
        notifyError("The node was not shown.", error);
      } finally {
        this.rendering = false;
      }
    },
    byteClicked(offset) {
      if (this.$refs.tree) {
        this.$refs.tree.reveal(offset);
      }
    },
    revealHit(hit) {
      if (this.$refs.tree) {
        this.$refs.tree.reveal(hit.offset != null ? hit.offset : hit.match);
      }
    },
    async copyRendered() {
      try {
        await copyText(this.currentRendered);
        this.$q.notify({ type: "positive", message: "Copied" });
      } catch (error) {
        notifyError("Copying failed.", error);
      }
    },
    downloadRendered() {
      const name = (this.selected && nodeName(this.selected)) || `node_${this.selected ? this.selected.offset : 0}`;
      const xml = this.tab === "xml";
      downloadBlob(new Blob([this.currentRendered], { type: xml ? "application/xml" : "text/plain" }), `${name}.${xml ? "xml" : "txt"}`);
    },
    async saveSettings() {
      this.saving = true;
      try {
        const result = await api("save-viewer-settings", { method: "POST", body: { sourceid: this.datasourceId, asn1: this.current } });
        this.$q.notify({ type: "positive", message: "The datasource's files open with this decoding now." });
        this.$emit("saved", result.settings);
      } catch (error) {
        notifyError("The decoding was not saved.", error);
      } finally {
        this.saving = false;
      }
    },
    // Dragging the bar between the tree and the bytes: the tree's share, 15 to 85%.
    startDrag(event) {
      const box = this.$refs.panes.getBoundingClientRect();
      const move = (moved) => {
        this.ratio = Math.min(Math.max(((moved.clientX - box.left) / box.width) * 100, 15), 85);
      };
      const stop = () => {
        window.removeEventListener("mousemove", move);
        window.removeEventListener("mouseup", stop);
        try {
          localStorage.setItem(RATIO_KEY, String(Math.round(this.ratio)));
        } catch {
          // Storage off: not remembered.
        }
      };
      move(event);
      window.addEventListener("mousemove", move);
      window.addEventListener("mouseup", stop);
    },
  },
};
</script>

<style scoped>
.asn1-pane {
  height: 100%;
  min-height: 0;
}
.toolbar {
  flex-wrap: wrap;
}
.grammar-select {
  width: 260px;
}
.type-select {
  min-width: 260px;
  max-width: 420px;
}
.offset-input {
  width: 130px;
}
.filler-select {
  width: 130px;
}
.toolbar-btn {
  height: 40px;
}
.facts {
  padding-top: 12px;
}
.panes {
  min-height: 0;
  border-top: 1px solid var(--rapo-panel-border);
}
.tree-side {
  min-width: 0;
  min-height: 0;
  padding-top: 6px;
}
.data-side {
  min-width: 0;
  min-height: 0;
}
.split-handle-v {
  flex: 0 0 8px;
  cursor: col-resize;
  border-left: 1px solid var(--rapo-panel-border);
  border-right: 1px solid var(--rapo-panel-border);
  background: var(--rapo-surface-alt);
}
.split-handle-v:hover {
  background: var(--rapo-teal-soft);
}
.tab-body {
  min-height: 0;
}
.tab-body :deep(.q-tab-panel) {
  height: 100%;
}
.tab-bar {
  border-top: 1px solid var(--rapo-panel-border);
  background: var(--rapo-surface-alt);
}
.details-box {
  flex: 0 0 160px;
  min-height: 0;
}
</style>
