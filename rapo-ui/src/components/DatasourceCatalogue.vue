<template>
  <q-page class="column no-wrap" :style-fn="fillViewportToBottom">
    <div class="row items-end" :class="activeFilters.length || sortChip ? 'q-mb-sm' : 'q-mb-lg'">
      <h2 class="row items-center no-wrap text-no-wrap q-gutter-lg q-mb-none">
        <div v-if="showSkeleton">Datasources</div>
        <div v-else>{{ countTitle }}</div>
        <div v-if="refreshing && !showSkeleton">
          <q-avatar size="lg" color="grey-5">
            <q-icon name="fas fa-sync fa-spin" />
          </q-avatar>
        </div>
      </h2>
      <q-space />

      <!-- Lane and issue totals, laid out like the day totals of Results. -->
      <div v-if="!showSkeleton" class="row items-center justify-end q-gutter-x-md text-blue-grey-8">
        <div>
          <q-chip v-for="entry in laneCounts" :key="entry.lane.value" clickable @click="filter.lanes = [entry.lane.value]">
            <q-avatar :icon="entry.lane.icon" :color="entry.lane.color" text-color="white" />
            <span class="text-weight-bold q-mr-xs">{{ entry.lane.label }}</span>({{ entry.count }})
            <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">Show the datasources of {{ entry.lane.label }}</q-tooltip>
          </q-chip>
        </div>
        <!-- The datasources by issue, whatever the filters; a click filters by it. None with no datasource. -->
        <div v-if="issueCounts.length">
          <q-chip v-for="entry in issueCounts" :key="entry.key" clickable @click="addIssueFilter(entry.key)">
            <q-avatar :icon="entry.icon" :color="entry.color" text-color="white" />
            <span class="text-weight-bold q-mr-xs">{{ entry.label }}</span>({{ entry.count }})
            <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">Show the datasources flagged {{ entry.label }}</q-tooltip>
          </q-chip>
        </div>
      </div>
    </div>
    <filter-chips v-if="!showSkeleton" :filters="activeFilters" :sort="sortChip" class="q-mb-md" @clear="clearFilters" />

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
      :virtual-scroll-sticky-size-start="28"
      :table-colspan="11">
      <template #before>
        <thead>
          <tr class="bg-blue-grey-2">
            <th v-for="column in columns" :key="column.key" :title="column.title" :class="['text-' + column.align, { sortable: column.sort }]" @click="column.sort && toggleSort(sort, column.key)" v-keyboard="column.sort" :aria-sort="column.sort ? ariaSort(sort, column.key) : undefined">
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
          <td class="text-right text-grey-8 number-cell">{{ row.id }}</td>
          <td class="text-left">
            <router-link :to="{ name: 'edit-datasource', params: { id: row.id } }" class="datasource-name text-weight-bold text-grey-9">
              {{ row.sourcename }}
            </router-link>
          </td>
          <td class="text-left path-cell">
            <!-- A path opens the files of the datasource's input directories, the "All files" of the row menu. -->
            <div
              v-for="path in directoriesOf(row)"
              :key="path"
              class="ellipsis path-link"
              :title="`${path}\nShow all files in Input`"
              v-keyboard:button
              @click="$refs.fileDialog.open(row, 'all')">
              <q-icon v-if="isMissing(row, path)" name="fas fa-folder-minus" color="red-5" size="12px" class="q-mr-xs" />{{ path }}
            </div>
            <div class="ellipsis mask-line" :title="`FILES_MASK: ${row.files_mask}`">
              <q-icon name="fas fa-filter" size="10px" class="q-mr-xs" />{{ row.files_mask }}
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
          <td class="text-right number-cell">
            <template v-if="logOf(row)">
              {{ formatNumber(logOf(row).files) }}
              <q-tooltip>
                Last load {{ toDateTimeString(logOf(row).last_load).slice(5, 16) }}. In the last 24 hours: {{ formatNumber(logOf(row).files) }} file(s),
                {{ formatNumber(logOf(row).records || 0) }} record(s) written, {{ formatNumber(logOf(row).rejected || 0) }} rejected, {{ logOf(row).errors }} error(s),
                {{ logOf(row).duplicates }} duplicate(s)
              </q-tooltip>
            </template>
            <span v-else-if="datasourceStatus && !datasourceStatus.pending" class="text-grey-7" title="Nothing loaded in the last 24 hours">&ndash;</span>
          </td>
          <td class="text-right number-cell">{{ row.files_retention_days }}</td>
          <td class="text-right number-cell">{{ row.files_max_per_cycle }}</td>
          <td class="text-center">
            <q-icon v-if="row.leave_input_zipped" name="fas fa-file-archive" color="grey-7" size="14px" title="Input files are kept gzipped" />
          </td>
          <td class="text-center">
            <q-icon v-if="row.files_load_parallel" name="fas fa-stream" color="grey-7" size="14px" title="Files are loaded in parallel" />
          </td>
          <td class="text-center">
            <q-icon v-if="row.input_scan_subdirs" name="fas fa-sitemap" color="grey-7" size="14px" title="Subdirectories are scanned" />
          </td>
          <td>
            <q-btn aria-label="Row actions" size="sm" color="grey-7" round flat icon="fas fa-ellipsis-v" @click="openRowMenu($event, row)" />
          </td>
        </tr>
      </template>
      <template #after>
        <tbody v-if="showSkeleton">
          <skeleton-rows v-if="!loadError" :columns="['QChip', 'text', 'text', 'text', 'text', 'text', 'text', null, null, null, null]" />
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
import FilterChips from "./FilterChips.vue";
import SkeletonRows from "./SkeletonRows.vue";
import { api, notifyError } from "../api";
import { DATASOURCE_LANES, datasourceLane } from "../constants";
import { liveRefetch } from "../socket";
import { ISSUES, issuesOf, splitDirectories } from "../utils/datasources";
import { listFilter, searchFilter, valueFilter } from "../utils/filters";
import { escapeHtml, formatNumber, toDateTimeString } from "../utils/format";
import { fillViewportToBottom, textWidth } from "../utils/layout";
import { ariaSort, sortChip, sortIcon, sortRows, toggleSort } from "../utils/sort";
import persistFilters from "../mixins/persistFilters";

const COLUMNS = [
  { key: "isactive", label: "Lane", align: "center", sort: true, title: "The PDI Core lane that loads the datasource; click a lane to filter by it or switch it" },
  { key: "id", label: "ID", align: "right", sort: true, title: "The ID of the datasource (PDI_CORE_DS_CONFIG)" },
  { key: "sourcename", label: "Name", align: "left", sort: true, title: "The datasource's name, its description and issues; click the name to edit it" },
  { key: "input_directory", label: "Input files", align: "left", sort: true, title: "The input directories and, under them, the files mask; click a directory for its files" },
  { key: "files_24h", label: "Files 24h", align: "right", sort: true, title: "Files loaded in the last 24 hours; hover for records, errors and duplicates" },
  { key: "files_retention_days", label: "Ret. days", align: "right", sort: true, title: "Days archived files are kept" },
  { key: "files_max_per_cycle", label: "Max/cycle", align: "right", sort: true, title: "The most files one load cycle picks up" },
  { key: "leave_input_zipped", label: "Zipped", align: "center", sort: true, title: "Input files are kept gzipped" },
  { key: "files_load_parallel", label: "Parallel", align: "center", sort: true, title: "Files are loaded in parallel" },
  { key: "input_scan_subdirs", label: "Subdirs", align: "center", sort: true, title: "Subdirectories of the input directories are scanned too" },
];

// No column: the server's order, by name.
const DEFAULT_SORT = { key: null, dir: "asc" };

// The PDI Core datasources (pdi_core_ds_config), flagged by the issues of their setup and of the server's last scan of
// their directories (get-ds-status). Kept alive (App.vue): activated/deactivated start and stop its live refresh.
export default {
  name: "DatasourceCatalogue",
  mixins: [persistFilters("datasources", ["filter", "sort"])],
  components: { FileListDialog, FilterChips, SkeletonRows },
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
        issues: [],
      },
      sort: { ...DEFAULT_SORT },
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
    issueCounts() {
      const counts = new Map();
      this.issueIndex.forEach((issues) => issues.forEach((issue) => counts.set(issue.key, (counts.get(issue.key) || 0) + 1)));
      return ISSUES.filter((issue) => counts.get(issue.key)).map((issue) => ({ ...issue, count: counts.get(issue.key) }));
    },
    stalledMinutes() {
      return (this.datasourceStatus && this.datasourceStatus.stalled_minutes) || 60;
    },
    sortChip() {
      return sortChip(this.sort, DEFAULT_SORT, Object.fromEntries(this.columns.filter((column) => column.sort).map((column) => [column.key, column.label])), "by name");
    },
    activeFilters() {
      const filter = this.filter;
      const issueLabel = (key) => (ISSUES.find((issue) => issue.key === key) || {}).label || key;
      return [
        ...valueFilter("text", "Text", filter.text, () => (filter.text = null), { text: true }),
        ...listFilter("lane", "Lane", filter.lanes, (value) => (filter.lanes = filter.lanes.filter((item) => item !== value)), (value) => datasourceLane(value).label),
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
      if (!search && !text && !lanes.length && !issues.length) {
        return this.datasourceCatalogue;
      }
      return this.datasourceCatalogue.filter((row) => {
        const haystack = `${row.sourcename} ${row.input_directory} ${row.files_mask}`.toUpperCase();
        if (search && !haystack.includes(search)) return false;
        if (text && !haystack.includes(text)) return false;
        if (lanes.length && !lanes.includes(row.isactive)) return false;
        if (issues.length) {
          const own = this.issueIndex.get(row.id) || [];
          if (!issues.some((key) => own.some((issue) => issue.key === key))) return false;
        }
        return true;
      });
    },
    sortedDatasources() {
      const key = this.sort.key;
      // A sort kept from a column that is gone is ignored.
      if (!key || !COLUMNS.some((column) => column.key === key)) {
        return this.filteredDatasources;
      }
      const valueOf = {
        files_24h: (row) => (this.logOf(row) || {}).files,
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
    formatNumber,
    sortIcon,
    toDateTimeString,
    ariaSort,
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
    addIssueFilter(key) {
      if (!this.filter.issues.includes(key)) {
        this.filter.issues.push(key);
      }
    },
    clearFilters() {
      this.filter.text = null;
      this.filter.lanes = [];
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
/* Fixed columns, so rows swapped in while scrolling don't resize them; the input directory (with the mask under the
   paths) takes the rest. */
.datasource-table :deep(table) {
  table-layout: fixed;
  min-width: calc(900px + var(--name-column-width));
}
.datasource-table th:nth-child(1) { width: 84px; }
.datasource-table th:nth-child(2) { width: 56px; }
.datasource-table th:nth-child(3) { width: var(--name-column-width); }
.datasource-table th:nth-child(5) { width: 80px; }
.datasource-table th:nth-child(6) { width: 70px; }
.datasource-table th:nth-child(7) { width: 80px; }
.datasource-table th:nth-child(8) { width: 64px; }
.datasource-table th:nth-child(9) { width: 64px; }
.datasource-table th:nth-child(10) { width: 64px; }
.datasource-table th:nth-child(11) { width: 44px; }
.datasource-table td:nth-child(3) { white-space: normal; }

/* The same as the control names of the Controls page. */
.datasource-name {
  white-space: normal;
  overflow-wrap: anywhere;
}
.path-cell {
  font-family: var(--rapo-font-mono);
  font-size: 12px;
}
/* The issue chips under the directories keep the page's font. */
.path-cell .issue-chips {
  font-family: Roboto, sans-serif;
  font-size: 13px;
}
/* The files mask under the directories, light blue in both themes. */
.mask-line {
  color: var(--rapo-mask);
}
.path-link {
  cursor: pointer;
}
.path-link:hover {
  text-decoration: underline;
}

/* A disabled datasource (ISACTIVE=0) is dimmed, its name still readable and a link. */
.row-inactive > td > * {
  opacity: 0.6;
}
.row-inactive .datasource-name {
  opacity: 1;
  color: var(--rapo-muted) !important;
}
</style>
