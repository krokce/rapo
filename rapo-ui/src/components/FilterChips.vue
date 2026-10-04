<template>
  <div v-if="filters.length || sort" class="row items-center q-gutter-xs filter-chips">
    <!-- The badge that removes them all, in the list's strong orange, then each filter in pale orange with a thin border. -->
    <q-chip v-if="filters.length" removable size="13px" color="orange-10" text-color="white" icon="fas fa-filter" class="filter-badge" @remove="clear">
      Filter<span v-if="shown" class="filter-badge__shown">{{ shown }}</span>
      <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">Remove all filters</q-tooltip>
    </q-chip>
    <q-chip v-for="filter in filters" :key="filter.key" removable size="13px" color="orange-1" text-color="orange-10" class="filter-chip" :title="filter.label" @remove="filter.clear()">
      <span class="ellipsis">{{ filter.label }}</span>
    </q-chip>
    <!-- A sort hides no rows, so it is neutral and the Filter badge leaves it alone. -->
    <q-chip v-if="sort" removable size="13px" color="blue-grey-1" text-color="blue-grey-9" :icon="sort.icon" class="sort-chip" :title="sort.title" @remove="sort.clear()">
      {{ sort.label }}
    </q-chip>
  </div>
</template>

<script>
// The active filters of a list in small print: a Filter badge whose ✕ removes them all (`clear`), with an optional
// `shown` count ("12 of 40"), then one removable chip per filter. `filters` is [{key, label, clear}], one entry per
// value (a multi-select gives one per selected value). `sort` (utils/sort.js `sortChip`, optional) adds a last chip
// naming a column sort; its ✕ restores the list's default order.
export default {
  name: "FilterChips",
  props: {
    filters: { type: Array, required: true },
    shown: { type: String, default: null },
    sort: { type: Object, default: null },
  },
  emits: ["clear"],
  methods: {
    clear() {
      this.$emit("clear");
    },
  },
};
</script>

<style scoped>
.filter-chips .q-chip {
  max-width: 360px;
}
.filter-badge {
  font-weight: 500;
}
.filter-badge__shown {
  font-weight: 400;
  margin-left: 6px;
}
.sort-chip {
  border: 1px solid var(--rapo-border-soft);
  font-weight: 500;
}
.filter-chip {
  border: 1px solid var(--rapo-filter-border);
  font-weight: 500;
}
</style>
