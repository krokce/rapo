<template>
  <div class="files-loading">
    <mini-trend :buckets="data.buckets" :unit="data.unit" :series="recordSeries" :headline="compactNumber(loaded)" caption="records loaded" :legend="false" @pick="$emit('pick', $event)">
      <template #actions>
        <q-chip dense :color="rejected ? 'red-1' : null" :text-color="rejected ? 'red-9' : null" class="files-loading__rejected" :title="rejectedTitle">
          {{ compactNumber(rejected) }} rejected · {{ rejectedShare }}
        </q-chip>
      </template>
    </mini-trend>
    <mini-trend :buckets="data.buckets" :unit="data.unit" :series="rateSeries" :headline="rateHeadline" caption="records/min of load time" :legend="false" />
  </div>
</template>

<script>
import MiniTrend from "./MiniTrend.vue";
import { compactNumber, formatNumber } from "../../utils/format";

// The value of `source` for every datasource.
export const ALL_SOURCES = "all";

const sum = (values) => (values || []).reduce((total, value) => total + (value || 0), 0);

// How the files loaded, for every datasource or the one picked in the panel's head (`source`): the records loaded with
// the records rejected over the span as a chip, and the throughput (records written per minute of the SUCCESS files'
// load time), as two small trends side by side (one under the other when narrow).
export default {
  name: "FilesLoading",
  components: { MiniTrend },
  props: {
    // The files part of get-dashboard.
    data: { type: Object, required: true },
    // A sourceid of `data.throughput.sources`, or ALL_SOURCES.
    source: { type: [String, Number], default: ALL_SOURCES },
  },
  emits: ["pick"],
  computed: {
    picked() {
      return this.data.throughput.sources.find((item) => item.sourceid === this.source) || null;
    },
    write() {
      return this.picked ? this.picked.write : this.data.records.write;
    },
    loaded() {
      return sum(this.write);
    },
    rejected() {
      return sum(this.picked ? this.picked.reject : this.data.records.reject);
    },
    rejectedShare() {
      const read = sum(this.picked ? this.picked.read : this.data.records.read);
      return read ? `${formatNumber((this.rejected * 100) / read, 2)}%` : "0%";
    },
    rejectedTitle() {
      return `${formatNumber(this.rejected)} records rejected in this span, ${this.rejectedShare} of the records read`;
    },
    recordSeries() {
      return [{ key: "write", label: "Loaded", color: "teal-6", values: this.write, type: "area", format: compactNumber }];
    },
    rateSeries() {
      const values = this.picked ? this.picked.rates : this.data.throughput.all;
      return [{ key: "rate", label: this.picked ? this.picked.sourcename : "All datasources", color: "indigo-4", values, type: "line", format: (value) => `${formatNumber(value)} rec/min` }];
    },
    rateHeadline() {
      const values = this.rateSeries[0].values.filter((value) => value !== null && value !== undefined);
      return values.length ? compactNumber(values.reduce((total, value) => total + value, 0) / values.length) : "–";
    },
  },
  methods: {
    compactNumber,
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

.files-loading__rejected {
  margin: 0;
  font-size: 12px;
}
</style>
