<template>
  <div class="q-gutter-y-md">
    <div class="row q-gutter-md">
      <q-select class="col" outlined emit-value map-options v-model="email.send_when" :options="sendWhenOptions" label="Send when">
        <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
          'Done, with results': only runs that end Done and have rows in the attachment (after its filter).<br />
          'Done, always': every run that ends Done, empty ones with a note instead of a file.<br />
          'Done or error': as 'Done, always', plus runs that end in Error, with the error and no file.
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
        label="Max records"
        clearable>
        <template v-slot:prepend>
          <q-icon name="fas fa-list-ol" @click.stop.prevent />
        </template>
        <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
          Above this many rows the email is sent without the file, with a note.<br />
          Empty = the instance limit ([EMAIL] max_attachment_rows in rapo.ini), which also caps this value.
        </q-tooltip>
      </q-input>
      <q-toggle class="col" v-model="email.include_summary" label="Append run summary">
        <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
          Adds the control, window, status, record counts and attachment rows below the body.
        </q-tooltip>
      </q-toggle>
      <q-toggle class="col" v-model="email.attach" label="Attach Excel file" />
    </div>

    <div v-for="field in recipientFields" :key="field.key" class="row">
      <q-select
        class="col"
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

    <div class="row">
      <q-input
        ref="subject"
        class="col"
        outlined
        v-model="email.subject"
        label="Subject">
        <template v-slot:append>
          <q-btn flat dense size="sm" icon="fas fa-code" @click.stop>
            <q-tooltip>Insert variable</q-tooltip>
            <q-menu>
              <q-list dense>
                <q-item v-for="variable in variables" :key="variable.token" clickable v-close-popup @click="insertVariable('subject', variable.token)">
                  <q-item-section>{{ variable.label }}</q-item-section>
                  <q-item-section side class="text-mono">{{ variable.token }}</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
          </q-btn>
        </template>
      </q-input>
    </div>

    <div class="row">
      <q-input ref="body" class="col" outlined v-model="email.body" label="Body" type="textarea" autogrow input-style="min-height: 120px">
        <template v-slot:append>
          <q-btn flat dense size="sm" icon="fas fa-code" @click.stop>
            <q-tooltip>Insert variable</q-tooltip>
            <q-menu>
              <q-list dense>
                <q-item v-for="variable in variables" :key="variable.token" clickable v-close-popup @click="insertVariable('body', variable.token)">
                  <q-item-section>{{ variable.label }}</q-item-section>
                  <q-item-section side class="text-mono">{{ variable.token }}</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
          </q-btn>
        </template>
      </q-input>
    </div>

    <div class="text-grey-7 text-caption">
      Variables such as <span class="text-mono">{control_name}</span> or <span class="text-mono">{control_date_from:%Y-%m-%d}</span> are replaced in the
      subject, the body, the file name, the sheet filters and the Free SQL. An unknown one stays as it is.
    </div>

    <div class="text-subtitle1 q-mt-lg">{{ email.attach ? "Attachment" : "Results" }}</div>
    <div v-if="email.attach" class="row">
      <q-input
        ref="attachment_name"
        class="col"
        outlined
        :model-value="email.attachment_name"
        @update:model-value="(value) => (email.attachment_name = value && value.trim() ? value : null)"
        label="File name"
        :placeholder="attachmentName"
        stack-label>
        <template v-slot:prepend>
          <q-icon name="fas fa-file-excel" @click.stop.prevent />
        </template>
        <template v-slot:append>
          <q-btn flat dense size="sm" icon="fas fa-code" @click.stop>
            <q-tooltip>Insert variable</q-tooltip>
            <q-menu>
              <q-list dense>
                <q-item v-for="variable in variables" :key="variable.token" clickable v-close-popup @click="insertVariable('attachment_name', variable.token)">
                  <q-item-section>{{ variable.label }}</q-item-section>
                  <q-item-section side class="text-mono">{{ variable.token }}</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
          </q-btn>
        </template>
        <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
          Name of the Excel file, with variables, e.g. Losses_{control_date_from:%Y%m%d}. .xlsx is added when missing,<br />
          and \ / : * ? " &lt; &gt; | become _. Empty = {{ attachmentName }}.
        </q-tooltip>
      </q-input>
    </div>
    <div v-if="!email.attach" class="text-grey-7 text-caption">
      No file is attached. The sheets below still decide which rows count as results for 'Done, with results'.
    </div>
    <div v-else-if="!anySheetIncluded" class="text-warning text-caption">No sheet is included, so no file is attached and 'Done, with results' never sends.</div>

    <q-card v-for="sheet in sheets" :key="sheet.key" flat bordered>
      <q-card-section class="q-gutter-y-md">
        <div class="row items-center q-gutter-md">
          <div class="text-weight-bold">{{ sheet.title }}</div>
          <q-input
            dense
            outlined
            style="width: 260px"
            maxlength="31"
            :model-value="email.sheets[sheet.key].name"
            @update:model-value="(value) => (email.sheets[sheet.key].name = value && value.trim() ? value : null)"
            label="Sheet name"
            :placeholder="sheet.defaultName"
            stack-label
            :error="sheetNameInvalid(sheet.key)"
            hide-bottom-space>
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
              Name of the sheet in the Excel file, up to 31 characters without [ ] : * ? / \.<br />
              Empty = {{ sheet.defaultName || "the control name" }}.
            </q-tooltip>
          </q-input>
          <div class="text-grey-7 text-mono">{{ sheet.table }}</div>
          <q-space />
          <q-toggle
            v-model="email.sheets[sheet.key].enabled"
            :disable="sheet.rec && sheet.available.length === 0"
            :label="sheet.rec && sheet.available.length === 0 ? 'No output saved for this side' : 'Include'" />
        </div>

        <template v-if="email.sheets[sheet.key].enabled">
          <div v-if="sheet.rec" class="row items-center q-gutter-md">
            <span class="text-grey-8">Result types</span>
            <q-checkbox
              v-for="type in sheet.available"
              :key="type"
              :model-value="email.sheets[sheet.key].result_types.includes(type)"
              @update:model-value="(checked) => toggleResultType(sheet.key, type, checked)"
              :label="type" />
          </div>

          <code-box
            label="Filter"
            v-model="email.sheets[sheet.key].filter"
            :columns="sheet.columns"
            :template-vars="sheetVariables"
            :examples="filterExamples(sheet.key)"
            :check="filterChecker(sheet.key)">
          </code-box>

          <div>
            <div class="row items-center q-gutter-sm q-mb-sm">
              <span class="text-grey-8">Fields</span>
              <span class="text-grey-6 text-caption">{{ email.sheets[sheet.key].fields.length ? "" : "none selected: all columns, in table order" }}</span>
              <q-space />
              <q-select
                dense
                outlined
                style="min-width: 260px"
                :model-value="null"
                :options="unusedColumns(sheet)"
                label="Add field"
                @update:model-value="(column) => addField(sheet.key, column)" />
              <q-btn flat dense no-caps label="Add all" @click="addAllFields(sheet)" :disable="unusedColumns(sheet).length === 0" />
              <q-btn flat dense no-caps label="Clear" @click="email.sheets[sheet.key].fields.splice(0)" :disable="email.sheets[sheet.key].fields.length === 0" />
            </div>
            <q-markup-table v-if="email.sheets[sheet.key].fields.length" flat dense bordered>
              <thead>
                <tr class="bg-blue-grey-1">
                  <th class="text-left" style="width: 40px">#</th>
                  <th class="text-left">Column</th>
                  <th class="text-left">Header label</th>
                  <th style="width: 120px"></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(field, index) in email.sheets[sheet.key].fields" :key="field.column">
                  <td class="text-grey-7">{{ index + 1 }}.</td>
                  <td class="text-mono" :class="{ 'text-negative': !sheet.columns.includes(field.column) }">
                    {{ field.column }}
                    <q-tooltip v-if="!sheet.columns.includes(field.column)">Not a column of the result table: it will be skipped</q-tooltip>
                  </td>
                  <td>
                    <q-input
                      dense
                      borderless
                      :model-value="field.label"
                      @update:model-value="(value) => (field.label = value || null)"
                      :placeholder="field.column" />
                  </td>
                  <td class="text-right text-no-wrap">
                    <q-btn flat dense size="sm" icon="fas fa-arrow-up" :disable="index === 0" @click="moveField(sheet.key, index, -1)" />
                    <q-btn
                      flat
                      dense
                      size="sm"
                      icon="fas fa-arrow-down"
                      :disable="index === email.sheets[sheet.key].fields.length - 1"
                      @click="moveField(sheet.key, index, 1)" />
                    <q-btn flat dense size="sm" icon="fas fa-times" @click="email.sheets[sheet.key].fields.splice(index, 1)" />
                  </td>
                </tr>
              </tbody>
            </q-markup-table>
          </div>
        </template>
      </q-card-section>
    </q-card>

    <q-card flat bordered>
      <q-card-section class="q-gutter-y-md">
        <div class="row items-center q-gutter-md">
          <div class="text-weight-bold">Free SQL</div>
          <q-input
            dense
            outlined
            style="width: 260px"
            maxlength="31"
            :model-value="email.sheets.sql.name"
            @update:model-value="(value) => (email.sheets.sql.name = value && value.trim() ? value : null)"
            label="Sheet name"
            :placeholder="defaultSqlSheetName"
            stack-label
            :error="sheetNameInvalid('sql')"
            hide-bottom-space>
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
              Name of the sheet in the Excel file, up to 31 characters without [ ] : * ? / \.<br />
              Empty = {{ defaultSqlSheetName }}.
            </q-tooltip>
          </q-input>
          <div class="text-grey-7">A query of your own, as the last sheet</div>
          <q-space />
          <q-toggle v-model="email.sheets.sql.enabled" label="Include" />
        </div>
        <template v-if="email.sheets.sql.enabled">
          <code-box
            label="Query"
            v-model="email.sheets.sql.query"
            :tables="sqlTables"
            :template-vars="sheetVariables"
            :examples="sqlExamples"
            :check="sqlChecker">
          </code-box>
          <div class="text-grey-7 text-caption">
            A select or with query. Its columns are the sheet's columns, named as the query returns them, so a quoted alias such as "Loss amount" becomes the
            header. Variables are replaced as text, so quote dates, e.g. to_date('{control_date_from:%Y-%m-%d}', 'yyyy-mm-dd'). Its rows count toward the
            limits, and toward 'Done, with results' only when no other sheet is included.
          </div>
        </template>
      </q-card-section>
    </q-card>

    <div class="row items-start q-gutter-md q-mt-lg">
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
  </div>
</template>

<script>
import { api, notifyError } from "../api";
import CodeBox from "./CodeBox.vue";
import { examplesFor } from "../utils/codeExamples";
import {
  DEFAULT_SQL_SHEET_NAME,
  RESULT_META_COLUMNS,
  SEND_WHEN_OPTIONS,
  SHEET_NAME_INVALID,
  completeEmailConfig,
  defaultSheetName,
  emailVariables,
  isEmailAddress,
  sheetVariables,
} from "../utils/email";

// rule_config.email of a control. modelValue is the parent's object and is edited in place.
export default {
  components: { CodeBox },
  props: {
    modelValue: { type: Object, required: true },
    controlName: String,
    controlType: String,
    // rule_config of a REC control, for the result types each side saves.
    ruleConfig: Object,
    // Source columns per sheet ({ main, a, b }), offered while the result table does not exist yet.
    sourceColumns: { type: Object, default: () => ({}) },
    // Whether the control is saved and the form unchanged since, so a test send uses what is shown.
    saved: Boolean,
  },
  data() {
    return {
      sendWhenOptions: SEND_WHEN_OPTIONS,
      defaultSqlSheetName: DEFAULT_SQL_SHEET_NAME,
      recipientFields: [
        { key: "to", label: "To", icon: "fas fa-envelope" },
        { key: "cc", label: "CC", icon: "fas fa-copy" },
        { key: "bcc", label: "BCC", icon: "fas fa-user-secret" },
      ],
      // Columns of the existing result tables, by sheet key.
      resultColumns: {},
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
      return emailVariables(this.controlType);
    },
    // The variables of the filters and the Free SQL: listed under the box and completed after "{".
    sheetVariables() {
      return sheetVariables(this.controlType);
    },
    // The control's result tables with their columns, so the Free SQL completes them.
    sqlTables() {
      if (!this.controlName) return {};
      return Object.fromEntries(this.sheets.map((sheet) => [sheet.table, sheet.columns]));
    },
    sqlExamples() {
      return examplesFor({ field: "email_sql", controlType: this.controlType, controlName: this.controlName, side: "a" });
    },
    anySheetIncluded() {
      const included = this.sheets.some((sheet) => this.email.sheets[sheet.key].enabled && (!sheet.rec || sheet.available.length));
      return included || this.email.sheets.sql.enabled;
    },
    tableNames() {
      const name = (this.controlName || "<NAME>").toUpperCase();
      return this.isRec ? { a: "RAPO_RESA_" + name, b: "RAPO_RESB_" + name } : { main: "RAPO_REST_" + name };
    },
    sheets() {
      const meta = RESULT_META_COLUMNS[this.isRec ? "rec" : "single"];
      const columns = (key) => {
        const existing = this.resultColumns[key];
        if (existing && existing.length) return existing;
        return [...new Set([...(this.sourceColumns[key] || []).map((column) => column.toUpperCase()), ...meta])];
      };
      if (!this.isRec) {
        return [
          { key: "main", title: "Sheet", defaultName: defaultSheetName("main", this.controlName), table: this.tableNames.main, rec: false, columns: columns("main"), available: [] },
        ];
      }
      const rule = this.ruleConfig || {};
      return ["a", "b"].map((side) => ({
        key: side,
        title: "Sheet " + side.toUpperCase(),
        defaultName: defaultSheetName(side),
        table: this.tableNames[side],
        rec: true,
        columns: columns(side),
        available: [...(rule["need_issues_" + side] ? ["Loss", "Discrepancy"] : []), ...(rule["need_recons_" + side] ? ["Match"] : [])],
      }));
    },
    attachmentName() {
      return (this.controlName || "<NAME>").toUpperCase() + "_<run from>[_<run to>].xlsx";
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
      },
    },
    tableNames: {
      immediate: true,
      handler() {
        this.loadResultColumns();
      },
    },
  },
  methods: {
    filterExamples(side) {
      return examplesFor({ field: "email_filter", controlType: this.controlType, controlName: this.controlName, side });
    },
    // The filter is checked against the sheet's result table, with sample values for the {variables}.
    filterChecker(side) {
      return (statement) =>
        api("validate-sql", {
          method: "POST",
          loadingBar: false,
          body: { kind: "email_filter", statement, control_name: this.controlName, control_type: this.controlType, side },
        });
    },
    // The query is checked with sample values for the {variables}; it needs no saved control.
    sqlChecker(statement) {
      return api("validate-sql", {
        method: "POST",
        loadingBar: false,
        body: { kind: "email_sql", statement, control_name: this.controlName, control_type: this.controlType },
      });
    },
    isEmailAddress,
    sheetNameInvalid(key) {
      return SHEET_NAME_INVALID.test(this.email.sheets[key].name || "");
    },
    async loadResultColumns() {
      if (!this.controlName) {
        this.resultColumns = {};
        return;
      }
      const result = {};
      await Promise.all(
        Object.entries(this.tableNames).map(async ([key, table]) => {
          try {
            const columns = await api("get-datasource-columns", { params: { datasource_name: table }, loadingBar: false });
            result[key] = columns.map((column) => column.column_name);
          } catch (error) {
            result[key] = [];
          }
        })
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
    insertVariable(field, token) {
      const input = this.$refs[field] && this.$refs[field].getNativeElement();
      const text = this.email[field] || "";
      if (input && typeof input.selectionStart === "number" && document.activeElement === input) {
        const start = input.selectionStart;
        const end = input.selectionEnd;
        this.email[field] = text.slice(0, start) + token + text.slice(end);
        this.$nextTick(() => input.setSelectionRange(start + token.length, start + token.length));
      } else {
        this.email[field] = text + token;
      }
    },
    toggleResultType(key, type, checked) {
      const types = this.email.sheets[key].result_types;
      const index = types.indexOf(type);
      if (checked && index < 0) types.push(type);
      if (!checked && index >= 0) types.splice(index, 1);
    },
    unusedColumns(sheet) {
      const used = new Set(this.email.sheets[sheet.key].fields.map((field) => field.column));
      return sheet.columns.filter((column) => !used.has(column));
    },
    addField(key, column) {
      if (column) this.email.sheets[key].fields.push({ column, label: null });
    },
    addAllFields(sheet) {
      this.unusedColumns(sheet).forEach((column) => this.addField(sheet.key, column));
    },
    moveField(key, index, offset) {
      const fields = this.email.sheets[key].fields;
      const [field] = fields.splice(index, 1);
      fields.splice(index + offset, 0, field);
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
.text-mono {
  font-family: monospace;
}
</style>
