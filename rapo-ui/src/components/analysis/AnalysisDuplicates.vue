<template>
  <div v-if="!duplicates">
    <q-skeleton type="rect" height="60px" class="q-mb-md" />
    <q-skeleton type="rect" height="300px" />
  </div>
  <div v-else-if="!duplicates.duplicate_rows" class="column items-center q-pa-xl text-grey-7">
    <q-icon name="fas fa-check-circle" color="green-6" size="40px" class="q-mb-md" />
    The sample has no duplicate rows: no two rows are equal in every column.
  </div>
  <div v-else>
    <div class="row items-center q-mb-md">
      <div class="text-blue-grey-9">
        <strong>{{ formatNumber(duplicates.duplicate_rows) }}</strong> rows ({{ formatPct(duplicates.duplicate_pct) }}) repeat an earlier row of the sample
        in every column.
        <span v-if="duplicates.rows.length >= 50" class="text-grey-7">The 50 most frequent are listed.</span>
      </div>
      <q-space />
      <q-btn outline color="primary" icon="fas fa-table" label="Show all duplicate rows" no-caps @click="$emit('show-rows', [{ op: 'duplicated' }])" />
    </div>
    <div class="duplicates-scroll">
      <q-markup-table dense flat bordered class="duplicates-table">
        <thead>
          <tr class="bg-blue-grey-2">
            <th class="text-right">Count</th>
            <th v-for="name in duplicates.columns" :key="name" class="text-left">{{ name.toUpperCase() }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in duplicates.rows" :key="index" class="cursor-pointer" title="Show these rows" @click="showRow(row)">
            <td class="text-right text-weight-bold">{{ formatNumber(row.count) }}</td>
            <td v-for="(value, position) in row.values" :key="position" :class="{ 'text-grey-5': value === null }">
              {{ value === null ? "–" : formatValue(value, kinds[duplicates.columns[position]]) }}
            </td>
          </tr>
        </tbody>
      </q-markup-table>
    </div>
  </div>
</template>

<script>
import { formatNumber } from "../../utils/format";
import { formatPct, formatValue, valueFilter } from "../../utils/analysis";

export default {
  name: "AnalysisDuplicates",
  props: {
    duplicates: { type: Object, default: null },
    kinds: { type: Object, default: () => ({}) },
  },
  emits: ["show-rows"],
  methods: {
    formatNumber,
    formatPct,
    formatValue,
    // The rows equal to this one: one filter per column.
    showRow(row) {
      this.$emit(
        "show-rows",
        this.duplicates.columns.map((name, index) => valueFilter(name, row.values[index]))
      );
    },
  },
};
</script>

<style scoped>
.duplicates-scroll {
  overflow-x: auto;
}

.duplicates-table td {
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.duplicates-table tbody tr:hover {
  background: #e0f2f1;
}
</style>
