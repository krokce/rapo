import { date } from "quasar";

// Escape text before passing it to a Quasar dialog with html: true.
export function escapeHtml(value) {
  return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// Local calendar date as YYYY-MM-DD, shifted by offsetDays (toISOString would give the UTC date).
export function localDate(offsetDays = 0) {
  return date.formatDate(date.addToDate(new Date(), { days: offsetDays }), "YYYY-MM-DD");
}

// A YYYY-MM-DD day moved by `days`; null for no day.
export function shiftDay(day, days) {
  return day ? date.formatDate(date.addToDate(date.extractDate(day, "YYYY-MM-DD"), { days }), "YYYY-MM-DD") : null;
}

// A YYYY-MM-DD day as DD.MM.YYYY; "" for no day.
export function dayTitle(day) {
  return day ? date.formatDate(date.extractDate(day, "YYYY-MM-DD"), "DD.MM.YYYY") : "";
}

// A YYYY-MM-DD day with its weekday, as "Fri 03.10.2026"; "" for no day.
export function dayLabel(day) {
  return day ? date.formatDate(date.extractDate(day, "YYYY-MM-DD"), "ddd DD.MM.YYYY") : "";
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

// Naive server datetime string as milliseconds, read as local time like the server wrote it.
export function toMillis(value) {
  return new Date(String(value).substring(0, 19)).getTime();
}

export function round(value, places) {
  return Math.round(value * Math.pow(10, places)) / Math.pow(10, places);
}

export function formatNumber(value, decimals = 0) {
  return Number(value).toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

// 1234 → 1.2k, 1234567 → 1.2M; the exact number goes to a tooltip.
export function compactNumber(value) {
  const number = Number(value || 0);
  const units = [
    [1e9, "G"],
    [1e6, "M"],
    [1e3, "k"],
  ];
  for (const [size, unit] of units) {
    if (Math.abs(number) >= size) {
      const scaled = number / size;
      return `${scaled.toFixed(scaled < 10 ? 1 : 0)}${unit}`;
    }
  }
  return String(Math.round(number));
}

// Seconds as h:mm:ss (hours beyond 24 kept, e.g. 27:04:33).
export function formatDuration(seconds) {
  const total = Math.round(Number(seconds) || 0);
  const pad = (value) => String(value).padStart(2, "0");
  return `${Math.floor(total / 3600)}:${pad(Math.floor((total % 3600) / 60))}:${pad(total % 60)}`;
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

// 0 B, 512 B, 1.5 KB, 12 MB; empty for a missing size.
export function formatBytes(bytes) {
  if (bytes === null || bytes === undefined) {
    return "";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = Number(bytes);
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${formatNumber(value, unit && value < 10 ? 1 : 0)} ${units[unit]}`;
}

// Hands a Blob to the browser as a file download.
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}
