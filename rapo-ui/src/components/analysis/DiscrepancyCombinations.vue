<template>
  <div>
    <div class="text-caption text-grey-7 q-mb-sm">
      Pairs of bins of two attributes that together set the discrepancies apart more than either alone: over-represented, and with a discrepancy rate
      at least 1.5 times that of the better of the two bins. The strongest attributes are combined, each reduced to its main bins; ranked by how many
      discrepancies they explain beyond the base rate (weighted relative accuracy).
    </div>
    <q-markup-table v-if="report.combinations.length" dense flat bordered class="ranking">
      <thead>
        <tr class="bg-blue-grey-2">
          <th title="The first attribute and its bin" class="text-left">First</th>
          <th title="The second attribute and its bin" class="text-left">Second</th>
          <th title="Share of the discrepancies in both bins" class="text-right">Discrepancies</th>
          <th title="Share of the normal records in both bins" class="text-right">Normal</th>
          <th title="How many times more common both bins together are among the discrepancies" class="text-right">Lift</th>
          <th title="Lift of each bin alone" class="text-right">Alone</th>
          <th title="Share of the records in both bins that are discrepancies" class="text-right">Rate</th>
          <th />
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in report.combinations" :key="item.id">
          <td v-for="(part, index) in item.parts" :key="index" class="part-cell">
            <a class="attribute-link text-weight-medium" v-keyboard:button @click="$emit('show-attribute', part.attribute)">{{ part.what }}</a>
            <div class="ellipsis" :title="part.label">{{ part.label }}</div>
          </td>
          <td class="text-right number-cell" :title="`${formatNumber(item.disc)} discrepancies`">{{ formatPct(item.disc_share * 100) }}</td>
          <td class="text-right number-cell" :title="`${formatNumber(item.normal)} normal records`">{{ formatPct(item.normal_share * 100) }}</td>
          <td class="text-right">
            <q-chip dense square size="sm" :color="liftColor(item.lift)" :text-color="chipTextColor(liftColor(item.lift))" class="text-weight-bold" :title="`z = ${item.z}`">
              {{ liftText(item.lift, "Only") }}
            </q-chip>
          </td>
          <td class="text-right text-grey-7 text-no-wrap">{{ item.parts.map((part) => liftText(part.lift, "only")).join(" · ") }}</td>
          <td class="text-right number-cell">{{ formatPct(item.rate * 100) }}</td>
          <td class="text-right text-no-wrap">
            <q-btn aria-label="Show these discrepancies" v-if="item.filter" flat dense round size="xs" color="primary" icon="fas fa-table" @click="$emit('show-rows', { filters: [item.filter] })">
              <q-tooltip>Show these discrepancies</q-tooltip>
            </q-btn>
            <q-btn aria-label="Show these fetched records" v-if="item.filter" flat dense round size="xs" color="blue-grey-6" icon="fas fa-database" @click="$emit('show-rows', { filters: [item.filter], fetched: true })">
              <q-tooltip>Show these fetched records</q-tooltip>
            </q-btn>
          </td>
        </tr>
      </tbody>
    </q-markup-table>
    <div v-else class="state-notice">
      <q-icon name="fas fa-link" />
      <div>No pair of attributes sets the discrepancies apart more than its attributes alone.</div>
    </div>
  </div>
</template>

<script>
import { formatNumber } from "../../utils/format";
import { chipTextColor, formatPct, liftColor, liftText } from "../../utils/analysis";

// The combinations of a discrepancy analysis: pairs of bins of two attributes, stronger together than alone.
export default {
  name: "DiscrepancyCombinations",
  props: {
    report: { type: Object, required: true },
  },
  emits: ["show-attribute", "show-rows"],
  methods: {
    formatNumber,
    formatPct,
    chipTextColor,
    liftColor,
    liftText,
  },
};
</script>

<style scoped>
.part-cell {
  max-width: 300px;
}

.attribute-link {
  color: var(--rapo-teal);
  cursor: pointer;
}

.attribute-link:hover {
  text-decoration: underline;
}
</style>
