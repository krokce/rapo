"""Contains control schedule parsing and fire time calculation.

A control schedule is the `schedule_config` JSON of a `rapo_config` row with
the cron-like units `mday`, `wday`, `hour`, `min` and `sec`. Each unit is
one of:

* `None` or `*` - any value;
* `N` - exactly N;
* `/N` - any value divisible by N (`/0` is never);
* `N-M` - any value from N to M inclusive;
* `N,M,...` - any of the listed values;
* anything else, including an empty string - never.

A moment matches when all units match. Week days are numbered from 1
(Monday) to 7 (Sunday). A schedule with all units empty is not scheduled, it
is either disabled or triggered in cascade by another control.
"""

import datetime as dt
import json
import re


UNITS = ['mday', 'wday', 'hour', 'min', 'sec']
DOMAINS = {
    'mday': range(1, 32),
    'wday': range(1, 8),
    'hour': range(0, 24),
    'min': range(0, 60),
    'sec': range(0, 60),
}
# Longest horizon searched for the next fire. Rare combinations of month and
# week days (e.g. 29th of February on Monday) are found within 28 years.
HORIZON_DAYS = 366*28


def parse(schedule_config):
    """Get schedule units from `schedule_config` JSON.

    Returns
    -------
    schedule : dict or None
        Units by name, or None when the control is not scheduled.
    """
    schedule = dict.fromkeys(UNITS)
    if schedule_config:
        values = json.loads(schedule_config)
        if isinstance(values, dict):
            schedule.update({k: v for k, v in values.items() if k in UNITS})
    if any(value for value in schedule.values()):
        return schedule
    return None


def check(unit, now):
    """Check whether one schedule unit matches the given value."""
    if unit is None:
        return True
    unit = str(unit)
    # Check if empty or *.
    if re.match(r'^(\*)$', unit) is not None:
        return True
    # Check if unit is lonely digit and equals to now.
    elif re.match(r'^\d+$', unit) is not None:
        return now == int(unit)
    # Check if unit is a cycle and integer division with now is true.
    elif re.match(r'^/\d+$', unit) is not None:
        unit = int(re.search(r'\d+', unit).group())
        if unit == 0:
            return False
        return now % unit == 0
    # Check if unit is a range and now is in this range.
    elif re.match(r'^\d+-\d+$', unit) is not None:
        unit = [int(i) for i in re.findall(r'\d+', unit)]
        return now in range(unit[0], unit[1] + 1)
    # Check if unit is a list and now is in this list.
    elif re.match(r'^\d+,\s*\d+.*$', unit):
        unit = [int(i) for i in re.findall(r'\d+', unit)]
        return now in unit
    # All other cases is not for the now.
    return False


def matches(schedule, moment):
    """Check whether the schedule fires at the given datetime."""
    return (check(schedule['mday'], moment.day)
            and check(schedule['wday'], moment.isoweekday())
            and check(schedule['hour'], moment.hour)
            and check(schedule['min'], moment.minute)
            and check(schedule['sec'], moment.second))


def values(schedule):
    """Get sorted matching values of each unit within its domain."""
    return {unit: [value for value in DOMAINS[unit]
                   if check(schedule[unit], value)]
            for unit in UNITS}


def next_fire(schedule, after, limit=1, before=None):
    """Get the next fire times of the schedule.

    Parameters
    ----------
    schedule : dict
        Schedule units as returned by `parse`.
    after : datetime
        Fire times are strictly later than this naive local datetime.
    limit : int or None
        Maximum number of fire times to return, None for no limit.
    before : datetime or None
        Fire times are strictly earlier than this datetime.

    Returns
    -------
    fires : list of datetime
        Naive local datetimes with second precision in ascending order.
    """
    allowed = values(schedule)
    if not all(allowed.values()):
        return []
    fires = []
    after = after.replace(microsecond=0)
    day = after.date()
    last_day = day+dt.timedelta(days=HORIZON_DAYS)
    if before is not None:
        last_day = min(last_day, before.date())
    while day <= last_day:
        if (day.day in allowed['mday']
                and day.isoweekday() in allowed['wday']):
            for hour in allowed['hour']:
                for minute in allowed['min']:
                    for second in allowed['sec']:
                        moment = dt.datetime(day.year, day.month, day.day,
                                             hour, minute, second)
                        if moment <= after or not exists(moment):
                            continue
                        if before is not None and moment >= before:
                            return fires
                        fires.append(moment)
                        if limit is not None and len(fires) >= limit:
                            return fires
        day += dt.timedelta(days=1)
    return fires


def exists(moment):
    """Check that a naive local datetime is not skipped by a DST change."""
    return dt.datetime.fromtimestamp(moment.timestamp()) == moment


def read_all():
    """Read schedules of all active controls from the configuration table.

    Yields
    ------
    control_name, item : str, dict
        Control name and a dictionary with its `schedule` and `control_id`,
        `control_type` and `control_group`.
    """
    from ..database import db
    from ..logger import logger
    table = db.tables.config
    select = (table.select()
                   .where(table.c.status == 'Y')
                   .order_by(table.c.control_id))
    for record in db.execute(select, as_records=True):
        try:
            item = parse(record.schedule_config)
        except Exception:
            logger.warning(f'Control {record.control_name} has invalid '
                           'schedule configuration')
            continue
        if item:
            yield record.control_name, {
                'schedule': item,
                'control_id': int(record.control_id),
                'control_type': record.control_type,
                'control_group': record.control_group,
            }
