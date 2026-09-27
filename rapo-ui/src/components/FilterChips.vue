<template>
  <div v-if="filters.length" class="row items-center q-gutter-xs filter-chips">
    <q-icon name="fas fa-filter" color="orange-10" size="11px" class="q-mr-xs" />
    <q-chip v-for="filter in filters" :key="filter.key" dense removable size="sm" color="orange-10" text-color="white" :title="filter.label" @remove="filter.clear()">
      <span class="ellipsis">{{ filter.label }}</span>
    </q-chip>
  </div>
</template>

<script>
// The active filters of a list in small print, each removable on its own. `filters` is [{key, label, clear}],
// one entry per value (a multi-select gives one per selected value).
export default {
  name: "FilterChips",
  props: {
    filters: { type: Array, required: true },
  },
};
</script>

<style scoped>
.filter-chips .q-chip {
  max-width: 320px;
}
</style>
