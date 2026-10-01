<template>
  <div class="row items-end q-mb-md">
    <h2 class="row title-baseline items-center no-wrap text-no-wrap q-gutter-md q-mb-none">
      <div>{{ title }}</div>
      <div v-if="!options.length" class="text-grey-7 page-subject">{{ subject }}</div>
      <div v-if="options.length">
        <q-btn-toggle
          :model-value="modelValue"
          no-caps
          unelevated
          toggle-color="blue-grey-7"
          color="grey-3"
          text-color="grey-8"
          :options="options"
          @update:model-value="(value) => $emit('update:modelValue', value)">
          <template v-for="option in options" :key="option.value" #[option.slot]>
            {{ option.text }}<span v-if="option.count" class="dataset-count">({{ option.count }})</span>
          </template>
        </q-btn-toggle>
      </div>
    </h2>
    <q-space />
    <div v-if="meta" class="row items-center justify-end q-gutter-x-md text-blue-grey-8">
      <q-chip>
        <q-avatar :icon="controlType(meta.control_type).icon" :color="controlType(meta.control_type).color" text-color="white" />
        {{ meta.control_type }}
        <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">{{ controlType(meta.control_type).label }}</q-tooltip>
      </q-chip>
      <router-link class="control-link text-weight-bold" :to="{ name: 'edit-control', params: { controlId: meta.control_id } }">
        {{ meta.control_name }}
      </router-link>
      <div>
        PID <strong>{{ meta.process_id }}</strong>
      </div>
      <div>
        {{ windowText }}
      </div>
      <q-chip>
        <q-avatar :icon="runStatus(meta.status).icon" :color="runStatus(meta.status).color" text-color="white" />
        {{ runStatus(meta.status).label }}
      </q-chip>
      <slot />
      <q-btn aria-label="Copy a link to this view" flat dense round size="sm" color="blue-grey-7" icon="fas fa-link" @click="$emit('copy-link')">
        <q-tooltip anchor="top middle" self="bottom middle">Copy a link to this view</q-tooltip>
      </q-btn>
    </div>
  </div>
</template>

<script>
import { controlType, runStatus } from "../../constants";
import { toDateTimeString } from "../../utils/format";

// The header of the analysis pages: the title with the switch between the run's datasets (or sides), and the run's
// facts. `options` are q-btn-toggle options, each drawn by its `slot` so the count can be in normal weight.
export default {
  name: "AnalysisHeader",
  props: {
    title: { type: String, required: true },
    subject: { type: String, default: "" },
    options: { type: Array, default: () => [] },
    modelValue: { type: String, default: null },
    meta: { type: Object, default: null },
  },
  emits: ["update:modelValue", "copy-link"],
  computed: {
    windowText() {
      if (!this.meta) {
        return "";
      }
      const from = toDateTimeString(this.meta.date_from);
      const to = toDateTimeString(this.meta.date_to);
      return from.substring(0, 10) === to.substring(0, 10) && from.endsWith("00:00:00") && to.endsWith("23:59:59") ? from.substring(0, 10) : `${from} – ${to}`;
    },
  },
  methods: {
    controlType,
    runStatus,
  },
};
</script>

<style scoped>
.dataset-count {
  font-weight: 400;
  margin-left: 4px;
}

.control-link {
  color: var(--rapo-teal);
  text-decoration: none;
}

.control-link:hover {
  text-decoration: underline;
}
</style>
