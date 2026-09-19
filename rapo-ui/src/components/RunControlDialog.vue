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
            @filter="filterControlCatalogue"
            v-model="run_control_name"
            :options="controlNameOptions"
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
import { mapActions, mapState } from "vuex";
import { api, notifyError } from "../api";
import { localDate } from "../utils/format";

// Run a control for a date or a date range. With a control_name prop it runs that control, otherwise the user
// picks one. `hook` is called after a successful start, otherwise the dialog navigates to the Results page.
export default {
  props: ["hook", "control_name"],
  data() {
    return {
      visible: false,
      range: false,
      debug_mode: false,
      selectDate: localDate(),
      controlFilter: "",
      run_control_name: this.control_name || "",
    };
  },
  computed: {
    ...mapState(["controlCatalogue"]),
    controlNameOptions() {
      const needle = this.controlFilter.toLowerCase();
      return this.controlCatalogue.map((control) => control.control_name).filter((name) => name.toLowerCase().includes(needle));
    },
  },
  methods: {
    ...mapActions(["updateControlCatalogue"]),
    filterControlCatalogue(val, update) {
      update(() => {
        this.controlFilter = val;
      });
    },
    rangeChange() {
      this.selectDate = this.range ? { from: localDate(-3), to: localDate(-2) } : localDate();
    },
    async runControl() {
      if (!this.run_control_name) {
        this.$q.notify({ type: "negative", message: "Please select a control to run" });
        return;
      }
      if (!this.selectDate) {
        this.$q.notify({ type: "negative", message: "Please select a date" });
        return;
      }

      const params = { name: this.run_control_name, debug_mode: this.debug_mode ? "true" : null };
      if (this.range) {
        // q-date returns a plain string when a single day is picked in range mode.
        const { from, to } = typeof this.selectDate === "string" ? { from: this.selectDate, to: this.selectDate } : this.selectDate;
        Object.assign(params, { date_from: from, date_to: to + "T23:59:59" });
      } else {
        params.date = this.selectDate;
      }

      try {
        await api("run-control", { method: "POST", params });
      } catch (error) {
        notifyError("Control " + this.run_control_name + " failed to start.", error);
        return;
      }
      this.$q.notify({ type: "positive", message: "Control " + this.run_control_name + " queued for execution" });
      if (this.hook) {
        this.hook();
        this.visible = false;
      } else {
        this.$router.push({ name: "results" });
      }
    },
    open() {
      this.visible = true;
    },
  },
  mounted() {
    if (!this.control_name) {
      this.updateControlCatalogue().catch((error) => notifyError("Failed to load controls.", error));
    }
  },
};
</script>
