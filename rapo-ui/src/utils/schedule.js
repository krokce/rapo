// schedule_config helpers shared by the scheduler editor and the catalogue summary.
// Types: D daily, W weekly, M monthly, C cascade (no time, triggered by another control),
// X complex (cron-like ranges, steps or lists the simple editors can't represent).

import { allUpstreams } from "./chain";

export function defaultSchedule() {
  return { mday: null, wday: null, hour: "8", min: "15", sec: "0", trigger_id: null };
}

const isEmpty = (value) => value == null || value === "";

export function scheduleType(schedule) {
  const { mday, wday, hour, min, sec } = schedule;
  const text = [mday, wday, hour, min, sec].map((value) => (isEmpty(value) ? "" : String(value)));
  if (text.some((value) => /[/*-]/.test(value)) || (!isEmpty(mday) && !isEmpty(wday)) || text.slice(2).some((value) => value.includes(","))) {
    return "X";
  }
  if (isEmpty(hour) && isEmpty(min) && isEmpty(sec)) {
    return "C";
  }
  if (!isEmpty(mday)) {
    return "M";
  }
  if (!isEmpty(wday)) {
    return "W";
  }
  return "D";
}

// Parse the stored JSON string; simple schedules get mday/wday as arrays of numbers for the day pickers.
export function parseSchedule(scheduleString) {
  const schedule = { mday: null, wday: null, hour: null, min: null, sec: null, trigger_id: null, ...JSON.parse(scheduleString) };
  if (scheduleType(schedule) !== "X") {
    for (const key of ["mday", "wday"]) {
      if (!isEmpty(schedule[key])) {
        schedule[key] = String(schedule[key]).split(",").map(Number);
      }
    }
  }
  return schedule;
}

// Note the scheduler reads null as "any" but "" as "never", so hour/min/sec keep "" as is.
export function serializeSchedule(schedule) {
  const days = (value) => (value && value.length !== 0 ? String(value) : null);
  const time = (value) => (value != null ? String(value) : null);
  return JSON.stringify({
    mday: days(schedule.mday),
    wday: days(schedule.wday),
    hour: time(schedule.hour),
    min: time(schedule.min),
    sec: time(schedule.sec),
    trigger_id: schedule.trigger_id ? schedule.trigger_id : null,
  });
}

export function scheduleTime(schedule) {
  return [schedule.hour, schedule.min, schedule.sec].map((value) => String(value ?? 0).padStart(2, "0")).join(":");
}

// Everything a run of this control performs besides the control itself: the controls whose results it reads,
// which run first (upstream), its enabled iterations, and the enabled controls cascading from it (the ones
// triggered by its control_id). Malformed configuration of one control must not break the caller.
export function chainOf(controlName, catalogue) {
  const control = (catalogue || []).find((item) => item.control_name === controlName);
  if (!control) {
    return { iterations: 0, cascade: [], upstream: [] };
  }
  let iterations = 0;
  try {
    iterations = JSON.parse(control.iteration_config || "[]").filter((item) => item.status === "Y").length;
  } catch (err) {
    iterations = 0;
  }
  const cascade = catalogue.filter((item) => {
    if (item.status !== "Y" || !item.schedule_config) {
      return false;
    }
    try {
      const { trigger_id } = JSON.parse(item.schedule_config);
      return !!trigger_id && control.control_id === Number(trigger_id);
    } catch (err) {
      return false;
    }
  });
  return { iterations, cascade: cascade.map((item) => item.control_name), upstream: allUpstreams(controlName, catalogue) };
}

// A sentence naming the controls a run cascades into, or "" when it cascades into none.
// The iterations are not named here: they are optional on a manual run and have their own switch.
export function cascadeMessage(cascade) {
  return cascade.length ? `This will also cascade into ${cascade.join(", ")}.` : "";
}

// The values of one unit a moment can match, as schedule.check matches them; null for "any" (null or "*").
// A unit of none of the known forms, "" included, matches nothing.
const DOMAINS = { mday: [1, 31], wday: [1, 7], hour: [0, 23], min: [0, 59], sec: [0, 59] };

export function unitValues(unit, name) {
  if (unit == null || (Array.isArray(unit) && !unit.length)) {
    return null;
  }
  const text = String(unit);
  if (text === "*") {
    return null;
  }
  const [low, high] = DOMAINS[name];
  const domain = Array.from({ length: high - low + 1 }, (item, index) => low + index);
  let match;
  if (/^\d+$/.test(text)) {
    return domain.filter((value) => value === Number(text));
  } else if ((match = text.match(/^\/(\d+)$/))) {
    const step = Number(match[1]);
    return step ? domain.filter((value) => value % step === 0) : [];
  } else if ((match = text.match(/^(\d+)-(\d+)$/))) {
    return domain.filter((value) => value >= Number(match[1]) && value <= Number(match[2]));
  } else if (/^\d+,\s*\d+/.test(text)) {
    const listed = (text.match(/\d+/g) || []).map(Number);
    return domain.filter((value) => listed.includes(value));
  }
  return [];
}

// The units of a schedule_config (JSON text or object) as { mday, wday, hour, min, sec } of value lists (null for
// any), plus trigger_id and whether the scheduler fires it at all (schedule.parse: some unit set, none matching
// nothing); null for text that is no JSON object.
export function scheduleUnits(config) {
  let raw = config;
  if (typeof config === "string" || config == null) {
    try {
      raw = config ? JSON.parse(config) : {};
    } catch (err) {
      return null;
    }
  }
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return null;
  }
  const units = { trigger_id: raw.trigger_id || null };
  const names = Object.keys(DOMAINS);
  names.forEach((name) => (units[name] = unitValues(Array.isArray(raw[name]) ? raw[name].join(",") : raw[name], name)));
  const set = names.some((name) => raw[name] != null && raw[name] !== "" && !(Array.isArray(raw[name]) && !raw[name].length));
  units.set = set;
  units.fires = set && names.every((name) => units[name] === null || units[name].length > 0);
  return units;
}

const WEEKDAYS = ["", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const pad = (value) => String(value).padStart(2, "0");
const ordinal = (day) => `${day}${[11, 12, 13].includes(day % 100) ? "th" : { 1: "st", 2: "nd", 3: "rd" }[day % 10] || "th"}`;
const times = (count) => (count === 2 ? "Twice" : `${count}×`);
const all = (values, name) => values === null || values.length === DOMAINS[name][1] - DOMAINS[name][0] + 1;

// The step of values evenly spaced from below the step (0, 15, 30, 45 → 15), else 0.
function stepOf(values) {
  if (values.length < 2) {
    return 0;
  }
  const step = values[1] - values[0];
  return values[0] < step && values.every((value, index) => value === values[0] + index * step) ? step : 0;
}

// 1st–10th for consecutive days, else 1st, 15th, 28th.
function daysText(days) {
  const consecutive = days.length > 2 && days.every((day, index) => day === days[0] + index);
  return consecutive ? `${ordinal(days[0])}–${ordinal(days[days.length - 1])}` : days.map(ordinal).join(", ");
}

function weekdaysText(days, long) {
  const key = days.join(",");
  if (key === "1,2,3,4,5") return "Weekdays";
  if (key === "6,7") return "Weekends";
  if (long && days.length === 1) return `Weekly on ${WEEKDAYS[days[0]]}`;
  return days.map((day) => WEEKDAYS[day].slice(0, 3)).join(", ");
}

// The day part: "" for every day.
function dayPhrase(units) {
  const mday = all(units.mday, "mday") ? null : units.mday;
  const wday = all(units.wday, "wday") ? null : units.wday;
  if (mday && wday) {
    return `${weekdaysText(wday, false)} within the ${daysText(mday)}`;
  }
  if (wday) {
    return weekdaysText(wday, true);
  }
  if (mday) {
    if (mday.length === 1) return `Monthly on the ${ordinal(mday[0])}`;
    if (mday.length <= 5) return `${times(mday.length)} a month (${mday.map(ordinal).join(", ")})`;
    return `Monthly on the ${daysText(mday)}`;
  }
  return "";
}

// The time part: { text, count } where count is the number of fires a day.
function timePhrase(units) {
  const hours = units.hour || [...Array(24).keys()];
  const minutes = units.min || [...Array(60).keys()];
  const seconds = units.sec || [...Array(60).keys()];
  const count = hours.length * minutes.length * seconds.length;
  const clock = (h, m, s) => `${pad(h)}:${pad(m)}${s ? `:${pad(s)}` : ""}`;
  const withSeconds = seconds.some(Boolean);
  const span = () => {
    if (all(units.hour, "hour")) return "";
    const last = clock(hours[hours.length - 1], minutes[minutes.length - 1], withSeconds ? seconds[seconds.length - 1] : 0);
    return `, ${clock(hours[0], minutes[0], withSeconds ? seconds[0] : 0)}–${last}`;
  };
  if (count <= 4) {
    const list = [];
    hours.forEach((h) => minutes.forEach((m) => seconds.forEach((s) => list.push(clock(h, m, withSeconds ? s : 0)))));
    return { text: `at ${list.join(", ")}`, count };
  }
  if (seconds.length > 1) {
    const step = stepOf(seconds);
    return { text: `${step ? (step === 1 ? "every second" : `every ${step} s`) : `${seconds.length}× a minute`}${span()}`, count };
  }
  const secondText = seconds[0] ? `:${pad(seconds[0])}` : "";
  if (minutes.length > 1) {
    const step = stepOf(minutes);
    return { text: `${step ? (step === 1 ? "every minute" : `every ${step} min`) : `${minutes.length}× an hour`}${span()}`, count };
  }
  const step = stepOf(hours);
  const at = `at :${pad(minutes[0])}${secondText}`;
  if (step) {
    return { text: `${step === 1 ? "every hour" : `every ${step} hours`} ${at}`, count };
  }
  const consecutive = hours.every((hour, index) => hour === hours[0] + index);
  return { text: consecutive ? `every hour ${pad(hours[0])}–${pad(hours[hours.length - 1])} ${at}` : `${hours.length}× a day ${at}`, count };
}

// A short description of a schedule_config: "Every day at 08:15", "Weekly on Monday at 08:15", "Twice a month
// (1st, 2nd) at 08:15:01", "Every hour at :05:12", "After CHN_B finishes", "Not scheduled". `triggerName` names the
// control a cascade follows.
export function describeSchedule(config, triggerName = null) {
  const units = scheduleUnits(config);
  if (!units) {
    return "Invalid schedule";
  }
  if (!units.fires) {
    if (units.trigger_id) {
      return `After ${triggerName || `control ${units.trigger_id}`} finishes`;
    }
    return units.set ? "Never fires" : "Not scheduled";
  }
  const days = dayPhrase(units);
  const time = timePhrase(units);
  if (!days) {
    if (time.count === 1) return `Every day ${time.text}`;
    if (time.count <= 4) return `${times(time.count)} a day ${time.text}`;
    return time.text.charAt(0).toUpperCase() + time.text.slice(1);
  }
  return time.count <= 4 ? `${days} ${time.text}` : `${days}, ${time.text}`;
}

// How often a schedule fires, for the avatar color: subdaily, daily, weekly, monthly,
// complex (month and week days), cascade, none.
export function scheduleFrequency(config) {
  const units = scheduleUnits(config);
  if (!units || !units.fires) {
    return units && units.trigger_id ? "cascade" : "none";
  }
  const mday = !all(units.mday, "mday");
  const wday = !all(units.wday, "wday");
  if (timePhrase(units).count > 1) return "subdaily";
  if (mday && wday) return "complex";
  if (mday) return "monthly";
  if (wday) return "weekly";
  return "daily";
}

// Where the fires fall: 24 hours for a schedule firing every day, 7 week days for a weekly one, 31 month days
// otherwise; null when it does not fire.
export function scheduleRhythm(config) {
  const units = scheduleUnits(config);
  if (!units || !units.fires) {
    return null;
  }
  const slots = (name) => {
    const [low, high] = DOMAINS[name];
    return Array.from({ length: high - low + 1 }, (item, index) => units[name] === null || units[name].includes(low + index));
  };
  const mday = !all(units.mday, "mday");
  const wday = !all(units.wday, "wday");
  if (mday) return { scale: "month", slots: slots("mday") };
  if (wday) return { scale: "week", slots: slots("wday") };
  return { scale: "day", slots: slots("hour") };
}
