<template>
  <q-dialog v-model="visible">
    <q-card class="column no-wrap" style="width: 1100px; max-width: 95vw; max-height: 90vh">
      <q-card-section class="row items-center q-py-sm">
        <div class="text-h6">Orphaned result tables</div>
        <q-space />
        <q-btn flat round icon="close" v-close-popup />
      </q-card-section>
      <q-separator />

      <q-card-section class="col scroll">
        <div class="text-grey-7 q-mb-md">
          No run writes these tables any more: the control no longer writes that side or type, or no control has the name the table was created for.
          Dropping one deletes its past results.
        </div>
        <div v-if="!tables.length" class="text-grey-7">None left.</div>
        <q-markup-table v-else dense flat bordered separator="horizontal">
          <thead>
            <tr>
              <th class="text-left">Table</th>
              <th class="text-left">Control</th>
              <th class="text-left">Why</th>
              <th class="text-left">Rows</th>
              <th style="width: 200px"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="table in tables" :key="table.table">
              <td>{{ table.table }}</td>
              <td>
                <router-link v-if="table.control_name" :to="{ name: 'edit-control', params: { controlId: String(table.control_id) } }" @click="visible = false">
                  {{ table.control_name }}
                </router-link>
                <span v-else class="text-grey-7">no control</span>
              </td>
              <td class="text-grey-8">{{ table.reason || "its control was deleted, or renamed outside the application" }}</td>
              <td class="text-grey-8">{{ rowsText(table, exactRows[table.table]) }}</td>
              <td class="text-right">
                <q-btn
                  flat
                  dense
                  no-caps
                  size="sm"
                  color="primary"
                  :label="exactRows[table.table] ? 'Count again' : 'Get exact count'"
                  :loading="Boolean(counting[table.table])"
                  @click="count(table)">
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
import { escapeHtml } from "../utils/format";

// Open with this.$refs.<ref>.open(). The tables come from get-schema-drift: a control's orphans (with control_id,
// control_name and reason) and those of no control. After a drop it emits "changed" so the page refetches them.
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
    open() {
      this.visible = true;
    },
    // A control's table is counted as one of its result tables, one of no control as such.
    async count(table) {
      const name = table.table;
      this.counting = { ...this.counting, [name]: true };
      try {
        const result = await api("count-control-table-rows", { params: { table: name, name: table.control_name } });
        this.exactRows = { ...this.exactRows, [name]: result };
      } catch (error) {
        notifyError("Counting the rows of " + name + " failed.", error);
      } finally {
        this.counting = { ...this.counting, [name]: false };
      }
    },
    drop(table) {
      const owner = table.control_name ? `<div class="q-mb-xs">${escapeHtml(`Control ${table.control_name}: ${table.reason}.`)}</div>` : "";
      this.$q
        .dialog({
          title: "Drop orphaned table?",
          message: `${owner}<div>${escapeHtml(describeOrphan(table, this.exactRows[table.table]))}</div><div class="text-negative q-mt-md">Its past results will be deleted!</div>`,
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
