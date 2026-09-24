<template>
  <q-dialog v-model="visible">
    <q-card class="column no-wrap" style="width: 1400px; max-width: 95vw; max-height: 90vh">
      <q-card-section class="row items-center q-py-sm">
        <div class="text-h6">
          <template v-if="comparison">
            <q-btn flat round dense icon="fas fa-arrow-left" size="sm" class="q-mr-sm" @click="comparison = null">
              <q-tooltip>Back to the versions</q-tooltip>
            </q-btn>
            {{ comparison.from.label }} &rarr; {{ comparison.to.label }} ({{ comparison.rows.length }})
          </template>
          <template v-else>Versions of {{ current && current.control_name }} ({{ versions.length }})</template>
        </div>
        <q-space />
        <q-btn flat round icon="close" v-close-popup />
      </q-card-section>
      <q-separator />

      <q-card-section v-if="comparison" class="col scroll">
        <diff-table :rows="comparison.rows" empty-text="The two versions hold the same configuration." />
      </q-card-section>

      <template v-else>
        <q-card-section class="row items-center q-gutter-sm q-py-sm">
          <span>Remove versions older than</span>
          <q-input v-model.number="olderThanDays" type="number" dense outlined :min="0" style="width: 80px" />
          <span>days, keeping the newest</span>
          <q-input v-model.number="keep" type="number" dense outlined :min="0" style="width: 70px" />
          <q-btn flat color="negative" :label="pruneLabel" :disable="busy || !versions.length || !validPrune" @click="prune">
            <q-tooltip>The versions that would be removed are marked in red</q-tooltip>
          </q-btn>
          <q-separator vertical class="q-mx-md" />
          <q-btn flat color="negative" :label="`Remove duplicates (${duplicateIds.length})`" :disable="busy || !duplicateIds.length" @click="removeDuplicates">
            <q-tooltip>Versions equal to the version just before them; the oldest of each run of equal versions stays</q-tooltip>
          </q-btn>
        </q-card-section>
        <q-separator />

        <q-card-section class="col scroll q-pa-none">
          <table class="versions-table">
            <colgroup>
              <col style="width: 44px" />
              <col />
              <col style="width: 110px" />
              <col style="width: 200px" />
              <col style="width: 90px" />
            </colgroup>
            <thead>
              <tr>
                <th>
                  <q-checkbox :model-value="allSelected" dense :disable="!versions.length" @update:model-value="toggleAll">
                    <q-tooltip>Select or unselect all past versions</q-tooltip>
                  </q-checkbox>
                </th>
                <th>Version</th>
                <th>Action</th>
                <th>Changed by</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in rows"
                :key="row.id"
                :class="{ 'versions-table__current': row.current, 'versions-table__marked': markedIds.has(row.id) }">
                <td><q-checkbox v-model="selected" :val="row.id" dense /></td>
                <td>
                  <span class="versions-table__label">{{ row.label }}</span>
                  <q-badge v-if="row.current" color="teal" class="q-ml-xs">saved</q-badge>
                  <q-badge v-else-if="row.id === loadedId" color="orange" class="q-ml-xs">in the editor</q-badge>
                </td>
                <td>{{ row.action }}</td>
                <td>{{ row.user }}</td>
                <td class="text-right">
                  <template v-if="!row.current">
                    <q-btn flat round dense size="sm" icon="fas fa-file-import" color="primary" @click="load(row)">
                      <q-tooltip>Load this version into the editor</q-tooltip>
                    </q-btn>
                    <q-btn flat round dense size="sm" icon="fas fa-trash" color="negative" :disable="busy" @click="remove([row])">
                      <q-tooltip>Delete this version</q-tooltip>
                    </q-btn>
                  </template>
                </td>
              </tr>
              <tr v-if="!versions.length">
                <td colspan="5" class="text-grey-7">No past versions</td>
              </tr>
            </tbody>
          </table>
        </q-card-section>
        <q-separator />

        <q-card-actions align="right">
          <span class="text-grey-7 q-mr-auto q-pl-sm">Tick one version to compare it with the saved one, or two to compare them.</span>
          <q-btn flat color="primary" label="Compare" :disable="!canCompare" @click="compare" />
          <q-btn
            flat
            color="negative"
            :label="`Delete selected (${selectedVersions.length})`"
            :disable="busy || !selectedVersions.length"
            @click="remove(selectedVersions)" />
          <q-btn flat label="Close" color="primary" v-close-popup />
        </q-card-actions>
      </template>
    </q-card>
  </q-dialog>
</template>

<script>
import { api, notifyError } from "../api";
import { consecutiveDuplicates, diffControl } from "../utils/controlDiff";
import { toDateTimeString } from "../utils/format";
import DiffTable from "./DiffTable.vue";

const CURRENT = "current";
// version_ids per delete request, keeping the query string well under the server's request-line limit.
const DELETE_BATCH = 100;
// Delay after the last edit of the age boxes before the versions they would remove are asked for.
const PREVIEW_DELAY = 300;

// The past versions of one control (rapo_config_bak, newest first, each with its ROWID as version_id) beside the
// saved row: compare any two, load one into the editor, delete some, all older than a number of days, or consecutive
// duplicates. What a removal would delete is marked in red: by age once the age boxes were edited (the server works
// it out with the database clock, which stamped audit_date), by duplicates while their removal is being confirmed.
// A canceled removal leaves its versions ticked instead, to be reviewed, compared or deleted as a selection.
export default {
  name: "ControlVersionsDialog",
  components: { DiffTable },
  props: {
    // The saved rapo_config row (the catalogue's), not the form.
    current: { type: Object, default: null },
    versions: { type: Array, default: () => [] },
    // version_id of the version the editor shows, if any.
    loadedId: { type: String, default: null },
  },
  emits: ["load", "changed"],
  data() {
    return {
      visible: false,
      selected: [],
      comparison: null,
      olderThanDays: 30,
      keep: 5,
      busy: false,
      // version_ids the age rule would remove, null until the age boxes are edited.
      ageIds: null,
      // version_ids of the duplicates while their removal is confirmed.
      duplicateMarks: null,
    };
  },
  computed: {
    // Newest first, the saved row on top.
    rows() {
      const rows = this.versions.map((version) => ({
        id: version.version_id,
        label: version.label,
        action: version.audit_action,
        user: [version.audit_user, toDateTimeString(version.audit_date)].filter(Boolean).join(", "),
        version,
      }));
      if (this.current) {
        const user = [this.current.updated_by, toDateTimeString(this.current.updated_date)].filter(Boolean).join(", ");
        rows.unshift({ id: CURRENT, label: this.current.label || "current", action: "", user, version: this.current, current: true });
      }
      return rows;
    },
    selectedVersions() {
      return this.selected.filter((id) => id !== CURRENT).map((id) => this.rows.find((row) => row.id === id)).filter(Boolean);
    },
    canCompare() {
      return this.selected.length === 2 || (this.selected.length === 1 && this.selected[0] !== CURRENT);
    },
    pastIds() {
      return this.versions.map((version) => version.version_id);
    },
    // true all past versions ticked, false none, null some (the indeterminate header checkbox).
    allSelected() {
      const ticked = this.pastIds.filter((id) => this.selected.includes(id)).length;
      return ticked === 0 ? false : ticked === this.pastIds.length ? true : null;
    },
    duplicateIds() {
      return consecutiveDuplicates(this.versions);
    },
    markedIds() {
      return new Set(this.duplicateMarks || this.ageIds || []);
    },
    pruneLabel() {
      return this.ageIds ? `Remove (${this.ageIds.length})` : "Remove";
    },
    validPrune() {
      return Number.isInteger(this.olderThanDays) && this.olderThanDays >= 0 && Number.isInteger(this.keep) && this.keep >= 0;
    },
  },
  watch: {
    // A deleted version leaves the selection.
    rows(rows) {
      this.selected = this.selected.filter((id) => rows.some((row) => row.id === id));
    },
    olderThanDays() {
      this.schedulePreview();
    },
    keep() {
      this.schedulePreview();
    },
    // After a delete the age marks follow the remaining versions.
    versions() {
      if (this.ageIds) {
        this.schedulePreview();
      }
    },
  },
  unmounted() {
    clearTimeout(this.previewTimer);
  },
  methods: {
    // The version the editor shows, when it is not the saved one, starts ticked: Compare then shows it against the
    // saved row.
    open() {
      this.selected = this.loadedId ? [this.loadedId] : [];
      this.comparison = null;
      this.ageIds = null;
      this.duplicateMarks = null;
      this.visible = true;
    },
    toggleAll() {
      const keepCurrent = this.selected.includes(CURRENT) ? [CURRENT] : [];
      this.selected = this.allSelected === true ? keepCurrent : [...keepCurrent, ...this.pastIds];
    },
    schedulePreview() {
      clearTimeout(this.previewTimer);
      if (!this.visible || !this.current || !this.validPrune) {
        this.ageIds = null;
        return;
      }
      this.previewTimer = setTimeout(() => this.previewAge(), PREVIEW_DELAY);
    },
    // The version_ids the age rule would remove now; null when they can not be had.
    async previewAge() {
      const params = { control_id: this.current.control_id, older_than_days: this.olderThanDays, keep: this.keep, dry_run: true };
      try {
        const result = await api("delete-control-versions", { method: "DELETE", params, loadingBar: false });
        // A later edit of the boxes supersedes this answer.
        if (params.older_than_days === this.olderThanDays && params.keep === this.keep) {
          this.ageIds = result.version_ids;
        }
        return result.version_ids;
      } catch (error) {
        notifyError("Failed to find the versions to remove.", error);
        return null;
      }
    },
    async removeDuplicates() {
      const ids = this.duplicateIds;
      this.duplicateMarks = ids;
      const confirmed = await this.confirm(`Delete ${ids.length} duplicate version(s), keeping the oldest of each run of equal versions?`);
      this.duplicateMarks = null;
      if (confirmed) {
        await this.delete({ version_id: ids });
      } else {
        this.selected = ids;
      }
    },
    // From the older to the newer, whatever order they were ticked in; one ticked version against the saved row.
    compare() {
      const ids = this.selected.length === 1 ? [this.selected[0], CURRENT] : this.selected;
      const [to, from] = this.rows.filter((row) => ids.includes(row.id));
      this.comparison = { from, to, rows: diffControl(JSON.stringify(from.version), to.version) };
    },
    load(row) {
      this.visible = false;
      this.$emit("load", row.version);
    },
    async remove(rows) {
      const message =
        rows.length === 1 ? `Delete version ${rows[0].label}?` : `Delete the ${rows.length} selected versions? This can not be undone.`;
      if (!(await this.confirm(message))) {
        return;
      }
      await this.delete({ version_id: rows.map((row) => row.id) });
    },
    async prune() {
      const params = { older_than_days: this.olderThanDays, keep: this.keep };
      clearTimeout(this.previewTimer);
      const ids = await this.previewAge();
      if (ids === null) {
        return;
      }
      const count = ids.length;
      if (!count) {
        this.$q.notify({ color: "grey-7", message: "No version is that old." });
        return;
      }
      const message = `Delete ${count} version(s) older than ${this.olderThanDays} days, keeping the newest ${this.keep}? This can not be undone.`;
      if (await this.confirm(message)) {
        await this.delete(params);
      } else {
        this.selected = ids;
      }
    },
    // Listed versions go in batches of DELETE_BATCH; a failed batch stops the rest, and the list is refreshed either way.
    async delete(params) {
      const batches = [];
      if (params.version_id) {
        for (let start = 0; start < params.version_id.length; start += DELETE_BATCH) {
          batches.push({ version_id: params.version_id.slice(start, start + DELETE_BATCH) });
        }
      } else {
        batches.push(params);
      }
      this.busy = true;
      let deleted = 0;
      try {
        for (const batch of batches) {
          const result = await api("delete-control-versions", { method: "DELETE", params: { ...batch, control_id: this.current.control_id } });
          deleted += result.count;
        }
        this.$q.notify({ type: "positive", message: `${deleted} version(s) deleted` });
      } catch (error) {
        notifyError(`Failed to delete versions (${deleted} deleted).`, error);
      } finally {
        this.busy = false;
        this.$emit("changed");
      }
    },
    confirm(message) {
      return new Promise((resolve) => {
        this.$q
          .dialog({ title: "Delete versions", message, ok: { label: "Delete", color: "negative" }, cancel: { flat: true }, persistent: true })
          .onOk(() => resolve(true))
          .onCancel(() => resolve(false));
      });
    },
  },
};
</script>

<style lang="sass" scoped>
.versions-table
  border-collapse: collapse
  width: 100%
  table-layout: fixed
  font-size: 13px

  th
    position: sticky
    top: 0
    z-index: 1
    background: #cfd8dc
    text-align: left
    font-weight: 500
    padding: 6px 8px

  td
    padding: 2px 8px
    border-bottom: 1px solid #eeeeee
    white-space: nowrap
    overflow: hidden
    text-overflow: ellipsis

.versions-table__current td
  background: #e0f2f1

// Versions the removal in view would delete.
.versions-table__marked td
  background: #ffebee

  .versions-table__label
    text-decoration: line-through
    color: #b71c1c
</style>
