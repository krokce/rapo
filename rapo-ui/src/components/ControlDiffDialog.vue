<template>
  <q-dialog v-model="visible">
    <q-card class="column no-wrap" style="width: 1400px; max-width: 95vw; max-height: 90vh">
      <q-card-section class="row items-center q-py-sm">
        <div class="text-h6">Unsaved changes ({{ rows.length }})</div>
        <q-space />
        <q-btn aria-label="Close" flat round icon="fas fa-times" v-close-popup />
      </q-card-section>
      <q-separator />

      <q-card-section class="col scroll">
        <diff-table :rows="rows" undoable @undo="(row) => $emit('undo', row)" empty-text="No differences in the values: only their order changed." />
      </q-card-section>
      <q-separator />

      <q-card-actions align="right">
        <q-btn flat label="Discard all changes" color="negative" :disable="busy" @click="discard" />
        <q-space />
        <q-btn flat label="Close" color="primary" v-close-popup />
        <q-btn label="Apply" color="primary" :disable="busy" @click="apply" />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script>
import DiffTable from "./DiffTable.vue";
import { DERIVED_FIELDS } from "../utils/controlDiff";

// What Apply would change in the saved control, from the parent's diff function (utils/controlDiff.js). It is
// called only while the dialog is open, and again whenever the form changes behind it, so an undone row (undo:
// the parent reverts it) leaves the list. Rows derived from other fields say what they follow instead.
export default {
  name: "ControlDiffDialog",
  components: { DiffTable },
  props: {
    diff: { type: Function, required: true },
    busy: { type: Boolean, default: false },
  },
  emits: ["apply", "undo", "discard"],
  data() {
    return { visible: false };
  },
  computed: {
    rows() {
      return this.visible ? this.diff().map((row) => (DERIVED_FIELDS[row.path] ? { ...row, follows: DERIVED_FIELDS[row.path] } : row)) : [];
    },
  },
  methods: {
    open() {
      this.visible = true;
    },
    discard() {
      this.visible = false;
      this.$emit("discard");
    },
    // Closes first, so that a failed validation shows its tab and message.
    apply() {
      this.visible = false;
      this.$emit("apply");
    },
  },
};
</script>
