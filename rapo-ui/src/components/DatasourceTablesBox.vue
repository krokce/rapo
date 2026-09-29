<template>
  <div class="q-gutter-y-md">
    <div class="text-caption text-grey-7">
      The tables this datasource loads (PDI_CORE_DS_TABLES). A RECYCLE or DELETE of a file deletes its records from each of them by FILE_ID. With a
      partition key, the PDI Core maintenance keeps PARTITION_DAYS_TO_RETAIN daily partitions and creates PARTITION_DAYS_IN_ADVANCE ahead. When
      several datasources share a table, only one of them should partition it.
    </div>

    <q-banner v-if="sourceTableHint" dense rounded class="bg-orange-1 text-orange-10">
      <template #avatar><q-icon name="fas fa-info-circle" size="16px" /></template>
      Table {{ sourceTableHint }} exists and is named like the datasource, but is not linked.
      <template #action>
        <q-btn flat label="Link it" @click="addLink(sourceTableHint)" />
      </template>
    </q-banner>

    <q-markup-table flat bordered dense>
      <thead>
        <tr class="bg-blue-grey-2">
          <th class="text-left" style="width: 30%">Table</th>
          <th class="text-left" style="width: 22%">Partition key</th>
          <th class="text-left" style="width: 12%">Days to retain</th>
          <th class="text-left" style="width: 12%">Days in advance</th>
          <th class="text-left">In the database</th>
          <th style="width: 44px"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!links.length">
          <td colspan="6" class="text-grey-7">No tables. Add the tables this datasource loads, the one named like it first.</td>
        </tr>
        <tr v-for="(link, index) in links" :key="index" class="align-top">
          <td>
            <q-select
              v-model="link.table_name"
              outlined
              dense
              use-input
              hide-selected
              fill-input
              input-debounce="100"
              new-value-mode="add-unique"
              :options="tableOptions"
              :rules="[(value) => !!value || 'Required', (value) => !duplicate(value, index) || 'Listed twice']"
              hide-bottom-space
              @filter="filterTables"
              @input-value="(value) => (link.table_name = value ? value.toUpperCase() : '')"
              @update:model-value="(value) => tableChanged(link, value)" />
          </td>
          <td>
            <q-select
              v-model="link.partition_key"
              outlined
              dense
              clearable
              use-input
              hide-selected
              fill-input
              new-value-mode="add-unique"
              :options="dateColumnsOf(link.table_name)"
              :hint="columnHint(link)"
              @input-value="(value) => (link.partition_key = value ? value.toUpperCase() : null)"
              @update:model-value="(value) => keyChanged(link, value)" />
          </td>
          <td>
            <q-input
              v-model.number="link.partition_days_to_retain"
              type="number"
              outlined
              dense
              :disable="!link.partition_key"
              :rules="[(value) => !link.partition_key || (Number.isInteger(value) && value >= 1) || '1 or more']"
              hide-bottom-space />
          </td>
          <td>
            <q-input
              v-model.number="link.partition_days_in_advance"
              type="number"
              outlined
              dense
              :disable="!link.partition_key"
              :rules="[(value) => !link.partition_key || value === null || value === '' || (Number.isInteger(value) && value >= 0) || '0 or more']"
              hide-bottom-space />
          </td>
          <td class="facts">
            <template v-if="factsOf(link.table_name)">
              <div v-for="(line, lineIndex) in factLines(link)" :key="lineIndex" :class="line.class">
                <q-icon v-if="line.icon" :name="line.icon" size="12px" class="q-mr-xs" />{{ line.text }}
              </div>
              <!-- Another datasource retaining the table: PDI Core should partition a table from one datasource only. -->
              <div v-for="other in otherRetainers(link)" :key="other.id" :class="link.partition_key ? 'text-orange-9' : 'text-blue-grey-8'">
                <q-icon :name="link.partition_key ? 'fas fa-exclamation-triangle' : 'fas fa-info-circle'" size="12px" class="q-mr-xs" />
                {{ link.partition_key ? "Also retained by" : "Retained by" }}
                <router-link :to="{ name: 'edit-datasource', params: { id: String(other.id) }, query: { tab: 'retention' } }">{{ other.sourcename }}</router-link>:
                {{ other.partition_key }}, {{ other.partition_days_to_retain }} day(s){{ other.partition_days_in_advance != null ? `, ${other.partition_days_in_advance} ahead` : "" }}
                <q-btn v-if="!link.partition_key" flat size="sm" color="primary" label="Copy" class="q-ml-xs" @click="copyRetention(link, other)">
                  <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]" max-width="360px">Fill in the partition key and days of {{ other.sourcename }}, e.g. to move the retention here; then remove them there</q-tooltip>
                </q-btn>
              </div>
            </template>
            <q-skeleton v-else-if="link.table_name" type="text" width="70%" />
          </td>
          <td>
            <q-btn aria-label="Remove row" v-if="removable(link)" size="sm" color="primary" flat round icon="fas fa-minus" @click="links.splice(index, 1)">
              <q-tooltip anchor="top right" self="bottom right" :offset="[0, 5]">Remove the table from the datasource (the table itself stays)</q-tooltip>
            </q-btn>
          </td>
        </tr>
      </tbody>
    </q-markup-table>

    <div>
      <q-btn size="md" color="primary" icon="fas fa-plus" label="Add table" @click="addLink(links.length ? '' : datasource.sourcename)" />
    </div>
  </div>
</template>

<script>
import { api } from "../api";
import { emptyLink } from "../utils/datasources";

const DATE_TYPE = /^(DATE|TIMESTAMP)/;

// The tables of a datasource (its `links`, PDI_CORE_DS_TABLES rows), edited in place in the parent's object, and what
// the dictionary says about each (get-ds-table-facts): whether it exists, how it is partitioned, and which datasources
// partition it. A table need not exist: the list may name the tables of another environment.
export default {
  name: "DatasourceTablesBox",
  props: {
    modelValue: { type: Object, required: true },
    // The tables and views of rapo's schema (get-datasources).
    tables: { type: Array, default: () => [] },
    // The table names of the saved datasource: without a DELETE grant those cannot be removed.
    savedTables: { type: Array, default: () => [] },
    canDelete: { type: Boolean, default: true },
  },
  data() {
    return {
      tableOptions: this.tables,
      facts: {},
      columns: {},
    };
  },
  computed: {
    datasource() {
      return this.modelValue;
    },
    // The editor always gives a datasource its links array.
    links() {
      return this.datasource.links;
    },
    // Tables whose facts are wanted: every linked one and the one named like the datasource.
    factNames() {
      const names = this.links.map((link) => (link.table_name || "").toUpperCase()).filter(Boolean);
      if (this.datasource.sourcename) {
        names.push(this.datasource.sourcename.toUpperCase());
      }
      return [...new Set(names)].sort();
    },
    sourceTableHint() {
      const name = (this.datasource.sourcename || "").toUpperCase();
      const fact = this.facts[name];
      const linked = this.links.some((link) => (link.table_name || "").toUpperCase() === name);
      return name && fact && fact.exists && !linked ? name : null;
    },
  },
  watch: {
    // A save or reload swaps the datasource: which datasources partition a table may have changed with it.
    modelValue() {
      this.facts = {};
      this.loadFacts(this.factNames);
    },
    tables(value) {
      this.tableOptions = value;
    },
    factNames: {
      handler(names) {
        clearTimeout(this.factsTimer);
        this.factsTimer = setTimeout(() => this.loadFacts(names), 300);
      },
      immediate: true,
    },
  },
  unmounted() {
    clearTimeout(this.factsTimer);
  },
  methods: {
    filterTables(value, update) {
      const needle = (value || "").toUpperCase();
      update(() => {
        this.tableOptions = needle ? this.tables.filter((name) => name.includes(needle)).slice(0, 200) : this.tables.slice(0, 200);
      });
    },
    async loadFacts(names) {
      const missing = names.filter((name) => !(name in this.facts));
      if (!missing.length) {
        return;
      }
      try {
        const facts = await api("get-ds-table-facts", { params: { tables: missing }, loadingBar: false });
        this.facts = { ...this.facts, ...facts };
      } catch (error) {
        // The facts are hints only: without them the rows show no dictionary line.
      }
      missing.filter((name) => this.facts[name] && this.facts[name].exists).forEach((name) => this.loadColumns(name));
    },
    async loadColumns(name) {
      if (name in this.columns) {
        return;
      }
      this.columns = { ...this.columns, [name]: null };
      try {
        const columns = await api("get-datasource-columns", { params: { datasource_name: name }, loadingBar: false });
        this.columns = { ...this.columns, [name]: columns };
      } catch (error) {
        // The key is then typed rather than picked.
      }
    },
    factsOf(name) {
      return name ? this.facts[String(name).toUpperCase()] : null;
    },
    dateColumnsOf(name) {
      const columns = name ? this.columns[String(name).toUpperCase()] : null;
      return (columns || []).filter((column) => DATE_TYPE.test(column.data_type)).map((column) => column.column_name);
    },
    columnHint(link) {
      const fact = this.factsOf(link.table_name);
      return fact && fact.exists && !this.dateColumnsOf(link.table_name).length ? "The table has no DATE column" : undefined;
    },
    duplicate(value, index) {
      const name = (value || "").toUpperCase();
      return this.links.some((link, other) => other !== index && (link.table_name || "").toUpperCase() === name);
    },
    removable(link) {
      return this.canDelete || !this.savedTables.includes((link.table_name || "").toUpperCase());
    },
    tableChanged(link, value) {
      link.table_name = value ? String(value).toUpperCase() : "";
    },
    // Days mean nothing without a key, and are cleared with it; a new key starts with the usual month and week.
    keyChanged(link, value) {
      link.partition_key = value ? String(value).toUpperCase() : null;
      if (!link.partition_key) {
        link.partition_days_to_retain = null;
        link.partition_days_in_advance = null;
      } else if (link.partition_days_to_retain == null) {
        link.partition_days_to_retain = 30;
        link.partition_days_in_advance = 7;
      }
    },
    addLink(name) {
      this.links.push({ ...emptyLink(), table_name: (name || "").toUpperCase() });
    },
    // What the dictionary says of a link's table, and what looks wrong: {text, class, icon} lines.
    factLines(link) {
      const fact = this.factsOf(link.table_name);
      const lines = [];
      if (!fact.exists) {
        lines.push({ text: "Not found in rapo's schema", class: "text-orange-9", icon: "fas fa-exclamation-triangle" });
        return lines;
      }
      if (!fact.partitioned) {
        lines.push({ text: `Not partitioned${fact.num_rows != null ? `, ~${Number(fact.num_rows).toLocaleString()} rows` : ""}` });
        if (link.partition_key) {
          lines.push({ text: "A partition key needs a partitioned table", class: "text-red-6", icon: "fas fa-exclamation-circle" });
        }
      } else {
        const range = [boundary(fact.first_partition), boundary(fact.last_partition)].filter(Boolean);
        lines.push({
          text: `${fact.partitioning_type || "Partitioned"} by ${fact.partition_keys.join(", ")}${fact.interval ? " (interval)" : ""}, ${fact.partition_count} partition(s)${
            range.length === 2 ? `, below ${range[0]} to ${range[1]}` : ""
          }`,
        });
        if (link.partition_key && !fact.partition_keys.includes(link.partition_key)) {
          lines.push({ text: `The table is partitioned by ${fact.partition_keys.join(", ")}, not ${link.partition_key}`, class: "text-red-6", icon: "fas fa-exclamation-circle" });
        }
      }
      return lines;
    },
    // Other datasources partitioning the same table, with their key and days: a note, and a warning once this one
    // partitions it too, which the PDI Core documentation warns against.
    otherRetainers(link) {
      const fact = this.factsOf(link.table_name);
      return fact ? fact.partitioned_by.filter((item) => item.id !== this.datasource.id) : [];
    },
    copyRetention(link, other) {
      link.partition_key = other.partition_key;
      link.partition_days_to_retain = other.partition_days_to_retain;
      link.partition_days_in_advance = other.partition_days_in_advance;
    },
  },
};

// The date of a partition's high value, e.g. TO_DATE(' 2026-09-27 00:00:00', ...), else the value.
function boundary(value) {
  if (!value) {
    return null;
  }
  const match = String(value).match(/\d{4}-\d{2}-\d{2}/);
  return match ? match[0] : String(value).slice(0, 30);
}
</script>

<style scoped>
.align-top td {
  vertical-align: top;
}
.facts {
  font-size: 12px;
  white-space: normal;
  padding-top: 10px !important;
}
</style>
