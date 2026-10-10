<template>
  <div class="q-mb-md">
    <div class="row items-end">
      <h2 class="row title-baseline items-center no-wrap text-no-wrap q-gutter-md q-mb-none">
        <div>{{ title }}</div>
        <div v-if="subject" class="text-grey-7 page-subject">{{ subject }}</div>
      </h2>
      <q-space />
      <!-- The records of a file: the datasource, the file and its status in the file log. -->
      <div v-if="meta && meta.kind === 'file'" class="row items-center justify-end q-gutter-x-md text-blue-grey-8">
        <router-link class="control-link text-weight-bold" :to="{ name: 'edit-datasource', params: { id: meta.sourceid } }">
          {{ meta.sourcename }}
        </router-link>
        <router-link class="control-link text-mono" :to="{ name: 'files-log', params: { id: meta.sourceid }, query: fileLogQuery }">
          {{ meta.file_name }}
        </router-link>
        <div>
          File ID <strong>{{ meta.file_id }}</strong>
        </div>
        <q-chip>
          <q-avatar :icon="fileStatus(meta.status).icon" :color="fileStatus(meta.status).color" text-color="white" />
          {{ fileStatus(meta.status).label }}
        </q-chip>
        <slot />
        <q-btn aria-label="Copy a link to this view" flat dense round size="sm" color="grey-7" icon="fas fa-link" @click="$emit('copy-link')">
          <q-tooltip anchor="top middle" self="bottom middle">Copy a link to this view</q-tooltip>
        </q-btn>
      </div>
      <div v-else-if="meta" class="row items-center justify-end q-gutter-x-md text-blue-grey-8">
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
        <q-btn aria-label="Copy a link to this view" flat dense round size="sm" color="grey-7" icon="fas fa-link" @click="$emit('copy-link')">
          <q-tooltip anchor="top middle" self="bottom middle">Copy a link to this view</q-tooltip>
        </q-btn>
      </div>
    </div>
    <!-- The run's other datasets (or sides) with their counts; the one shown is ringed. -->
    <div v-if="shownOptions.length > 1" class="row items-center q-mt-sm">
      <q-chip
        v-for="option in shownOptions"
        :key="option.value"
        clickable
        class="q-ml-none q-mr-sm"
        :class="{ 'chip-selected': option.value === modelValue }"
        :aria-pressed="option.value === modelValue"
        @click="option.value !== modelValue && $emit('update:modelValue', option.value)">
        <q-avatar :icon="option.icon" :color="option.color" text-color="white" />
        <span class="text-weight-bold q-mr-xs">{{ option.text }}</span><template v-if="option.count">({{ option.count }})</template>
      </q-chip>
    </div>
  </div>
</template>

<script>
import { controlType, fileStatus, runStatus } from "../../constants";
import { toDateTimeString } from "../../utils/format";

// The header of the analysis pages: the title and what is analysed, the run's (or file's) facts with the page's own
// buttons (the default slot), and the run's datasets or sides as chips to switch between. `options` are
// [{value, text, count, icon, color, hidden}].
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
    shownOptions() {
      return this.options.filter((option) => !option.hidden || option.value === this.modelValue);
    },
    // The file log of the file's day, the file marked.
    fileLogQuery() {
      const day = this.meta.start_date ? String(this.meta.start_date).substring(0, 10) : null;
      return day ? { date: day, file: this.meta.file_id } : { file: this.meta.file_id };
    },
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
    fileStatus,
    runStatus,
  },
};
</script>

<style scoped>
.control-link {
  color: var(--rapo-teal);
  text-decoration: none;
}

.control-link:hover {
  text-decoration: underline;
}
</style>
