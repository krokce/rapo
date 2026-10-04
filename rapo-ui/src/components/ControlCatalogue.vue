<template>
  <q-page class="column no-wrap" :style-fn="fillViewportToBottom">
    <div class="row items-end" :class="activeFilters.length || sortChip ? 'q-mb-sm' : 'q-mb-lg'">
      <h2 class="row items-center no-wrap text-no-wrap q-gutter-lg q-mb-none">
        <div v-if="showSkeleton">Controls</div>
        <div v-else>{{ countTitle }}</div>
        <div v-if="refreshing && !showSkeleton">
          <q-avatar size="lg" color="grey-5">
            <q-icon name="fas fa-sync fa-spin" />
          </q-avatar>
        </div>
      </h2>
      <q-space />
      <div class="row items-center justify-end q-gutter-x-md">
        <div v-if="schemaDriftError">
          <q-chip color="amber-8" text-color="grey-10" icon="fas fa-exclamation-triangle">
            Schema check failed
            <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 5]" max-width="500px">
              Schema drift and orphaned tables cannot be shown: {{ schemaDriftError }}. The server log has the details.
            </q-tooltip>
          </q-chip>
        </div>
        <div v-if="orphanTables.length">
          <q-chip clickable color="red-4" text-color="white" icon="fas fa-trash-alt" @click="$refs.orphanDialog.open()">
            {{ orphanTables.length }} orphaned result table{{ orphanTables.length > 1 ? "s" : "" }}
            <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 5]">
              Result tables no run writes any more: review and drop them
            </q-tooltip>
          </q-chip>
        </div>
        <div v-if="orphanKpis.length">
          <q-chip clickable color="red-4" text-color="white" icon="fas fa-trash-alt" @click="$refs.orphanKpisDialog.open()">
            {{ orphanKpis.length }} orphaned KPI{{ orphanKpis.length > 1 ? "s" : "" }}
            <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 5]">
              KPIs configured for a name no control has, so never calculated: review, assign or delete them
            </q-tooltip>
          </q-chip>
        </div>
        <div v-if="tempTables.total_tables">
          <q-chip clickable color="blue-grey" text-color="white" icon="fas fa-trash-alt" @click="$refs.tempDialog.open()">
            {{ tempTables.total_tables }} temporary table{{ tempTables.total_tables > 1 ? "s" : "" }} · {{ formatNumber(tempTables.total_mb, 1) }} MB
            <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 5]">Left by failed, canceled or debug runs: review and drop them</q-tooltip>
          </q-chip>
        </div>
        <!-- The controls flagged in the list, whatever the filters, like the day totals of Results; a chip filters by it. -->
        <div v-if="headerCounts.sourceMissing || headerCounts.drift || headerCounts.noKpi">
          <q-chip v-if="headerCounts.sourceMissing" clickable @click="addAttributeFilter('Datasource missing')">
            <q-avatar icon="fas fa-unlink" color="negative" text-color="white" />
            <span class="text-weight-bold q-mr-xs">Datasource missing</span>({{ headerCounts.sourceMissing }})
            <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">Controls whose datasource does not exist: their runs fail</q-tooltip>
          </q-chip>
          <q-chip v-if="headerCounts.drift" clickable @click="addAttributeFilter('Schema drift')">
            <q-avatar icon="fas fa-table" :color="headerCounts.driftColor" text-color="white" />
            <span class="text-weight-bold q-mr-xs">Schema drift</span>({{ headerCounts.drift }})
            <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">
              Controls whose result tables need Update or Recreate schema, or have orphaned tables
            </q-tooltip>
          </q-chip>
          <q-chip v-if="headerCounts.noKpi" clickable @click="addAttributeFilter('No KPI')">
            <q-avatar :icon="kpiIcon" color="red-4" text-color="white" />
            <span class="text-weight-bold q-mr-xs">No KPI</span>({{ headerCounts.noKpi }})
            <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">Controls without a KPI configuration</q-tooltip>
          </q-chip>
        </div>
      </div>
    </div>
    <filter-chips v-if="!showSkeleton" :filters="activeFilters" :sort="sortChip" class="q-mb-md" @clear="clearFilters" />

    <div class="row items-center q-mb-md">
      <q-btn
        class="col-2 q-mb-md q-pa-sm"
        size="lg"
        color="primary"
        icon="fas fa-plus-circle"
        label="New control"
        :to="{ name: 'edit-control', params: { controlId: 'new' } }" />

      <q-select
        v-model="filter.type"
        class="col-2 q-mb-md q-pa-sm"
        clearable
        outlined
        options-dense
        emit-value
        map-options
        :options="controlTypeOptions"
        label="Control type">
      </q-select>

      <q-input clearable class="col q-mb-md q-pa-sm" outlined v-model="filter.control_name" label="Control name" maxlength="45" style="min-width: 150px" />

      <q-select
        v-model="filter.group"
        class="col q-mb-md q-pa-sm"
        style="min-width: 180px"
        clearable
        outlined
        options-dense
        emit-value
        map-options
        :options="groupFilterOptions"
        label="Control group">
      </q-select>

      <q-select
        :model-value="filter.system"
        class="col q-mb-md q-pa-sm"
        style="min-width: 150px"
        clearable
        outlined
        options-dense
        use-input
        hide-selected
        fill-input
        input-debounce="0"
        maxlength="90"
        :options="systemOptions"
        label="System"
        @filter="filterSystems"
        @input-value="(value) => (filter.system = value || null)"
        @update:model-value="(value) => (filter.system = value || null)">
      </q-select>

      <q-select
        v-model="filter.status"
        class="col q-mb-md q-pa-sm"
        style="min-width: 170px"
        clearable
        outlined
        options-dense
        emit-value
        map-options
        :options="[
          { label: 'Active', value: 'Y' },
          { label: 'Inactive', value: 'N' },
        ]"
        label="Scheduler status">
      </q-select>

      <q-select
        v-model="filter.other_attributes"
        class="col q-mb-md q-pa-sm"
        style="min-width: 220px"
        outlined
        options-dense
        emit-value
        map-options
        multiple
        use-chips
        :options="attributeOptions"
        label="Control attributes">
        <!-- The attributes in groups: a group's name is a caption, not an option. -->
        <template #option="scope">
          <q-item-label v-if="scope.opt.header" header class="q-pt-sm q-pb-xs text-weight-bold">{{ scope.opt.label }}</q-item-label>
          <q-item v-else v-bind="scope.itemProps">
            <q-item-section class="q-pl-sm">{{ scope.opt.label }}</q-item-section>
          </q-item>
        </template>
      </q-select>

    </div>

    <q-virtual-scroll
      type="table"
      class="list-table catalogue-table"
      :style="{ '--name-column-width': nameColumnWidth + 'px', '--scheduler-column-width': schedulerColumnWidth + 'px' }"
      :items="sortedControlCatalogue"
      :virtual-scroll-item-size="90"
      :virtual-scroll-sticky-size-start="28"
      :table-colspan="5">
      <template #before>
        <thead>
          <tr class="bg-blue-grey-2">
            <th title="The control type: ANL analysis, REC reconciliation, CMP comparison, REP report; click a type to filter by it" class="text-center sortable" @click="toggleSort(sort, 'control_type')" v-keyboard :aria-sort="ariaSort(sort, 'control_type')">
              Type
              <q-icon v-if="sort.key === 'control_type'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th title="The control's name, with the date of its last change; click it to edit the control" class="text-left sortable" @click="toggleSort(sort, 'control_name')" v-keyboard :aria-sort="ariaSort(sort, 'control_name')">
              Name
              <q-icon v-if="sort.key === 'control_name'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th title="The description and the control's attributes: group, engine, hooks, SQL scripts, systems A and B, issues; click a chip to filter by it" class="text-left sortable" @click="toggleSort(sort, 'control_description')" v-keyboard :aria-sort="ariaSort(sort, 'control_description')">
              Description
              <q-icon v-if="sort.key === 'control_description'" :name="sortIcon(sort)" size="12px" />
            </th>

            <th title="When the control runs next, scheduled, after the control it cascades from or pulled by a control reading its results, and in how long; then the schedule in words, where its runs fall (hours, week days or month days) and the data window of a run. Hover a row for its next runs and their data windows; sorted by the next run" class="text-left sortable" @click="toggleSort(sort, 'next_fire')" v-keyboard :aria-sort="ariaSort(sort, 'next_fire')">
              Scheduler
              <q-icon v-if="sort.key === 'next_fire'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-left"></th>
          </tr>
        </thead>
      </template>
      <template #default="{ item: control }">
        <tr :key="control.control_id">
          <td>
            <q-chip clickable :title="controlType(control.control_type).label" @click="filter.type = control.control_type">
              <q-avatar :icon="controlType(control.control_type).icon" :color="controlType(control.control_type).color" text-color="white" />
              {{ control.control_type }}
            </q-chip>
          </td>
          <td class="text-left">
            <router-link :to="{ name: 'edit-control', params: { controlId: control.control_id } }" class="text-weight-bold text-grey-9 control-name">
              {{ control.control_name }}
            </router-link>
            <router-link
              :to="{
                name: 'edit-control',
                params: { controlId: control.control_id },
              }"
              style="text-decoration: none">
              <div>
                <small class="text-indigo-4"> v.{{ toDateTimeString(control.updated_date) }} </small>
              </div>
            </router-link>
          </td>

          <td class="text-left">
            <div style="white-space: normal; word-wrap: break-word">
              {{ control.control_description }}
            </div>

            <div class="row justify-start items-center">
              <q-chip
                v-if="control.control_group"
                clickable
                size="sm"
                color="blue-grey-5"
                text-color="white"
                icon="fas fa-folder"
                @click="filter.group = control.control_group.trim()">
                {{ control.control_group }}
              </q-chip>

              <q-chip v-if="control.status !== 'Y'" clickable size="sm" color="red-4" text-color="white" icon="fas fa-clock" @click="filter.status = 'N'">
                Scheduler inactive
              </q-chip>

              <q-chip
                clickable
                v-if="control.need_postrun_hook != 'Y'"
                size="sm"
                color="red-4"
                text-color="white"
                icon="fas fa-bolt"
                @click="addAttributeFilter('No Post-run hook')">
                No Post-run hook
              </q-chip>

              <q-chip
                clickable
                v-if="engineOf(control)"
                size="sm"
                color="indigo-4"
                text-color="white"
                icon="fas fa-cogs"
                :title="engineTitle(control)"
                @click="addAttributeFilter(`${engineOf(control)} engine`)">
                {{ engineOf(control) }} engine
              </q-chip>

              <q-chip clickable v-if="lacksKpi(control)" size="sm" color="red-4" text-color="white" :icon="kpiIcon" @click="addAttributeFilter('No KPI')">
                No KPI
              </q-chip>

              <q-chip
                clickable
                v-if="driftOf(control)"
                size="sm"
                :color="driftColor(driftOf(control))"
                text-color="white"
                icon="fas fa-table"
                :title="driftTitle(driftOf(control))"
                @click="addAttributeFilter('Schema drift')">
                Schema drift
              </q-chip>

              <q-chip
                clickable
                v-if="sourceMissingOf(control)"
                size="sm"
                color="negative"
                text-color="white"
                icon="fas fa-unlink"
                :title="`${sourceMissingOf(control).reason}. Runs of this control fail. Open the control to fix it.`"
                @click="addAttributeFilter('Datasource missing')">
                Datasource missing
              </q-chip>

              <q-chip
                clickable
                v-if="control.prerequisite_sql"
                size="sm"
                color="indigo-4"
                text-color="white"
                icon="fas fa-database"
                @click="addAttributeFilter('Prerequisite SQL')">
                Prerequisite SQL
              </q-chip>

              <q-chip
                clickable
                v-if="control.preparation_sql"
                size="sm"
                color="indigo-4"
                text-color="white"
                icon="fas fa-database"
                @click="addAttributeFilter('Preparation SQL')">
                Preparation SQL
              </q-chip>

              <q-chip
                clickable
                v-if="control.completion_sql"
                size="sm"
                color="indigo-4"
                text-color="white"
                icon="fas fa-database"
                @click="addAttributeFilter('Completion SQL')">
                Completion SQL
              </q-chip>

              <q-chip
                clickable
                v-if="sendsEmail(control)"
                size="sm"
                color="indigo-4"
                text-color="white"
                icon="fas fa-envelope"
                @click="addAttributeFilter('Email')">
                Email
              </q-chip>

              <q-chip
                clickable
                v-if="control.need_prerun_hook === 'Y'"
                size="sm"
                color="indigo-4"
                text-color="white"
                icon="fas fa-bolt"
                @click="addAttributeFilter('Pre-run hook')">
                Pre-run hook
              </q-chip>

              <q-chip
                clickable
                v-if="control.case_config"
                size="sm"
                color="indigo-4"
                text-color="white"
                icon="fas fa-tag"
                @click="addAttributeFilter('Case definition')">
                Case definition
              </q-chip>

              <q-chip
                clickable
                v-if="iterationCount(control) > 0"
                size="sm"
                color="indigo-4"
                text-color="white"
                icon="fas fa-history"
                @click="addAttributeFilter('Iterations')">
                +{{ iterationCount(control) }} Iteration{{ iterationCount(control) > 1 ? "s" : "" }}
              </q-chip>

              <q-chip
                clickable
                v-if="chains.has(control.control_name)"
                size="sm"
                color="indigo-4"
                text-color="white"
                icon="fas fa-link"
                :title="chainTitle(control)"
                @click="addAttributeFilter('Chain')">
                Chain
              </q-chip>

              <q-chip
                v-if="control.source_type_a"
                clickable
                color="green-8"
                text-color="white"
                size="sm"
                icon-right="fas fa-plug fa-rotate-270"
                @click="filter.system = control.source_type_a.trim()"
                style="align-items: center">
                {{ control.source_type_a }}
              </q-chip>
              <q-icon v-if="control.source_type_a && control.source_type_b" name="fas fa-wave-square" size="9px" color="green-8" />
              <q-chip
                v-if="control.source_type_b"
                clickable
                color="green-8"
                text-color="white"
                size="sm"
                icon="fas fa-plug fa-rotate-90"
                @click="filter.system = control.source_type_b.trim()"
                style="align-items: center">
                {{ control.source_type_b }}
              </q-chip>
              
            </div>
          </td>
          <td>
            <div class="row justify-start items-center">
              <schedule-summary
                class="col"
                :control="control"
                :next="nextFires.controls[control.control_id]"
                :now="serverNow"
                :scheduler-active="nextFires.scheduler_active"
                :trigger-name="triggerNameOf(control)" />
            </div>
          </td>

          <td>
            <q-btn aria-label="Row actions" size="sm" color="grey-7" round flat icon="fas fa-ellipsis-v" @click="openRowMenu($event, control)" />
          </td>
        </tr>
      </template>
      <template #after>
        <tbody v-if="showSkeleton">
          <skeleton-rows v-if="!loadError" :columns="['QChip', 'text', 'text', 'QChip', null]" />
          <tr v-else>
            <td colspan="5" class="text-center text-grey-7 q-pa-lg">Controls could not be loaded</td>
          </tr>
        </tbody>
        <tbody v-else-if="!sortedControlCatalogue.length">
          <tr>
            <td colspan="5" class="text-center text-grey-7 q-pa-lg">No controls match the filters</td>
          </tr>
        </tbody>
      </template>
    </q-virtual-scroll>
    <q-menu ref="rowMenu" :target="menuTarget" no-parent-event>
      <q-list v-if="menuRow" dense class="text-no-wrap">
        <run-control-dialog :control_name="menuRow.control_name">
          <q-item dense clickable class="col items-center">
            <q-item-section> Run </q-item-section>
          </q-item>
        </run-control-dialog>
        <q-separator />
        <q-item
          clickable
          :to="{
            name: 'edit-control',
            params: { controlId: menuRow.control_id },
          }">
          <q-item-section> Edit control </q-item-section>
        </q-item>
        <q-item
          clickable
          :to="{
            name: 'edit-control',
            params: { controlId: menuRow.control_id },
            query: { clone: true },
          }"
          v-close-popup>
          <q-item-section> Clone control</q-item-section>
        </q-item>
        <q-separator />
        <q-item dense clickable v-close-popup @click="confirmRecreateSchema(menuRow.control_name)">
          <q-item-section> Recreate schema </q-item-section>
        </q-item>
        <q-item dense clickable v-close-popup @click="deleteControl(menuRow)">
          <q-item-section> Delete control </q-item-section>
        </q-item>
      </q-list>
    </q-menu>
    <orphan-tables-dialog ref="orphanDialog" :tables="orphanTables" @changed="refreshSchemaDrift" />
    <orphan-kpis-dialog ref="orphanKpisDialog" :kpis="orphanKpis" @changed="refreshKpiControls" />
    <temp-tables-dialog ref="tempDialog" :tables="tempTables" @changed="refreshTempTables" />
  </q-page>
</template>

<script>
import { mapActions, mapGetters, mapState } from "vuex";
import ScheduleSummary from "./ScheduleSummary.vue";
import SkeletonRows from "./SkeletonRows.vue";
import RunControlDialog from "./RunControlDialog.vue";
import FilterChips from "./FilterChips.vue";
import { listFilter, searchFilter, valueFilter } from "../utils/filters";
import OrphanTablesDialog from "./OrphanTablesDialog.vue";
import OrphanKpisDialog from "./OrphanKpisDialog.vue";
import TempTablesDialog from "./TempTablesDialog.vue";
import { api, notifyError } from "../api";
import { CONTROL_ENGINES, CONTROL_TYPE_OPTIONS, controlType, KPI_ICON } from "../constants";
import { liveRefetch } from "../socket";
import { chainIndex } from "../utils/chain";
import { controlGroups, controlSystems, filterOptions, NO_CONTROL_GROUP } from "../utils/controlGroups";
import { sendsEmail } from "../utils/email";
import { formatNumber, toDateTimeString, toMillis } from "../utils/format";
import { scheduleFrequency, scheduleText, scheduleUnits, windowLabel } from "../utils/schedule";
import { fillViewportToBottom, textWidth } from "../utils/layout";
import { ariaSort, sortChip, sortIcon, sortRows, toggleSort } from "../utils/sort";
import persistFilters from "../mixins/persistFilters";

// No column: the server's order, last modified first.
const DEFAULT_SORT = { key: null, dir: "asc" };
const SORT_LABELS = { control_type: "Type", control_name: "Name", control_description: "Description", next_fire: "Scheduler" };

// Kept alive (App.vue), so it is built once; activated/deactivated start and stop its live refresh.
export default {
  name: "ControlCatalogue",
  mixins: [persistFilters("controls", ["filter", "sort"])],
  components: {
    OrphanTablesDialog,
    OrphanKpisDialog,
    TempTablesDialog,
    RunControlDialog,
    FilterChips,
    ScheduleSummary,
    SkeletonRows,
  },
  data() {
    return {
      // The System filter's options, narrowed to the typed text.
      systemOptions: [],
      // The message of a failed get-schema-drift, shown in the header, or null.
      schemaDriftError: null,
      // The answer of get-temp-tables: temporary tables runs left behind, shown as a header chip.
      tempTables: {},
      tempTablesRequest: 0,
      controlTypeOptions: CONTROL_TYPE_OPTIONS,
      kpiIcon: KPI_ICON,
      // The ids of the controls with at least one KPI (racs_kpi_config), or null when that is not known, e.g.
      // where the KPI tables are not deployed, so no control is flagged "No KPI".
      kpiControlIds: null,
      // get-kpi-type-usage rows (the KPIs of each control) and get-orphan-kpis rows (those of no control).
      kpiUsage: [],
      orphanKpis: [],
      loaded: false,
      refreshing: false,
      loadError: false,
      // The one row menu of the table, opened at the kebab button of the row it acts on.
      menuTarget: false,
      menuControlId: null,
      // The answer of get-next-fires ({ controls: { id: { fires, invalid } }, scheduler_active }), and the server
      // time the countdowns read: the browser clock corrected by the offset of the server's, advanced by a ticker.
      nextFires: { controls: {}, scheduler_active: true },
      clockOffset: 0,
      clock: Date.now(),
      filter: {
        control_name: "",
        group: null,
        type: null,
        status: null,
        other_attributes: [],
        system: null,
      },
      sort: { ...DEFAULT_SORT },
    };
  },
  methods: {
    ...mapActions(["updateControlCatalogue", "updateSchemaDrift"]),
    filterSystems(text, update) {
      update(() => {
        this.systemOptions = filterOptions(this.systemFilterOptions, text);
      });
    },
    controlType,
    formatNumber,
    toDateTimeString,
    sortIcon,
    ariaSort,
    toggleSort,
    fillViewportToBottom,
    async refreshControlCatalogue() {
      this.refreshing = true;
      this.loadError = false;
      try {
        await this.updateControlCatalogue();
        this.loaded = true;
      } catch (error) {
        this.loadError = true;
        notifyError("Failed to load controls.", error);
      } finally {
        this.refreshing = false;
      }
    },
    openRowMenu(event, row) {
      this.menuTarget = event.currentTarget;
      this.menuControlId = row.control_id;
      this.$nextTick(() => this.$refs.rowMenu.show());
    },
    // The result tables its type writes and its orphans (get-schema-drift); none when the check found no table.
    resultTablesOf(control) {
      const drift = (this.schemaDrift.controls || {})[control.control_id];
      const orphans = drift ? drift.orphans.map((orphan) => orphan.table) : [];
      if (drift && drift.level === "missing" && !orphans.length) {
        return [];
      }
      const name = control.control_name.toUpperCase();
      const written = control.control_type === "REC" ? [`RAPO_RESA_${name}`, `RAPO_RESB_${name}`] : [`RAPO_REST_${name}`];
      return [...new Set([...written, ...orphans])];
    },
    // Asks first, offering to drop the result tables and delete the KPIs too (ticked), so none is left behind as an
    // orphan.
    deleteControl(control) {
      const tables = this.resultTablesOf(control);
      const kpis = this.kpiUsage.filter((item) => item.control_id === control.control_id).map((item) => item.kpi_type);
      const items = [];
      if (tables.length) items.push({ label: `Also drop the result tables ${tables.join(", ")}, with all results`, value: "drop" });
      if (kpis.length) items.push({ label: `Also delete its KPI${kpis.length > 1 ? "s" : ""} ${kpis.join(", ")} (stored values are kept)`, value: "kpis" });
      const options = items.length ? { type: "checkbox", model: items.map((item) => item.value), items } : undefined;
      this.$q
        .dialog({ title: `Delete ${control.control_name}?`, message: "The control and its schedule are deleted.", options, cancel: true, persistent: true })
        .onOk(async (selected) => {
          const dropTables = (selected || []).includes("drop");
          const deleteKpis = (selected || []).includes("kpis");
          try {
            const result = await api("delete-control", {
              method: "DELETE",
              params: { control_id: control.control_id, drop_tables: dropTables, delete_kpis: deleteKpis },
            });
            const dropped = result.dropped || [];
            const kpisDeleted = result.kpis_deleted || [];
            const done = [dropped.length ? `its tables ${dropped.join(", ")} dropped` : "", kpisDeleted.length ? `its KPIs ${kpisDeleted.join(", ")} deleted` : ""].filter(Boolean);
            this.$q.notify({
              type: "positive",
              message: `Control ${control.control_name} was deleted${done.length ? `, and ${done.join(" and ")}` : ""}.`,
            });
          } catch (error) {
            notifyError("Control was not deleted.", error);
          }
          await Promise.all([this.updateControlCatalogue(), this.refreshSchemaDrift(), this.refreshKpiControls()]);
        });
    },
    confirmRecreateSchema(control_name) {
      this.$q
        .dialog({ title: control_name, message: "Recreate result tables? Past discrepancies will be deleted!", cancel: true, persistent: true, ok: { label: "Recreate", color: "negative" } })
        .onOk(() => this.recreateSchema(control_name));
    },
    async recreateSchema(control_name) {
      try {
        await api("recreate-control-schema", { method: "POST", params: { name: control_name } });
        this.$q.notify({ type: "positive", message: "Result tables of " + control_name + " were recreated." });
      } catch (error) {
        notifyError("Recreating the result tables of " + control_name + " failed.", error);
      }
    },
    // The drift of a control's result tables when there is something to fix, else null.
    driftOf(control) {
      const drift = (this.schemaDrift.controls || {})[control.control_id];
      return drift && (["update", "recreate", "error"].includes(drift.level) || drift.orphans.length) ? drift : null;
    },
    // The drift of a control whose datasource does not exist (get-schema-drift), else null; its reason names it.
    sourceMissingOf(control) {
      const drift = (this.schemaDrift.controls || {})[control.control_id];
      return drift && drift.level === "source_missing" ? drift : null;
    },
    // Amber when Update schema fixes it all, red when it takes Recreate schema, a configuration fix or a drop.
    driftColor(drift) {
      return drift.level === "update" && !drift.orphans.length ? "amber-8" : "red-4";
    },
    driftTitle(drift) {
      const orphans = drift.orphans.length ? ` Orphaned, no longer written: ${drift.orphans.map((orphan) => orphan.table).join(", ")}.` : "";
      if (drift.level === "error") {
        return `Schema check failed: ${drift.reason}.${orphans} Open the control to fix it.`;
      }
      if (!["update", "recreate"].includes(drift.level)) {
        return `${orphans.trim()} Open the control to drop them.`;
      }
      const parts = [];
      if (drift.changes) parts.push(`${drift.changes} column change(s) for Update schema`);
      if (drift.incompatible) parts.push(`${drift.incompatible} incompatible column(s) needing Recreate schema`);
      return `${drift.tables.join(", ")}: ${parts.join(", ")}.${orphans} Open the control to fix it.`;
    },
    async refreshSchemaDrift() {
      try {
        await this.updateSchemaDrift();
        this.schemaDriftError = null;
      } catch (error) {
        // Shown in the header rather than as a notification: the check refreshes itself on every change, and the
        // editor's own check still works.
        this.schemaDriftError = error.message;
      }
    },
    // A failure only hides the chip (the server log has it); the tables are refetched on the next run change.
    async refreshTempTables() {
      const request = ++this.tempTablesRequest;
      let data = {};
      try {
        data = await api("get-temp-tables", { loadingBar: false });
      } catch {
        // Nothing to show.
      }
      if (request === this.tempTablesRequest) {
        this.tempTables = data;
      }
    },
    // The engine of a REC control, the only type that has a choice; the others always run on DB.
    engineOf(control) {
      return control.control_type === "REC" ? control.control_engine || "DB" : null;
    },
    engineTitle(control) {
      const engine = CONTROL_ENGINES[this.engineOf(control)];
      return engine ? `Runs on the ${engine.label} engine` : "";
    },
    lacksKpi(control) {
      return this.kpiControlIds !== null && !this.kpiControlIds.has(control.control_id);
    },
    async refreshKpiControls() {
      if (!(this.getEnvInfo && this.getEnvInfo.kpi_available)) {
        this.kpiControlIds = null;
        this.kpiUsage = [];
        this.orphanKpis = [];
        return;
      }
      try {
        const [usage, orphans] = await Promise.all([api("get-kpi-type-usage", { loadingBar: false }), api("get-orphan-kpis", { loadingBar: false })]);
        this.kpiUsage = usage;
        this.orphanKpis = orphans;
        this.kpiControlIds = new Set(usage.map((item) => item.control_id).filter((id) => id != null));
      } catch (error) {
        console.error("KPI usage check failed:", error);
      }
    },
    // What the Chain chip says on hover: whose results the control reads, and who reads its results.
    chainTitle(control) {
      const chain = this.chains.get(control.control_name);
      return [
        chain.upstream.length ? `Runs ${chain.upstream.join(", ")} first and reads the results.` : "",
        chain.dependents.length ? `Its results are read by ${chain.dependents.join(", ")}.` : "",
      ]
        .filter(Boolean)
        .join(" ");
    },
    addAttributeFilter(attr) {
      if (!this.filter.other_attributes.includes(attr)) {
        this.filter.other_attributes.push(attr);
      }
    },
    iterationCount(control) {
      // A malformed iteration_config must not break rendering of the whole catalogue.
      try {
        return control.iteration_config ? JSON.parse(control.iteration_config).length || 0 : 0;
      } catch (err) {
        return 0;
      }
    },
    sendsEmail,
    // Every filter and the header search; the sort stays.
    clearFilters() {
      this.filter.control_name = null;
      this.filter.group = null;
      this.filter.type = null;
      this.filter.status = null;
      this.filter.other_attributes = [];
      this.filter.system = null;
      this.$store.commit("updateSearch", "");
    },
    // The time of the next run in milliseconds, null when none.
    nextFireValue(item) {
      const entry = this.nextFires.controls[item.control_id];
      return entry && entry.fires.length ? toMillis(entry.fires[0].time) : null;
    },
    // The controls pulling this one (chain-rules), from its next runs.
    pulledByOf(control) {
      const entry = this.nextFires.controls[control.control_id];
      return entry ? [...new Set(entry.fires.filter((fire) => fire.source === "chain").map((fire) => fire.via))] : [];
    },
    triggerNameOf(control) {
      const units = scheduleUnits(control.schedule_config);
      return units && units.trigger_id ? this.controlNames.get(Number(units.trigger_id)) || null : null;
    },
    async refreshNextFires() {
      try {
        const answer = await api("get-next-fires", { loadingBar: false });
        this.clockOffset = toMillis(answer.server_time) - Date.now();
        this.clock = Date.now();
        this.nextFires = Object.freeze(answer);
      } catch (error) {
        // Kept as it was: the countdowns go on, and the next change or fire tries again.
      }
      this.scheduleNextFiresRefresh();
    },
    // Refetch when the earliest run is due (it moves on to the next one), at the latest every 5 minutes.
    scheduleNextFiresRefresh() {
      clearTimeout(this.nextFiresTimer);
      const times = Object.values(this.nextFires.controls)
        .filter((entry) => entry.fires.length)
        .map((entry) => toMillis(entry.fires[0].time) - this.clockOffset - Date.now());
      const wait = Math.min(Math.max(Math.min(...times, Infinity) + 2000, 5000), 300000);
      this.nextFiresTimer = setTimeout(this.refreshNextFires, wait);
    },
  },
  computed: {
    // Every result table no run writes (get-schema-drift), reviewed in OrphanTablesDialog: those of a control whose
    // configuration no longer writes them, by control name, then those of no control.
    orphanTables() {
      const byId = new Map(this.controlCatalogue.map((control) => [String(control.control_id), control]));
      const owned = Object.entries(this.schemaDrift.controls || {}).flatMap(([controlId, drift]) => {
        const control = byId.get(controlId);
        return drift.orphans.map((orphan) => ({ ...orphan, control_id: Number(controlId), control_name: control ? control.control_name : null }));
      });
      owned.sort((a, b) => (a.control_name || "").localeCompare(b.control_name || "") || a.table.localeCompare(b.table));
      const unowned = (this.schemaDrift.unowned || []).map((table) => ({ ...table, control_id: null, control_name: null, reason: null }));
      return [...owned, ...unowned];
    },
    ...mapState(["controlCatalogue", "schemaDrift"]),
    ...mapGetters(["getSearch", "getEnvInfo"]),
    // Controls reading the results of other controls, or read by them (chain-rules), by control name.
    chains() {
      return chainIndex(this.controlCatalogue);
    },
    // "12 Controls", or "12 of 340 Controls" while filtered.
    countTitle() {
      const total = this.controlCatalogue.length;
      const shown = this.filteredControlCatalogueLen;
      const count = this.activeFilters.length ? `${shown} of ${total}` : String(shown);
      return `${count} Control${(this.activeFilters.length ? total : shown) === 1 ? "" : "s"}`;
    },
    sortChip() {
      return sortChip(this.sort, DEFAULT_SORT, SORT_LABELS, "last modified first");
    },
    activeFilters() {
      const filter = this.filter;
      return [
        ...valueFilter("type", "Type", filter.type, () => (filter.type = null)),
        ...valueFilter("name", "Name", filter.control_name, () => (filter.control_name = null), { text: true }),
        ...valueFilter("group", "Group", filter.group, () => (filter.group = null), { label: filter.group === NO_CONTROL_GROUP ? "No group" : filter.group }),
        ...valueFilter("system", "System", filter.system, () => (filter.system = null), { text: !this.systemFilterOptions.includes((filter.system || "").trim()) }),
        ...valueFilter("status", "Scheduler", filter.status, () => (filter.status = null), { label: filter.status === "Y" ? "Active" : "Inactive" }),
        ...listFilter("attribute", "Attribute", filter.other_attributes, (value) => (filter.other_attributes = filter.other_attributes.filter((item) => item !== value))),
        ...searchFilter(this.$store),
      ];
    },
    // How many controls of the whole catalogue each header chip counts; the drift avatar is amber only while every
    // drift is a plain Update schema, as the row chips are.
    headerCounts() {
      const counts = { sourceMissing: 0, drift: 0, noKpi: 0, driftColor: "amber-8" };
      this.controlCatalogue.forEach((control) => {
        const drift = this.driftOf(control);
        if (drift) {
          counts.drift++;
          if (this.driftColor(drift) !== "amber-8") counts.driftColor = "red-4";
        }
        if (this.sourceMissingOf(control)) counts.sourceMissing++;
        if (this.lacksKpi(control)) counts.noKpi++;
      });
      return counts;
    },
    // "No group" and the groups in use.
    groupFilterOptions() {
      return [{ label: "No group", value: NO_CONTROL_GROUP }, ...controlGroups(this.controlCatalogue).map((group) => ({ label: group, value: group }))];
    },
    // The systems in use, of side A and B alike. A system of the list matches exactly; typed text that is none of them
    // matches as a substring, ignoring case.
    systemFilterOptions() {
      return controlSystems(this.controlCatalogue);
    },
    // The attributes by group, the run steps in the order a run performs them; each group starts with a header.
    attributeOptions() {
      const groups = [
        ["Execution", ["DB engine", "PL engine"]],
        ["Scheduling", ["Cascade schedule", "Chain", "Iterations"]],
        ["Run steps", ["Preparation SQL", "Prerequisite SQL", "Pre-run hook", "Case definition", "Completion SQL", "Post-run hook", "No Post-run hook"]],
        ["Output", ["Email", ...(this.kpiControlIds !== null ? ["No KPI"] : [])]],
        ["Issues", ["Schema drift", "Datasource missing"]],
      ];
      return groups.flatMap(([group, values]) => [
        { label: group, value: `header:${group}`, header: true, disable: true },
        ...values.map((value) => ({ label: value, value })),
      ]);
    },
    // Skeleton rows only while nothing is known yet; a catalogue already in the store is shown at once.
    showSkeleton() {
      return !this.loaded && !this.controlCatalogue.length;
    },
    // The Name column fits the longest control name (bold 16px) or its version line (12px), plus the 16px cell
    // paddings; a longer name wraps.
    nameColumnWidth() {
      const names = textWidth(
        this.controlCatalogue.map((control) => control.control_name),
        "bold 16px Roboto, sans-serif"
      );
      const version = textWidth(["v.2026-09-30 10:27:09"], "12px Roboto, sans-serif");
      return Math.min(Math.max(names, version) + 36, 360);
    },
    // The Scheduler column fits its widest content, plus the cell paddings: the avatar (28px, 8px gap), then the
    // widest of the next run (a fixed worst case, since the countdown moves), the schedule in words, and the strip
    // (72px, 6px gap) with the window chip (icon, 5px paddings, border). Past the cap the words are cut short.
    schedulerColumnWidth() {
      const nextRun = textWidth(["≈ Tomorrow 17:28:05"], "500 13px Roboto, sans-serif") + 6 + textWidth(["(in 23h 59m)"], "13px Roboto, sans-serif");
      const words = textWidth(
        this.controlCatalogue.map((control) => scheduleText(control.schedule_config, this.triggerNameOf(control), this.pulledByOf(control))),
        "12px Roboto, sans-serif"
      );
      const windows = textWidth(
        this.controlCatalogue.map((control) => windowLabel(control.period_back, control.period_number, control.period_type)),
        "11px Roboto, sans-serif"
      );
      const details = 72 + 6 + (windows ? windows + 26 : 0);
      return Math.min(28 + 8 + Math.max(nextRun, words, details) + 34, 400);
    },
    serverNow() {
      return this.clock + this.clockOffset;
    },
    // Control names by ID, naming the control a cascade follows.
    controlNames() {
      return new Map(this.controlCatalogue.map((control) => [control.control_id, control.control_name]));
    },
    // Looked up by ID, so an open menu follows live updates of its control.
    menuRow() {
      return this.controlCatalogue.find((control) => control.control_id === this.menuControlId) || null;
    },
    sortedControlCatalogue() {
      const key = this.sort.key;
      if (!key) {
        return this.filteredControlCatalogue;
      }
      const valueOf =
        key === "next_fire" ? (item) => this.nextFireValue(item) : (item) => item[key];
      return sortRows(this.filteredControlCatalogue, valueOf, this.sort.dir);
    },
    filteredControlCatalogue() {
      const s = this.getSearch;
      var data = this.controlCatalogue;
      const system = (this.filter.system || "").trim();
      const exactSystem = this.systemFilterOptions.includes(system);
      if (s || this.filter.control_name || this.filter.group || this.filter.type || this.filter.status || this.filter.system || (this.filter.other_attributes && this.filter.other_attributes.length > 0)) {
        data = this.controlCatalogue.filter((item) => {
          const matchesSearch = s ? item.control_name?.toUpperCase().includes(s.toUpperCase()) : true;
          const matchesControlName = this.filter.control_name ? item.control_name?.toUpperCase().includes(this.filter.control_name.toUpperCase()) : true;
          const group = (item.control_group || "").trim();
          const matchesGroup = !this.filter.group || (this.filter.group === NO_CONTROL_GROUP ? !group : group === this.filter.group);
          const matchesType = this.filter.type ? item.control_type === this.filter.type : true;
          const matchesStatus = this.filter.status ? item.status === this.filter.status : true;
          const matchesSystem = !system || [item.source_type_a, item.source_type_b].some((value) => (exactSystem ? (value || "").trim() === system : (value || "").toLowerCase().includes(system.toLowerCase())));
          const matchesAttributes =
        this.filter.other_attributes && this.filter.other_attributes.length > 0
          ? this.filter.other_attributes.some((attr) => {
          return (
            (attr === `${this.engineOf(item)} engine`) ||
            (attr === "Preparation SQL" && item.preparation_sql) ||
            (attr === "Prerequisite SQL" && item.prerequisite_sql) ||
            (attr === "Completion SQL" && item.completion_sql) ||
            (attr === "Iterations" && this.iterationCount(item) > 0) ||
            (attr === "Cascade schedule" && scheduleFrequency(item.schedule_config) === "cascade") ||
            (attr === "Chain" && this.chains.has(item.control_name)) ||
            (attr === "Case definition" && item.case_config) ||
            (attr === "Pre-run hook" && item.need_prerun_hook === "Y") ||
            (attr === "Post-run hook" && item.need_postrun_hook === "Y") ||
            (attr === "No Post-run hook" && item.need_postrun_hook !== "Y") ||
            (attr === "No KPI" && this.lacksKpi(item)) ||
            (attr === "Email" && sendsEmail(item)) ||
            (attr === "Schema drift" && this.driftOf(item)) ||
            (attr === "Datasource missing" && this.sourceMissingOf(item))
          );
            })
          : true;

          return matchesSearch && matchesControlName && matchesGroup && matchesType && matchesStatus && matchesSystem && matchesAttributes;
        });
      }

      return data;
    },
    filteredControlCatalogueLen() {
      return this.filteredControlCatalogue.length;
    },
  },
  watch: {
    // The instance details can arrive after the page was opened.
    "getEnvInfo.kpi_available"() {
      this.refreshKpiControls();
    },
  },
  created() {
    // A sort kept from before the Scheduler column (Periods back, Schedule time).
    if (["schedule_days", "schedule_time", "schedule"].includes(this.sort.key)) {
      this.sort.key = "next_fire";
    }
  },
  // Also runs after the first mount.
  activated() {
    const stopCatalogue = liveRefetch("controls:changed", this.updateControlCatalogue);
    // A save or a schema update fixes drift, and so does a run (it updates its tables before saving).
    const stopDriftConfig = liveRefetch("controls:changed", this.refreshSchemaDrift);
    const stopDriftRuns = liveRefetch("runs:changed", this.refreshSchemaDrift, { interval: 30000 });
    // Runs leave temporary tables behind, or drop them.
    const stopTempRuns = liveRefetch("runs:changed", this.refreshTempTables, { interval: 30000 });
    // save-control writes the KPIs of a control; nothing watches racs_kpi_config itself.
    const stopKpis = liveRefetch("controls:changed", this.refreshKpiControls);
    // A schedule change moves the next runs; a scheduler stop or start greys or ungreys them.
    const stopNextFires = liveRefetch("controls:changed", this.refreshNextFires);
    const stopNextFiresScheduler = liveRefetch("scheduler:changed", this.refreshNextFires);
    const ticker = setInterval(() => (this.clock = Date.now()), 30000);
    this.stopLiveUpdates = () => {
      stopNextFires();
      stopNextFiresScheduler();
      clearInterval(ticker);
      clearTimeout(this.nextFiresTimer);
      stopKpis();
      stopCatalogue();
      stopDriftConfig();
      stopDriftRuns();
      stopTempRuns();
    };
    this.refreshControlCatalogue();
    this.refreshSchemaDrift();
    this.refreshTempTables();
    this.refreshKpiControls();
    this.refreshNextFires();
  },
  deactivated() {
    this.stopLiveUpdates();
  },
};
</script>

<style scoped>
/* Fixed columns, so rows swapped in while scrolling don't resize them. Type, Name and Scheduler fit their content
   (the type chip, nameColumnWidth, schedulerColumnWidth); Description takes the rest, at least 300px before the
   table scrolls sideways. */
.catalogue-table :deep(table) {
  table-layout: fixed;
  min-width: calc(110px + var(--name-column-width) + 300px + var(--scheduler-column-width) + 62px);
}
.catalogue-table th:nth-child(1) { width: 110px; }
.catalogue-table th:nth-child(2) { width: var(--name-column-width); }
.catalogue-table th:nth-child(4) { width: var(--scheduler-column-width); }
.catalogue-table th:nth-child(5) { width: 62px; }
.catalogue-table td:nth-child(4) { white-space: normal; }
.control-name {
  white-space: normal;
  overflow-wrap: anywhere;
}
</style>
