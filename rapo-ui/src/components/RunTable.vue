<template>
  <div class="run-table column no-wrap">
    <q-resize-observer @resize="onResize" />
    <q-virtual-scroll
      ref="scroll"
      type="table"
      dense
      class="list-table runs-table"
      :class="{ 'with-name': show.name, 'runs-table--compact': compact }"
      :style="{ '--name-column-width': nameWidth + 'px', '--table-min-width': tableMinWidth + 'px' }"
      :items="shownRuns"
      :virtual-scroll-item-size="45"
      :virtual-scroll-sticky-size-start="28"
      :table-colspan="colspan">
      <template #before>
        <thead>
          <tr class="bg-blue-grey-2">
            <th v-if="show.type" :title="filterable ? 'The control type: ANL analysis, REC reconciliation, CMP comparison, REP report; click a type to filter by it' : 'The control type: ANL analysis, REC reconciliation, CMP comparison, REP report'" class="col-type text-left sortable" @click="toggleSort(sort, 'control_type')" v-keyboard :aria-sort="ariaSort(sort, 'control_type')">
              Type
              <q-icon v-if="sort.key === 'control_type'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th :title="filterable ? 'When the run started, and what started it: hover its icon, click it to filter by it (again: clears the filter)' : 'When the run started, and what started it: hover its icon'" class="col-start text-left sortable" @click="toggleSort(sort, 'start_date')" v-keyboard :aria-sort="ariaSort(sort, 'start_date')">
              Start
              <q-icon v-if="sort.key === 'start_date'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th title="How long the run took, in minutes" class="col-runtime text-right sortable" @click="toggleSort(sort, 'duration_minutes')" v-keyboard :aria-sort="ariaSort(sort, 'duration_minutes')">
              Runtime
              <q-icon v-if="sort.key === 'duration_minutes'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th
              title="Runs of this period: this run and the earlier ones it superseded (any later run of the same period supersedes them); click a number to show or fold them"
              class="col-ver text-center">
              <span
                v-if="grouping.earlier.size"
                class="run-ver-all"
                :class="{ 'run-ver-all--on': expandAll }"
                :title="expandAll ? 'Fold the earlier runs of every period' : 'Show the earlier runs of every period'"
                v-keyboard:button
                @click.stop="toggleExpandAll">
                Ver
              </span>
              <template v-else>Ver</template>
            </th>
            <th title="The process ID of the run; click a value to copy it" class="col-pid text-center sortable" @click="toggleSort(sort, 'process_id')" v-keyboard :aria-sort="ariaSort(sort, 'process_id')">
              PID
              <q-icon v-if="sort.key === 'process_id'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th v-if="show.name" :title="filterable ? 'The control the run belongs to: its name opens its Run log on the run, the magnifier filters by it (again: clears the filter)' : 'The control the run belongs to: its name opens the control'" class="col-name text-left sortable" @click="toggleSort(sort, 'control_name')" v-keyboard :aria-sort="ariaSort(sort, 'control_name')">
              Control
              <q-icon v-if="sort.key === 'control_name'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th
              v-if="compact"
              title="The data window the run read: its day, or its first and last day; sorted by its start"
              class="col-period text-left sortable"
              @click="toggleSort(sort, 'date_from')"
              v-keyboard
              :aria-sort="ariaSort(sort, 'date_from')">
              Period
              <q-icon v-if="sort.key === 'date_from'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th v-if="!compact" title="The start of the data window the run read" class="col-date text-left sortable" @click="toggleSort(sort, 'date_from')" v-keyboard :aria-sort="ariaSort(sort, 'date_from')">
              Run from
              <q-icon v-if="sort.key === 'date_from'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th v-if="!compact" title="The end of the data window the run read" class="col-date text-left sortable" @click="toggleSort(sort, 'date_to')" v-keyboard :aria-sort="ariaSort(sort, 'date_to')">
              Run to
              <q-icon v-if="sort.key === 'date_to'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th title="Records fetched from datasource A; click the number for its SQL or data analysis" class="col-fetched text-right sortable" @click="toggleSort(sort, 'fetched_number_a')" v-keyboard :aria-sort="ariaSort(sort, 'fetched_number_a')">
              Fetched A
              <q-icon v-if="sort.key === 'fetched_number_a'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th v-if="showB" title="Records fetched from datasource B; click the number for its SQL or data analysis" class="col-fetched text-right sortable" @click="toggleSort(sort, 'fetched_number_b')" v-keyboard :aria-sort="ariaSort(sort, 'fetched_number_b')">
              Fetched B
              <q-icon v-if="sort.key === 'fetched_number_b'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th title="Discrepancies found on side A (the result rows of ANL, CMP and REP); click the number for its SQL or data analysis" class="col-discr text-right sortable" @click="toggleSort(sort, 'error_number_a')" v-keyboard :aria-sort="ariaSort(sort, 'error_number_a')">
              Discr. A
              <q-icon v-if="sort.key === 'error_number_a'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th v-if="showB" title="Discrepancies found on side B; click the number for its SQL or data analysis" class="col-discr text-right sortable" @click="toggleSort(sort, 'error_number_b')" v-keyboard :aria-sort="ariaSort(sort, 'error_number_b')">
              Discr. B
              <q-icon v-if="sort.key === 'error_number_b'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th title="Discrepancies of side A as a percentage of the records fetched from A" class="col-level text-right sortable" @click="toggleSort(sort, 'error_level_a')" v-keyboard :aria-sort="ariaSort(sort, 'error_level_a')">
              {{ compact ? "Err. A %" : "Err. lvl A [%]" }}
              <q-icon v-if="sort.key === 'error_level_a'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th v-if="showB" title="Discrepancies of side B as a percentage of the records fetched from B" class="col-level text-right sortable" @click="toggleSort(sort, 'error_level_b')" v-keyboard :aria-sort="ariaSort(sort, 'error_level_b')">
              {{ compact ? "Err. B %" : "Err. lvl B [%]" }}
              <q-icon v-if="sort.key === 'error_level_b'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th
              v-for="kpi in kpiColumns"
              :key="kpi.kpi_type"
              :title="kpiHeaderTitle(kpi)"
              class="col-kpi text-right sortable ellipsis"
              @click="toggleSort(sort, kpiSortKey(kpi))"
              v-keyboard
              :aria-sort="ariaSort(sort, kpiSortKey(kpi))">
              {{ kpi.kpi_type }}
              <q-icon v-if="sort.key === kpiSortKey(kpi)" :name="sortIcon(sort)" size="12px" />
            </th>
            <th
              v-if="kpiSummary.length"
              title="The KPIs stored for the run by priority, green within their limits, on the alarm's color when alarmed; hover a value for its KPI, + for all of them; sorts by the highest alarm"
              class="col-kpis text-left sortable"
              @click="toggleSort(sort, KPI_ALARM_SORT, 'desc')"
              v-keyboard
              :aria-sort="ariaSort(sort, KPI_ALARM_SORT)">
              KPIs
              <q-icon v-if="sort.key === KPI_ALARM_SORT" :name="sortIcon(sort)" size="12px" />
            </th>
            <th :title="filterable ? 'The status of the run; click a status to filter by it' : 'The status of the run'" class="col-status text-left sortable" @click="toggleSort(sort, 'status')" v-keyboard :aria-sort="ariaSort(sort, 'status')">
              Status
              <q-icon v-if="sort.key === 'status'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="col-menu text-left"></th>
          </tr>
        </thead>
      </template>
      <template #default="{ item: run, index }">
        <tr
          :key="run.process_id"
          :class="{
            'run-row--group-edge': groupEdge(index),
            'run-row--superseded': run.superseded_by,
            'run-row--folded': grouping.folded.has(run.process_id),
            'run-row--focus': run.process_id === selected,
            'run-row--selectable': selectable,
          }"
          @click="selectable && selectRow(run, $event)">
          <td v-if="show.type" class="text-center run-chip-cell">
            <q-chip :clickable="filterable" :title="controlType(run.control_type).label" @click="filterable && $emit('filter', { type: run.control_type })">
              <q-avatar :icon="controlType(run.control_type).icon" :color="controlType(run.control_type).color" text-color="white" />
              {{ run.control_type }}
            </q-chip>
          </td>
          <td class="text-left">
            <div class="text-blue-grey-7 no-wrap row items-center">
              <strong>{{ toDateString(run.start_date) }}</strong>
              <small class="text-grey-7 q-px-sm">{{ toTimeString(run.start_date) }}</small>
              <q-icon
                :name="triggerOf(run).icon"
                size="11px"
                :class="[run.trigger_type ? 'text-blue-grey-4' : 'text-grey-4', { 'cursor-pointer': filterable }]"
                :title="filterable ? `${triggerTitle(run)}; click to filter by it` : triggerTitle(run)"
                v-keyboard:button="filterable"
                :aria-label="filterable ? `Filter by ${triggerTitle(run)}` : undefined"
                @click="filterable && $emit('filter', { trigger_type: triggerKey(run) })" />
            </div>
          </td>
          <td class="text-right number-cell">{{ round(run.duration_minutes, 1) }} min</td>
          <td class="text-center">
            <span
              v-if="grouping.earlier.has(run.process_id)"
              class="run-ver run-ver--link"
              :style="versionStyle(grouping.earlier.get(run.process_id) + 1)"
              :title="`${grouping.earlier.get(run.process_id) + 1} runs of this period: ${isExpanded(run.process_id) ? 'fold' : 'show'} the ${grouping.earlier.get(run.process_id)} earlier one(s) it superseded`"
              v-keyboard:button
              @click="toggleExpanded(run.process_id)">
              {{ grouping.earlier.get(run.process_id) + 1 }}
            </span>
            <span
              v-else-if="grouping.versions.has(run.process_id)"
              class="run-ver run-ver--old"
              :class="{ 'run-ver--link': openRuns }"
              :title="openRuns ? `${supersededTitle(run)}; click to open the run log on this run` : supersededTitle(run)"
              v-keyboard:button="openRuns"
              @click="openRuns && $emit('open-run', run)">
              {{ grouping.versions.get(run.process_id) }}
            </span>
            <q-icon
              v-else-if="run.superseded_by"
              name="fas fa-history"
              size="12px"
              color="blue-grey-5"
              :class="{ 'cursor-pointer': openRuns }"
              :title="openRuns ? `${supersededTitle(run)}; click to open the run log on this run` : supersededTitle(run)"
              v-keyboard:button="openRuns"
              :aria-label="openRuns ? 'Open the run log on this run' : undefined"
              @click="openRuns && $emit('open-run', run)" />
            <span v-else class="run-ver" :style="versionStyle(1)" title="The only run of this period">1</span>
          </td>
          <td class="text-center text-weight-bold text-blue-grey-7 number-cell">
            <span class="cursor-pointer number-link" v-keyboard:button :title="`Copy process ID ${run.process_id}`" @click="copyProcessId(run)">{{ run.process_id }}</span>
          </td>
          <td v-if="show.name" class="text-left text-weight-bold text-teal-8 ellipsis" :title="run.control_name">
            <q-btn
              v-if="filterable"
              :aria-label="isFilteredName(run) ? 'Clear the filter by this control' : 'Filter by this control'"
              :aria-pressed="isFilteredName(run)"
              size="7px"
              :color="isFilteredName(run) ? 'teal-8' : 'grey-5'"
              round
              flat
              icon="fas fa-search"
              @click.stop="$emit('filter', { control_name: run.control_name })" />
            <router-link :to="controlLink(run)" :title="openRuns ? `${run.control_name}: open its Run log on this run` : run.control_name">
              <span class="col cursor-pointer" style="font-size: 13px" :class="'text-' + controlTypeTextColor(run.control_type)">
                {{ run.control_name }}
              </span>
            </router-link>
          </td>
          <td v-if="compact" class="text-left text-weight-bold text-blue-grey-7 no-wrap ellipsis" :title="periodTitle(run)">
            {{ periodText(run) }}
          </td>
          <template v-else>
            <td class="text-left text-weight-bold text-blue-grey-7">
              {{ toDateString(run.date_from) }}
            </td>
            <td class="text-left text-weight-bold text-blue-grey-7">
              {{ toDateString(run.date_to) }}
            </td>
          </template>
          <td class="text-right number-cell">
            <span v-if="run.fetched_number_a > 0" class="cursor-pointer number-link" v-keyboard:button @click="openNumberMenu($event, run, 'fetched_a')" @contextmenu.prevent="openNumberMenu($event, run, 'fetched_a')">
              {{ formatNumber(run.fetched_number_a) }}
            </span>
            <span v-else>{{ formatNumber(run.fetched_number_a) }}</span>
          </td>
          <td v-if="showB" class="text-right number-cell">
            <span v-if="run.fetched_number_b > 0" class="cursor-pointer number-link" v-keyboard:button @click="openNumberMenu($event, run, 'fetched_b')" @contextmenu.prevent="openNumberMenu($event, run, 'fetched_b')">
              {{ formatNumber(run.fetched_number_b) }}
            </span>
            <span v-else>{{ formatNumber(run.fetched_number_b) }}</span>
          </td>
          <td class="text-right number-cell">
            <span v-if="run.error_number_a > 0" class="cursor-pointer number-link text-primary" v-keyboard:button @click="openNumberMenu($event, run, 'result_a')" @contextmenu.prevent="openNumberMenu($event, run, 'result_a')">
              {{ formatNumber(run.error_number_a) }}
            </span>
            <span v-else>{{ formatNumber(run.error_number_a) }}</span>
          </td>
          <td v-if="showB" class="text-right number-cell">
            <span v-if="run.error_number_b > 0" class="cursor-pointer number-link text-primary" v-keyboard:button @click="openNumberMenu($event, run, 'result_b')" @contextmenu.prevent="openNumberMenu($event, run, 'result_b')">
              {{ formatNumber(run.error_number_b) }}
            </span>
            <span v-else>{{ formatNumber(run.error_number_b) }}</span>
          </td>
          <td class="text-right number-cell">
            <span v-if="run.error_level_a > 0" class="cursor-pointer number-link text-primary" v-keyboard:button @click="openNumberMenu($event, run, 'result_a')" @contextmenu.prevent="openNumberMenu($event, run, 'result_a')">
              {{ formatNumber(run.error_level_a, 2) }}%
            </span>
            <span v-else> {{ formatNumber(run.error_level_a, 2) }}% </span>
          </td>
          <td v-if="showB" class="text-right number-cell">
            <span v-if="run.error_level_b > 0" class="cursor-pointer number-link text-primary" v-keyboard:button @click="openNumberMenu($event, run, 'result_b')" @contextmenu.prevent="openNumberMenu($event, run, 'result_b')">
              {{ formatNumber(run.error_level_b, 2) }}%
            </span>
            <span v-else> {{ formatNumber(run.error_level_b, 2) }}% </span>
          </td>
          <td v-for="kpi in kpiColumns" :key="kpi.kpi_type" class="text-right number-cell">
            <span
              v-if="kpiCell(run, kpi)"
              class="run-kpi cursor-pointer"
              :class="{ 'run-kpi--alarm': kpiCell(run, kpi).alarm_level > 0 }"
              :style="kpiCell(run, kpi).alarm_level > 0 ? { background: alarmColor(kpiCell(run, kpi).alarm_level) } : null"
              :title="kpiCellTitle(run, kpi)"
              v-keyboard:button
              @click="$can('kpis', 'operate') && $emit('calculate-kpis', run)">
              {{ compactKpiValue(kpiCell(run, kpi).value) }}
            </span>
          </td>
          <td v-if="kpiSummary.length" class="text-left number-cell no-wrap">
            <template v-for="kpi in summaryOf(run).shown" :key="kpi.type">
              <span
                class="run-kpi run-kpi--summary cursor-pointer"
                :class="{ 'run-kpi--alarm': kpi.alarm_level > 0 }"
                :style="kpi.alarm_level > 0 ? { background: alarmColor(kpi.alarm_level) } : null"
                :title="summaryTitle(run, kpi)"
                v-keyboard:button
                @click="$can('kpis', 'operate') && $emit('calculate-kpis', run)">
                {{ compactKpiValue(kpi.value) }}
              </span>
            </template>
            <span v-if="summaryOf(run).more" class="run-kpi-more" :title="summaryAllTitle(run)">+{{ summaryOf(run).more }}</span>
          </td>
          <td class="text-left text-no-wrap run-chip-cell">
            <q-chip :clickable="filterable" :class="{ 'cursor-pointer': filterable }" :title="statusTitle(run)" @click="filterable && $emit('filter', { status: run.status })">
              <q-avatar :icon="prerequisiteStopped(run) ? 'fas fa-stop' : runStatus(run.status).icon" :color="runStatus(run.status).color" text-color="white">
                <q-badge
                  v-if="run.has_warning"
                  floating
                  rounded
                  color="amber-9"
                  class="run-warning cursor-pointer"
                  title="Finished with warnings: click for the run details"
                  aria-label="Finished with warnings: open the run details"
                  v-keyboard:button
                  @click.stop="$refs.runLogDialog.open(run)">
                  <q-icon name="fas fa-exclamation" size="7px" />
                </q-badge>
                <q-badge
                  v-if="hasPrerequisite(run)"
                  rounded
                  color="blue-7"
                  class="run-pv"
                  :title="`Prerequisite SQL value ${run.prerequisite_value}${prerequisiteStopped(run) ? ': the control stopped before its checks' : ''}`">
                  <q-icon name="fas fa-info" size="7px" />
                </q-badge>
              </q-avatar>
              {{ runStatus(run.status).label }}
            </q-chip>
          </td>
          <td class="text-left">
            <q-btn aria-label="Row actions" size="sm" color="grey-7" round flat icon="fas fa-ellipsis-v" @click="openRowMenu($event, run)" />
          </td>
        </tr>
      </template>
      <template #after>
        <tbody v-if="loading || error">
          <skeleton-rows v-if="!error" :columns="skeletonColumns" />
          <tr v-else>
            <td :colspan="colspan" class="text-center text-grey-7 q-pa-lg">Runs could not be loaded</td>
          </tr>
        </tbody>
        <tbody v-else-if="!shownRuns.length">
          <tr>
            <td :colspan="colspan" class="text-center text-grey-7 q-pa-lg">
              <slot name="empty">{{ emptyText }}</slot>
            </td>
          </tr>
        </tbody>
        <tbody v-if="loadingMore && !loading && !error">
          <tr>
            <td :colspan="colspan" class="text-center text-grey-7 q-pa-md">
              <q-spinner size="14px" class="q-mr-sm" />
              {{ loadingMoreText }}
            </td>
          </tr>
        </tbody>
      </template>
    </q-virtual-scroll>
    <run-dataset-menu ref="numberMenu" />
    <run-log-dialog ref="runLogDialog" />
    <q-menu ref="rowMenu" :target="menuTarget" no-parent-event>
      <q-list v-if="menuRow" dense class="text-no-wrap">
        <template v-if="$can('runs', 'operate')">
          <q-item dense clickable :disable="!!runDisabled" @click="reRun(menuRow, refresh)" v-close-popup>
            <q-item-section> Re-run </q-item-section>
            <q-tooltip v-if="runDisabled">{{ runDisabled }}</q-tooltip>
          </q-item>
          <run-control-dialog v-if="!runDisabled" :control_name="menuRow.control_name" :hook="refresh">
            <q-item dense clickable class="col items-center">
              <q-item-section> Run </q-item-section>
            </q-item>
          </run-control-dialog>
          <q-item v-else dense disable>
            <q-item-section> Run </q-item-section>
            <q-tooltip>{{ runDisabled }}</q-tooltip>
          </q-item>
        </template>
        <template v-if="editLink && $can('controls')">
          <q-separator />
          <q-item dense clickable :to="{ name: 'edit-control', params: { controlId: menuRow.control_id } }">
            <q-item-section> Edit control </q-item-section>
          </q-item>
        </template>
        <q-separator />
        <q-item v-if="menuRow.status != 'X' && $can('runs', 'operate')" dense clickable class="col items-center" @click="revokeRun(menuRow, refresh)" v-close-popup>
          <q-item-section> Revoke run </q-item-section>
        </q-item>
        <q-item v-if="activeRunStatuses.includes(menuRow.status) && $can('runs', 'operate')" dense clickable class="col items-center" @click="cancelRun(menuRow, refresh)" v-close-popup>
          <q-item-section> Cancel run </q-item-section>
        </q-item>
        <q-item dense clickable class="col items-center" @click="$refs.runLogDialog.open(menuRow)" v-close-popup>
          <q-item-section> Show full log </q-item-section>
        </q-item>
        <q-item v-if="hasKpis && hasKpis(menuRow) && $can('kpis', 'operate')" dense clickable class="col items-center" @click="$emit('calculate-kpis', menuRow)" v-close-popup>
          <q-item-section> Calculate KPIs </q-item-section>
        </q-item>
        <q-item v-if="menuRow.status == 'D' && menuRowSendsEmail && $can('runs', 'operate')" dense clickable class="col items-center" @click="sendEmail(menuRow)" v-close-popup>
          <q-item-section> Send email </q-item-section>
        </q-item>
      </q-list>
    </q-menu>
  </div>
</template>

<script>
import { mapGetters } from "vuex";
import RunControlDialog from "./RunControlDialog.vue";
import RunDatasetMenu from "./RunDatasetMenu.vue";
import RunLogDialog from "./RunLogDialog.vue";
import SkeletonRows from "./SkeletonRows.vue";
import { ACTIVE_RUN_STATUSES, controlType, controlTypeTextColor, runStatus } from "../constants";
import { cancelRun, copyAndNotify, reRun, revokeRun, sendEmail } from "../runActions";
import { EMAIL_CONTROL_TYPES, sendsEmail } from "../utils/email";
import { formatNumber, round, toDateString, toDateTimeString, toTimeString } from "../utils/format";
import { alarmLevel, compactKpiValue, formatKpiValue } from "../utils/kpi";
import { paletteColor } from "../utils/palette";
import { textWidth } from "../utils/layout";
import { KPI_ALARM_SORT, KPI_SORT_PREFIX, groupRuns, summaryKpis, runSortValue, supersededTitle, triggerKey, triggerOf, triggerTitle } from "../utils/runs";
import { ariaSort, sortIcon, sortRows, toggleSort } from "../utils/sort";

// A table of runs (get-control-runs rows), shared by the Results page and the editor's Run log: sortable columns,
// the trigger icon, the number menus (RunDatasetMenu), one row menu for the whole table and the full log dialog.
// A virtual scroll: the parent sizes it, and the table scrolls inside with its header kept in view. A run superseded by a
// later Done run of its period is folded under that run (when listed) and faded; optional KPI columns (Run log).

// The fixed widths of the columns (px), as the style sets them; the Control column takes the rest, else the Status
// column (`status`; beside a name it is `namedStatus`). Compact: one Period column and narrower numbers.
const WIDTHS = { type: 86, start: 162, runtime: 66, ver: 40, pid: 96, date: 87, fetched: 92, discr: 84, level: 80, kpi: 56, kpis: 210, status: 96, namedStatus: 104, menu: 50 };
// Compact widths are the content's (7-digit counts, "100.00%", a Done chip with its warning) plus the cell padding.
const COMPACT_WIDTHS = { ...WIDTHS, start: 156, ver: 38, pid: 90, period: 132, fetched: 84, discr: 70, level: 66, kpi: 54, kpis: 166, status: 96, menu: 40 };
// The values in the KPIs column: 4 in the full layout, 3 in the compact ones (their codes in the titles).
const SUMMARY_SHOWN = { full: 4, compact: 3 };
// The least width of the Control column before it is cut (ellipsis).
const NAME_MIN = 100;
// The bubble of a period's number of runs: darker the more (the last for any more).
const VERSION_COLORS = ["blue-grey-2", "indigo-2", "indigo-3", "indigo-5", "indigo-7", "indigo-9"];


function readFlag(key) {
  try {
    return localStorage.getItem(key) === "1";
  } catch (error) {
    return false;
  }
}

export default {
  components: { RunControlDialog, RunDatasetMenu, RunLogDialog, SkeletonRows },
  props: {
    runs: { type: Array, required: true },
    // { key, dir }, changed in place by the headers.
    sort: { type: Object, required: true },
    // The columns that may show: the type, the control's name (true: always, "optional": dropped last when the table
    // is narrow) and side B's numbers (b, shown unless false). The width decides the rest (`levels`).
    columns: { type: Object, default: () => ({ type: true, name: true }) },
    // KPI columns (get-control-runs' kpi_types of one control): the values stored for each run.
    kpiColumns: { type: Array, default: () => [] },
    // One KPIs column instead (Results: controls with other KPIs): get-control-runs' kpi_types of the runs.
    kpiSummary: { type: Array, default: () => [] },
    // Whether a superseded run's mark (⟲, its version number) emits open-run with the run (Results).
    openRuns: { type: Boolean, default: false },
    // A run to show: its period unpacked, scrolled to and selected (the Run log opened on a run by a link).
    focusRun: { type: Number, default: null },
    // A click on a row selects it (tinted yellow), one at a time; a click on the selected row's plain area or Esc
    // clears it (the Run log).
    selectable: { type: Boolean, default: false },
    // Where this browser keeps whether every period's earlier runs are shown.
    expandKey: { type: String, default: "rapo_runs_expand" },
    // The row menu's Edit control (not inside the editor itself).
    editLink: { type: Boolean, default: true },
    // Type and status chips and the name's magnifier emit filter ({ type } / { status } / { control_name }).
    filterable: { type: Boolean, default: false },
    // Why Re-run and Run are not offered now (e.g. unsaved changes), or null.
    runDisabled: { type: String, default: null },
    // Called after a run action changed a run.
    refresh: { type: Function, default: () => {} },
    loading: { type: Boolean, default: false },
    error: { type: Boolean, default: false },
    emptyText: { type: String, default: "No runs" },
    // The control name filtered by, whose magnifiers are highlighted (a click clears it), or null.
    filteredName: { type: String, default: null },
    // Whether a run's control has KPIs; the row menu's Calculate KPIs emits calculate-kpis (run).
    hasKpis: { type: Function, default: null },
    // More runs can be loaded (the Run log's older periods): load-more is emitted near the end of the rows, and while
    // the rows do not fill the table. `loadingMore` shows `loadingMoreText` in a last row meanwhile.
    more: { type: Boolean, default: false },
    loadingMore: { type: Boolean, default: false },
    loadingMoreText: { type: String, default: "Loading more…" },
  },
  emits: ["filter", "calculate-kpis", "open-run", "load-more"],
  data() {
    return {
      KPI_ALARM_SORT,
      expandAll: readFlag(this.expandKey),
      // The width the table has (px), 0 until measured.
      width: 0,
      // The focus run already shown (showFocusRun).
      focused: null,
      // The selected run's process ID (selectable, or the focus run), or null.
      selected: null,
      // The runs whose earlier runs are shown (or folded, while expandAll): process ID -> true.
      toggled: {},
      activeRunStatuses: ACTIVE_RUN_STATUSES,
      // The one row menu of the table, opened at the kebab button of the row it acts on.
      menuTarget: false,
      menuProcessId: null,
    };
  },
  computed: {
    ...mapGetters(["controlCatalogueById"]),
    sortedRuns() {
      return sortRows(this.runs, (run) => runSortValue(run, this.sort.key), this.sort.dir);
    },
    grouping() {
      return groupRuns(this.sortedRuns, this.isExpanded);
    },
    shownRuns() {
      return this.grouping.rows;
    },
    showB() {
      return this.columns.b !== false;
    },
    // The layouts from the widest down, each dropping what the next needs: separate Run from/to and the type, one
    // Period column and narrower numbers, no type, no name (only an optional name).
    levels() {
      const type = Boolean(this.columns.type);
      const name = Boolean(this.columns.name);
      const levels = [
        { compact: false, type, name },
        { compact: true, type, name },
        { compact: true, type: false, name },
      ];
      if (this.columns.name === "optional") levels.push({ compact: true, type: false, name: false });
      return levels;
    },
    // The first layout that fits the width with the name whole, else the last one (a cut name, or scrolling).
    show() {
      const fits = this.levels.find((level) => this.minWidth(level) + (level.name ? this.nameColumnWidth : 0) <= this.width);
      return !this.width ? this.levels[0] : fits || this.levels[this.levels.length - 1];
    },
    compact() {
      return this.show.compact;
    },
    // The name column's least width: whole when it fits, else what is left, at least NAME_MIN.
    nameWidth() {
      if (!this.show.name) return 0;
      const left = this.width ? this.width - this.minWidth(this.show) : this.nameColumnWidth;
      return Math.max(NAME_MIN, Math.min(this.nameColumnWidth, left));
    },
    colspan() {
      return 10 + (this.compact ? 0 : 1) + ["type", "name"].filter((column) => this.show[column]).length + (this.showB ? 3 : 0) + this.kpiColumns.length + (this.kpiSummary.length ? 1 : 0);
    },
    tableMinWidth() {
      return this.minWidth(this.show);
    },
    skeletonColumns() {
      return [
        ...(this.show.type ? ["QChip"] : []),
        "text",
        "text",
        "QChip",
        "text",
        ...(this.show.name ? ["text"] : []),
        ...Array((this.showB ? 8 : 5) - (this.compact ? 1 : 0)).fill("text"),
        ...this.kpiColumns.map(() => "text"),
        ...(this.kpiSummary.length ? ["text"] : []),
        "QChip",
        null,
      ];
    },
    // The Control column fits the longest name (bold 13px, plus the search button and padding).
    nameColumnWidth() {
      return this.columns.name ? Math.min(textWidth(this.runs.map((row) => row.control_name), "bold 13px Roboto, sans-serif") + 40, 400) : 0;
    },
    // Looked up by PID, so an open menu follows live updates of its run.
    menuRow() {
      return this.runs.find((row) => row.process_id === this.menuProcessId) || null;
    },
    // The email configuration is in the catalogue. Until it is loaded, every type that can send one is offered.
    menuRowSendsEmail() {
      const control = this.menuRow && this.controlCatalogueById(this.menuRow.control_id);
      return control ? sendsEmail(control) : Boolean(this.menuRow) && EMAIL_CONTROL_TYPES.includes(this.menuRow.control_type);
    },
  },
  mounted() {
    if (this.selectable) document.addEventListener("keydown", this.onKeydown);
    this.scrollElement = this.$el.querySelector(".runs-table");
    if (this.scrollElement) this.scrollElement.addEventListener("scroll", this.fillRows, { passive: true });
  },
  beforeUnmount() {
    document.removeEventListener("keydown", this.onKeydown);
    if (this.scrollElement) this.scrollElement.removeEventListener("scroll", this.fillRows);
  },
  watch: {
    shownRuns() {
      this.$nextTick(() => {
        this.onResize();
        this.fillRows();
      });
      this.showFocusRun();
    },
    more() {
      this.$nextTick(this.fillRows);
    },
    loadingMore() {
      this.$nextTick(this.fillRows);
    },
    focusRun() {
      this.focused = null;
      this.showFocusRun();
    },
    expandKey(key) {
      this.expandAll = readFlag(key);
      this.toggled = {};
    },
  },
  methods: {
    supersededTitle,
    // The width the rows have: the table's box less its vertical scrollbar (measured again when the rows change).
    // Unpacks the focus run's period once it is among the runs, then scrolls to it (once per focus run).
    showFocusRun() {
      const run = this.focusRun && this.focused !== this.focusRun && this.runs.find((row) => row.process_id === this.focusRun);
      if (!run) return;
      this.focused = this.focusRun;
      this.selected = this.focusRun;
      const parent = run.superseded_by && this.runs.some((row) => row.process_id === run.superseded_by) ? run.superseded_by : null;
      if (parent && !this.isExpanded(parent)) this.toggleExpanded(parent);
      this.$nextTick(() => {
        const index = this.shownRuns.findIndex((row) => row.process_id === this.focusRun);
        if (index >= 0 && this.$refs.scroll) this.$refs.scroll.scrollTo(Math.max(index - 2, 0), "start-force");
      });
    },
    // A click in a row selects it; on the selected row, one outside its buttons, chips and links clears it. Selecting text
    // is no click.
    selectRow(run, event) {
      const selection = window.getSelection();
      if (selection && selection.toString()) return;
      const found = event.target.closest('button, a, input, .q-chip, .q-icon, .cursor-pointer, .run-ver--link, [role="button"], [tabindex]');
      const control = found && found !== event.currentTarget && event.currentTarget.contains(found);
      this.selected = this.selected === run.process_id && !control ? null : run.process_id;
    },
    copyProcessId(run) {
      copyAndNotify(String(run.process_id), `Process ID ${run.process_id}`, "Failed to copy the process ID.");
    },
    onKeydown(event) {
      if (event.key !== "Escape" || this.selected === null || event.defaultPrevented) return;
      if (document.querySelector(".q-dialog, .q-menu") || ["INPUT", "TEXTAREA"].includes(document.activeElement && document.activeElement.tagName)) return;
      this.selected = null;
    },
    // The editor of a run's control: on Results (openRuns), its Run log on the run.
    controlLink(run) {
      const link = { name: "edit-control", params: { controlId: run.control_id } };
      return this.openRuns ? { ...link, query: { tab: "log", run: String(run.process_id) } } : link;
    },
    onResize() {
      const scroll = this.$el.querySelector(".runs-table");
      this.width = scroll ? scroll.clientWidth : 0;
      this.fillRows();
    },
    // Asks for more runs (more) while the end of the rows is within ten rows of the view, also when they do not fill the
    // table; checked on scrolling and whenever the rows or the table's size change.
    fillRows() {
      if (!this.more || this.loadingMore || this.loading || this.error) return;
      const scroll = this.scrollElement;
      if (scroll && scroll.clientHeight && scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight <= 450) this.$emit("load-more");
    },
    // The least width of the table in a layout without the Control column: every fixed column and Status.
    minWidth(level) {
      const w = level.compact ? COMPACT_WIDTHS : WIDTHS;
      const sides = this.showB ? 2 : 1;
      return (
        (level.type ? w.type : 0) +
        w.start +
        w.runtime +
        w.ver +
        w.pid +
        (level.compact ? w.period : 2 * w.date) +
        sides * (w.fetched + w.discr + w.level) +
        this.kpiColumns.length * w.kpi +
        (this.kpiSummary.length ? w.kpis : 0) +
        (level.name ? w.namedStatus : w.status) +
        w.menu
      );
    },
    hasPrerequisite(run) {
      return run.prerequisite_value !== null && run.prerequisite_value !== undefined;
    },
    // A run whose Prerequisite SQL returned 0: it stopped before its checks.
    prerequisiteStopped(run) {
      return this.hasPrerequisite(run) && Number(run.prerequisite_value) === 0;
    },
    // The status chip's title, with the Prerequisite SQL's value (once the PV column).
    statusTitle(run) {
      const label = runStatus(run.status).label;
      if (this.prerequisiteStopped(run)) return `${label}: the Prerequisite SQL returned 0, so the control stopped before its checks`;
      if (this.hasPrerequisite(run)) return `${label} · Prerequisite SQL value ${run.prerequisite_value}`;
      return label;
    },
    // A bubble of `count` runs: the darker the more.
    versionStyle(count) {
      const index = Math.min(count, VERSION_COLORS.length) - 1;
      return { background: paletteColor(VERSION_COLORS[index]), color: index >= 3 ? "var(--rapo-on-strong)" : "var(--rapo-header-text)" };
    },
    // An expanded period stands apart: a line above its latest run and below its last earlier run; other rows keep the
    // table's thin lines.
    groupEdge(index) {
      if (index === 0) return false;
      const run = this.shownRuns[index];
      const previous = this.shownRuns[index - 1];
      const startsGroup = this.grouping.earlier.has(run.process_id) && this.isExpanded(run.process_id);
      const endsGroup = this.grouping.folded.has(previous.process_id) && !this.grouping.folded.has(run.process_id);
      return startsGroup || endsGroup;
    },
    isExpanded(processId) {
      return Boolean(this.expandAll) !== Boolean(this.toggled[processId]);
    },
    toggleExpanded(processId) {
      this.toggled = { ...this.toggled, [processId]: !this.toggled[processId] };
    },
    toggleExpandAll() {
      this.expandAll = !this.expandAll;
      this.toggled = {};
      try {
        localStorage.setItem(this.expandKey, this.expandAll ? "1" : "0");
      } catch (error) {
        // Not remembered, which is all a failure costs.
      }
    },
    kpiSortKey(kpi) {
      return `${KPI_SORT_PREFIX}${kpi.kpi_type}`;
    },
    kpiHeaderTitle(kpi) {
      const unit = kpi.kpi_value_unit ? ` (${kpi.kpi_value_unit})` : "";
      return `KPI ${kpi.kpi_type}${kpi.kpi_type_desc ? `: ${kpi.kpi_type_desc}` : ""}${unit}, as stored for the run, on its alarm level's color; click a value to calculate the KPIs of the run`;
    },
    kpiCell(run, kpi) {
      return (run.kpis && run.kpis[kpi.kpi_type]) || null;
    },
    compactKpiValue,
    // The KPIs a run shows in the KPIs column and how many more it has.
    summaryOf(run) {
      const all = summaryKpis(run, this.kpiSummary);
      const count = SUMMARY_SHOWN[this.compact ? "compact" : "full"];
      return { shown: all.slice(0, count), more: Math.max(all.length - count, 0) };
    },
    summaryType(code) {
      return this.kpiSummary.find((type) => type.kpi_type === code) || { kpi_type: code };
    },
    summaryTitle(run, kpi) {
      return this.kpiCellTitle(run, this.summaryType(kpi.type));
    },
    // Every KPI of the run, exact.
    summaryAllTitle(run) {
      return summaryKpis(run, this.kpiSummary)
        .map((kpi) => {
          const type = this.summaryType(kpi.type);
          const unit = type.kpi_value_unit ? ` ${type.kpi_value_unit}` : "";
          return `${kpi.type} = ${formatKpiValue(kpi.value, type.kpi_decimal_places)}${unit} · ${alarmLevel(kpi.alarm_level).label}`;
        })
        .join("\n");
    },
    // "2026-10-12" for a window of one day, "2026-10-01 → 31" within a month, "2026-09-28 → 10-04" within a year.
    periodText(run) {
      const from = toDateString(run.date_from);
      const to = toDateString(run.date_to);
      if (!from || !to || from === to) return from || to;
      if (from.slice(0, 7) === to.slice(0, 7)) return `${from}\u2009→\u2009${to.slice(8)}`;
      if (from.slice(0, 4) === to.slice(0, 4)) return `${from}\u2009→\u2009${to.slice(5)}`;
      return `${from}\u2009→\u2009${to}`;
    },
    periodTitle(run) {
      return run.date_from ? `${toDateTimeString(run.date_from)} – ${toDateTimeString(run.date_to)}` : "";
    },
    kpiCellTitle(run, kpi) {
      const cell = this.kpiCell(run, kpi);
      const unit = kpi.kpi_value_unit ? ` ${kpi.kpi_value_unit}` : "";
      return `${kpi.kpi_type} = ${formatKpiValue(cell.value, kpi.kpi_decimal_places)}${unit} · ${alarmLevel(cell.alarm_level).label}; click to calculate the KPIs of run ${run.process_id}`;
    },
    alarmColor(level) {
      return paletteColor(alarmLevel(level).color);
    },
    isFilteredName(run) {
      return Boolean(this.filteredName) && (run.control_name || "").toUpperCase() === this.filteredName.toUpperCase();
    },
    ariaSort,
    cancelRun,
    controlType,
    controlTypeTextColor,
    formatNumber,
    reRun,
    revokeRun,
    round,
    runStatus,
    sendEmail,
    sortIcon,
    toDateString,
    toTimeString,
    toggleSort,
    triggerKey,
    triggerOf,
    triggerTitle,
    // The menu leads to the records behind the number, which need Data.
    openNumberMenu(event, row, dataset) {
      if (this.$can("data")) {
        this.$refs.numberMenu.open(event, row, dataset);
      }
    },
    openRowMenu(event, row) {
      this.menuTarget = event.currentTarget;
      this.menuProcessId = row.process_id;
      this.$nextTick(() => this.$refs.rowMenu.show());
    },
  },
};
</script>

<style lang="css" scoped>
/* Its width is what the page gives it, never its rows' (the layout level is picked from it): it scrolls inside. */
.run-table {
  flex: 0 1 auto;
  min-height: 0;
  contain: inline-size;
}

/* Override the default link styles */
a {
  color: var(--rapo-teal);
  text-decoration: none;
}
a:hover {
  text-decoration: underline;
}
a:visited {
  color: var(--rapo-teal);
}
/* A run superseded by a later Done run of its period: faded, whole again on hover; folded under that run, indented. */
.run-row--superseded > td {
  opacity: 0.5;
}
.run-row--superseded:hover > td {
  opacity: 1;
}
.run-row--group-edge > td {
  border-top: 2px solid var(--rapo-header);
}
.run-row--folded > td:first-child {
  box-shadow: inset 3px 0 0 var(--rapo-grid);
}
/* The number of runs of a period as a bubble; an earlier run's version outlined. */
.run-ver {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 5px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
}
/* The Ver header shows or folds every period's earlier runs. */
/* The type and status chips sit tight in their cells (13px, no outer margin), so the name keeps the width. */
.run-chip-cell :deep(.q-chip) {
  margin: 0;
  font-size: 13px;
}
/* Badges on the status chip's avatar: warnings (amber, top right), the Prerequisite SQL's value (blue, bottom right). */
.run-warning,
.run-pv {
  min-width: 14px;
  min-height: 14px;
  padding: 0;
  justify-content: center;
}
.run-warning {
  top: -5px;
  right: -5px;
}
.run-pv {
  position: absolute;
  bottom: -5px;
  right: -5px;
}
.run-ver-all {
  cursor: pointer;
  border-bottom: 1px dashed currentColor;
}
.run-ver-all--on {
  color: var(--rapo-teal);
}
.run-ver--link {
  cursor: pointer;
}
.run-ver--link:hover {
  box-shadow: 0 0 0 2px var(--rapo-teal);
}
.run-ver--old {
  border: 1.5px solid var(--rapo-label);
  color: var(--rapo-label);
}
/* The selected run (a click in the Run log, or the run a link opened it on), whole even when superseded. */
.run-row--selectable {
  cursor: pointer;
}
.run-row--focus > td {
  background: var(--rapo-focus);
}
.run-row--superseded.run-row--focus > td {
  opacity: 1;
}
/* A stored KPI value in a box: dark on soft green, white on its alarm level's color when it alarmed. */
/* One width for every value (4 compact characters), digits on the right, so the KPIs of each row line up. */
.run-kpi {
  display: inline-block;
  box-sizing: border-box;
  width: 40px;
  padding: 0 4px;
  text-align: right;
  background: var(--rapo-kpi-ok);
  color: var(--rapo-header-text);
  font-weight: 500;
  border-radius: 3px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: middle;
}
.run-kpi--summary {
  margin-right: 4px;
}
.run-kpi-more {
  font-size: 11px;
  color: var(--rapo-label);
  cursor: default;
}
.run-kpi:hover {
  text-decoration: underline;
}
.run-kpi--alarm {
  color: var(--rapo-on-strong);
}

/* Fixed columns, so rows swapped in while scrolling don't resize them. With Control (Results) it takes the
   rest, but at least the width of the longest name (nameColumnWidth), else the table scrolls sideways; the Start
   column's trigger icon (18px) is taken from it, as min-width leaves it out. Without it the Status column takes the
   rest. */
.runs-table :deep(table) {
  table-layout: fixed;
  min-width: var(--table-min-width);
}
.runs-table.with-name :deep(table) {
  min-width: calc(var(--table-min-width) + var(--name-column-width));
}
.runs-table .col-type { width: 86px; }
.runs-table .col-start { width: 162px; }
.runs-table .col-runtime { width: 66px; }
.runs-table .col-ver { width: 40px; }
.runs-table .col-pid { width: 96px; }
.runs-table .col-kpi { width: 56px; }
.runs-table .col-kpis { width: 210px; }
.runs-table.runs-table--compact .col-kpis { width: 166px; }
.runs-table .col-period { width: 132px; }
.runs-table.runs-table--compact .col-start { width: 156px; }
.runs-table.runs-table--compact .col-ver { width: 38px; }
.runs-table.runs-table--compact .col-pid { width: 90px; }
.runs-table.runs-table--compact .col-fetched { width: 84px; }
.runs-table.runs-table--compact .col-discr { width: 70px; }
.runs-table.runs-table--compact .col-level { width: 66px; }
.runs-table.runs-table--compact .col-kpi { width: 54px; }
.runs-table.runs-table--compact .col-menu { width: 40px; }
.runs-table .col-date { width: 87px; }
.runs-table .col-fetched { width: 92px; }
.runs-table .col-discr { width: 84px; }
.runs-table .col-level { width: 80px; }
.runs-table.with-name .col-status { width: 104px; }
.runs-table .col-menu { width: 50px; }
</style>
