<template>
  <div>
    <span class="row items-center justify-between">
      <label>{{ label }}</label>
      <div class="row items-center no-wrap">
        <slot name="actions"></slot>
        <q-btn v-if="check && !readonly" flat size="sm" label="Check" :disable="!code || !code.trim()" :loading="checking" @click="runCheck" />
        <q-btn v-if="code && !readonly" flat size="xs" icon="fas fa-times" @click="clearCode">
          <q-tooltip>Clear text</q-tooltip>
        </q-btn>
        <q-btn v-if="!readonly && hasExamples" flat size="sm" label="Example" icon-right="fas fa-caret-down">
          <q-menu>
            <q-list dense class="code-examples">
              <q-item v-for="example in examples.items" :key="example.title" clickable v-close-popup @click="pickExample(example)">
                <q-item-section>
                  <q-item-label>{{ example.title }}</q-item-label>
                  <q-item-label caption>{{ example.caption }}</q-item-label>
                </q-item-section>
              </q-item>
              <template v-if="examples.more && examples.more.length">
                <q-separator />
                <q-item clickable>
                  <q-item-section>More</q-item-section>
                  <q-item-section side><q-icon name="fas fa-caret-right" size="xs" /></q-item-section>
                  <q-menu anchor="top end" self="top start">
                    <q-list dense class="code-examples">
                      <template v-for="group in examples.more" :key="group.group">
                        <q-item-label header class="q-py-xs">{{ group.group }}</q-item-label>
                        <q-item v-for="example in group.items" :key="group.group + example.title" clickable v-close-popup @click="pickExample(example)">
                          <q-item-section>
                            <q-item-label>{{ example.title }}</q-item-label>
                            <q-item-label caption>{{ example.caption }}</q-item-label>
                          </q-item-section>
                        </q-item>
                      </template>
                    </q-list>
                  </q-menu>
                </q-item>
              </template>
            </q-list>
          </q-menu>
        </q-btn>
      </div>
    </span>
    <codemirror
      ref="editor"
      class="cm-wrapper"
      :class="{ 'cm-readonly': readonly }"
      v-model="code"
      :indent-with-tab="true"
      :smart-indent="true"
      :tab-size="4"
      :extensions="extensions"
      @ready="onReady" />
    <div v-if="variableList.length && !readonly" class="row items-center q-gutter-xs q-mt-xs text-caption text-grey-7">
      <span>Variables:</span>
      <span v-for="variable in variableList" :key="variable.name" class="code-variable" @mousedown.prevent @click="insertText(variable.token)">
        {{ variable.token }}
        <q-tooltip v-if="variable.label">{{ variable.label }} — click to insert</q-tooltip>
      </span>
    </div>
    <div v-if="checkResult" class="text-caption q-mt-xs check-result" :class="checkResult.color">
      {{ checkResult.message }}
      <div v-if="checkResult.thresholds" class="text-grey-8">Dashboard thresholds: {{ checkResult.thresholds }}</div>
    </div>
  </div>
</template>

<script>
import { Codemirror } from "vue-codemirror";
import { EditorState } from "@codemirror/state";
import { sql, PLSQL } from "@codemirror/lang-sql";
import { notifyError } from "../api";
import { escapeHtml } from "../utils/format";

// One line for the answer of a check: the error, the warning, or what the statement returns.
function describeCheck(result) {
  const thresholds = (result.thresholds || [])
    .filter((item) => item.condition && item.alarm)
    .map((item) => `${item.condition} → ${item.alarm}`)
    .join(", ");
  if (!result.valid) return { color: "text-negative", message: result.error };
  if (result.warning) return { color: "text-warning", message: result.warning, thresholds };
  const columns = result.columns || [];
  let message = "OK — compiles";
  if (result.message) message = result.message;
  else if (columns.length === 1) message = `OK — 1 column, ${columns[0].type}`;
  else if (columns.length > 1) message = `OK — ${columns.length} columns`;
  return { color: "text-positive", message, thresholds };
}

// A completion source for the fixed set of Oracle bind variables a statement is run with (e.g. RACS_KPI_PKG's
// :v_processid). It only activates right after a ":", independently of the schema/keyword sources sql() adds.
function bindCompletionSource(binds) {
  return (context) => {
    const match = context.matchBefore(/:\w*/);
    if (!match) return null;
    return {
      from: match.from,
      options: binds.map((name) => ({ label: ":" + name, type: "variable" })),
      validFor: /^:\w*$/,
    };
  };
}

// The fixed set of {control_name}-style variables Parser.parse_variables() substitutes into Preparation SQL,
// Prerequisite SQL and Completion SQL before they run (rapo/core/control.py). Date ones show a sample strftime
// format, since the substitution is meaningless without one; %Y-%m-%d matches the format used in the box's own
// "Insert log line" example. boost puts them ahead of unrelated keyword/property matches for the same prefix.
const TEMPLATE_VARIABLES = [
  { name: "control_name", label: "Control name" },
  { name: "process_id", label: "Process ID" },
  { name: "control_date", format: "%Y-%m-%d", label: "Run date" },
  { name: "control_date_from", format: "%Y-%m-%d", label: "Run from" },
  { name: "control_date_to", format: "%Y-%m-%d", label: "Run to" },
];

function variableToken({ name, format }) {
  return `{${name}${format ? ":" + format : ""}}`;
}

// Inserts a token over the typed "{name", swallowing the "}" that bracket closing added after the cursor.
function applyToken(token) {
  return (view, completion, from, to) => {
    const end = view.state.sliceDoc(to, to + 1) === "}" ? to + 1 : to;
    view.dispatch({ changes: { from, to: end, insert: token }, selection: { anchor: from + token.length } });
  };
}

// A completion source for those variables. It only activates right after a "{", and inserts the full
// {name} or {name:format} token in one go, closing brace included.
function templateVariableCompletionSource(variables) {
  return (context) => {
    const match = context.matchBefore(/\{\w*/);
    if (!match) return null;
    return {
      from: match.from,
      options: variables.map((variable) => ({
        label: variableToken(variable),
        detail: variable.label,
        type: "variable",
        boost: 99,
        apply: applyToken(variableToken(variable)),
      })),
      validFor: /^\{\w*$/,
    };
  };
}

export default {
  props: {
    modelValue: String,
    label: String,
    readonly: Boolean,
    columns: Array,
    tables: Object,
    binds: Array,
    // true: the engine's TEMPLATE_VARIABLES. An array of {name, format, label} replaces them. Either way they are
    // completed after "{" and listed under the box, each token inserted at the cursor on a click.
    templateVars: [Boolean, Array],
    // {items, more} from utils/codeExamples.js examplesFor().
    examples: Object,
    // An async function(text) answering validate-sql / validate-kpi-sql; shows the Check button.
    check: Function,
  },
  emits: ["update:modelValue"],
  components: {
    Codemirror,
  },
  data() {
    return {
      checking: false,
      checkResult: null,
    };
  },
  computed: {
    extensions() {
      const config = { dialect: PLSQL };
      const tableNames = this.tables && Object.keys(this.tables);
      if (tableNames && tableNames.length) {
        // Real table names (e.g. a control's own RAPO_REST_/RAPO_RESA_/RAPO_RESB_ table): they're valid bare
        // schema keys, so they're offered as completions themselves, and typing one then "." completes its
        // own columns.
        config.schema = this.tables;
        if (tableNames.length === 1) {
          // A single table also becomes the default, so its columns complete unqualified too.
          config.defaultTable = tableNames[0];
        } else {
          // Several tables (REC's two sides): CodeMirror's defaultTable only takes one name, and typing
          // table.column for everything is unwieldy, so every table's columns are also offered unqualified,
          // deduplicated across tables, on top of the qualified per-table completions above.
          const merged = [...new Set(tableNames.flatMap((name) => this.tables[name]))];
          config.tables = merged.map((column) => ({ label: column, type: "property" }));
        }
      } else if (this.columns && this.columns.length) {
        // Filters are unqualified WHERE-clause fragments, not queries against a named table, and real
        // datasource names (schema-qualified, @dblink) aren't valid bare schema keys, so columns are offered
        // directly via CodeMirror's own flat "tables" completions list rather than a schema table. `schema`
        // still needs to be set (even empty) for schema-based completion to run at all.
        config.schema = {};
        config.tables = this.columns.map((column) => ({ label: column, type: "property" }));
      }
      const extensions = [sql(config), EditorState.readOnly.of(Boolean(this.readonly))];
      if (this.binds && this.binds.length) {
        extensions.push(PLSQL.language.data.of({ autocomplete: bindCompletionSource(this.binds) }));
      }
      if (this.templateVariables.length) {
        extensions.push(PLSQL.language.data.of({ autocomplete: templateVariableCompletionSource(this.templateVariables) }));
      }
      return extensions;
    },
    code: {
      get() {
        return this.modelValue;
      },
      set(value) {
        this.$emit("update:modelValue", value);
      },
    },
    templateVariables() {
      if (Array.isArray(this.templateVars)) return this.templateVars;
      return this.templateVars ? TEMPLATE_VARIABLES : [];
    },
    variableList() {
      return this.templateVariables.map((variable) => ({ ...variable, token: variableToken(variable) }));
    },
    hasExamples() {
      return Boolean(this.examples && (this.examples.items.length || (this.examples.more || []).length));
    },
  },
  watch: {
    // A result describes the text it was run on.
    modelValue() {
      this.checkResult = null;
    },
  },
  methods: {
    onReady({ view }) {
      this.view = view;
    },
    // Replaces the selection with the text. An editor never focused has its cursor at 0, so the text is appended.
    insertText(text) {
      const view = this.view;
      if (!view) {
        this.code = (this.code || "") + text;
        return;
      }
      const end = view.state.doc.length;
      const selection = view.state.selection.main;
      const { from, to } = view.hasFocus || selection.from > 0 ? selection : { from: end, to: end };
      view.dispatch({ changes: { from, to, insert: text }, selection: { anchor: from + text.length }, scrollIntoView: true });
      view.focus();
    },
    // An example replaces the whole text, so a text of one's own is replaced only after a confirmation.
    pickExample(example) {
      if (!this.code || !this.code.trim() || this.code === example.text) {
        this.code = example.text;
        return;
      }
      this.$q
        .dialog({
          title: `Replace with "${example.title}"?`,
          message: `The current text will be replaced by:<pre class="code-example-preview">${escapeHtml(example.text)}</pre>`,
          html: true,
          ok: { label: "Replace" },
          cancel: { label: "Cancel", flat: true },
        })
        .onOk(() => {
          this.code = example.text;
        });
    },
    clearCode() {
      this.code = "";
    },
    // check() parses the text on the server without running it and answers {valid, error, warning, columns,
    // thresholds}. The result is informative only and never blocks saving.
    async runCheck() {
      this.checking = true;
      try {
        this.checkResult = describeCheck(await this.check(this.code));
      } catch (error) {
        notifyError("Statement was not checked.", error);
      } finally {
        this.checking = false;
      }
    },
  },
};
</script>

<style>
.cm-editor {
  min-height: 56px;
  max-height: 20em;
  border: 1px solid #bbb;
  border-radius: 0.25em;
  outline: none;
}

.cm-gutters {
  min-height: 56px !important; /* Matches the min-height of .cm-editor */
  border-right: 1px solid #bbb;
  box-sizing: border-box; /* Ensures padding and borders are included in the height calculation */
}

.cm-editor:hover {
  border: 1px solid #666;
}

.cm-editor.cm-focused {
  border: 1px solid #027be3;
  outline: 1px solid #027be3;
}

.cm-activeLine {
  background: transparent !important;
}

.cm-focused .cm-activeLine {
  background: rgba(100, 100, 100, 0.1) !important;
}

.cm-activeLineGutter {
  background: transparent !important;
}

.code-examples {
  max-width: 460px;
}

.code-variable {
  font-family: monospace;
  padding: 0 4px;
  border-radius: 3px;
  background: #eceff1;
  cursor: pointer;
}

.code-variable:hover {
  background: #cfd8dc;
  color: #263238;
}

.check-result {
  white-space: pre-line;
}

.code-example-preview {
  max-height: 16em;
  overflow: auto;
  padding: 8px;
  background: #f5f5f5;
  border-radius: 4px;
  font-size: 12px;
}

/* A read-only editor shows a value that is not the user's to edit, e.g. a KPI type's default statement. */
.cm-readonly .cm-editor {
  background: #f5f5f5;
  color: #757575;
}

.cm-readonly .cm-editor:hover {
  border: 1px solid #bbb;
}

.cm-readonly .cm-cursor {
  display: none !important;
}

.cm-focused .cm-activeLineGutter {
  background: rgba(100, 100, 100, 0.1) !important;
}

/* Table-name completions (CodeMirror's SQL schema completion gives them type "type") get the same "database"
   icon used elsewhere in the app for a datasource, instead of the library's default italic "t". */
.cm-completionIcon-type::after {
  content: "\f1c0";
  font-family: "Font Awesome 5 Free";
  font-weight: 900;
}

/* Bind-variable completions (registered with type "variable", see bindCompletionSource) get a dollar-sign
   icon, instead of the library's default italic "x", to set them apart from columns and table names. */
.cm-completionIcon-variable::after {
  content: "\f155";
  font-family: "Font Awesome 5 Free";
  font-weight: 900;
}
</style>
