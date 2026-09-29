<template>
  <q-dialog v-model="visible">
    <q-card style="width: 700px; max-width: 95vw">
      <q-card-section class="row items-center q-py-sm">
        <div class="text-h6">Check {{ label.toLowerCase() }}</div>
        <q-space />
        <q-btn aria-label="Close" flat round icon="fas fa-times" v-close-popup />
      </q-card-section>
      <q-separator />
      <q-card-section class="q-gutter-y-md">
        <div class="row items-center no-wrap q-gutter-x-sm">
          <q-icon :name="state.icon" :color="state.color" size="18px" />
          <code class="mask">{{ mask }}</code>
        </div>
        <div :class="state.textClass">{{ state.text }}</div>
        <div v-if="summary" class="text-grey-8">In the saved directories: {{ summary }}</div>
        <q-input
          outlined
          type="textarea"
          autogrow
          autofocus
          v-model="samples"
          label="Sample file names, one per line"
          input-class="text-mono"
          input-style="min-height: 100px"
          @update:model-value="scheduleCheck" />
        <q-list v-if="result && !result.error && result.names.length" dense bordered separator class="rounded-borders">
          <q-item v-for="(item, index) in result.names" :key="index">
            <q-item-section avatar>
              <q-icon :name="item.matches ? 'fas fa-check' : 'fas fa-times'" :color="item.matches ? 'teal' : 'red-5'" size="16px" />
            </q-item-section>
            <q-item-section class="text-mono">{{ item.name }}</q-item-section>
            <q-item-section side>{{ item.matches ? "Matches" : "Does not match" }}</q-item-section>
          </q-item>
        </q-list>
      </q-card-section>
    </q-card>
  </q-dialog>
</template>

<script>
import { api, notifyError } from "../api";

const SAMPLES_KEY = "rapo_mask_samples";

// Checks a file name pattern of a datasource with the server's regular expressions (the ones its file scan uses) and
// tries it on sample names, each matched whole like PDI Core does. It needs no saved datasource. The samples are kept
// for the browser session, to try the next change of the pattern on them.
export default {
  name: "MaskCheckDialog",
  data() {
    return {
      visible: false,
      mask: "",
      label: "",
      summary: undefined,
      samples: "",
      result: null,
    };
  },
  computed: {
    names() {
      return this.samples
        .split("\n")
        .map((name) => name.trim())
        .filter(Boolean);
    },
    state() {
      if (!this.mask) {
        return { icon: "fas fa-circle", color: "grey-5", text: "No pattern", textClass: "text-grey-7" };
      }
      if (!this.result) {
        return { icon: "fas fa-circle", color: "grey-5", text: "Checking...", textClass: "text-grey-7" };
      }
      if (this.result.error) {
        return { icon: "fas fa-exclamation-circle", color: "red-5", text: `Not a valid regular expression: ${this.result.error}`, textClass: "text-negative" };
      }
      const matched = this.result.names.filter((item) => item.matches).length;
      return {
        icon: "fas fa-check-circle",
        color: "teal",
        text: this.result.names.length ? `A valid regular expression; matches ${matched} of ${this.result.names.length} sample name(s)` : "A valid regular expression",
        textClass: "text-teal-9",
      };
    },
  },
  methods: {
    open({ mask, label, summary }) {
      this.mask = mask || "";
      this.label = label;
      this.summary = summary;
      this.result = null;
      try {
        this.samples = sessionStorage.getItem(SAMPLES_KEY) || "";
      } catch (error) {
        this.samples = "";
      }
      this.visible = true;
      this.check();
    },
    scheduleCheck() {
      try {
        sessionStorage.setItem(SAMPLES_KEY, this.samples);
      } catch (error) {
        // Not kept, then.
      }
      clearTimeout(this.timer);
      this.timer = setTimeout(this.check, 300);
    },
    async check() {
      if (!this.mask) {
        return;
      }
      const request = (this.request = (this.request || 0) + 1);
      try {
        const result = await api("check-ds-mask", { params: { mask: this.mask, names: this.names }, loadingBar: false });
        if (request === this.request) {
          this.result = result;
        }
      } catch (error) {
        notifyError("Failed to check the pattern", error);
      }
    },
  },
};
</script>

<style scoped>
.mask {
  font-size: 15px;
  word-break: break-all;
}
</style>
