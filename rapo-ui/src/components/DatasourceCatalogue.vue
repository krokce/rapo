<template>
  <q-page class="column no-wrap" :style-fn="fillViewportToBottom">
    <div class="row items-end" :class="activeFilters.length ? 'q-mb-sm' : 'q-mb-lg'">
      <h2 class="row items-center no-wrap text-no-wrap q-gutter-lg q-mb-none">
        <div v-if="showSkeleton">Datasources</div>
        <div v-else>{{ countTitle }}</div>
        <div v-if="!showSkeleton && activeFilters.length" class="row items-center"><filter-badge :filters="activeFilters" @clear="clearFilters" /></div>
        <div v-if="refreshing && !showSkeleton">
          <q-avatar size="lg" color="grey-5">
            <q-icon name="fas fa-sync fa-spin" />
          </q-avatar>
        </div>
      </h2>
      <q-space />

      <!-- Lane and incoming-file totals, laid out like the day totals of Results. Incoming: files in the input directories, not
           yet in the file log (whose WAITING status is another thing). -->
      <div v-if="!showSkeleton" class="row items-center justify-end q-gutter-x-md text-blue-grey-8">
        <div>
          <q-chip v-for="entry in laneCounts" :key="entry.lane.value" clickable @click="filter.lanes = [entry.lane.value]">
            <q-avatar :icon="entry.lane.icon" :color="entry.lane.color" text-color="white" />
            <span class="text-weight-bold q-mr-xs">{{ entry.lane.label }}</span>({{ entry.count }})
            <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">Show the datasources of {{ entry.lane.label }}</q-tooltip>
          </q-chip>
        </div>
        <div>
          <q-chip v-if="waitingTotal !== null" clickable @click="filter.waiting = 'Y'">
            <q-avatar icon="fas fa-inbox" color="blue-grey-6" text-color="white" />
            <span class="text-weight-bold q-mr-xs">Incoming</span>({{ formatNumber(waitingTotal) }})
            <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]" max-width="400px">{{ scanTitle }}</q-tooltip>
          </q-chip>
          <q-chip v-else>
            <q-avatar icon="fas fa-hourglass-half" color="grey-5" text-color="white" />
            Counting files...
          </q-chip>
        </div>
      </div>
    </div>
    <filter-chips :filters="activeFilters" class="q-mb-md" />

    <div class="row items-center q-mb-md">
      <q-btn
        v-if="writable"
        class="col-2 q-mb-md q-pa-sm"
        size="lg"
        color="primary"
        icon="fas fa-plus-circle"
        label="New datasource"
        :to="{ name: 'edit-datasource', params: { id: 'new' } }" />

      <q-input clearable class="col q-mb-md q-pa-sm" outlined v-model="filter.text" label="Name, directory or mask" maxlength="100" />

      <q-select
        v-model="filter.lanes"
        class="col-2 q-mb-md q-pa-sm"
        outlined
        options-dense
        emit-value
        map-options
        multiple
        use-chips
        :options="laneOptions"
        label="Scheduler lane">
      </q-select>

      <q-select
        v-model="filter.waiting"
        class="col-2 q-mb-md q-pa-sm"
        clearable
        outlined
        options-dense
        emit-value
        map-options
        :options="[
          { label: 'Files incoming', value: 'Y' },
          { label: 'No incoming files', value: 'N' },
        ]"
        label="Incoming files">
      </q-select>

      <q-select
        v-model="filter.issues"
        class="col-3 q-mb-md q-pa-sm"
        outlined
        options-dense
        emit-value
        map-options
        multiple
        use-chips
        :options="issueOptions"
        label="Issues">
      </q-select>
    </div>

    <q-virtual-scroll
      type="table"
      class="list-table datasource-table"
      :style="{ '--name-column-width': nameColumnWidth + 'px' }"
      :items="sortedDatasources"
      :virtual-scroll-item-size="72"
      :virtual-scroll-sticky-size-start="48"
      :table-colspan="11">
      <template #before>
        <thead>
          <tr class="bg-blue-grey-2">
            <th v-for="column in columns" :key="column.key" :class="['text-' + column.align, { sortable: column.sort }]" @click="column.sort && toggleSort(sort, column.key)">
              {{ column.label }}
              <q-icon v-if="sort.key === column.key" :name="sortIcon(sort)" size="12px" />
            </th>
            <th></th>
          </tr>
        </thead>
      </template>
      <template #default="{ item: row }">
        <tr :key="row.id" :class="{ 'row-inactive': row.isactive === 0 }">
          <td>
            <q-chip :clickable="writable" :title="writable ? 'Change the scheduler lane (ISACTIVE)' : lane(row.isactive).label" @click="writable && openLaneMenu($event, row)">
              <q-avatar :icon="lane(row.isactive).icon" :color="lane(row.isactive).color" text-color="white" />
              <span class="text-weight-bold">{{ lane(row.isactive).short }}</span>
            </q-chip>
          </td>
          <td class="text-right text-grey-8">{{ row.id }}</td>
          <td class="text-left">
            <router-link :to="{ name: 'edit-datasource', params: { id: row.id } }" class="datasource-name text-weight-bold text-grey-9">
              {{ row.sourcename }}
            </router-link>
          </td>
          <td class="text-left path-cell">
            <div v-for="path in directoriesOf(row)" :key="path" class="ellipsis" :title="path">
              <q-icon v-if="isMissing(row, path)" name="fas fa-folder-minus" color="red-5" size="12px" class="q-mr-xs" />{{ path }}
            </div>
            <div class="row items-center issue-chips">
              <q-chip
                v-for="issue in issuesOf(row)"
                :key="issue.key"
                clickable
                size="sm"
                :color="issue.color"
                text-color="white"
                :icon="issue.icon"
                :title="issue.title"
                @click="addIssueFilter(issue.key)">
                {{ issue.label }}
              </q-chip>
            </div>
          </td>
          <td class="text-left mask-cell ellipsis" :title="row.files_mask">{{ row.files_mask }}</td>
          <td class="text-right">
            <div v-if="statusOf(row) && missingOf(row).length && !statusOf(row).waiting" class="text-red-5" :title="`Missing on this server: ${missingOf(row).join(', ')}`">
              missing
            </div>
            <template v-else-if="statusOf(row) && statusOf(row).waiting !== undefined">
              <div :class="waitingClass(row)">
                {{ formatNumber(statusOf(row).waiting) }}{{ statusOf(row).capped ? "+" : "" }}
                <q-icon v-if="statusOf(row).stale" name="fas fa-history" size="11px" color="grey-6" title="Not counted in the last scan (its time budget ran out)" />
              </div>
              <div v-if="statusOf(row).waiting" class="text-caption text-grey-7">
                {{ formatBytes(statusOf(row).bytes) }} · {{ formatAge(ageOf(row)) }}
                <q-tooltip>Oldest incoming file modified {{ toDateTimeString(statusOf(row).oldest_at) }}</q-tooltip>
              </div>
            </template>
            <span v-else-if="row.isactive === 0 && datasourceStatus && !datasourceStatus.pending" class="text-grey-5" title="Not counted: the datasource is disabled">
              &ndash;
            </span>
            <q-skeleton v-else type="text" width="40px" class="float-right" />
          </td>
          <td class="text-left">
            <template v-if="logOf(row)">
              <div>{{ toDateTimeString(logOf(row).last_load).slice(5, 16) }}</div>
              <div class="text-caption text-grey-7">
                {{ formatNumber(logOf(row).files) }} file(s)
                <span v-if="logOf(row).errors" class="text-red-6 text-weight-bold"> · {{ logOf(row).errors }} error(s)</span>
                <span v-if="logOf(row).rejected" class="text-orange-9"> · {{ formatNumber(logOf(row).rejected) }} rej.</span>
                <q-tooltip>
                  In the last 24 hours: {{ formatNumber(logOf(row).files) }} file(s), {{ formatNumber(logOf(row).records || 0) }} record(s) written,
                  {{ formatNumber(logOf(row).rejected || 0) }} rejected, {{ logOf(row).errors }} error(s), {{ logOf(row).duplicates }} duplicate(s)
                </q-tooltip>
              </div>
            </template>
            <span v-else-if="datasourceStatus && !datasourceStatus.pending" class="text-grey-5" title="Nothing loaded in the last 24 hours">&ndash;</span>
          </td>
          <td class="text-right">{{ row.files_retention_days }}</td>
          <td class="text-right">{{ row.files_max_per_cycle }}</td>
          <td class="text-center">
            <q-icon v-if="row.input_scan_subdirs" name="fas fa-sitemap" color="grey-7" size="14px" title="Subdirectories are scanned" />
          </td>
          <td>
            <q-btn size="sm" color="grey-7" round flat icon="fas fa-ellipsis-v" @click="openRowMenu($event, row)" />
          </td>
        </tr>
      </template>
      <template #after>
        <tbody v-if="showSkeleton">
          <skeleton-rows v-if="!loadError" :columns="['QChip', 'text', 'text', 'text', 'text', 'text', 'text', 'text', 'text', null, null]" />
          <tr v-else>
            <td colspan="11" class="text-center text-grey-7 q-pa-lg">Datasources could not be loaded</td>
          </tr>
        </tbody>
        <tbody v-else-if="!sortedDatasources.length">
          <tr>
            <td colspan="11" class="text-center text-grey-7 q-pa-lg">No datasources match the filters</td>
          </tr>
        </tbody>
      </template>
    </q-virtual-scroll>

    <!-- The one lane menu of the table, opened at the lane chip of the row it acts on. -->
    <q-menu ref="laneMenu" :target="laneTarget" no-parent-event>
      <q-list v-if="laneRow" dense class="text-no-wrap">
        <q-item-label header class="q-py-sm">ISACTIVE of {{ laneRow.sourcename }}</q-item-label>
        <q-item
          v-for="option in laneMenuOptions"
          :key="option.value"
          clickable
          v-close-popup
          :active="option.value === laneRow.isactive"
          @click="setLane(laneRow, option.value)">
          <q-item-section avatar>
            <q-avatar size="24px" :icon="option.icon" :color="option.color" text-color="white" />
          </q-item-section>
          <q-item-section>{{ option.label }}</q-item-section>
        </q-item>
        <q-separator />
        <q-item clickable>
          <q-item-section>Other lane</q-item-section>
          <q-item-section side><q-icon name="fas fa-chevron-right" size="12px" /></q-item-section>
          <q-menu anchor="top end" self="top start">
            <q-list dense>
              <q-item v-for="option in otherLaneOptions" :key="option.value" clickable v-close-popup="2" @click="setLane(laneRow, option.value)">
                <q-item-section avatar>
                  <q-avatar size="24px" :icon="option.icon" :color="option.color" text-color="white" />
                </q-item-section>
                <q-item-section>{{ option.label }}</q-item-section>
              </q-item>
            </q-list>
          </q-menu>
        </q-item>
      </q-list>
    </q-menu>

    <!-- The one row menu of the table, opened at the kebab button of the row it acts on. -->
    <q-menu ref="rowMenu" :target="menuTarget" no-parent-event>
      <q-list v-if="menuRow" dense class="text-no-wrap">
        <q-item clickable :to="{ name: 'edit-datasource', params: { id: menuRow.id } }">
          <q-item-section>Edit datasource</q-item-section>
        </q-item>
        <q-item v-if="writable" clickable v-close-popup :to="{ name: 'edit-datasource', params: { id: 'new' }, query: { clone: menuRow.id } }">
          <q-item-section>Clone datasource</q-item-section>
        </q-item>
        <q-separator />
        <q-item clickable v-close-popup @click="$refs.fileDialog.open(menuRow, 'match')">
          <q-item-section>Show matched files waiting</q-item-section>
        </q-item>
        <q-item clickable v-close-popup @click="$refs.fileDialog.open(menuRow, 'all')">
          <q-item-section>All files waiting in Input</q-item-section>
        </q-item>
        <q-item v-if="menuRow.input_clean_files_mask" clickable v-close-popup @click="$refs.fileDialog.open(menuRow, 'clean')">
          <q-item-section>Show clean-up files</q-item-section>
        </q-item>
        <template v-if="writable">
          <q-item v-for="path in missingOf(menuRow)" :key="path" clickable v-close-popup @click="createDirectory(menuRow, path)">
            <q-item-section>Create input directory {{ path }}</q-item-section>
          </q-item>
        </template>
        <template v-if="writable">
          <q-separator />
          <q-item clickable>
            <q-item-section>Set lane</q-item-section>
            <q-item-section side><q-icon name="fas fa-chevron-right" size="12px" /></q-item-section>
            <q-menu anchor="top end" self="top start">
              <q-list dense>
                <q-item
                  v-for="option in allLaneOptions"
                  :key="option.value"
                  clickable
                  v-close-popup="2"
                  :active="option.value === menuRow.isactive"
                  @click="setLane(menuRow, option.value)">
                  <q-item-section avatar>
                    <q-avatar size="24px" :icon="option.icon" :color="option.color" text-color="white" />
                  </q-item-section>
                  <q-item-section>{{ option.label }}</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
          </q-item>
        </template>
        <!-- Only a disabled datasource can be deleted, so no PDI Core scheduler loses one it is processing. -->
        <template v-if="deletable && menuRow.isactive === 0">
          <q-separator />
          <q-item dense clickable v-close-popup @click="deleteDatasource(menuRow)">
            <q-item-section>Delete datasource</q-item-section>
          </q-item>
        </template>
      </q-list>
    </q-menu>

    <file-list-dialog ref="fileDialog" />
  </q-page>
</template>

<script>
import { mapActions, mapGetters, mapState } from "vuex";
import FileListDialog from "./FileListDialog.vue";
import FilterBadge from "./FilterBadge.vue";
import FilterChips from "./FilterChips.vue";
import SkeletonRows from "./SkeletonRows.vue";
import { api, notifyError } from "../api";
import { DATASOURCE_LANES, datasourceLane } from "../constants";
import { liveRefetch } from "../socket";
import { ISSUES, formatAge, formatBytes, issuesOf, splitDirectories } from "../utils/datasources";
import { listFilter, searchFilter, valueFilter } from "../utils/filters";
import { escapeHtml, formatNumber, toDateTimeString } from "../utils/format";
import { fillViewportToBottom, textWidth } from "../utils/layout";
import { sortIcon, sortRows, toggleSort } from "../utils/sort";
import persistFilters from "../mixins/persistFilters";

const COLUMNS = [
  { key: "isactive", label: "Lane", align: "center", sort: true },
  { key: "id", label: "ID", align: "right", sort: true },
  { key: "sourcename", label: "Name", align: "left", sort: true },
  { key: "input_directory", label: "Input directory", align: "left", sort: true },
  { key: "files_mask", label: "Files mask", align: "left", sort: true },
  { key: "waiting", label: "Incoming", align: "right", sort: true },
  { key: "last_load", label: "Last 24h", align: "left", sort: true },
  { key: "files_retention_days", label: "Ret. days", align: "right", sort: true },
  { key: "files_max_per_cycle", label: "Max/cycle", align: "right", sort: true },
  { key: "input_scan_subdirs", label: "Subdirs", align: "center", sort: true },
];

// The PDI Core datasources (pdi_core_ds_config), with the files waiting in their input directories as the server last
// counted them (get-ds-status). Kept alive (App.vue): activated/deactivated start and stop its live refresh.
export default {
  name: "DatasourceCatalogue",
  mixins: [persistFilters("datasources", ["filter", "sort"])],
  components: { FileListDialog, FilterBadge, FilterChips, SkeletonRows },
  data() {
    return {
      columns: COLUMNS,
      loaded: false,
      refreshing: false,
      loadError: false,
      menuTarget: false,
      menuId: null,
      laneTarget: false,
      laneId: null,
      filter: {
        text: "",
        lanes: [],
        waiting: null,
        issues: [],
      },
      sort: {
        key: null,
        dir: "asc",
      },
    };
  },
  computed: {
    ...mapState(["datasourceCatalogue", "datasourceStatus"]),
    ...mapGetters(["getSearch", "getEnvInfo"]),
    writable() {
      return Boolean(this.getEnvInfo && this.getEnvInfo.datasources_writable);
    },
    deletable() {
      return Boolean(this.getEnvInfo && this.getEnvInfo.datasources_deletable);
    },
    showSkeleton() {
      return !this.loaded && !this.datasourceCatalogue.length;
    },
    countTitle() {
      const total = this.datasourceCatalogue.length;
      const shown = this.filteredDatasources.length;
      const count = this.activeFilters.length ? `${shown} of ${total}` : String(shown);
      return `${count} Datasource${(this.activeFilters.length ? total : shown) === 1 ? "" : "s"}`;
    },
    // The lanes in use, with their counts, Disabled first.
    laneCounts() {
      const counts = new Map();
      this.datasourceCatalogue.forEach((row) => counts.set(row.isactive, (counts.get(row.isactive) || 0) + 1));
      return [...counts.entries()].sort(([a], [b]) => a - b).map(([value, count]) => ({ lane: datasourceLane(value), count }));
    },
    laneOptions() {
      return this.laneCounts.map((entry) => ({ label: entry.lane.label, value: entry.lane.value }));
    },
    // The lane menu offers Disabled and the lanes in use; the others are under "Other lane".
    laneMenuOptions() {
      const used = new Set([0, ...this.laneCounts.map((entry) => entry.lane.value)]);
      return [...used].sort((a, b) => a - b).map(datasourceLane);
    },
    otherLaneOptions() {
      const used = new Set(this.laneMenuOptions.map((option) => option.value));
      return DATASOURCE_LANES.filter((value) => !used.has(value)).map(datasourceLane);
    },
    allLaneOptions() {
      return DATASOURCE_LANES.map(datasourceLane);
    },
    issueOptions() {
      return ISSUES.map((issue) => ({ label: issue.label, value: issue.key }));
    },
    stalledMinutes() {
      return (this.datasourceStatus && this.datasourceStatus.stalled_minutes) || 60;
    },
    waitingTotal() {
      if (!this.datasourceStatus || this.datasourceStatus.pending) {
        return null;
      }
      return this.datasourceCatalogue.reduce((total, row) => total + ((this.statusOf(row) || {}).waiting || 0), 0);
    },
    scanTitle() {
      const status = this.datasourceStatus;
      return status && status.scanned_at
        ? `Counted at ${toDateTimeString(status.scanned_at)} in ${status.duration} s, every ${status.interval} s while this page is open. Show the datasources with incoming files.`
        : "";
    },
    activeFilters() {
      const filter = this.filter;
      const issueLabel = (key) => (ISSUES.find((issue) => issue.key === key) || {}).label || key;
      return [
        ...valueFilter("text", "Text", filter.text, () => (filter.text = null), { text: true }),
        ...listFilter("lane", "Lane", filter.lanes, (value) => (filter.lanes = filter.lanes.filter((item) => item !== value)), (value) => datasourceLane(value).label),
        ...valueFilter("waiting", "Incoming", filter.waiting, () => (filter.waiting = null), { label: filter.waiting === "Y" ? "Files incoming" : "No incoming files" }),
        ...listFilter("issue", "Issue", filter.issues, (value) => (filter.issues = filter.issues.filter((item) => item !== value)), issueLabel),
        ...searchFilter(this.$store),
      ];
    },
    // Issues by datasource id, computed once per catalogue or scan.
    issueIndex() {
      const index = new Map();
      this.datasourceCatalogue.forEach((row) => index.set(row.id, issuesOf(row, this.statusOf(row), this.stalledMinutes)));
      return index;
    },
    filteredDatasources() {
      const search = (this.getSearch || "").toUpperCase();
      const text = (this.filter.text || "").toUpperCase();
      const lanes = this.filter.lanes || [];
      const issues = this.filter.issues || [];
      if (!search && !text && !lanes.length && !this.filter.waiting && !issues.length) {
        return this.datasourceCatalogue;
      }
      return this.datasourceCatalogue.filter((row) => {
        const haystack = `${row.sourcename} ${row.input_directory} ${row.files_mask}`.toUpperCase();
        if (search && !haystack.includes(search)) return false;
        if (text && !haystack.includes(text)) return false;
        if (lanes.length && !lanes.includes(row.isactive)) return false;
        if (this.filter.waiting) {
          const waiting = ((this.statusOf(row) || {}).waiting || 0) > 0;
          if (waiting !== (this.filter.waiting === "Y")) return false;
        }
        if (issues.length) {
          const own = this.issueIndex.get(row.id) || [];
          if (!issues.some((key) => own.some((issue) => issue.key === key))) return false;
        }
        return true;
      });
    },
    sortedDatasources() {
      const key = this.sort.key;
      if (!key) {
        return this.filteredDatasources;
      }
      const valueOf = {
        waiting: (row) => (this.statusOf(row) || {}).waiting,
        last_load: (row) => (this.logOf(row) || {}).last_load,
      }[key] || ((row) => row[key]);
      return sortRows(this.filteredDatasources, valueOf, this.sort.dir);
    },
    nameColumnWidth() {
      const width = textWidth(
        this.datasourceCatalogue.map((row) => row.sourcename),
        "bold 16px Roboto, sans-serif"
      );
      // Only the name is in it (the issue chips are under the directories), so it is as wide as the longest one.
      return Math.min(Math.max(width + 28, 160), 340);
    },
    menuRow() {
      return this.datasourceCatalogue.find((row) => row.id === this.menuId) || null;
    },
    laneRow() {
      return this.datasourceCatalogue.find((row) => row.id === this.laneId) || null;
    },
  },
  methods: {
    ...mapActions(["updateDatasourceCatalogue", "updateDatasourceStatus"]),
    fillViewportToBottom,
    formatAge,
    formatBytes,
    formatNumber,
    sortIcon,
    toDateTimeString,
    toggleSort,
    lane: datasourceLane,
    statusOf(row) {
      const status = this.datasourceStatus;
      return status && status.datasources ? status.datasources[String(row.id)] : undefined;
    },
    logOf(row) {
      const status = this.statusOf(row);
      return status ? status.log : null;
    },
    issuesOf(row) {
      return this.issueIndex.get(row.id) || [];
    },
    directoriesOf(row) {
      return splitDirectories(row.input_directory);
    },
    missingOf(row) {
      const status = this.statusOf(row);
      return status && status.missing ? status.missing : [];
    },
    isMissing(row, path) {
      return this.missingOf(row).includes(path);
    },
    // The oldest waiting file's age when it was counted.
    ageOf(row) {
      const status = this.statusOf(row);
      return status && status.oldest ? this.datasourceStatus.scanned_epoch - status.oldest : null;
    },
    waitingClass(row) {
      const status = this.statusOf(row);
      if (status.stalled) return "text-red-6 text-weight-bold";
      if (status.waiting) return "text-weight-bold";
      return "text-grey-6";
    },
    addIssueFilter(key) {
      if (!this.filter.issues.includes(key)) {
        this.filter.issues.push(key);
      }
    },
    clearFilters() {
      this.filter.text = null;
      this.filter.lanes = [];
      this.filter.waiting = null;
      this.filter.issues = [];
      this.$store.commit("updateSearch", "");
    },
    async refreshCatalogue() {
      this.refreshing = true;
      this.loadError = false;
      try {
        await this.updateDatasourceCatalogue();
        this.loaded = true;
      } catch (error) {
        this.loadError = true;
        notifyError("Failed to load datasources.", error);
      } finally {
        this.refreshing = false;
      }
    },
    async refreshStatus() {
      try {
        await this.updateDatasourceStatus();
      } catch (error) {
        // The counts stay as they were; the next scan's event asks again.
      }
    },
    openRowMenu(event, row) {
      this.menuTarget = event.currentTarget;
      this.menuId = row.id;
      this.$nextTick(() => this.$refs.rowMenu.show());
    },
    openLaneMenu(event, row) {
      this.laneTarget = event.currentTarget;
      this.laneId = row.id;
      this.$nextTick(() => this.$refs.laneMenu.show());
    },
    // Saved at once, guarded by the lane the row showed; the notice can undo it.
    async setLane(row, value, undo = true) {
      if (row.isactive === value) {
        return;
      }
      const previous = row.isactive;
      try {
        await api("set-ds-active", { method: "POST", params: { id: row.id, value, expected: previous } });
      } catch (error) {
        notifyError(`The lane of ${row.sourcename} was not changed.`, error);
        await this.refreshCatalogue();
        return;
      }
      await this.refreshCatalogue();
      this.$q.notify({
        type: "positive",
        message: `${row.sourcename}: ${datasourceLane(previous).label} → ${datasourceLane(value).label}`,
        actions: undo ? [{ label: "Undo", color: "white", handler: () => this.setLane({ ...row, isactive: value }, previous, false) }] : [],
      });
    },
    async createDirectory(row, path) {
      try {
        await api("create-ds-directory", { method: "POST", params: { id: row.id, path } });
        this.$q.notify({ type: "positive", message: `${path} was created.` });
      } catch (error) {
        notifyError(`${path} was not created.`, error);
      }
    },
    // Names the tables whose links go and the file log rows left without a datasource, then deletes.
    async deleteDatasource(row) {
      let rows = null;
      try {
        rows = (await api("count-ds-file-log", { params: { id: row.id } })).rows;
      } catch (error) {
        rows = null;
      }
      const parts = [`The datasource ${escapeHtml(row.sourcename)} (ID ${row.id}) is deleted`];
      parts.push(row.tables.length ? `with its links to the tables ${row.tables.map(escapeHtml).join(", ")}; the tables themselves stay.` : "; it has no linked tables.");
      if (rows) {
        parts.push(`<br><br>Its ${formatNumber(rows)} file log row(s) stay in PDI_CORE_FILE_LOG, pointing to a datasource that no longer exists.`);
      }
      this.$q
        .dialog({ title: `Delete ${escapeHtml(row.sourcename)}?`, message: parts.join(" "), html: true, cancel: true, persistent: true, ok: { label: "Delete", color: "negative" } })
        .onOk(async () => {
          try {
            await api("delete-ds-config", { method: "DELETE", params: { id: row.id } });
            this.$q.notify({ type: "positive", message: `Datasource ${row.sourcename} was deleted.` });
          } catch (error) {
            notifyError("Datasource was not deleted.", error);
          }
          await this.refreshCatalogue();
        });
    },
  },
  // Also runs after the first mount.
  activated() {
    const stopCatalogue = liveRefetch("datasources:changed", this.refreshCatalogue, { filter: (payload) => payload.kind === "config" });
    const stopStatus = liveRefetch("datasources:changed", this.refreshStatus, { filter: (payload) => payload.kind === "status" });
    this.stopLiveUpdates = () => {
      stopCatalogue();
      stopStatus();
    };
    this.refreshCatalogue();
    this.refreshStatus();
  },
  deactivated() {
    this.stopLiveUpdates();
  },
};
</script>

<style scoped>
.sortable {
  cursor: pointer;
  user-select: none;
}

/* Fixed columns, so rows swapped in while scrolling don't resize them; the input directory takes the rest. */
.datasource-table :deep(table) {
  table-layout: fixed;
  min-width: calc(1100px + var(--name-column-width));
}
.datasource-table th:nth-child(1) { width: 84px; }
.datasource-table th:nth-child(2) { width: 56px; }
.datasource-table th:nth-child(3) { width: var(--name-column-width); }
.datasource-table th:nth-child(5) { width: 200px; }
.datasource-table th:nth-child(6) { width: 110px; }
.datasource-table th:nth-child(7) { width: 150px; }
.datasource-table th:nth-child(8) { width: 80px; }
.datasource-table th:nth-child(9) { width: 84px; }
.datasource-table th:nth-child(10) { width: 70px; }
.datasource-table th:nth-child(11) { width: 50px; }
.datasource-table td:nth-child(3),
.datasource-table td:nth-child(4) { white-space: normal; }

/* The same as the control names of the Controls page. */
.datasource-name {
  display: block;
  font-size: 16px;
  white-space: normal;
  overflow-wrap: anywhere;
  text-decoration: none;
}
.datasource-name:hover {
  text-decoration: underline;
}
/* The issue chips under the directories keep the page's font. */
.issue-chips {
  font-family: Roboto, sans-serif;
}
.path-cell,
.mask-cell {
  font-family: monospace;
  font-size: 12px;
}

/* A disabled datasource (ISACTIVE=0) is dimmed, its name still readable and a link. */
.row-inactive > td {
  color: #9e9e9e;
}
.row-inactive > td > * {
  opacity: 0.6;
}
.row-inactive .datasource-name {
  opacity: 1;
  color: #757575 !important;
}
</style>
