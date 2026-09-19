<template>
  <span @click="visible = true">
    <slot></slot>
  </span>

  <q-dialog v-model="visible">
    <q-card class="column my-card" style="width: 400px">
      <q-card-section class="col bg-blue-grey-2">
        <div class="row no-wrap items-center">
          <div v-if="control_name" class="text-h6 ellipsis">{{ control_name }}</div>

          <q-select
            v-if="!control_name"
            class="col"
            outlined
            use-input
            hide-selected
            fill-input
            input-debounce="0"
            emit-value
            map-options
            @filter="filterControlCatalogue"
            v-model="run_control_name"
            :options="controlCatalogueList.map((ctrl) => ({ label: ctrl.control_name, value: ctrl.control_name }))"
            :selected-value="controlCatalogueList[0]?.control_name"
            label="Select control to run"
            style="background-color: white">
          </q-select>
        </div>
      </q-card-section>

      <q-card-section class="column items-center">
        <div class="q-pa-md">
          Run for <span v-if="!range">date</span> <span v-else>range</span>:
          <p>{{ selectDate }}</p>

          <div class="row items-start">
            <q-date v-model="selectDate" :range="range" today-btn mask="YYYY-MM-DD" color="teal" flat />
          </div>

          <div class="column">
            <q-toggle label="Run for date range" color="teal" :false-value="false" :true-value="true" v-model="range" @update:model-value="rangeChange" />

            <q-toggle color="blue" label="Run in debug mode" v-model="debug_mode">
              <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]"> Leave RAPO_TEMP% tables after execution </q-tooltip>
            </q-toggle>
          </div>
        </div>
      </q-card-section>

      <q-separator />

      <q-card-actions align="right">
        <q-btn v-close-popup="-1" flat color="primary" label="Run" icon="fas fa-play" @click="runControl" />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script>
import { mapActions } from "vuex";
import { useQuasar } from "quasar";
import { localDate } from "../utils/format";

export default {
  props: ["hook", "control_name"],
  data() {
    return {
      visible: false,
      range: false,
      debug_mode: false,
      selectDate: localDate(),
      controlCatalogueList: [],
      controlCatalogue: [],
      run_control_name: "",
      $q: useQuasar(),
    };
  },
  methods: {
    ...mapActions(["updateControlCatalogue"]),
    filterControlCatalogue(val, update, abort) {
      if (val.length < 0) {
        abort();
        return;
      }

      update(() => {
        const needle = val.toLowerCase();
        this.controlCatalogueList = this.controlCatalogue.filter((v) => v.control_name.toLowerCase().indexOf(needle) > -1);
      });
    },
    rangeChange() {
      this.selectDate = this.range ? { from: localDate(-3), to: localDate(-2) } : localDate();
    },
    runControl() {
      if (!this.run_control_name) {
        this.$q.notify({ type: "negative", message: "Please select a control to run" });
        return;
      }
      if (!this.selectDate) {
        this.$q.notify({ type: "negative", message: "Please select a date" });
        return;
      }
      this.$q.loadingBar.start();

      // In range mode q-date returns a plain string when a single day is picked.
      const params = new URLSearchParams({ name: this.run_control_name });
      if (this.range) {
        const { from, to } = typeof this.selectDate === "string" ? { from: this.selectDate, to: this.selectDate } : this.selectDate;
        params.set("date_from", from);
        params.set("date_to", to + "T23:59:59");
      } else {
        params.set("date", this.selectDate);
      }
      if (this.debug_mode) {
        params.set("debug_mode", "true");
      }

      fetch("/api/run-control?" + params, {
        method: "POST",
        headers: { Authorization: `Bearer ${this.$store.getters.getToken}` },
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error(response.status + " " + response.statusText);
          }
          this.$q.notify({ type: "positive", message: "Control " + this.run_control_name + " queued for execution" });
          if (this.hook) {
            this.hook();
            this.visible = false;
          } else {
            this.$router.push({ name: "results" });
          }
        })
        .catch((error) => {
          this.$q.notify({ type: "negative", message: "Control " + this.run_control_name + " failed to start. " + error.message });
        })
        .finally(() => {
          this.$q.loadingBar.stop();
        });
    },
    open() {
      // Logic to display the dialog
      this.visible = true;
    },
  },
  async mounted() {
    if (!this.control_name) {
      this.controlCatalogue = await this.updateControlCatalogue();
      this.controlCatalogueList = this.controlCatalogue;
    } else {
      this.run_control_name = this.control_name;
    }
  },
};
</script>
