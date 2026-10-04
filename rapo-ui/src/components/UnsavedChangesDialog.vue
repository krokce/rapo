<template>
  <q-dialog ref="dialog" persistent @hide="$emit('hide')">
    <q-card style="min-width: 360px">
      <q-card-section class="text-h6">Unsaved changes</q-card-section>
      <q-card-section class="q-pt-none">Save your changes before leaving?</q-card-section>
      <q-card-actions align="right">
        <q-btn flat label="Keep editing" color="primary" @click="hide" />
        <q-btn flat label="Discard" color="negative" @click="choose('discard')" />
        <q-btn label="Save" color="primary" autofocus @click="choose('save')" />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script>
// The question when leaving an editor with unsaved changes, for $q.dialog({ component }): ok("save" | "discard"),
// or cancel to keep editing.
export default {
  name: "UnsavedChangesDialog",
  emits: ["ok", "hide"],
  methods: {
    show() {
      this.$refs.dialog.show();
    },
    hide() {
      this.$refs.dialog.hide();
    },
    choose(choice) {
      this.$emit("ok", choice);
      this.hide();
    },
  },
};
</script>
