<template>
  <div v-if="breakdown && breakdown.columns.length" class="row q-col-gutter-md">
    <div v-for="column in breakdown.columns" :key="column.column" class="col-12 col-md">
      <q-card flat bordered class="full-height">
        <q-card-section class="q-py-sm">
          <div class="text-subtitle2 text-blue-grey-9">
            {{ column.label }}
            <span class="text-caption text-grey-6 q-ml-xs">{{ column.column.toUpperCase() }} · {{ formatNumber(column.distinct) }} distinct</span>
          </div>
        </q-card-section>
        <q-card-section class="q-pt-none">
          <div
            v-for="(item, index) in column.values"
            :key="index"
            class="row no-wrap items-center breakdown-row cursor-pointer"
            :title="`${item.value === null ? '(missing)' : item.value}: ${formatNumber(item.count)} (${formatPct(item.pct)})`"
            @click="$emit('show-rows', [valueFilter(column.column, item.value)])">
            <div class="breakdown-label ellipsis" :class="{ 'text-italic text-grey-6': item.value === null }">
              {{ item.value === null ? "(missing)" : item.value }}
            </div>
            <div class="col bar-cell">
              <div class="bar" :style="{ width: Math.max(item.pct, 0.5) + '%', background: barColor(column.column, item.value) }" />
            </div>
            <div class="breakdown-count text-right">{{ formatNumber(item.count) }}</div>
            <div class="breakdown-pct text-right text-grey-7">{{ formatPct(item.pct) }}</div>
          </div>
        </q-card-section>
      </q-card>
    </div>
  </div>
</template>

<script>
import { formatNumber } from "../../utils/format";
import { formatPct, valueFilter } from "../../utils/analysis";

// Result types of a reconciliation have fixed colors; everything else is blue-grey.
const TYPE_COLORS = { Loss: "#e53935", Discrepancy: "#fb8c00", Duplicate: "#8e24aa", Match: "#43a047" };

// The split of a result dataset by the metadata columns the engine writes: result type, case value and
// discrepancy description. Each bar opens the rows it counts.
export default {
  name: "ResultBreakdown",
  props: {
    breakdown: { type: Object, default: null },
  },
  emits: ["show-rows"],
  methods: {
    formatNumber,
    formatPct,
    valueFilter,
    barColor(column, value) {
      return (column === "rapo_result_type" && TYPE_COLORS[value]) || "#90a4ae";
    },
  },
};
</script>

<style scoped>
.breakdown-row {
  font-size: 13px;
  height: 24px;
  border-radius: 3px;
}

.breakdown-row:hover {
  background: #e0f2f1;
}

.breakdown-label {
  width: 45%;
  padding-right: 8px;
}

.bar-cell {
  height: 12px;
}

.bar {
  height: 100%;
  border-radius: 2px;
}

.breakdown-count {
  width: 64px;
}

.breakdown-pct {
  width: 56px;
}
</style>
