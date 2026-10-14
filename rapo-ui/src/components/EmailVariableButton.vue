<template>
  <q-btn aria-label="Insert variable" flat dense size="sm" icon="fas fa-code" @click.stop>
    <q-tooltip>Insert variable</q-tooltip>
    <q-menu>
      <q-list dense>
        <q-item v-for="variable in variables" :key="variable.token" clickable v-close-popup @click="insert(variable.token)">
          <q-item-section>{{ variable.label }}</q-item-section>
          <q-item-section side class="text-mono">{{ variable.token }}</q-item-section>
        </q-item>
      </q-list>
    </q-menu>
  </q-btn>
</template>

<script>
// The {variables} menu of an email text input: inserts the token at the input's caret when it has the focus, else at
// the end, and emits the new text.
export default {
  props: {
    variables: { type: Array, required: true },
    // Gets the q-input it belongs to (refs are not reactive, so not the component itself); text is its current text.
    input: Function,
    text: String,
  },
  emits: ["update:text"],
  methods: {
    insert(token) {
      const field = this.input && this.input();
      const element = field && field.getNativeElement();
      const text = this.text || "";
      if (element && typeof element.selectionStart === "number" && document.activeElement === element) {
        const start = element.selectionStart;
        const end = element.selectionEnd;
        this.$emit("update:text", text.slice(0, start) + token + text.slice(end));
        this.$nextTick(() => element.setSelectionRange(start + token.length, start + token.length));
      } else {
        this.$emit("update:text", text + token);
      }
    },
  },
};
</script>
