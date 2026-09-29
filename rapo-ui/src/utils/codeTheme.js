import { EditorView } from "@codemirror/view";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { tags } from "@lezer/highlight";

// The dark theme of the SQL editors: colors of the editor, its gutter, the popups and the SQL syntax. The light theme is
// CodeMirror's default.
const darkTheme = EditorView.theme(
  {
    "&": { backgroundColor: "#1d1d1d", color: "#e0e0e0" },
    ".cm-content": { caretColor: "#e0e0e0" },
    ".cm-cursor, .cm-dropCursor": { borderLeftColor: "#e0e0e0" },
    "&.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection": { backgroundColor: "#37474f" },
    ".cm-gutters": { backgroundColor: "#242a2d", color: "#90a4ae", borderRightColor: "#555" },
    ".cm-tooltip": { backgroundColor: "#2b2b2b", color: "#e0e0e0", border: "1px solid #555" },
    ".cm-tooltip-autocomplete > ul > li[aria-selected]": { backgroundColor: "#37474f", color: "#ffffff" },
    ".cm-panels": { backgroundColor: "#2b2b2b", color: "#e0e0e0" },
    ".cm-searchMatch": { backgroundColor: "#5d4a12" },
  },
  { dark: true }
);

const darkHighlight = HighlightStyle.define([
  { tag: [tags.keyword, tags.standard(tags.name)], color: "#82aaff" },
  { tag: [tags.string, tags.special(tags.string)], color: "#c3e88d" },
  { tag: [tags.number, tags.bool, tags.null], color: "#f78c6c" },
  { tag: [tags.comment, tags.lineComment, tags.blockComment], color: "#8a9ba3", fontStyle: "italic" },
  { tag: [tags.typeName, tags.className], color: "#ffcb6b" },
  { tag: [tags.operator, tags.punctuation], color: "#89ddff" },
  { tag: [tags.function(tags.variableName), tags.propertyName], color: "#80cbc4" },
]);

export const darkExtensions = [darkTheme, syntaxHighlighting(darkHighlight)];
