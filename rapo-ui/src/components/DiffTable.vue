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
    </tr>
  </table>
</template>

<script>
const KIND_COLORS = { added: "positive", removed: "negative", changed: "orange-8" };

// The rows of utils/controlDiff.js: one per changed value, by path, with a line diff for multi-line texts.
export default {
  name: "DiffTable",
  props: {
    rows: { type: Array, required: true },
    emptyText: { type: String, default: "No differences." },
  },
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
  font-family: Monospace, sans-serif
  font-size: 12px

  td
    padding: 6px 12px 6px 0
    vertical-align: top
    border-bottom: 1px solid #eeeeee

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

.diff-table__old
  color: #9e9e9e
  text-decoration: line-through

.diff-table__lines
  white-space: pre-wrap
  border: 1px solid #e0e0e0
  border-radius: 4px

  > div
    padding: 0 6px

.diff-table__added
  background: #e8f5e9
  color: #1b5e20

.diff-table__removed
  background: #ffebee
  color: #b71c1c

.diff-table__gap
  color: #9e9e9e
  background: #fafafa
</style>
