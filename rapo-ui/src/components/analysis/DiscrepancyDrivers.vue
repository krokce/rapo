<template>
  <div>
    <div class="text-caption text-grey-7 q-mb-sm">
      Every binning of every column, by how much it tells discrepancies from normal records (Theil's U, with φK). A bin is over-represented when it
      holds at least {{ minSupport }} discrepancies, twice their share among the normal records or more, and the difference is significant (z ≥ 4).
      Click an attribute for its bins.
    </div>
    <q-markup-table dense flat bordered class="ranking q-mb-md">
      <thead>
        <tr class="bg-blue-grey-2">
          <th title="The column of the discrepancies (its source column in the fetched records when named apart)" class="text-left">Column</th>
          <th title="How the column's values are grouped into bins" class="text-left">Bins</th>
          <th title="Share of the uncertainty about a record being a discrepancy that the bins remove (Theil's U)" class="text-left" style="width: 240px">
            Explained
          </th>
          <th title="phik correlation of the bins with being a discrepancy, 0 to 1" class="text-right">φK</th>
          <th title="Bins where discrepancies are at least twice as common as among the normal records" class="text-left">Over-represented</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="item in report.attributes"
          :key="item.id"
          class="cursor-pointer"
          :class="{ selected: selected && selected.id === item.id }"
          v-keyboard
          @click="$emit('select', item.id)">
          <td class="text-weight-medium">
            <q-icon :name="kindInfo(item).icon" :color="kindInfo(item).color" size="12px" class="q-mr-xs" :title="kindInfo(item).label" />
            {{ item.column }}<span v-if="item.source !== item.column" class="text-grey-7 text-weight-regular"> ← {{ item.source }}</span>
          </td>
          <td class="text-grey-8">{{ item.feature_label }}</td>
          <td>
            <div class="row items-center no-wrap">
              <div class="score-bar" :style="{ width: scoreWidth(item.score) + 'px', background: discColor }" />
              <span class="q-ml-sm text-weight-medium">{{ formatPct(item.score * 100) }}</span>
            </div>
          </td>
          <td class="text-right number-cell">{{ item.phik === null ? "–" : item.phik.toFixed(2) }}</td>
          <td class="ellipsis over-cell">
            <q-chip v-for="bin in topBins(item)" :key="bin.code" dense square size="sm" color="red-1" text-color="red-9" :title="bin.label">
              {{ bin.label }}
            </q-chip>
            <span v-if="item.special.length > 2" class="text-caption text-grey-7">+{{ item.special.length - 2 }}</span>
          </td>
        </tr>
      </tbody>
    </q-markup-table>

    <q-card v-if="selected" ref="detail" flat bordered>
      <q-card-section class="q-pb-none">
        <div class="text-subtitle1 text-blue-grey-9">
          {{ selected.column }} <span class="text-grey-7">· {{ selected.feature_label }}</span>
        </div>
        <div class="text-caption text-grey-7">
          Share of the discrepancies and of the normal records in each bin. Lift is the first share divided by the second: above 1 a bin is more
          common among the discrepancies. Rate is the share of the bin's records that are discrepancies.
        </div>
      </q-card-section>
      <q-card-section class="row q-col-gutter-lg">
        <div class="col-12 col-lg-6">
          <e-chart :option="detailOption" :height="Math.max(160, selected.bins.length * 22 + 50)" @select="selectBin" />
        </div>
        <div class="col-12 col-lg-6">
          <q-markup-table dense flat class="lift-table">
            <thead>
              <tr>
                <th title="The bin: a value, a range, a prefix, an hour…" class="text-left">Bin</th>
                <th title="Share of the discrepancies in this bin" class="text-right">Discrepancies</th>
                <th title="Share of the normal records (fetched less discrepancies) in this bin" class="text-right">Normal</th>
                <th title="How many times more common the bin is among the discrepancies" class="text-right">Lift</th>
                <th title="Share of the bin's records that are discrepancies" class="text-right">Rate</th>
                <th />
              </tr>
            </thead>
            <tbody>
              <tr v-for="bin in selected.bins" :key="String(bin.code)">
                <td class="ellipsis bin-label" :style="flagStyle(bin)" :title="bin.label" :class="{ 'text-italic text-grey-7': bin.code === null || !bin.filter }">{{ bin.label }}</td>
                <td class="text-right number-cell" :title="`${formatNumber(bin.disc)} discrepancies`">{{ formatPct(bin.disc_share * 100) }}</td>
                <td class="text-right number-cell" :title="`${formatNumber(bin.normal)} normal records`">{{ formatPct(bin.normal_share * 100) }}</td>
                <td class="text-right">
                  <q-chip
                    dense
                    square
                    size="sm"
                    :color="liftColor(bin.lift)"
                    :text-color="chipTextColor(liftColor(bin.lift))"
                    class="text-weight-bold"
                    :title="bin.z === null ? '' : `z = ${bin.z}`">
                    {{ liftText(bin.lift, bin.disc ? "Only" : "–") }}
                  </q-chip>
                </td>
                <td class="text-right number-cell">{{ bin.rate === null ? "–" : formatPct(bin.rate * 100) }}</td>
                <td class="text-right text-no-wrap">
                  <q-btn aria-label="Show these discrepancies" v-if="bin.filter && bin.filter.result && bin.disc" flat dense round size="xs" color="primary" icon="fas fa-table" @click="showBin(bin, false)">
                    <q-tooltip>Show these discrepancies</q-tooltip>
                  </q-btn>
                  <q-btn aria-label="Show these fetched records" v-if="bin.filter && bin.filter.fetched" flat dense round size="xs" color="blue-grey-6" icon="fas fa-database" @click="showBin(bin, true)">
                    <q-tooltip>Show these fetched records</q-tooltip>
                  </q-btn>
                </td>
              </tr>
            </tbody>
          </q-markup-table>
        </div>
      </q-card-section>
    </q-card>
  </div>
</template>

<script>
import EChart from "./EChart.vue";
import { escapeHtml, formatNumber } from "../../utils/format";
import { KIND_ICONS, baseOption, chipTextColor, formatPct, liftColor, liftText, valueAxis } from "../../utils/analysis";

const DISC_COLOR = "#e53935";
const NORMAL_COLOR = "#78909c";
const UNDER_COLOR = "#1e88e5";

// The attributes of a discrepancy analysis, ranked, and the bins of the chosen one: a butterfly of the discrepancies'
// and the normal records' shares, and their lifts. Each bin opens its discrepancies or fetched records in Data analysis.
export default {
  name: "DiscrepancyDrivers",
  components: { EChart },
  props: {
    report: { type: Object, required: true },
    selectedId: { type: String, default: null },
  },
  emits: ["select", "show-rows"],
  data() {
    return { discColor: DISC_COLOR };
  },
  computed: {
    selected() {
      const attributes = this.report.attributes;
      return attributes.find((item) => item.id === this.selectedId) || attributes[0] || null;
    },
    minSupport() {
      return Math.max(10, Math.ceil((this.report.meta.discrepancies || 0) * 0.01));
    },
    detailOption() {
      const bins = [...this.selected.bins].reverse();
      return baseOption({
        grid: { left: 8, right: 16, top: 26, bottom: 4 },
        legend: { top: 0, textStyle: { fontSize: 11 } },
        tooltip: {
          trigger: "axis",
          formatter: (points) => {
            const bin = bins[points[0].dataIndex];
            return (
              `<b>${escapeHtml(bin.label)}</b><br/>Discrepancies ${formatPct(bin.disc_share * 100)} (${formatNumber(bin.disc)})` +
              `<br/>Normal ${formatPct(bin.normal_share * 100)} (${formatNumber(bin.normal)})<br/>Lift ${liftText(bin.lift, bin.disc ? "only discrepancies" : "–")}`
            );
          },
        },
        xAxis: valueAxis({ axisLabel: { formatter: (value) => `${Math.abs(value)}%` } }),
        yAxis: { type: "category", data: bins.map((bin) => bin.label), axisLabel: { fontSize: 10, width: 160, overflow: "truncate" }, axisTick: { show: false } },
        series: [
          {
            name: "Normal records",
            type: "bar",
            stack: "share",
            data: bins.map((bin) => -round(bin.normal_share * 100)),
            itemStyle: { color: NORMAL_COLOR },
            cursor: "pointer",
          },
          {
            name: "Discrepancies",
            type: "bar",
            stack: "share",
            data: bins.map((bin) => ({ value: round(bin.disc_share * 100), itemStyle: { opacity: bin.flag === "over" ? 1 : 0.55 } })),
            itemStyle: { color: DISC_COLOR },
            cursor: "pointer",
          },
        ],
      });
    },
  },
  watch: {
    selectedId() {
      this.$nextTick(() => this.$refs.detail && this.$refs.detail.$el.scrollIntoView({ behavior: "smooth", block: "nearest" }));
    },
  },
  methods: {
    formatNumber,
    formatPct,
    chipTextColor,
    liftColor,
    liftText,
    kindInfo(item) {
      return KIND_ICONS[item.kind] || KIND_ICONS.text;
    },
    // A mark before an over- (red) or under-represented (blue) bin.
    flagStyle(bin) {
      const color = { over: DISC_COLOR, under: UNDER_COLOR }[bin.flag];
      return color ? { boxShadow: `inset 3px 0 0 ${color}` } : {};
    },
    scoreWidth(score) {
      return Math.max(3, Math.min(160, (score || 0) * 320));
    },
    topBins(item) {
      return item.bins
        .filter((bin) => bin.flag === "over")
        .sort((first, second) => second.disc_share - first.disc_share)
        .slice(0, 2);
    },
    showBin(bin, fetched) {
      this.$emit("show-rows", { filters: [bin.filter], fetched });
    },
    selectBin(event) {
      const bins = [...this.selected.bins].reverse();
      const bin = bins[event.dataIndex];
      if (bin && bin.filter && bin.filter.result && bin.disc) {
        this.showBin(bin, false);
      }
    },
  },
};

function round(value) {
  return Math.round(value * 100) / 100;
}
</script>

<style scoped>
.ranking tbody tr:hover {
  background: var(--rapo-teal-soft);
}

.ranking tbody tr.selected {
  background: var(--rapo-selected-row);
}

.score-bar {
  height: 10px;
  border-radius: 2px;
}

.over-cell {
  max-width: 420px;
}

.bin-label {
  max-width: 240px;
}
</style>
