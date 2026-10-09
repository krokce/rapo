<template>
  <q-dialog v-model="visible" :maximized="maximized">
    <q-card class="column no-wrap" :style="maximized ? '' : 'width: 1200px; max-width: 95vw; height: 90vh'">
      <q-card-section class="row items-center q-py-sm no-wrap">
        <q-icon name="fas fa-book" size="sm" class="q-mr-sm text-blue-grey-7" />
        <div class="text-h6">ASN.1 grammars</div>
        <div class="q-ml-md text-caption text-grey-7">{{ countText }}</div>
        <q-space />
        <q-btn flat round :icon="maximized ? 'fas fa-compress' : 'fas fa-expand'" :aria-label="maximized ? 'Restore' : 'Maximize'" @click="maximized = !maximized">
          <q-tooltip>{{ maximized ? "Restore" : "Maximize" }}</q-tooltip>
        </q-btn>
        <q-btn aria-label="Close" flat round icon="fas fa-times" v-close-popup />
      </q-card-section>
      <q-separator />

      <q-card-section class="col column no-wrap q-gutter-y-sm grammar-list">
        <div class="text-caption text-grey-7">
          A grammar names the fields of a binary file and their types for the viewer's ASN.1 view: ASN.1 modules (TAP, RAP, NRTRDE, 3GPP TS 32.298 CDRs or a vendor's own;
          upload or paste all the modules it imports together), or the tag map of a Pentaho ASN.1 decoder (<span class="text-mono">props.put("82.4.1","nodeAddress,ia5,4");</span>
          lines or <span class="text-mono">82.4.1=nodeAddress,ia5</span>), which names fields by tag path and decodes values as the decoder does. A type a grammar lacks just
          leaves its fields unnamed.
        </div>
        <div class="row items-center q-gutter-sm">
          <q-input v-model="search" dense outlined clearable class="search-input" placeholder="Search name, file or module">
            <template #prepend><q-icon name="fas fa-search" size="14px" /></template>
          </q-input>
          <q-space />
          <q-btn unelevated no-caps color="primary" icon="fas fa-plus" label="Add grammar" @click="$refs.editor.openAdd()" />
        </div>

        <q-virtual-scroll
          type="table"
          class="col list-table grammar-table"
          :items="shownGrammars"
          :virtual-scroll-item-size="48"
          :virtual-scroll-sticky-size-start="28"
          :table-colspan="7">
          <template #before>
            <thead>
              <tr class="bg-blue-grey-2">
                <th class="text-left" title="The grammar's name, picked in the viewer; click a row to edit the grammar">Name</th>
                <th class="text-left" title="ASN.1 modules, or the tag map of a Pentaho ASN.1 decoder">Kind</th>
                <th class="text-left" title="The files of the grammar">Files</th>
                <th class="text-left" title="The ASN.1 modules the files define, or the entries of a tag map">Modules</th>
                <th class="text-left" title="The datasources whose files the viewer opens with this grammar (Save for datasource)">Used by</th>
                <th class="text-left" title="When the grammar was last saved (database clock)">Updated</th>
                <th class="text-left"></th>
              </tr>
            </thead>
          </template>
          <template #default="{ item: grammar }">
            <tr :key="grammar.name" class="clickable-row" @click="$refs.editor.openEdit(grammar.name)">
              <td class="text-left text-weight-bold">{{ grammar.name }}</td>
              <td class="text-left">
                <q-chip :title="grammar.kind === 'tagmap' ? 'Tag map of a Pentaho ASN.1 decoder' : 'ASN.1 modules'">
                  <q-avatar :icon="grammar.kind === 'tagmap' ? 'fas fa-tags' : 'fas fa-sitemap'" color="blue-grey-6" text-color="white" />
                  {{ grammar.kind === "tagmap" ? "Tag map" : "ASN.1" }}
                </q-chip>
              </td>
              <td class="text-left text-mono cell-wrap" :title="filesTitle(grammar)">{{ shortList(grammar.files.map((file) => file.name)) }}</td>
              <td class="text-left text-grey-8 cell-wrap">
                <template v-if="grammar.kind === 'tagmap'">{{ formatNumber(grammar.entries) }} entries</template>
                <template v-else>
                  <span :title="grammar.modules.join(', ')">{{ shortList(grammar.modules) }}</span>
                  <q-icon v-if="grammar.wrapped.length" name="fas fa-info-circle" color="blue-grey-5" size="12px">
                    <q-tooltip>Without a module header (read as IMPLICIT TAGS): {{ grammar.wrapped.join(", ") }}</q-tooltip>
                  </q-icon>
                </template>
              </td>
              <td class="text-left">
                <span v-if="grammar.used_by.length">{{ grammar.used_by.join(", ") }}</span>
                <span v-else class="text-grey-7">&ndash;</span>
              </td>
              <td class="text-left text-grey-8">{{ toDateTimeString(grammar.updated_date) }}</td>
              <td @click.stop>
                <q-btn aria-label="Row actions" size="sm" color="grey-7" round flat icon="fas fa-ellipsis-v" @click="openRowMenu($event, grammar)" />
              </td>
            </tr>
          </template>
          <template #after>
            <tbody v-if="loading && !grammars.length">
              <skeleton-rows :rows="5" :columns="['text', 'QChip', 'text', 'text', 'text', 'text', null]" />
            </tbody>
            <tbody v-else-if="!shownGrammars.length">
              <tr>
                <td colspan="7" class="text-center text-grey-7 q-pa-lg">
                  {{ grammars.length ? "No grammar matches the search" : "No grammar yet: Add grammar to paste or upload one." }}
                </td>
              </tr>
            </tbody>
          </template>
        </q-virtual-scroll>
      </q-card-section>
    </q-card>

    <q-menu v-if="menuTarget" ref="rowMenu" :target="menuTarget" no-parent-event>
      <q-list v-if="menuGrammar" dense class="text-no-wrap">
        <q-item clickable v-close-popup @click="$refs.editor.openEdit(menuGrammar.name)">
          <q-item-section> Edit grammar </q-item-section>
        </q-item>
        <q-item clickable v-close-popup @click="$refs.editor.openDuplicate(menuGrammar.name)">
          <q-item-section> Duplicate </q-item-section>
        </q-item>
        <q-item clickable v-close-popup @click="download(menuGrammar)">
          <q-item-section> Download </q-item-section>
        </q-item>
        <q-separator />
        <q-item v-if="menuGrammar.used_by.length" dense disable>
          <q-item-section> Delete grammar </q-item-section>
          <q-tooltip anchor="top middle" self="bottom middle">Used by datasource {{ menuGrammar.used_by.join(", ") }}</q-tooltip>
        </q-item>
        <q-item v-else clickable v-close-popup @click="remove(menuGrammar)">
          <q-item-section class="text-negative"> Delete grammar </q-item-section>
        </q-item>
      </q-list>
    </q-menu>
    <grammar-edit-dialog ref="editor" @saved="saved" />
  </q-dialog>
</template>

<script>
import { api, notifyError } from "../../api";
import { downloadBlob, escapeHtml, formatBytes, formatNumber, toDateTimeString } from "../../utils/format";
import SkeletonRows from "../SkeletonRows.vue";
import GrammarEditDialog from "./GrammarEditDialog.vue";

// The uploaded ASN.1 grammars (get-asn1-grammars), listed like the app's other lists: a row opens the grammar in
// GrammarEditDialog, which also adds one (pasted or uploaded); the row menu duplicates, downloads (the files one after
// another in one file) or deletes one no datasource uses. Emits `changed` with the name saved or deleted, and
// `{renamedFrom}` when a grammar was renamed.
export default {
  name: "GrammarDialog",
  components: { GrammarEditDialog, SkeletonRows },
  emits: ["changed"],
  data() {
    return {
      visible: false,
      maximized: false,
      loading: false,
      grammars: [],
      search: "",
      menuTarget: null,
      menuGrammar: null,
    };
  },
  computed: {
    shownGrammars() {
      const needle = (this.search || "").trim().toLowerCase();
      if (!needle) {
        return this.grammars;
      }
      return this.grammars.filter((grammar) =>
        [grammar.name, ...grammar.files.map((file) => file.name), ...grammar.modules].some((text) => text.toLowerCase().includes(needle))
      );
    },
    countText() {
      const total = this.grammars.length;
      const shown = this.shownGrammars.length;
      const noun = `grammar${total === 1 ? "" : "s"}`;
      return shown === total ? `${formatNumber(total)} ${noun}` : `${formatNumber(shown)} of ${formatNumber(total)} ${noun}`;
    },
  },
  methods: {
    formatNumber,
    toDateTimeString,
    open() {
      this.visible = true;
      this.search = "";
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
    // At most three names, then how many more (all of them in the cell's tooltip).
    shortList(names) {
      return names.length > 3 ? `${names.slice(0, 3).join(", ")} +${names.length - 3} more` : names.join(", ");
    },
    filesTitle(grammar) {
      return grammar.files.map((file) => `${file.name} (${formatBytes(file.size)})`).join(", ");
    },
    openRowMenu(event, grammar) {
      this.menuTarget = event.currentTarget;
      this.menuGrammar = grammar;
      this.$nextTick(() => this.$refs.rowMenu.show());
    },
    async saved({ name, renamedFrom }) {
      await this.load();
      this.$emit("changed", name, { renamedFrom });
    },
    async download(grammar) {
      try {
        const loaded = await api("get-asn1-grammar", { params: { name: grammar.name } });
        const text = loaded.files.map((file) => (loaded.files.length > 1 ? `-- ${file.name}\n${file.text}` : file.text)).join("\n\n");
        const extension = loaded.kind === "tagmap" ? "properties" : "asn";
        downloadBlob(new Blob([text], { type: "text/plain" }), `${grammar.name}.${extension}`);
      } catch (error) {
        notifyError(`The grammar ${grammar.name} was not downloaded.`, error);
      }
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
          try {
            await api("delete-asn1-grammar", { method: "POST", params: { name: grammar.name } });
            this.$q.notify({ type: "positive", message: `Grammar ${grammar.name} deleted.` });
            await this.load();
            this.$emit("changed", null, {});
          } catch (error) {
            notifyError(`Deleting the grammar ${grammar.name} failed.`, error);
          }
        });
    },
  },
};
</script>

<style scoped>
.grammar-list {
  min-height: 0;
}
.search-input {
  width: 320px;
}
.grammar-table {
  min-height: 0;
}
.cell-wrap {
  white-space: normal;
  word-break: break-word;
  max-width: 320px;
}
</style>
