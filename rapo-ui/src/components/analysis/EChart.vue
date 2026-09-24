<template>
  <v-chart class="echart" :option="option" :style="{ height: height + 'px' }" autoresize @click="$emit('select', $event)" />
</template>

<script>
// ECharts with only the charts the analysis page draws, registered once. It is imported by the analysis page
// alone, which is its own lazily loaded chunk, so the other pages never load ECharts.
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { BarChart, HeatmapChart, LineChart } from "echarts/charts";
import { DataZoomComponent, GridComponent, LegendComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import VChart from "vue-echarts";

use([CanvasRenderer, BarChart, HeatmapChart, LineChart, DataZoomComponent, GridComponent, LegendComponent, TooltipComponent, VisualMapComponent]);

export default {
  name: "EChart",
  components: { VChart },
  props: {
    option: { type: Object, required: true },
    height: { type: Number, default: 180 },
  },
  emits: ["select"],
};
</script>

<style scoped>
.echart {
  width: 100%;
}
</style>
