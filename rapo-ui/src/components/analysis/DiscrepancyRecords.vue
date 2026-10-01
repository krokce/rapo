<template>
  <div>
    <div class="text-caption text-grey-7 q-mb-sm">
      Example records of the strongest findings: up to 10 discrepancies, and up to 10 fetched records of the same bins (fetched records hold the
      discrepancies too). The columns of the finding come first. Open all of them in Data analysis for more.
    </div>
    <div v-if="!report.excerpts.length" class="state-notice">
      <q-icon name="fas fa-table" />
      <div>There is no finding to show records of.</div>
    </div>
    <q-card v-for="excerpt in report.excerpts" :key="excerpt.finding" flat bordered class="q-mb-md">
      <q-card-section class="row items-center no-wrap q-py-sm header">
        <div class="text-weight-medium text-blue-grey-10 ellipsis" :title="excerpt.label">{{ excerpt.label }}</div>
        <q-space />
        <q-btn v-if="filterOf(excerpt)" flat dense no-caps size="sm" color="primary" icon="fas fa-table" label="All discrepancies" @click="$emit('show-rows', { filters: [filterOf(excerpt)] })" />
        <q-btn v-if="filterOf(excerpt)" flat dense no-caps size="sm" color="blue-grey-7" icon="fas fa-database" label="All fetched" @click="$emit('show-rows', { filters: [filterOf(excerpt)], fetched: true })" />
      </q-card-section>
      <q-separator />
      <q-card-section v-for="which in ['result', 'fetched']" :key="which" class="q-py-sm">
        <div class="text-subtitle2 text-blue-grey-9 q-mb-xs">{{ which === "result" ? "Discrepancies" : "Fetched records" }}</div>
        <div v-if="excerpt[`${which}_error`]" class="text-red-8 text-caption">{{ excerpt[`${which}_error`] }}</div>
        <div v-else-if="!excerpt[which].length" class="text-grey-7 text-caption">No record.</div>
        <div v-else class="excerpt-scroll">
          <table class="excerpt-table">
            <thead>
              <tr>
                <th v-for="index in order(excerpt)" :key="index" :class="{ 'key-column': keyColumns(excerpt).has(excerpt.columns[index]) }" :title="excerpt.columns[index]">
                  {{ excerpt.columns[index] }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, rowIndex) in excerpt[which]" :key="rowIndex">
                <td v-for="index in order(excerpt)" :key="index" class="number-cell" :class="{ 'key-column': keyColumns(excerpt).has(excerpt.columns[index]) }">
                  {{ cell(row[index]) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </q-card-section>
    </q-card>
  </div>
</template>

<script>
// Example records of a discrepancy analysis' findings, the finding's columns first and highlighted.
export default {
  name: "DiscrepancyRecords",
  props: {
    report: { type: Object, required: true },
  },
  emits: ["show-rows"],
  methods: {
    finding(excerpt) {
      return this.report.findings.find((item) => item.id === excerpt.finding);
    },
    filterOf(excerpt) {
      const finding = this.finding(excerpt);
      return finding ? finding.filter : null;
    },
    // The columns of the attributes a finding is about.
    keyColumns(excerpt) {
      const finding = this.finding(excerpt);
      const ids = new Set();
      if (finding) {
        ids.add(finding.attribute);
        const combination = (this.report.combinations || []).find((item) => item.id === finding.id);
        (combination ? combination.attributes : []).forEach((id) => ids.add(id));
      }
      return new Set(this.report.attributes.filter((item) => ids.has(item.id)).map((item) => item.column));
    },
    order(excerpt) {
      const keys = this.keyColumns(excerpt);
      const indexes = excerpt.columns.map((column, index) => index);
      return [...indexes.filter((index) => keys.has(excerpt.columns[index])), ...indexes.filter((index) => !keys.has(excerpt.columns[index]))];
    },
    cell(value) {
      if (value === null || value === undefined) {
        return "";
      }
      return typeof value === "string" ? value.replace("T", " ").replace(/ 00:00:00$/, "") : String(value);
    },
  },
};
</script>

<style scoped>
.header {
  background: var(--rapo-surface-alt);
}

.excerpt-scroll {
  overflow-x: auto;
}

.excerpt-table {
  border-collapse: collapse;
  font-size: 12px;
  white-space: nowrap;
}

.excerpt-table th {
  text-align: left;
  font-weight: 500;
  color: var(--rapo-label);
  padding: 2px 8px;
  border-bottom: 1px solid var(--rapo-panel-border);
}

.excerpt-table td {
  padding: 2px 8px;
  border-bottom: 1px solid var(--rapo-grid);
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.excerpt-table .key-column {
  background: var(--rapo-highlight);
}
</style>
