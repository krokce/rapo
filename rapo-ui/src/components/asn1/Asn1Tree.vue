<template>
  <div class="asn1-tree column no-wrap" tabindex="0" @keydown="keydown">
    <q-virtual-scroll ref="scroll" class="col asn1-tree-body" :items="rows" :virtual-scroll-item-size="ROW_HEIGHT" @virtual-scroll="scrolledTo">
      <template #default="{ item, index }">
        <div :key="item.key" class="asn1-row row no-wrap items-center" :class="{ 'asn1-row--selected': item.node && item.node.offset === selectedOffset }" :data-index="index" @click="clickRow(item)">
          <div class="row no-wrap items-center ellipsis col" :style="{ paddingLeft: item.depth * 16 + 4 + 'px' }">
            <q-icon
              v-if="item.kind === 'node' && item.node.has_children"
              :name="expanded[item.node.offset] ? 'fas fa-chevron-down' : 'fas fa-chevron-right'"
              size="10px"
              color="grey-7"
              class="chevron"
              @click.stop="toggle(item.node)"
            />
            <span v-else class="chevron" />
            <template v-if="item.kind === 'node'">
              <q-icon :name="nodeIcon(item.node)" :color="item.node.undecodable ? 'orange-9' : item.node.constructed ? 'blue-grey-6' : 'grey-6'" size="13px" class="q-mr-xs" />
              <span v-if="item.name" class="asn1-name ellipsis" :title="item.title">{{ item.name }}</span>
              <span v-else-if="item.node.type" class="asn1-type ellipsis" :title="item.title">{{ item.node.type }}</span>
              <span class="asn1-tag text-mono" :class="{ 'text-orange-9': item.node.unknown, 'q-ml-xs': item.name || item.node.type }" :title="item.name || item.node.type ? null : item.title">{{ item.tag }}</span>
              <span v-if="item.preview" class="asn1-preview text-mono ellipsis q-ml-sm" :title="item.preview">{{ item.preview }}</span>
            </template>
            <template v-else-if="item.kind === 'loading'">
              <q-spinner size="12px" color="grey-6" class="q-mr-sm" />
              <span class="text-grey-7">Reading…</span>
            </template>
            <span v-else-if="item.kind === 'error'" class="text-red-7 ellipsis" :title="item.label">
              <q-icon name="fas fa-exclamation-circle" size="12px" class="q-mr-xs" />
              {{ item.label }}
            </span>
            <span v-else class="asn1-more text-primary cursor-pointer">
              <q-icon :name="item.kind === 'earlier' ? 'fas fa-angle-double-up' : 'fas fa-angle-double-down'" size="12px" class="q-mr-xs" />
              {{ item.label }}
            </span>
          </div>
        </div>
      </template>
    </q-virtual-scroll>
  </div>
</template>

<script>
import { api, notifyError } from "../../api";
import { formatNumber } from "../../utils/format";
import { decodingParams, fullTagSegment, nodeName, nodePreview, nodeTag, parentKey } from "../../utils/asn1";

const ROW_HEIGHT = 22;
// Children read at once, and before a node revealed out of the read ones.
const PAGE = 500;
const BEFORE = 50;

// The ASN.1 nodes of a file as a tree (get-ds-file-asn1): the root's TLVs, the children of a node read when it is first
// opened, a page at a time (more as the end of a level is scrolled to). The rows shown are flattened into one virtual-
// scroll list (Quasar's tree renders every node). Arrow keys move the selection and open or close a node.
export default {
  name: "Asn1Tree",
  props: {
    fileId: { type: Number, required: true },
    // {start_offset, record_header, filler, grammar, top}: a change reads the tree anew.
    decoding: { type: Object, required: true },
    selectedOffset: { type: Number, default: null },
  },
  emits: ["select", "meta"],
  data() {
    return {
      ROW_HEIGHT,
      // By parent key: {nodes, first (the ordinal of nodes[0]), eof, loading, error}.
      levels: {},
      expanded: {},
    };
  },
  computed: {
    rows() {
      const rows = [];
      this.pushLevel(rows, parentKey(null), null, 0);
      return rows;
    },
  },
  watch: {
    fileId() {
      this.reload();
    },
    decoding: {
      deep: true,
      handler() {
        this.reload();
      },
    },
  },
  mounted() {
    this.reload();
  },
  methods: {
    nodeIcon(node) {
      if (node.undecodable) {
        return "fas fa-exclamation-triangle";
      }
      return node.constructed ? "fas fa-folder" : "fas fa-file";
    },
    pushLevel(rows, key, parent, depth) {
      const level = this.levels[key];
      if (!level || (level.loading && !level.nodes.length)) {
        rows.push({ key: `${key}#loading`, kind: "loading", depth });
        return;
      }
      if (level.first > 0) {
        rows.push({ key: `${key}#earlier`, kind: "earlier", depth, parent, levelKey: key, label: `Show ${formatNumber(Math.min(PAGE, level.first))} earlier (from #${formatNumber(level.first + 1)})` });
      }
      for (const node of level.nodes) {
        const name = nodeName(node);
        rows.push({
          key: `n${node.offset}`,
          kind: "node",
          node,
          parent,
          levelKey: key,
          depth,
          name,
          tag: nodeTag(node),
          preview: nodePreview(node),
          title: this.nodeTitle(node, name),
        });
        if (this.expanded[node.offset] && node.has_children) {
          this.pushLevel(rows, parentKey(node.offset), node, depth + 1);
        }
      }
      if (level.error) {
        rows.push({ key: `${key}#error`, kind: "error", depth, label: level.error });
      } else if (level.loading) {
        rows.push({ key: `${key}#loading`, kind: "loading", depth });
      } else if (!level.eof) {
        rows.push({ key: `${key}#more`, kind: "more", depth, parent, levelKey: key, label: `Show more (from #${formatNumber(level.first + level.nodes.length + 1)})` });
      }
    },
    nodeTitle(node, name) {
      if (node.undecodable) {
        return `Bytes that are no TLV, from offset ${formatNumber(node.offset)} (${formatNumber(node.length)} bytes)`;
      }
      const parts = [`#${formatNumber(node.ordinal + 1)}`, name, node.type, node.tag, `offset ${formatNumber(node.offset)}`, `${formatNumber(node.length)} bytes`];
      if (node.unknown) {
        parts.push("not in the grammar");
      }
      return parts.filter(Boolean).join(" · ");
    },
    params(parent, ordinal, count) {
      return {
        id: this.fileId,
        parent: parent ? parent.offset : null,
        state: parent ? parent.state : null,
        ordinal,
        count,
        ...decodingParams(this.decoding),
      };
    },
    reload() {
      this.request = (this.request || 0) + 1;
      this.levels = {};
      this.expanded = {};
      this.load(null, 0, "replace");
    },
    // Reads a page of a level: replace (from `ordinal`), append (after the read ones) or prepend (before them).
    async load(parent, ordinal, mode, count = PAGE) {
      const key = parentKey(parent ? parent.offset : null);
      const request = this.request;
      const old = this.levels[key];
      this.levels[key] = { nodes: mode === "replace" || !old ? [] : old.nodes, first: mode === "replace" || !old ? ordinal : old.first, eof: old ? old.eof : false, loading: true, error: null };
      try {
        const result = await api("get-ds-file-asn1", { params: this.params(parent, ordinal, count), loadingBar: false });
        if (request !== this.request) {
          return null;
        }
        // The full tag (SEQ.1.4.0) of each node, from its parent's.
        for (const node of result.nodes) {
          const segment = fullTagSegment(node);
          node.fullTag = parent && parent.fullTag ? `${parent.fullTag}.${segment}` : segment;
        }
        const level = this.levels[key];
        if (mode === "append") {
          level.nodes = level.nodes.concat(result.nodes);
          level.eof = result.eof;
        } else if (mode === "prepend") {
          level.nodes = result.nodes.concat(level.nodes);
          level.first = ordinal;
        } else {
          level.nodes = result.nodes;
          level.first = ordinal;
          level.eof = result.eof;
        }
        level.loading = false;
        if (!parent) {
          this.$emit("meta", result);
        }
        return result;
      } catch (error) {
        if (request !== this.request) {
          return null;
        }
        this.levels[key].loading = false;
        this.levels[key].error = error.message;
        if (!parent) {
          this.$emit("meta", null, error);
        }
        return null;
      }
    },
    toggle(node) {
      if (!node.has_children) {
        return;
      }
      const open = !this.expanded[node.offset];
      this.expanded[node.offset] = open;
      if (open && !this.levels[parentKey(node.offset)]) {
        this.load(node, 0, "replace");
      }
    },
    clickRow(item) {
      if (item.kind === "node") {
        this.$emit("select", item.node);
      } else if (item.kind === "more") {
        this.loadMore(item);
      } else if (item.kind === "earlier") {
        this.loadEarlier(item);
      }
    },
    loadMore(item) {
      const level = this.levels[item.levelKey];
      if (level && !level.loading && !level.eof) {
        this.load(item.parent, level.first + level.nodes.length, "append");
      }
    },
    loadEarlier(item) {
      const level = this.levels[item.levelKey];
      if (level && !level.loading && level.first > 0) {
        const from = Math.max(level.first - PAGE, 0);
        this.load(item.parent, from, "prepend", level.first - from);
      }
    },
    // A "more" row scrolled into view reads the next page.
    scrolledTo({ to }) {
      for (let index = Math.max(to - 3, 0); index <= to && index < this.rows.length; index += 1) {
        if (this.rows[index].kind === "more") {
          this.loadMore(this.rows[index]);
        }
      }
    },
    // Opens the tree down to the deepest node holding a byte (locate-ds-file-asn1) and selects it.
    async reveal(offset) {
      let result;
      try {
        result = await api("locate-ds-file-asn1", { params: { id: this.fileId, offset, ...decodingParams(this.decoding) }, loadingBar: false });
      } catch (error) {
        notifyError("The node was not found.", error);
        return null;
      }
      const request = this.request;
      let parent = null;
      let last = null;
      for (const step of result.levels) {
        const key = parentKey(step.parent);
        let level = this.levels[key];
        const ordinal = step.node.ordinal;
        if (!level || level.loading || ordinal < level.first || ordinal >= level.first + level.nodes.length) {
          await this.load(parent, Math.max(ordinal - BEFORE, 0), "replace");
          if (request !== this.request) {
            return null;
          }
          level = this.levels[key];
        }
        last = level.nodes.find((node) => node.offset === step.node.offset) || step.node;
        if (step !== result.levels[result.levels.length - 1]) {
          this.expanded[last.offset] = true;
        }
        parent = last;
      }
      if (last) {
        this.$emit("select", last);
        this.$nextTick(() => this.scrollToNode(last.offset));
      }
      return last;
    },
    scrollToNode(offset) {
      const index = this.rows.findIndex((row) => row.node && row.node.offset === offset);
      if (index >= 0 && this.$refs.scroll) {
        this.$refs.scroll.scrollTo(index, "center-force");
      }
    },
    keydown(event) {
      const index = this.rows.findIndex((row) => row.node && row.node.offset === this.selectedOffset);
      const row = this.rows[index];
      let next = null;
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        const step = event.key === "ArrowDown" ? 1 : -1;
        for (let at = index + step; at >= 0 && at < this.rows.length; at += step) {
          if (this.rows[at].kind === "node") {
            next = this.rows[at];
            break;
          }
        }
      } else if (event.key === "ArrowRight" && row && row.node.has_children) {
        if (!this.expanded[row.node.offset]) {
          this.toggle(row.node);
        }
      } else if (event.key === "ArrowLeft" && row) {
        if (this.expanded[row.node.offset]) {
          this.toggle(row.node);
        } else if (row.parent) {
          next = this.rows.find((item) => item.node && item.node.offset === row.parent.offset);
        }
      } else {
        return;
      }
      event.preventDefault();
      if (next) {
        this.$emit("select", next.node);
        this.$nextTick(() => {
          const at = this.rows.indexOf(next);
          if (at >= 0) {
            this.$refs.scroll.scrollTo(at);
          }
        });
      }
    },
  },
};
</script>

<style scoped>
.asn1-tree {
  height: 100%;
  outline: none;
}
.asn1-tree-body {
  min-height: 0;
}
.asn1-row {
  height: 22px;
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
}
.asn1-row:hover {
  background: var(--rapo-row-hover);
}
.asn1-row--selected,
.asn1-row--selected:hover {
  background: var(--rapo-selected);
}
.chevron {
  width: 14px;
  flex: 0 0 14px;
  text-align: center;
}
.asn1-name {
  font-weight: 500;
}
.asn1-type {
  color: var(--rapo-strong);
  font-style: italic;
}
.asn1-tag {
  color: var(--rapo-info);
  font-size: 12px;
}
.asn1-preview {
  color: var(--rapo-muted);
  font-size: 12px;
}
</style>
