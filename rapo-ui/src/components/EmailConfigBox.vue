<template>
  <div class="q-gutter-y-md">
    <q-card class="q-pa-sm" flat bordered>
      <q-item-section class="q-ma-xs">
        <q-item-label>Delivery</q-item-label>
      </q-item-section>
      <q-card-section class="q-gutter-y-md">
        <div class="row q-gutter-md items-center">
          <q-select class="col" outlined emit-value map-options v-model="email.send_when" :options="sendWhenOptions" label="Send when">
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
              'Done, with results': only runs that end Done and have rows in the files' result sheets (after their filters).<br />
              'Done, always': every run that ends Done, empty files left out with a note.<br />
              'Done or error': as 'Done, always', plus runs that end in Error, with the error and no file.<br />
              'Evaluate SQL': only when the Evaluate SQL returns a number above 0, whatever the run status or result rows.
            </q-tooltip>
          </q-select>
          <q-input
            class="col"
            outlined
            type="number"
            :min="1"
            :step="1"
            :model-value="email.max_records"
            @update:model-value="(value) => (email.max_records = value === '' || value == null ? null : Number(value))"
            label="Max records per file"
            clearable>
            <template v-slot:prepend>
              <q-icon name="fas fa-list-ol" @click.stop.prevent />
            </template>
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
              A file with more rows is left out, with a note; the other files are still attached.<br />
              Empty = the instance limit ([EMAIL] max_attachment_rows in rapo.ini), which also caps this value.
            </q-tooltip>
          </q-input>
          <q-toggle class="col" v-model="email.include_summary" label="Append run summary">
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
              Adds the control, window, status, record counts and a line per file (rows, sheets, or why it is not attached) below the body.
            </q-tooltip>
          </q-toggle>
        </div>
        <div v-if="email.send_when === 'evaluate_sql'" class="email-evaluate" :class="{ 'email-evaluate--open': evaluateOpen }">
          <div class="email-evaluate__head row no-wrap items-center q-gutter-x-sm" @click="evaluateOpen = !evaluateOpen">
            <q-chip class="email-evaluate__kind" title="The email is sent only when this query returns a number above 0">
              <q-avatar icon="fas fa-calculator" color="deep-orange-6" text-color="white" />
              Evaluate SQL
            </q-chip>
            <div v-if="evaluateSummary" class="text-grey-7 text-mono ellipsis">{{ evaluateSummary }}</div>
            <div v-else class="text-grey-7">no query</div>
            <q-space />
            <q-icon v-if="!evaluateSummary" name="fas fa-exclamation-triangle" color="negative" size="14px" title="No query: the email is never sent" />
            <q-icon :name="evaluateOpen ? 'fas fa-chevron-up' : 'fas fa-chevron-down'" size="12px" color="grey-7" class="q-mr-sm" />
          </div>
          <div v-if="evaluateOpen" class="email-evaluate__body">
            <code-box label="Evaluate SQL" :template-vars="true" v-model="email.evaluate_sql" :tables="sqlTables" :examples="evaluateExamples" :check="evaluateChecker">
            </code-box>
            <div class="text-grey-7 text-caption">
              A query returning one number, run when the run ends Done or Error. The email is sent only when the number is above 0; 0, a negative number or a
              failed query sends nothing. Variables as in the Prerequisite SQL, e.g. <span class="text-mono">{process_id}</span>. Its value is
              <span class="text-mono">{evaluate_value}</span> in the subject, the body and the file names.
            </div>
          </div>
        </div>
      </q-card-section>
    </q-card>

    <q-card class="q-pa-sm" flat bordered>
      <q-item-section class="q-ma-xs">
        <q-item-label>Recipients</q-item-label>
      </q-item-section>
      <q-card-section class="q-gutter-y-md">
        <div class="row q-col-gutter-md">
          <q-select
            v-for="field in recipientFields"
            :key="field.key"
            :class="field.key === 'to' ? 'col-12' : 'col-12 col-md-6'"
            outlined
            :model-value="email[field.key]"
            @update:model-value="(value) => (email[field.key] = value)"
            :label="field.label"
            use-input
            use-chips
            multiple
            hide-dropdown-icon
            input-debounce="0"
            new-value-mode="add-unique"
            @new-value="(value, done) => addRecipients(field.key, value, done)">
            <template v-slot:prepend>
              <q-icon :name="field.icon" @click.stop.prevent />
            </template>
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
              Type an address and press Enter. Several addresses separated by ',' or ';' can be pasted at once.
            </q-tooltip>
          </q-select>
        </div>
      </q-card-section>
    </q-card>

    <q-card class="q-pa-sm" flat bordered>
      <q-item-section class="q-ma-xs">
        <q-item-label>Message</q-item-label>
      </q-item-section>
      <q-card-section class="q-gutter-y-md">
        <q-input ref="subject" outlined v-model="email.subject" label="Subject">
          <template v-slot:append>
            <email-variable-button :variables="variables" :input="() => $refs.subject" :text="email.subject" @update:text="(text) => (email.subject = text)" />
          </template>
        </q-input>
        <q-input ref="body" outlined v-model="email.body" label="Body" type="textarea" autogrow input-style="min-height: 120px">
          <template v-slot:append>
            <email-variable-button :variables="variables" :input="() => $refs.body" :text="email.body" @update:text="(text) => (email.body = text)" />
          </template>
        </q-input>
        <div class="text-grey-7 text-caption">
          Variables such as <span class="text-mono">{control_name}</span> or <span class="text-mono">{control_date_from:%Y-%m-%d}</span> are replaced in the
          subject, the body, the file names, the sheet filters and the Free SQL. An unknown one stays as it is.
        </div>
      </q-card-section>
    </q-card>

    <q-card class="q-pa-sm" flat bordered>
      <q-item-section class="q-ma-xs">
        <q-item-label>
          Attachments
          <span class="text-grey-7 q-ml-sm">{{ attachmentFacts }}</span>
        </q-item-label>
      </q-item-section>
      <q-card-section class="q-gutter-y-md">
        <div v-if="!email.files.length" :class="email.send_when === 'done_with_results' ? 'text-negative' : 'text-grey-7'" class="text-caption">
          {{
            email.send_when === "done_with_results"
              ? "No file: 'Done, with results' needs one to count the results in. Add a file (its Attach may be off), or choose another 'Send when'."
              : "No file: the email is sent without attachments."
          }}
        </div>

        <div
          v-for="(file, fileIndex) in email.files"
          :key="itemKey(file)"
          :ref="(element) => (fileElements[fileIndex] = element)"
          class="email-file"
          :class="{ 'email-file--over': overFile === fileIndex, 'email-file--dragging': draggingFile === fileIndex }"
          :draggable="fileHandleDown === fileIndex"
          @dragstart="(event) => onFileDragStart(event, fileIndex)"
          @dragend="onFileDragEnd"
          @dragover="(event) => onFileDragOver(event, fileIndex)"
          @dragleave="overFile = null"
          @drop="(event) => onFileDrop(event, fileIndex)">
          <div class="row no-wrap items-center q-gutter-x-sm">
            <q-icon
              name="fas fa-grip-vertical"
              size="11px"
              class="email-file__handle"
              title="Drag to move the file"
              @mousedown="fileHandleDown = fileIndex"
              @mouseup="fileHandleDown = null" />
            <q-input
              :ref="(component) => (fileInputs[fileIndex] = component)"
              class="col email-file__name"
              dense
              outlined
              :model-value="file.name"
              @update:model-value="(value) => (file.name = value && value.trim() ? value : null)"
              :label="'File ' + (fileIndex + 1)"
              :placeholder="defaultFileName(fileIndex)"
              stack-label
              :error="fileProblem(fileIndex) !== null"
              hide-bottom-space>
              <template v-slot:prepend>
                <q-icon name="fas fa-file-excel" size="16px" @click.stop.prevent />
              </template>
              <template v-slot:append>
                <email-variable-button
                  :variables="variables"
                  :input="() => fileInputs[fileIndex]"
                  :text="file.name"
                  @update:text="(text) => (file.name = text && text.trim() ? text : null)" />
              </template>
              <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
                Name of the Excel file, with variables, e.g. Losses_{control_date_from:%Y%m%d}. .xlsx is added when missing,<br />
                and \ / : * ? " &lt; &gt; | become _. Empty = {{ defaultFileName(fileIndex) }}.
              </q-tooltip>
            </q-input>
            <q-toggle v-model="file.attach" label="Attach">
              <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
                Off: the file is not attached, but its rows still count for 'Done, with results' and {attachment_rows}.
              </q-tooltip>
            </q-toggle>
            <q-btn flat round dense size="sm" icon="fas fa-ellipsis-v" color="grey-7" :aria-label="'File ' + (fileIndex + 1) + ' menu'">
              <q-menu anchor="bottom right" self="top right">
                <q-list dense style="min-width: 150px">
                  <q-item v-close-popup clickable :disable="fileIndex === 0" @click="moveFile(fileIndex, fileIndex - 1)">
                    <q-item-section avatar><q-icon name="fas fa-arrow-up" size="12px" /></q-item-section>
                    <q-item-section>Move up</q-item-section>
                  </q-item>
                  <q-item v-close-popup clickable :disable="fileIndex === email.files.length - 1" @click="moveFile(fileIndex, fileIndex + 1)">
                    <q-item-section avatar><q-icon name="fas fa-arrow-down" size="12px" /></q-item-section>
                    <q-item-section>Move down</q-item-section>
                  </q-item>
                  <q-item v-close-popup clickable @click="duplicateFile(fileIndex)">
                    <q-item-section avatar><q-icon name="fas fa-clone" size="12px" /></q-item-section>
                    <q-item-section>Duplicate</q-item-section>
                  </q-item>
                  <q-separator />
                  <q-item v-close-popup clickable @click="removeFile(fileIndex)">
                    <q-item-section avatar><q-icon name="fas fa-trash" size="12px" /></q-item-section>
                    <q-item-section>Remove</q-item-section>
                  </q-item>
                </q-list>
              </q-menu>
            </q-btn>
          </div>
          <div v-if="fileProblem(fileIndex)" class="text-negative text-caption q-mt-xs">{{ fileProblem(fileIndex) }}</div>
          <div v-else-if="!file.attach" class="text-grey-7 text-caption q-mt-xs">Not attached: its rows still count for 'Done, with results' and {attachment_rows}.</div>

          <div class="email-file__sheets">
            <email-sheet-row
              v-for="(sheet, sheetIndex) in file.sheets"
              :key="itemKey(sheet)"
              :ref="(component) => (sheetRows[itemKey(sheet)] = component)"
              :model-value="sheet"
              :file-index="fileIndex"
              :index="sheetIndex"
              :first="sheetIndex === 0"
              :last="sheetIndex === file.sheets.length - 1"
              :open="openKeys.includes(itemKey(sheet))"
              :file-targets="fileTargets(fileIndex)"
              :effective-name="sheetNames[fileIndex][sheetIndex]"
              :default-name="defaultNames[fileIndex][sheetIndex]"
              :problem="sheetProblem(fileIndex, sheetIndex)"
              :control-name="controlName"
              :control-type="controlType"
              :rule-config="ruleConfig"
              :tables="tableNames"
              :columns-by-side="columnsBySide"
              :sheet-variables="sheetVariables"
              :sql-tables="sqlTables"
              @toggle="toggleOpen(sheet)"
              @command="(command) => sheetCommand(fileIndex, sheetIndex, command)"
              @drop-sheet="({ from, to }) => moveSheet(from, to)" />
          </div>

          <q-btn-dropdown flat dense no-caps color="primary" icon="fas fa-plus" label="Sheet" class="q-mt-sm">
            <q-list dense style="min-width: 200px">
              <q-item v-for="option in sheetOptions" :key="option.label" v-close-popup clickable @click="addSheet(fileIndex, option)">
                <q-item-section avatar><q-icon :name="option.icon" :color="option.color" size="14px" /></q-item-section>
                <q-item-section>
                  <q-item-label>{{ option.label }}</q-item-label>
                  <q-item-label caption>{{ option.caption }}</q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </q-btn-dropdown>
        </div>

        <q-btn outline color="primary" no-caps icon="fas fa-plus" label="File" @click="addFile" />
      </q-card-section>
    </q-card>

    <q-card class="q-pa-sm" flat bordered>
      <q-item-section class="q-ma-xs">
        <q-item-label>Send a test</q-item-label>
      </q-item-section>
      <q-card-section>
        <div class="row items-start q-gutter-md">
          <q-input
            class="col-4"
            outlined
            dense
            v-model="testAddress"
            label="Send a test to"
            :disable="!canTest"
            :error="Boolean(testAddress) && !isEmailAddress(testAddress)"
            hide-bottom-space />
          <q-btn
            color="primary"
            outline
            icon="fas fa-paper-plane"
            label="Send test"
            :disable="!canTest || !isEmailAddress(testAddress)"
            :loading="testing"
            @click="sendTest" />
          <div class="col text-grey-7 text-caption q-pt-sm">
            {{
              canTest
                ? "Sends this configuration for the last finished run of the control, to this address only."
                : "Apply your changes first: the test uses the saved configuration and the last finished run."
            }}
          </div>
        </div>
      </q-card-section>
    </q-card>
  </div>
</template>

<script>
import { toRaw } from "vue";
import { api, notifyError } from "../api";
import CodeBox from "./CodeBox.vue";
import EmailSheetRow from "./EmailSheetRow.vue";
import EmailVariableButton from "./EmailVariableButton.vue";
import { examplesFor } from "../utils/codeExamples";
import {
  RESULT_META_COLUMNS,
  SEND_WHEN_OPTIONS,
  completeEmailConfig,
  defaultFileName,
  defaultResultSheet,
  defaultSheetNames,
  defaultSqlSheet,
  effectiveSheetNames,
  emailConfigProblem,
  emailDrag,
  emailVariables,
  isEmailAddress,
  sheetVariables,
} from "../utils/email";

// Stable keys of files and sheets, which have no id of their own, so that moving one keeps its row.
const keys = new WeakMap();
let lastKey = 0;

// rule_config.email of a control. modelValue is the parent's object and is edited in place.
export default {
  components: { CodeBox, EmailSheetRow, EmailVariableButton },
  props: {
    modelValue: { type: Object, required: true },
    controlName: String,
    controlType: String,
    // rule_config of a REC control, for the result types each side saves.
    ruleConfig: Object,
    // Source columns per side ({ main, a, b }), offered while the result table does not exist yet.
    sourceColumns: { type: Object, default: () => ({}) },
    // Whether the control is saved and the form unchanged since, so a test send uses what is shown.
    saved: Boolean,
    // A validation problem to show ({ file, sheet } of emailConfigProblem): opens the sheet and scrolls to it.
    reveal: Object,
  },
  data() {
    return {
      sendWhenOptions: SEND_WHEN_OPTIONS,
      recipientFields: [
        { key: "to", label: "To", icon: "fas fa-envelope" },
        { key: "cc", label: "CC", icon: "fas fa-copy" },
        { key: "bcc", label: "BCC", icon: "fas fa-user-secret" },
      ],
      // Columns of the existing result tables, by side.
      resultColumns: {},
      // Keys of the sheets whose editor is open.
      openKeys: [],
      // Whether the Evaluate SQL editor is open; a saved query starts folded.
      evaluateOpen: false,
      fileHandleDown: null,
      draggingFile: null,
      overFile: null,
      testAddress: "",
      testing: false,
    };
  },
  computed: {
    email() {
      return this.modelValue;
    },
    isRec() {
      return this.controlType === "REC";
    },
    variables() {
      return emailVariables(this.controlType, this.email.send_when);
    },
    // The variables of the filters and the Free SQL: listed under the box and completed after "{".
    sheetVariables() {
      return sheetVariables(this.controlType);
    },
    tableNames() {
      const name = (this.controlName || "<NAME>").toUpperCase();
      return this.isRec ? { a: "RAPO_RESA_" + name, b: "RAPO_RESB_" + name } : { main: "RAPO_REST_" + name };
    },
    columnsBySide() {
      const meta = RESULT_META_COLUMNS[this.isRec ? "rec" : "single"];
      return Object.fromEntries(
        Object.keys(this.tableNames).map((side) => {
          const existing = this.resultColumns[side];
          if (existing && existing.length) return [side, existing];
          return [side, [...new Set([...(this.sourceColumns[side] || []).map((column) => column.toUpperCase()), ...meta])]];
        }),
      );
    },
    // The control's result tables with their columns, so the Free SQL and the Evaluate SQL complete them.
    sqlTables() {
      if (!this.controlName) return {};
      return Object.fromEntries(Object.entries(this.tableNames).map(([side, table]) => [table, this.columnsBySide[side]]));
    },
    // The first line of the Evaluate SQL, shown while it is folded.
    evaluateSummary() {
      return (this.email.evaluate_sql || "").split("\n").map((line) => line.trim()).find(Boolean) || "";
    },
    evaluateExamples() {
      return examplesFor({ field: "evaluate_sql", controlType: this.controlType, controlName: this.controlName, side: "a" });
    },
    defaultNames() {
      return this.email.files.map((file) => defaultSheetNames(file.sheets, this.controlType, this.controlName, this.ruleConfig));
    },
    sheetNames() {
      return this.email.files.map((file) => effectiveSheetNames(file.sheets, this.controlType, this.controlName, this.ruleConfig));
    },
    // The first problem of the configuration, live, so its sheet or file shows it while it lasts.
    problem() {
      return emailConfigProblem(this.email, { controlType: this.controlType, controlName: this.controlName, ruleConfig: this.ruleConfig });
    },
    attachmentFacts() {
      const files = this.email.files.length;
      const sheets = this.email.files.reduce((total, file) => total + file.sheets.length, 0);
      if (!files) return "";
      return `${files} ${files === 1 ? "file" : "files"}, ${sheets} ${sheets === 1 ? "sheet" : "sheets"}`;
    },
    sheetOptions() {
      const sql = { label: "Free SQL", caption: "A query of your own", icon: "fas fa-code", color: "deep-purple-4", kind: "sql" };
      if (!this.isRec) {
        return [{ label: "Results", caption: this.tableNames.main, icon: "fas fa-table", color: "teal-7", kind: "result", side: "main" }, sql];
      }
      return [
        { label: "Side A results", caption: this.tableNames.a, icon: "fas fa-table", color: "teal-8", kind: "result", side: "a" },
        { label: "Side B results", caption: this.tableNames.b, icon: "fas fa-table", color: "indigo-6", kind: "result", side: "b" },
        sql,
      ];
    },
    canTest() {
      return this.saved && Boolean(this.controlName);
    },
  },
  watch: {
    modelValue: {
      immediate: true,
      handler(value) {
        completeEmailConfig(value, this.controlType);
        this.evaluateOpen = !this.evaluateSummary;
      },
    },
    // Choosing Evaluate SQL without a query opens its editor.
    "email.send_when"(value) {
      if (value === "evaluate_sql" && !this.evaluateSummary) this.evaluateOpen = true;
    },
    tableNames: {
      immediate: true,
      handler() {
        this.loadResultColumns();
      },
    },
    reveal: {
      immediate: true,
      handler(value) {
        if (value) this.$nextTick(() => this.revealProblem(value));
      },
    },
  },
  created() {
    // Element and component refs by index or key; not reactive.
    this.fileElements = [];
    this.fileInputs = [];
    this.sheetRows = {};
  },
  methods: {
    isEmailAddress,
    defaultFileName(index) {
      return defaultFileName(index, this.controlName);
    },
    itemKey(item) {
      const raw = toRaw(item);
      if (!keys.has(raw)) keys.set(raw, ++lastKey);
      return keys.get(raw);
    },
    fileProblem(fileIndex) {
      return this.problem && this.problem.file === fileIndex && this.problem.sheet === null ? this.problem.message : null;
    },
    sheetProblem(fileIndex, sheetIndex) {
      return this.problem && this.problem.file === fileIndex && this.problem.sheet === sheetIndex ? this.problem.message : null;
    },
    fileTargets(fileIndex) {
      return this.email.files.map((file, index) => ({ index, label: file.name || "File " + (index + 1) })).filter((target) => target.index !== fileIndex);
    },
    // Checked as a Prerequisite SQL: a select returning one number.
    evaluateChecker(statement) {
      return api("validate-sql", {
        method: "POST",
        loadingBar: false,
        body: { kind: "prerequisite", statement, control_name: this.controlName, control_type: this.controlType },
      });
    },
    async loadResultColumns() {
      if (!this.controlName) {
        this.resultColumns = {};
        return;
      }
      const result = {};
      await Promise.all(
        Object.entries(this.tableNames).map(async ([side, table]) => {
          try {
            const columns = await api("get-datasource-columns", { params: { datasource_name: table }, loadingBar: false });
            result[side] = columns.map((column) => column.column_name);
          } catch (error) {
            result[side] = [];
          }
        }),
      );
      this.resultColumns = result;
    },
    addRecipients(key, value, done) {
      const addresses = value
        .split(/[;,\s]+/)
        .map((address) => address.trim())
        .filter(Boolean);
      const invalid = addresses.filter((address) => !isEmailAddress(address));
      if (invalid.length) {
        this.$q.notify({ type: "negative", message: "Not an email address: " + invalid.join(", ") });
      }
      const valid = addresses.filter((address) => isEmailAddress(address) && !this.email[key].includes(address));
      valid.forEach((address) => this.email[key].push(address));
      done();
    },
    toggleOpen(sheet) {
      const key = this.itemKey(sheet);
      const index = this.openKeys.indexOf(key);
      if (index >= 0) this.openKeys.splice(index, 1);
      else this.openKeys.push(key);
    },
    open(sheet) {
      const key = this.itemKey(sheet);
      if (!this.openKeys.includes(key)) this.openKeys.push(key);
    },
    revealProblem({ file, sheet }) {
      if (this.email.send_when === "evaluate_sql" && !this.evaluateSummary) this.evaluateOpen = true;
      const target = this.email.files[file];
      if (!target) return;
      const element = sheet !== null && target.sheets[sheet] ? this.revealSheet(target.sheets[sheet]) : this.fileElements[file];
      if (element && element.scrollIntoView) element.scrollIntoView({ block: "center", behavior: "smooth" });
    },
    revealSheet(sheet) {
      this.open(sheet);
      const row = this.sheetRows[this.itemKey(sheet)];
      return row && row.$el;
    },
    newSheet(option) {
      if (option.kind === "sql") return defaultSqlSheet();
      return defaultResultSheet(option.side, this.isRec ? this.ruleConfig : null);
    },
    addSheet(fileIndex, option) {
      const sheet = this.newSheet(option);
      this.email.files[fileIndex].sheets.push(sheet);
      this.open(this.email.files[fileIndex].sheets[this.email.files[fileIndex].sheets.length - 1]);
    },
    // A new file starts with one result sheet, so it is never empty.
    addFile() {
      const sheet = defaultResultSheet(this.isRec ? "a" : "main", this.isRec ? this.ruleConfig : null);
      this.email.files.push({ name: null, attach: true, sheets: [sheet] });
      const file = this.email.files[this.email.files.length - 1];
      this.open(file.sheets[0]);
    },
    hasContent(sheet) {
      return Boolean((sheet.query || "").trim() || (sheet.filter || "").trim() || (sheet.fields && sheet.fields.length));
    },
    confirm(message, action) {
      this.$q.dialog({ title: "Remove", message, cancel: true, persistent: false }).onOk(action);
    },
    sheetCommand(fileIndex, sheetIndex, command) {
      const sheets = this.email.files[fileIndex].sheets;
      const sheet = sheets[sheetIndex];
      if (command.name === "move") {
        this.moveSheet({ file: fileIndex, index: sheetIndex }, { file: fileIndex, index: sheetIndex + command.offset });
      } else if (command.name === "duplicate") {
        sheets.splice(sheetIndex + 1, 0, JSON.parse(JSON.stringify({ ...sheet, name: null })));
        this.open(sheets[sheetIndex + 1]);
      } else if (command.name === "transfer") {
        if (command.file === null) {
          this.email.files.push({ name: null, attach: true, sheets: [] });
        }
        const target = command.file === null ? this.email.files.length - 1 : command.file;
        this.moveSheet({ file: fileIndex, index: sheetIndex }, { file: target, index: this.email.files[target].sheets.length });
      } else if (command.name === "remove") {
        const remove = () => sheets.splice(sheetIndex, 1);
        if (this.hasContent(sheet)) {
          this.confirm(`Remove sheet "${this.sheetNames[fileIndex][sheetIndex]}" with its ${sheet.kind === "sql" ? "query" : "filter and fields"}?`, remove);
        } else {
          remove();
        }
      }
    },
    // Moves a sheet to the place of another (or to the end of a file), also between files.
    moveSheet(from, to) {
      const source = this.email.files[from.file].sheets;
      const [sheet] = source.splice(from.index, 1);
      this.email.files[to.file].sheets.splice(Math.min(to.index, this.email.files[to.file].sheets.length), 0, sheet);
    },
    moveFile(from, to) {
      const [file] = this.email.files.splice(from, 1);
      this.email.files.splice(to, 0, file);
    },
    // The copy gets the default name, numbered after the others, so the names stay apart.
    duplicateFile(fileIndex) {
      const copy = JSON.parse(JSON.stringify(this.email.files[fileIndex]));
      copy.name = null;
      this.email.files.splice(fileIndex + 1, 0, copy);
    },
    removeFile(fileIndex) {
      const file = this.email.files[fileIndex];
      const remove = () => this.email.files.splice(fileIndex, 1);
      if (file.sheets.some(this.hasContent)) {
        this.confirm(`Remove file ${fileIndex + 1} with its ${file.sheets.length} sheet(s)?`, remove);
      } else {
        remove();
      }
    },
    onFileDragStart(event, fileIndex) {
      emailDrag.file = fileIndex;
      this.draggingFile = fileIndex;
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", "file");
    },
    onFileDragEnd() {
      emailDrag.file = null;
      this.draggingFile = null;
      this.fileHandleDown = null;
    },
    // A file takes another file's place; a sheet dropped on a file (not on a sheet) goes to its end.
    accepts(fileIndex) {
      return (emailDrag.file !== null && emailDrag.file !== fileIndex) || (emailDrag.sheet !== null && emailDrag.sheet.file !== fileIndex);
    },
    onFileDragOver(event, fileIndex) {
      if (this.accepts(fileIndex)) {
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        this.overFile = fileIndex;
      }
    },
    onFileDrop(event, fileIndex) {
      this.overFile = null;
      if (!this.accepts(fileIndex)) return;
      event.preventDefault();
      if (emailDrag.file !== null) {
        this.moveFile(emailDrag.file, fileIndex);
      } else {
        this.moveSheet(emailDrag.sheet, { file: fileIndex, index: this.email.files[fileIndex].sheets.length });
      }
    },
    async sendTest() {
      this.testing = true;
      try {
        await api("send-test-email", { method: "POST", params: { control_name: this.controlName, to: this.testAddress } });
        this.$q.notify({ type: "positive", message: "Test email sent to " + this.testAddress + "." });
      } catch (error) {
        notifyError("Test email was not sent.", error);
      } finally {
        this.testing = false;
      }
    },
  },
};
</script>

<style scoped>
/* The Evaluate SQL folds like a sheet (EmailSheetRow). */
.email-evaluate {
  border: 1px solid var(--rapo-border-soft);
  border-radius: 4px;
  background: var(--rapo-surface);
}

.email-evaluate--open {
  border-color: var(--rapo-panel-border);
}

.email-evaluate__head {
  min-height: 40px;
  padding: 2px 4px 2px 8px;
  cursor: pointer;
}

.email-evaluate__kind {
  margin: 0;
  font-size: 12px;
  flex: none;
}

.email-evaluate__body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 12px;
  border-top: 1px solid var(--rapo-border-soft);
}

.email-file {
  padding: 8px 10px 6px;
  border: 1px solid var(--rapo-panel-border);
  border-radius: 6px;
  background: var(--rapo-surface-alt);
}

.email-file--dragging {
  opacity: 0.5;
}

.email-file--over {
  outline: 2px dashed var(--rapo-teal);
  outline-offset: 2px;
}

.email-file__handle {
  color: var(--rapo-label);
  cursor: grab;
  opacity: 0.5;
}

.email-file:hover > .row > .email-file__handle {
  opacity: 1;
}

/* The file name stands out from the card as a field to edit. */
.email-file__name :deep(.q-field__control) {
  background: var(--rapo-surface);
}

.email-file__sheets {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 8px 0 0 19px;
}
</style>
