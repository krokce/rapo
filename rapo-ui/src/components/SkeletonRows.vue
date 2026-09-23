<template>
  <tr v-for="row in rows" :key="row" class="skeleton-row">
    <td v-for="(column, index) in columns" :key="index">
      <q-skeleton v-if="column" :type="column" :width="column === 'text' ? '80%' : undefined" animation="fade" />
    </td>
  </tr>
</template>

<script>
// Placeholder rows for a table body whose data has not arrived yet: one cell per column, each with a QSkeleton of
// the given type ("text", "QChip", "QBtn", ...) or empty for null.
export default {
  props: {
    columns: { type: Array, required: true },
    rows: { type: Number, default: 12 },
  },
};
</script>
