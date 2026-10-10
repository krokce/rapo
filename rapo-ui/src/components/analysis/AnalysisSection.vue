<template>
  <section :id="id" class="analysis-section">
    <div class="row items-center q-mb-sm section-head">
      <q-icon v-if="icon" :name="icon" size="15px" class="q-mr-sm section-icon" />
      <div class="text-subtitle1 text-weight-medium text-blue-grey-9">{{ title }}</div>
      <div v-if="$slots.facts" class="row items-center q-ml-md text-grey-7 section-facts">
        <slot name="facts" />
      </div>
      <q-space />
      <slot name="actions" />
    </div>
    <slot />
  </section>
</template>

<script>
// One section of an analysis page: its title (the rail names it the same), facts beside it, actions on the right.
// AnalysisLayout finds the sections by their class and `id`.
export default {
  name: "AnalysisSection",
  props: {
    id: { type: String, required: true },
    title: { type: String, required: true },
    icon: { type: String, default: null },
  },
};
</script>

<style scoped>
.analysis-section {
  margin-bottom: 32px;
  /* Below the fixed header when a link scrolls the section to the top. */
  scroll-margin-top: 76px;
}

.section-head {
  min-height: 32px;
}

.section-icon {
  color: var(--rapo-label);
}

.section-facts {
  font-size: 13px;
}
</style>
