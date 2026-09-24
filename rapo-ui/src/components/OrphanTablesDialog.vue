<template>
  <q-dialog v-model="visible">
    <q-card class="column no-wrap" style="width: 900px; max-width: 95vw; max-height: 90vh">
      <q-card-section class="row items-center q-py-sm">
        <div class="text-h6">Result tables of no control</div>
        <q-space />
        <q-btn flat round icon="close" v-close-popup />
      </q-card-section>
      <q-separator />

      <q-card-section class="col scroll">
        <div class="text-grey-7 q-mb-md">
          No control has the name these tables were created for: its control was deleted, or renamed outside the application. No run writes them any more.
        </div>
        <div v-if="!tables.length" class="text-grey-7">None left.</div>
        <q-markup-table v-else dense flat bordered separator="horizontal">
          <thead>
            <tr>
              <th class="text-left">Table</th>
              <th class="text-left">Rows</th>
              <th class="text-left">Results since</th>
              <th style="width: 220px"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="table in tables" :key="table.table">
              <td>{{ table.table }}</td>
              <td class="text-grey-8">{{ rowsText(table, exactRows[table.table]) }}</td>
              <td class="text-grey-8">{{ table.oldest ? toDateString(table.oldest) : "–" }}</td>
              <td class="text-right">
                <q-btn
                  flat
                  dense
                  no-caps
                  size="sm"
                  color="primary"
                  :label="exactRows[table.table] ? 'Count again' : 'Get exact count'"
                  :loading="Boolean(counting[table.table])"
                  @click="count(table.table)">
                  <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 5]">Counts every row: a full scan, which takes a while on a big table</q-tooltip>
                </q-btn>
                <q-btn flat dense no-caps size="sm" color="negative" label="Drop table" :disable="dropping" @click="drop(table)" />
              </td>
            </tr>
          </tbody>
        </q-markup-table>
      </q-card-section>

      <q-separator />
      <q-card-actions align="right">
        <q-btn label="Close" flat color="primary" v-close-popup />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script>
import { api, notifyError } from "../api";
import { describeOrphan, rowsText } from "../utils/schema";
import { escapeHtml, toDateString } from "../utils/format";

// Open with this.$refs.<ref>.open(). The tables come from get-schema-drift (unowned); after a drop it emits
// "changed" so the page refetches them.
export default {
  name: "OrphanTablesDialog",
  props: {
    tables: { type: Array, default: () => [] },
  },
  emits: ["changed"],
  data() {
    return { visible: false, exactRows: {}, counting: {}, dropping: false };
  },
  methods: {
    rowsText,
    toDateString,
    open() {
      this.visible = true;
    },
    async count(table) {
      this.counting = { ...this.counting, [table]: true };
      try {
        const result = await api("count-control-table-rows", { params: { table } });
        this.exactRows = { ...this.exactRows, [table]: result };
      } catch (error) {
        notifyError("Counting the rows of " + table + " failed.", error);
      } finally {
        this.counting = { ...this.counting, [table]: false };
      }
    },
    drop(table) {
      this.$q
        .dialog({
          title: "Drop orphaned table?",
          message: `<div>${escapeHtml(describeOrphan(table, this.exactRows[table.table]))}</div><div class="text-negative q-mt-md">Its past results will be deleted!</div>`,
          html: true,
          ok: { label: "Drop", color: "negative" },
          cancel: { label: "Cancel", flat: true },
          persistent: true,
        })
        .onOk(async () => {
          this.dropping = true;
          try {
            await api("drop-orphaned-table", { method: "POST", params: { table: table.table } });
            this.$q.notify({ type: "positive", message: table.table + " was dropped." });
            this.$emit("changed");
          } catch (error) {
            notifyError("Dropping " + table.table + " failed.", error);
          } finally {
            this.dropping = false;
          }
        });
    },
  },
};
</script>
