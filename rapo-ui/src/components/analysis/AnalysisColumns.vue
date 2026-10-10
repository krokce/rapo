<template>
  <div v-if="!columns" class="row q-col-gutter-md">
    <div v-for="index in 4" :key="index" class="col-12 col-md-6 col-xl-4"><q-skeleton type="rect" height="160px" /></div>
  </div>
  <div v-else>
    <q-input v-if="cards.length > SEARCH_FROM" v-model="search" dense outlined clearable debounce="200" class="column-search q-mb-md" placeholder="Find a column">
      <template #prepend><q-icon name="fas fa-search" size="13px" /></template>
    </q-input>
    <div class="row q-col-gutter-md">
      <div v-for="column in shown" :key="column.name" class="col-12 col-md-6 col-xl-4">
        <column-card :column="column" :db-type="dbTypes[column.name]" @show-rows="$emit('show-rows', $event)" />
      </div>
    </div>
    <div v-if="search && !shown.length" class="state-notice"><q-icon name="fas fa-search" /><div>No column matches.</div></div>
    <div v-if="unusable.length" class="text-caption text-grey-7 q-mt-md">
      <q-icon name="fas fa-eye-slash" class="q-mr-xs" />Not profiled:
      <span v-for="(column, index) in unusable" :key="column.name">
        <span class="text-weight-medium text-blue-grey-8">{{ column.name.toUpperCase() }}</span> {{ unusableText(column) }}<span v-if="index < unusable.length - 1"> · </span>
      </span>
    </div>
  </div>
</template>

<script>
import ColumnCard from "./ColumnCard.vue";
import { GROUP_ORDER, formatValue } from "../../utils/analysis";

// The column cards of a sample, those that partition the records first (GROUP_ORDER, the dataset's order within a
// group). The engine's RAPO_ columns are the Result types section's; constant, empty and unique columns are only named.
export default {
  name: "AnalysisColumns",
  components: { ColumnCard },
  props: {
    columns: { type: Array, default: null },
    types: { type: Array, default: () => [] },
  },
  emits: ["show-rows"],
  data() {
    return { search: "", SEARCH_FROM: 12 };
  },
  computed: {
    dbTypes() {
      const types = {};
      this.types.forEach((column) => (types[column.name] = column.db_type));
      return types;
    },
    profiled() {
      return this.columns.filter((column) => !column.metadata);
    },
    cards() {
      const rank = (column) => GROUP_ORDER.indexOf(column.group);
      return this.profiled
        .map((column, position) => ({ column, position }))
        .filter(({ column }) => !column.unusable)
        .sort((first, second) => rank(first.column) - rank(second.column) || first.position - second.position)
        .map(({ column }) => column);
    },
    shown() {
      const search = (this.search || "").toLowerCase();
      return search ? this.cards.filter((column) => column.name.includes(search)) : this.cards;
    },
    unusable() {
      return this.profiled.filter((column) => column.unusable);
    },
  },
  methods: {
    unusableText(column) {
      if (column.unusable === "constant") {
        const value = column.top.length ? column.top[0].value : null;
        return `constant ${value === "" ? "(blank)" : `"${formatValue(value, column.kind, Boolean(column.stats && column.stats.date_only))}"`}`;
      }
      if (column.unusable === "unique") {
        return column.distinct === column.count ? "unique" : "nearly unique";
      }
      return "empty";
    },
  },
};
</script>

<style scoped>
.column-search {
  width: 260px;
}
</style>
