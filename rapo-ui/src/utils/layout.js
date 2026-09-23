import { Screen } from "quasar";

// q-page style-fn for a list page whose table scrolls by itself: the page takes exactly the viewport height below
// the header, less what App.vue puts around every page above and below it: the q-page padding (Quasar's
// q-layout-padding: 8px on xs, 16px on sm, 24px from md) and the q-ma-lg margin (24px). Screen is reactive, so
// the height follows a breakpoint change.
export function fillViewport(offset, height) {
  const padding = Screen.lt.sm ? 8 : Screen.lt.md ? 16 : 24;
  return { height: `${height - offset - 2 * (padding + 24)}px` };
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
