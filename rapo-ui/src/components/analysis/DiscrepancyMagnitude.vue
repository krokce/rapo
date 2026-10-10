<template>
  <div>
    <div v-for="field in magnitude.fields" :key="field.field" class="field-row row items-center q-col-gutter-lg">
      <div class="col-12 col-md-5">
        <div class="row items-center no-wrap">
          <q-avatar icon="fas fa-not-equal" color="orange-8" text-color="white" size="22px" font-size="11px" class="q-mr-sm" />
          <span class="text-weight-bold text-blue-grey-10">{{ field.field }}</span>
          <span class="text-grey-7 q-ml-sm">differs in {{ formatNumber(field.records) }} ({{ formatPct(field.share * 100) }})</span>
        </div>
        <div v-if="field.numeric" class="text-caption text-grey-8 q-mt-xs facts">
          <span title="The smallest and the largest difference">{{ formatStat(field.min) }} … {{ formatStat(field.max) }}</span>
          <span title="Half of the differences are smaller">median {{ formatStat(field.median) }}</span>
          <span v-if="field.sum !== null && field.sum !== undefined" title="The differences added up">sum {{ formatStat(field.sum) }}</span>
        </div>
        <div v-else class="text-caption text-grey-7 q-mt-xs">{{ formatNumber(field.distinct) }} different values</div>
      </div>
      <div class="col-12 col-md-7">
        <mini-histogram
          v-if="field.numeric && field.histogram && field.histogram.length > 1"
          :bars="bars(field)"
          :start="formatStat(field.min)"
          :end="formatStat(field.max)"
          :clickable="false"
          :height="44"
          color="var(--rapo-type-discrepancy)" />
        <mini-bars v-else :items="values(field)" :clickable="false" />
      </div>
    </div>
    <div v-if="magnitude.cut" class="text-caption text-grey-7 q-mt-sm">Only the 2,000 most frequent descriptions are read, so the sums are left out.</div>
  </div>
</template>

<script>
import MiniBars from "./MiniBars.vue";
import MiniHistogram from "./MiniHistogram.vue";
import { formatNumber } from "../../utils/format";
import { formatPct, formatStat } from "../../utils/analysis";

// How a reconciliation's value discrepancies differ, by field, as the engine wrote them in RAPO_DISCREPANCY_DESCRIPTION:
// the spread of the differences (or the percentage of a percentage rule), or their most common values.
export default {
  name: "DiscrepancyMagnitude",
  components: { MiniBars, MiniHistogram },
  props: {
    magnitude: { type: Object, required: true },
  },
  methods: {
    formatNumber,
    formatPct,
    formatStat,
    bars(field) {
      return field.histogram.map((item) => {
        const range = item.low === item.high ? formatStat(item.low) : `${formatStat(item.low)} – ${formatStat(item.high)}`;
        return { count: item.count, title: `${range}: ${formatNumber(item.count)} ${item.count === 1 ? "record" : "records"}` };
      });
    },
    values(field) {
      return field.values.slice(0, 6).map((item, index) => ({ key: `v${index}`, label: item.value, count: item.count, pct: item.share * 100 }));
    },
  },
};
</script>

<style scoped>
.field-row {
  padding: 4px 0 12px;
}

.field-row + .field-row {
  border-top: 1px solid var(--rapo-grid);
  padding-top: 12px;
}

.facts {
  display: flex;
  gap: 12px;
}
</style>
