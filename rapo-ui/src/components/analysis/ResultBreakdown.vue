<template>
  <div v-if="breakdown">
    <template v-if="types.length">
      <div class="type-bar row no-wrap q-mb-sm">
        <div
          v-for="item in types"
          :key="item.key"
          class="type-segment cursor-pointer"
          :style="{ width: item.pct + '%', background: item.bar }"
          :title="`${item.label}: ${formatNumber(item.count)} (${formatPct(item.pct)})`"
          @click="showType(item)" />
      </div>
      <div class="row items-center q-mb-sm">
        <q-chip v-for="item in types" :key="item.key" clickable class="q-ml-none q-mr-sm" @click="showType(item)">
          <q-avatar :icon="item.icon" :color="item.color" text-color="white" />
          <span class="text-weight-bold q-mr-xs">{{ item.label }}</span>({{ formatNumber(item.count) }})
          <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">{{ formatPct(item.pct) }} of the records: show them</q-tooltip>
        </q-chip>
      </div>
    </template>
    <div v-if="breakdown.fields.length" class="row items-center q-mb-sm">
      <span class="text-grey-7 q-mr-sm">Values differ in</span>
      <q-chip v-for="item in breakdown.fields" :key="item.field" clickable class="q-ml-none q-mr-sm" @click="showField(item)">
        <q-avatar icon="fas fa-not-equal" color="orange-8" text-color="white" />
        <span class="text-weight-bold q-mr-xs">{{ item.field }}</span>({{ formatNumber(item.count) }} of {{ formatNumber(breakdown.described) }})
        <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">The records whose RAPO_DISCREPANCY_DESCRIPTION names {{ item.field }}: show them</q-tooltip>
      </q-chip>
    </div>
    <div v-if="breakdown.values.length" class="values">
      <div class="text-caption text-grey-7 q-mb-xs">Case values (RAPO_RESULT_VALUE)</div>
      <mini-bars :items="caseValues" @select="(item) => $emit('show-rows', [item.filter])" />
    </div>
  </div>
</template>

<script>
import MiniBars from "./MiniBars.vue";
import { formatNumber } from "../../utils/format";
import { formatPct, resultType, valueFilter } from "../../utils/analysis";

const TYPE_COLUMN = "rapo_result_type";
const DESCRIPTION_COLUMN = "rapo_discrepancy_description";
const VALUE_COLUMN = "rapo_result_value";

// The result metadata of a result dataset: the split by result type, the fields its value discrepancies differ in
// (from the descriptions), and the case values when there are several. Each opens the records it counts.
export default {
  name: "ResultBreakdown",
  components: { MiniBars },
  props: {
    breakdown: { type: Object, default: null },
  },
  emits: ["show-rows"],
  computed: {
    types() {
      return this.breakdown.types.map((item, index) => ({
        ...resultType(item.value),
        key: `t${index}`,
        value: item.value,
        label: item.value === null ? "(none)" : item.value,
        count: item.count,
        pct: item.pct,
      }));
    },
    caseValues() {
      return this.breakdown.values.map((item, index) => ({
        key: `v${index}`,
        label: item.value === null ? "(missing)" : String(item.value),
        muted: item.value === null,
        count: item.count,
        pct: item.pct,
        filter: valueFilter(VALUE_COLUMN, item.value),
      }));
    },
  },
  methods: {
    formatNumber,
    formatPct,
    showType(item) {
      this.$emit("show-rows", [valueFilter(TYPE_COLUMN, item.value)]);
    },
    showField(item) {
      this.$emit("show-rows", [{ column: DESCRIPTION_COLUMN, op: "contains", value: `${item.field}|` }]);
    },
  },
};
</script>

<style scoped>
.type-bar {
  height: 14px;
  border-radius: 3px;
  overflow: hidden;
  gap: 2px;
}

.type-segment {
  min-width: 3px;
  height: 100%;
}

.type-segment:hover {
  opacity: 0.8;
}

.values {
  max-width: 640px;
}
</style>
