<template>
  <div v-if="error" class="state-notice state-notice--error">
    <q-icon name="fas fa-exclamation-triangle" />
    <div>This section could not be loaded: {{ error }}</div>
    <q-btn flat dense no-caps color="primary" label="Retry" @click="$emit('retry')" />
  </div>
</template>

<script>
// A section of an analysis page that could not be loaded, with Retry.
export default {
  name: "SectionError",
  props: {
    error: { type: String, default: "" },
  },
  emits: ["retry"],
};
</script>
