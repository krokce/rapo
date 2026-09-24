<template>
  <div v-if="!overview" class="row q-col-gutter-md">
    <div v-for="index in 6" :key="index" class="col-6 col-sm-4 col-md-2"><q-skeleton type="rect" height="84px" /></div>
    <div class="col-12"><q-skeleton type="rect" height="200px" /></div>
  </div>
  <div v-else>
    <div class="row q-col-gutter-md q-mb-lg">
      <div v-for="card in cards" :key="card.label" class="col-6 col-sm-4 col-md-2">
        <q-card flat bordered class="stat-card" :class="{ 'cursor-pointer': card.filters }" @click="card.filters && $emit('show-rows', card.filters)">
          <q-card-section class="q-pa-sm">
            <div class="text-caption text-grey-7">
              <q-icon :name="card.icon" class="q-mr-xs" />
              {{ card.label }}
            </div>
            <div class="text-h6 text-blue-grey-9">{{ card.value }}</div>
            <div class="text-caption text-grey-6">{{ card.note || "\u00a0" }}</div>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <div class="row q-col-gutter-lg">
      <div class="col-12 col-md-4">
        <div class="text-subtitle1 text-blue-grey-9 q-mb-sm">Column types</div>
        <q-list dense bordered separator class="rounded-borders">
          <q-item v-for="item in types" :key="item.key">
            <q-item-section avatar>
              <q-avatar size="24px" :icon="item.icon" :color="item.color" text-color="white" font-size="12px" />
            </q-item-section>
            <q-item-section>{{ item.label }}</q-item-section>
            <q-item-section side class="text-weight-bold">{{ item.count }}</q-item-section>
          </q-item>
        </q-list>
      </div>
      <div class="col-12 col-md-8">
        <div class="row items-center q-mb-sm">
          <div class="text-subtitle1 text-blue-grey-9">Alerts</div>
          <q-badge class="q-ml-sm" color="blue-grey-5">{{ overview.alerts.length }}</q-badge>
          <q-space />
          <q-btn-toggle
            v-model="alertLevel"
            dense
            no-caps
            unelevated
            toggle-color="blue-grey-7"
            color="grey-3"
            text-color="grey-8"
            size="sm"
            :options="[
              { label: `Warnings ${warningCount}`, value: 'warning' },
              { label: 'All', value: 'all' },
            ]" />
        </div>
        <div v-if="!shownAlerts.length" class="text-grey-7 q-pa-md">No alerts{{ alertLevel === "warning" ? " at warning level" : "" }}.</div>
        <q-list v-else dense bordered separator class="rounded-borders">
          <q-item v-for="(alert, index) in shownAlerts" :key="index">
            <q-item-section avatar>
              <q-icon :name="alert.level === 'warning' ? 'fas fa-exclamation-triangle' : 'fas fa-info-circle'" :color="alert.level === 'warning' ? 'orange-8' : 'blue-grey-5'" size="16px" />
            </q-item-section>
            <q-item-section>
              <q-item-label>
                <a v-if="alert.column" class="column-link" @click="$emit('show-column', alert.column)">{{ alert.column.toUpperCase() }}</a>
                <span :class="{ 'q-ml-sm': alert.column }">{{ alert.message }}</span>
              </q-item-label>
            </q-item-section>
            <q-item-section side>
              <q-chip dense square size="sm" color="grey-3" text-color="grey-8">{{ alertLabel(alert.code) }}</q-chip>
            </q-item-section>
            <q-item-section side>
              <q-btn v-if="alertFilters(alert)" flat dense round size="sm" color="primary" icon="fas fa-table" @click="$emit('show-rows', alertFilters(alert))">
                <q-tooltip>Show these rows</q-tooltip>
              </q-btn>
            </q-item-section>
          </q-item>
        </q-list>
      </div>
    </div>
  </div>
</template>

<script>
import { formatNumber } from "../../utils/format";
import { KIND_ICONS, formatBytes, formatPct } from "../../utils/analysis";

const ALERT_LABELS = {
  duplicates: "Duplicates",
  empty: "Empty",
  constant: "Constant",
  unique: "Unique",
  missing: "Missing",
  some_missing: "Missing",
  high_cardinality: "High cardinality",
  imbalanced: "Imbalanced",
  zeros: "Zeros",
  skewed: "Skewed",
  blank: "Blank",
};

export default {
  name: "AnalysisOverview",
  props: {
    overview: { type: Object, default: null },
  },
  emits: ["show-rows", "show-column"],
  data() {
    return { alertLevel: "warning" };
  },
  computed: {
    cards() {
      const o = this.overview;
      return [
        { label: "Rows", icon: "fas fa-list", value: formatNumber(o.rows), note: "in the sample" },
        { label: "Columns", icon: "fas fa-columns", value: formatNumber(o.columns) },
        { label: "Missing cells", icon: "fas fa-border-none", value: formatNumber(o.missing_cells), note: formatPct(o.missing_pct) },
        {
          label: "Duplicate rows",
          icon: "fas fa-clone",
          value: formatNumber(o.duplicate_rows),
          note: formatPct(o.duplicate_pct),
          filters: o.duplicate_rows ? [{ op: "duplicated" }] : null,
        },
        { label: "Memory", icon: "fas fa-memory", value: formatBytes(o.memory_bytes), note: "of the sample" },
        { label: "Alerts", icon: "fas fa-exclamation-triangle", value: formatNumber(o.alerts.length), note: `${this.warningCount} warnings` },
      ];
    },
    types() {
      return Object.entries(this.overview.types).map(([key, count]) => ({ key, count, ...KIND_ICONS[key] }));
    },
    warningCount() {
      return this.overview.alerts.filter((alert) => alert.level === "warning").length;
    },
    shownAlerts() {
      return this.alertLevel === "all" ? this.overview.alerts : this.overview.alerts.filter((alert) => alert.level === "warning");
    },
  },
  watch: {
    // With no warnings, the informational alerts are shown straight away.
    overview: {
      immediate: true,
      handler(overview) {
        if (overview && !overview.alerts.some((alert) => alert.level === "warning")) {
          this.alertLevel = "all";
        }
      },
    },
  },
  methods: {
    alertLabel(code) {
      return ALERT_LABELS[code] || code;
    },
    alertFilters(alert) {
      if (alert.code === "duplicates") {
        return [{ op: "duplicated" }];
      }
      if (["missing", "some_missing", "empty"].includes(alert.code)) {
        return [{ column: alert.column, op: "null" }];
      }
      return null;
    },
  },
};
</script>

<style scoped>
.stat-card {
  height: 100%;
}

.column-link {
  color: #009688;
  cursor: pointer;
  font-weight: 500;
}

.column-link:hover {
  text-decoration: underline;
}
</style>
