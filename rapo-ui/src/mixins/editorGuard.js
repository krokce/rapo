// What the editors (control, KPI type, datasource) share around their save: Ctrl+S / Cmd+S is Apply, the browser asks
// before closing a tab with unsaved changes, leaving asks Keep editing / Discard / Save, and a save refused because
// someone else saved first (409) offers Reload or Overwrite.
//
// The component provides:
// - `dirty` and `ready`; `editorWritable` (computed): whether this token may save at all;
// - `editorNoun`: "Control", "KPI type", "Datasource" (titles and notices);
// - `persist(mode)`: Save ("close") or Apply ("stay"); `submit(mode, lock)`: the write, true when saved;
// - `saveBeforeLeave()`: checks and saves on leaving, true when saved (false keeps the editor);
// - `reloadSaved()`: takes the version saved meanwhile, dropping the edits (a conflict's Reload);
// - optionally `editorShortcutBlocked()`: true while a dialog of its own owns Ctrl+S.
// Route guards are not merged from mixins, so each editor's beforeRouteLeave/Update calls confirmLeave.
import UnsavedChangesDialog from "../components/UnsavedChangesDialog.vue";

export default {
  created() {
    window.addEventListener("keydown", this.onEditorKeydown);
    window.addEventListener("beforeunload", this.onEditorBeforeUnload);
  },
  unmounted() {
    window.removeEventListener("keydown", this.onEditorKeydown);
    window.removeEventListener("beforeunload", this.onEditorBeforeUnload);
  },
  methods: {
    editorShortcutBlocked() {
      return false;
    },
    // Ctrl+S / Cmd+S is Apply anywhere in the editor, and never the browser's "Save page as".
    onEditorKeydown(event) {
      if ((event.ctrlKey || event.metaKey) && !event.altKey && (event.key === "s" || event.key === "S")) {
        event.preventDefault();
        if (this.ready && this.editorWritable && !this.editorShortcutBlocked()) {
          this.persist("stay");
        }
      }
    },
    onEditorBeforeUnload(event) {
      if (this.dirty && this.editorWritable) {
        event.preventDefault();
        event.returnValue = "";
      }
    },
    // A form without changes is not written at all; Save still goes back to the list.
    noChanges(mode, listRoute) {
      this.$q.notify({ color: "grey-7", message: "No changes" });
      if (mode === "close") {
        this.$router.push({ name: listRoute });
      }
    },
    // Leaving with unsaved changes (Cancel, the side menu, back, another item) asks first; a save that fails
    // (validation, conflict, error) keeps the editor open.
    confirmLeave(next) {
      if (!this.dirty || this.saving || !this.editorWritable) {
        next();
        return;
      }
      this.$q
        .dialog({ component: UnsavedChangesDialog })
        .onOk(async (choice) => {
          if (choice === "save") {
            next((await this.saveBeforeLeave()) ? undefined : false);
            return;
          }
          this.$q.notify({ type: "warning", message: "Changes discarded" });
          next();
        })
        .onCancel(() => next(false));
    },
    resolveConflict(mode, message) {
      this.$q
        .dialog({
          title: `${this.editorNoun} changed meanwhile`,
          message: `${message} Overwrite it with your version, or reload it and lose your changes?`,
          cancel: { label: "Keep editing", flat: true },
          persistent: true,
          options: {
            type: "radio",
            model: "reload",
            items: [
              { label: "Reload the saved version (discard my changes)", value: "reload" },
              { label: "Overwrite it with my version", value: "overwrite" },
            ],
          },
        })
        .onOk(async (choice) => {
          if (choice === "overwrite") {
            // A save on leaving was refused and the navigation canceled: the editor stays.
            await this.submit(mode === "leave" ? "stay" : mode, false);
            return;
          }
          await this.reloadSaved();
        });
    },
  },
};
