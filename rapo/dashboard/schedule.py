"""Contains the scheduler of the Dashboard: its last and next 24 hours."""

import collections
import datetime as dt

from ..core import journal
from . import spans
from .memo import memo


EVENT_ORDER = (journal.STARTED, journal.FIRED, journal.MISSED,
               journal.FAILED, journal.CANCELED)
UPCOMING_HOURS = 24
MISSED_LIMIT = 500


def scheduler():
    """Get the scheduler around now, whatever the span: its events of the
    last 24 hours per hour and type (the current hour last), the fires of the
    next 24 hours per hour (the current hour first) and type, and the number
    of missed fires never caught up.
    """
    def read():
        from ..core.scheduler import upcoming
        now = dt.datetime.now()
        hour = now.replace(minute=0, second=0, microsecond=0)
        past = [hour - dt.timedelta(hours=back)
                for back in range(UPCOMING_HOURS - 1, -1, -1)]
        positions = spans.index(past)
        counts = {}
        for row in journal.count_events(past[0], 'hour'):
            position = positions.get(row['bucket'])
            if position is None:
                continue
            series = counts.setdefault(row['event_type'], [0] * len(past))
            series[position] += int(row['events'])
        future = [hour + dt.timedelta(hours=index)
                  for index in range(UPCOMING_HOURS)]
        total = [0] * UPCOMING_HOURS
        by_type = {}
        by_trigger = collections.Counter()
        for fire in upcoming(UPCOMING_HOURS):
            index = int((fire['scheduled_time'] - hour).total_seconds()
                        // 3600)
            if not 0 <= index < UPCOMING_HOURS:
                continue
            total[index] += 1
            series = by_type.setdefault(fire['control_type'],
                                        [0] * UPCOMING_HOURS)
            series[index] += 1
            by_trigger[fire['trigger_type']] += 1
        rows = missed()
        return {
            'server_time': now.replace(microsecond=0),
            'past': {'hours': spans.labels(past, 'hour'),
                     'events': [{'code': code, 'counts': counts[code]}
                                for code in sorted(counts, key=_event_rank)]},
            'upcoming': {'hours': spans.labels(future, 'hour'),
                         'counts': total, 'by_type': by_type,
                         'by_trigger': dict(by_trigger)},
            'missed_total': len(rows),
            'missed_capped': len(rows) >= MISSED_LIMIT,
        }
    return memo.get(('scheduler',), read)


def next_fire():
    """Get the next fire of the scheduler's own schedules within 24 hours:
    its `time`, the first control by name (`control_id`, `control_name`,
    `control_type`) and how many `others` fire at the same time; None when
    nothing is scheduled.
    """
    def read():
        from ..core.scheduler import upcoming
        fires = [fire for fire in upcoming(UPCOMING_HOURS)
                 if fire['trigger_type'] == journal.SCHEDULE]
        if not fires:
            return None
        first = fires[0]
        same = [fire for fire in fires
                if fire['scheduled_time'] == first['scheduled_time']]
        return {'time': first['scheduled_time'],
                'control_id': first['control_id'],
                'control_name': first['control_name'],
                'control_type': first['control_type'],
                'others': len(same) - 1}
    return memo.get(('scheduler', 'next'), read)


def missed():
    """Get the missed fires never caught up, newest first."""
    return memo.get(('scheduler', 'missed'), lambda: journal.read_missed(
        dt.datetime.now(), MISSED_LIMIT))


def _event_rank(code):
    return EVENT_ORDER.index(code) if code in EVENT_ORDER \
        else len(EVENT_ORDER)
