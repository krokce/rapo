import { Screen } from "quasar";

// Quasar's q-layout-padding, which App.vue puts around every page: 8px on xs, 16px up to lg, 24px from lg.
function layoutPadding() {
  return Screen.lt.sm ? 8 : Screen.lt.lg ? 16 : 24;
}

// q-page style-fn for a list page whose table scrolls by itself and may run to the bottom edge of the window. App.vue
// puts the q-page padding (layoutPadding) and a q-ma-lg margin (24px) around every page: only the spacing above the
// page is subtracted, and a negative bottom margin cancels the spacing below it. The table is still as tall as its
// rows, so it reaches the edge only when it has enough of them.
export function fillViewportToBottom(offset, height) {
  const spacing = layoutPadding() + 24;
  return { height: `${height - offset - spacing}px`, marginBottom: `-${spacing}px` };
}

let measureContext = null;

// Width in px of the widest of the texts in the given CSS font, for sizing a fixed-layout column to its content.
export function textWidth(texts, font) {
  measureContext = measureContext || document.createElement("canvas").getContext("2d");
  measureContext.font = font;
  let width = 0;
  new Set(texts).forEach((text) => (width = Math.max(width, measureContext.measureText(text || "").width)));
  return Math.ceil(width);
}
