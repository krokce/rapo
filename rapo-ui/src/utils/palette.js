// The colors of the app for ECharts, which cannot read CSS: a Quasar palette color as the chips' avatars paint it
// (bg-<name>), and the --rapo-* tokens, each resolved once per theme (light or dark) and kept.
import { Dark } from "quasar";

const cache = new Map();

// The background of bg-<name>, e.g. "teal-8" as a REC chip's avatar shows it.
export function paletteColor(name) {
  if (!name) {
    return null;
  }
  const key = `${Dark.isActive ? "dark" : "light"}:${name}`;
  if (!cache.has(key)) {
    const element = document.createElement("div");
    element.className = `bg-${name} invisible fixed no-pointer-events`;
    document.body.appendChild(element);
    const color = getComputedStyle(element).backgroundColor;
    element.remove();
    cache.set(key, color && color !== "rgba(0, 0, 0, 0)" ? color : "#90a4ae");
  }
  return cache.get(key);
}

// A --rapo-* token of the current theme (styles/app.sass, redefined for the dark body).
export function tokenColor(name) {
  const key = `${Dark.isActive ? "dark" : "light"}:--${name}`;
  if (!cache.has(key)) {
    cache.set(key, getComputedStyle(document.body).getPropertyValue(`--${name}`).trim() || "#90a4ae");
  }
  return cache.get(key);
}
