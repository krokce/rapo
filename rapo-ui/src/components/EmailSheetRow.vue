<template>
  <div
    class="email-sheet"
    :class="{ 'email-sheet--open': open, 'email-sheet--over': over, 'email-sheet--dragging': dragging }"
    :draggable="handleDown"
    @dragstart="onDragStart"
    @dragend="onDragEnd"
    @dragover="onDragOver"
    @dragleave="over = false"
    @drop="onDrop">
    <div class="email-sheet__head row no-wrap items-center q-gutter-x-sm" v-keyboard:button :aria-expanded="String(open)" @click="$emit('toggle')">
      <q-icon
        name="fas fa-grip-vertical"
        size="11px"
        class="email-sheet__handle"
        title="Drag to move the sheet, also into another file"
        @click.stop
        @mousedown="handleDown = true"
        @mouseup="handleDown = false" />
      <q-chip class="email-sheet__kind" :title="kind.title">
        <q-avatar :icon="kind.icon" :color="kind.color" text-color="white" />
        {{ kind.label }}
      </q-chip>
      <div class="text-weight-medium ellipsis">{{ effectiveName }}</div>
      <div v-if="sheet.kind === 'result'" class="text-grey-7 text-mono ellipsis gt-xs">{{ table }}</div>
      <div v-if="rec && sheet.kind === 'result'" class="dash-note ellipsis">{{ typesText }}</div>
      <q-space />
      <q-badge v-if="sheet.kind === 'result' && (sheet.filter || '').trim()" outline color="grey-7" label="filter" />
      <q-badge v-if="sheet.kind === 'result' && sheet.fields.length" outline color="grey-7" :label="sheet.fields.length + (sheet.fields.length === 1 ? ' field' : ' fields')" />
      <q-icon v-if="problem" name="fas fa-exclamation-triangle" color="negative" size="14px" :title="problem" />
      <q-icon :name="open ? 'fas fa-chevron-up' : 'fas fa-chevron-down'" size="12px" color="grey-7" />
      <q-btn flat round dense size="sm" icon="fas fa-ellipsis-v" color="grey-7" aria-label="Sheet menu" @click.stop>
        <q-menu anchor="bottom right" self="top right">
          <q-list dense style="min-width: 170px">
            <q-item v-close-popup clickable :disable="first" @click="$emit('command', { name: 'move', offset: -1 })">
              <q-item-section avatar><q-icon name="fas fa-arrow-up" size="12px" /></q-item-section>
              <q-item-section>Move up</q-item-section>
            </q-item>
            <q-item v-close-popup clickable :disable="last" @click="$emit('command', { name: 'move', offset: 1 })">
              <q-item-section avatar><q-icon name="fas fa-arrow-down" size="12px" /></q-item-section>
              <q-item-section>Move down</q-item-section>
            </q-item>
            <q-item v-close-popup clickable @click="$emit('command', { name: 'duplicate' })">
              <q-item-section avatar><q-icon name="fas fa-clone" size="12px" /></q-item-section>
              <q-item-section>Duplicate</q-item-section>
            </q-item>
            <q-item clickable>
              <q-item-section avatar><q-icon name="fas fa-file-export" size="12px" /></q-item-section>
              <q-item-section>Move to file</q-item-section>
              <q-item-section side><q-icon name="fas fa-chevron-right" size="10px" /></q-item-section>
              <q-menu anchor="top end" self="top start">
                <q-list dense style="min-width: 150px">
                  <q-item v-for="target in fileTargets" :key="target.index" v-close-popup clickable @click="$emit('command', { name: 'transfer', file: target.index })">
                    <q-item-section>{{ target.label }}</q-item-section>
                  </q-item>
                  <q-item v-close-popup clickable @click="$emit('command', { name: 'transfer', file: null })">
                    <q-item-section class="text-primary">New file</q-item-section>
                  </q-item>
                </q-list>
              </q-menu>
            </q-item>
            <q-separator />
            <q-item v-close-popup clickable @click="$emit('command', { name: 'remove' })">
              <q-item-section avatar><q-icon name="fas fa-trash" size="12px" /></q-item-section>
              <q-item-section>Remove</q-item-section>
            </q-item>
          </q-list>
        </q-menu>
      </q-btn>
    </div>

    <div v-if="open" class="email-sheet__body">
      <div class="row items-center q-gutter-md">
        <q-input
          dense
          outlined
          style="width: 260px"
          maxlength="31"
          :model-value="sheet.name"
          @update:model-value="(value) => (sheet.name = value && value.trim() ? value : null)"
          label="Sheet name"
          :placeholder="defaultName"
          stack-label
          :error="nameInvalid"
          hide-bottom-space>
          <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">
            Name of the sheet in the Excel file, up to 31 characters without [ ] : * ? / \.<br />
            Empty = {{ defaultName }}{{ rec && sheet.kind === "result" ? " (the side, plus the result types when not all of them)" : "" }}.
          </q-tooltip>
        </q-input>
        <template v-if="rec && sheet.kind === 'result'">
          <div class="row items-center q-gutter-x-sm">
            <span class="text-grey-8">Side</span>
            <q-chip
              v-for="side in ['a', 'b']"
              :key="side"
              clickable
              :disable="!availableBySide[side].length"
              :class="{ 'chip-selected': sheet.side === side }"
              :title="availableBySide[side].length ? 'Export ' + tables[side] : 'Side ' + side.toUpperCase() + ' saves no results'"
              @click="pickSide(side)">
              <q-avatar :color="SIDE_COLORS[side]" text-color="white">{{ side.toUpperCase() }}</q-avatar>
              {{ tables[side] }}
            </q-chip>
          </div>
          <div class="row items-center q-gutter-x-md">
            <span class="text-grey-8">Result types</span>
            <q-checkbox
              v-for="type in available"
              :key="type"
              dense
              :model-value="sheet.result_types.includes(type)"
              @update:model-value="(checked) => toggleResultType(type, checked)"
              :label="type" />
          </div>
        </template>
      </div>

      <template v-if="sheet.kind === 'result'">
        <code-box label="Filter" v-model="sheet.filter" :columns="columns" :template-vars="sheetVariables" :examples="filterExamples" :check="filterChecker"></code-box>

        <div>
          <div class="row items-center q-gutter-sm q-mb-sm">
            <span class="text-grey-8">Fields</span>
            <span class="text-grey-7 text-caption">{{ sheet.fields.length ? "" : "none selected: all columns, in table order" }}</span>
            <q-space />
            <q-select dense outlined style="min-width: 260px" :model-value="null" :options="unusedColumns" label="Add field" @update:model-value="addField" />
            <q-btn flat dense no-caps label="Add all" @click="unusedColumns.forEach(addField)" :disable="unusedColumns.length === 0" />
            <q-btn flat dense no-caps label="Clear" @click="sheet.fields.splice(0)" :disable="sheet.fields.length === 0" />
          </div>
          <q-markup-table v-if="sheet.fields.length" flat dense bordered>
            <thead>
              <tr class="bg-blue-grey-1">
                <th title="The order of the column in the sheet" class="text-left" style="width: 40px">#</th>
                <th title="The column of the result table" class="text-left">Column</th>
                <th title="The header the column gets in the sheet" class="text-left">Header label</th>
                <th style="width: 120px"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(field, index) in sheet.fields" :key="field.column">
                <td class="text-grey-7">{{ index + 1 }}.</td>
                <td class="text-mono" :class="{ 'text-negative': !columns.includes(field.column) }">
                  {{ field.column }}
                  <q-tooltip v-if="!columns.includes(field.column)">Not a column of the result table: it will be skipped</q-tooltip>
                </td>
                <td>
                  <q-input dense borderless :model-value="field.label" @update:model-value="(value) => (field.label = value || null)" :placeholder="field.column" />
                </td>
                <td class="text-right text-no-wrap">
                  <q-btn aria-label="Move up" flat dense size="sm" icon="fas fa-arrow-up" :disable="index === 0" @click="moveField(index, -1)" />
                  <q-btn aria-label="Move down" flat dense size="sm" icon="fas fa-arrow-down" :disable="index === sheet.fields.length - 1" @click="moveField(index, 1)" />
                  <q-btn aria-label="Remove field" flat dense size="sm" icon="fas fa-times" @click="sheet.fields.splice(index, 1)" />
                </td>
              </tr>
            </tbody>
          </q-markup-table>
        </div>
      </template>

      <template v-else>
        <code-box label="Query" v-model="sheet.query" :tables="sqlTables" :template-vars="sheetVariables" :examples="sqlExamples" :check="sqlChecker"></code-box>
        <div class="text-grey-7 text-caption">
          A select or with query. Its columns are the sheet's columns, named as the query returns them, so a quoted alias such as "Loss amount" becomes the
          header. Variables are replaced as text, so quote dates, e.g. to_date('{control_date_from:%Y-%m-%d}', 'yyyy-mm-dd'). Its rows count toward the
          limits, and toward 'Done, with results' only when no file has a result sheet.
        </div>
      </template>
    </div>
  </div>
</template>

<script>
import { api } from "../api";
import CodeBox from "./CodeBox.vue";
import { examplesFor } from "../utils/codeExamples";
import { SHEET_NAME_INVALID, availableResultTypes, chosenResultTypes, emailDrag } from "../utils/email";

const SIDE_COLORS = { a: "teal-8", b: "indigo-6" };

// One sheet of an email file (rule_config.email.files[].sheets[]): a summary line that opens its editor. modelValue is
// the parent's object and is edited in place; moves and removal are emitted as commands for the file list.
export default {
  components: { CodeBox },
  props: {
    modelValue: { type: Object, required: true },
    // Where it is: indexes of its file and of itself, to tell drops apart.
    fileIndex: { type: Number, required: true },
    index: { type: Number, required: true },
    first: Boolean,
    last: Boolean,
    open: Boolean,
    // The other files it can be moved to: [{ index, label }].
    fileTargets: { type: Array, default: () => [] },
    effectiveName: String,
    defaultName: String,
    // The first validation problem of the sheet, shown as a warning icon.
    problem: String,
    controlName: String,
    controlType: String,
    ruleConfig: Object,
    // Result table names and columns by side (main, or a and b).
    tables: { type: Object, required: true },
    columnsBySide: { type: Object, required: true },
    sheetVariables: Array,
    sqlTables: Object,
  },
  emits: ["toggle", "command", "drop-sheet"],
  data() {
    return { SIDE_COLORS, handleDown: false, dragging: false, over: false };
  },
  computed: {
    sheet() {
      return this.modelValue;
    },
    rec() {
      return this.controlType === "REC";
    },
    kind() {
      if (this.sheet.kind === "sql") return { label: "Free SQL", icon: "fas fa-code", color: "deep-purple-4", title: "A query of your own" };
      if (!this.rec) return { label: "Results", icon: "fas fa-table", color: "teal-7", title: "Rows of the result table of this run" };
      const side = String(this.sheet.side || "").toUpperCase();
      return { label: "Side " + side, icon: "fas fa-table", color: SIDE_COLORS[this.sheet.side] || "grey-6", title: "Rows of result table " + side + " of this run" };
    },
    table() {
      return this.tables[this.sheet.side] || "";
    },
    columns() {
      return this.columnsBySide[this.sheet.side] || [];
    },
    availableBySide() {
      return { a: availableResultTypes(this.ruleConfig, "a"), b: availableResultTypes(this.ruleConfig, "b") };
    },
    available() {
      return this.availableBySide[this.sheet.side] || [];
    },
    typesText() {
      const chosen = chosenResultTypes(this.sheet, this.ruleConfig).filter((type) => this.sheet.result_types.includes(type));
      if (!chosen.length) return "no result type";
      return chosen.length === this.available.length ? "all types" : chosen.join(", ");
    },
    nameInvalid() {
      return SHEET_NAME_INVALID.test(this.sheet.name || "");
    },
    unusedColumns() {
      const used = new Set(this.sheet.fields.map((field) => field.column));
      return this.columns.filter((column) => !used.has(column));
    },
    filterExamples() {
      return examplesFor({ field: "email_filter", controlType: this.controlType, controlName: this.controlName, side: this.sheet.side });
    },
    sqlExamples() {
      return examplesFor({ field: "email_sql", controlType: this.controlType, controlName: this.controlName, side: "a" });
    },
  },
  methods: {
    // The filter is checked against the sheet's result table, with sample values for the {variables}.
    filterChecker(statement) {
      return api("validate-sql", {
        method: "POST",
        loadingBar: false,
        body: { kind: "email_filter", statement, control_name: this.controlName, control_type: this.controlType, side: this.sheet.side },
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
    // Another side keeps the chosen types it also saves, else takes all of them.
    pickSide(side) {
      if (this.sheet.side === side) return;
      const available = this.availableBySide[side];
      const kept = this.sheet.result_types.filter((type) => available.includes(type));
      this.sheet.side = side;
      this.sheet.result_types.splice(0, this.sheet.result_types.length, ...(kept.length ? kept : available));
    },
    toggleResultType(type, checked) {
      const types = this.sheet.result_types;
      const index = types.indexOf(type);
      if (checked && index < 0) types.push(type);
      if (!checked && index >= 0) types.splice(index, 1);
    },
    addField(column) {
      if (column) this.sheet.fields.push({ column, label: null });
    },
    moveField(index, offset) {
      const [field] = this.sheet.fields.splice(index, 1);
      this.sheet.fields.splice(index + offset, 0, field);
    },
    onDragStart(event) {
      emailDrag.sheet = { file: this.fileIndex, index: this.index };
      this.dragging = true;
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", "sheet");
      event.stopPropagation();
    },
    onDragEnd() {
      emailDrag.sheet = null;
      this.dragging = false;
      this.handleDown = false;
    },
    accepts() {
      const dragged = emailDrag.sheet;
      return dragged && !(dragged.file === this.fileIndex && dragged.index === this.index);
    },
    onDragOver(event) {
      if (this.accepts()) {
        event.preventDefault();
        event.stopPropagation();
        event.dataTransfer.dropEffect = "move";
        this.over = true;
      }
    },
    // The dragged sheet takes this sheet's place.
    onDrop(event) {
      this.over = false;
      if (this.accepts()) {
        event.preventDefault();
        event.stopPropagation();
        this.$emit("drop-sheet", { from: emailDrag.sheet, to: { file: this.fileIndex, index: this.index } });
      }
    },
  },
};
</script>

<style scoped>
.email-sheet {
  border: 1px solid var(--rapo-border-soft);
  border-radius: 4px;
  background: var(--rapo-surface);
}

.email-sheet--open {
  border-color: var(--rapo-panel-border);
}

.email-sheet--dragging {
  opacity: 0.5;
}

.email-sheet--over {
  outline: 2px dashed var(--rapo-teal);
  outline-offset: 1px;
}

.email-sheet__head {
  min-height: 40px;
  padding: 2px 4px 2px 8px;
  cursor: pointer;
}

/* A flex column, not q-gutter-y: its negative top margin would pull the border up into the head. */
.email-sheet__body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 12px;
  border-top: 1px solid var(--rapo-border-soft);
}

.email-sheet__handle {
  color: var(--rapo-label);
  cursor: grab;
  opacity: 0.5;
}

.email-sheet:hover .email-sheet__handle {
  opacity: 1;
}

.email-sheet__kind {
  margin: 0 0 0 12px;
  font-size: 12px;
  flex: none;
}
</style>
