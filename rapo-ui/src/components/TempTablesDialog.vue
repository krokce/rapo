<template>
  <q-dialog v-model="visible">
    <q-card class="column no-wrap" style="width: 1100px; max-width: 95vw; max-height: 90vh">
      <q-card-section class="row items-center q-py-sm">
        <div class="text-h6">Temporary tables</div>
        <q-space />
        <q-btn aria-label="Close" flat round icon="fas fa-times" v-close-popup />
      </q-card-section>
      <q-separator />

      <q-card-section class="col column no-wrap scroll">
        <div class="text-grey-7 q-mb-md">
          A run drops its temporary tables when it ends Done, unless it runs in debug mode. Failed, canceled and debug runs leave them behind.
          They hold no results; runs in progress are not listed.
        </div>
        <div v-if="!runs.length && !scratch.length && !unknown.length" class="text-grey-7">None left.</div>

        <template v-if="runs.length">
          <div class="text-subtitle2 q-mb-xs">Runs ({{ runs.length }})</div>
          <q-virtual-scroll
            type="table"
            dense
            class="list-table temp-runs"
            :items="runs"
            :virtual-scroll-item-size="33"
            :virtual-scroll-sticky-size-start="28"
            :table-colspan="7">
            <template #before>
              <thead>
                <tr>
                  <th class="text-left">Run</th>
                  <th class="text-left">Control</th>
                  <th class="text-left">Status</th>
                  <th class="text-left">Started</th>
                  <th class="text-right">Tables</th>
                  <th class="text-right">MB</th>
                  <th></th>
                </tr>
              </thead>
            </template>
            <template #default="{ item: run }">
              <tr :key="run.process_id">
                <td>
                  {{ run.process_id }}
                  <q-badge v-if="run.debug" outline color="grey-7" class="q-ml-xs" label="debug" title="Kept on purpose: the run was started in debug mode" />
                </td>
                <td>
                  <router-link v-if="run.control_name" :to="{ name: 'edit-control', params: { controlId: String(run.control_id) } }" @click="visible = false">
                    {{ run.control_name }}
                  </router-link>
                  <span v-else class="text-grey-7">{{ run.in_log ? "deleted control" : "run no longer in the log" }}</span>
                </td>
                <td>
                  <q-chip v-if="run.in_log" dense size="12px">
                    <q-avatar :icon="runStatus(run.status).icon" :color="runStatus(run.status).color" text-color="white" />
                    {{ runStatus(run.status).label }}
                  </q-chip>
                </td>
                <td class="text-grey-8">{{ toDateTimeString(run.started) }}</td>
                <td class="text-right" :title="run.tables.join('\n')">{{ run.tables.length }}</td>
                <td class="text-right text-grey-8">{{ formatNumber(run.mb, 1) }}</td>
                <td class="text-right">
                  <q-btn flat dense no-caps size="sm" color="negative" label="Drop" :disable="dropping" @click="dropRun(run)" />
                </td>
              </tr>
            </template>
          </q-virtual-scroll>
        </template>

        <template v-if="scratch.length">
          <div class="text-subtitle2 q-mt-md q-mb-xs">Schema check leftovers ({{ scratch.length }})</div>
          <q-markup-table dense flat bordered separator="horizontal">
            <tbody>
              <tr v-for="table in scratch" :key="table.table">
                <td>{{ table.table }}</td>
                <td class="text-grey-8">created {{ toDateTimeString(table.created) }}</td>
                <td class="text-right text-grey-8">{{ formatNumber(table.mb, 1) }} MB</td>
                <td class="text-right" style="width: 80px">
                  <q-btn flat dense no-caps size="sm" color="negative" label="Drop" :disable="dropping" @click="dropScratch(table)" />
                </td>
              </tr>
            </tbody>
          </q-markup-table>
        </template>

        <template v-if="unknown.length">
          <div class="text-subtitle2 q-mt-md">Not recognized ({{ unknown.length }})</div>
          <div class="text-grey-7 q-mb-xs">Named like temporary tables, but not ones Rapo creates, so they are never dropped here. Check and drop them manually.</div>
          <q-markup-table dense flat bordered separator="horizontal">
            <tbody>
              <tr v-for="table in unknown" :key="table.table">
                <td>{{ table.table }}</td>
                <td class="text-grey-8">{{ table.type }}</td>
                <td class="text-grey-8">created {{ toDateTimeString(table.created) }}</td>
                <td class="text-right text-grey-8">{{ formatNumber(table.mb, 1) }} MB</td>
                <td class="text-right" style="width: 80px">
                  <q-btn flat dense round size="sm" color="grey-7" icon="fas fa-copy" aria-label="Copy name" @click="copyName(table)">
                    <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 5]">Copy name</q-tooltip>
                  </q-btn>
                </td>
              </tr>
            </tbody>
          </q-markup-table>
        </template>
      </q-card-section>

      <q-separator />
      <q-card-actions align="right">
        <q-checkbox v-if="debugRuns.length" v-model="includeDebug" dense :label="`Include debug runs (${debugRuns.length})`" class="q-mr-md" />
        <q-btn v-if="allTargets.count" label="Drop all" color="negative" outline :loading="dropping" @click="dropAll" />
        <q-btn label="Close" flat color="primary" v-close-popup />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script>
import { api, notifyError } from "../api";
import { runStatus } from "../constants";
import { copyAndNotify } from "../runActions";
import { escapeHtml, formatNumber, round, toDateTimeString } from "../utils/format";

// Open with this.$refs.<ref>.open(). `tables` is the answer of get-temp-tables. The server re-checks every drop
// (only temporary tables it recognizes, never those of a run in progress). After a drop it emits "changed".
export default {
  name: "TempTablesDialog",
  props: {
    tables: { type: Object, default: () => ({}) },
  },
  emits: ["changed"],
  data() {
    return { visible: false, includeDebug: false, dropping: false };
  },
  computed: {
    runs() {
      return this.tables.runs || [];
    },
    scratch() {
      return this.tables.scratch || [];
    },
    unknown() {
      return this.tables.unknown || [];
    },
    debugRuns() {
      return this.runs.filter((run) => run.debug);
    },
    // What Drop all drops: every listed run (debug runs only when ticked) and every schema check leftover.
    allTargets() {
      const runs = this.runs.filter((run) => this.includeDebug || !run.debug);
      const tables = runs.reduce((sum, run) => sum + run.tables.length, 0) + this.scratch.length;
      const mb = [...runs, ...this.scratch].reduce((sum, item) => sum + item.mb, 0);
      return { runs, count: tables, mb };
    },
  },
  methods: {
    runStatus,
    formatNumber,
    toDateTimeString,
    open() {
      this.visible = true;
    },
    copyName(table) {
      copyAndNotify(table.table, "Table name", "Copying the table name failed.");
    },
    dropRun(run) {
      const control = run.control_name ? ` of ${run.control_name}` : "";
      const debug = run.debug ? "<div class='q-mt-sm'>The run was started in debug mode, so they were kept on purpose.</div>" : "";
      this.confirmDrop(
        `<div>${escapeHtml(`${run.tables.length} temporary table(s) of run ${run.process_id}${control}, ${formatNumber(run.mb, 1)} MB.`)}</div>${debug}`,
        { process_ids: [run.process_id], tables: [] },
      );
    },
    dropScratch(table) {
      this.confirmDrop(`<div>${escapeHtml(`${table.table}, the scratch table of a schema check that did not finish.`)}</div>`, { process_ids: [], tables: [table.table] });
    },
    dropAll() {
      const { runs, count, mb } = this.allTargets;
      const scratch = this.scratch.length ? `, ${this.scratch.length} schema check leftover(s)` : "";
      const debug = this.debugRuns.length && !this.includeDebug ? "<div class='q-mt-sm'>Debug runs are kept.</div>" : "";
      this.confirmDrop(`<div>${escapeHtml(`${count} temporary table(s) of ${runs.length} run(s)${scratch}, ${formatNumber(round(mb, 1), 1)} MB.`)}</div>${debug}`, {
        process_ids: runs.map((run) => run.process_id),
        tables: this.scratch.map((table) => table.table),
      });
    },
    confirmDrop(message, body) {
      this.$q
        .dialog({
          title: "Drop temporary tables?",
          message,
          html: true,
          ok: { label: "Drop", color: "negative" },
          cancel: { label: "Cancel", flat: true },
          persistent: true,
        })
        .onOk(() => this.drop(body));
    },
    async drop(body) {
      this.dropping = true;
      try {
        const result = await api("drop-temp-tables", { method: "POST", body });
        this.report(result);
      } catch (error) {
        notifyError("Dropping temporary tables failed.", error);
      } finally {
        this.dropping = false;
        this.$emit("changed");
      }
    },
    // Dropped, skipped (a run started meanwhile, or already cleaned) and failed tables, each said once.
    report({ dropped, skipped, failed }) {
      if (dropped.length) {
        this.$q.notify({ type: "positive", message: `${dropped.length} temporary table(s) dropped.` });
      }
      if (skipped.length) {
        const reasons = skipped.map((item) => `${item.process_id || item.table}: ${item.reason}`);
        this.$q.notify({ type: "warning", message: `${skipped.length} run(s) skipped.`, caption: reasons.slice(0, 5).join("; ") });
      }
      if (failed.length) {
        const errors = failed.map((item) => `${item.table}: ${item.error}`);
        this.$q.notify({
          type: "negative",
          message: `${failed.length} temporary table(s) could not be dropped.`,
          caption: errors.slice(0, 3).join("; "),
          timeout: 0,
          actions: [{ label: "Close", color: "white" }],
        });
      }
    },
  },
};
</script>

<style lang="sass" scoped>
.temp-runs
  max-height: 50vh
</style>
