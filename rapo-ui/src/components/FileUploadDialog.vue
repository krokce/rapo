<template>
  <q-dialog v-model="visible" :persistent="uploading" @hide="close">
    <q-card class="column no-wrap upload-card">
      <q-card-section class="row items-center no-wrap q-py-sm">
        <q-icon name="fas fa-upload" color="blue-grey-6" size="20px" class="q-mr-sm" />
        <div class="text-h6 col ellipsis">Upload files{{ check && check.sourcename ? ` to ${check.sourcename}` : "" }}</div>
        <q-btn aria-label="Close" flat round icon="fas fa-times" :disable="uploading" v-close-popup />
      </q-card-section>
      <q-separator />

      <q-card-section class="q-gutter-y-sm">
        <div v-if="check" class="row items-center no-wrap q-gutter-x-sm">
          <span class="text-grey-7">Into</span>
          <span class="text-mono ellipsis" :title="check.directory">{{ check.directory }}</span>
          <q-badge v-if="!check.exists" color="red-5" label="Missing" />
          <q-badge v-else-if="!check.writable" color="red-5" label="Not writable" />
          <q-space />
          <q-btn v-if="!check.exists" outline dense no-caps color="primary" icon="fas fa-folder-plus" label="Create directory" :loading="creating" @click="createDirectory" />
        </div>
        <q-banner v-if="check && !check.active" dense class="bg-orange-1 text-orange-10" rounded>
          <template #avatar><q-icon name="fas fa-pause-circle" color="orange-8" /></template>
          The datasource is disabled: PDI Core picks the files up once it is in a lane again.
        </q-banner>

        <div
          class="drop-zone column items-center justify-center text-grey-7"
          :class="{ 'drop-zone--over': dragOver }"
          v-keyboard:button
          @click="pickFiles"
          @dragover.prevent="dragOver = true"
          @dragleave="dragOver = false"
          @drop.prevent="dropped">
          <q-icon name="fas fa-cloud-upload-alt" size="28px" class="q-mb-xs" />
          <div>Drop files here or <span class="text-primary text-weight-medium">choose files</span></div>
          <div v-if="check" class="text-caption">At most {{ formatBytes(check.max_bytes) }} each; a file already waiting is not overwritten.</div>
        </div>
        <input ref="input" type="file" multiple class="hidden" @change="picked" />
      </q-card-section>

      <q-card-section v-if="items.length" class="col scroll q-pt-none">
        <q-list separator bordered class="rounded-borders">
          <q-item v-for="item in items" :key="item.key">
            <q-item-section avatar>
              <q-icon :name="itemIcon(item).name" :color="itemIcon(item).color" size="18px" />
            </q-item-section>
            <q-item-section>
              <q-item-label class="text-mono ellipsis" :title="item.name">{{ item.name }}</q-item-label>
              <q-item-label caption>
                {{ formatBytes(item.file.size) }}
                <span v-if="item.problem" class="text-red-7"> · {{ item.problem }}</span>
                <span v-else-if="item.error" class="text-red-7"> · {{ item.error }}</span>
                <span v-else-if="item.state === 'done'" class="text-positive"> · Uploaded</span>
                <span v-if="item.matches === false && !item.problem" class="text-orange-9"> · Does not match the file name pattern: PDI Core will not pick it up</span>
              </q-item-label>
              <q-linear-progress v-if="item.state === 'uploading'" :value="item.progress" color="primary" class="q-mt-xs" rounded />
            </q-item-section>
            <q-item-section side>
              <q-btn v-if="item.state !== 'done' && item.state !== 'uploading' && !uploading" aria-label="Remove" flat round dense size="sm" icon="fas fa-times" @click="remove(item)">
                <q-tooltip>Leave it out</q-tooltip>
              </q-btn>
            </q-item-section>
          </q-item>
        </q-list>
      </q-card-section>

      <q-separator />
      <q-card-actions align="right" class="q-px-md">
        <span v-if="ready.length" class="text-caption text-grey-7 q-mr-sm">{{ formatNumber(ready.length) }} file(s), {{ formatBytes(readyBytes) }}</span>
        <q-btn v-if="uploading" flat no-caps color="negative" label="Cancel" @click="cancel" />
        <q-btn v-else flat no-caps label="Close" v-close-popup />
        <q-btn
          unelevated
          no-caps
          color="primary"
          icon="fas fa-upload"
          :label="`Upload${ready.length ? ` (${formatNumber(ready.length)})` : ''}`"
          :disable="!ready.length || uploading || !check || !check.writable"
          :loading="uploading"
          @click="upload" />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script>
import { api, apiUpload, notifyError } from "../api";
import { formatBytes, formatNumber } from "../utils/format";

let nextKey = 0;

// Uploads files into the first input directory of a saved datasource (upload-ds-file), one at a time with its
// progress. check-ds-upload checks the names first: a file of the name already waiting is left out, one not matching
// the file name pattern is only flagged. The server writes a temporary file and renames it when complete.
export default {
  name: "FileUploadDialog",
  emits: ["uploaded"],
  data() {
    return {
      visible: false,
      datasourceId: null,
      check: null,
      items: [],
      dragOver: false,
      uploading: false,
      creating: false,
    };
  },
  computed: {
    ready() {
      return this.items.filter((item) => (item.state === "waiting" || item.state === "failed") && !item.problem);
    },
    readyBytes() {
      return this.ready.reduce((total, item) => total + item.file.size, 0);
    },
  },
  methods: {
    formatBytes,
    formatNumber,
    // A datasource ID and, from a drop, the files to start with.
    open(datasourceId, files = []) {
      this.datasourceId = datasourceId;
      this.check = null;
      this.items = [];
      this.visible = true;
      this.add(files);
      if (!files.length) {
        this.recheck();
      }
    },
    close() {
      this.cancel();
      this.items = [];
    },
    pickFiles() {
      if (!this.uploading) {
        this.$refs.input.click();
      }
    },
    picked(event) {
      this.add([...event.target.files]);
      event.target.value = "";
    },
    dropped(event) {
      this.dragOver = false;
      if (!this.uploading) {
        this.add([...event.dataTransfer.files]);
      }
    },
    add(files) {
      const known = new Set(this.items.filter((item) => item.state !== "done").map((item) => item.name));
      for (const file of files) {
        if (!known.has(file.name)) {
          known.add(file.name);
          this.items.push({ key: nextKey++, file, name: file.name, state: "waiting", progress: 0, problem: null, error: null, matches: null });
        }
      }
      if (files.length) {
        this.recheck();
      }
    },
    remove(item) {
      this.items = this.items.filter((other) => other !== item);
    },
    // The directory and, for each file waiting, why it can not be uploaded and whether the pattern matches it.
    async recheck() {
      try {
        const names = this.items.filter((item) => item.state === "waiting").map((item) => item.name);
        const check = await api("check-ds-upload", { method: "POST", body: { id: this.datasourceId, names }, loadingBar: false });
        this.check = check;
        const byName = new Map(check.files.map((file) => [file.name, file]));
        for (const item of this.items) {
          const result = byName.get(item.name);
          if (!result || item.state !== "waiting") {
            continue;
          }
          item.matches = result.matches_mask;
          item.problem = result.error
            ? result.error
            : result.exists
              ? "Already waiting in the input directory"
              : item.file.size > check.max_bytes
                ? `Larger than ${formatBytes(check.max_bytes)}`
                : null;
        }
      } catch (error) {
        notifyError("The files were not checked.", error);
      }
    },
    async createDirectory() {
      this.creating = true;
      try {
        await api("create-ds-directory", { method: "POST", params: { id: this.datasourceId, path: this.check.directory } });
        await this.recheck();
      } catch (error) {
        notifyError("The directory was not created.", error);
      } finally {
        this.creating = false;
      }
    },
    async upload() {
      this.uploading = true;
      this.canceled = false;
      let uploaded = 0;
      for (const item of this.ready) {
        if (this.canceled) {
          break;
        }
        item.state = "uploading";
        item.progress = 0;
        item.error = null;
        const request = apiUpload("upload-ds-file", {
          params: { id: this.datasourceId, name: item.name },
          file: item.file,
          onProgress: (loaded, total) => (item.progress = total ? loaded / total : 0),
        });
        this.abort = request.abort;
        try {
          await request.promise;
          item.state = "done";
          uploaded += 1;
        } catch (error) {
          item.state = error.aborted ? "waiting" : "failed";
          item.error = error.aborted ? null : error.message;
        }
      }
      this.abort = null;
      this.uploading = false;
      if (uploaded) {
        this.$q.notify({ type: "positive", message: `${formatNumber(uploaded)} file(s) uploaded into ${this.check.directory}.` });
        this.$emit("uploaded", uploaded);
      }
      this.recheck();
    },
    cancel() {
      this.canceled = true;
      if (this.abort) {
        this.abort();
      }
    },
    itemIcon(item) {
      if (item.state === "done") {
        return { name: "fas fa-check-circle", color: "positive" };
      }
      if (item.state === "failed" || item.problem) {
        return { name: "fas fa-times-circle", color: "red-5" };
      }
      if (item.matches === false) {
        return { name: "fas fa-exclamation-triangle", color: "orange-8" };
      }
      return { name: "far fa-file", color: "blue-grey-5" };
    },
  },
};
</script>

<style scoped>
.upload-card {
  width: 720px;
  max-width: 95vw;
  max-height: 85vh;
}
.drop-zone {
  min-height: 110px;
  border: 2px dashed var(--rapo-code-border);
  border-radius: 6px;
  cursor: pointer;
}
.drop-zone--over {
  border-color: var(--rapo-teal);
  background: var(--rapo-teal-soft);
}
</style>
