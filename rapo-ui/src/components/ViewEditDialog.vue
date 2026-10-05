<template>
  <q-dialog v-model="visible" persistent :maximized="maximized" @hide="reset">
    <q-card class="column no-wrap view-edit" :style="maximized ? '' : 'width: 1200px; max-width: 95vw; height: 90vh'">
      <q-card-section class="row items-center q-py-sm no-wrap">
        <q-icon name="fas fa-eye" size="sm" class="q-mr-sm text-blue-grey-7" />
        <div class="text-h6 ellipsis">View {{ (name || "").toUpperCase() }}</div>
        <q-badge v-if="view" class="q-ml-sm" :color="view.status === 'VALID' ? 'positive' : 'negative'" :title="'Status of the view in the database'">
          {{ view.status }}
        </q-badge>
        <div v-if="view && view.last_ddl_time" class="q-ml-md text-caption text-grey-7" title="Last DDL change of the view (database clock)">
          changed {{ formatTime(view.last_ddl_time) }}
        </div>
        <q-space />
        <q-btn flat round :icon="maximized ? 'fas fa-compress' : 'fas fa-expand'" :aria-label="maximized ? 'Restore' : 'Maximize'" @click="maximized = !maximized">
          <q-tooltip>{{ maximized ? "Restore" : "Maximize" }}</q-tooltip>
        </q-btn>
        <q-btn aria-label="Close" flat round icon="fas fa-times" @click="close" />
      </q-card-section>
      <q-separator />

      <q-card-section v-if="!view" class="col">
        <div v-if="loadError" class="text-negative">{{ loadError }}</div>
        <q-skeleton v-else type="rect" height="300px" />
      </q-card-section>

      <q-card-section v-else class="col column no-wrap q-gutter-y-sm view-edit__body">
        <div v-if="!view.editable" class="text-negative">{{ view.reason }}</div>
        <div v-if="otherControls.length || view.dependents.objects.length" class="row items-center q-gutter-xs text-caption">
          <q-icon name="fas fa-exclamation-triangle" color="orange-9" />
          <span class="text-orange-10">A change applies to everything reading this view:</span>
          <q-chip v-for="other in otherControls" :key="other" dense size="12px" icon="fas fa-cog" :title="'Control ' + other + ' reads this view'">{{ other }}</q-chip>
          <q-chip
            v-for="object in view.dependents.objects"
            :key="object.owner + '.' + object.name"
            dense
            size="12px"
            icon="fas fa-database"
            :title="object.type + ' depending on this view'">
            {{ object.owner }}.{{ object.name }}
          </q-chip>
        </div>
        <div v-if="view.aliases" class="text-caption text-blue-grey-8">
          The view names its columns in a list ({{ view.aliases.join(", ") }}), kept as it is: the query must return as many columns, in that order.
        </div>
        <div v-for="error in view.errors" :key="error.line + ':' + error.position" class="text-caption text-negative">
          Line {{ error.line }}, position {{ error.position }}: {{ error.text }}
        </div>

        <CodeBox ref="code" v-model="body" class="view-edit__code" :class="{ 'view-edit__code--split': preview }" label="Query (the text after AS)" :tables="completionTables" :readonly="!view.editable">
          <template #actions>
            <q-btn flat size="sm" label="Format" :disable="!view.editable || !body.trim()" :loading="formatting" @click="format">
              <q-tooltip>Format in rapo's style (Ctrl+Z undoes it)</q-tooltip>
            </q-btn>
            <q-btn flat size="sm" label="Revert" :disable="body === view.body" @click="body = view.body">
              <q-tooltip>Back to the query as it was opened</q-tooltip>
            </q-btn>
          </template>
        </CodeBox>

        <div v-if="check" class="text-caption">
          <div v-if="!check.valid" class="text-negative check-error">{{ check.error }}</div>
          <div v-else class="row items-center q-gutter-xs">
            <span class="text-positive">Valid, {{ check.columns.length }} column(s).</span>
            <span v-if="!diffCount" class="text-grey-7">Same columns as now.</span>
            <q-badge v-for="column in check.diff.added" :key="'a' + column" outline color="positive" :title="'New column'">+ {{ column }}</q-badge>
            <q-badge v-for="column in check.diff.removed" :key="'r' + column" outline color="negative" :title="'Column no longer returned'">− {{ column }}</q-badge>
            <q-badge v-for="column in check.diff.retyped" :key="'t' + column.column_name" outline color="orange-9" :title="'Type changes from ' + column.old + ' to ' + column.new">
              {{ column.column_name }} {{ column.old }} → {{ column.new }}
            </q-badge>
          </div>
        </div>

        <div class="row items-center q-gutter-sm">
          <q-btn outline color="primary" label="Check" icon="fas fa-check" :disable="!view.editable || !body.trim()" :loading="checking" @click="runCheck" />
          <q-btn outline color="primary" label="Preview" icon="fas fa-table" :disable="!body.trim()" :loading="previewing" @click="runPreview" />
          <q-input v-model.number="rows" dense outlined type="number" min="1" :max="maxRows" style="width: 110px" label="Rows" />
          <q-space />
          <div v-if="!compileReady && view.editable" class="text-caption text-grey-7">Check the query to compile it.</div>
          <q-btn unelevated color="primary" label="Compile" icon="fas fa-cogs" :disable="!compileReady" :loading="compiling" @click="confirmCompile">
            <q-tooltip>Replace the view in the database with this query</q-tooltip>
          </q-btn>
        </div>

        <div v-if="preview" class="column no-wrap view-edit__preview">
          <div class="text-caption text-grey-7 q-mb-xs">
            {{ preview.rows.length }} row(s){{ preview.more ? ` (the first ${preview.limit})` : "" }} in {{ preview.elapsed }} ms
          </div>
          <q-virtual-scroll
            type="table"
            dense
            class="list-table col"
            :items="preview.rows"
            :virtual-scroll-item-size="28"
            :virtual-scroll-sticky-size-start="28"
            :table-colspan="preview.columns.length">
            <template #before>
              <thead>
                <tr>
                  <th v-for="column in preview.columns" :key="column.name" :class="isNumber(column) ? 'text-right' : 'text-left'" :title="column.name + ': ' + column.type">
                    {{ column.name }}
                  </th>
                </tr>
              </thead>
            </template>
            <template #default="{ item, index }">
              <tr :key="index">
                <td v-for="(value, position) in item" :key="position" :class="isNumber(preview.columns[position]) ? 'text-right number-cell' : ''">
                  <span v-if="value === null" class="text-grey-5">null</span>
                  <template v-else>{{ display(value) }}</template>
                </td>
              </tr>
            </template>
          </q-virtual-scroll>
        </div>
      </q-card-section>
    </q-card>
  </q-dialog>
</template>

<script>
import { api, notifyError } from "../api";
import { escapeHtml, toDateTimeString } from "../utils/format";
import CodeBox from "./CodeBox.vue";

// Table names a query reads: after FROM or JOIN, OWNER.NAME or NAME, quoted or not.
const TABLE_NAME = /\b(?:from|join)\s+((?:"[^"]+"|[A-Za-z][\w$#]*)(?:\.(?:"[^"]+"|[A-Za-z][\w$#]*))?)/gi;
const NUMBER_TYPES = ["NUMBER", "BINARY_FLOAT", "BINARY_DOUBLE", "BINARY_INTEGER"];

// Edits the query of a view datasource (open(name)). Check creates it under a scratch name, Preview runs the edited
// query read only, Compile replaces the view, only after a passing Check of the same text, and emits "compiled".
export default {
  components: { CodeBox },
  props: {
    // The control whose editor opened it: named in the server log, left out of "everything reading this view".
    controlName: String,
  },
  emits: ["compiled"],
  data() {
    return {
      visible: false,
      maximized: false,
      name: null,
      view: null,
      loadError: null,
      body: "",
      check: null,
      checkedBody: null,
      checking: false,
      formatting: false,
      previewing: false,
      preview: null,
      rows: 10,
      compiling: false,
      // Columns of the tables named in the query, fetched while typing: {name: [column]}.
      typedTables: {},
    };
  },
  computed: {
    maxRows() {
      return (this.$store.getters.getEnvInfo || {}).view_preview_max_rows || 1000;
    },
    otherControls() {
      const own = (this.controlName || "").toUpperCase();
      return this.view ? this.view.dependents.controls.filter((name) => name.toUpperCase() !== own) : [];
    },
    completionTables() {
      return { ...(this.view ? this.view.dependencies : {}), ...this.typedTables };
    },
    compileReady() {
      return Boolean(this.view && this.view.editable && this.check && this.check.valid && this.checkedBody === this.body);
    },
    diffCount() {
      const diff = this.check && this.check.diff;
      return diff ? diff.added.length + diff.removed.length + diff.retyped.length : 0;
    },
  },
  watch: {
    // A check describes the text it was run on; columns of newly named tables are fetched after a pause.
    body() {
      if (this.check && this.checkedBody !== this.body) {
        this.check = null;
      }
      clearTimeout(this.tablesTimer);
      this.tablesTimer = setTimeout(this.fetchTypedTables, 700);
    },
  },
  beforeUnmount() {
    clearTimeout(this.tablesTimer);
  },
  methods: {
    async open(name) {
      this.reset();
      this.name = name;
      this.visible = true;
      await this.load();
    },
    async load() {
      this.loadError = null;
      try {
        const view = await api("get-view", { params: { name: this.name } });
        this.view = view;
        this.body = view.body;
        this.check = null;
        this.checkedBody = null;
      } catch (error) {
        this.loadError = error.message;
      }
    },
    reset() {
      clearTimeout(this.tablesTimer);
      Object.assign(this.$data, { ...this.$options.data.call(this), maximized: this.maximized });
      this.requestedTables = new Set();
    },
    close() {
      if (!this.view || this.body === this.view.body) {
        this.visible = false;
        return;
      }
      this.$q
        .dialog({
          title: "Discard the changes?",
          message: "The edited query was not compiled and will be lost.",
          ok: { label: "Discard", color: "negative", flat: true },
          cancel: { label: "Keep editing", flat: true },
        })
        .onOk(() => (this.visible = false));
    },
    async format() {
      this.formatting = true;
      try {
        const { body } = await api("format-view", { method: "POST", body: { body: this.body } });
        const view = this.$refs.code && this.$refs.code.view;
        if (view) {
          // Through the editor, so Ctrl+Z brings the text back.
          view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: body } });
        } else {
          this.body = body;
        }
      } catch (error) {
        notifyError("Query was not formatted.", error);
      } finally {
        this.formatting = false;
      }
    },
    async runCheck() {
      const body = this.body;
      this.checking = true;
      try {
        const check = await api("check-view", { method: "POST", body: { name: this.view.name, body } });
        if (body === this.body) {
          this.check = check;
          this.checkedBody = body;
          if (!check.valid && check.error_offset != null) {
            this.moveCursor(check.error_offset);
          }
        }
      } catch (error) {
        notifyError("Query was not checked.", error);
      } finally {
        this.checking = false;
      }
    },
    // The server checks the query without its leading white space.
    moveCursor(offset) {
      const view = this.$refs.code && this.$refs.code.view;
      if (!view) return;
      const lead = this.body.length - this.body.trimStart().length;
      const anchor = Math.min(lead + offset, view.state.doc.length);
      view.dispatch({ selection: { anchor }, scrollIntoView: true });
      view.focus();
    },
    async runPreview() {
      this.previewing = true;
      const rows = Math.max(1, Math.min(Number(this.rows) || 10, this.maxRows));
      this.rows = rows;
      try {
        this.preview = await api("preview-view", { method: "POST", body: { body: this.body, rows } });
      } catch (error) {
        this.preview = null;
        notifyError("Preview failed.", error);
      } finally {
        this.previewing = false;
      }
    },
    confirmCompile() {
      const diff = this.check.diff;
      const lines = [];
      if (diff.removed.length) {
        lines.push(`Columns no longer returned: <b>${escapeHtml(diff.removed.join(", "))}</b>`);
      }
      if (diff.retyped.length) {
        lines.push(`Columns changing type: <b>${escapeHtml(diff.retyped.map((column) => `${column.column_name} ${column.old} → ${column.new}`).join(", "))}</b>`);
      }
      if (this.otherControls.length) {
        lines.push(`Other controls reading it: <b>${escapeHtml(this.otherControls.join(", "))}</b>`);
      }
      if (this.view.dependents.objects.length) {
        lines.push(`Database objects depending on it: <b>${escapeHtml(this.view.dependents.objects.map((object) => `${object.owner}.${object.name}`).join(", "))}</b>`);
      }
      lines.push("The previous DDL is written to the server log only.");
      this.$q
        .dialog({
          title: `Replace view ${this.view.name}?`,
          message: lines.map((line) => `<div class="q-mb-xs">${line}</div>`).join(""),
          html: true,
          ok: { label: "Compile", color: "primary", unelevated: true },
          cancel: { label: "Cancel", flat: true },
        })
        .onOk(() => this.compile(false));
    },
    async compile(force) {
      this.compiling = true;
      try {
        const result = await api("compile-view", {
          method: "POST",
          body: { name: this.view.name, body: this.body, expected_ddl_time: this.view.last_ddl_time, force, control_name: this.controlName || null },
        });
        this.$q.notify({ type: "positive", message: `View ${result.name} was replaced.` });
        this.$emit("compiled", { name: result.name, columns: result.columns, diff: result.diff });
        this.view = result;
        this.visible = false;
      } catch (error) {
        if (error.status === 409) {
          this.resolveConflict(error.message);
        } else {
          notifyError("View was not replaced.", error);
        }
      } finally {
        this.compiling = false;
      }
    },
    resolveConflict(message) {
      this.$q
        .dialog({
          title: "The view was changed meanwhile",
          message: `${message} Reload its current query (your edits are lost) or overwrite it with yours?`,
          ok: { label: "Overwrite", color: "negative", flat: true },
          cancel: { label: "Reload", flat: true },
          persistent: true,
        })
        .onOk(() => this.compile(true))
        .onCancel(() => this.load());
    },
    // Columns of tables named in the query that the view did not read yet, each name asked once.
    async fetchTypedTables() {
      if (!this.view) return;
      const known = new Set(Object.keys(this.completionTables).map((name) => name.toLowerCase()));
      const names = [...new Set([...this.body.matchAll(TABLE_NAME)].map((match) => match[1]))].filter(
        (name) => !known.has(name.toLowerCase()) && !this.requestedTables.has(name.toLowerCase()),
      );
      if (!names.length) return;
      names.forEach((name) => this.requestedTables.add(name.toLowerCase()));
      try {
        const found = await api("get-object-columns", { params: { names: names.join(",") }, loadingBar: false });
        const tables = {};
        for (const [name, columns] of Object.entries(found)) {
          // As the dictionary names it: upper case, a quoted part as written.
          tables[name.replace(/"[^"]*"|[^".]+/g, (part) => (part.startsWith('"') ? part : part.toUpperCase()))] = columns;
        }
        this.typedTables = { ...this.typedTables, ...tables };
      } catch (error) {
        names.forEach((name) => this.requestedTables.delete(name.toLowerCase()));
      }
    },
    isNumber(column) {
      return Boolean(column) && NUMBER_TYPES.includes(column.type);
    },
    display(value) {
      return typeof value === "string" && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$/.test(value) ? value.replace("T", " ").replace(/ 00:00:00$/, "") : value;
    },
    formatTime(value) {
      return toDateTimeString(value);
    },
  },
};
</script>

<style lang="sass" scoped>
.view-edit__body
  min-height: 0
// The query fills the dialog; once a preview is shown, it takes 2/3 of the space and the preview 1/3. CodeMirror's
// own wrapper is display: contents, so .cm-editor is a flex item of the box.
.view-edit__code
  display: flex
  flex-direction: column
  flex: 1 1 0
  min-height: 0
.view-edit__code--split
  flex-grow: 2
.view-edit__code :deep(.cm-editor)
  flex: 1 1 0
  min-height: 0
  max-height: none
.view-edit__preview
  flex: 1 1 0
  min-height: 0
.check-error
  white-space: pre-wrap
</style>
