<template>
  <div v-if="!rows.length" class="text-grey-7">{{ emptyText }}</div>
  <table v-else class="diff-table">
    <tr v-for="row in rows" :key="row.path">
      <td class="diff-table__kind">
        <q-badge :color="KIND_COLORS[row.kind]">{{ row.kind }}</q-badge>
      </td>
      <td class="diff-table__path">{{ row.path }}</td>
      <td class="diff-table__value">
        <div v-if="row.lines" class="diff-table__lines">
          <div v-for="(line, index) in row.lines" :key="index" :class="lineClass(line)">
            <template v-if="line.type === 'gap'">&hellip;</template>
            <template v-else>{{ line.type }} {{ line.text }}</template>
          </div>
        </div>
        <template v-else-if="row.kind === 'changed'">
          <span class="diff-table__old">{{ display(row.old) }}</span>
          &rarr;
          <strong>{{ display(row.new) }}</strong>
        </template>
        <strong v-else-if="row.kind === 'added'">{{ display(row.new) }}</strong>
        <span v-else class="diff-table__old">{{ display(row.old) }}</span>
      </td>
      <td v-if="undoable" class="diff-table__undo">
        <span v-if="row.follows" class="diff-table__follows">follows {{ row.follows }}</span>
        <q-btn v-else flat round dense size="sm" icon="fas fa-undo" aria-label="Undo" @click="$emit('undo', row)">
          <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 5]">Revert to the saved value</q-tooltip>
        </q-btn>
      </td>
    </tr>
  </table>
</template>

<script>
const KIND_COLORS = { added: "positive", removed: "negative", changed: "orange-8" };

// The rows of utils/controlDiff.js: one per changed value, by path, with a line diff for multi-line texts. With
// undoable, each row ends with an Undo button (emits undo), or what it follows when it cannot be reverted alone.
export default {
  name: "DiffTable",
  props: {
    rows: { type: Array, required: true },
    emptyText: { type: String, default: "No differences." },
    undoable: { type: Boolean, default: false },
  },
  emits: ["undo"],
  data() {
    return { KIND_COLORS };
  },
  methods: {
    display(value) {
      if (value === null || value === undefined || value === "") {
        return "empty";
      }
      return typeof value === "object" ? JSON.stringify(value) : String(value);
    },
    lineClass(line) {
      return { "+": "diff-table__added", "-": "diff-table__removed", gap: "diff-table__gap" }[line.type] || "";
    },
  },
};
</script>

<style lang="sass" scoped>
// The monospace font of the Instance details tables, for the paths and the values alike. The path keeps to one line
// while it fits in 40% of the width; the value takes the rest.
.diff-table
  border-collapse: collapse
  width: 100%
  font-family: var(--rapo-font-mono)
  font-size: 12px

  td
    padding: 6px 12px 6px 0
    vertical-align: top
    border-bottom: 1px solid var(--rapo-panel-border)

.diff-table__kind
  width: 80px

.diff-table__path
  white-space: nowrap
  max-width: 40%

  @media (max-width: 900px)
    white-space: normal
    word-break: break-all

.diff-table__value
  width: 100%
  word-break: break-word

.diff-table__undo
  padding-right: 0
  text-align: right
  white-space: nowrap

.diff-table__follows
  color: var(--rapo-muted)

.diff-table__old
  color: var(--rapo-muted)
  text-decoration: line-through

.diff-table__lines
  white-space: pre-wrap
  border: 1px solid var(--rapo-panel-border)
  border-radius: 4px

  > div
    padding: 0 6px

.diff-table__added
  background: var(--rapo-added-bg)
  color: var(--rapo-added-fg)

.diff-table__removed
  background: var(--rapo-removed-bg)
  color: var(--rapo-removed-fg)

.diff-table__gap
  color: var(--rapo-muted)
  background: var(--rapo-surface-alt)
</style>
