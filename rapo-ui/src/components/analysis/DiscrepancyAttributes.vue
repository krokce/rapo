<template>
  <div>
    <div class="attr-head row no-wrap items-center text-caption text-grey-7">
      <div class="attr-toggle" />
      <div class="attr-name" title="The column of the discrepancies, by the binning that tells the most">Column</div>
      <div class="col attr-score" title="The share of the uncertainty about a record being a discrepancy that the column's bins remove (Theil's U, 0 to 100%)">
        Explained
      </div>
      <div class="attr-over" title="Bins where discrepancies are at least twice as common as among the normal records, with their lift">Over-represented</div>
    </div>
    <template v-for="entry in shownColumns" :key="entry.column">
      <div
        :id="rowId(entry.column)"
        class="attr-row row no-wrap items-center cursor-pointer"
        :class="{ 'attr-row--open': entry.column === openColumn }"
        :aria-expanded="entry.column === openColumn"
        v-keyboard
        @click="toggle(entry)">
        <q-icon :name="entry.column === openColumn ? 'fas fa-chevron-down' : 'fas fa-chevron-right'" size="10px" class="attr-toggle text-grey-6" />
        <div class="attr-name ellipsis" :title="entry.best.source !== entry.column ? `${entry.column} ← ${entry.best.source}` : entry.column">
          <q-icon :name="kindInfo(entry.best).icon" :color="kindInfo(entry.best).color" size="12px" class="q-mr-xs" />
          <span class="text-weight-medium">{{ entry.column }}</span>
          <span v-if="binningShown(entry.best)" class="text-grey-7"> · {{ entry.best.feature_label.toLowerCase() }}</span>
        </div>
        <div class="col attr-score row no-wrap items-center">
          <div class="col score-track"><div class="score-bar" :style="{ width: scoreWidth(entry.best.score) }" /></div>
          <span class="score-text text-right">{{ formatPct(entry.best.score * 100) }}</span>
        </div>
        <div class="attr-over row no-wrap items-center">
          <q-chip v-for="bin in overBins(entry.best)" :key="String(bin.code)" dense square size="12px" color="red-1" text-color="red-9" class="over-chip" :title="bin.label">
            <span class="ellipsis">{{ bin.label }}</span><span class="text-weight-bold q-ml-xs">{{ liftText(bin.lift, "only") }}</span>
          </q-chip>
        </div>
      </div>
      <div v-if="entry.column === openColumn && openAttribute" class="attr-detail">
        <div v-if="entry.attributes.length > 1" class="row items-center q-mb-sm">
          <span class="text-caption text-grey-7 q-mr-sm">Binning</span>
          <q-chip
            v-for="attribute in entry.attributes"
            :key="attribute.id"
            clickable
            size="12px"
            class="q-ml-none"
            :class="{ 'chip-selected': attribute.id === openAttribute.id }"
            @click="$emit('expand', attribute.id)">
            {{ attribute.feature_label }}<span class="text-grey-7 q-ml-xs">{{ formatPct(attribute.score * 100) }}</span>
          </q-chip>
        </div>
        <div class="bin-head row no-wrap items-center text-caption text-grey-7">
          <div class="bin-label text-right" title="A value, a range, a prefix, an hour… of the column">Bin</div>
          <div class="col text-right bin-side-head" title="The bin's share of the normal records (fetched less discrepancies)">Normal records</div>
          <div class="bin-axis" />
          <div class="col bin-side-head" title="The bin's share of the discrepancies">Discrepancies</div>
          <div class="bin-lift text-right" title="How many times more common the bin is among the discrepancies than among the normal records">Lift</div>
          <div class="bin-actions" />
        </div>
        <div v-for="bin in shownBins" :key="String(bin.code)" class="bin-row row no-wrap items-center" :title="binTitle(bin)">
          <div class="bin-label ellipsis text-right" :class="{ 'text-italic text-grey-7': bin.code === null || !bin.filter }">{{ bin.label }}</div>
          <div class="col row no-wrap items-center justify-end bin-side">
            <span class="bin-pct text-grey-7">{{ formatPct(bin.normal_share * 100) }}</span>
            <div class="bin-bar" :style="{ width: binWidth(bin.normal_share), background: 'var(--rapo-normal)' }" />
          </div>
          <div class="bin-axis" />
          <div class="col row no-wrap items-center bin-side">
            <div class="bin-bar" :class="{ 'bin-bar--faint': bin.flag !== 'over' }" :style="{ width: binWidth(bin.disc_share), background: 'var(--rapo-disc)' }" />
            <span class="bin-pct" :class="bin.flag === 'over' ? 'text-red-8 text-weight-medium' : 'text-grey-7'">{{ formatPct(bin.disc_share * 100) }}</span>
          </div>
          <div class="bin-lift text-right">
            <q-chip dense square size="11px" :color="liftColor(bin.lift)" :text-color="chipTextColor(liftColor(bin.lift))" class="text-weight-bold q-mr-none">
              {{ liftText(bin.lift, bin.disc ? "only" : "–") }}
            </q-chip>
          </div>
          <div class="bin-actions row no-wrap justify-end">
            <q-btn v-if="bin.filter && bin.filter.result && bin.disc" aria-label="Show these discrepancies" flat dense round size="xs" color="primary" icon="fas fa-table" @click="showBin(bin, false)">
              <q-tooltip>Show these discrepancies</q-tooltip>
            </q-btn>
            <q-btn v-if="bin.filter && bin.filter.fetched" aria-label="Show these fetched records" flat dense round size="xs" color="grey-7" icon="fas fa-database" @click="showBin(bin, true)">
              <q-tooltip>Show these fetched records</q-tooltip>
            </q-btn>
          </div>
        </div>
        <div v-if="openAttribute.bins.length > shownBins.length" class="text-caption text-grey-7 q-mt-xs bin-more">
          {{ openAttribute.bins.length - shownBins.length }} smaller bins are not shown
        </div>
      </div>
    </template>
    <q-btn
      v-if="unrelatedColumns.length"
      flat
      dense
      no-caps
      color="primary"
      padding="4px 8px"
      class="q-mt-sm"
      :icon="showUnrelated ? 'fas fa-chevron-up' : 'fas fa-chevron-down'"
      :label="showUnrelated ? 'Hide the columns not related' : `${unrelatedColumns.length} not related`"
      @click="showUnrelated = !showUnrelated" />
  </div>
</template>

<script>
import { chipTextColor, formatPct, kindInfo, liftColor, liftText } from "../../utils/analysis";
import { formatNumber } from "../../utils/format";

const SHOWN_BINS = 12;

// The attributes of a discrepancy analysis, one row per column by its best binning, strongest first; the columns not
// related to the discrepancies at the end, folded. A row opens in place: the column's other binnings, and a butterfly
// of the bins' shares of the normal records and of the discrepancies, on one scale, each bin opening its records.
export default {
  name: "DiscrepancyAttributes",
  props: {
    report: { type: Object, required: true },
    // The attribute shown open (the URL's `attr`), or null.
    expanded: { type: String, default: null },
  },
  emits: ["expand", "show-rows"],
  data() {
    return { showUnrelated: false };
  },
  computed: {
    // The attributes of each column, its best first, the columns by their best.
    columns() {
      const byColumn = new Map();
      this.report.attributes.forEach((attribute) => {
        if (!byColumn.has(attribute.column)) {
          byColumn.set(attribute.column, { column: attribute.column, best: attribute, attributes: [] });
        }
        byColumn.get(attribute.column).attributes.push(attribute);
      });
      return [...byColumn.values()];
    },
    unrelatedColumns() {
      const unrelated = new Set(this.report.unrelated || []);
      return this.columns.filter((entry) => unrelated.has(entry.column));
    },
    shownColumns() {
      if (this.showUnrelated) {
        return this.columns;
      }
      const unrelated = new Set(this.report.unrelated || []);
      return this.columns.filter((entry) => !unrelated.has(entry.column) || entry.column === this.openColumn);
    },
    topScore() {
      return Math.max(0.0001, ...this.columns.map((entry) => entry.best.score || 0));
    },
    openAttribute() {
      return this.expanded ? this.report.attributes.find((attribute) => attribute.id === this.expanded) || null : null;
    },
    openColumn() {
      return this.openAttribute ? this.openAttribute.column : null;
    },
    // The bins that hold the most of either side, in the attribute's order.
    shownBins() {
      const bins = this.openAttribute.bins;
      if (bins.length <= SHOWN_BINS) {
        return bins;
      }
      const weight = (bin) => Math.max(bin.disc_share, bin.normal_share);
      const kept = new Set([...bins].sort((first, second) => weight(second) - weight(first)).slice(0, SHOWN_BINS));
      return bins.filter((bin) => kept.has(bin));
    },
    topShare() {
      return Math.max(0.0001, ...this.shownBins.map((bin) => Math.max(bin.disc_share, bin.normal_share)));
    },
  },
  methods: {
    formatPct,
    chipTextColor,
    kindInfo(attribute) {
      return kindInfo({ kind: attribute.kind });
    },
    liftColor,
    liftText,
    rowId(column) {
      return `attribute-${column}`;
    },
    binningShown(attribute) {
      return !["value", "decile"].includes(attribute.feature);
    },
    scoreWidth(score) {
      return `${Math.max(((score || 0) * 100) / this.topScore, 1)}%`;
    },
    binWidth(share) {
      return `${Math.max((share * 100) / this.topShare, share ? 1 : 0)}%`;
    },
    // Up to two over-represented bins (or merged bands), the most discrepancies first.
    overBins(attribute) {
      return attribute.bins
        .filter((bin) => bin.flag === "over")
        .sort((first, second) => second.disc_share - first.disc_share)
        .slice(0, 2);
    },
    binTitle(bin) {
      const rate = bin.rate === null || bin.rate === undefined ? "" : `; ${formatPct(bin.rate * 100)} of its records are discrepancies`;
      return `${bin.label}: ${formatNumber(bin.disc)} discrepancies (${formatPct(bin.disc_share * 100)}), ${formatNumber(bin.normal)} normal records (${formatPct(bin.normal_share * 100)})${rate}`;
    },
    toggle(entry) {
      this.$emit("expand", entry.column === this.openColumn ? null : entry.best.id);
    },
    // Scrolls an attribute's row into view, e.g. when a finding opens it.
    reveal(id) {
      const attribute = this.report.attributes.find((item) => item.id === id);
      if (!attribute) {
        return;
      }
      this.$nextTick(() => {
        const element = document.getElementById(this.rowId(attribute.column));
        if (element) {
          element.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    },
    showBin(bin, fetched) {
      this.$emit("show-rows", { filters: [bin.filter], fetched });
    },
  },
};
</script>

<style scoped>
.attr-head,
.bin-head {
  height: 24px;
  border-bottom: 1px solid var(--rapo-panel-border);
}

.attr-row {
  min-height: 34px;
  border-bottom: 1px solid var(--rapo-grid);
  font-size: 13px;
  scroll-margin-top: 84px;
}

.attr-row:hover {
  background: var(--rapo-teal-soft);
}

.attr-row--open {
  background: var(--rapo-surface-alt);
}

.attr-toggle {
  width: 22px;
  flex: 0 0 22px;
  text-align: center;
}

.attr-name {
  flex: 0 0 30%;
  padding-right: 12px;
}

.attr-score {
  padding-right: 16px;
}

.score-track {
  height: 10px;
}

.score-bar {
  height: 100%;
  border-radius: 2px;
  background: var(--rapo-disc);
}

.score-text {
  width: 52px;
  font-weight: 500;
}

.attr-over {
  flex: 0 0 34%;
  overflow: hidden;
}

.over-chip {
  max-width: 50%;
}

.attr-detail {
  padding: 12px 8px 16px 22px;
  border-bottom: 1px solid var(--rapo-grid);
  background: var(--rapo-surface-alt);
}

.bin-row {
  height: 24px;
  font-size: 12px;
}

.bin-row:hover {
  background: var(--rapo-row-hover);
}

.bin-label {
  flex: 0 0 22%;
  padding-right: 12px;
}

.bin-side {
  height: 100%;
}

.bin-side-head {
  padding: 0 8px;
}

.bin-axis {
  width: 1px;
  align-self: stretch;
  background: var(--rapo-panel-border);
}

.bin-bar {
  height: 12px;
  border-radius: 2px;
}

.bin-bar--faint {
  opacity: 0.5;
}

.bin-pct {
  padding: 0 6px;
  font-size: 11px;
  white-space: nowrap;
}

.bin-lift {
  width: 64px;
}

.bin-actions {
  width: 56px;
}

.bin-more {
  padding-left: 22%;
}
</style>
