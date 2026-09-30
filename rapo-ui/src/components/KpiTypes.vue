<template>
  <q-page class="column no-wrap" :style-fn="fillViewportToBottom">
    <div class="row items-end" :class="activeFilters.length ? 'q-mb-sm' : 'q-mb-lg'">
      <h2 class="row items-center no-wrap text-no-wrap q-gutter-lg q-mb-none">
        <div v-if="!loaded">KPI types</div>
        <div v-else>{{ countTitle }}</div>
      </h2>
    </div>
    <filter-chips v-if="loaded" :filters="activeFilters" class="q-mb-md" @clear="clearFilters" />

    <div class="row items-center q-mb-md">
      <q-btn
        class="col-2 q-mb-md q-pa-sm"
        size="lg"
        color="primary"
        icon="fas fa-plus-circle"
        label="New KPI type"
        :to="{ name: 'edit-kpi-type', params: { kpiCode: 'new' } }" />

      <q-input clearable class="col q-mb-md q-pa-sm" outlined v-model="filter.text" label="Code or description" maxlength="45" />

      <q-select
        v-model="filter.unit"
        class="col-2 q-mb-md q-pa-sm"
        clearable
        outlined
        options-dense
        emit-value
        map-options
        :options="unitOptions"
        label="Unit">
      </q-select>

      <q-select
        v-model="filter.used"
        class="col-2 q-mb-md q-pa-sm"
        clearable
        outlined
        options-dense
        emit-value
        map-options
        :options="[
          { label: 'Used by controls', value: 'Y' },
          { label: 'Not used', value: 'N' },
        ]"
        label="Usage">
      </q-select>

    </div>

    <q-virtual-scroll
      type="table"
      class="list-table kpi-table"
      :items="sortedKpiTypes"
      :virtual-scroll-item-size="56"
      :virtual-scroll-sticky-size-start="48"
      :table-colspan="8">
      <template #before>
        <thead>
          <tr class="bg-blue-grey-2">
            <th class="text-left sortable" @click="toggleSort(sort, 'kpi_type')" v-keyboard :aria-sort="ariaSort(sort, 'kpi_type')">
              Code
              <q-icon v-if="sort.key === 'kpi_type'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-left sortable" @click="toggleSort(sort, 'kpi_type_desc')" v-keyboard :aria-sort="ariaSort(sort, 'kpi_type_desc')">
              Description
              <q-icon v-if="sort.key === 'kpi_type_desc'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-center sortable" @click="toggleSort(sort, 'kpi_value_unit')" v-keyboard :aria-sort="ariaSort(sort, 'kpi_value_unit')">
              Unit
              <q-icon v-if="sort.key === 'kpi_value_unit'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-center sortable" @click="toggleSort(sort, 'kpi_priority')" v-keyboard :aria-sort="ariaSort(sort, 'kpi_priority')">
              Priority
              <q-icon v-if="sort.key === 'kpi_priority'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-center sortable" @click="toggleSort(sort, 'kpi_decimal_places')" v-keyboard :aria-sort="ariaSort(sort, 'kpi_decimal_places')">
              Decimals
              <q-icon v-if="sort.key === 'kpi_decimal_places'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-center">Default statements</th>
            <th class="text-center sortable" @click="toggleSort(sort, 'usage_count')" v-keyboard :aria-sort="ariaSort(sort, 'usage_count')">
              Used by
              <q-icon v-if="sort.key === 'usage_count'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-left"></th>
          </tr>
        </thead>
      </template>
      <!-- The row opens the editor; what reacts on its own (the unit chip, the menu) stops the click. -->
      <template #default="{ item: kpiType }">
        <tr :key="kpiType.kpi_type" class="clickable-row" @click="$router.push({ name: 'edit-kpi-type', params: { kpiCode: kpiType.kpi_type } })">
          <td class="text-left">
            <q-chip :title="kpiType.kpi_value_unit || 'No unit'">
              <q-avatar :icon="kpiIcon" :color="kpiUnitColor(kpiType.kpi_value_unit)" text-color="white" />
              {{ kpiType.kpi_type }}
            </q-chip>
          </td>
          <td class="text-left">{{ kpiType.kpi_type_desc }}</td>
          <td class="text-center">
            <q-chip v-if="kpiType.kpi_value_unit" size="12px" clickable @click.stop="filter.unit = kpiType.kpi_value_unit">
              {{ kpiType.kpi_value_unit }}
            </q-chip>
          </td>
          <td class="text-center number-cell">{{ kpiType.kpi_priority }}</td>
          <td class="text-center number-cell">{{ kpiType.kpi_decimal_places }}</td>
          <td class="text-center">
            <!-- A type without a default leaves that half to the controls, which is worth seeing at a glance. -->
            <q-chip v-if="kpiType.default_kpi_sql_statement" size="12px" color="blue-grey-2" icon="fas fa-calculator"> KPI </q-chip>
            <q-chip v-if="kpiType.default_alarm_sql_statement" size="12px" color="blue-grey-2" icon="fas fa-bell"> Alarm </q-chip>
          </td>
          <td class="text-center">
            <span v-if="usageOf(kpiType.kpi_type).length">{{ usageOf(kpiType.kpi_type).length }}</span>
            <span v-else class="text-grey-7">&ndash;</span>
          </td>
          <td @click.stop>
            <q-btn aria-label="Row actions" size="sm" color="grey-7" round flat icon="fas fa-ellipsis-v" @click="openRowMenu($event, kpiType)" />
          </td>
        </tr>
      </template>
      <template #after>
        <tbody v-if="!loaded">
          <skeleton-rows :rows="8" :columns="['QChip', 'text', 'QChip', 'text', 'text', 'text', 'text', null]" />
        </tbody>
        <tbody v-else-if="!sortedKpiTypes.length">
          <tr>
            <td colspan="8" class="text-center text-grey-7 q-pa-lg">No KPI types match the filters</td>
          </tr>
        </tbody>
      </template>
    </q-virtual-scroll>
    <q-menu ref="rowMenu" :target="menuTarget" no-parent-event>
      <q-list v-if="menuRow" dense class="text-no-wrap">
        <q-item clickable v-close-popup :to="{ name: 'edit-kpi-type', params: { kpiCode: menuRow.kpi_type } }">
          <q-item-section> Edit KPI type </q-item-section>
        </q-item>
        <q-separator />
        <!-- racs_kpi_config references the code, so a used type cannot be deleted. -->
        <q-item v-if="usageOf(menuRow.kpi_type).length" dense disable>
          <q-item-section> Delete KPI type </q-item-section>
          <q-tooltip anchor="top middle" self="bottom middle"> Used by {{ usageOf(menuRow.kpi_type).length }} control(s) </q-tooltip>
        </q-item>
        <q-item v-else dense clickable v-close-popup @click="confirmDeleteKpiType(menuRow.kpi_type)">
          <q-item-section> Delete KPI type </q-item-section>
        </q-item>
      </q-list>
    </q-menu>
  </q-page>
</template>

<script>
import { mapActions, mapGetters, mapState } from "vuex";
import FilterChips from "./FilterChips.vue";
import SkeletonRows from "./SkeletonRows.vue";
import { api, notifyError } from "../api";
import { KPI_ICON, kpiUnitColor } from "../constants";
import { searchFilter, valueFilter } from "../utils/filters";
import { fillViewportToBottom } from "../utils/layout";
import { ariaSort, sortIcon, sortRows, toggleSort } from "../utils/sort";
import persistFilters from "../mixins/persistFilters";

export default {
  mixins: [persistFilters("kpi_types", ["filter", "sort"])],
  components: {
    FilterChips,
    SkeletonRows,
  },
  data() {
    return {
      kpiIcon: KPI_ICON,
      // Until the first load, the table shows skeleton rows: the usage counts are never cached.
      loaded: false,
      // One row per (KPI type, control) of racs_kpi_config, which is what makes a type undeletable.
      usage: [],
      filter: {
        text: "",
        unit: null,
        used: null,
      },
      sort: {
        key: null,
        dir: "asc",
      },
      menuTarget: false,
      menuKpiType: null,
    };
  },
  methods: {
    ...mapActions(["updateKpiTypes"]),
    sortIcon,
    ariaSort,
    toggleSort,
    kpiUnitColor,
    fillViewportToBottom,
    openRowMenu(event, row) {
      this.menuTarget = event.currentTarget;
      this.menuKpiType = row.kpi_type;
      this.$nextTick(() => this.$refs.rowMenu.show());
    },
    usageOf(kpiType) {
      return this.usage.filter((item) => item.kpi_type === kpiType);
    },
    // Every filter and the header search; the sort stays.
    clearFilters() {
      this.filter.text = null;
      this.filter.unit = null;
      this.filter.used = null;
      this.$store.commit("updateSearch", "");
    },
    async load() {
      // Force, because the catalogue is edited here and the store caches it for the whole session.
      const [types] = await Promise.all([this.updateKpiTypes({ force: true }), this.loadUsage()]);
      return types;
    },
    async loadUsage() {
      this.usage = await api("get-kpi-type-usage", { loadingBar: false });
    },
    confirmDeleteKpiType(kpi_type) {
      this.$q
        .dialog({ title: kpi_type, message: `Do you really want to delete KPI type ${kpi_type}?`, cancel: true, persistent: true, ok: { label: "Delete", color: "negative" } })
        .onOk(() => this.deleteKpiType(kpi_type));
    },
    async deleteKpiType(kpi_type) {
      try {
        await api("delete-kpi-type", { method: "DELETE", params: { kpi_type } });
        this.$q.notify({ type: "positive", message: "KPI type " + kpi_type + " was deleted." });
        await this.load();
      } catch (error) {
        notifyError("KPI type was not deleted.", error);
      }
    },
  },
  computed: {
    ...mapState(["kpiTypes"]),
    ...mapGetters(["getSearch"]),
    // "12 KPI types", or "3 of 25 KPI types" while filtered.
    countTitle() {
      const total = this.kpiTypes.length;
      const shown = this.filteredKpiTypesLen;
      const count = this.activeFilters.length ? `${shown} of ${total}` : String(shown);
      return `${count} KPI type${(this.activeFilters.length ? total : shown) === 1 ? "" : "s"}`;
    },
    activeFilters() {
      const filter = this.filter;
      return [
        ...valueFilter("text", "Code or description", filter.text, () => (filter.text = null), { text: true }),
        ...valueFilter("unit", "Unit", filter.unit, () => (filter.unit = null)),
        ...valueFilter("used", "Usage", filter.used, () => (filter.used = null), { label: filter.used === "Y" ? "Used by controls" : "Not used" }),
        ...searchFilter(this.$store),
      ];
    },
    // Looked up by code, so an open menu follows a refresh.
    menuRow() {
      return this.kpiTypes.find((item) => item.kpi_type === this.menuKpiType) || null;
    },
    unitOptions() {
      return [...new Set(this.kpiTypes.map((item) => item.kpi_value_unit).filter(Boolean))].sort();
    },
    sortedKpiTypes() {
      const key = this.sort.key;
      if (!key) {
        return this.filteredKpiTypes;
      }
      const valueOf = key === "usage_count" ? (item) => this.usageOf(item.kpi_type).length : (item) => item[key];
      return sortRows(this.filteredKpiTypes, valueOf, this.sort.dir);
    },
    filteredKpiTypes() {
      const s = this.getSearch;
      var data = this.kpiTypes;
      if (s || this.filter.text || this.filter.unit || this.filter.used) {
        data = this.kpiTypes.filter((item) => {
          const text = (item.kpi_type + " " + (item.kpi_type_desc || "")).toUpperCase();
          const matchesSearch = s ? text.includes(s.toUpperCase()) : true;
          const matchesText = this.filter.text ? text.includes(this.filter.text.toUpperCase()) : true;
          const matchesUnit = this.filter.unit ? item.kpi_value_unit === this.filter.unit : true;
          const matchesUsed = this.filter.used ? (this.usageOf(item.kpi_type).length > 0) === (this.filter.used === "Y") : true;

          return matchesSearch && matchesText && matchesUnit && matchesUsed;
        });
      }

      return data;
    },
    filteredKpiTypesLen() {
      return this.filteredKpiTypes.length;
    },
  },
  async mounted() {
    // Nothing watches racs_kpi_* for live updates, so the page refreshes itself after every write.
    try {
      await this.load();
      this.loaded = true;
    } catch (error) {
      notifyError("Failed to load KPI types.", error);
    }
  },
};
</script>

<style scoped>
/* Fixed columns, so rows swapped in while scrolling don't resize them; Description takes the rest. */
.kpi-table :deep(table) {
  table-layout: fixed;
  min-width: 860px;
}
.kpi-table th:nth-child(1) { width: 190px; }
.kpi-table th:nth-child(3) { width: 80px; }
.kpi-table th:nth-child(4) { width: 90px; }
.kpi-table th:nth-child(5) { width: 100px; }
.kpi-table th:nth-child(6) { width: 200px; }
.kpi-table th:nth-child(7) { width: 100px; }
.kpi-table th:nth-child(8) { width: 62px; }
</style>
