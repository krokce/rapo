<template>
  <q-dialog v-model="shown">
    <q-card style="width: 1200px; max-width: 96vw">
      <q-card-section class="row items-center q-pb-sm">
        <div>
          <div class="text-h6">Counterpart on side {{ result ? result.other_side : otherSide }}</div>
          <div class="text-caption text-grey-7">
            The records of the other side with this row's correlation key: those the run saved, and those in the other datasource for the
            run's window (time shift included).
          </div>
        </div>
        <q-space />
        <q-btn v-close-popup flat round dense icon="fas fa-times" />
      </q-card-section>

      <q-card-section class="q-pt-none">
        <div class="text-subtitle2 text-blue-grey-9 q-mb-xs">This row (side {{ side }})</div>
        <div class="row-scroll q-mb-md">
          <table class="cp-table">
            <thead>
              <tr>
                <th v-for="column in columns" :key="column.name">{{ column.name.toUpperCase() }}</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td v-for="(value, index) in row" :key="index" :class="{ 'text-grey-5': value === null }">{{ value === null ? "∅" : formatValue(value, columns[index].kind) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <q-skeleton v-if="loading" type="rect" height="160px" />
        <q-banner v-else-if="error" class="bg-red-1 text-red-9" rounded>{{ error }}</q-banner>
        <template v-else-if="result">
          <div class="row items-center q-gutter-sm q-mb-md">
            <span class="text-grey-8">Correlation key</span>
            <q-chip v-for="(key, index) in result.keys" :key="index" dense color="blue-grey-1" text-color="blue-grey-10">
              <code class="q-mr-xs">{{ key.expression }}</code> = <strong class="q-ml-xs">{{ key.value === null ? "null" : key.value }}</strong>
            </q-chip>
          </div>
          <div v-for="part in parts" :key="part.key" class="q-mb-md">
            <div class="text-subtitle2 text-blue-grey-9">
              {{ part.title }}
              <q-badge :color="part.data.rows.length ? 'primary' : 'grey-5'" class="q-ml-xs">{{ part.data.rows.length }}{{ part.data.more ? "+" : "" }}</q-badge>
            </div>
            <div v-if="part.data.error" class="text-red-8 text-caption">{{ part.data.error }}</div>
            <div v-else-if="!part.data.rows.length" class="text-grey-7 text-caption q-py-xs">{{ part.empty }}</div>
            <div v-else class="row-scroll">
              <table class="cp-table">
                <thead>
                  <tr>
                    <th v-for="name in part.data.columns" :key="name">{{ name.toUpperCase() }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(values, index) in part.data.rows" :key="index">
                    <td v-for="(value, position) in values" :key="position" :class="cellClass(part.data.columns[position], value)">
                      {{ value === null ? "∅" : formatValue(value, isDate(value) ? "datetime" : "text") }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </template>
      </q-card-section>
    </q-card>
  </q-dialog>
</template>

<script>
import { api } from "../../api";
import { formatValue } from "../../utils/analysis";

const TYPE_CLASSES = { Loss: "text-red-8 text-weight-bold", Discrepancy: "text-orange-9 text-weight-bold", Duplicate: "text-purple-8 text-weight-bold", Match: "text-green-8 text-weight-bold" };

// The other side of a reconciliation row: looked up by the server with the control's correlation expressions.
export default {
  name: "CounterpartDialog",
  props: {
    sessionId: { type: String, required: true },
    columns: { type: Array, required: true },
    side: { type: String, default: "A" },
  },
  data() {
    return { shown: false, row: [], result: null, error: null, loading: false };
  },
  computed: {
    otherSide() {
      return this.side === "A" ? "B" : "A";
    },
    parts() {
      if (!this.result) {
        return [];
      }
      return [
        {
          key: "results",
          title: `Saved by the run in ${this.result.results.table}`,
          data: this.result.results,
          empty: "The run saved no record with this key on the other side (a matched record is saved only with Save reconciled).",
        },
        {
          key: "source",
          title: `In datasource ${this.result.other_side} for the run's window`,
          data: this.result.source,
          empty: "No record of the other datasource has this key in the run's window.",
        },
      ];
    },
  },
  methods: {
    formatValue,
    async open(row) {
      this.row = row;
      this.result = null;
      this.error = null;
      this.shown = true;
      this.loading = true;
      try {
        this.result = await api("analysis-counterpart", { method: "POST", params: { session_id: this.sessionId }, body: { row }, loadingBar: false });
      } catch (error) {
        this.error = error.message;
      } finally {
        this.loading = false;
      }
    },
    isDate(value) {
      return typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(value);
    },
    cellClass(name, value) {
      if (value === null) {
        return "text-grey-5";
      }
      return name === "rapo_result_type" ? TYPE_CLASSES[value] || "" : "";
    },
  },
};
</script>

<style scoped>
.row-scroll {
  overflow-x: auto;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
}

.cp-table {
  border-collapse: collapse;
  font-size: 13px;
  width: 100%;
}

.cp-table th {
  background: #cfd8dc;
  padding: 5px 8px;
  text-align: left;
  white-space: nowrap;
  font-weight: 600;
}

.cp-table td {
  padding: 4px 8px;
  border-top: 1px solid #eceff1;
  white-space: nowrap;
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
