<template>
  <div class="config-catalogue">
    <div v-if="error" class="text-negative">{{ error }}</div>
    <template v-else-if="!catalogue">
      <q-skeleton v-for="row in 4" :key="row" height="60px" class="q-mb-sm" />
    </template>
    <template v-else>
      <div class="row items-center q-gutter-sm q-mb-sm no-wrap">
        <q-input v-model="filter" dense outlined clearable placeholder="Filter options" class="col" style="max-width: 320px">
          <template #prepend><q-icon name="fas fa-search" size="14px" /></template>
        </q-input>
        <q-toggle v-model="onlySet" dense size="sm" label="Only set in rapo.ini" class="text-grey-8" />
      </div>
      <!-- What the colors and symbols of the tables mean. -->
      <div class="config-legend q-mb-sm">
        <span><span class="config-set">value</span> set in rapo.ini</span>
        <span><span class="config-default">value</span> default, not set</span>
        <span><q-icon name="fas fa-pen" size="10px" class="config-legend-pen" /> click to change, applies at once</span>
        <span><i class="config-dot config-dot-restart" /> applies after a restart</span>
        <span><q-icon name="fas fa-lock" size="10px" class="text-grey-6" /> secret, never shown</span>
        <span><i class="config-dot config-dot-unknown" /> not an option rapo reads</span>
        <span><i class="config-swatch" /> changed on disk, not applied yet</span>
      </div>

      <div class="config-section-title">General</div>
      <table class="config-table config-general">
        <tbody>
          <tr v-for="item in general" :key="item.label">
            <td class="config-name">{{ item.label }}</td>
            <td class="config-general-value">{{ item.value || "–" }}</td>
          </tr>
        </tbody>
      </table>

      <template v-for="section in sections" :key="section.name">
        <div class="config-section-title config-section-separated" :title="section.description">{{ section.name }}</div>
        <table class="config-table">
          <colgroup>
            <col style="width: 240px" />
            <col style="width: 190px" />
            <col style="width: 120px" />
            <col />
          </colgroup>
          <thead>
            <tr>
              <th title="Name of the option in rapo.ini">Parameter</th>
              <th title="The value set in rapo.ini (blue); an option not set there shows its default (grey)">Value</th>
              <th title="The value rapo uses when rapo.ini does not set the option">Default</th>
              <th title="What the option does">Description</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="option in section.options" :key="option.name" :class="rowClass(section, option)">
              <td class="config-name">
                <span :title="option.written_as && option.written_as !== option.name ? `Written as ${option.written_as}, a former name` : ''">{{ option.name }}</span>
                <i v-if="option.restart" class="config-dot config-dot-restart" title="Read at start: a change applies after a restart, and is made in rapo.ini on the server" />
                <i v-if="option.unknown" class="config-dot config-dot-unknown" title="Set in rapo.ini, but no option rapo reads: a typo or a removed option" />
              </td>
              <td class="config-value" :class="{ 'config-editable': option.editable }" @click="option.editable && openEditor($event, section, option)">
                <template v-if="option.secret">
                  <q-icon name="fas fa-lock" size="10px" class="q-mr-xs text-grey-6" />
                  <span class="config-muted">{{ option.set ? "set (hidden)" : "not set" }}</span>
                </template>
                <span v-else-if="option.set" class="config-set" :title="display(option.value)">{{ display(option.value) }}</span>
                <span v-else class="config-default" :title="display(option.default)">{{ display(option.default, "none") }}</span>
                <template v-if="pending(section, option)">
                  <span class="config-pending" :title="pendingTitle(section, option)">
                    &larr; {{ pending(section, option).change === "removed" ? "removed" : "changed" }} on disk
                  </span>
                </template>
                <q-icon v-if="option.editable" name="fas fa-pen" size="10px" class="config-pencil" />
              </td>
              <td class="config-muted config-cut" :title="option.secret ? '' : display(option.default)">{{ option.secret ? "" : display(option.default, "–") }}</td>
              <td class="config-description config-cut" :title="option.description">{{ option.description }}</td>
            </tr>
          </tbody>
        </table>
      </template>
      <div v-if="!sections.length" class="text-grey-7 q-mt-md">No option matches.</div>

      <q-menu v-if="editor.target" v-model="editor.visible" :target="editor.target" anchor="bottom left" self="top left" no-parent-event @hide="editor.option = null">
        <div v-if="editor.option" class="config-editor q-pa-sm">
          <div class="text-caption text-grey-8 q-mb-xs">
            <span class="text-mono">[{{ editor.section }}] {{ editor.option.name }}</span>
          </div>
          <q-toggle v-if="editor.option.type === 'bool'" v-model="editor.value" :label="editor.value ? 'True' : 'False'" dense />
          <q-select v-else-if="editor.option.type === 'choice'" v-model="editor.value" :options="editor.option.choices" dense outlined options-dense autofocus />
          <q-input
            v-else
            v-model="editor.value"
            dense
            outlined
            autofocus
            :type="isNumber(editor.option) ? 'number' : 'text'"
            :min="editor.option.minimum"
            :placeholder="editor.option.default === null ? 'empty' : `default ${display(editor.option.default)}`"
            :input-class="isNumber(editor.option) ? 'number-cell' : 'text-mono'"
            @keyup.enter="save"
            @keyup.esc="editor.visible = false" />
          <div class="text-caption text-grey-7 q-mt-xs" style="max-width: 300px">{{ editor.option.description }}</div>
          <div class="row items-center q-mt-sm q-gutter-xs">
            <q-btn v-if="editor.option.set" flat dense no-caps size="sm" color="grey-8" label="Reset to default" :disable="saving" @click="save(true)">
              <q-tooltip>Remove the option from rapo.ini, so its default applies</q-tooltip>
            </q-btn>
            <q-space />
            <q-btn flat dense no-caps size="sm" label="Cancel" @click="editor.visible = false" />
            <q-btn unelevated dense no-caps size="sm" color="teal" label="Save" class="q-px-sm" :loading="saving" @click="save(false)" />
          </div>
        </div>
      </q-menu>
    </template>
  </div>
</template>

<script>
import { mapActions, mapGetters } from "vuex";
import { api, notifyError } from "../api";

// Every rapo.ini option rapo knows (get-config-catalogue): the value set in the file, its default and description, per
// section. A value that applies without a restart and holds no secret is changed in place: set-config-option writes
// that one line of rapo.ini (after a backup) and reloads it on this server.
export default {
  name: "ConfigCatalogue",
  data() {
    return {
      catalogue: null,
      error: null,
      filter: "",
      onlySet: false,
      saving: false,
      editor: { visible: false, target: null, section: null, option: null, value: null },
    };
  },
  computed: {
    ...mapGetters(["getEnvConfigChanges"]),
    general() {
      const general = this.catalogue.general;
      return [
        { label: "Version", value: general.version },
        { label: "Instance", value: general.instance_name },
        { label: "Configuration", value: general.config_path },
        { label: "Logs", value: general.log_directory },
      ];
    },
    // The sections with their options matching the filter; options in rapo.ini that rapo does not know close their
    // section, those of a section rapo does not know form an Other section.
    sections() {
      const text = (this.filter || "").trim().toLowerCase();
      const unknown = this.catalogue.unknown || [];
      const known = this.catalogue.sections.map((section) => section.name);
      const sections = [
        ...this.catalogue.sections.map((section) => ({
          ...section,
          options: [...section.options, ...unknown.filter((item) => item.section.toUpperCase() === section.name).map(this.unknownOption)],
        })),
      ];
      const other = unknown.filter((item) => !known.includes(item.section.toUpperCase())).map(this.unknownOption);
      if (other.length) {
        sections.push({ name: "Other", description: "sections rapo does not read", options: other });
      }
      return sections
        .map((section) => ({
          ...section,
          options: section.options.filter(
            (option) =>
              (!this.onlySet || option.set) &&
              (!text ||
                `${section.name} ${option.name} ${option.description} ${option.secret ? "" : this.display(option.value)}`.toLowerCase().includes(text)),
          ),
        }))
        .filter((section) => section.options.length);
    },
    changes() {
      return (this.getEnvConfigChanges && this.getEnvConfigChanges.changes) || [];
    },
  },
  mounted() {
    this.load();
  },
  methods: {
    ...mapActions(["updateEnvironment"]),
    async load() {
      try {
        this.catalogue = await api("get-config-catalogue", { loadingBar: false });
        this.error = null;
      } catch (error) {
        this.error = `Failed to load the configuration: ${error.message}`;
      }
    },
    unknownOption(item) {
      return { name: item.name, value: item.value, set: true, unknown: true, description: "", default: null, secret: item.value === null };
    },
    isNumber(option) {
      return option.type === "int" || option.type === "float";
    },
    // A value as written in rapo.ini; tabs and line ends of a template shown as \t and \n.
    display(value, empty = "") {
      if (value === null || value === undefined || value === "") {
        return empty;
      }
      if (typeof value === "boolean") {
        return value ? "True" : "False";
      }
      return String(value).replace(/\t/g, "\\t").replace(/\n/g, "\\n");
    },
    // A change of rapo.ini on disk not applied yet (get-config-changes): one that needs a restart, or one waiting
    // for Reload.
    pending(section, option) {
      return this.changes.find((item) => item.section.toUpperCase() === section.name && item.option === (option.written_as || option.name));
    },
    pendingTitle(section, option) {
      const item = this.pending(section, option);
      if (item.secret) {
        return "Changed on disk, not applied yet";
      }
      return `Loaded ${this.display(item.loaded, "nothing")}, on disk ${this.display(item.file, "nothing")}: ` + (item.restart ? "applies after a restart" : "Reload applies it");
    },
    rowClass(section, option) {
      const item = this.pending(section, option);
      return item ? `env-${item.change}` : "";
    },
    openEditor(event, section, option) {
      const value = option.set ? option.value : option.default;
      this.editor = {
        visible: true,
        target: event.currentTarget,
        section: section.name,
        option,
        value: option.type === "bool" ? value === true : value === null || value === undefined ? "" : this.display(value),
      };
    },
    async save(reset = false) {
      const { section, option } = this.editor;
      if (!option || this.saving) {
        return;
      }
      this.saving = true;
      try {
        let value = this.editor.value;
        if (option.type === "text" && option.name === "format") {
          value = String(value).replace(/\\t/g, "\t").replace(/\\n/g, "\n");
        }
        await api("set-config-option", {
          method: "POST",
          body: { section, option: option.name, value, reset, digest: this.catalogue.digest },
        });
        this.editor.visible = false;
        this.$q.notify({ type: "positive", message: reset ? `${section}.${option.name} reset to its default` : `${section}.${option.name} saved and applied` });
        await Promise.all([this.load(), this.updateEnvironment()]);
      } catch (error) {
        notifyError(`Failed to change ${section}.${option.name}.`, error);
        if (/changed on disk/.test(error.message)) {
          this.editor.visible = false;
          await Promise.all([this.load(), this.updateEnvironment()]);
        }
      } finally {
        this.saving = false;
      }
    },
  },
};
</script>

<style lang="sass">
.config-legend
  display: flex
  flex-wrap: wrap
  gap: 2px 16px
  font-size: 11px
  color: var(--rapo-muted)

  > span
    display: inline-flex
    align-items: center
    gap: 5px

.config-legend-pen
  color: var(--rapo-teal)

.config-swatch
  display: inline-block
  width: 14px
  height: 10px
  border-radius: 2px
  background: var(--rapo-highlight)
  border: 1px solid var(--rapo-filter-border)

.config-dot
  display: inline-block
  width: 7px
  height: 7px
  border-radius: 50%
  margin-left: 6px
  vertical-align: middle

  .config-legend &
    margin-left: 0

  &.config-dot-restart
    background: var(--rapo-warn)
  &.config-dot-unknown
    background: var(--rapo-crit)

.config-section-title
  font-size: 13px
  font-weight: 500
  letter-spacing: 0.03em
  color: var(--rapo-strong)
  margin-bottom: 2px

.config-section-separated
  margin-top: 14px
  padding-top: 10px
  border-top: 1px solid var(--rapo-panel-border)

.config-table
  width: 100%
  border-collapse: collapse
  table-layout: fixed
  font-size: 12px
  line-height: 1.35

  th
    text-align: left
    font-weight: 500
    color: var(--rapo-label)
    padding: 3px 8px
    border-bottom: 1px solid var(--rapo-panel-border)
  td
    padding: 4px 8px
    vertical-align: top
    border-bottom: 1px solid var(--rapo-grid)
  tbody tr:last-child td
    border-bottom: none
  tbody tr:hover td
    background: var(--rapo-row-hover)

  // Options of rapo.ini changed on disk and not applied yet.
  tr.env-changed td, tr.env-added td, tr.env-removed td
    background: var(--rapo-highlight)

// One line per option: what does not fit is cut, the whole text is in the tooltip.
.config-cut, .config-value
  white-space: nowrap
  overflow: hidden
  text-overflow: ellipsis

.config-general
  td
    border-bottom: none
    padding: 2px 8px
  .config-name
    width: 240px

.config-general-value
  font-family: var(--rapo-font-mono)
  word-break: break-all

.config-name
  font-family: var(--rapo-font-mono)
  font-weight: 700
  color: var(--rapo-header-text)
  white-space: nowrap

.config-value
  font-family: var(--rapo-font-mono)
  position: relative
  padding-right: 24px !important

  &.config-editable
    cursor: pointer
    &:hover
      background: var(--rapo-teal-soft) !important

.config-pencil
  position: absolute
  right: 8px
  top: 7px
  color: var(--rapo-teal)
  visibility: hidden

tr:hover .config-pencil
  visibility: visible

.config-set
  color: var(--rapo-info)
  font-family: var(--rapo-font-mono)

.config-default
  color: var(--rapo-muted)
  font-family: var(--rapo-font-mono)

.config-muted
  color: var(--rapo-muted)
  font-family: var(--rapo-font-mono)

.config-pending
  margin-left: 6px
  color: var(--rapo-warn)
  font-family: Roboto, sans-serif
  font-size: 11px

.config-description
  color: var(--rapo-strong)

.config-editor
  min-width: 260px
</style>
