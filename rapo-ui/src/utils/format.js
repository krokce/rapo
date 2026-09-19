import { date } from "quasar";

// Escape text before passing it to a Quasar dialog with html: true.
export function escapeHtml(value) {
  return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// Local calendar date as YYYY-MM-DD, shifted by offsetDays (toISOString would give the UTC date).
export function localDate(offsetDays = 0) {
  return date.formatDate(date.addToDate(new Date(), { days: offsetDays }), "YYYY-MM-DD");
}
