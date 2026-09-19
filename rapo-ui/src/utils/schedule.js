// schedule_config helpers shared by the scheduler editor and the catalogue summary.
// Types: D daily, W weekly, M monthly, C cascade (no time, triggered by another control),
// X complex (cron-like ranges, steps or lists the simple editors can't represent).

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
