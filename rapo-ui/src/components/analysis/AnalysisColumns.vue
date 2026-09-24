<template>
  <div v-if="!columns">
    <q-skeleton v-for="index in 3" :key="index" type="rect" height="230px" class="q-mb-md" />
  </div>
  <div v-else>
    <div class="row items-center q-gutter-sm q-mb-md">
      <q-input v-model="search" dense outlined clearable class="column-search" placeholder="Find a column">
        <template #prepend><q-icon name="fas fa-search" size="14px" /></template>
      </q-input>
      <q-btn-toggle
        v-model="kind"
        dense
        no-caps
        unelevated
        toggle-color="blue-grey-7"
        color="grey-3"
        text-color="grey-8"
        :options="kindOptions" />
      <q-toggle v-model="alertsOnly" dense label="With warnings only" color="orange-8" />
      <q-space />
      <div class="text-grey-7">{{ shown.length }} of {{ columns.length }} columns</div>
    </div>
    <div v-for="column in shown" :id="`analysis-column-${column.name}`" :key="column.name" class="q-mb-md">
      <q-intersection once class="card-slot" :style="{ minHeight: '230px' }">
        <column-card :column="column" :db-type="dbTypes[column.name]" :focused="focusedName === column.name" @show-rows="$emit('show-rows', $event)" />
      </q-intersection>
    </div>
    <div v-if="!shown.length" class="text-grey-7 q-pa-md">No column matches.</div>
  </div>
</template>

<script>
import ColumnCard from "./ColumnCard.vue";
import { KIND_ICONS } from "../../utils/analysis";

// One card per column, rendered when it scrolls into view (q-intersection), so a wide dataset does not draw
// hundreds of charts at once.
export default {
  name: "AnalysisColumns",
  components: { ColumnCard },
  props: {
    columns: { type: Array, default: null },
    types: { type: Array, default: () => [] },
  },
  emits: ["show-rows"],
  data() {
    return { search: "", kind: null, alertsOnly: false, focusedName: null };
  },
  computed: {
    dbTypes() {
      const types = {};
      this.types.forEach((column) => (types[column.name] = column.db_type));
      return types;
    },
    kindOptions() {
      const present = new Set((this.columns || []).map((column) => (column.categorical ? "categorical" : column.kind)));
      return [{ label: "All", value: null }].concat(
        Object.entries(KIND_ICONS)
          .filter(([key]) => present.has(key))
          .map(([key, info]) => ({ label: info.label, value: key }))
      );
    },
    shown() {
      const search = (this.search || "").toLowerCase();
      return this.columns.filter(
        (column) =>
          (!search || column.name.includes(search)) &&
          (!this.kind || (column.categorical ? "categorical" : column.kind) === this.kind) &&
          (!this.alertsOnly || column.alerts.some((alert) => alert.level === "warning"))
      );
    },
  },
  methods: {
    // Scrolls to a column's card and marks it, e.g. from an alert of the overview.
    focus(name) {
      this.search = "";
      this.kind = null;
      this.alertsOnly = false;
      this.focusedName = name;
      this.$nextTick(() => {
        const element = document.getElementById(`analysis-column-${name}`);
        if (element) {
          element.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
      clearTimeout(this.focusTimer);
      this.focusTimer = setTimeout(() => (this.focusedName = null), 2500);
    },
  },
};
</script>

<style scoped>
.column-search {
  width: 240px;
}
</style>
