<template>
  <q-btn
    v-if="status"
    :color="stopped ? 'green' : 'deep-orange'"
    :icon="stopped ? 'fas fa-play' : 'fas fa-stop'"
    :label="stopped ? 'Start scheduler' : 'Stop scheduler'"
    :disable="status.state === 'off' || busy"
    :loading="busy"
    no-caps
    unelevated
    @click="toggle">
    <q-tooltip v-if="status.state === 'off'">The scheduler is disabled for this server in rapo.ini or in development mode.</q-tooltip>
  </q-btn>
</template>

<script>
import { Dialog, Notify } from "quasar";
import { mapActions, mapState } from "vuex";
import { api, notifyError } from "../api";

// Stops or starts scheduling on all servers. The state is persisted, so it survives restarts.
// Runs already running or queued are not affected, and controls can still be run manually.
export default {
  data() {
    return { busy: false };
  },
  computed: {
    ...mapState({ status: "schedulerStatus" }),
    stopped() {
      return this.status.disabled;
    },
  },
  methods: {
    ...mapActions(["updateSchedulerStatus"]),
    toggle() {
      const stopping = !this.stopped;
      Dialog.create({
        title: stopping ? "Stop scheduler" : "Start scheduler",
        message: stopping
          ? "Scheduled controls will not run on any server until the scheduler is started again. Running and queued runs continue, and controls can still be run manually. Fires skipped meanwhile are not recorded as missed."
          : "Scheduled controls will run again from now on.",
        cancel: true,
        persistent: true,
      }).onOk(() => this.submit(stopping));
    },
    async submit(stopping) {
      this.busy = true;
      try {
        await api(stopping ? "scheduler-stop" : "scheduler-start", { method: "POST" });
        Notify.create({ type: "positive", message: stopping ? "Scheduler stopped" : "Scheduler started" });
      } catch (error) {
        notifyError(stopping ? "Failed to stop the scheduler." : "Failed to start the scheduler.", error);
      } finally {
        this.busy = false;
      }
      this.updateSchedulerStatus().catch((error) => notifyError("Failed to load scheduler status.", error));
    },
  },
};
</script>
