<template>
  <q-page>
    <h2 class="row q-gutter-lg q-mb-lg">
      <div>{{ filteredKpiTypesLen }} KPI type<span v-if="filteredKpiTypesLen != 1">s</span></div>
      <div v-if="!loaded">
        <q-avatar size="lg" color="grey-5">
          <q-icon name="fas fa-sync fa-spin" />
        </q-avatar>
      </div>
    </h2>

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

      <q-btn flat round color="grey" class="q-mb-md q-pa-sm" icon="fas fa-times-circle" @click="clearFilters">
        <q-tooltip anchor="top left" self="bottom left" :offset="[15, 10]"> Clear filters </q-tooltip>
      </q-btn>
    </div>

    <div>
      <q-markup-table>
        <thead>
          <tr class="bg-blue-grey-2">
            <th class="text-left sortable" style="width: 90px" @click="toggleSort(sort, 'kpi_type')">
              Code
              <q-icon v-if="sort.key === 'kpi_type'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-left sortable" @click="toggleSort(sort, 'kpi_type_desc')">
              Description
              <q-icon v-if="sort.key === 'kpi_type_desc'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-center sortable" style="width: 70px" @click="toggleSort(sort, 'kpi_value_unit')">
              Unit
              <q-icon v-if="sort.key === 'kpi_value_unit'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-center sortable" style="width: 80px" @click="toggleSort(sort, 'kpi_priority')">
              Priority
              <q-icon v-if="sort.key === 'kpi_priority'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-center sortable" style="width: 90px" @click="toggleSort(sort, 'kpi_decimal_places')">
              Decimals
              <q-icon v-if="sort.key === 'kpi_decimal_places'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-center" style="width: 200px">Default statements</th>
            <th class="text-center sortable" style="width: 90px" @click="toggleSort(sort, 'usage_count')">
              Used by
              <q-icon v-if="sort.key === 'usage_count'" :name="sortIcon(sort)" size="12px" />
            </th>
            <th class="text-left"></th>
          </tr>
        </thead>
        <tbody>
          <!-- The row opens the editor; what reacts on its own (the unit chip, the menu) stops the click. -->
          <tr
            v-for="kpiType in sortedKpiTypes"
            :key="kpiType.kpi_type"
            class="clickable-row"
            @click="$router.push({ name: 'edit-kpi-type', params: { kpiCode: kpiType.kpi_type } })">
            <td class="text-left">
              <div class="text-weight-bold text-grey-9" style="font-size: 16px">
                {{ kpiType.kpi_type }}
              </div>
            </td>
            <td class="text-left">{{ kpiType.kpi_type_desc }}</td>
            <td class="text-center">
              <q-chip v-if="kpiType.kpi_value_unit" size="12px" clickable @click.stop="filter.unit = kpiType.kpi_value_unit">
                {{ kpiType.kpi_value_unit }}
              </q-chip>
            </td>
            <td class="text-center">{{ kpiType.kpi_priority }}</td>
            <td class="text-center">{{ kpiType.kpi_decimal_places }}</td>
            <td class="text-center">
              <!-- A type without a default leaves that half to the controls, which is worth seeing at a glance. -->
              <q-chip v-if="kpiType.default_kpi_sql_statement" size="12px" color="blue-grey-2" icon="fas fa-calculator"> KPI </q-chip>
              <q-chip v-if="kpiType.default_alarm_sql_statement" size="12px" color="blue-grey-2" icon="fas fa-bell"> Alarm </q-chip>
            </td>
            <td class="text-center">
              <span v-if="usageOf(kpiType.kpi_type).length">{{ usageOf(kpiType.kpi_type).length }}</span>
              <span v-else class="text-grey-5">&ndash;</span>
            </td>

            <td @click.stop>
              <q-btn size="sm" color="grey-7" round flat icon="fas fa-ellipsis-v">
                <q-menu>
                  <q-list dense class="text-no-wrap">
                    <q-item
                      clickable
                      :to="{
                        name: 'edit-kpi-type',
                        params: { kpiCode: kpiType.kpi_type },
                      }">
                      <q-item-section> Edit KPI type </q-item-section>
                    </q-item>
                    <q-separator />
                    <!-- racs_kpi_config references the code, so a used type cannot be deleted. -->
                    <q-item v-if="usageOf(kpiType.kpi_type).length" dense disable>
                      <q-item-section> Delete KPI type </q-item-section>
                      <q-tooltip anchor="top middle" self="bottom middle">
                        Used by {{ usageOf(kpiType.kpi_type).length }} control(s)
                      </q-tooltip>
                    </q-item>
                    <confirm-dialog
                      v-else
                      icon="fas fa-trash-alt"
                      :text="'Do you really want to delete KPI type ' + kpiType.kpi_type + '?'"
                      :action="deleteKpiType"
                      :argument="kpiType.kpi_type">
                      <q-item dense clickable>
                        <q-item-section> Delete KPI type </q-item-section>
                      </q-item>
                    </confirm-dialog>
                  </q-list>
                </q-menu>
              </q-btn>
            </td>
          </tr>
        </tbody>
      </q-markup-table>
    </div>
  </q-page>
</template>

<script>
import { mapActions, mapGetters, mapState } from "vuex";
import ConfirmDialog from "./ConfirmDialog.vue";
import { api, notifyError } from "../api";
import { sortIcon, sortRows, toggleSort } from "../utils/sort";

export default {
  components: {
    ConfirmDialog,
  },
  data() {
    return {
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
    };
  },
  methods: {
    ...mapActions(["updateKpiTypes"]),
    sortIcon,
    toggleSort,
    usageOf(kpiType) {
      return this.usage.filter((item) => item.kpi_type === kpiType);
    },
    clearFilters() {
      this.filter.text = null;
      this.filter.unit = null;
      this.filter.used = null;
      this.sort.key = null;
      this.sort.dir = "asc";
    },
    async load() {
      // Force, because the catalogue is edited here and the store caches it for the whole session.
      const [types] = await Promise.all([this.updateKpiTypes({ force: true }), this.loadUsage()]);
      return types;
    },
    async loadUsage() {
      this.usage = await api("get-kpi-type-usage", { loadingBar: false });
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
.sortable {
  cursor: pointer;
  user-select: none;
}

.clickable-row {
  cursor: pointer;
}

.clickable-row:hover {
  background: rgba(0, 0, 0, 0.03);
}
</style>
