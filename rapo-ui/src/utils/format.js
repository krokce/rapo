import { date } from "quasar";

// Escape text before passing it to a Quasar dialog with html: true.
export function escapeHtml(value) {
  return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// Local calendar date as YYYY-MM-DD, shifted by offsetDays (toISOString would give the UTC date).
export function localDate(offsetDays = 0) {
  return date.formatDate(date.addToDate(new Date(), { days: offsetDays }), "YYYY-MM-DD");
}

// The API sends datetimes as naive ISO strings (2026-09-19T10:05:07); these slice them for display.
export function toDateString(value) {
  return value ? String(value).substring(0, 10) : "";
}

export function toTimeString(value) {
  return value ? String(value).substring(11, 19) : "";
}

export function toDateTimeString(value) {
  return value ? String(value).substring(0, 19).replace("T", " ") : "";
}

export function round(value, places) {
  return Math.round(value * Math.pow(10, places)) / Math.pow(10, places);
}

export function formatNumber(value, decimals = 0) {
  return Number(value).toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

// navigator.clipboard needs a secure context, which a plain-http intranet server isn't, so fall back to execCommand.
export async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  document.body.appendChild(textarea);
  textarea.select();
  try {
    if (!document.execCommand("copy")) {
      throw new Error("Copy command was rejected");
    }
  } finally {
    document.body.removeChild(textarea);
  }
}
