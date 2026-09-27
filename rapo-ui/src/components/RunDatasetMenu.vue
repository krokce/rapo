<template>
  <q-menu ref="menu" :target="target" no-parent-event>
    <q-list v-if="run" dense class="text-no-wrap">
      <q-item-label header class="q-py-xs text-caption">{{ label }}</q-item-label>
      <q-item dense clickable v-close-popup @click="copyDatasetSql(run, dataset, label)">
        <q-item-section avatar class="menu-icon"><q-icon name="fas fa-copy" size="14px" color="blue-grey-7" /></q-item-section>
        <q-item-section> Copy SQL to clipboard </q-item-section>
      </q-item>
      <q-item dense clickable v-close-popup :to="{ name: 'data-analysis', params: { processId: run.process_id, dataset } }">
        <q-item-section avatar class="menu-icon"><q-icon name="fas fa-chart-bar" size="14px" color="primary" /></q-item-section>
        <q-item-section> Data analysis </q-item-section>
      </q-item>
    </q-list>
  </q-menu>
</template>

<script>
import { copyDatasetSql } from "../runActions";
import { datasetLabel } from "../utils/analysis";

// The menu of a run's number (fetched, discrepancies, error level): its dataset's SQL and its data analysis. One per
// table, opened with open(event, run, dataset) on a click or a right-click of the number.
export default {
  name: "RunDatasetMenu",
  data() {
    return { target: false, run: null, dataset: null };
  },
  computed: {
    // "Fetched A", "Discrepancies B", "Report rows", as the analysis page names the dataset.
    label() {
      if (!this.run) {
        return "";
      }
      const [kind, side] = this.dataset.split("_");
      return datasetLabel({ control_type: this.run.control_type, kind, side: side.toUpperCase() });
    },
  },
  methods: {
    copyDatasetSql,
    // `run` needs process_id and control_type.
    open(event, run, dataset) {
      this.target = event.currentTarget;
      this.run = run;
      this.dataset = dataset;
      this.$nextTick(() => this.$refs.menu.show());
    },
  },
};
</script>

<style scoped>
.menu-icon {
  min-width: 28px;
}
</style>
