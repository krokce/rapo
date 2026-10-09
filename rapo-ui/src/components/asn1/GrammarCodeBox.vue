<template>
  <div ref="editor" class="grammar-code" />
</template>

<script>
import { Dark } from "quasar";
import { EditorState, Compartment } from "@codemirror/state";
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter, placeholder } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { searchKeymap, highlightSelectionMatches } from "@codemirror/search";
import { StreamLanguage, syntaxHighlighting, defaultHighlightStyle } from "@codemirror/language";
import { asn1 } from "@codemirror/legacy-modes/mode/asn1";
import { darkExtensions } from "../../utils/codeTheme";

const ASN1 = StreamLanguage.define(asn1({}));

// An editable CodeMirror of one grammar file: ASN.1 highlighting (`language` asn1) or none (plain, a tag map). The
// view is built once and lives outside Vue's reactivity; a new `modelValue` from outside (another file) replaces the
// document, typing emits it.
export default {
  name: "GrammarCodeBox",
  props: {
    modelValue: { type: String, default: "" },
    language: { type: String, default: "asn1" },
    placeholderText: { type: String, default: "" },
    // Focus the editor once built (a new, empty file to paste into).
    autofocus: { type: Boolean, default: false },
  },
  emits: ["update:modelValue"],
  watch: {
    modelValue(value) {
      if (this.view && value !== this.view.state.doc.toString()) {
        this.view.dispatch({ changes: { from: 0, to: this.view.state.doc.length, insert: value || "" } });
      }
    },
    language() {
      if (this.view) {
        this.view.dispatch({ effects: this.languageSlot.reconfigure(this.languageExtension()) });
      }
    },
  },
  mounted() {
    this.languageSlot = new Compartment();
    const extensions = [
      lineNumbers(),
      highlightActiveLineGutter(),
      highlightActiveLine(),
      highlightSelectionMatches(),
      history(),
      keymap.of([indentWithTab, ...defaultKeymap, ...historyKeymap, ...searchKeymap]),
      placeholder(this.placeholderText),
      this.languageSlot.of(this.languageExtension()),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          this.$emit("update:modelValue", update.state.doc.toString());
        }
      }),
    ];
    if (Dark.isActive) {
      extensions.push(...darkExtensions);
    }
    this.view = new EditorView({ state: EditorState.create({ doc: this.modelValue || "", extensions }), parent: this.$refs.editor });
    if (this.autofocus) {
      this.view.focus();
    }
  },
  beforeUnmount() {
    if (this.view) {
      this.view.destroy();
      this.view = null;
    }
  },
  methods: {
    languageExtension() {
      return this.language === "asn1" ? [ASN1, syntaxHighlighting(defaultHighlightStyle, { fallback: true })] : [];
    },
    focus() {
      if (this.view) {
        this.view.focus();
      }
    },
    // Puts the cursor on a line (1-based) and scrolls to it.
    goToLine(line) {
      if (!this.view) {
        return;
      }
      const doc = this.view.state.doc;
      const target = doc.line(Math.min(Math.max(line, 1), doc.lines));
      this.view.dispatch({ selection: { anchor: target.from }, scrollIntoView: true });
      this.view.focus();
    },
  },
};
</script>

<style scoped>
.grammar-code {
  height: 100%;
}
.grammar-code :deep(.cm-editor) {
  height: 100%;
  border: 1px solid var(--rapo-code-border);
  border-radius: 0.25em;
}
.grammar-code :deep(.cm-editor.cm-focused) {
  outline: none;
  border-color: var(--rapo-teal);
}
.grammar-code :deep(.cm-content),
.grammar-code :deep(.cm-gutters) {
  font-size: 12px;
}
</style>
