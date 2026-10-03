<template>
  <q-page class="column no-wrap" :style-fn="fillViewportToBottom">
    <div class="row items-end" :class="activeFilters.length ? 'q-mb-sm' : 'q-mb-md'">
      <h2 class="row items-center no-wrap text-no-wrap q-gutter-lg q-mb-none">
        <div>File processing</div>
        <div><day-navigator :day="day" :today="today" :calendar="loadCalendar" :legend="{ count: 'files', errors: 'errors' }" @go="goToDay" /></div>
        <div v-if="refreshing && hasDay">
          <q-avatar size="lg" color="grey-5">
            <q-icon name="fas fa-sync fa-spin" />
          </q-avatar>
        </div>
      </h2>
      <q-space />

      <!-- The day's totals, whatever the filters, like the day totals of Results; a status chip filters by it. -->
      <div v-if="hasDay" class="column items-end text-blue-grey-8">
        <!-- Three groups: the day's files by status (and duplicates), the datasources Silent or with a Drop this day and, on
             today, those Stalled now. An issue counts the rows it filters to; the others are on the Datasources page. -->
        <div v-if="statusEntries.length || totals.duplicates || issueEntries.length" class="row items-center justify-end header-chips">
          <div v-if="statusEntries.length || totals.duplicates" class="row items-center">
            <q-chip v-for="entry in statusEntries" :key="entry.status" clickable @click="addStatusFilter(entry.status)">
              <q-avatar :icon="fileStatus(entry.status).icon" :color="fileStatus(entry.status).color" text-color="white" />
              <span class="text-weight-bold q-mr-xs">{{ fileStatus(entry.status).label }}</span>({{ formatNumber(entry.count) }})
            </q-chip>
            <q-chip v-if="totals.duplicates" clickable @click="filter.duplicates = true">
              <q-avatar icon="fas fa-clone" color="purple-3" text-color="white" />
              <span class="text-weight-bold q-mr-xs">Duplicate</span>({{ formatNumber(totals.duplicates) }})
              <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">Show the datasources with duplicate files</q-tooltip>
            </q-chip>
          </div>
          <div v-for="group in issueGroups" :key="group.key" class="row items-center">
            <q-chip v-for="entry in group.entries" :key="entry.key" clickable @click="addIssueFilter(entry.key)">
              <q-avatar :icon="entry.icon" :color="entry.color" text-color="white" />
              <span class="text-weight-bold q-mr-xs">{{ entry.label }}</span>({{ formatNumber(entry.count) }})
              <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">{{ entry.hint }}</q-tooltip>
            </q-chip>
          </div>
        </div>
        <div class="q-mr-xs">
          {{ formatNumber(totals.files) }} files &middot;
          <template v-if="totals.duplicates">{{ formatNumber(totals.duplicates) }} duplicates &middot;</template>
          {{ compactNumber(totals.read) }} read &middot;
          {{ compactNumber(totals.written) }} written
          <span :class="{ 'text-red-6': totals.rejected }">&middot; {{ compactNumber(totals.rejected) }} rejected</span>
          &middot; {{ formatDuration(totals.runtime) }} runtime
          <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">
            Records read {{ formatNumber(totals.read) }}, written {{ formatNumber(totals.written) }}, rejected {{ formatNumber(totals.rejected) }}; the runtimes of
            the files summed
          </q-tooltip>
        </div>
      </div>
    </div>
    <filter-chips v-if="hasDay" :filters="activeFilters" :shown="`${rows.length} of ${allRowsCount} datasources`" class="q-mb-sm" @clear="clearFilters" />

    <!-- The lanes (core_load schedulers) of PDI Core, as PDI_CORE_STATE says, and the lock of all of them. -->
    <div v-if="stateAvailable" class="row items-center q-gutter-x-sm q-mb-sm">
      <span class="text-blue-grey-8 q-mr-xs">Lanes</span>
      <q-chip
        v-for="lane in laneStates"
        :key="lane.value"
        :clickable="!lane.running || stateDelete"
        :outline="!lane.running"
        :color="lane.stale ? 'red-1' : undefined"
        :text-color="lane.stale ? 'red-9' : lane.running ? undefined : 'grey-7'"
        @click="clickLane(lane)">
        <q-avatar :icon="lane.running ? 'fas fa-sync' : lane.icon" :color="lane.running ? (lane.stale ? 'red-6' : lane.color) : 'grey-4'" text-color="white" />
        <span class="text-weight-bold q-mr-xs">{{ lane.label }}</span>
        <span v-if="lane.running">({{ formatAge(lane.age) }})</span>
        <span v-else class="text-grey-7">idle</span>
        <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">
          <template v-if="lane.running">
            Active since {{ toDateTimeString(lane.since) }}{{ lane.stale ? `, longer than ${staleMinutes} minutes: the lock may be stale` : "" }}.
            <span v-if="stateDelete">Click to remove its lock (LOAD_{{ lane.value }}).</span>
          </template>
          <template v-else>No core_load run holds LOAD_{{ lane.value }}. Click to show only its datasources.</template>
        </q-tooltip>
      </q-chip>
      <q-space />
      <q-btn v-if="!globalLock && stateWrite" outline dense no-caps color="negative" icon="fas fa-lock" label="Lock all lanes" padding="4px 10px" @click="setGlobalLock(true)">
        <q-tooltip>Insert the LOCK record of PDI_CORE_STATE: no core_load run starts while it exists</q-tooltip>
      </q-btn>
      <q-btn v-if="globalLock && stateDelete" outline dense no-caps color="positive" icon="fas fa-lock-open" label="Unlock all lanes" padding="4px 10px" @click="setGlobalLock(false)">
        <q-tooltip>Remove the LOCK record of PDI_CORE_STATE, so the lanes run again</q-tooltip>
      </q-btn>
    </div>
    <!-- Said rather than hidden: a synonym without the grant behind it, or a table not deployed, is worth knowing. -->
    <div v-else-if="pdiState && !pdiState.available" class="row items-center q-gutter-x-sm q-mb-sm text-grey-7">
      <span class="text-blue-grey-8 q-mr-xs">Lanes</span>
      <q-icon name="fas fa-exclamation-triangle" color="orange-8" size="14px" />
      <span>unavailable: PDI_CORE_STATE cannot be read by rapo's database user{{ pdiState.error ? ` (${pdiState.error})` : "" }}.</span>
      <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 6]" max-width="480px">
        Rapo reads PDI_CORE_STATE in its own schema, or through a private or public synonym to the owner's table, which needs a SELECT grant
        (INSERT and DELETE to lock and unlock). It checks again every minute.
      </q-tooltip>
    </div>
    <q-banner v-if="globalLock" dense rounded class="bg-red-1 text-red-10 q-mb-sm">
      <template #avatar><q-icon name="fas fa-lock" size="18px" /></template>
      All lanes are locked since {{ toDateTimeString(globalLock) }} (the LOCK record of PDI_CORE_STATE): PDI Core loads no file.
    </q-banner>

    <hour-heatmap v-if="hasDay" :rows="heatmap" :selected="filter.hour" class="q-mt-sm q-mb-md" @select="(hour) => (filter.hour = hour)" />

    <div class="row items-center q-mb-sm">
      <q-input
        ref="fileSearch"
        v-model="fileSearch"
        class="col-2 q-mb-md q-pa-sm"
        outlined
        clearable
        debounce="400"
        label="Find file"
        @update:model-value="searchFiles">
        <template #prepend><q-icon name="fas fa-search" size="14px" /></template>
        <q-menu v-model="fileSearchOpen" no-focus no-refocus fit :offset="[0, 4]" max-height="400px">
          <q-list dense style="min-width: 420px">
            <q-item-label header class="q-py-sm">
              {{ fileSearchResults.length >= 200 ? "The first 200 files" : `${fileSearchResults.length} file(s)` }} of {{ dayTitle }}
            </q-item-label>
            <q-item v-for="file in fileSearchResults" :key="file.id" clickable v-close-popup @click="openFile(file)">
              <q-item-section avatar>
                <q-icon :name="fileStatus(file.filestatus).icon" :color="fileStatus(file.filestatus).color" size="16px" />
              </q-item-section>
              <q-item-section>
                <q-item-label class="ellipsis">{{ file.inputfilename }}</q-item-label>
                <q-item-label caption>{{ file.sourcename }} &middot; {{ toDateTimeString(file.startloaddate).slice(11) }}</q-item-label>
              </q-item-section>
            </q-item>
            <q-item v-if="!fileSearchResults.length">
              <q-item-section class="text-grey-7">No file of that name</q-item-section>
            </q-item>
          </q-list>
        </q-menu>
      </q-input>

      <q-input clearable class="col q-mb-md q-pa-sm name-filter" outlined v-model="filter.text" label="Datasource" maxlength="60" />

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
        label="Lane">
      </q-select>

      <q-select
        v-model="filter.statuses"
        class="col-2 q-mb-md q-pa-sm"
        outlined
        options-dense
        emit-value
        map-options
        multiple
        use-chips
        :options="statusOptions"
        label="File status">
      </q-select>

      <q-select
        v-model="filter.issues"
        class="col-2 q-mb-md q-pa-sm"
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
      dense
      class="list-table files-table"
      :style="{ '--table-width': tableWidth + 'px' }"
      :items="sortedRows"
      :virtual-scroll-item-size="52"
      :virtual-scroll-sticky-size-start="28"
      :table-colspan="tableColumns.length">
      <template #before>
        <thead>
          <tr class="bg-blue-grey-2">
            <th
              v-for="column in tableColumns"
              :key="column.key"
              :class="['text-' + column.align, { sortable: column.sort }]"
              :style="{ width: column.width ? column.width + 'px' : undefined }"
              :title="column.title"
              v-keyboard="column.sort"
              :aria-sort="column.sort ? ariaSort(sort, column.key) : undefined"
              @click="column.sort && toggleSort(sort, column.key)">
              <q-icon v-if="column.status" :name="fileStatus(column.status).icon" :color="fileStatus(column.status).color" size="13px" class="q-mr-xs" />
              <q-icon v-else-if="column.icon" :name="column.icon" :color="column.iconColor" size="13px" class="q-mr-xs" />
              {{ column.label }}
              <q-icon v-if="sort.key === column.key" :name="sortIcon(sort)" size="12px" />
            </th>
          </tr>
        </thead>
      </template>
      <template #default="{ item: row }">
        <tr :key="row.id" :class="{ 'row-inactive': row.isactive === 0 }">
          <td v-for="column in tableColumns" :key="column.key" :class="['text-' + column.align, { 'number-cell': column.number, 'name-cell': column.key === 'sourcename' }]">
            <template v-if="column.key === 'isactive'">
              <q-chip v-if="row.isactive !== null" clickable :title="lane(row.isactive).label" @click="addLaneFilter(row.isactive)">
                <q-avatar :icon="lane(row.isactive).icon" :color="lane(row.isactive).color" text-color="white" />
                <span class="text-weight-bold">{{ lane(row.isactive).short }}</span>
              </q-chip>
            </template>
            <span v-else-if="column.key === 'id'" class="text-grey-8">{{ row.id }}</span>
            <template v-else-if="column.key === 'sourcename'">
              <router-link :to="logLink(row)" class="text-weight-bold text-grey-9 datasource-name">
                {{ row.sourcename }}
              </router-link>
              <div v-if="rowIssues(row).length" class="row items-center">
                <q-chip
                  v-for="issue in rowIssues(row)"
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
            </template>
            <!-- A count opens the files behind it (/files-log), with the status, hour and duplicate filters of this page. -->
            <template v-else-if="column.status">
              <router-link
                v-if="row.statuses[column.status]"
                :to="logLink(row, { status: column.status })"
                class="status-count"
                :class="statusClass(column.status, row.statuses[column.status])"
                :title="`Show the ${formatNumber(row.statuses[column.status])} ${fileStatus(column.status).label} file(s)`">
                {{ formatNumber(row.statuses[column.status]) }}
              </router-link>
            </template>
            <template v-else-if="column.key === 'duplicates'">
              <router-link
                v-if="row.duplicates"
                :to="logLink(row, { duplicate: 'Y' })"
                class="status-count text-purple-6 text-weight-bold"
                :title="`Show the ${formatNumber(row.duplicates)} duplicate file(s)`">
                {{ formatNumber(row.duplicates) }}
              </router-link>
            </template>
            <!-- Incoming files are not in the file log yet: FileListDialog lists them from the input directories. -->
            <template v-else-if="column.key === 'waiting'">
              <a
                v-if="waitingOf(row) && datasources.has(row.id)"
                href="#"
                class="status-count text-weight-bold"
                title="Show the files waiting in the input directories"
                @click.prevent="$refs.fileDialog.open(datasources.get(row.id), 'match')">
                {{ formatNumber(waitingOf(row)) }}
              </a>
              <span v-else-if="waitingOf(row) !== null" :class="waitingOf(row) ? 'text-weight-bold' : 'text-grey-7'">{{ formatNumber(waitingOf(row)) }}</span>
            </template>
            <span v-else-if="column.key === 'read'">{{ row.files ? formatNumber(row.read) : "" }}</span>
            <span v-else-if="column.key === 'written'">{{ row.files ? formatNumber(row.written) : "" }}</span>
            <span v-else-if="column.key === 'rejected'" :class="{ 'text-red-6 text-weight-bold': row.rejected }">{{ row.files ? formatNumber(row.rejected) : "" }}</span>
            <span v-else-if="column.key === 'runtime'">{{ row.files ? formatDuration(row.runtime) : "" }}</span>
            <span v-else-if="column.key === 'lastSuccess'">{{ toTimeString(row.lastSuccess) }}</span>
            <template v-else-if="column.key === 'change'">
              <span v-if="row.change !== null" :class="changeClass(row.change)" :title="`${row.dayFiles} file(s), ${row.weekBefore} a week earlier${isToday ? ' up to this time' : ''}`">
                {{ row.change > 0 ? "+" : "" }}{{ Math.round(row.change * 100) }}%
              </span>
            </template>
          </td>
        </tr>
      </template>
      <template #after>
        <tbody v-if="!hasDay">
          <skeleton-rows v-if="!loadError" :columns="tableColumns.map((column) => (column.key === 'isactive' ? 'QChip' : 'text'))" />
          <tr v-else>
            <td :colspan="tableColumns.length" class="text-center text-grey-7 q-pa-lg">The file log could not be loaded</td>
          </tr>
        </tbody>
        <tbody v-else-if="!sortedRows.length">
          <tr>
            <td :colspan="tableColumns.length" class="text-center text-grey-7 q-pa-lg">No datasource matches the filters</td>
          </tr>
        </tbody>
      </template>
    </q-virtual-scroll>

    <file-list-dialog ref="fileDialog" />
  </q-page>
</template>

<script>
import { mapActions, mapGetters, mapState } from "vuex";
import DayNavigator from "./DayNavigator.vue";
import HourHeatmap from "./HourHeatmap.vue";
import FilterChips from "./FilterChips.vue";
import SkeletonRows from "./SkeletonRows.vue";
import { api, notifyError } from "../api";
import { datasourceLane, fileStatus } from "../constants";
import { liveRefetch } from "../socket";
import { ISSUES as DATASOURCE_ISSUES, formatAge, issuesOf as datasourceIssuesOf } from "../utils/datasources";
import { ALWAYS_STATUSES, FILE_ISSUES, datasourceRows, dayStatuses, heatmapRows, hourRange, statusRank, statusTotals } from "../utils/files";
import FileListDialog from "./FileListDialog.vue";
import { listFilter, searchFilter, valueFilter } from "../utils/filters";
import { compactNumber, dayTitle, formatDuration, formatNumber, toDateTimeString, toTimeString } from "../utils/format";
import { fillViewportToBottom, textWidth } from "../utils/layout";
import { ariaSort, sortIcon, sortRows, toggleSort } from "../utils/sort";
import persistFilters from "../mixins/persistFilters";

// The Datasources page's issues this page shows too (on today), and the issues the header counts.
const FILE_DATASOURCE_ISSUES = ["stalled"];
const HEADER_ISSUES = ["silent", "drop", "ds_stalled"];

// The columns around the status columns (one per status the day has files in); `title` is the header's tooltip.
const LEADING_COLUMNS = [
  { key: "isactive", label: "Lane", align: "left", width: 84, title: "The PDI Core lane that loads the datasource; click a lane to filter by it" },
  { key: "id", label: "ID", align: "right", width: 56, title: "The ID of the datasource (PDI_CORE_DS_CONFIG)" },
  { key: "sourcename", label: "Datasource", align: "left", title: "The datasource; click its name to open its files of the day" },
];

// Incoming: files in the input directories now, not yet picked up into the file log (unlike its WAITING status), so
// only for today; after the Waiting column, where the workflow (read backwards from Success) starts.
const INCOMING_COLUMN = { key: "waiting", label: "Incoming", align: "right", width: 96, number: true, icon: "fas fa-inbox", iconColor: "blue-grey-6", title: "Files matching the mask in the input directories now, not yet in the file log (today only)" };

// Only when the day has any, after the RELOAD column (or the last status before it).
const DUPLICATES_COLUMN = { key: "duplicates", label: "Duplicates", align: "right", width: 96, number: true, icon: "fas fa-clone", iconColor: "purple-3", title: "Files PDI Core flagged as duplicates" };

const TRAILING_COLUMNS = [
  { key: "read", label: "Read", align: "right", width: 130, number: true, title: "Records read from the files" },
  { key: "written", label: "Written", align: "right", width: 130, number: true, title: "Records written to the tables of the datasource" },
  { key: "rejected", label: "Rejected", align: "right", width: 90, number: true, title: "Records rejected while loading" },
  { key: "runtime", label: "Runtime", align: "right", width: 100, number: true, title: "The runtimes of the files, summed (h:mm:ss)" },
  { key: "lastSuccess", label: "Last success", align: "right", width: 100, title: "When the last file of the day loaded successfully started loading" },
  { key: "change", label: "Trend", align: "right", width: 80, title: "The day's files against the same day a week earlier (today: up to this time)" },
];

// The PDI Core file log of one day, by datasource, like Results is for control runs: /files?date=YYYY-MM-DD (plain =
// the database's today). Built from aggregates (get-files-day), so that every filter applies at once; a datasource
// opens its files (/files-log/<id>). Kept alive (App.vue): activated/deactivated start and stop its live refresh.
export default {
  name: "FileResults",
  mixins: [persistFilters("files", ["filter", "sort"])],
  components: { DayNavigator, HourHeatmap, FileListDialog, FilterChips, SkeletonRows },
  data() {
    return {
      refreshing: false,
      loadError: false,
      fileSearch: "",
      fileSearchResults: [],
      fileSearchOpen: false,
      filter: {
        text: "",
        lanes: [],
        statuses: [],
        issues: [],
        hour: null,
        // Only the datasources with files flagged as duplicates.
        duplicates: false,
      },
      sort: {
        key: null,
        dir: "asc",
      },
    };
  },
  computed: {
    ...mapState(["fileDay", "pdiState", "datasourceCatalogue", "datasourceStatus"]),
    ...mapGetters(["getSearch", "getEnvInfo"]),
    // The day shown: ?date=YYYY-MM-DD, or the database's today.
    day() {
      return this.$route.query.date || this.today;
    },
    today() {
      return this.fileDay ? this.fileDay.today : null;
    },
    hasDay() {
      return Boolean(this.fileDay) && this.fileDay.date === this.day;
    },
    dayTitle() {
      return dayTitle(this.day);
    },
    dayQuery() {
      return this.$route.query.date ? { date: this.$route.query.date } : {};
    },
    isToday() {
      return Boolean(this.day) && this.day >= this.today;
    },
    datasources() {
      return new Map(this.datasourceCatalogue.map((row) => [row.id, row]));
    },
    totals() {
      return statusTotals(this.hasDay ? this.fileDay.cells : []);
    },
    statusEntries() {
      return Object.entries(this.totals.statuses)
        .sort((a, b) => b[1] - a[1])
        .map(([status, count]) => ({ status, count }));
    },
    // Rows by datasource with the cells that pass the filters; the active datasources without files while no status
    // or hour is picked.
    rows() {
      if (!this.hasDay) {
        return [];
      }
      const statuses = this.filter.statuses || [];
      const hour = this.filter.hour;
      const withoutFiles = !statuses.length && hour === null;
      return datasourceRows(
        this.fileDay,
        this.datasources,
        (cell) => this.datasourceMatches(cell.sourceid) && (!statuses.length || statuses.includes(cell.status)) && (hour === null || cell.hour === hour),
        (row) => this.datasourceMatches(row.id) && this.issuesMatch(row) && (!this.filter.duplicates || row.duplicates > 0),
        withoutFiles
      );
    },
    // The day's rows whatever the filters: the count of the filter badge and of the issue chips.
    allRows() {
      if (!this.hasDay) {
        return [];
      }
      return datasourceRows(this.fileDay, this.datasources, () => true, () => true, true);
    },
    allRowsCount() {
      return this.allRows.length;
    },
    // Only on today: Stalled, of the Datasources page's issues, describes the datasources now, not a past day; the
    // others are about a datasource's setup and stay there. Keyed ds_<key>, so that the Issue filter tells them apart.
    showDatasourceIssues() {
      return this.hasDay && this.isToday;
    },
    stalledMinutes() {
      return (this.datasourceStatus && this.datasourceStatus.stalled_minutes) || 60;
    },
    datasourceIssues() {
      const byId = new Map();
      if (!this.showDatasourceIssues) {
        return byId;
      }
      const statuses = (this.datasourceStatus && this.datasourceStatus.datasources) || {};
      this.datasourceCatalogue.forEach((row) => {
        const issues = datasourceIssuesOf(row, statuses[String(row.id)], this.stalledMinutes)
          .filter((issue) => FILE_DATASOURCE_ISSUES.includes(issue.key))
          .map((issue) => ({ ...issue, key: `ds_${issue.key}` }));
        if (issues.length) {
          byId.set(row.id, issues);
        }
      });
      return byId;
    },
    // Every issue the filter can pick: the day's, then (on today) the Datasources page's.
    issueKinds() {
      const datasourceKinds = this.showDatasourceIssues
        ? DATASOURCE_ISSUES.filter((issue) => FILE_DATASOURCE_ISSUES.includes(issue.key)).map((issue) => ({
            ...issue,
            key: `ds_${issue.key}`,
            group: "datasource",
            hint: "Active datasources whose oldest incoming file has waited too long, as they are now",
          }))
        : [];
      return [...FILE_ISSUES.map((issue) => ({ ...issue, group: "day" })), ...datasourceKinds];
    },
    // The issue chips of the header (HEADER_ISSUES), by the rows of the day whatever the filters; none with no datasource.
    issueGroups() {
      const counts = new Map();
      this.allRows.forEach((row) => this.rowIssues(row).forEach((issue) => counts.set(issue.key, (counts.get(issue.key) || 0) + 1)));
      const entries = this.issueKinds.filter((kind) => HEADER_ISSUES.includes(kind.key) && counts.get(kind.key)).map((kind) => ({ ...kind, count: counts.get(kind.key) }));
      return ["day", "datasource"]
        .map((key) => ({ key, entries: entries.filter((entry) => entry.group === key) }))
        .filter((group) => group.entries.length);
    },
    issueEntries() {
      return this.issueGroups.flatMap((group) => group.entries);
    },
    // The heatmap follows the datasources shown and the statuses, but not the hour, which it picks.
    heatmap() {
      if (!this.hasDay) {
        return [];
      }
      const shown = new Set(this.rows.map((row) => row.id));
      const statuses = this.filter.statuses || [];
      return heatmapRows(this.fileDay, this.datasources, (cell) => shown.has(cell.sourceid) && (!statuses.length || statuses.includes(cell.status)));
    },
    // The statuses the day has files in, whatever the filters, so the columns stay put while filtering, and always
    // Waiting, Started and Success.
    statusColumns() {
      return dayStatuses(this.hasDay ? this.fileDay.cells : [], ALWAYS_STATUSES).map((status) => ({
        key: `status:${status}`,
        status,
        label: fileStatus(status).label,
        align: "right",
        width: 96,
        number: true,
        title: fileStatus(status).hint || `Files in ${status}`,
      }));
    },
    tableColumns() {
      // Incoming only for today, after Waiting; Duplicates only when the day has any, after Reload.
      const statuses = [...this.statusColumns];
      const insertAfter = (last, column) => statuses.splice(statuses.filter((other) => !other.status || statusRank(other.status) <= statusRank(last)).length, 0, column);
      if (this.isToday) insertAfter("WAITING", INCOMING_COLUMN);
      if (this.totals.duplicates > 0) insertAfter("RELOAD", DUPLICATES_COLUMN);
      return [...LEADING_COLUMNS, ...statuses, ...TRAILING_COLUMNS].map((column) => ({ sort: true, ...column, width: column.key === "sourcename" ? this.nameColumnWidth : column.width }));
    },
    tableWidth() {
      return this.tableColumns.reduce((total, column) => total + (column.width || 0), 0);
    },
    sortedRows() {
      const key = this.sort.key;
      // A kept sort on a column that is not shown (a status the day has none of, the former Files column) is ignored.
      if (!key || !this.tableColumns.some((column) => column.key === key)) {
        return this.rows;
      }
      const valueOf = key.startsWith("status:")
        ? (row) => row.statuses[key.slice(7)] || null
        : { waiting: (row) => this.waitingOf(row) }[key] || ((row) => row[key]);
      return sortRows(this.rows, valueOf, this.sort.dir);
    },
    // The Datasource column fits the longest name of the day, whatever the filters, so it doesn't change width while
    // filtering; the issue chips wrap under the name.
    nameColumnWidth() {
      const names = this.hasDay ? datasourceRows(this.fileDay, this.datasources, () => true, () => true, true).map((row) => row.sourcename) : [];
      const width = textWidth(names, "bold 16px Roboto, sans-serif");
      return Math.max(width + 32, 200);
    },
    laneOptions() {
      const lanes = new Set(this.datasourceCatalogue.map((row) => row.isactive));
      return [...lanes].sort((a, b) => a - b).map((value) => ({ label: datasourceLane(value).label, value }));
    },
    // The statuses the day has files in (as the status columns), and a picked one it has none in, so it can be removed.
    statusOptions() {
      const statuses = dayStatuses(this.hasDay ? this.fileDay.cells : []);
      (this.filter.statuses || []).forEach((status) => statuses.includes(status) || statuses.push(status));
      return statuses.map((value) => ({ label: fileStatus(value).label, value }));
    },
    issueOptions() {
      return this.issueKinds.map((issue) => ({ label: issue.label, value: issue.key }));
    },
    activeFilters() {
      const filter = this.filter;
      const issueLabel = (key) => (this.issueKinds.find((issue) => issue.key === key) || {}).label || key;
      const hourLabel = filter.hour === null ? null : hourRange(filter.hour);
      return [
        ...valueFilter("text", "Datasource", filter.text, () => (filter.text = null), { text: true }),
        ...listFilter("lane", "Lane", filter.lanes, (value) => (filter.lanes = filter.lanes.filter((item) => item !== value)), (value) => datasourceLane(value).label),
        ...listFilter("status", "Status", filter.statuses, (value) => (filter.statuses = filter.statuses.filter((item) => item !== value)), (value) => fileStatus(value).label),
        ...listFilter("issue", "Issue", filter.issues, (value) => (filter.issues = filter.issues.filter((item) => item !== value)), issueLabel),
        ...valueFilter("hour", "Hour", filter.hour, () => (filter.hour = null), { label: hourLabel }),
        ...valueFilter("duplicates", "Duplicates", filter.duplicates || null, () => (filter.duplicates = false), { label: "With duplicate files" }),
        ...searchFilter(this.$store),
      ];
    },
    stateAvailable() {
      return Boolean(this.pdiState && this.pdiState.available);
    },
    stateWrite() {
      return Boolean(this.getEnvInfo && this.getEnvInfo.datasources_state_write);
    },
    stateDelete() {
      return Boolean(this.getEnvInfo && this.getEnvInfo.datasources_state_delete);
    },
    staleMinutes() {
      return (this.pdiState && this.pdiState.lock_stale_minutes) || 30;
    },
    globalLock() {
      return this.pdiState ? this.pdiState.lock : null;
    },
    // Every lane with datasources, and any other lane holding a lock; the age by the database's clock.
    laneStates() {
      const state = this.pdiState || { lanes: {} };
      const values = new Set(this.datasourceCatalogue.map((row) => row.isactive).filter(Boolean));
      Object.keys(state.lanes || {}).forEach((lane) => values.add(Number(lane)));
      return [...values]
        .sort((a, b) => a - b)
        .map((value) => {
          const since = (state.lanes || {})[value] || null;
          const age = since && state.database_time ? Math.max((new Date(state.database_time) - new Date(since)) / 1000, 0) : null;
          return { ...datasourceLane(value), running: Boolean(since), since, age, stale: age !== null && age > this.staleMinutes * 60 };
        });
    },
  },
  methods: {
    ...mapActions(["updateFileDay", "updatePdiState", "updateDatasourceCatalogue", "updateDatasourceStatus"]),
    compactNumber,
    formatDuration,
    fileStatus,
    fillViewportToBottom,
    formatAge,
    formatNumber,
    sortIcon,
    toDateTimeString,
    toTimeString,
    ariaSort,
    toggleSort,
    lane: datasourceLane,
    datasourceMatches(id) {
      const datasource = this.datasources.get(id);
      const lanes = this.filter.lanes || [];
      if (lanes.length && !(datasource && lanes.includes(datasource.isactive))) {
        return false;
      }
      const name = (datasource ? datasource.sourcename : (this.fileDay && this.fileDay.names && this.fileDay.names[id]) || `#${id}`).toUpperCase();
      const text = (this.filter.text || "").toUpperCase();
      const search = (this.getSearch || "").toUpperCase();
      return (!text || name.includes(text)) && (!search || name.includes(search));
    },
    // The day's issues of a row, then (on today) those of its datasource.
    rowIssues(row) {
      const datasource = this.datasourceIssues.get(row.id);
      return datasource ? [...row.issues, ...datasource] : row.issues;
    },
    issuesMatch(row) {
      const issues = this.filter.issues || [];
      return !issues.length || issues.some((key) => this.rowIssues(row).some((issue) => issue.key === key));
    },
    waitingOf(row) {
      const status = this.datasourceStatus && this.datasourceStatus.datasources ? this.datasourceStatus.datasources[String(row.id)] : null;
      return status && status.waiting !== undefined ? status.waiting : null;
    },
    statusClass(status, count) {
      if (!count) return "";
      return status === "ERROR" ? "text-red-6 text-weight-bold" : ["RECYCLE", "RELOAD", "DELETE"].includes(status) ? "text-indigo-7 text-weight-bold" : "";
    },
    changeClass(change) {
      return change <= -0.5 ? "text-red-6 text-weight-bold" : change < 0 ? "text-orange-9" : "text-grey-8";
    },
    // The file log of a datasource on this day, filtered as this page is: the statuses (or the one of the count clicked),
    // the hour and, for the duplicates, only them. `status` is always in the query, so that the filters kept for the
    // file log do not apply and the list adds up to the count.
    logLink(row, { status = null, duplicate = null } = {}) {
      const query = { ...this.dayQuery, status: (status ? [status] : this.filter.statuses || []).join(",") };
      if (this.filter.hour !== null) {
        query.hour = String(this.filter.hour);
      }
      if (duplicate) {
        query.dup = duplicate;
      }
      return { name: "files-log", params: { id: row.id }, query };
    },
    addStatusFilter(status) {
      if (!this.filter.statuses.includes(status)) {
        this.filter.statuses.push(status);
      }
    },
    // A running lane's chip removes its lock; an idle one filters the page by the lane.
    clickLane(lane) {
      if (!lane.running) {
        this.addLaneFilter(lane.value);
      } else if (this.stateDelete) {
        this.removeLaneLock(lane);
      }
    },
    addLaneFilter(lane) {
      if (!this.filter.lanes.includes(lane)) {
        this.filter.lanes.push(lane);
      }
    },
    addIssueFilter(key) {
      if (!this.filter.issues.includes(key)) {
        this.filter.issues.push(key);
      }
    },
    clearFilters() {
      this.filter.text = null;
      this.filter.lanes = [];
      this.filter.statuses = [];
      this.filter.issues = [];
      this.filter.hour = null;
      this.filter.duplicates = false;
      this.$store.commit("updateSearch", "");
    },
    // The calendar dots of a month (YYYY-MM) for the day pill.
    loadCalendar(month) {
      return api("get-files-calendar", { params: { month }, loadingBar: false });
    },
    goToDay(day) {
      this.$router.push({ name: "files", query: day && day !== this.today ? { date: day } : {} });
    },
    async refreshDay() {
      this.refreshing = true;
      this.loadError = false;
      try {
        await this.updateFileDay(this.$route.query.date || null);
      } catch (error) {
        this.loadError = true;
        notifyError("Failed to load the file log.", error);
      } finally {
        this.refreshing = false;
      }
    },
    // Asked for whatever the instance details say (they may not have arrived yet); a server without the table
    // answers available: false.
    async refreshState() {
      try {
        await this.updatePdiState();
      } catch (error) {
        // The lanes stay as they were; the next state event asks again.
      }
    },
    async searchFiles(text) {
      const value = (text || "").trim();
      if (value.length < 3) {
        this.fileSearchResults = [];
        this.fileSearchOpen = false;
        return;
      }
      try {
        this.fileSearchResults = await api("search-files", { params: { text: value, date: this.$route.query.date || null }, loadingBar: false });
        this.fileSearchOpen = true;
      } catch (error) {
        notifyError("The files could not be searched.", error);
      }
    },
    openFile(file) {
      this.$router.push({ name: "files-log", params: { id: file.sourceid }, query: { ...this.dayQuery, file: file.id } });
    },
    removeLaneLock(lane) {
      const warning = lane.stale
        ? `It is older than ${this.staleMinutes} minutes, so the core_load run holding it has probably died.`
        : `<b>It is only ${formatAge(lane.age)} old: if its core_load run is still going, a second run may start beside it and process the same files.</b>`;
      this.$q
        .dialog({
          title: `Remove the lock of ${lane.label}?`,
          message: `Deletes LOAD_${lane.value} (active since ${toDateTimeString(lane.since)}) from PDI_CORE_STATE, so the lane runs again. ${warning}`,
          html: true,
          cancel: true,
          persistent: true,
          ok: { label: "Remove lock", color: lane.stale ? "primary" : "negative" },
        })
        .onOk(async () => {
          try {
            await api("remove-lane-lock", { method: "POST", params: { lane: lane.value, since: lane.since } });
            this.$q.notify({ type: "positive", message: `The lock of ${lane.label} was removed.` });
          } catch (error) {
            notifyError(`The lock of ${lane.label} was not removed.`, error);
          }
          this.refreshState();
        });
    },
    setGlobalLock(on) {
      const run = async () => {
        try {
          await api("set-global-lock", { method: "POST", params: { on } });
          this.$q.notify({ type: on ? "warning" : "positive", message: on ? "All lanes are locked." : "The lanes are unlocked." });
        } catch (error) {
          notifyError(on ? "The lanes were not locked." : "The lanes were not unlocked.", error);
        }
        this.refreshState();
      };
      if (!on) {
        run();
        return;
      }
      this.$q
        .dialog({
          title: "Lock all lanes?",
          message: "Inserts the LOCK record into PDI_CORE_STATE: no core_load run starts until it is removed, so no file is loaded. Runs going on finish.",
          cancel: true,
          persistent: true,
          ok: { label: "Lock all lanes", color: "negative" },
        })
        .onOk(run);
    },
  },
  watch: {
    // The Datasources page's issues describe today, so their filters are dropped once another day is shown.
    hasDay(loaded) {
      if (loaded && !this.isToday && (this.filter.issues || []).some((key) => key.startsWith("ds_"))) {
        this.filter.issues = this.filter.issues.filter((key) => !key.startsWith("ds_"));
      }
    },
    // Day navigation only changes the query; the filters and the sort are kept.
    "$route.query.date"() {
      if (this.active && this.$route.name === "files") {
        this.filter.hour = null;
        this.refreshDay();
      }
    },
  },
  activated() {
    this.active = true;
    const stops = [
      liveRefetch("datasources:changed", () => this.updateFileDay(this.$route.query.date || null), { filter: (payload) => payload.kind === "files", interval: 15000 }),
      liveRefetch("datasources:changed", this.refreshState, { filter: (payload) => payload.kind === "state" }),
      liveRefetch("datasources:changed", this.updateDatasourceStatus, { filter: (payload) => payload.kind === "status" }),
      liveRefetch("datasources:changed", this.updateDatasourceCatalogue, { filter: (payload) => payload.kind === "config" }),
    ];
    this.stopLiveUpdates = () => stops.forEach((stop) => stop());
    this.refreshDay();
    this.refreshState();
    this.updateDatasourceCatalogue().catch(() => null);
    this.updateDatasourceStatus().catch(() => null);
  },
  deactivated() {
    this.active = false;
    this.stopLiveUpdates();
  },
};
</script>

<style scoped>
.header-chips {
  column-gap: 16px;
}
.datasource-name {
  white-space: nowrap;
}
/* The table keeps its columns' widths and scrolls sideways inside the list, never widening the page. */
.files-table :deep(table) {
  table-layout: fixed;
  min-width: var(--table-width);
}
.files-table td {
  white-space: nowrap;
}
.status-count {
  color: inherit;
  text-decoration: none;
}
.status-count:hover {
  text-decoration: underline;
}
.files-table td.name-cell { white-space: normal; }
</style>
