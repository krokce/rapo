<template>
  <div class="donut row no-wrap items-center">
    <div class="donut__chart">
      <dashboard-chart :option="option" :height="height" @select="select" />
      <div class="donut__center column no-wrap items-center justify-center">
        <div class="donut__total dash-value">{{ centerValue }}</div>
        <div class="donut__label dash-note">{{ centerLabel }}</div>
      </div>
    </div>
    <div class="col donut__legend">
      <div
        v-for="item in rows"
        :key="item.key"
        class="donut__row dash-text row no-wrap items-center"
        :class="{ 'donut__row--link': pickable(item) }"
        :title="item.title || item.label"
        v-keyboard:button="pickable(item)"
        @click="pickable(item) && $emit('pick', { key: item.key })">
        <q-avatar v-if="item.icon" :icon="item.icon" size="18px" font-size="10px" text-color="white" :style="{ background: color(item.color) }" class="q-mr-sm" />
        <span v-else class="donut__swatch q-mr-sm" :style="{ background: color(item.color) }" />
        <span class="col ellipsis">{{ item.label }}</span>
        <span class="donut__value dash-text">{{ format(item.value) }}</span>
        <span class="donut__share dash-note">{{ share(item.value) }}</span>
      </div>
    </div>
  </div>
</template>

<script>
import DashboardChart from "./DashboardChart.vue";
import { compactNumber, escapeHtml, formatNumber } from "../../utils/format";
import { paletteColor } from "../../utils/palette";

// A share of a whole as a donut, its total in the middle, and the parts listed beside it with their share; a click on a
// slice or a row picks it.
export default {
  name: "DonutChart",
  components: { DashboardChart },
  props: {
    // [{key, label, color (Quasar name), value, icon?, title?, pick?}]; `pick: false` for a slice that opens nothing (Others).
    items: { type: Array, required: true },
    centerLabel: { type: String, default: "" },
    height: { type: Number, default: 150 },
    clickable: { type: Boolean, default: true },
    // The values in the list (the tooltip has them exact).
    format: { type: Function, default: formatNumber },
  },
  emits: ["pick"],
  computed: {
    rows() {
      return this.items.filter((item) => item.value);
    },
    total() {
      return this.rows.reduce((sum, item) => sum + item.value, 0);
    },
    centerValue() {
      return compactNumber(this.total);
    },
    option() {
      return {
        animation: false,
        tooltip: {
          trigger: "item",
          confine: true,
          formatter: (item) => `${escapeHtml(item.name)} <b>${formatNumber(item.value)}</b> (${this.share(item.value)})`,
        },
        series: [
          {
            type: "pie",
            radius: ["62%", "88%"],
            avoidLabelOverlap: false,
            label: { show: false },
            labelLine: { show: false },
            itemStyle: { borderWidth: 1, borderColor: "rgba(0, 0, 0, 0)" },
            data: this.rows.map((item) => ({ name: item.label, value: item.value, cursor: this.pickable(item) ? "pointer" : "default", itemStyle: { color: paletteColor(item.color) } })),
          },
        ],
      };
    },
  },
  methods: {
    formatNumber,
    color: paletteColor,
    share(value) {
      return this.total ? `${formatNumber((value * 100) / this.total, value * 100 < this.total ? 1 : 0)}%` : "";
    },
    pickable(item) {
      return this.clickable && item.pick !== false;
    },
    select(event) {
      const item = this.rows[event.dataIndex];
      if (item && this.pickable(item)) {
        this.$emit("pick", { key: item.key });
      }
    },
  },
};
</script>

<style scoped>
.donut__chart {
  position: relative;
  flex: 0 0 150px;
  width: 150px;
}

.donut__center {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.donut__legend {
  min-width: 0;
  margin-left: 12px;
}

.donut__row {
  padding: 2px 4px;
  border-radius: 3px;
}

.donut__row--link {
  cursor: pointer;
}

.donut__row--link:hover {
  background: var(--rapo-row-hover);
}

.donut__swatch {
  flex: none;
  width: 10px;
  height: 10px;
  border-radius: 2px;
}

.donut__value {
  margin-left: 8px;
  font-weight: 600;
  color: var(--rapo-header-text);
}

.donut__share {
  flex: 0 0 42px;
  text-align: right;
}
</style>
