<template>
  <q-dialog v-model="visible">
    <q-card class="column no-wrap" style="width: 1000px; max-width: 95vw; max-height: 90vh">
      <q-card-section class="row items-center q-py-sm">
        <q-icon name="fas fa-book" color="blue-grey-6" size="20px" class="q-mr-sm" />
        <div class="text-h6">ASN.1 grammars</div>
        <q-space />
        <q-btn aria-label="Close" flat round icon="fas fa-times" v-close-popup />
      </q-card-section>
      <q-separator />

      <q-card-section class="col scroll">
        <div class="text-grey-7 q-mb-md">
          A grammar is one or more ASN.1 modules (.asn files) that name the fields of a file and their types: TAP and RAP (GSMA TD.57, TD.32), NRTRDE (TD.35), 3GPP TS 32.298 CDRs
          or a vendor's own. Upload all the modules it imports in one grammar; a type the grammar lacks just leaves its fields unnamed. A file of type assignments only, without a
          module header, is read as one module with IMPLICIT TAGS.
        </div>

        <div class="row items-start q-gutter-sm q-mb-md upload-row">
          <q-input v-model="newName" dense outlined label="Grammar name" class="col-3" :error="Boolean(nameError)" :error-message="nameError" hide-bottom-space />
          <q-btn outline no-caps color="primary" icon="fas fa-folder-open" label="Choose .asn files" class="pick-btn" @click="$refs.input.click()" />
          <input ref="input" type="file" multiple accept=".asn,.asn1,.txt,.ASN,.ASN1" class="hidden" @change="picked" />
          <div class="col text-caption text-grey-8 picked">
            <template v-if="files.length">{{ files.map((file) => `${file.name} (${formatBytes(file.size)})`).join(", ") }}</template>
            <template v-else>No files chosen</template>
          </div>
          <q-btn unelevated no-caps color="primary" icon="fas fa-upload" label="Upload" class="pick-btn" :loading="saving" :disable="!files.length || !newName.trim()" @click="upload(false)" />
        </div>
        <q-banner v-if="uploadError" dense rounded class="bg-red-1 text-red-10 q-mb-md upload-error">
          <template #avatar><q-icon name="fas fa-exclamation-circle" color="red-7" /></template>
          <span class="text-mono">{{ uploadError }}</span>
        </q-banner>

        <div v-if="loading && !grammars.length" class="text-grey-7">Reading…</div>
        <div v-else-if="!grammars.length" class="text-grey-7">No grammar uploaded yet.</div>
        <q-markup-table v-else dense flat bordered separator="horizontal">
          <thead>
            <tr>
              <th class="text-left" title="The grammar's name, picked in the viewer">Name</th>
              <th class="text-left" title="The .asn files of the grammar">Files</th>
              <th class="text-left" title="The ASN.1 modules they define">Modules</th>
              <th class="text-left" title="The datasources whose files the viewer decodes with it">Used by</th>
              <th class="text-left" title="When the grammar was last uploaded">Updated</th>
              <th style="width: 180px"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="grammar in grammars" :key="grammar.name">
              <td class="text-weight-medium">{{ grammar.name }}</td>
              <td class="text-grey-8 text-mono cell-wrap">{{ grammar.files.map((file) => file.name).join(", ") }}</td>
              <td class="text-grey-8 cell-wrap">
                {{ grammar.modules.join(", ") }}
                <q-icon v-if="grammar.wrapped.length" name="fas fa-info-circle" color="blue-grey-5" size="12px">
                  <q-tooltip>Without a module header (read as IMPLICIT TAGS): {{ grammar.wrapped.join(", ") }}</q-tooltip>
                </q-icon>
              </td>
              <td class="text-grey-8">{{ grammar.used_by.length ? grammar.used_by.join(", ") : "–" }}</td>
              <td class="text-grey-8">{{ toDateTimeString(grammar.updated_date) }}</td>
              <td class="text-right">
                <q-btn flat dense no-caps size="sm" color="primary" label="Replace files" :disable="saving" @click="startReplace(grammar)">
                  <q-tooltip>Choose new files for this grammar, then Upload</q-tooltip>
                </q-btn>
                <q-btn flat dense no-caps size="sm" color="negative" label="Delete" :disable="saving || grammar.used_by.length > 0" @click="remove(grammar)">
                  <q-tooltip v-if="grammar.used_by.length">Used by datasource {{ grammar.used_by.join(", ") }}</q-tooltip>
                </q-btn>
              </td>
            </tr>
          </tbody>
        </q-markup-table>
      </q-card-section>
    </q-card>
  </q-dialog>
</template>

<script>
import { api, notifyError } from "../../api";
import { escapeHtml, formatBytes, toDateTimeString } from "../../utils/format";

// Reads a file as text: UTF-8, else Windows-1252 (any byte is a character), as .asn files of other tools are.
async function readText(file) {
  const buffer = await file.arrayBuffer();
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(buffer);
  } catch {
    return new TextDecoder("windows-1252").decode(buffer);
  }
}

// The uploaded ASN.1 grammars (get-asn1-grammars): upload one (save-asn1-grammar, parsed on the server first, which
// names the file and line of an error), replace its files, delete one no datasource uses. Emits `changed` with the
// name saved or deleted.
export default {
  name: "GrammarDialog",
  emits: ["changed"],
  data() {
    return {
      visible: false,
      loading: false,
      saving: false,
      grammars: [],
      newName: "",
      files: [],
      uploadError: null,
    };
  },
  computed: {
    nameError() {
      const name = this.newName.trim();
      if (name && !/^[A-Za-z0-9][A-Za-z0-9 ._()+-]{0,63}$/.test(name)) {
        return "1 to 64 letters, digits, spaces and ._()+-";
      }
      return null;
    },
  },
  methods: {
    formatBytes,
    toDateTimeString,
    open() {
      this.visible = true;
      this.files = [];
      this.newName = "";
      this.uploadError = null;
      this.load();
    },
    async load() {
      this.loading = true;
      try {
        this.grammars = (await api("get-asn1-grammars", { loadingBar: false })).grammars;
      } catch (error) {
        notifyError("The grammars were not read.", error);
      } finally {
        this.loading = false;
      }
    },
    picked(event) {
      this.files = Array.from(event.target.files || []);
      this.uploadError = null;
      if (!this.newName.trim() && this.files.length) {
        this.newName = this.files[0].name.replace(/\.[^.]*$/, "").slice(0, 64);
      }
      event.target.value = "";
    },
    startReplace(grammar) {
      this.newName = grammar.name;
      this.uploadError = null;
      this.$refs.input.click();
    },
    async upload(replace) {
      const name = this.newName.trim();
      if (!name || this.nameError || !this.files.length) {
        return;
      }
      this.saving = true;
      this.uploadError = null;
      try {
        const files = [];
        for (const file of this.files) {
          files.push({ name: file.name, text: await readText(file) });
        }
        const result = await api("save-asn1-grammar", { method: "POST", body: { name, files, replace } });
        this.$q.notify({ type: "positive", message: `Grammar ${name} saved: ${result.modules.join(", ")}` });
        this.files = [];
        this.newName = "";
        await this.load();
        this.$emit("changed", name);
      } catch (error) {
        if (error.status === 409 && !replace) {
          this.confirmReplace(name);
        } else if (error.status === 400 || error.status === 413) {
          this.uploadError = error.message;
        } else {
          notifyError("The grammar was not saved.", error);
        }
      } finally {
        this.saving = false;
      }
    },
    confirmReplace(name) {
      this.$q
        .dialog({
          title: "Replace the grammar?",
          message: `<div>${escapeHtml(`A grammar ${name} exists already. Replace its files with the chosen ones?`)}</div>`,
          html: true,
          ok: { label: "Replace", color: "primary" },
          cancel: { label: "Cancel", flat: true },
          persistent: true,
        })
        .onOk(() => this.upload(true));
    },
    remove(grammar) {
      this.$q
        .dialog({
          title: "Delete the grammar?",
          message: `<div>${escapeHtml(`Delete the grammar ${grammar.name} (${grammar.files.map((file) => file.name).join(", ")})?`)}</div>`,
          html: true,
          ok: { label: "Delete", color: "negative" },
          cancel: { label: "Cancel", flat: true },
          persistent: true,
        })
        .onOk(async () => {
          this.saving = true;
          try {
            await api("delete-asn1-grammar", { method: "POST", params: { name: grammar.name } });
            this.$q.notify({ type: "positive", message: `Grammar ${grammar.name} deleted.` });
            await this.load();
            this.$emit("changed", null);
          } catch (error) {
            notifyError(`Deleting the grammar ${grammar.name} failed.`, error);
          } finally {
            this.saving = false;
          }
        });
    },
  },
};
</script>

<style scoped>
.upload-row {
  flex-wrap: wrap;
}
.pick-btn {
  height: 40px;
}
.picked {
  min-width: 160px;
  padding-top: 10px;
}
.cell-wrap {
  white-space: normal;
  word-break: break-word;
}
.upload-error {
  white-space: pre-wrap;
}
</style>
