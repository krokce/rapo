"""Contains the calendar buckets of date-time values.

A histogram of dates is cut into whole clock hours, days, months or years,
never into equal parts of an odd range, so that a daily run's records show as
the 24 hours of its window. The unit follows the span: up to `HOUR_DAYS` an
hour, up to `DAY_DAYS` a day, up to `MONTH_DAYS` a month, beyond a year.
Shared by the profile of a sample (`profile.py`) and the time binning of the
discrepancy analysis (`explain.py`).
"""

import datetime as dt


HOUR_DAYS = 2
DAY_DAYS = 62
MONTH_DAYS = 5 * 366
# A date column is bucketed on the run's window when this share of its values
# lies in it.
WINDOW_SHARE = 0.9
WEEKDAYS = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')


def unit_of(start, end):
    """Get the unit of buckets over `start`..`end`."""
    days = (end - start).total_seconds() / 86400
    if days <= HOUR_DAYS:
        return 'hour'
    if days <= DAY_DAYS:
        return 'day'
    return 'month' if days <= MONTH_DAYS else 'year'


def floor(moment, unit):
    """Get the start of the unit `moment` is in."""
    moment = moment.replace(minute=0, second=0, microsecond=0)
    if unit == 'hour':
        return moment
    moment = moment.replace(hour=0)
    if unit == 'day':
        return moment
    moment = moment.replace(day=1)
    return moment if unit == 'month' else moment.replace(month=1)


def step(moment, unit):
    """Get the start of the unit after the one starting at `moment`."""
    if unit == 'hour':
        return moment + dt.timedelta(hours=1)
    if unit == 'day':
        return moment + dt.timedelta(days=1)
    if unit == 'month':
        return moment.replace(year=moment.year + moment.month // 12,
                              month=moment.month % 12 + 1)
    return moment.replace(year=moment.year + 1)


def edges(start, end, unit=None):
    """Get the unit and the bucket edges covering `start`..`end`, both in:
    from the start of `start`'s unit to the first edge after `end` (a
    window 00:00:00 – 23:59:59 gives 25 edges, 24 hours).
    """
    unit = unit or unit_of(start, end)
    result = [floor(start, unit)]
    while result[-1] <= end:
        result.append(step(result[-1], unit))
    return unit, result


def same_day(start, end):
    """Whether two moments are of one calendar day."""
    return start.date() == end.date()


def label(start, unit):
    """Get the text of the bucket starting at `start`: `2026-10-09 18:00 –
    18:59`, `Fri 2026-10-09`, `Oct 2026`, `2026`."""
    if unit == 'hour':
        return f'{start:%Y-%m-%d %H}:00 – {start:%H}:59'
    if unit == 'day':
        return f'{WEEKDAYS[start.weekday()]} {start:%Y-%m-%d}'
    return f'{start:%b %Y}' if unit == 'month' else f'{start:%Y}'


def moment_text(moment):
    """Get an edge as text, without the seconds and a midnight's time."""
    if moment == floor(moment, 'day'):
        return f'{moment:%Y-%m-%d}'
    return f'{moment:%Y-%m-%d %H:%M}'
