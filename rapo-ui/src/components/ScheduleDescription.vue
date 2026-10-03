<template>
  <div class="schedule-description">
    <div class="description-text ellipsis" :class="{ 'text-grey-7': dim }">
      <template v-for="(part, index) in parts" :key="index">
        <router-link
          v-if="part.control && controlIds.has(part.control)"
          :to="{ name: 'edit-control', params: { controlId: controlIds.get(part.control) }, query: { tab: 'scheduler' } }"
          class="control-link"
          :title="`Open ${part.control}`"
          @click.stop>
          {{ part.control }}
        </router-link>
        <template v-else>{{ part.text ?? part.control }}</template>
      </template>
    </div>
    <div v-if="hasRhythm || window" class="details row no-wrap items-center">
      <schedule-rhythm :schedule-config="scheduleConfig" :color="color" />
      <span v-if="window" class="window-chip" :title="windowTitle"><q-icon name="fas fa-history" size="9px" /> {{ window }}</span>
    </div>
  </div>
</template>

<script>
import { mapGetters } from "vuex";
import ScheduleRhythm from "./ScheduleRhythm.vue";
import { scheduleFrequency, scheduleParts, scheduleRhythm, windowLabel } from "../utils/schedule";

// A schedule in words, then the strip of where its fires fall and the data window of a run. Lines 2 and 3 of
// ScheduleSummary; the control editor shows it live under the schedule fields.
export default {
  components: { ScheduleRhythm },
  props: {
    scheduleConfig: { type: String, default: null },
    // The name of the control a cascade follows.
    triggerName: { type: String, default: null },
    // Controls that pull this one while it has no schedule of its own; shown instead of "Not scheduled".
    pulledBy: { type: Array, default: () => [] },
    periodBack: { type: [Number, String], default: null },
    periodNumber: { type: [Number, String], default: null },
    periodType: { type: String, default: null },
    color: { type: String, default: "grey-6" },
    dim: { type: Boolean, default: false },
  },
  computed: {
    hasRhythm() {
      return !!scheduleRhythm(this.scheduleConfig);
    },
    ...mapGetters({ controlIds: "controlIdsByName" }),
    // The sentence, the controls it names (the trigger of a cascade, the controls pulling it) linking to their editor.
    parts() {
      return scheduleParts(this.scheduleConfig, this.triggerName, this.pulledBy);
    },
    window() {
      return windowLabel(this.periodBack, this.periodNumber, this.periodType);
    },
    windowTitle() {
      const periods = `periods back ${this.periodBack ?? 0}, number of periods ${this.periodNumber ?? 1}, period type ${this.periodType}`;
      if (scheduleFrequency(this.scheduleConfig) === "cascade") {
        const trigger = this.triggerName || "the control it follows";
        return `Data window of a scheduled cascade: counted back from the fire time of ${trigger} by this control's own periods (${periods}). When ${trigger} runs manually, its dates are used instead.`;
      }
      return `Data window of a run: ${periods}`;
    },
  },
};
</script>

<style scoped>
.schedule-description {
  font-size: 12px;
  line-height: 16px;
  min-width: 0;
}
.control-link {
  color: inherit;
  text-decoration: none;
  font-weight: 500;
}
.control-link:hover {
  text-decoration: underline;
}
.details {
  gap: 6px;
  margin-top: 2px;
}
.window-chip {
  flex: none;
  padding: 0 5px;
  border-radius: 8px;
  font-size: 11px;
  color: var(--rapo-muted);
  background: var(--rapo-surface-alt);
  border: 1px solid var(--rapo-border-soft);
  white-space: nowrap;
}
</style>
