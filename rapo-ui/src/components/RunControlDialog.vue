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

            <q-toggle v-if="iterationCount" color="teal" :label="`Run ${iterationCount} iteration${iterationCount > 1 ? 's' : ''}`" v-model="iterations">
              <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]"> Also run the control for the periods of its iteration configuration </q-tooltip>
            </q-toggle>
          </div>

          <div v-if="iterations" class="q-mt-sm text-caption text-grey-8">
            <div v-if="!iterationPreview.length">Loading iteration dates...</div>
            <div v-for="item in iterationPreview" :key="item.iteration_id">
              {{ item.iteration_description || "Iteration #" + item.iteration_id }}:
              {{ previewDates(item) }}
            </div>
          </div>
        </div>
      </q-card-section>

      <q-separator />

      <q-card-section v-if="cascadeNote" class="text-caption text-grey-8">
        <q-icon name="fas fa-diagram-project" class="q-mr-xs" />{{ cascadeNote }}
      </q-card-section>

      <q-card-actions align="right">
        <q-btn v-close-popup="-1" flat color="primary" label="Run" icon="fas fa-play" @click="runControl" />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script>
import { mapActions, mapState } from "vuex";
import { api, notifyError } from "../api";
import { cascadeMessage, chainOf } from "../utils/schedule";
import { localDate, toDateString } from "../utils/format";

// Run a control for a date or a date range. With a control_name prop it runs that control, otherwise the user
// picks one. `hook` is called after a successful start, otherwise the dialog navigates to the Results page.
export default {
  props: ["hook", "control_name"],
  data() {
    return {
      visible: false,
      range: false,
      debug_mode: false,
      iterations: false,
      iterationPreview: [],
      previewTimer: null,
      selectDate: localDate(),
      controlFilter: "",
      run_control_name: this.control_name || "",
    };
  },
  computed: {
    ...mapState(["controlCatalogue"]),
    chain() {
      return chainOf(this.run_control_name, this.controlCatalogue);
    },
    // A run always cascades into the controls following it, so the dialog names them.
    cascadeNote() {
      return cascadeMessage(this.chain.cascade);
    },
    iterationCount() {
      return this.chain.iterations;
    },
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
    // The window of the run, in the shape run-control and iteration-preview both take.
    dateParams() {
      if (!this.range) {
        return { date: this.selectDate };
      }
      // q-date returns a plain string when a single day is picked in range mode.
      const { from, to } = typeof this.selectDate === "string" ? { from: this.selectDate, to: this.selectDate } : this.selectDate;
      return { date_from: from, date_to: to + "T23:59:59" };
    },
    previewDates(item) {
      const from = toDateString(item.date_from);
      const to = toDateString(item.date_to);
      return from === to ? from : `${from} - ${to}`;
    },
    // The engine computes the iteration windows, so what is offered is what the run performs.
    schedulePreviewFetch() {
      clearTimeout(this.previewTimer);
      if (!this.iterations || !this.run_control_name || !this.selectDate) {
        this.iterationPreview = [];
        return;
      }
      this.previewTimer = setTimeout(async () => {
        const params = { name: this.run_control_name, ...this.dateParams() };
        try {
          this.iterationPreview = await api("iteration-preview", { params, loadingBar: false });
        } catch (error) {
          this.iterationPreview = [];
        }
      }, 300);
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

      const params = {
        name: this.run_control_name,
        debug_mode: this.debug_mode ? "true" : null,
        iterations: this.iterations ? "true" : null,
        ...this.dateParams(),
      };

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
  watch: {
    // The catalogue holds the control list and the chain configuration. It is loaded when the dialog
    // is opened, not on mount, because the results table mounts one of these per row.
    visible(opened) {
      if (opened && !this.controlCatalogue.length) {
        this.updateControlCatalogue().catch((error) => notifyError("Failed to load controls.", error));
      }
    },
    iterations: "schedulePreviewFetch",
    selectDate: "schedulePreviewFetch",
    range: "schedulePreviewFetch",
    run_control_name() {
      this.iterations = false;
      this.iterationPreview = [];
    },
  },
  unmounted() {
    clearTimeout(this.previewTimer);
  },
};
</script>
