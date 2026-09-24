<template>
  <q-dialog v-model="visible">
    <q-card class="column no-wrap" style="width: 1000px; max-width: 95vw; max-height: 90vh">
      <q-card-section class="row items-center q-py-sm">
        <div class="text-h6">Result table schema</div>
        <q-space />
        <q-toggle v-model="showAll" dense label="Show all columns" class="q-mr-md" />
        <q-btn flat round icon="close" v-close-popup />
      </q-card-section>
      <q-separator />

      <q-card-section class="col scroll q-gutter-y-md">
        <div v-if="!check" class="text-grey-7">Checking...</div>
        <template v-else>
          <div v-if="summary.errors.length" class="text-negative">
            <div v-for="error in summary.errors" :key="error">{{ error }}</div>
          </div>
          <div v-if="sourceNotice" class="text-orange-9">{{ sourceNotice }}</div>
          <div v-if="summary.renamed" class="text-blue-grey-8">The result tables will be renamed to the new control name when it is saved.</div>
          <div v-if="check.active_run" class="text-orange-9">A run of this control is in progress: changing its tables now may make it fail.</div>

          <div v-for="orphan in summary.orphans" :key="orphan.table">
            <div class="row items-baseline q-gutter-x-md q-mb-xs">
              <div class="text-subtitle1 text-weight-medium">{{ orphan.table.toUpperCase() }}</div>
              <q-badge color="negative" title="No run of this configuration writes this table any more">Orphaned</q-badge>
              <div class="text-grey-7">
                {{ rowsText(orphan, exactRows[orphan.table]) }}<template v-if="orphan.oldest">, results since {{ toDateString(orphan.oldest) }}</template>
              </div>
              <q-btn
                flat
                dense
                no-caps
                size="sm"
                color="primary"
                :label="exactRows[orphan.table] ? 'Count again' : 'Get exact count'"
                :loading="Boolean(countingRows[orphan.table])"
                @click="$emit('count', orphan.table)" />
              <q-btn flat dense no-caps size="sm" color="negative" label="Drop table" :disable="busy" @click="drop(orphan.table)" />
            </div>
            <div class="text-grey-7">{{ orphanReason(orphan) }}</div>
          </div>

          <div v-for="table in summary.tables" :key="table.target">
            <div class="row items-baseline q-gutter-x-md q-mb-xs">
              <div class="text-subtitle1 text-weight-medium">{{ table.table.toUpperCase() }}</div>
              <div v-if="table.table !== table.target" class="text-blue-grey-8">→ {{ table.target.toUpperCase() }}</div>
              <div v-if="!table.exists" class="text-grey-7">does not exist yet, the next run creates it</div>
              <div v-else class="text-grey-7">
                {{ rowsText(table, exactRows[table.table]) }}<template v-if="table.oldest">, results since {{ toDateString(table.oldest) }}</template>
              </div>
              <q-btn
                v-if="table.exists"
                flat
                dense
                no-caps
                size="sm"
                color="primary"
                :label="exactRows[table.table] ? 'Count again' : 'Get exact count'"
                :loading="Boolean(countingRows[table.table])"
                @click="$emit('count', table.table)">
                <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 5]">Counts every row: a full scan, which takes a while on a big table</q-tooltip>
              </q-btn>
            </div>
            <q-markup-table v-if="table.exists && rowsOf(table).length" dense flat bordered separator="horizontal">
              <thead>
                <tr>
                  <th class="text-left">Column</th>
                  <th class="text-left" style="width: 130px">Status</th>
                  <th class="text-left">In the table</th>
                  <th class="text-left">Expected</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="column in rowsOf(table)" :key="column.name">
                  <td>{{ column.name.toUpperCase() }}</td>
                  <td>
                    <q-badge :color="status(column).color" :title="status(column).title">{{ status(column).label }}</q-badge>
                  </td>
                  <td class="text-grey-8">{{ column.current || "–" }}</td>
                  <td>{{ column.expected || "–" }}</td>
                </tr>
              </tbody>
            </q-markup-table>
            <div v-else-if="table.exists" class="text-grey-7">All {{ table.columns.length }} columns hold what the configuration writes.</div>
          </div>
        </template>
      </q-card-section>

      <q-separator />
      <q-card-actions align="right">
        <div v-if="dirty" class="text-grey-7 q-mr-md">Unsaved changes are saved first.</div>
        <q-btn v-if="summary.safe" label="Update schema" color="primary" :disable="busy" @click="act('update')" />
        <q-btn label="Recreate schema" color="negative" :flat="!emphasizeRecreate" :disable="busy" @click="act('recreate')" />
        <q-btn label="Close" flat color="primary" v-close-popup />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script>
import { SCHEMA_STATUSES, rowsText, summarizeSchema } from "../utils/schema";
import { toDateString } from "../utils/format";

// Open with this.$refs.<ref>.open(). It follows the parent's check live, and hands Update/Recreate back to it.
export default {
  name: "SchemaDiffDialog",
  props: {
    check: { type: Object, default: null },
    dirty: { type: Boolean, default: false },
    busy: { type: Boolean, default: false },
    // Exact row counts by table name, and the tables being counted, both kept by the parent.
    exactRows: { type: Object, default: () => ({}) },
    countingRows: { type: Object, default: () => ({}) },
  },
  emits: ["update", "recreate", "count", "drop"],
  data() {
    return { visible: false, showAll: false };
  },
  computed: {
    summary() {
      return summarizeSchema(this.check);
    },
    // What a changed datasource means for the tables: start anew, or keep their history where the columns allow.
    sourceNotice() {
      const sides = this.check ? this.check.source_changed : [];
      if (!sides.length) {
        return null;
      }
      const which = sides.includes("source") ? "The datasource" : `Datasource ${sides.join(" and ")}`;
      if (this.summary.incompatible) {
        return `${which} changed. Only Recreate schema makes the result tables fit it, deleting their past results.`;
      }
      const empty = this.summary.notOutput ? `, with ${this.summary.notOutput} old column(s) left empty from now on` : "";
      return `${which} changed. Recreate schema starts the result tables anew for it. Update schema keeps them and their history${empty}.`;
    },
    emphasizeRecreate() {
      return this.summary.incompatible > 0 || Boolean(this.check && this.check.source_changed.length);
    },
  },
  methods: {
    rowsText,
    toDateString,
    open() {
      this.visible = true;
    },
    status(column) {
      return SCHEMA_STATUSES[column.status] || SCHEMA_STATUSES.ok;
    },
    rowsOf(table) {
      return this.showAll ? table.columns : table.columns.filter((column) => column.status !== "ok");
    },
    // Why nothing writes the table: a reconciliation side whose output is off, or a table of another control type.
    orphanReason(orphan) {
      const side = { rapo_resa_: "A", rapo_resb_: "B" }[orphan.target.slice(0, 10)];
      if (side && this.check.control_type === "REC") {
        return `No discrepancies of side ${side} are written (Data and logic), so runs no longer fill this table. Drop it, or tick its output again to keep using it.`;
      }
      return "It belongs to another control type than this control has now, so runs no longer fill it.";
    },
    drop(table) {
      this.visible = false;
      this.$emit("drop", table);
    },
    act(action) {
      this.visible = false;
      this.$emit(action);
    },
  },
};
</script>
