<template>
  <div ref="scroller" class="hex-scroller" @scroll.passive="scrolled">
    <div class="hex-layer text-mono" :style="{ height: viewHeight + 'px' }" @click="clicked">
      <div class="hex-row hex-head">
        <span class="hex-addr" title="Offset of the row's first byte, in hex">Address</span>
        <span v-for="column in 16" :key="column" class="hex-byte" :title="`Byte ${(column - 1).toString(16).toUpperCase()} of the row`">{{ (column - 1).toString(16).toUpperCase() }}</span>
        <span class="hex-text" title="The bytes as ASCII text (a dot when not printable)">Text</span>
      </div>
      <div v-for="row in visibleRows" :key="row.index" class="hex-row">
        <span class="hex-addr">{{ row.address }}</span>
        <span v-for="cell in row.cells" :key="cell.offset" :data-offset="cell.offset" class="hex-byte" :class="cell.cls">{{ cell.hex }}</span>
        <span class="hex-text">
          <span v-for="cell in row.cells" :key="cell.offset" :data-offset="cell.offset" :class="cell.cls">{{ cell.char }}</span>
        </span>
      </div>
    </div>
    <div :style="{ height: spacerHeight + 'px' }" />
  </div>
</template>

<script>
import { api, notifyError } from "../../api";
import { byteChar, hexAddress, rangeKind } from "../../utils/asn1";

const ROW = 18;
const HEAD = 20;
const PAGE = 65536;
const PAGES_KEPT = 48;
// The browsers' limit of an element's height is about 33 million pixels: past this the scroll range is scaled.
const MAX_HEIGHT = 8000000;

// A hex dump of a whole file (get-ds-file-bytes, 64 KB pages fetched as rows come into view), 16 bytes per row, its
// rows drawn only where visible: a scroller holds a spacer as high as the rows (scaled down past MAX_HEIGHT) and a
// sticky layer with the rows of its scroll position. The selected node's tag, length and value bytes are colored; a
// click on a byte emits its offset.
export default {
  name: "HexPane",
  props: {
    fileId: { type: Number, required: true },
    // The uncompressed size when known.
    dataSize: { type: Number, default: null },
    // Byte ranges to color: [{kind: prefix|tag|len|value|hit, from, to}] (prefix: a record header).
    ranges: { type: Array, default: () => [] },
  },
  emits: ["byte"],
  data() {
    return {
      viewHeight: 400,
      scrollTop: 0,
      // Bumped when a page arrives (the pages themselves are not reactive).
      version: 0,
      // The end found by a short page, when the size was not known.
      knownEnd: null,
    };
  },
  computed: {
    size() {
      if (this.knownEnd !== null) {
        return this.knownEnd;
      }
      return this.dataSize;
    },
    rowCount() {
      if (this.size === null || this.size === undefined) {
        // Unknown: what is loaded, and a page more.
        return Math.ceil((this.loadedEnd() + PAGE) / 16);
      }
      return Math.max(Math.ceil(this.size / 16), 1);
    },
    visibleCount() {
      return Math.max(Math.floor((this.viewHeight - HEAD) / ROW), 1);
    },
    totalHeight() {
      return Math.min(this.rowCount * ROW + HEAD, MAX_HEIGHT);
    },
    scaled() {
      return this.rowCount * ROW + HEAD > MAX_HEIGHT;
    },
    spacerHeight() {
      return Math.max(this.totalHeight - this.viewHeight, 0);
    },
    firstRow() {
      const room = this.rowCount - this.visibleCount;
      if (room <= 0) {
        return 0;
      }
      if (!this.scaled) {
        return Math.min(Math.floor(this.scrollTop / ROW), room);
      }
      const range = this.totalHeight - this.viewHeight;
      return Math.min(Math.round((this.scrollTop / Math.max(range, 1)) * room), room);
    },
    visibleRows() {
      // eslint-disable-next-line no-unused-expressions
      this.version;
      const rows = [];
      const last = Math.min(this.firstRow + this.visibleCount + 1, this.rowCount);
      for (let index = this.firstRow; index < last; index += 1) {
        const start = index * 16;
        const cells = [];
        for (let column = 0; column < 16; column += 1) {
          const offset = start + column;
          if (this.size !== null && this.size !== undefined && offset >= this.size) {
            break;
          }
          const byte = this.byteAt(offset);
          const kind = byte === null ? null : rangeKind(this.ranges, offset);
          cells.push({
            offset,
            hex: byte === null ? "··" : byte.toString(16).toUpperCase().padStart(2, "0"),
            char: byte === null ? " " : byteChar(byte),
            cls: kind ? `hex-${kind}` : byte === null ? "hex-missing" : "",
          });
        }
        rows.push({ index, address: hexAddress(start), cells });
      }
      return rows;
    },
    // The bytes shown, as a key the pages to fetch follow.
    shownBytes() {
      const last = Math.min(this.firstRow + this.visibleCount + 1, this.rowCount);
      return `${this.firstRow * 16}:${last * 16}`;
    },
  },
  watch: {
    fileId() {
      this.reset();
      this.requestShown();
    },
    shownBytes() {
      this.requestShown();
    },
  },
  // Before the watchers, which read the shown rows when they are set up.
  beforeCreate() {
    this.pages = new Map();
    this.loading = new Set();
  },
  mounted() {
    this.observer = new ResizeObserver(() => this.measure());
    this.observer.observe(this.$refs.scroller);
    this.measure();
    this.requestShown();
  },
  beforeUnmount() {
    if (this.observer) {
      this.observer.disconnect();
    }
  },
  methods: {
    reset() {
      this.pages = new Map();
      this.loading = new Set();
      this.knownEnd = null;
      this.version += 1;
      if (this.$refs.scroller) {
        this.$refs.scroller.scrollTop = 0;
      }
    },
    measure() {
      const scroller = this.$refs.scroller;
      if (scroller) {
        this.viewHeight = scroller.clientHeight || 400;
      }
    },
    scrolled() {
      this.scrollTop = this.$refs.scroller.scrollTop;
    },
    loadedEnd() {
      let end = 0;
      for (const [index, data] of this.pages) {
        if (data) {
          end = Math.max(end, index * PAGE + data.length);
        }
      }
      return end;
    },
    byteAt(offset) {
      const data = this.pages.get(Math.floor(offset / PAGE));
      if (!data) {
        return null;
      }
      const at = offset % PAGE;
      return at < data.length ? data[at] : null;
    },
    requestShown() {
      const [from, to] = this.shownBytes.split(":").map(Number);
      this.request(from, to);
    },
    // Fetches the pages of a byte range that are not there yet.
    request(from, to) {
      const first = Math.floor(from / PAGE);
      const last = Math.floor(Math.max(to - 1, from) / PAGE);
      for (let index = first; index <= last; index += 1) {
        if (!this.pages.has(index) && !this.loading.has(index)) {
          this.fetchPage(index);
        }
      }
    },
    async fetchPage(index) {
      const fileId = this.fileId;
      this.loading.add(index);
      try {
        const response = await api("get-ds-file-bytes", { params: { id: fileId, offset: index * PAGE, size: PAGE }, raw: true, loadingBar: false });
        const data = new Uint8Array(await response.arrayBuffer());
        if (fileId !== this.fileId) {
          return;
        }
        this.pages.set(index, data);
        if (data.length < PAGE) {
          this.knownEnd = index * PAGE + data.length;
        }
        // The pages viewed last are kept.
        while (this.pages.size > PAGES_KEPT) {
          this.pages.delete(this.pages.keys().next().value);
        }
        this.version += 1;
      } catch (error) {
        notifyError("The bytes were not read.", error);
      } finally {
        this.loading.delete(index);
      }
    },
    clicked(event) {
      const offset = event.target && event.target.dataset ? event.target.dataset.offset : undefined;
      if (offset !== undefined) {
        this.$emit("byte", Number(offset));
      }
    },
    // Brings a byte into view (a third from the top), unless it is shown already.
    scrollToOffset(offset) {
      const scroller = this.$refs.scroller;
      if (!scroller) {
        return;
      }
      const row = Math.floor(offset / 16);
      if (row >= this.firstRow && row < this.firstRow + this.visibleCount - 1) {
        return;
      }
      const first = Math.max(row - Math.floor(this.visibleCount / 3), 0);
      const room = this.rowCount - this.visibleCount;
      if (room <= 0) {
        return;
      }
      const top = this.scaled ? (Math.min(first, room) / room) * (this.totalHeight - this.viewHeight) : first * ROW;
      scroller.scrollTop = top;
      this.scrollTop = scroller.scrollTop;
    },
  },
};
</script>

<style scoped>
.hex-scroller {
  height: 100%;
  overflow-y: auto;
  overflow-x: auto;
  position: relative;
  background: var(--rapo-surface);
}
.hex-layer {
  position: sticky;
  top: 0;
  font-size: 12px;
  line-height: 18px;
  overflow: hidden;
  white-space: nowrap;
  cursor: default;
}
.hex-row {
  display: flex;
  height: 18px;
  padding: 0 8px;
}
.hex-head {
  height: 20px;
  line-height: 20px;
  background: var(--rapo-header);
  color: var(--rapo-header-text);
  font-weight: 500;
}
.hex-addr {
  width: 84px;
  flex: 0 0 84px;
  color: var(--rapo-info);
}
.hex-head .hex-addr {
  color: inherit;
}
.hex-byte {
  width: 24px;
  flex: 0 0 24px;
  text-align: center;
  cursor: pointer;
}
.hex-text {
  margin-left: 16px;
  padding-left: 8px;
  border-left: 1px solid var(--rapo-panel-border);
  background: var(--rapo-highlight);
  white-space: pre;
}
.hex-head .hex-text {
  background: transparent;
}
.hex-text span {
  cursor: pointer;
}
.hex-missing {
  color: var(--rapo-muted);
}
.hex-prefix {
  background: var(--rapo-asn1-prefix);
}
.hex-tag {
  background: var(--rapo-asn1-tag);
}
.hex-len {
  background: var(--rapo-asn1-len);
}
.hex-value {
  background: var(--rapo-asn1-value);
}
.hex-hit {
  background: var(--rapo-asn1-hit);
  outline: 1px solid var(--rapo-warn);
}
</style>
