<template>
  <q-card flat bordered class="finding-card full-height cursor-pointer" :class="{ 'finding-card--lead': lead }" v-keyboard:button @click="$emit('open', finding)">
    <q-card-section class="q-pb-xs">
      <div class="row no-wrap items-start">
        <q-avatar :icon="kind.icon" :color="kind.color" text-color="white" size="26px" font-size="12px" class="q-mr-sm" :title="kind.label" />
        <div class="col finding-text">
          <div class="text-caption text-grey-7 ellipsis" :title="finding.what">{{ finding.what }}</div>
          <div class="text-weight-bold text-blue-grey-10 ellipsis finding-label" :title="finding.label">{{ finding.label }}</div>
        </div>
        <q-chip dense square :color="liftColor(finding.lift)" :text-color="chipTextColor(liftColor(finding.lift))" class="text-weight-bold q-mr-none" :title="liftTitle">
          {{ liftText(finding.lift, "only") }}
        </q-chip>
      </div>
    </q-card-section>
    <q-card-section class="q-pt-xs q-pb-sm">
      <div v-for="share in shares" :key="share.key" class="share-row row no-wrap items-center" :title="share.title">
        <div class="share-label text-grey-7">{{ share.label }}</div>
        <div class="col share-track">
          <div class="share-bar" :style="{ width: Math.max(share.value * 100, 0.5) + '%', background: share.color }" />
        </div>
        <div class="share-pct text-right">{{ formatPct(share.value * 100) }}</div>
      </div>
      <div class="row justify-end q-mt-xs">
        <q-btn outline dense no-caps color="primary" icon="fas fa-table" padding="2px 8px" size="sm" label="Records" @click.stop="$emit('records', finding)">
          <q-tooltip anchor="top middle" self="bottom middle">Open these {{ formatNumber(finding.disc) }} discrepancies in Data analysis</q-tooltip>
        </q-btn>
      </div>
    </q-card-section>
  </q-card>
</template>

<script>
import { formatNumber } from "../../utils/format";
import { chipTextColor, formatPct, liftColor, liftText } from "../../utils/analysis";

const KINDS = {
  driver: { icon: "fas fa-bullseye", color: "red-7", label: "Driver: a value of one column" },
  time: { icon: "fas fa-clock", color: "purple-6", label: "Driver: a time of a date column" },
  combination: { icon: "fas fa-link", color: "deep-orange-6", label: "Combination: two columns together" },
};

// One finding of a discrepancy analysis: what it is, the share of the discrepancies it holds against the share of the
// normal records, on the same scale, and its lift. A click opens its attribute; Records its discrepancies.
export default {
  name: "FindingCard",
  props: {
    finding: { type: Object, required: true },
    lead: { type: Boolean, default: false },
  },
  emits: ["open", "records"],
  computed: {
    kind() {
      return KINDS[this.finding.kind] || KINDS.driver;
    },
    shares() {
      const finding = this.finding;
      return [
        {
          key: "disc",
          label: "Discrepancies",
          value: finding.disc_share,
          color: "var(--rapo-disc)",
          title: `${formatNumber(finding.disc)} of the discrepancies (${formatPct(finding.disc_share * 100)})`,
        },
        {
          key: "normal",
          label: "Normal",
          value: finding.normal_share,
          color: "var(--rapo-normal)",
          title: `${formatNumber(finding.normal)} of the normal records (${formatPct(finding.normal_share * 100)})`,
        },
      ];
    },
    liftTitle() {
      const finding = this.finding;
      const rate = finding.rate === null || finding.rate === undefined ? "" : ` ${formatPct(finding.rate * 100)} of these records are discrepancies.`;
      return finding.lift === null || finding.lift === undefined
        ? `Only among the discrepancies.${rate}`
        : `${liftText(finding.lift)} as common among the discrepancies as among the normal records.${rate}`;
    },
  },
  methods: {
    formatNumber,
    formatPct,
    chipTextColor,
    liftColor,
    liftText,
  },
};
</script>

<style scoped>
.finding-card:hover {
  border-color: var(--rapo-teal);
}

.finding-text {
  min-width: 0;
}

.finding-label {
  font-size: 15px;
}

.finding-card--lead .finding-label {
  font-size: 18px;
}

.share-row {
  height: 18px;
  font-size: 12px;
}

.share-label {
  width: 92px;
}

.share-track {
  height: 8px;
  background: var(--rapo-bar-track);
  border-radius: 2px;
}

.share-bar {
  height: 100%;
  border-radius: 2px;
}

.share-pct {
  width: 48px;
}
</style>
