<template>
  <div class="q-gutter-y-md">
    <div class="row items-center no-wrap q-gutter-x-sm">
      <div class="setting-label text-grey-8" title="The ASN.1 decoding the file viewer opens the datasource's files with">ASN.1</div>
      <q-skeleton v-if="!loaded" type="text" width="320px" />
      <template v-else-if="asn1">
        <q-chip :title="grammarKind === 'tagmap' ? 'Tag map of a Pentaho ASN.1 decoder' : 'ASN.1 modules'">
          <q-avatar :icon="grammarIcon(grammarKind)" color="blue-grey-6" text-color="white" />
          {{ asn1.grammar }}
        </q-chip>
        <div class="text-grey-8">{{ asn1Facts }}</div>
      </template>
      <div v-else class="text-grey-7">None saved: binary files open in the ASN.1 view without a grammar.</div>
    </div>
    <div class="row items-center no-wrap q-gutter-x-sm">
      <div class="setting-label text-grey-8" title="How the file viewer splits the lines of the datasource's text files into columns">Delimiter</div>
      <q-skeleton v-if="!loaded" type="text" width="240px" />
      <div v-else-if="layout.kind === 'widths'" class="text-grey-8">
        Fixed widths <span class="text-mono">{{ layout.widths.join(",") }}</span>
      </div>
      <div v-else-if="layout.kind === 'delimiter'" class="text-grey-8">
        <span v-if="layout.delimiter === '\t'">Tab</span>
        <span v-else class="text-mono delimiter">{{ layout.delimiter }}</span>
      </div>
      <div v-else class="text-grey-7">Detected from each file.</div>
    </div>
    <div class="text-caption text-grey-7">
      Both are saved in the file viewer (Save for datasource for the ASN.1 view, the save button of the Delimiter field) and apply to everyone opening the
      files of this datasource.
    </div>
    <q-separator />
    <div class="row q-gutter-sm">
      <q-btn outline color="primary" icon="fas fa-book" label="Grammars" class="icon-button" @click="$refs.grammars.open()">
        <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">Upload, edit and delete the grammars the file viewer decodes binary files with</q-tooltip>
      </q-btn>
    </div>
    <grammar-dialog ref="grammars" @changed="load" />
  </div>
</template>

<script>
import { api } from "../api";
import { FILLERS, grammarIcon } from "../utils/asn1";
import { parseLayout } from "../utils/csvView";
import { formatNumber } from "../utils/format";
import GrammarDialog from "./asn1/GrammarDialog.vue";

// The file viewer settings of a saved datasource (get-viewer-settings), read only: the ASN.1 decoding its files open
// with and the delimiter of its text files, both saved from the viewer. Read again when shown (the editor's tabs are
// kept alive, and the File log tab opens the viewer) and after a grammar changed (a rename moves its datasources).
export default {
  name: "ViewerSettingsBox",
  components: { GrammarDialog },
  props: {
    // The saved datasource.
    datasource: { type: Object, required: true },
  },
  data() {
    return {
      loaded: false,
      settings: {},
      grammars: [],
    };
  },
  computed: {
    asn1() {
      const asn1 = this.settings.asn1;
      return asn1 && asn1.grammar ? asn1 : null;
    },
    grammarKind() {
      const grammar = this.asn1 && this.grammars.find((item) => item.name === this.asn1.grammar);
      return grammar ? grammar.kind : null;
    },
    asn1Facts() {
      const asn1 = this.asn1;
      const parts = [];
      if (asn1.top) {
        parts.push(`type ${asn1.top}`);
      }
      parts.push(`start offset ${formatNumber(asn1.start_offset || 0)}`);
      if (asn1.record_header) {
        parts.push(`record header ${formatNumber(asn1.record_header)} bytes`);
      }
      const filler = FILLERS.find((item) => item.value === (asn1.filler || "00ff"));
      parts.push(`filler ${filler ? filler.label : asn1.filler}`);
      return parts.join(" · ");
    },
    layout() {
      return parseLayout(this.settings.layout);
    },
  },
  watch: {
    "datasource.id"() {
      this.load();
    },
  },
  mounted() {
    this.mountedOnce = true;
    this.load();
  },
  activated() {
    // Also called right after mounted, which loaded already.
    if (this.mountedOnce) {
      this.mountedOnce = false;
      return;
    }
    this.load();
  },
  methods: {
    grammarIcon,
    async load() {
      const sourceid = this.datasource.id;
      try {
        const [settings, grammars] = await Promise.all([
          api("get-viewer-settings", { params: { sourceid }, loadingBar: false }),
          api("get-asn1-grammars", { loadingBar: false }).catch(() => ({ grammars: [] })),
        ]);
        if (sourceid !== this.datasource.id) {
          return;
        }
        this.settings = settings.settings || {};
        this.grammars = grammars.grammars;
      } catch (error) {
        this.settings = {};
      } finally {
        this.loaded = true;
      }
    },
  },
};
</script>

<style scoped>
.setting-label {
  width: 80px;
  flex: none;
}
.delimiter {
  padding: 0 4px;
  border-radius: 3px;
  background: var(--rapo-grid);
  white-space: pre;
}
.icon-button :deep(.q-icon) {
  font-size: 1.2em;
}
</style>
