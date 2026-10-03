// The present on pages that show another clock's hours: the app server's (runs, scheduler) or the database's (file log).
// Their times are naive strings, read like every other (toMillis): a moment in ms whose local wall clock is theirs.
import { date } from "quasar";
import { toMillis } from "./format";

const HOUR = 3600000;

// That clock minus this browser's, from the naive time it answered; 0 when it answered none.
export function clockOffset(serverTime) {
  const millis = serverTime ? toMillis(serverTime) : NaN;
  return Number.isNaN(millis) ? 0 : millis - Date.now();
}

// Where a moment falls among HourHeatmap's 24 columns from `start` (ms): the column plus the share of its hour gone,
// null outside them.
export function windowPosition(now, start) {
  const position = (now - start) / HOUR;
  return position >= 0 && position < 24 ? position : null;
}

// The same for the hours 0..23 of a day (YYYY-MM-DD): null on any other day.
export function dayPosition(now, day) {
  if (!day || date.formatDate(now, "YYYY-MM-DD") !== day) {
    return null;
  }
  const moment = new Date(now);
  return moment.getHours() + moment.getMinutes() / 60;
}

// HH:mm of a moment, for the heatmap's Now marker.
export function clockLabel(now) {
  return date.formatDate(now, "HH:mm");
}
