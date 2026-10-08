import { Decoration, ViewPlugin, WidgetType } from "@codemirror/view";
import { RangeSetBuilder, StateEffect } from "@codemirror/state";
import { formatBytes } from "./format";

// The file viewer's columns and matches (FileViewerDialog). The lines of the editor are the rows the viewer loaded,
// one per line, so a decoration finds its row by the line number; only the visible lines are decorated.

export const DELIMITER_OPTIONS = [
  { label: "Auto", value: "auto" },
  { label: "Semicolon ;", value: ";" },
  { label: "Comma ,", value: "," },
  { label: "Pipe |", value: "|" },
  { label: "Tab", value: "\t" },
  { label: "None", value: "none" },
];
const CANDIDATES = [";", ",", "|", "\t"];
const COLORS = 8;
const SAMPLE_LINES = 50;

// The [start, end) of each field of a line. A field starting with a quote runs to the closing quote ("" inside is a
// quote), so a delimiter inside quotes does not split it.
export function splitFields(text, delimiter) {
  const fields = [];
  let start = 0;
  const length = text.length;
  while (start <= length) {
    let end;
    if (text[start] === '"') {
      let position = start + 1;
      for (;;) {
        const quote = text.indexOf('"', position);
        if (quote < 0) {
          position = length;
          break;
        }
        if (text[quote + 1] === '"') {
          position = quote + 2;
          continue;
        }
        position = quote + 1;
        break;
      }
      end = text.indexOf(delimiter, position);
    } else {
      end = text.indexOf(delimiter, start);
    }
    if (end < 0) {
      end = length;
    }
    fields.push([start, end]);
    start = end + delimiter.length;
    if (end === length) {
      break;
    }
  }
  return fields;
}

// The delimiter giving most of the first lines the same number of fields (more than one), or null: plain text.
export function detectDelimiter(lines) {
  const sample = lines.filter((line) => line).slice(0, SAMPLE_LINES);
  if (!sample.length) {
    return null;
  }
  let best = null;
  for (const delimiter of CANDIDATES) {
    const counts = new Map();
    for (const line of sample) {
      if (!line.includes(delimiter)) {
        continue;
      }
      const count = splitFields(line, delimiter).length;
      counts.set(count, (counts.get(count) || 0) + 1);
    }
    for (const [count, lines] of counts) {
      const share = lines / sample.length;
      if (count > 1 && share >= 0.8 && (!best || share > best.share || (share === best.share && count > best.count))) {
        best = { delimiter, share, count };
      }
    }
  }
  return best && best.delimiter;
}

export function delimiterLabel(delimiter) {
  const option = DELIMITER_OPTIONS.find((item) => item.value === delimiter);
  return option ? option.label : "None";
}

// Dispatched when what the decorations show changed without the text (delimiter, header, highlight).
export const refreshDecorations = StateEffect.define();

function changed(update) {
  return update.docChanged || update.viewportChanged || update.transactions.some((transaction) => transaction.effects.some((effect) => effect.is(refreshDecorations)));
}

function visibleLines(view, callback) {
  for (const { from, to } of view.visibleRanges) {
    for (let position = from; position <= to; ) {
      const line = view.state.doc.lineAt(position);
      callback(line);
      position = line.to + 1;
    }
  }
}

// Colors the fields of each line by their column; `source.delimiter()` is the delimiter or null, `source.header()`
// the field names of line 1 (shown on hover).
export function columnColors(source) {
  return ViewPlugin.fromClass(
    class {
      constructor(view) {
        this.decorations = this.build(view);
      }
      update(update) {
        if (changed(update)) {
          this.decorations = this.build(update.view);
        }
      }
      build(view) {
        const builder = new RangeSetBuilder();
        const delimiter = source.delimiter();
        if (!delimiter) {
          return builder.finish();
        }
        const header = source.header() || [];
        const marks = [];
        const mark = (index) =>
          marks[index] ||
          (marks[index] = Decoration.mark({
            class: `cm-csv-c${index % COLORS}`,
            attributes: { title: `Column ${index + 1}${header[index] ? `: ${header[index]}` : ""}` },
          }));
        const separator = Decoration.mark({ class: "cm-csv-sep" });
        visibleLines(view, (line) => {
          const fields = splitFields(line.text, delimiter);
          if (fields.length < 2) {
            return;
          }
          fields.forEach(([start, end], index) => {
            if (index > 0) {
              builder.add(line.from + start - delimiter.length, line.from + start, separator);
            }
            if (end > start) {
              builder.add(line.from + start, line.from + end, mark(index));
            }
          });
        });
        return builder.finish();
      }
    },
    { decorations: (plugin) => plugin.decorations },
  );
}

class CutWidget extends WidgetType {
  constructor(bytes) {
    super();
    this.bytes = bytes;
  }
  eq(other) {
    return other.bytes === this.bytes;
  }
  toDOM() {
    const span = document.createElement("span");
    span.className = "cm-viewer-cut";
    span.textContent = ` … ${formatBytes(this.bytes)} more`;
    span.title = "The line is longer than the viewer shows ([DATASOURCES] view_line_chars)";
    return span;
  }
}

// Marks the matches of each line: the row's `spans` (a search on the server), else those of `source.highlight()`, a
// RegExp (global) or null; and the end of a cut line.
export function matchMarks(source) {
  const match = Decoration.mark({ class: "cm-viewer-match" });
  return ViewPlugin.fromClass(
    class {
      constructor(view) {
        this.decorations = this.build(view);
      }
      update(update) {
        if (changed(update)) {
          this.decorations = this.build(update.view);
        }
      }
      build(view) {
        const builder = new RangeSetBuilder();
        const rows = source.rows();
        const highlight = source.highlight();
        visibleLines(view, (line) => {
          const row = rows[line.number - 1];
          if (!row) {
            return;
          }
          let spans = row.spans;
          if (!spans && highlight) {
            spans = [];
            highlight.lastIndex = 0;
            for (const found of line.text.matchAll(highlight)) {
              if (found[0].length) {
                spans.push([found.index, found.index + found[0].length]);
              }
            }
          }
          for (const [start, end] of spans || []) {
            const to = Math.min(end, line.length);
            if (to > start) {
              builder.add(line.from + start, line.from + to, match);
            }
          }
          if (row.cut) {
            builder.add(line.to, line.to, Decoration.widget({ widget: new CutWidget(row.cut), side: 1 }));
          }
        });
        return builder.finish();
      }
    },
    { decorations: (plugin) => plugin.decorations },
  );
}

// The search of the viewer as a RegExp for the lines already loaded, or null when the browser does not take it.
export function searchExpression(text, { regex, matchCase }) {
  if (!text) {
    return null;
  }
  try {
    return new RegExp(regex ? text : text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), matchCase ? "g" : "gi");
  } catch {
    return null;
  }
}
