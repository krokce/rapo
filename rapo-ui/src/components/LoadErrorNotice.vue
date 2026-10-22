<template>
  <div class="state-notice state-notice--error">
    <q-icon name="fas fa-exclamation-triangle" />
    <div>{{ message }}</div>
    <q-btn flat dense no-caps color="primary" label="Retry" @click="$emit('retry')" />
  </div>
</template>

<script>
// A failed load inside a panel or table, in place of its skeleton or empty text, with a Retry.
export default {
  props: {
    message: { type: String, required: true },
  },
  emits: ["retry"],
};
</script>
