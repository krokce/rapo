<template>
  <q-chip v-if="filters.length" removable color="orange-10" text-color="white" icon="fas fa-filter" class="filter-badge" @remove="clear">
    Filter<span v-if="shown" class="filter-badge__shown">{{ shown }}</span>
    <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">Remove all filters</q-tooltip>
  </q-chip>
</template>

<script>
// The hint that a list is filtered, beside its title: its ✕ removes every filter. `filters` is the page's
// activeFilters ([{key, label, clear}]), also listed by FilterChips; `shown` is an optional "12 of 40".
export default {
  name: "FilterBadge",
  props: {
    filters: { type: Array, required: true },
    shown: { type: String, default: null },
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
/* Beside an h2 title, whose light weight it would inherit. */
.filter-badge {
  font-size: 14px;
  font-weight: 500;
}

.filter-badge__shown {
  font-weight: 400;
  margin-left: 6px;
}
</style>
