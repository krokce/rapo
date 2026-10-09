<template>
  <div class="asn1-search">
    <div class="row no-wrap items-start q-gutter-x-xs">
      <template v-if="mode === 'field'">
        <q-input v-model="field" class="col search-field" dense outlined clearable label="Field" input-class="text-mono" hide-bottom-space @keyup.enter="start">
          <q-tooltip anchor="top middle" self="bottom middle" :delay="600" max-width="360px">
            A name or a tag, or a path of them ending at the node: servedIMSI, [3], listOfTrafficVolumes/dataVolumeGPRSUplink, [20]/[3]. Empty: any primitive node.
          </q-tooltip>
        </q-input>
        <q-input v-model="value" class="col search-value" dense outlined clearable :label="matchExact ? 'Value equals' : 'Value contains'" input-class="text-mono" hide-bottom-space @keyup.enter="start">
          <template #append>
            <q-btn aria-label="Whole value" flat dense no-caps class="search-toggle" :color="matchExact ? 'primary' : 'grey-8'" label="=" @click="matchExact = !matchExact">
              <q-tooltip>The whole value (else a part of it); any case, any reading or the hex</q-tooltip>
            </q-btn>
          </template>
        </q-input>
      </template>
      <q-input v-else v-model="hex" class="col" dense outlined clearable label="Hex bytes, e.g. 80 04 0A F9" input-class="text-mono" hide-bottom-space @keyup.enter="start" />
      <q-btn-toggle
        v-model="mode"
        dense
        no-caps
        unelevated
        toggle-color="blue-grey-7"
        color="grey-3"
        text-color="grey-8"
        class="search-mode"
        :options="[
          { value: 'field', label: 'Field', attrs: { title: 'Find nodes by field and value' } },
          { value: 'hex', label: 'Hex', attrs: { title: 'Find a sequence of bytes' } },
        ]" />
      <q-btn unelevated no-caps color="primary" icon="fas fa-search" class="search-go" :loading="loading" :disable="!canStart" aria-label="Find" @click="start">
        <q-tooltip>Find from the start of the file</q-tooltip>
      </q-btn>
    </div>
    <div v-if="searched" class="q-mt-xs">
      <div class="row items-center no-wrap text-caption text-grey-8 q-gutter-x-sm">
        <span class="ellipsis">{{ statusText }}</span>
        <q-space />
        <q-btn v-if="!eof" flat dense no-caps size="sm" color="primary" icon="fas fa-search-plus" label="Find more" :loading="loading" @click="more" />
        <q-btn flat dense round size="sm" icon="fas fa-times" aria-label="Close the results" @click="clear">
          <q-tooltip>Close the results</q-tooltip>
        </q-btn>
      </div>
      <q-virtual-scroll v-if="hits.length" class="search-hits" :items="hits" :virtual-scroll-item-size="22">
        <template #default="{ item, index }">
          <div :key="index" class="search-hit row no-wrap items-center" :class="{ 'search-hit--current': index === current }" @click="pick(item, index)">
            <span class="text-mono hit-offset text-grey-7">{{ formatNumber(item.match != null ? item.match : item.offset) }}</span>
            <span class="ellipsis hit-path" :title="item.path">{{ item.path }}</span>
            <span v-if="item.preview" class="text-mono ellipsis hit-preview q-ml-sm" :title="item.preview">{{ item.preview }}</span>
          </div>
        </template>
      </q-virtual-scroll>
    </div>
  </div>
</template>

<script>
import { api, notifyError } from "../../api";
import { formatBytes, formatNumber } from "../../utils/format";

// Finds ASN.1 nodes of the file on the server (search-ds-file-asn1): by field (names or tags) and value, or by bytes. A
// request reads on from where the last one stopped (`next_offset`), at most the search budgets; a hit opens the tree at
// its node.
export default {
  name: "Asn1Search",
  props: {
    fileId: { type: Number, required: true },
    decoding: { type: Object, required: true },
  },
  emits: ["reveal"],
  data() {
    return {
      mode: "field",
      field: "",
      value: "",
      hex: "",
      matchExact: false,
      loading: false,
      searched: false,
      hits: [],
      nextOffset: 0,
      eof: false,
      stopped: null,
      scanned: 0,
      current: -1,
    };
  },
  computed: {
    canStart() {
      return this.mode === "hex" ? Boolean(this.hex && this.hex.trim()) : Boolean((this.field && this.field.trim()) || (this.value && this.value.trim()));
    },
    statusText() {
      const count = `${formatNumber(this.hits.length)} hit${this.hits.length === 1 ? "" : "s"}`;
      if (this.eof) {
        return `${count} in the whole file`;
      }
      const paused = this.stopped === "time" ? " · the search paused, find more to go on" : "";
      return `${count} in the first ${formatBytes(this.scanned)}${paused}`;
    },
  },
  watch: {
    fileId() {
      this.clear();
    },
    decoding: {
      deep: true,
      handler() {
        this.clear();
      },
    },
  },
  methods: {
    formatNumber,
    clear() {
      this.request = (this.request || 0) + 1;
      this.searched = false;
      this.loading = false;
      this.hits = [];
      this.current = -1;
    },
    start() {
      if (!this.canStart) {
        return;
      }
      this.clear();
      this.searched = true;
      this.nextOffset = 0;
      this.scanned = 0;
      this.eof = false;
      this.fetch();
    },
    more() {
      if (!this.loading && !this.eof) {
        this.fetch();
      }
    },
    async fetch() {
      const request = this.request;
      this.loading = true;
      const params = {
        id: this.fileId,
        offset: this.nextOffset,
        start_offset: this.decoding.start_offset || 0,
        grammar: this.decoding.grammar || null,
        top: this.decoding.top || null,
      };
      if (this.mode === "hex") {
        params.hex = this.hex;
      } else {
        params.field = this.field || null;
        params.value = this.value || null;
        params.match = this.matchExact ? "equals" : "contains";
      }
      try {
        const result = await api("search-ds-file-asn1", { params, loadingBar: false });
        if (request !== this.request) {
          return;
        }
        this.hits = this.hits.concat(result.hits);
        this.nextOffset = result.next_offset;
        this.eof = result.eof;
        this.stopped = result.stopped;
        this.scanned += result.scanned_bytes;
      } catch (error) {
        if (request === this.request) {
          notifyError("The file was not searched.", error);
          this.searched = false;
        }
      } finally {
        if (request === this.request) {
          this.loading = false;
        }
      }
    },
    pick(hit, index) {
      this.current = index;
      if (hit.offset != null || hit.match != null) {
        this.$emit("reveal", hit);
      }
    },
  },
};
</script>

<style scoped>
.search-field {
  min-width: 140px;
}
.search-value {
  min-width: 140px;
}
.search-toggle {
  min-width: 28px;
  font-family: var(--rapo-font-mono);
  font-weight: 600;
}
.search-mode {
  height: 40px;
}
.search-go {
  height: 40px;
}
.search-hits {
  max-height: 160px;
  border: 1px solid var(--rapo-panel-border);
  border-radius: 4px;
}
.search-hit {
  height: 22px;
  font-size: 12px;
  padding: 0 6px;
  cursor: pointer;
}
.search-hit:hover {
  background: var(--rapo-row-hover);
}
.search-hit--current {
  background: var(--rapo-selected);
}
.hit-offset {
  flex: 0 0 90px;
}
.hit-path {
  flex: 1 1 auto;
}
.hit-preview {
  color: var(--rapo-muted);
  flex: 0 1 40%;
}
</style>
