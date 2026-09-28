<template>
  <div class="q-gutter-y-sm">
    <div v-for="(part, index) in parts" :key="index" class="row items-center no-wrap q-gutter-x-sm">
      <q-input
        class="directory-input"
        outlined
        :model-value="part"
        :label="index === 0 ? label : `Another ${label.toLowerCase()}`"
        placeholder="/data_in/SOURCE"
        :rules="[(value) => isAbsolute(value) || 'An absolute path, starting with /']"
        lazy-rules
        hide-bottom-space
        @update:model-value="(value) => setPart(index, value)">
        <template #prepend>
          <q-icon
            :name="stateOf(part).icon"
            :color="stateOf(part).color"
            :class="{ 'cursor-pointer': stateOf(part).attention }"
            @click.stop.prevent="stateOf(part).attention && $emit('attention')">
            <q-tooltip anchor="top left" self="bottom left" :offset="[0, 5]">{{ stateOf(part).text }}</q-tooltip>
          </q-icon>
        </template>
      </q-input>
      <!-- Both slots are always there, so a row keeps its width whichever buttons it shows. -->
      <template v-if="multiple">
        <div class="part-slot">
          <q-btn size="sm" color="primary" flat round v-if="parts.length > 1" icon="fas fa-minus" @click="removePart(index)">
            <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 5]">Remove this directory</q-tooltip>
          </q-btn>
        </div>
        <div class="part-slot">
          <q-btn size="sm" color="primary" flat round icon="fas fa-plus" v-if="index === parts.length - 1" @click="addPart">
            <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 5]">Add a directory: PDI Core scans every directory of the list</q-tooltip>
          </q-btn>
        </div>
      </template>
    </div>
  </div>
</template>

<script>
import { splitDirectories } from "../utils/datasources";

// One directory column of a datasource, edited in place in the parent's object (modelValue[field]). With multiple, it
// is INPUT_DIRECTORY: a list of paths PDI Core separates by "|", one input each. Each path shows whether it exists on
// this server, as the saved datasource's check found it (states, from get-ds-config); a path not saved yet is unknown.
export default {
  name: "DirectoryListBox",
  props: {
    modelValue: { type: Object, required: true },
    field: { type: String, required: true },
    label: { type: String, required: true },
    multiple: { type: Boolean, default: false },
    // [{field, path, exists, writable}] of the saved datasource.
    states: { type: Array, default: () => [] },
  },
  emits: ["attention"],
  data() {
    return {
      // The paths as typed, blank ones included, so a new line doesn't vanish before it is filled.
      parts: this.split(),
    };
  },
  computed: {
    datasource() {
      return this.modelValue;
    },
  },
  watch: {
    // Another datasource (a reload, a version): the paths follow.
    modelValue() {
      this.parts = this.split();
    },
  },
  created() {
    // A change from outside the box (not typed here), e.g. a version loaded into the same object.
    this.$watch(
      () => this.modelValue[this.field],
      (value) => {
        if (value !== this.joined()) {
          this.parts = this.split();
        }
      }
    );
  },
  methods: {
    split() {
      const value = this.modelValue[this.field];
      const parts = this.multiple ? splitDirectories(value) : [String(value || "").trim()];
      return parts.length ? parts : [""];
    },
    joined() {
      return this.parts
        .map((part) => part.trim())
        .filter(Boolean)
        .join("|");
    },
    setPart(index, value) {
      this.parts[index] = value || "";
      this.datasource[this.field] = this.joined();
    },
    addPart() {
      this.parts.push("");
    },
    removePart(index) {
      this.parts.splice(index, 1);
      this.datasource[this.field] = this.joined();
    },
    isAbsolute(value) {
      return !value || String(value).trim().startsWith("/");
    },
    stateOf(part) {
      const path = (part || "").trim();
      if (!path) {
        return { icon: "fas fa-folder", color: "grey-5", text: "No directory" };
      }
      const state = this.states.find((item) => item.field === this.field && item.path === path);
      if (!state) {
        return { icon: "fas fa-folder", color: "grey-5", text: "Not saved yet, or not checked yet: whether it exists is checked after a save" };
      }
      if (state.exists === null) {
        return { icon: "fas fa-question-circle", color: "grey-6", text: "Unknown: checking it took longer than 5 s (a slow or hung network file system?)" };
      }
      if (!state.exists) {
        return { icon: "fas fa-folder-minus", color: "red-5", text: "Does not exist on this server. Create it on Need attention.", attention: true };
      }
      if (!state.writable) {
        return { icon: "fas fa-folder", color: "orange-8", text: "Exists, but rapo may not write in it; PDI Core's user needs read and write access. See Need attention.", attention: true };
      }
      return { icon: "fas fa-folder-open", color: "teal", text: "Exists on this server" };
    },
  },
};
</script>

<style scoped>
.directory-input {
  width: 600px;
  max-width: 100%;
  flex: 0 1 auto;
}
.part-slot {
  width: 32px;
  flex: none;
}
</style>
