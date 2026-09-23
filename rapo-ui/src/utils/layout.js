import { Screen } from "quasar";

// Quasar's q-layout-padding, which App.vue puts around every page: 8px on xs, 16px up to lg, 24px from lg.
function layoutPadding() {
  return Screen.lt.sm ? 8 : Screen.lt.lg ? 16 : 24;
}

// q-page style-fn for a list page whose table scrolls by itself: the page takes exactly the viewport height below
// the header, less what App.vue puts around every page above and below it: the q-page padding (layoutPadding) and
// the q-ma-lg margin (24px). Screen is reactive, so the height follows a breakpoint change.
export function fillViewport(offset, height) {
  return { height: `${height - offset - 2 * (layoutPadding() + 24)}px` };
}

// The same for a page whose table may run to the bottom edge of the window: only the spacing above the page is
// subtracted, and a negative bottom margin cancels the padding and margin App.vue puts below it. The table is still
// as tall as its rows, so it reaches the edge only when it has enough of them.
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
