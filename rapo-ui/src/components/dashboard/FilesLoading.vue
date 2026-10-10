<template>
  <div class="files-loading">
    <mini-trend :buckets="data.buckets" :unit="data.unit" :series="recordSeries" :headline="compactNumber(loaded)" :caption="recordCaption" @pick="$emit('pick', $event)" />
    <mini-trend :buckets="data.buckets" :unit="data.unit" :series="rateSeries" :headline="rateHeadline" caption="records/min of load time" :legend="false">
      <template #actions>
        <q-select
          v-model="source"
          :options="options"
          emit-value
          map-options
          dense
          borderless
          options-dense
          use-input
          hide-selected
          fill-input
          input-debounce="0"
          class="loading-select"
          aria-label="Datasource of the throughput"
          @filter="filter" />
      </template>
    </mini-trend>
  </div>
</template>

<script>
import MiniTrend from "./MiniTrend.vue";
import { compactNumber, formatNumber } from "../../utils/format";

const ALL = "all";

// How the files loaded: the records written with the share rejected, and the throughput (records written per minute of
// the SUCCESS files' load time) of every datasource or one picked, as two small trends side by side (one under the other
// when narrow).
export default {
  name: "FilesLoading",
  components: { MiniTrend },
  props: {
    // The files part of get-dashboard.
    data: { type: Object, required: true },
  },
  emits: ["pick"],
  data() {
    return { source: ALL, search: "" };
  },
  computed: {
    loaded() {
      return this.data.records.write.reduce((sum, value) => sum + (value || 0), 0);
    },
    recordCaption() {
      const read = this.data.records.read.reduce((sum, value) => sum + (value || 0), 0);
      const rejected = this.data.records.reject.reduce((sum, value) => sum + (value || 0), 0);
      return `records loaded · ${read ? formatNumber((rejected * 100) / read, 2) : 0}% rejected`;
    },
    recordSeries() {
      return [
        { key: "write", label: "Loaded", color: "teal-6", values: this.data.records.write, type: "area" },
        { key: "rate", label: "Rejected %", color: "red-6", values: this.data.reject_rate, type: "line", axis: 1, format: (value) => `${formatNumber(value, 2)}%` },
      ];
    },
    sources() {
      return this.data.throughput.sources;
    },
    picked() {
      return this.sources.find((source) => source.sourceid === this.source) || null;
    },
    rateSeries() {
      const values = this.picked ? this.picked.rates : this.data.throughput.all;
      return [{ key: "rate", label: this.picked ? this.picked.sourcename : "All datasources", color: "indigo-4", values, type: "line", format: (value) => `${formatNumber(value)} rec/min` }];
    },
    rateHeadline() {
      const values = this.rateSeries[0].values.filter((value) => value !== null && value !== undefined);
      return values.length ? compactNumber(values.reduce((sum, value) => sum + value, 0) / values.length) : "–";
    },
    options() {
      const all = [{ label: "All datasources", value: ALL }, ...this.sources.map((source) => ({ label: source.sourcename || String(source.sourceid), value: source.sourceid }))];
      const text = this.search.toLowerCase();
      return text ? all.filter((option) => option.label.toLowerCase().includes(text)) : all;
    },
  },
  watch: {
    sources(sources) {
      if (this.source !== ALL && !sources.some((source) => source.sourceid === this.source)) {
        this.source = ALL;
      }
    },
  },
  methods: {
    compactNumber,
    filter(text, update) {
      update(() => (this.search = text));
    },
  },
};
</script>

<style scoped>
.files-loading {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 20px;
}

.files-loading > * {
  flex: 1 1 280px;
  min-width: 0;
}

.loading-select {
  width: 170px;
  font-size: 12px;
}

.loading-select :deep(.q-field__control),
.loading-select :deep(.q-field__native) {
  min-height: 22px;
  height: 22px;
  padding: 0;
}

.loading-select :deep(.q-field__marginal) {
  height: 22px;
}
</style>
