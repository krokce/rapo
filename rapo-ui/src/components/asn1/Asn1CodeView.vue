<template>
  <div ref="editor" class="asn1-code" />
</template>

<script>
import { Dark } from "quasar";
import { EditorState } from "@codemirror/state";
import { EditorView, lineNumbers } from "@codemirror/view";
import { xml } from "@codemirror/lang-xml";
import { syntaxHighlighting, defaultHighlightStyle } from "@codemirror/language";
import { darkExtensions } from "../../utils/codeTheme";

// A read-only CodeMirror of the XML or Text rendering of a node's subtree. The view is built once and its document
// replaced; it lives outside Vue's reactivity.
export default {
  name: "Asn1CodeView",
  props: {
    text: { type: String, default: "" },
    language: { type: String, default: "text" },
  },
  watch: {
    text() {
      this.build();
    },
    language() {
      this.build();
    },
  },
  mounted() {
    this.build();
  },
  beforeUnmount() {
    if (this.view) {
      this.view.destroy();
      this.view = null;
    }
  },
  methods: {
    build() {
      const extensions = [lineNumbers(), EditorState.readOnly.of(true), EditorView.editable.of(false)];
      if (this.language === "xml") {
        extensions.push(xml(), syntaxHighlighting(defaultHighlightStyle, { fallback: true }));
      }
      if (Dark.isActive) {
        extensions.push(...darkExtensions);
      }
      const state = EditorState.create({ doc: this.text, extensions });
      if (this.view) {
        this.view.setState(state);
      } else {
        this.view = new EditorView({ state, parent: this.$refs.editor });
      }
    },
  },
};
</script>

<style scoped>
.asn1-code {
  height: 100%;
}
.asn1-code :deep(.cm-editor) {
  height: 100%;
}
.asn1-code :deep(.cm-editor.cm-focused) {
  outline: none;
}
.asn1-code :deep(.cm-content),
.asn1-code :deep(.cm-gutters) {
  font-size: 12px;
}
</style>
