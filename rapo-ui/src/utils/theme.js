// The color theme: "auto" follows the operating system, "light" and "dark" force it. Remembered by the browser.
import { Dark } from "quasar";

const THEME_KEY = "rapo_theme";
export const THEMES = ["auto", "light", "dark"];

export function readTheme() {
  try {
    const theme = localStorage.getItem(THEME_KEY);
    return THEMES.includes(theme) ? theme : "auto";
  } catch (error) {
    return "auto";
  }
}

export function applyTheme(theme) {
  Dark.set(theme === "auto" ? "auto" : theme === "dark");
}

export function saveTheme(theme) {
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch (error) {
    // The choice then lasts until the page is closed.
  }
}
