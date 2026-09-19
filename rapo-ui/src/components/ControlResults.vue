<template>
  <q-page>
    <h2 class="row q-gutter-lg">
      <div>Last control result<span v-if="filteredControlResultsLen != 1">s</span></div>
      <div v-if="controlResults.length === 0">
        <q-avatar size="lg" color="grey-5">
          <q-icon name="fas fa-sync fa-spin" />
        </q-avatar>
      </div>
    </h2>

    <div class="row items-center q-mb-md">
      <q-btn class="col-2 q-mb-md q-pa-sm" size="lg" color="primary" icon="fas fa-play-circle" label="Run control" @click="$refs.runControlDialog.open()" />
      <run-control-dialog ref="runControlDialog" :hook="refreshControlResults" />

      <q-select
        v-model="filter.type"
        class="col-2 q-mb-md q-pa-sm"
        clearable
        outlined
        options-dense
        emit-value
        map-options
        :options="[
          { label: 'ANL - Analysis', value: 'ANL' },
          { label: 'REC - Reconciliation', value: 'REC' },
          { label: 'CMP - Comparison', value: 'CMP' },
          { label: 'REP - Reporting', value: 'REP' },
        ]"
        label="Control type">
      </q-select>

      <q-input clearable class="col q-mb-md q-pa-sm" outlined v-model="filter.control_name" label="Control name" maxlength="45" />

      <q-select
        v-model="filter.status"
        class="col-4 q-mb-md q-pa-sm"
        outlined
        options-dense
        emit-value
        map-options
        multiple
        use-chips
        :options="[
          { label: 'Initiated', value: 'I' },
          { label: 'Waiting', value: 'W' },
          { label: 'Started', value: 'S' },
          { label: 'Running', value: 'P' },
          { label: 'Finishing', value: 'F' },
          { label: 'Done', value: 'D' },
          { label: 'Error', value: 'E' },
          { label: 'Canceled', value: 'C' },
          { label: 'Revoked', value: 'X' },
        ]"
        label="Run status">
      </q-select>

      <q-btn flat round color="grey" class="q-mb-md q-pa-sm" icon="fas fa-times-circle" @click="clearFilters">
        <q-tooltip anchor="top left" self="bottom left" :offset="[15, 10]"> Clear filters </q-tooltip>
      </q-btn>
    </div>

    <div>
      <q-markup-table dense>
        <thead>
          <tr class="bg-blue-grey-2">
            <th class="text-left sortable" @click="setSort('control_type')">
              Type
              <q-icon v-if="sort.key === 'control_type'" :name="sort.dir === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'" size="12px" />
            </th>
            <th class="text-left sortable" @click="setSort('start_date')">
              Start
              <q-icon v-if="sort.key === 'start_date'" :name="sort.dir === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'" size="12px" />
            </th>
            <th class="text-right sortable" @click="setSort('duration_minutes')">
              Runtime
              <q-icon v-if="sort.key === 'duration_minutes'" :name="sort.dir === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'" size="12px" />
            </th>
            <th class="text-center sortable" @click="setSort('process_id')">
              PID
              <q-icon v-if="sort.key === 'process_id'" :name="sort.dir === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'" size="12px" />
            </th>
            <th class="text-left sortable" @click="setSort('control_name')">
              Processname
              <q-icon v-if="sort.key === 'control_name'" :name="sort.dir === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'" size="12px" />
            </th>
            <th class="text-left sortable" @click="setSort('date_from')">
              Run from
              <q-icon v-if="sort.key === 'date_from'" :name="sort.dir === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'" size="12px" />
            </th>
            <th class="text-left sortable" @click="setSort('date_to')">
              Run to
              <q-icon v-if="sort.key === 'date_to'" :name="sort.dir === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'" size="12px" />
            </th>
            <th class="text-right sortable" @click="setSort('fetched_number_a')">
              Fetched A
              <q-icon v-if="sort.key === 'fetched_number_a'" :name="sort.dir === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'" size="12px" />
            </th>
            <th class="text-right sortable" @click="setSort('fetched_number_b')">
              Fetched B
              <q-icon v-if="sort.key === 'fetched_number_b'" :name="sort.dir === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'" size="12px" />
            </th>
            <th class="text-right sortable" @click="setSort('error_number_a')">
              Discr. A
              <q-icon v-if="sort.key === 'error_number_a'" :name="sort.dir === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'" size="12px" />
            </th>
            <th class="text-right sortable" @click="setSort('error_number_b')">
              Discr. B
              <q-icon v-if="sort.key === 'error_number_b'" :name="sort.dir === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'" size="12px" />
            </th>
            <th class="text-right sortable" @click="setSort('error_level_a')">
              Err. lvl A [%]
              <q-icon v-if="sort.key === 'error_level_a'" :name="sort.dir === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'" size="12px" />
            </th>
            <th class="text-right sortable" @click="setSort('error_level_b')">
              Err. lvl B [%]
              <q-icon v-if="sort.key === 'error_level_b'" :name="sort.dir === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'" size="12px" />
            </th>
            <th class="text-right sortable" @click="setSort('prerequisite_value')">
              PV
              <q-icon v-if="sort.key === 'prerequisite_value'" :name="sort.dir === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'" size="12px" />
            </th>
            <th class="text-left sortable" @click="setSort('status')">
              Status
              <q-icon v-if="sort.key === 'status'" :name="sort.dir === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'" size="12px" />
            </th>
            <th class="text-left"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(control, index) in sortedControlResults" :key="control.process_id">
            <td class="text-center" :class="{ 'new-day-separator': newDaySeparator(index) }">
              <q-chip
                clickable
                size="11px"
                text-color="white"
                :class="{
                  'bg-pink-8': control.control_type === 'ANL',
                  'bg-teal-8': control.control_type === 'REC',
                  'bg-lime-8': control.control_type === 'CMP',
                  'bg-indigo-6': control.control_type === 'REP',
                }"
                class="text-weight-bold"
                @click="this.filter.type = control.control_type">
                {{ control.control_type }}
              </q-chip>
            </td>
            <td class="text-left" :class="{ 'new-day-separator': newDaySeparator(index) }">
              <div class="text-blue-grey-7">
                <strong>{{ toDateString(control.start_date) }}</strong>
                <small class="text-grey-7 q-px-sm">{{ toTimeString(control.start_date) }}</small>
              </div>
            </td>
            <td class="text-right" :class="{ 'new-day-separator': newDaySeparator(index) }">{{ round(control.duration_minutes, 1) }} min</td>
            <td class="text-center text-weight-bold text-blue-grey-7" :class="{ 'new-day-separator': newDaySeparator(index) }">{{ control.process_id }}</td>
            <td class="text-left text-weight-bold text-teal" :class="{ 'new-day-separator': newDaySeparator(index) }">
              <q-btn
                v-if="!this.getSearch"
                size="7px"
                color="grey-5"
                round
                flat
                icon="fas fa-search"
                @click.stop="this.filter.control_name = control.control_name" />
              <router-link
                :to="{
                  name: 'edit-control',
                  params: { controlId: control.control_id },
                }">
                <span
                  class="col cursor-pointer"
                  style="font-size: 13px"
                  :class="{
                    'text-pink-8': control.control_type === 'ANL',
                    'text-teal-8': control.control_type === 'REC',
                    'text-lime-8': control.control_type === 'CMP',
                    'text-indigo-6': control.control_type === 'REP',
                  }">
                  {{ control.control_name }}
                </span>
              </router-link>
            </td>
            <td class="text-left text-weight-bold text-blue-grey-7" :class="{ 'new-day-separator': newDaySeparator(index) }">
              {{ toDateString(control.date_from) }}
            </td>
            <td class="text-left text-weight-bold text-blue-grey-7" :class="{ 'new-day-separator': newDaySeparator(index) }">
              {{ toDateString(control.date_to) }}
            </td>
            <td class="text-right" :class="{ 'new-day-separator': newDaySeparator(index) }">
              <span
                v-if="control.fetched_number_a > 0 && control.control_type === 'REP'"
                class="cursor-pointer text-red"
                @click="copyToClipboard(control, 'A')">
                {{ Number(control.fetched_number_a).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 }) }}
              </span>
              <span v-else>
                {{ Number(control.fetched_number_a).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 }) }}
              </span>
            </td>
            <td class="text-right" :class="{ 'new-day-separator': newDaySeparator(index) }">
              {{ Number(control.fetched_number_b).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 }) }}
            </td>
            <td class="text-right" :class="{ 'new-day-separator': newDaySeparator(index) }">
              <span v-if="control.error_number_a > 0" class="cursor-pointer text-red" @click="copyToClipboard(control, 'A')">
                {{ Number(control.error_number_a).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 }) }}
              </span>
              <span v-else>
                {{ Number(control.error_number_a).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 }) }}
              </span>
            </td>
            <td class="text-right" :class="{ 'new-day-separator': newDaySeparator(index) }">
              <span v-if="control.error_number_b > 0" class="cursor-pointer text-red" @click="copyToClipboard(control, 'B')">
                {{ Number(control.error_number_b).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 }) }}
              </span>
              <span v-else>
                {{ Number(control.error_number_b).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 }) }}
              </span>
            </td>
            <td class="text-right" :class="{ 'new-day-separator': newDaySeparator(index) }">
              <span v-if="control.error_level_a > 0" class="cursor-pointer text-red" @click="copyToClipboard(control, 'A')">
                {{ Number(control.error_level_a).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}%
              </span>
              <span v-else> {{ Number(control.error_level_a).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}% </span>
            </td>
            <td class="text-right" :class="{ 'new-day-separator': newDaySeparator(index) }">
              <span v-if="control.error_level_b > 0" class="cursor-pointer text-red" @click="copyToClipboard(control, 'B')">
                {{ Number(control.error_level_b).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}%
              </span>
              <span v-else> {{ Number(control.error_level_b).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}% </span>
            </td>
            <td class="text-right" :class="{ 'new-day-separator': newDaySeparator(index) }">
              <q-icon v-if="control.prerequisite_value == 0" class="cursor-pointer text-red" name="fas fa-stop">
                <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]"> Prerequisite SQL value is 0 </q-tooltip>
              </q-icon>
              <q-icon v-if="control.prerequisite_value" class="cursor-pointer text-green" name="fas fa-play">
                <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]"> Prerequisite SQL value is {{ control.prerequisite_value }} </q-tooltip>
              </q-icon>
            </td>
            <td class="text-left" :class="{ 'new-day-separator': newDaySeparator(index) }">
              <q-chip clickable class="cursor-pointer" @click="!this.filter.status.includes(control.status) && this.filter.status.push(control.status)">
                <q-avatar v-if="control.status == 'I'" icon="fas fa-plus-circle" color="indigo" text-color="white" />
                <q-avatar v-if="control.status == 'W'" icon="fas fa-pause-circle" color="amber-7" text-color="white" />
                <q-avatar v-if="control.status == 'S'" icon="fas fa-play-circle" color="blue" text-color="white" />
                <q-avatar v-if="control.status == 'P'" icon="fas fa-sync fa-spin" color="blue" text-color="white" />
                <q-avatar v-if="control.status == 'F'" icon="fas fa-circle-notch fa-spin" color="blue" text-color="white" />
                <q-avatar v-if="control.status == 'D'" icon="fas fa-check-circle" color="green" text-color="white" />
                <q-avatar v-if="control.status == 'C'" icon="fas fa-times-circle" color="purple-3" text-color="white" />
                <q-avatar v-if="control.status == 'E'" icon="fas fa-exclamation-circle" color="deep-orange" text-color="white" />
                <q-avatar v-if="control.status == 'X'" icon="fas fa-times-circle" color="grey" text-color="white" />
                <q-avatar v-if="!control.status" icon="fas fa-times-circle" color="deep-purple-3" text-color="white" />
                {{
                  control.status === "I"
                    ? "Initiated"
                    : control.status === "W"
                    ? "Waiting"
                    : control.status === "S"
                    ? "Started"
                    : control.status == "P"
                    ? "Running"
                    : control.status === "F"
                    ? "Finishing"
                    : control.status === "D"
                    ? "Done"
                    : control.status === "E"
                    ? "Error"
                    : control.status === "C"
                    ? "Canceled"
                    : control.status === "X"
                    ? "Revoked"
                    : !control.status
                    ? "Void"
                    : "Unknown"
                }}
              </q-chip>
            </td>
            <td class="text-left" :class="{ 'new-day-separator': newDaySeparator(index) }" style="width: 50px">
              <q-btn size="sm" color="grey-7" round flat icon="fas fa-ellipsis-v">
                <q-menu>
                  <q-list dense class="text-no-wrap">
                    <q-item dense clickable @click="reRun(control)" v-close-popup>
                      <q-item-section> Re-run </q-item-section>
                    </q-item>
                    <run-control-dialog :control_name="control.control_name" :hook="refreshControlResults">
                      <q-item dense clickable class="col items-center">
                        <q-item-section> Run </q-item-section>
                      </q-item>
                    </run-control-dialog>
                    <q-separator />
                    <q-item dense clickable @click="navigateToEditControl(control)">
                      <q-item-section> Edit control </q-item-section>
                    </q-item>
                    <q-separator />
                    <q-item v-if="control.status != 'X'" dense clickable class="col items-center" @click="showRevokeDialog(control)" v-close-popup>
                      <q-item-section> Revoke run </q-item-section>
                    </q-item>
                    <q-item
                      v-if="control.status == 'F' || control.status == 'I' || control.status == 'W' || control.status == 'S' || control.status == 'P'"
                      dense
                      clickable
                      class="col items-center"
                      @click="showCancelDialog(control)"
                      v-close-popup>
                      <q-item-section> Cancel run </q-item-section>
                    </q-item>
                    <q-item v-if="control.status == 'E'" dense clickable class="col items-center" @click="showErrorDialog(control)" v-close-popup>
                      <q-item-section> Show error log </q-item-section>
                    </q-item>
                    <q-item dense clickable @click="dropTemporaryTables(control)" v-close-popup>
                      <q-item-section> Drop temporary tables </q-item-section>
                    </q-item>
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
import { mapActions, mapGetters } from "vuex";
import { useQuasar } from "quasar";
import RunControlDialog from "./RunControlDialog.vue";
// import ConfirmDialog from "./ConfirmDialog.vue";

export default {
  components: {
    RunControlDialog,
    // ConfirmDialog,
  },
  data() {
    return {
      $q: useQuasar(),
      pagination: {
        rowsPerPage: 0,
      },
      refreshTimer: null,
      controlResults: [],
      filter: {
        type: null,
        status: [],
      },
      sort: {
        key: "start_date",
        dir: "desc",
      },
    };
  },
  methods: {
    ...mapActions(["updateControlResults", "updateSearch"]),
    newDaySeparator(index) {
      if (index > 0) {
        const prev_date = this.toDateString(this.sortedControlResults[index - 1].start_date);
        const curr_date = this.toDateString(this.sortedControlResults[index].start_date);
        if (prev_date != curr_date) {
          return true;
        }
      }
      return false;
    },
    copyToClipboard(control, side) {
      var table_suffix = "T";
      if (control.control_type == "REC") {
        table_suffix = side;
      }

      const textarea = document.createElement("textarea");
      textarea.value = "select * from RAPO_RES" + table_suffix + "_" + control.control_name + " where RAPO_PROCESS_ID = " + control.process_id + ";";
      textarea.style.position = "fixed";
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      try {
        document.execCommand("copy");
        this.$q.notify({ type: "positive", message: "SQL statement copied to clipboard: " + textarea.value });
      } catch (err) {
        this.$q.notify({ type: "negative", message: "Failed to copy SQL to clipboard" });
      }
      document.body.removeChild(textarea);
    },
    toDateString(val) {
      var ret = new Date(val).toISOString("de-DE").substring(0, 10);
      return ret;
    },
    toTimeString(val) {
      var ret = new Date(val).toISOString("de-DE").substring(11, 19);
      return ret;
    },
    toDateTimeString(val) {
      var ret = new Date(val).toISOString("de-DE").substring(0, 19).replace("T", " ");
      return ret;
    },
    round(val, places) {
      return Math.round(val * Math.pow(10, places)) / Math.pow(10, places);
    },
    parseNumericSortValue(val) {
      if (val == null) return null;
      if (typeof val === "number") {
        return Number.isFinite(val) ? val : null;
      }
      const match = String(val).match(/-?\d+(?:\.\d+)?/);
      return match ? Number(match[0]) : null;
    },
    navigateToEditControl(control) {
      this.$router.push({ name: "edit-control", params: { controlId: control.control_id } });
    },
    showErrorDialog(control) {
      this.$q.dialog({
        title: control.control_name + " - Error log",
        message: control.text_error
          ? "<div class='text-body2' style='font-family: monospace;'>" + control.text_error.replace(/\n/g, "<br>$&") + "</div>"
          : "No error log available",
        html: true,
        style: {
          width: "800px", // Adjust the width as needed
          maxWidth: "90vw", // Optional: Ensure it doesn't exceed viewport width
        },
      });
    },
    reRun(control) {
      // console.log("Re-run control: " + JSON.stringify(control));
      this.$q
        .dialog({
          title: control.control_name,
          message:
            "Re-run for '" +
            this.toDateString(control.date_from) +
            "'" +
            (this.toDateString(control.date_from) != this.toDateString(control.date_to) ? " - '" + this.toDateString(control.date_to) + "'" : "") +
            "?",
          cancel: true,
          persistent: true,
        })
        .onOk(() => {
          var url =
            "/api/run-control?name=" +
            control.control_name +
            "&date_from=" +
            this.toDateTimeString(control.date_from) +
            "&date_to=" +
            this.toDateTimeString(control.date_to);

          fetch(url, {
            method: "POST",
            headers: { Authorization: `Bearer ${this.$store.getters.getToken}`, "Content-Type": "application/json" },
          })
            .then((response) => {
              if (response.ok) {
                this.$q.notify({ type: "positive", message: "Control " + control.control_name + " queued for execution" });
                return response.json();
              } else {
                this.$q.notify({ type: "negative", message: "Control " + control.control_name + " failed" });
              }
            })
            .then(() => {
              this.$q.loadingBar.stop();
              this.refreshControlResults();
            });
        })
        .onCancel(() => {
          this.$q.notify({ message: "No action taken" });
          // console.log('Cancel')
        });
    },
    showCancelDialog(control) {
      this.$q
        .dialog({
          title: control.control_name,
          message: "Do you really want to stop the execution of this control?",
          cancel: true,
          persistent: true,
        })
        .onOk(() => {
          fetch("/api/cancel-control?id=" + control.process_id, {
            method: "POST",
            headers: { Authorization: `Bearer ${this.$store.getters.getToken}`, "Content-Type": "application/json" },
          })
            .then((response) => {
              if (response.ok) {
                this.$q.notify({ type: "positive", message: "Control run '" + control.control_name + " PID:" + control.process_id + "' was canceled" });
                control.status = "C";
              } else {
                this.$q.notify({ type: "negative", message: "Stopping control run '" + control.control_name + " PID:" + control.process_id + "' failed" });
              }
            })
            .then(() => {
              this.$q.loadingBar.stop();
            });
        })
        .onCancel(() => {
          this.$q.notify({ message: "No action taken" });
          // console.log('Cancel')
        });
    },
    showRevokeDialog(control) {
      this.$q
        .dialog({
          title: control.control_name,
          message: "Do you really want to revoke this control run?",
          cancel: true,
          persistent: true,
        })
        .onOk(() => {
          fetch("/api/revoke-control-run?id=" + control.process_id, {
            method: "DELETE",
            headers: { Authorization: `Bearer ${this.$store.getters.getToken}`, "Content-Type": "application/json" },
          })
            .then((response) => {
              if (response.ok) {
                this.$q.notify({ type: "positive", message: "Control run '" + control.control_name + " PID:" + control.process_id + "' was revoked" });
                control.status = "X";
              } else {
                this.$q.notify({ type: "negative", message: "Revoke of control run '" + control.control_name + " PID:" + control.process_id + "' failed" });
              }
            })
            .then(() => {
              this.$q.loadingBar.stop();
            });
        })
        .onCancel(() => {
          this.$q.notify({ message: "No action taken" });
          // console.log('Cancel')
        });
    },
    dropTemporaryTables(control) {
      this.$q
        .dialog({
          title: control.control_name,
          message: "Do you really want to drop all debug temporary tables for execution with PID: " + control.process_id + " ?",
          cancel: true,
          persistent: true,
        })
        .onOk(() => {
          fetch("/api/delete-control-temporary-tables?id=" + control.process_id, {
            method: "DELETE",
            headers: { Authorization: `Bearer ${this.$store.getters.getToken}`, "Content-Type": "application/json" },
          })
            .then((response) => {
              if (response.ok) {
                this.$q.notify({ type: "positive", message: "All temporary tables for PID:" + control.process_id + " were deleted" });
              } else {
                this.$q.notify({ type: "negative", message: "Temporary tables deletion for PID:" + control.process_id + "' failed" });
              }
            })
            .then(() => {
              this.$q.loadingBar.stop();
            });
        })
        .onCancel(() => {
          this.$q.notify({ message: "No action taken" });
          // console.log('Cancel')
        });
    },
    async refreshControlResults() {
      this.controlResults = await this.updateControlResults();
    },
    async startRefreshTimer() {
      this.refreshTimer = setInterval(this.refreshControlResults, 10000);
    },
    stopRefreshTimer() {
      clearInterval(this.refreshTimer);
    },
    clearFilters() {
      this.filter.control_name = null;
      this.filter.type = null;
      this.filter.status = [];
      this.sort.key = null;
      this.sort.dir = "asc";
      // this.updateSearch("");
    },
    setSort(key) {
      if (this.sort.key === key) {
        this.sort.dir = this.sort.dir === "asc" ? "desc" : "asc";
        return;
      }
      this.sort.key = key;
      this.sort.dir = "asc";
    },
    getSortValue(item) {
      const val = item[this.sort.key];
      if (this.sort.key === "start_date" || this.sort.key === "date_from" || this.sort.key === "date_to") {
        return val ? new Date(val).getTime() : null;
      }
      if (this.sort.key === "error_level_a" || this.sort.key === "error_level_b") {
        return this.parseNumericSortValue(val);
      }
      return val ?? null;
    },
  },
  computed: {
    ...mapGetters(["getSearch"]),
    sortedControlResults() {
      const dir = this.sort.dir === "asc" ? 1 : -1;
      return [...this.filteredControlResults].sort((a, b) => {
        const aVal = this.getSortValue(a);
        const bVal = this.getSortValue(b);

        if (aVal === bVal) return 0;
        if (aVal == null) return 1 * dir;
        if (bVal == null) return -1 * dir;

        if (typeof aVal === "number" && typeof bVal === "number") {
          return (aVal - bVal) * dir;
        }
        return String(aVal).localeCompare(String(bVal)) * dir;
      });
    },
    filteredControlResults() {
      const s = this.getSearch;
      var data = this.controlResults;
      data = this.controlResults.filter((item) => {
        const matchesSearch = s ? (item.control_name ? item.control_name.toUpperCase().includes(s.toUpperCase()) : false) : true;
        const matchesControlName = this.filter.control_name ? item.control_name.toUpperCase().includes(this.filter.control_name.toUpperCase()) : true;
        const matchesControlType = this.filter.type ? item.control_type === this.filter.type : true;
        const matchesStatus = this.filter.status && this.filter.status.length > 0 ? this.filter.status.includes(item.status) : true;

        return matchesSearch && matchesControlName && matchesControlType && matchesStatus;
      });
      return data;
    },
    filteredControlResultsLen() {
      return this.filteredControlResults.length;
    },
  },
  async mounted() {
    this.controlResults = await this.updateControlResults();
    this.startRefreshTimer();
  },
  unmounted() {
    this.stopRefreshTimer();
  },
};
</script>

<style lang="css" scoped>
/* Override the default link styles */
a {
  color: #009688;
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}

a:visited {
  color: #009688;
}

.new-day-separator {
  border-top: 2px solid #cfd8dc !important;
}

.sortable {
  cursor: pointer;
  user-select: none;
}
</style>
