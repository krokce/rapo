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

// "rgb(r, g, b)", "rgba(...)" or "#rrggbb" as [r, g, b], else null.
function channels(color) {
  const rgb = /rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)/.exec(color || "");
  if (rgb) {
    return rgb.slice(1, 4).map(Number);
  }
  const hex = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(color || "");
  return hex ? hex.slice(1, 4).map((value) => parseInt(value, 16)) : null;
}

function luminance([r, g, b]) {
  const linear = (value) => {
    const c = value / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b);
}

function contrast(a, b) {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}

// Whether --rapo-on-strong (white) reads better than --rapo-header-text on `color` painted at `alpha` over the page's
// surface: decided by the blended color, since a light hue (amber) stays light however strong.
export function prefersStrongText(color, alpha = 1) {
  const fill = channels(color);
  const surface = channels(tokenColor("rapo-surface"));
  if (!fill || !surface) {
    return alpha >= 0.55;
  }
  const blended = fill.map((value, index) => Math.round(value * alpha + surface[index] * (1 - alpha)));
  return contrast(blended, channels(tokenColor("rapo-on-strong")) || [255, 255, 255]) > contrast(blended, channels(tokenColor("rapo-header-text")) || [38, 50, 56]);
}
