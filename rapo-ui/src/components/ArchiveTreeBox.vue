<template>
  <div class="archive-tree">
    <div class="row items-center q-mb-sm">
      <div class="text-caption text-grey-7">
        The saved directories as this server sees them, read one folder at a time when it is opened (at most [DATASOURCES] list_max_files entries each).
      </div>
      <q-space />
      <q-btn flat dense round size="sm" icon="fas fa-sync" color="grey-7" @click="reset">
        <q-tooltip anchor="top right" self="bottom right" :offset="[0, 5]">Read the open folders again</q-tooltip>
      </q-btn>
    </div>

    <div class="tree-header row no-wrap">
      <div class="col">Name</div>
      <div class="cell-size text-right">Size</div>
      <div class="cell-modified">Modified</div>
      <div class="cell-owner">Owner</div>
      <div class="cell-mode">Mode</div>
    </div>
    <!-- One flat list of the rows shown, so that a folder of thousands of files scrolls without rendering them all. -->
    <q-virtual-scroll class="tree-body" :items="rows" :virtual-scroll-item-size="ROW_HEIGHT">
      <template #default="{ item }">
        <div :key="item.key" class="tree-row row no-wrap items-center" :class="{ 'cursor-pointer': item.expandable }" @click="item.expandable && toggle(item)">
          <div class="col row no-wrap items-center ellipsis" :style="{ paddingLeft: item.depth * 20 + 'px' }">
            <q-icon
              v-if="item.expandable"
              :name="expanded[item.key] ? 'fas fa-chevron-down' : 'fas fa-chevron-right'"
              size="10px"
              color="grey-7"
              class="chevron"
            />
            <span v-else class="chevron" />
            <q-spinner v-if="item.kind === 'loading'" size="14px" color="grey-6" class="q-mr-sm" />
            <q-icon v-else-if="item.icon" :name="item.icon" :color="item.color" size="14px" class="q-mr-sm" />
            <span :class="item.class" class="ellipsis" :title="item.title">{{ item.label }}</span>
            <span v-if="item.detail" class="text-mono text-grey-8 q-ml-md ellipsis" :title="item.detail">{{ item.detail }}</span>
            <span v-if="item.summary" class="text-grey-6 q-ml-sm text-no-wrap">{{ item.summary }}</span>
          </div>
          <div class="cell-size text-right">
            {{ item.size != null ? formatBytes(item.size) : "" }}
          </div>
          <div class="cell-modified">{{ toDateTimeString(item.modified) }}</div>
          <div class="cell-owner ellipsis">
            {{ item.owner ? `${item.owner}:${item.group}` : "" }}
          </div>
          <div class="cell-mode text-mono">{{ item.mode || "" }}</div>
        </div>
      </template>
    </q-virtual-scroll>
  </div>
</template>

<script>
import { api } from "../api";
import { formatBytes } from "../utils/datasources";
import { formatNumber, toDateTimeString } from "../utils/format";

const ROW_HEIGHT = 30;

const ROOTS = [
  {
    field: "archive_directory",
    label: "ARCHIVE_DIRECTORY",
    icon: "fas fa-archive",
  },
  {
    field: "error_directory",
    label: "ERROR_DIRECTORY",
    icon: "fas fa-exclamation-circle",
  },
  {
    field: "duplicate_directory",
    label: "DUPLICATE_DIRECTORY",
    icon: "fas fa-clone",
  },
];

// The archive, error and duplicate directories of a saved datasource as a tree (list-ds-archive), each folder read
// when first opened. The rows shown are flattened into one virtual-scroll list: Quasar's tree renders every node.
export default {
  name: "ArchiveTreeBox",
  props: {
    // The saved datasource: its paths are the ones the server lists.
    datasource: { type: Object, required: true },
  },
  data() {
    return {
      ROW_HEIGHT,
      // Listings by node key (field:path): {loading, error, listing}.
      listings: {},
      expanded: {},
    };
  },
  computed: {
    rows() {
      const rows = [];
      for (const root of ROOTS) {
        const key = nodeKey(root.field, "");
        const listing = this.listingOf(key);
        rows.push({
          key,
          field: root.field,
          path: "",
          depth: 0,
          kind: "root",
          expandable: Boolean(this.datasource[root.field]),
          icon: root.icon,
          color: "blue-grey-6",
          label: root.label,
          detail: this.datasource[root.field] || "(not set)",
          class: "text-weight-medium",
          summary: this.expanded[key] ? summaryOf(listing) : null,
        });
        if (this.expanded[key]) {
          this.pushChildren(rows, root.field, "", 1);
        }
      }
      return rows;
    },
  },
  watch: {
    // Another datasource, or its paths saved anew.
    "datasource.id"() {
      this.reset();
    },
    "datasource.archive_directory"() {
      this.reset();
    },
    "datasource.error_directory"() {
      this.reset();
    },
    "datasource.duplicate_directory"() {
      this.reset();
    },
  },
  mounted() {
    this.toggle({
      key: nodeKey(ROOTS[0].field, ""),
      field: ROOTS[0].field,
      path: "",
    });
  },
  methods: {
    formatBytes,
    toDateTimeString,
    listingOf(key) {
      const node = this.listings[key];
      return node && node.listing;
    },
    pushChildren(rows, field, path, depth) {
      const key = nodeKey(field, path);
      const node = this.listings[key];
      if (!node || node.loading) {
        rows.push({
          key: `${key}#loading`,
          depth,
          kind: "loading",
          label: "Reading...",
          class: "text-grey-6",
        });
        return;
      }
      if (node.error) {
        rows.push({
          key: `${key}#error`,
          depth,
          kind: "note",
          icon: "fas fa-exclamation-circle",
          color: "red-6",
          label: node.error,
          class: "text-red-6",
        });
        return;
      }
      const listing = node.listing;
      if (!listing.exists || !listing.readable) {
        const label = !listing.exists ? "Does not exist on this server" : `Not readable: ${listing.error}`;
        rows.push({
          key: `${key}#missing`,
          depth,
          kind: "note",
          icon: "fas fa-exclamation-triangle",
          color: "orange-9",
          label,
          class: "text-orange-9",
        });
        return;
      }
      if (!listing.dirs.length && !listing.files.length) {
        rows.push({
          key: `${key}#empty`,
          depth,
          kind: "note",
          label: "Empty",
          class: "text-grey-6",
        });
      }
      for (const dir of listing.dirs) {
        const childKey = nodeKey(field, dir.path);
        rows.push({
          key: childKey,
          field,
          path: dir.path,
          depth,
          kind: "dir",
          expandable: true,
          icon: this.expanded[childKey] ? "fas fa-folder-open" : "fas fa-folder",
          color: "amber-8",
          label: dir.name,
          modified: dir.modified,
          summary: this.expanded[childKey] ? summaryOf(this.listingOf(childKey)) : null,
        });
        if (this.expanded[childKey]) {
          this.pushChildren(rows, field, dir.path, depth + 1);
        }
      }
      for (const file of listing.files) {
        rows.push({
          key: nodeKey(field, file.path),
          depth,
          kind: "file",
          icon: /\.(gz|zip)$/i.test(file.name) ? "fas fa-file-archive" : "far fa-file",
          color: "grey-6",
          label: file.name,
          title: `${listing.root}/${file.path}`,
          size: file.size,
          modified: file.modified,
          owner: file.owner,
          group: file.group,
          mode: file.mode,
        });
      }
      if (listing.truncated) {
        rows.push({
          key: `${key}#truncated`,
          depth,
          kind: "note",
          icon: "fas fa-cut",
          color: "orange-8",
          label: "Only part of the folder was read, see [DATASOURCES] list_max_files and list_budget_seconds",
          class: "text-orange-9",
        });
      }
    },
    toggle(item) {
      if (this.expanded[item.key]) {
        const expanded = { ...this.expanded };
        delete expanded[item.key];
        this.expanded = expanded;
        return;
      }
      this.expanded = { ...this.expanded, [item.key]: true };
      if (!this.listings[item.key]) {
        this.load(item.field, item.path);
      }
    },
    async load(field, path) {
      const key = nodeKey(field, path);
      const id = this.datasource.id;
      this.listings = { ...this.listings, [key]: { loading: true } };
      let node;
      try {
        node = {
          listing: await api("list-ds-archive", {
            params: { id, field, path: path || null },
            loadingBar: false,
          }),
        };
      } catch (error) {
        node = { error: error.message || String(error) };
      }
      // A reset or another datasource meanwhile drops the answer.
      if (this.datasource.id === id && this.listings[key] && this.listings[key].loading) {
        this.listings = { ...this.listings, [key]: node };
      }
    },
    // Every open folder is read again; the closed ones when next opened.
    reset() {
      this.listings = {};
      const open = Object.keys(this.expanded);
      if (!open.length) {
        open.push(nodeKey(ROOTS[0].field, ""));
        this.expanded = { [open[0]]: true };
      }
      open.forEach((key) => {
        const [field, ...rest] = key.split(":");
        this.load(field, rest.join(":"));
      });
    },
  },
};

function nodeKey(field, path) {
  return `${field}:${path}`;
}

// What a read folder holds, e.g. "12 folders, 3,402 files, 1.2 GB".
function summaryOf(listing) {
  if (!listing || !listing.exists || !listing.readable) {
    return null;
  }
  const parts = [];
  if (listing.dirs.length) {
    parts.push(`${formatNumber(listing.dirs.length)} folder(s)`);
  }
  if (listing.files.length) {
    const bytes = listing.files.reduce((sum, file) => sum + file.size, 0);
    parts.push(`${formatNumber(listing.files.length)} file(s), ${formatBytes(bytes)}`);
  }
  return parts.length ? `${parts.join(", ")}${listing.truncated ? " or more" : ""}` : null;
}
</script>

<style scoped>
.tree-header {
  background: #cfd8dc;
  font-size: 12px;
  font-weight: 500;
  padding: 4px 8px;
}
.tree-body {
  max-height: 60vh;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-top: none;
}
.tree-row {
  height: 30px;
  padding: 0 8px;
  font-size: 13px;
}
.tree-row.cursor-pointer:hover {
  background: #eceff1;
}
.chevron {
  width: 18px;
  flex: none;
}
.cell-size {
  width: 90px;
  flex: none;
  padding-right: 16px;
}
.cell-modified {
  width: 150px;
  flex: none;
}
.cell-owner {
  width: 150px;
  flex: none;
}
.cell-mode {
  width: 100px;
  flex: none;
}
.text-mono {
  font-family: monospace;
}
</style>
