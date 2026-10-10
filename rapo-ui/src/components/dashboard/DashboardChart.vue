<template>
  <v-chart class="dashboard-chart" :option="option" :theme="theme" :style="{ height: height + 'px' }" autoresize @click="$emit('select', $event)" />
</template>

<script>
// ECharts with the charts the Dashboard draws, registered once: bars, lines, donuts and heatmaps. In the Dashboard's
// chunk; ECharts itself is the shared "echarts" chunk (vue.config.js).
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { BarChart, HeatmapChart, LineChart, PieChart } from "echarts/charts";
import { GridComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import VChart from "vue-echarts";
import { Dark } from "quasar";
import { chartTheme } from "../../utils/analysis";

use([CanvasRenderer, BarChart, HeatmapChart, LineChart, PieChart, GridComponent, TooltipComponent, VisualMapComponent]);

export default {
  name: "DashboardChart",
  components: { VChart },
  props: {
    option: { type: Object, required: true },
    height: { type: Number, default: 200 },
  },
  emits: ["select"],
  computed: {
    theme() {
      return chartTheme(Dark.isActive);
    },
  },
};
</script>

<style scoped>
.dashboard-chart {
  width: 100%;
}
</style>
