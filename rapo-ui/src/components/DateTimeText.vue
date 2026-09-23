<template>
  <span v-if="value" class="text-blue-grey-7">
    <strong>{{ toDateString(value) }}</strong>
    <small class="text-grey-7 q-px-sm">{{ toTimeString(value) }}</small>
  </span>
</template>

<script>
import { toDateString, toTimeString } from "../utils/format";

// A date-time as a bold date and a small grey time, the way list tables show it.
export default {
  props: {
    value: { type: String, default: null },
  },
  methods: {
    toDateString,
    toTimeString,
  },
};
</script>
