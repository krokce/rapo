<template>
  <div>
    <div class="text-caption text-grey-7 q-mb-sm">
      How the {{ formatNumber(magnitude.total) }} value discrepancies (result type Discrepancy: a counterpart found, with different values) differ, by
      field, as the engine wrote them in RAPO_DISCREPANCY_DESCRIPTION: the difference, or the percentage for a percentage rule.
      <span v-if="magnitude.cut">Only the most frequent 2,000 descriptions are read.</span>
    </div>
    <div class="row q-col-gutter-md">
      <div v-for="field in magnitude.fields" :key="field.field" class="col-12 col-lg-6">
        <q-card flat bordered class="full-height">
          <q-card-section class="row items-center no-wrap q-py-sm header">
            <div class="text-weight-bold text-blue-grey-10">{{ field.field }}</div>
            <div class="text-caption text-grey-7 q-ml-sm">
              differs in {{ formatNumber(field.records) }} ({{ formatPct(field.share * 100) }}) · {{ formatNumber(field.distinct) }} different values
            </div>
          </q-card-section>
          <q-separator />
          <q-card-section class="row q-col-gutter-md q-py-sm">
            <div class="col-12 col-md-5">
              <table class="stat-table">
                <tbody>
                  <tr v-if="field.numeric">
                    <td class="text-grey-7">Smallest</td>
                    <td class="text-right number-cell">{{ field.min }}</td>
                  </tr>
                  <tr v-if="field.numeric">
                    <td class="text-grey-7">Median</td>
                    <td class="text-right number-cell">{{ field.median }}</td>
                  </tr>
                  <tr v-if="field.numeric">
                    <td class="text-grey-7">Largest</td>
                    <td class="text-right number-cell">{{ field.max }}</td>
                  </tr>
                  <tr v-for="value in field.values.slice(0, field.numeric ? 5 : 8)" :key="value.value">
                    <td class="ellipsis value-cell number-cell" :title="value.value">{{ value.value }}</td>
                    <td class="text-right number-cell">{{ formatNumber(value.count) }} <span class="text-grey-7">{{ formatPct(value.share * 100) }}</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="field.numeric && field.histogram && field.histogram.length > 1" class="col-12 col-md-7">
              <e-chart :option="histogram(field)" :height="170" />
            </div>
          </q-card-section>
        </q-card>
      </div>
    </div>
  </div>
</template>

<script>
import EChart from "./EChart.vue";
import { formatNumber } from "../../utils/format";
import { baseOption, formatPct, formatStat, valueAxis } from "../../utils/analysis";

// The differences of a reconciliation's value discrepancies by field: their spread and most common values.
export default {
  name: "DiscrepancyMagnitude",
  components: { EChart },
  props: {
    magnitude: { type: Object, required: true },
  },
  methods: {
    formatNumber,
    formatPct,
    histogram(field) {
      const labels = field.histogram.map((item) => (item.low === item.high ? formatStat(item.low) : `${formatStat(item.low)} – ${formatStat(item.high)}`));
      return baseOption({
        grid: { left: 8, right: 8, top: 8, bottom: 4 },
        tooltip: { trigger: "axis", formatter: (items) => `${items[0].name}<br/><b>${formatNumber(items[0].value)}</b> records` },
        xAxis: { type: "category", data: labels, axisLabel: { fontSize: 10, hideOverlap: true } },
        yAxis: valueAxis(),
        series: [{ type: "bar", data: field.histogram.map((item) => item.count), itemStyle: { color: "#fb8c00" }, barCategoryGap: "8%" }],
      });
    },
  },
};
</script>

<style scoped>
.header {
  background: var(--rapo-surface-alt);
}

.stat-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.stat-table td {
  padding: 3px 4px;
  border-bottom: 1px solid var(--rapo-grid);
}

.value-cell {
  max-width: 160px;
}
</style>
