<template>
  <q-dialog v-model="visible" persistent :maximized="maximized">
    <q-card class="column no-wrap grammar-edit" :style="maximized ? '' : 'width: 1200px; max-width: 95vw; height: 90vh'" @keydown="keydown">
      <q-card-section class="row items-center q-py-sm no-wrap">
        <q-icon name="fas fa-book" size="sm" class="q-mr-sm text-blue-grey-7" />
        <div class="text-h6 ellipsis">{{ title }}</div>
        <div v-if="loaded && loaded.updated_date" class="q-ml-md text-caption text-grey-7" title="When the grammar was last saved">saved {{ toDateTimeString(loaded.updated_date) }}</div>
        <q-space />
        <q-btn flat round :icon="maximized ? 'fas fa-compress' : 'fas fa-expand'" :aria-label="maximized ? 'Restore' : 'Maximize'" @click="maximized = !maximized">
          <q-tooltip>{{ maximized ? "Restore" : "Maximize" }}</q-tooltip>
        </q-btn>
        <q-btn aria-label="Close" flat round icon="fas fa-times" @click="close" />
      </q-card-section>
      <q-separator />

      <q-card-section v-if="loading" class="col">
        <q-skeleton type="rect" height="300px" />
      </q-card-section>

      <q-card-section v-else class="col column no-wrap q-gutter-y-sm grammar-edit__body">
        <div class="row items-start q-gutter-sm">
          <q-input
            v-model="name"
            dense
            outlined
            label="Grammar name"
            class="name-input"
            :error="Boolean(nameError)"
            :error-message="nameError"
            hide-bottom-space
            autofocus />
          <q-chip class="kind-chip" :title="kindTitle">
            <q-avatar :icon="kind === 'tagmap' ? 'fas fa-tags' : 'fas fa-sitemap'" color="blue-grey-6" text-color="white" />
            {{ kind === "tagmap" ? "Tag map" : "ASN.1 modules" }}
          </q-chip>
          <div v-if="loaded" class="text-caption text-grey-7 saved-facts" :title="savedFacts">{{ savedFacts }}</div>
        </div>
        <div v-if="loaded && loaded.used_by.length && renamed" class="row items-center q-gutter-xs text-caption">
          <q-icon name="fas fa-exclamation-triangle" color="orange-9" />
          <span class="text-orange-10">Used by datasource{{ loaded.used_by.length > 1 ? "s" : "" }} {{ loaded.used_by.join(", ") }}: the rename carries them along.</span>
        </div>

        <div class="row items-center no-wrap file-tabs">
          <q-tabs v-model="tab" dense no-caps inline-label align="left" active-color="primary" indicator-color="primary" class="text-grey-8 col-auto file-tabs__tabs" outside-arrows mobile-arrows>
            <q-tab v-for="file in files" :key="file.key" :name="file.key" class="file-tab" @dblclick="startRename(file)">
              <div class="row items-center no-wrap">
                <q-icon :name="file.text.trim() && looksLikeTagMap(file.text) ? 'fas fa-tags' : 'fas fa-file-code'" size="13px" class="q-mr-xs" />
                <input
                  v-if="renaming === file.key"
                  ref="renameInput"
                  v-model="renameText"
                  class="rename-input text-mono"
                  @keydown.enter.stop.prevent="finishRename(file)"
                  @keydown.esc.stop.prevent="renaming = null"
                  @blur="finishRename(file)"
                  @click.stop />
                <span v-else class="text-mono file-tab__name" :title="'Double-click to rename'">{{ file.name }}</span>
                <span v-if="file.text !== file.loadedText" class="dirty-dot" title="Changed" />
                <q-btn v-if="renaming !== file.key" flat round dense size="xs" icon="fas fa-pen" class="q-ml-xs tab-btn" aria-label="Rename the file" @click.stop="startRename(file)">
                  <q-tooltip>Rename</q-tooltip>
                </q-btn>
                <q-btn v-if="files.length > 1" flat round dense size="xs" icon="fas fa-times" class="tab-btn" aria-label="Remove the file" @click.stop="removeFile(file)">
                  <q-tooltip>Remove the file</q-tooltip>
                </q-btn>
              </div>
            </q-tab>
          </q-tabs>
          <q-btn flat dense no-caps color="primary" icon="fas fa-plus" label="File" class="q-ml-sm" aria-label="Add a file">
            <q-menu anchor="bottom left" self="top left" no-refocus>
              <q-list dense style="min-width: 220px">
                <q-item clickable v-close-popup @click="$refs.input.click()">
                  <q-item-section avatar><q-icon name="fas fa-upload" size="14px" /></q-item-section>
                  <q-item-section>Upload files…</q-item-section>
                </q-item>
                <q-item clickable v-close-popup @click="addEmpty">
                  <q-item-section avatar><q-icon name="fas fa-paste" size="14px" /></q-item-section>
                  <q-item-section>New file (paste)</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
          </q-btn>
          <input ref="input" type="file" multiple accept=".asn,.asn1,.txt,.ASN,.ASN1,.properties,.java" class="hidden" @change="picked" />
          <q-space />
          <div class="text-caption text-grey-7 q-ml-sm text-no-wrap">Drop files on the text to add them</div>
        </div>

        <div class="col relative-position editor-wrap" @dragenter.prevent="dragging = true" @dragover.prevent="dragging = true" @dragleave.self="dragging = false" @drop.prevent="dropped">
          <grammar-code-box
            v-if="currentFile"
            ref="code"
            :key="currentFile.key"
            v-model="currentFile.text"
            :language="looksLikeTagMap(currentFile.text) ? 'plain' : 'asn1'"
            :autofocus="currentFile.key === focusKey"
            placeholder-text="Paste ASN.1 modules or a tag map (props.put(&quot;82.0&quot;,&quot;recordType,integer,1&quot;); or 82.0=recordType,integer), or upload files" />
          <div v-if="dragging" class="drop-overlay absolute-full column flex-center">
            <q-icon name="fas fa-file-upload" size="40px" />
            <div class="q-mt-sm">Drop .asn files or tag maps to add them</div>
          </div>
        </div>

        <div v-if="error" class="text-caption text-negative save-error text-mono">{{ error }}</div>
      </q-card-section>

      <q-separator />
      <q-card-actions class="q-px-md q-py-sm">
        <div class="text-caption text-grey-7">The text is checked when saved; Ctrl+S saves.</div>
        <q-space />
        <q-btn flat color="primary" label="Cancel" @click="close" />
        <q-btn color="primary" label="Save" :loading="saving" :disable="loading || !canSave" @click="save" />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script>
import { api, notifyError } from "../../api";
import { toDateTimeString } from "../../utils/format";
import { looksLikeTagMap, readText } from "../../utils/asn1";
import GrammarCodeBox from "./GrammarCodeBox.vue";

const NAME_PATTERN = /^[A-Za-z0-9][A-Za-z0-9 ._()+-]{0,63}$/;
let nextKey = 1;

function fileEntry(name, text, loaded = true) {
  nextKey += 1;
  return { key: `f${nextKey}`, name, text, loadedText: loaded ? text : "" };
}

// Adds or edits an ASN.1 grammar (get-asn1-grammar, save-asn1-grammar): its name and its files, one tab each, typed or
// pasted into an editor, uploaded or dropped. The server reads the files when saved and names the file and line of an
// error, which selects that file. Editing under another name renames the grammar (its datasources follow it).
export default {
  name: "GrammarEditDialog",
  components: { GrammarCodeBox },
  props: {
    // The list is maximized: the editor opens maximized too.
    listMaximized: { type: Boolean, default: false },
  },
  emits: ["saved"],
  data() {
    return {
      visible: false,
      maximized: false,
      loading: false,
      saving: false,
      // add (also a duplicate) or edit; the edited grammar as loaded.
      mode: "add",
      oldName: null,
      loaded: null,
      name: "",
      files: [],
      tab: null,
      renaming: null,
      renameText: "",
      dragging: false,
      error: null,
      // The file whose editor takes the focus when built.
      focusKey: null,
    };
  },
  computed: {
    title() {
      return this.mode === "edit" ? `Edit grammar ${this.oldName}` : "Add ASN.1 grammar";
    },
    currentFile() {
      return this.files.find((file) => file.key === this.tab) || null;
    },
    kind() {
      const texts = this.files.map((file) => file.text).filter((text) => text.trim());
      return texts.length && texts.every((text) => looksLikeTagMap(text)) ? "tagmap" : "asn1";
    },
    kindTitle() {
      return this.kind === "tagmap" ? "Every file is a tag map of a Pentaho ASN.1 decoder: fields are named by tag path" : "ASN.1 modules: fields are named by the grammar's types";
    },
    savedFacts() {
      const loaded = this.loaded;
      return loaded.kind === "tagmap" ? `Saved: tag map of ${loaded.entries} entries` : `Saved: ${loaded.modules.join(", ")}`;
    },
    renamed() {
      return this.mode === "edit" && this.name.trim() !== this.oldName;
    },
    nameError() {
      const name = this.name.trim();
      if (!name) {
        return null;
      }
      return NAME_PATTERN.test(name) ? null : "1 to 64 letters, digits, spaces and ._()+-, starting with a letter or digit";
    },
    canSave() {
      return Boolean(this.name.trim()) && !this.nameError && this.files.some((file) => file.text.trim());
    },
  },
  methods: {
    toDateTimeString,
    looksLikeTagMap,
    reset() {
      this.loaded = null;
      this.error = null;
      this.renaming = null;
      this.dragging = false;
      this.saving = false;
      this.maximized = this.maximized || this.listMaximized;
    },
    openAdd() {
      this.reset();
      this.mode = "add";
      this.oldName = null;
      this.name = "";
      this.files = [fileEntry("grammar1.asn", "", true)];
      this.tab = this.files[0].key;
      this.focusKey = this.tab;
      this.visible = true;
    },
    openEdit(name) {
      this.open(name, "edit");
    },
    openDuplicate(name) {
      this.open(name, "duplicate");
    },
    async open(name, mode) {
      this.reset();
      this.mode = mode === "edit" ? "edit" : "add";
      this.oldName = mode === "edit" ? name : null;
      this.name = mode === "edit" ? name : `${name} (copy)`.slice(0, 64);
      this.files = [];
      this.loading = true;
      this.visible = true;
      try {
        const grammar = await api("get-asn1-grammar", { params: { name } });
        this.loaded = mode === "edit" ? grammar : null;
        this.files = grammar.files.map((file) => fileEntry(file.name, file.text, mode === "edit"));
        this.tab = this.files.length ? this.files[0].key : null;
      } catch (error) {
        notifyError(`The grammar ${name} was not read.`, error);
        this.visible = false;
      } finally {
        this.loading = false;
      }
    },
    close() {
      this.visible = false;
    },
    keydown(event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        if (this.canSave && !this.saving) {
          this.save();
        }
      }
    },
    uniqueName(name) {
      const names = new Set(this.files.map((file) => file.name));
      if (!names.has(name)) {
        return name;
      }
      const match = name.match(/^(.*?)(\.[^.]*)?$/);
      for (let index = 2; ; index += 1) {
        const candidate = `${match[1]} (${index})${match[2] || ""}`;
        if (!names.has(candidate)) {
          return candidate;
        }
      }
    },
    addEmpty() {
      const file = fileEntry(this.uniqueName(`grammar${this.files.length + 1}.asn`), "", false);
      this.files.push(file);
      this.focusKey = file.key;
      this.tab = file.key;
    },
    async addFiles(list) {
      let last = null;
      for (const upload of Array.from(list || [])) {
        const text = await readText(upload);
        // An empty untouched tab is taken by the first file.
        const blank = this.files.find((file) => !file.text && !file.loadedText);
        if (blank && this.files.length === 1) {
          blank.name = upload.name;
          blank.text = text;
          last = blank;
        } else {
          last = fileEntry(this.uniqueName(upload.name), text, false);
          this.files.push(last);
        }
      }
      if (last) {
        this.tab = last.key;
        if (!this.name.trim() && this.mode === "add") {
          this.name = last.name.replace(/\.[^.]*$/, "").slice(0, 64);
        }
      }
    },
    picked(event) {
      this.addFiles(event.target.files);
      event.target.value = "";
    },
    dropped(event) {
      this.dragging = false;
      this.addFiles(event.dataTransfer && event.dataTransfer.files);
    },
    startRename(file) {
      this.renaming = file.key;
      this.renameText = file.name;
      this.$nextTick(() => {
        const input = this.$refs.renameInput;
        const element = Array.isArray(input) ? input[0] : input;
        if (element) {
          element.focus();
          element.select();
        }
      });
    },
    finishRename(file) {
      if (this.renaming !== file.key) {
        return;
      }
      const name = this.renameText.trim();
      if (name && name !== file.name && !this.files.some((other) => other !== file && other.name === name)) {
        file.name = name;
      }
      this.renaming = null;
    },
    removeFile(file) {
      const drop = () => {
        const index = this.files.indexOf(file);
        this.files.splice(index, 1);
        if (this.tab === file.key) {
          this.tab = this.files[Math.max(index - 1, 0)].key;
        }
      };
      if (!file.text.trim()) {
        drop();
        return;
      }
      this.$q
        .dialog({
          title: "Remove the file?",
          message: `Remove ${file.name} from the grammar? It is gone once the grammar is saved.`,
          ok: { label: "Remove", color: "negative" },
          cancel: { label: "Cancel", flat: true },
          persistent: true,
        })
        .onOk(drop);
    },
    async save() {
      const name = this.name.trim();
      const files = this.files.filter((file) => file.text.trim()).map((file) => ({ name: file.name, text: file.text }));
      if (new Set(files.map((file) => file.name)).size !== files.length) {
        this.error = "Two files have the same name: rename one.";
        return;
      }
      this.saving = true;
      this.error = null;
      try {
        await api("save-asn1-grammar", { method: "POST", body: { name, files, old_name: this.mode === "edit" ? this.oldName : null } });
        this.$q.notify({ type: "positive", message: `Grammar ${name} saved.` });
        this.$emit("saved", { name, renamedFrom: this.renamed ? this.oldName : null });
        this.visible = false;
      } catch (error) {
        if (error.status === 400 || error.status === 409 || error.status === 413) {
          this.showError(error.message);
        } else {
          notifyError("The grammar was not saved.", error);
        }
      } finally {
        this.saving = false;
      }
    },
    // A parse error names the file and line: show that file there.
    showError(message) {
      this.error = message;
      const found = message.match(/can not be read: (.+?): .*?line (\d+)/);
      if (!found) {
        return;
      }
      const file = this.files.find((item) => item.name === found[1]);
      if (file) {
        this.tab = file.key;
        this.$nextTick(() => this.$refs.code && this.$refs.code.goToLine(Number(found[2])));
      }
    },
  },
};
</script>

<style scoped>
.grammar-edit__body {
  min-height: 0;
}
.name-input {
  width: 380px;
}
.kind-chip {
  margin-top: 4px;
}
/* A long module list takes two lines at most (all of it in the tooltip), so the editor keeps its height. */
.saved-facts {
  padding-top: 12px;
  max-width: 50%;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.file-tabs {
  border-bottom: 1px solid var(--rapo-panel-border);
}
.file-tabs__tabs {
  max-width: calc(100% - 320px);
}
.file-tab__name {
  font-size: 13px;
}
.tab-btn {
  opacity: 0.6;
}
.tab-btn:hover {
  opacity: 1;
}
.dirty-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  margin-left: 6px;
  background: var(--rapo-warn);
}
.rename-input {
  font-size: 13px;
  width: 180px;
  border: 1px solid var(--q-primary);
  border-radius: 3px;
  padding: 1px 4px;
  background: var(--rapo-surface);
  color: inherit;
}
.editor-wrap {
  min-height: 0;
}
.save-error {
  white-space: pre-wrap;
}
</style>
