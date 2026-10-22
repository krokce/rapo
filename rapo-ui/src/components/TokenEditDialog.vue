<template>
  <q-dialog v-model="shown" persistent>
    <q-card style="width: 1100px; max-width: 95vw">
      <q-card-section class="q-pb-sm">
        <div class="text-h6">{{ readOnly ? "Revoked API token" : tokenId ? "Edit API token" : "New API token" }}</div>
        <div v-if="tokenId" class="text-caption text-grey-7">
          <span class="text-mono">{{ prefix }}…</span>
          · {{ readOnly ? "it no longer works and can not be changed; delete it from the row menu." : "changes apply to the next request; open pages reconnect with them." }}
        </div>
      </q-card-section>

      <q-card-section class="q-pt-none scroll" style="max-height: 70vh">
        <div class="row q-col-gutter-sm">
          <q-input class="col-12 col-sm-4" outlined dense v-model="form.user_name" label="User name" maxlength="128" :readonly="readOnly" :autofocus="!readOnly" />
          <q-input class="col-12 col-sm-4" outlined dense v-model="form.user_email" label="Email" type="email" maxlength="256" :readonly="readOnly" />
          <q-input class="col-12 col-sm-4" outlined dense v-model="form.label" label="Label (optional)" maxlength="128" :readonly="readOnly" title="What the token is for, e.g. UI or billing-sync script" />
        </div>

        <!-- The validity and the presets on one line, each label beside its chips. -->
        <div class="row items-center q-mt-sm token-chip-row">
          <span class="text-grey-7 q-mr-sm">{{ tokenId ? "Expires" : "Valid for" }}</span>
          <template v-if="!tokenId">
            <q-chip v-for="duration in durations" :key="duration.value" dense clickable :class="{ 'chip-selected': form.duration === duration.value }" @click="form.duration = duration.value">
              {{ duration.label }}
            </q-chip>
          </template>
          <span v-else-if="readOnly">Revoked {{ toDateTimeString(revoked) }}</span>
          <span v-else>{{ expires ? toDateTimeString(expires) : "never" }} <span class="text-grey-7">· Extend from the row menu</span></span>
          <q-space />
          <template v-if="!readOnly">
            <span class="text-grey-7 q-mr-sm">Preset</span>
            <q-chip v-for="(preset, name) in presets" :key="name" dense clickable :class="{ 'chip-selected': matchesPreset(preset) }" @click="applyPreset(preset)">
              {{ PRESET_LABELS[name] || name }}
            </q-chip>
          </template>
        </div>

        <div class="config-section-title config-section-separated">Access</div>
        <table class="config-table token-scope-table">
          <colgroup>
            <col style="width: 150px" />
            <col v-for="level in LEVELS" :key="level" style="width: 72px" />
            <col />
          </colgroup>
          <thead>
            <tr>
              <th title="A part of Rapo; Data is the records and file contents behind runs and files">Area</th>
              <th v-for="level in LEVELS" :key="level" class="text-center" :title="LEVEL_TITLES[level]">{{ LEVEL_LABELS[level] }}</th>
              <th title="What the chosen level allows in the area">Description</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="area in areas" :key="area.area">
              <td class="config-name">{{ area.title }}</td>
              <td v-for="level in LEVELS" :key="level" class="text-center">
                <q-radio
                  v-if="area.levels.includes(level)"
                  dense
                  size="sm"
                  v-model="form.scopes[area.area]"
                  :val="level"
                  :disable="readOnly"
                  :title="level === 'none' ? 'No access' : area.descriptions[level]"
                  :aria-label="`${area.title}: ${LEVEL_LABELS[level]}`" />
              </td>
              <td :class="form.scopes[area.area] === 'none' ? 'text-grey-6' : 'config-description'">{{ describe(area) }}</td>
            </tr>
            <!-- Free SQL is a flag beside the areas: off (None) or on (Edit, the strongest grant). -->
            <tr class="token-free-sql">
              <td class="config-name">{{ freeSql.title }}</td>
              <td class="text-center"><q-radio dense size="sm" v-model="form.free_sql" :val="false" :disable="readOnly" title="No SQL text" :aria-label="`${freeSql.title}: None`" /></td>
              <td></td>
              <td></td>
              <td class="text-center"><q-radio dense size="sm" v-model="form.free_sql" :val="true" :disable="readOnly" :title="freeSql.description" :aria-label="`${freeSql.title}: Allowed`" /></td>
              <td :class="freeSqlClass">{{ freeSqlText }}</td>
            </tr>
          </tbody>
        </table>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn flat :label="readOnly ? 'Close' : 'Cancel'" v-close-popup />
        <!-- On a wrapper: a disabled button gets no hover, so the reason would never show. -->
        <span v-if="!readOnly" class="inline-block">
          <q-btn color="primary" :label="tokenId ? 'Save' : 'Create token'" :loading="saving" :disable="!!problem" @click="save" />
          <q-tooltip v-if="problem">{{ problem }}</q-tooltip>
        </span>
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script>
import { api, notifyError } from "../api";
import { toDateTimeString } from "../utils/format";
import { LEVELS, LEVEL_LABELS, TOKEN_DURATIONS } from "../utils/scopes";

const PRESET_LABELS = { viewer: "Viewer", operator: "Operator", editor: "Editor", full: "Full" };

const LEVEL_TITLES = {
  none: "No access to the area",
  view: "See the area's pages and lists",
  operate: "Act without changing configuration: run, cancel, file status, scheduler stop/start",
  edit: "Change configuration: save and delete; for Free SQL: allowed",
};

// The texts (areas, levels, Free SQL) come from get-api-tokens: rapo/web/api/scopes.py, beside the routes they describe.
export default {
  name: "TokenEditDialog",
  props: {
    areas: { type: Array, required: true },
    presets: { type: Object, required: true },
    needsFreeSql: { type: Object, required: true },
    freeSql: { type: Object, required: true },
  },
  emits: ["saved"],
  data() {
    return {
      LEVELS,
      LEVEL_LABELS,
      LEVEL_TITLES,
      PRESET_LABELS,
      durations: TOKEN_DURATIONS,
      shown: false,
      saving: false,
      tokenId: null,
      prefix: "",
      expires: null,
      revoked: null,
      form: this.emptyForm(),
    };
  },
  methods: {
    toDateTimeString,
    emptyForm() {
      return { user_name: "", user_email: "", label: "", duration: "6m", scopes: {}, free_sql: false };
    },
    // A new token (null) starts as a viewer; an existing one with its own scopes, read only once revoked.
    open(token) {
      this.tokenId = token ? token.token_id : null;
      this.prefix = token ? token.token_prefix : "";
      this.expires = token ? token.expires_at : null;
      this.revoked = token ? token.revoked_at : null;
      const form = this.emptyForm();
      if (token) {
        Object.assign(form, { user_name: token.user_name, user_email: token.user_email, label: token.label || "", scopes: { ...token.scopes }, free_sql: token.free_sql });
      } else if (this.presets.viewer) {
        form.scopes = { ...this.presets.viewer.scopes };
      }
      for (const area of this.areas) {
        form.scopes[area.area] = form.scopes[area.area] || "none";
      }
      this.form = form;
      this.shown = true;
    },
    applyPreset(preset) {
      for (const area of this.areas) {
        this.form.scopes[area.area] = preset.scopes[area.area] || "none";
      }
      this.form.free_sql = preset.free_sql;
    },
    matchesPreset(preset) {
      return this.form.free_sql === preset.free_sql && this.areas.every((area) => (preset.scopes[area.area] || "none") === this.form.scopes[area.area]);
    },
    describe(area) {
      const level = this.form.scopes[area.area];
      return level === "none" ? "No access" : area.descriptions[level];
    },
    async save() {
      this.saving = true;
      const body = { user_name: this.form.user_name, user_email: this.form.user_email, label: this.form.label, scopes: this.form.scopes, free_sql: this.form.free_sql };
      try {
        const result = this.tokenId
          ? await api("update-api-token", { method: "POST", params: { id: this.tokenId }, body })
          : await api("create-api-token", { method: "POST", body: { ...body, duration: this.form.duration } });
        this.shown = false;
        this.$emit("saved", result);
      } catch (error) {
        notifyError("Token was not saved.", error);
      } finally {
        this.saving = false;
      }
    },
  },
  computed: {
    readOnly() {
      return Boolean(this.revoked);
    },
    // Edit levels that save SQL text need Free SQL (the server refuses them without it).
    missingFreeSql() {
      return Object.entries(this.needsFreeSql)
        .filter(([area, level]) => LEVELS.indexOf(this.form.scopes[area]) >= LEVELS.indexOf(level))
        .map(([area]) => (this.areas.find((item) => item.area === area) || {}).title || area);
    },
    freeSqlText() {
      if (this.form.free_sql) {
        return this.freeSql.description;
      }
      if (this.missingFreeSql.length) {
        return `Needed by ${this.missingFreeSql.join(" and ")}: Edit`;
      }
      return "No SQL; Data analysis filters on the dataset's columns only";
    },
    // Like the areas' descriptions: grey when off and not needed (Save's tooltip says when it is missing).
    freeSqlClass() {
      return this.form.free_sql || this.missingFreeSql.length ? "config-description" : "text-grey-6";
    },
    problem() {
      if (!this.form.user_name.trim()) {
        return "A user name is needed";
      }
      if (!/^[^@\s]+@[^@\s]+$/.test(this.form.user_email.trim())) {
        return "A valid email address is needed";
      }
      if (this.missingFreeSql.length && !this.form.free_sql) {
        return "Edit of Controls or KPIs needs Free SQL";
      }
      return null;
    },
  },
};
</script>

<style scoped>
.token-chip-row {
  min-height: 32px;
}
.token-scope-table td {
  vertical-align: middle;
}
/* Over the radios: the shared .config-table th is left-aligned. */
.token-scope-table th.text-center {
  text-align: center;
}
.token-scope-table tr.token-free-sql td {
  border-top: 1px solid var(--rapo-panel-border);
}
</style>
