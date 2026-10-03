// The Scheduler page's rolling 24 hours: Upcoming from the current hour on, History up to and including it, in whole
// hours of the server's clock (scheduler-upcoming / scheduler-events?hours=24 cut the same windows).
import { date } from "quasar";
import { CONTROL_TYPES, RUN_STATUSES, SCHEDULER_EVENT_TYPES, TRIGGER_TYPES } from "../constants";
import { toMillis } from "./format";

const HOUR = 3600000;

// The first hour of a window of 24 whole hours: the current one (offset 0, Upcoming) or 23 hours before it (History).
// serverNow is the server's time in the browser's reading of naive datetimes (Date.now() + clock offset).
export function windowStart(serverNow, offset = 0) {
  const start = new Date(serverNow);
  start.setMinutes(0, 0, 0);
  return start.getTime() + offset * HOUR;
}

// The 24 columns of HourHeatmap from the window start: midnight gets a divider and the day it starts.
export function rollingSlots(start) {
  return Array.from({ length: 24 }, (_, index) => {
    const from = new Date(start + index * HOUR);
    const to = new Date(start + (index + 1) * HOUR);
    const midnight = index > 0 && from.getHours() === 0;
    return {
      hour: from.getHours(),
      title: `${date.formatDate(from, "ddd DD.MM HH:00")}–${date.formatDate(to, "HH:00")}`,
      divider: midnight,
      dividerLabel: midnight ? date.formatDate(from, "ddd DD.MM") : null,
    };
  });
}

// The column of a naive datetime in the window, or null outside it.
export function slotOf(value, start) {
  if (!value) {
    return null;
  }
  const index = Math.floor((toMillis(value) - start) / HOUR);
  return index >= 0 && index < 24 ? index : null;
}

// One heatmap row of 24 cells: rows counted by the column of `timeKey`; `marks(row)` gives {errors, warnings} flags and
// `breakdown` the keys whose counts the tooltip lists, in their constants' order.
function heatmapRow(rows, start, timeKey, label, breakdown, marks = () => ({})) {
  const cells = Array.from({ length: 24 }, () => ({ count: 0, errors: 0, warnings: 0, parts: breakdown.map(() => new Map()) }));
  rows.forEach((row) => {
    const index = slotOf(row[timeKey], start);
    if (index === null) {
      return;
    }
    const cell = cells[index];
    const mark = marks(row);
    cell.count += 1;
    cell.errors += mark.errors ? 1 : 0;
    cell.warnings += mark.warnings ? 1 : 0;
    breakdown.forEach(({ key }, part) => cell.parts[part].set(row[key], (cell.parts[part].get(row[key]) || 0) + 1));
  });
  cells.forEach((cell) => {
    cell.breakdown = breakdown
      .map(({ order, text }, part) =>
        [...cell.parts[part].entries()]
          .sort(([a], [b]) => order.indexOf(a) - order.indexOf(b))
          .map(([value, count]) => `${text(value)} ${count}`)
          .join(", ")
      )
      .filter(Boolean)
      .join(" · ");
    delete cell.parts;
  });
  return [{ key: "total", label, cells }];
}

const TYPE_PART = { key: "control_type", order: Object.keys(CONTROL_TYPES), text: (value) => value };
const TRIGGER_PART = { key: "trigger_type", order: Object.keys(TRIGGER_TYPES), text: (value) => (TRIGGER_TYPES[value] || { label: value }).label };

// Upcoming fires per hour, by type and trigger.
export function upcomingHeatmapRows(fires, start) {
  return heatmapRow(fires, start, "scheduled_time", "Fires", [TYPE_PART, TRIGGER_PART]);
}

// Events per hour they were recorded, by type; errors: failed events or runs ended in error, warnings: missed fires.
export function historyHeatmapRows(events, start) {
  return heatmapRow(events, start, "event_time", "Events", [TYPE_PART], (event) => ({
    errors: event.event_type === "FAILED" || event.status === "E",
    warnings: event.event_type === "MISSED",
  }));
}

// Counts of rows by a field, in the order of its constants (others last): [{key, count}].
export function countBy(rows, field, order) {
  const counts = new Map();
  rows.forEach((row) => row[field] != null && counts.set(row[field], (counts.get(row[field]) || 0) + 1));
  const rank = (key) => (order.indexOf(key) < 0 ? order.length : order.indexOf(key));
  return [...counts.keys()].sort((a, b) => rank(a) - rank(b)).map((key) => ({ key, count: counts.get(key) }));
}

export const ORDERS = {
  type: Object.keys(CONTROL_TYPES),
  trigger: Object.keys(TRIGGER_TYPES),
  event: Object.keys(SCHEDULER_EVENT_TYPES),
  status: Object.keys(RUN_STATUSES),
};
