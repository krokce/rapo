<template>
  <q-page>
    <div v-if="!ready">
      <h2 class="row items-center q-mb-lg">
        <q-skeleton type="QChip" width="90px" height="50px" class="q-mr-md" />
        <q-skeleton type="text" width="420px" height="60px" />
      </h2>
      <editor-skeleton :rows="3" />
    </div>
    <div v-else>
      <!-- The chip shows the lane as saved, not the one being picked. -->
      <h2 class="row items-center q-mb-lg">
        <q-chip size="xl" :title="savedLane.label">
          <q-avatar :icon="savedLane.icon" :color="savedLane.color" text-color="white" class="type-avatar" />
          <span class="text-weight-bold">{{ savedLane.short }}</span>
        </q-chip>
        &nbsp;
        {{ saved ? saved.sourcename : "New datasource" }}
      </h2>

      <q-banner v-if="!writable" dense rounded class="bg-grey-3 q-mb-md">
        <template #avatar><q-icon name="fas fa-lock" size="16px" /></template>
        This database user may read the datasources, but not change them.
      </q-banner>

      <q-card>
        <q-tabs
          v-model="tab"
          class="text-white"
          :class="'bg-' + (datasource.isactive ? 'blue-grey-7' : 'grey-7')"
          active-color="light-blue-1"
          indicator-color="light-blue-1"
          align="justify"
          inline-label
          narrow-indicator
          no-caps>
          <q-tab name="main" label="Main" icon="fas fa-window-maximize" />
          <q-tab name="files" label="Input files" icon="fas fa-folder-open" />
          <q-tab name="processing" label="Processing" icon="fas fa-cogs" />
          <q-tab name="archive" label="Archive" icon="fas fa-archive" />
          <q-tab name="retention" :label="`Retention (${datasource.links.length})`" icon="fas fa-history" />
          <q-tab v-if="saved && logAvailable" name="log" label="File log" icon="fas fa-file-medical-alt" />
        </q-tabs>

        <q-separator />

        <q-form ref="form" @submit="persist('stay')" @reset="cancel" @validation-error="validationError">
          <q-tab-panels v-model="tab" animated keep-alive>
            <q-tab-panel name="main">
              <div class="q-ma-lg q-gutter-y-md">
                <div class="row q-gutter-md">
                  <q-input
                    class="col"
                    outlined
                    v-model="datasource.sourcename"
                    label="Source name"
                    maxlength="50"
                    counter
                    :rules="[(value) => !!value || 'Required', (value) => /^[A-Z0-9_]+$/.test(value) || 'Letters, digits and underscores']"
                    @update:model-value="(value) => (datasource.sourcename = (value || '').toUpperCase())" />
                  <q-select
                    class="col-3"
                    outlined
                    v-model="datasource.isactive"
                    emit-value
                    map-options
                    :options="laneOptions"
                    label="ISACTIVE (scheduler lane)">
                    <template #prepend>
                      <q-avatar size="26px" :icon="lane(datasource.isactive).icon" :color="lane(datasource.isactive).color" text-color="white" />
                    </template>
                    <template #option="scope">
                      <q-item v-bind="scope.itemProps">
                        <q-item-section avatar>
                          <q-avatar size="26px" :icon="lane(scope.opt.value).icon" :color="lane(scope.opt.value).color" text-color="white" />
                        </q-item-section>
                        <q-item-section>
                          <q-item-label>{{ scope.opt.label }}</q-item-label>
                          <q-item-label caption>{{ scope.opt.caption }}</q-item-label>
                        </q-item-section>
                      </q-item>
                    </template>
                  </q-select>
                  <q-input class="col-1" outlined readonly :model-value="datasource.id || 'new'" label="ID" />
                </div>
                <div class="text-caption text-grey-7">
                  The source name is the name of the PDI transformation in /public/core/load_file/datasources that loads the files, and the default
                  table a RECYCLE or DELETE cleans. It is also written to PDI_CORE_FILE_LOG, which holds 50 characters. ISACTIVE is the SCHEDULER_ID
                  of the core_load job that processes the datasource, e.g. lanes for light, large and huge files; 0 disables it, and then neither its
                  files are loaded nor its retention runs.
                </div>
                <div v-if="cloneNotice" class="text-caption text-orange-9">
                  <q-icon name="fas fa-info-circle" /> {{ cloneNotice }}
                </div>
              </div>
            </q-tab-panel>

            <q-tab-panel name="files">
              <div class="q-ma-lg q-gutter-y-md">
                <div class="row items-center q-gutter-sm">
                  <div class="text-subtitle1 text-weight-medium">Input directories</div>
                  <q-space />
                  <template v-if="saved">
                    <q-btn outline dense no-caps color="primary" icon="fas fa-filter" label="Matching files" padding="4px 10px" @click="openFiles('match')">
                      <q-tooltip>The files FILES_MASK picks up in the saved directories, with the masks as edited here</q-tooltip>
                    </q-btn>
                    <q-btn outline dense no-caps color="primary" icon="fas fa-folder-open" label="All files" padding="4px 10px" @click="openFiles('all')">
                      <q-tooltip>Every file in the saved directories and their subdirectories, with why it is or is not picked up</q-tooltip>
                    </q-btn>
                  </template>
                </div>
                <directory-list-box
                  v-model="datasource"
                  field="input_directory"
                  label="INPUT_DIRECTORY"
                  multiple
                  :states="directoryStates"
                  :can-create="writable && !!saved"
                  @create="createDirectory" />
                <div class="text-caption text-grey-7">
                  PDI Core scans every directory for files matching FILES_MASK and passes them to the transformation. The user of the Pentaho server
                  needs read and write access; PDI Core creates a missing directory itself on its first scan of an active datasource.
                </div>

                <div class="row q-gutter-md items-start">
                  <q-input
                    class="col"
                    outlined
                    v-model="datasource.files_mask"
                    label="FILES_MASK (regular expression)"
                    maxlength="4000"
                    input-class="text-mono"
                    :rules="[(value) => !!value || 'Required']"
                    :hint="maskHint"
                    @update:model-value="scheduleMaskCheck" />
                  <q-toggle
                    class="col-2"
                    v-model="datasource.input_scan_subdirs"
                    :true-value="1"
                    :false-value="0"
                    label="Scan subdirectories"
                    @update:model-value="scheduleMaskCheck" />
                  <q-input
                    class="col-2"
                    outlined
                    type="number"
                    v-model.number="datasource.files_max_per_cycle"
                    label="Max files per cycle"
                    :rules="[(value) => (Number.isInteger(value) && value >= 1) || '1 or more']" />
                </div>
                <div class="text-caption text-grey-7">
                  The whole file name must match (like Java's matches() in PDI Core), e.g. <code>^U(?!.*FIN).*</code>. A file modified in the last 60 s
                  waits for the next cycle. Max files per cycle bounds one run of core_load, which typically runs every minute.
                </div>

                <div class="row q-gutter-md items-start">
                  <q-input
                    class="col"
                    outlined
                    clearable
                    v-model="datasource.input_clean_files_mask"
                    label="INPUT_CLEAN_FILES_MASK (regular expression)"
                    maxlength="2000"
                    input-class="text-mono"
                    :hint="cleanHint"
                    @update:model-value="scheduleMaskCheck" />
                  <q-btn
                    v-if="saved"
                    outline
                    dense
                    no-caps
                    color="primary"
                    icon="fas fa-broom"
                    label="Clean-up files"
                    class="field-button"
                    :disable="!datasource.input_clean_files_mask"
                    @click="openFiles('clean')">
                    <q-tooltip>The small files INPUT_CLEAN_FILES_MASK names, e.g. the FIN markers of completed transfers</q-tooltip>
                  </q-btn>
                </div>
                <div class="text-caption text-grey-7">
                  The core maintenance job deletes the files of the input directories matching it and smaller than 10 bytes, e.g. <code>^U.*FIN$</code>.
                </div>
              </div>
            </q-tab-panel>

            <q-tab-panel name="processing">
              <div class="q-ma-lg q-gutter-y-md">
                <div class="text-subtitle1 text-weight-medium">Duplicate handling (FILES_DUP_HANDLING)</div>
                <q-option-group v-model="datasource.files_dup_handling" :options="dupOptions" type="radio">
                  <template #label="option">
                    <div>
                      <span class="text-weight-medium">{{ option.label }}</span>
                      <span class="text-grey-7"> &ndash; {{ option.description }}</span>
                    </div>
                  </template>
                </q-option-group>
                <q-separator />
                <div class="row q-gutter-md items-start">
                  <q-toggle class="col" v-model="datasource.leave_input_zipped" :true-value="1" :false-value="0" label="Leave input zipped (LEAVE_INPUT_ZIPPED)" />
                  <q-toggle class="col" v-model="datasource.files_load_parallel" :true-value="1" :false-value="0" label="Load files in parallel (FILES_LOAD_PARALLEL)" />
                  <q-input
                    class="col-3"
                    outlined
                    type="number"
                    v-model.number="datasource.max_recordsreject"
                    label="Max rejected records (MAX_RECORDSREJECT)"
                    :rules="[(value) => (Number.isInteger(value) && value >= 0) || '0 or more']" />
                </div>
                <div class="text-caption text-grey-7">
                  Leave input zipped when the transformation expects gzipped files. Load in parallel unless the transformation truncates a table or
                  similar; the number of parallel files is set in core_load_file_process. A file rejecting more records than the maximum ends in ERROR
                  and its loaded records are deleted.
                </div>
              </div>
            </q-tab-panel>

            <q-tab-panel name="archive">
              <div class="q-ma-lg q-gutter-y-md">
                <directory-list-box
                  v-for="field in archiveFields"
                  :key="field.name"
                  v-model="datasource"
                  :field="field.name"
                  :label="field.label"
                  :states="directoryStates"
                  :can-create="writable && !!saved"
                  @create="createDirectory" />
                <div class="text-caption text-grey-7">
                  Processed files are gzipped (unless they are) and moved to the archive directory, failed ones to the error directory, duplicates to
                  the duplicate directory, each in a subdirectory per day (YYYYMMDD).
                </div>
                <q-input
                  class="col-3"
                  style="max-width: 300px"
                  outlined
                  type="number"
                  v-model.number="datasource.files_retention_days"
                  label="Days files are kept (FILES_RETENTION_DAYS)"
                  :rules="[(value) => (Number.isInteger(value) && value >= 0) || '0 or more']" />
              </div>
            </q-tab-panel>

            <q-tab-panel name="retention">
              <div class="q-ma-lg">
                <datasource-tables-box
                  v-model="datasource"
                  :tables="tableNames"
                  :saved-tables="saved ? saved.links.map((link) => link.table_name) : []"
                  :can-delete="deletable || !saved" />
              </div>
            </q-tab-panel>

            <q-tab-panel v-if="saved && logAvailable" name="log">
              <div class="q-ma-lg">
                <file-log-table :datasource-id="saved.id" embedded />
              </div>
            </q-tab-panel>
          </q-tab-panels>

          <div class="editor-actions row items-center q-gutter-sm q-px-lg q-py-sm">
            <template v-if="writable">
              <q-btn label="Save" color="primary" :loading="saving" @click="persist('close')">
                <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">Save and return to the datasources</q-tooltip>
              </q-btn>
              <q-btn label="Apply" color="primary" outline :disable="!dirty || saving" @click="persist('stay')">
                <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">Save and keep editing (Ctrl+S)</q-tooltip>
              </q-btn>
            </template>
            <q-btn :label="writable ? 'Cancel' : 'Close'" type="reset" color="primary" flat />
            <q-space />
            <div v-if="dirty" class="text-orange-9 text-weight-medium row items-center no-wrap cursor-pointer" @click="diffVisible = true">
              <q-icon name="fas fa-circle" size="8px" class="q-mr-sm" />
              Unsaved changes
              <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 5]">Show what Apply will change</q-tooltip>
            </div>
          </div>
        </q-form>
      </q-card>
    </div>

    <q-dialog v-model="diffVisible">
      <q-card style="width: 1000px; max-width: 95vw">
        <q-card-section class="row items-center q-py-sm">
          <div class="text-h6">Unsaved changes ({{ unsavedChanges.length }})</div>
          <q-space />
          <q-btn flat round icon="close" v-close-popup />
        </q-card-section>
        <q-separator />
        <q-card-section class="scroll" style="max-height: 70vh">
          <diff-table :rows="unsavedChanges" empty-text="No changes." />
        </q-card-section>
      </q-card>
    </q-dialog>

    <file-list-dialog ref="fileDialog" />
  </q-page>
</template>

<script>
import { mapActions, mapGetters, mapState } from "vuex";
import DatasourceTablesBox from "./DatasourceTablesBox.vue";
import DiffTable from "./DiffTable.vue";
import DirectoryListBox from "./DirectoryListBox.vue";
import EditorSkeleton from "./EditorSkeleton.vue";
import FileListDialog from "./FileListDialog.vue";
import FileLogTable from "./FileLogTable.vue";
import { api, notifyError } from "../api";
import { DATASOURCE_LANES, DUP_HANDLING_OPTIONS, datasourceLane } from "../constants";
import { diffControl } from "../utils/controlDiff";
import { datasourcePayload, diffShape, emptyDatasource } from "../utils/datasources";
import { escapeHtml, formatNumber } from "../utils/format";

const ARCHIVE_FIELDS = [
  { name: "archive_directory", label: "ARCHIVE_DIRECTORY" },
  { name: "error_directory", label: "ERROR_DIRECTORY" },
  { name: "duplicate_directory", label: "DUPLICATE_DIRECTORY" },
];

// One PDI Core datasource (a pdi_core_ds_config row) and its tables (pdi_core_ds_tables). The form is a copy of the
// saved datasource, which is also the lock of a save: a datasource changed meanwhile, by anyone, is not overwritten.
export default {
  name: "EditDatasource",
  components: { DatasourceTablesBox, DiffTable, DirectoryListBox, EditorSkeleton, FileListDialog, FileLogTable },
  props: ["id"],
  data() {
    return {
      ready: false,
      tab: "main",
      datasource: emptyDatasource(),
      // The datasource as saved (get-ds-config or save-ds-config), null for a new one.
      saved: null,
      savedJson: null,
      directoryStates: [],
      tableNames: [],
      saving: false,
      diffVisible: false,
      cloneNotice: null,
      maskCheck: null,
      maskChecking: false,
      archiveFields: ARCHIVE_FIELDS,
      dupOptions: DUP_HANDLING_OPTIONS,
    };
  },
  computed: {
    ...mapState(["datasourceCatalogue"]),
    ...mapGetters(["getEnvInfo"]),
    writable() {
      return Boolean(this.getEnvInfo && this.getEnvInfo.datasources_writable);
    },
    deletable() {
      return Boolean(this.getEnvInfo && this.getEnvInfo.datasources_deletable);
    },
    logAvailable() {
      return Boolean(this.getEnvInfo && this.getEnvInfo.datasources_log);
    },
    savedLane() {
      return datasourceLane(this.saved ? this.saved.isactive : this.datasource.isactive);
    },
    // Every lane, with how many other datasources it has.
    laneOptions() {
      const counts = new Map();
      this.datasourceCatalogue.filter((row) => row.id !== this.datasource.id).forEach((row) => counts.set(row.isactive, (counts.get(row.isactive) || 0) + 1));
      return DATASOURCE_LANES.map((value) => ({
        value,
        label: datasourceLane(value).label,
        caption: counts.get(value) ? `${counts.get(value)} other datasource(s)` : value === 0 ? "Not processed" : "No datasource yet",
      }));
    },
    dirty() {
      if (!this.ready || !this.writable) {
        return false;
      }
      return this.savedJson === null || JSON.stringify(datasourcePayload(this.datasource)) !== this.savedJson;
    },
    unsavedChanges() {
      return diffControl(JSON.stringify(diffShape(this.saved || emptyDatasource())), diffShape(this.datasource));
    },
    maskHint() {
      if (!this.saved) {
        return "Save the datasource to try the mask on its directories";
      }
      const check = this.maskCheck;
      if (this.maskChecking && !check) {
        return "Reading the directories...";
      }
      if (!check) {
        return undefined;
      }
      if (check.mask_error) {
        return `Not a valid regular expression: ${check.mask_error}`;
      }
      const missing = check.directories.filter((directory) => !directory.exists).length;
      return `Matches ${formatNumber(check.matched)} of ${formatNumber(check.total)} file(s)${check.truncated ? " (read partly)" : ""}${
        missing ? `; ${missing} directory(ies) missing on this server` : ""
      }`;
    },
    cleanHint() {
      const check = this.maskCheck;
      if (!this.saved || !check || !this.datasource.input_clean_files_mask) {
        return undefined;
      }
      if (check.clean_mask_error) {
        return `Not a valid regular expression: ${check.clean_mask_error}`;
      }
      return `Names ${formatNumber(check.clean)} file(s) smaller than ${check.clean_max_bytes} bytes`;
    },
  },
  watch: {
    tab() {
      this.maskCheckIfShown();
    },
    // Another datasource in the same editor (a link): loaded anew. A first save only moves to its id.
    id(value) {
      if (!this.saved || String(this.saved.id) !== String(value)) {
        this.ready = false;
        this.tab = "main";
        this.maskCheck = null;
        this.load().catch((error) => notifyError("Failed to load the datasource.", error));
      }
    },
  },
  created() {
    window.addEventListener("keydown", this.onKeydown);
    window.addEventListener("beforeunload", this.onBeforeUnload);
  },
  unmounted() {
    window.removeEventListener("keydown", this.onKeydown);
    window.removeEventListener("beforeunload", this.onBeforeUnload);
    clearTimeout(this.maskTimer);
  },
  async mounted() {
    try {
      await this.load();
    } catch (error) {
      notifyError("Failed to load the datasource.", error);
    }
  },
  methods: {
    ...mapActions(["updateDatasourceCatalogue"]),
    lane: datasourceLane,
    async load() {
      const [, tables] = await Promise.all([
        this.updateDatasourceCatalogue().catch(() => null),
        api("get-datasources", { loadingBar: false }).catch(() => []),
      ]);
      this.tableNames = tables || [];
      if (this.id === "new") {
        const cloneId = this.$route.query.clone;
        this.datasource = cloneId ? this.cloneOf(await api("get-ds-config", { params: { id: cloneId } })) : emptyDatasource();
        this.saved = null;
        this.savedJson = null;
      } else {
        const row = await api("get-ds-config", { params: { id: this.id } });
        this.takeSaved(row);
      }
      this.ready = true;
      this.maskCheckIfShown();
    },
    // A clone starts disabled, so it never picks up the files of the original, and without partition settings, which
    // only one datasource of a table should have.
    cloneOf(row) {
      const copy = { ...emptyDatasource(), ...JSON.parse(JSON.stringify(row)) };
      delete copy.directories;
      copy.id = null;
      copy.sourcename = `${row.sourcename}_COPY`.slice(0, 50);
      copy.isactive = 0;
      const partitioned = copy.links.filter((link) => link.partition_key).map((link) => link.table_name);
      copy.links = copy.links.map((link) => ({ ...link, partition_key: null, partition_days_to_retain: null, partition_days_in_advance: null }));
      this.cloneNotice = `A copy of ${row.sourcename}: it starts disabled${
        partitioned.length ? `, and the partitioning of ${partitioned.join(", ")} stays with ${row.sourcename}, so it is left out` : ""
      }. Rename it after its PDI transformation.`;
      return copy;
    },
    takeSaved(row) {
      const copy = JSON.parse(JSON.stringify(row));
      // The directories as the background scan read them; null when it did not read them all, checked then in the
      // background, so that opening a datasource never waits on the file system.
      this.directoryStates = copy.directories || [];
      if (!copy.directories && copy.id) {
        this.checkDirectories(copy.id);
      }
      delete copy.directories;
      this.saved = Object.freeze(JSON.parse(JSON.stringify(copy)));
      this.datasource = { ...emptyDatasource(), ...copy };
      this.savedJson = JSON.stringify(datasourcePayload(this.datasource));
      this.cloneNotice = null;
    },
    // Whether the directories exist, checked now by the server (each within 5 s, else unknown).
    async checkDirectories(id) {
      try {
        const states = await api("check-ds-directories", { params: { id }, loadingBar: false });
        if (this.saved && this.saved.id === id) {
          this.directoryStates = states;
        }
      } catch (error) {
        // The icons stay unknown.
      }
    },
    // The masks are tried on the directories only while the Input files tab is shown: reading the directories may take
    // seconds on a network file system, which opening a datasource should not wait for.
    maskCheckIfShown() {
      if (this.tab === "files" && !this.maskCheck) {
        this.checkMasks();
      }
    },
    // The masks as edited, tried on the saved directories (debounced); an answer overtaken by a later one is dropped.
    scheduleMaskCheck() {
      clearTimeout(this.maskTimer);
      this.maskTimer = setTimeout(this.checkMasks, 700);
    },
    async checkMasks() {
      if (!this.saved || !this.datasource.files_mask) {
        return;
      }
      const request = (this.maskRequest = (this.maskRequest || 0) + 1);
      this.maskChecking = true;
      try {
        const result = await api("get-ds-files", { params: { id: this.saved.id, kind: "clean", ...this.maskOverrides() }, loadingBar: false });
        if (request === this.maskRequest) {
          this.maskCheck = result;
        }
      } catch (error) {
        if (request === this.maskRequest) {
          this.maskCheck = null;
        }
      } finally {
        if (request === this.maskRequest) {
          this.maskChecking = false;
        }
      }
    },
    maskOverrides() {
      return {
        files_mask: this.datasource.files_mask || "",
        clean_mask: this.datasource.input_clean_files_mask || "",
        subdirs: Boolean(this.datasource.input_scan_subdirs),
      };
    },
    openFiles(kind) {
      this.$refs.fileDialog.open(this.saved, kind, this.maskOverrides());
    },
    async createDirectory(path) {
      if (!this.saved) {
        return;
      }
      try {
        await api("create-ds-directory", { method: "POST", params: { id: this.saved.id, path } });
        this.$q.notify({ type: "positive", message: `${path} was created.` });
        await this.checkDirectories(this.saved.id);
        this.checkMasks();
      } catch (error) {
        notifyError(`${path} was not created.`, error);
      }
    },
    // Enter submits through the form, whose rules only cover the fields of the tabs rendered so far; persist()
    // checks them all and shows the tab of the first problem.
    validationError() {
      this.$q.notify({ type: "negative", message: "Please correct the marked fields." });
    },
    // Save ("close": back to the list) or Apply ("stay"). A form without changes is not written.
    async persist(mode) {
      if (this.saving || !this.writable) {
        return;
      }
      if (!this.dirty) {
        this.$q.notify({ color: "grey-7", message: "No changes" });
        if (mode === "close") {
          this.$router.push({ name: "datasources" });
        }
        return;
      }
      const problem = this.validate();
      if (problem) {
        this.tab = problem.tab;
        this.$q.notify({ type: "negative", message: problem.message });
        return;
      }
      if (this.saved && this.saved.sourcename !== this.datasource.sourcename) {
        this.confirmRename(mode);
        return;
      }
      await this.submit(mode, true);
    },
    // Checked here, with the tab to show; the server checks again and has the last word (regular expressions).
    validate() {
      const ds = this.datasource;
      const whole = (value, low) => Number.isInteger(value) && value >= low;
      const absolute = (value) => String(value || "").split("|").every((part) => !part.trim() || part.trim().startsWith("/"));
      if (!ds.sourcename) return { tab: "main", message: "Please enter a source name." };
      if (!/^[A-Z0-9_]+$/.test(ds.sourcename)) return { tab: "main", message: "The source name may only have letters, digits and underscores." };
      const other = this.datasourceCatalogue.find((row) => row.sourcename === ds.sourcename && row.id !== ds.id);
      if (other) return { tab: "main", message: `Datasource ${ds.sourcename} already exists (ID ${other.id}).` };
      if (!ds.input_directory || !absolute(ds.input_directory)) return { tab: "files", message: "Every input directory must be an absolute path." };
      if (!ds.files_mask) return { tab: "files", message: "FILES_MASK is required." };
      if (!whole(ds.files_max_per_cycle, 1)) return { tab: "files", message: "Max files per cycle must be 1 or more." };
      if (!whole(ds.max_recordsreject, 0)) return { tab: "processing", message: "Max rejected records must be 0 or more." };
      for (const field of ARCHIVE_FIELDS) {
        if (!ds[field.name] || !absolute(ds[field.name])) return { tab: "archive", message: `${field.label} must be an absolute path.` };
      }
      if (!whole(ds.files_retention_days, 0)) return { tab: "archive", message: "Days files are kept must be 0 or more." };
      const names = new Set();
      for (const link of ds.links) {
        const name = (link.table_name || "").toUpperCase();
        if (!name) return { tab: "retention", message: "Every table needs a name." };
        if (names.has(name)) return { tab: "retention", message: `Table ${name} is listed twice.` };
        names.add(name);
        if (link.partition_key && !whole(link.partition_days_to_retain, 1)) return { tab: "retention", message: `Table ${name} needs days to retain.` };
      }
      return null;
    },
    // A rename reaches beyond rapo: PDI Core finds the transformation by this name.
    confirmRename(mode) {
      const before = this.saved.sourcename;
      const after = this.datasource.sourcename;
      const selfLink = this.datasource.links.find((link) => (link.table_name || "").toUpperCase() === before);
      const message = [
        `PDI Core looks for a transformation named <b>${escapeHtml(after)}</b> in /public/core/load_file/datasources: rename it there too.`,
        `A RECYCLE or DELETE cleans the table named like the datasource by default, and PDI_CORE_FILE_LOG keeps ${escapeHtml(before)} for the files loaded so far.`,
      ].join("<br><br>");
      this.$q
        .dialog({
          title: `Rename ${escapeHtml(before)} to ${escapeHtml(after)}?`,
          message,
          html: true,
          cancel: true,
          persistent: true,
          options: selfLink ? { type: "checkbox", model: [], items: [{ label: `Also link table ${after} instead of ${before}`, value: "link" }] } : undefined,
        })
        .onOk(async (selected) => {
          if (selfLink && (selected || []).includes("link")) {
            selfLink.table_name = after;
          }
          await this.submit(mode, true);
        });
    },
    // With lock, the server refuses (409) to overwrite a datasource changed since it was loaded here.
    async submit(mode, lock) {
      const body = { datasource: datasourcePayload(this.datasource) };
      if (lock && this.saved) {
        body.expected = this.saved;
      }
      const firstSave = !this.saved;
      this.saving = true;
      let result;
      try {
        result = await api("save-ds-config", { method: "POST", body });
      } catch (error) {
        this.saving = false;
        if (error.status === 409) {
          this.resolveConflict(mode, error.message);
          return;
        }
        notifyError("Datasource was not saved.", error);
        return;
      }
      const tab = this.tab;
      this.takeSaved(result.datasource);
      this.tab = tab;
      this.saving = false;
      this.updateDatasourceCatalogue().catch(() => null);
      if (mode === "close") {
        this.$q.notify({ type: "positive", message: `Datasource ${result.datasource.sourcename} was saved successfully.` });
        this.$router.push({ name: "datasources" });
        return;
      }
      this.$q.notify({ type: "positive", message: `Datasource ${result.datasource.sourcename} was saved.` });
      this.maskCheck = null;
      this.maskCheckIfShown();
      if (firstSave) {
        await this.$router.replace({ name: "edit-datasource", params: { id: String(result.datasource.id) } });
      }
    },
    resolveConflict(mode, message) {
      this.$q
        .dialog({
          title: "Datasource changed meanwhile",
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
            await this.submit(mode, false);
            return;
          }
          try {
            this.takeSaved(await api("get-ds-config", { params: { id: this.saved.id } }));
          } catch (error) {
            notifyError("Failed to reload the datasource.", error);
          }
        });
    },
    cancel() {
      this.$router.push({ name: "datasources" });
    },
    confirmLeave(to, next) {
      // A first save moves to the datasource's own id, with nothing left unsaved.
      if (!this.dirty || this.saving) {
        next();
        return;
      }
      this.$q
        .dialog({ title: "Unsaved changes", message: "Discard your unsaved changes?", ok: { label: "Discard", color: "negative" }, cancel: { label: "Keep editing", flat: true }, persistent: true })
        .onOk(() => {
          this.$q.notify({ type: "warning", message: "Changes discarded" });
          next();
        })
        .onCancel(() => next(false));
    },
    onKeydown(event) {
      if ((event.ctrlKey || event.metaKey) && !event.altKey && (event.key === "s" || event.key === "S")) {
        event.preventDefault();
        if (this.ready) {
          this.persist("stay");
        }
      }
    },
    onBeforeUnload(event) {
      if (this.dirty) {
        event.preventDefault();
        event.returnValue = "";
      }
    },
  },
  // Another datasource, or leaving, with unsaved changes (Cancel, the side menu, back) asks first.
  beforeRouteUpdate(to, from, next) {
    this.confirmLeave(to, next);
  },
  beforeRouteLeave(to, from, next) {
    this.confirmLeave(to, next);
  },
};
</script>

<style lang="css" scoped>
/* A chip rounds its avatar with a fixed radius, which is not a circle at size xl. */
.q-chip .type-avatar {
  border-radius: 50%;
}

/* Save / Apply / Cancel stay in view on every tab, at the bottom of the window while the card is longer. */
.editor-actions {
  position: sticky;
  bottom: 0;
  z-index: 2;
  background: white;
  border-top: 1px solid rgba(0, 0, 0, 0.12);
}

/* As tall as the outlined input beside it. */
.field-button {
  height: 56px;
}

:deep(.text-mono) {
  font-family: monospace;
}
</style>
