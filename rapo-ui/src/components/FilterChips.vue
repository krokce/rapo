<template>
  <div v-if="filters.length" class="row items-center q-gutter-xs filter-chips">
    <q-icon name="fas fa-filter" color="orange-10" size="13px" class="q-mr-xs" />
    <!-- Light companions of the orange Filter badge that removes them all: pale orange, dark orange text, a thin border. -->
    <q-chip v-for="filter in filters" :key="filter.key" removable size="13px" color="orange-1" text-color="orange-10" class="filter-chip" :title="filter.label" @remove="filter.clear()">
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
  max-width: 360px;
}
.filter-chip {
  border: 1px solid #ffcc80;
  font-weight: 500;
}
</style>
