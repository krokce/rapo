"""Contains the KPIs of the Dashboard: the values RACS_KPI_PKG stored.

The history is read once for the last LOOKBACK_DAYS (`kpi.read_run_history_
since`) and every view is cut from it; STARTRUNDATE is the run's start on the
app server's clock, so the buckets are those of the runs.
"""

import collections
import datetime as dt

from ..kpi import kpi
from . import runs as run_data
from . import spans
from .memo import memo


LOOKBACK_DAYS = 31
HEATMAP_CONTROLS = 25
ALARM = 2


def available():
    """Check whether the KPI tables and their history can be read."""
    return kpi.available and kpi.history_available


def rows():
    """Get the KPI values of the runs of the last LOOKBACK_DAYS."""
    def read():
        since = (dt.datetime.combine(dt.date.today(), dt.time())
                 - dt.timedelta(days=LOOKBACK_DAYS))
        first = run_data.first_process_id(since)
        return [run_data._numbers(row)
                for row in kpi.read_run_history_since(first, since)]
    return memo.get(('kpi_rows',), read)


def kpis(span):
    """Get the KPI alarms of a span: the highest level per control and
    bucket, and the number of values at level ALARM or above.
    """
    if not available():
        return {'available': False}
    now = dt.datetime.now()
    start, buckets = spans.window(span, now)
    bucket_unit = spans.unit(span)
    positions = spans.index(buckets)
    cells = {}
    worst = collections.Counter()
    alarms = 0
    for row in rows():
        moment = row['startrundate']
        if moment is None or moment < start:
            continue
        position = positions.get(spans.truncate(moment, bucket_unit))
        if position is None:
            continue
        level = int(row['alarm_level'] or 0)
        key = (row['processname'], position)
        cells[key] = max(cells.get(key, 0), level)
        worst[row['processname']] = max(worst[row['processname']], level)
        if level >= ALARM:
            alarms += 1
    names = sorted(worst, key=lambda name: (-worst[name], name))
    names = names[:HEATMAP_CONTROLS]
    order = {name: index for index, name in enumerate(names)}
    ids = {row['control_name']: id
           for id, row in run_data.controls().items()}
    return {
        'available': True,
        'unit': bucket_unit,
        'buckets': spans.labels(buckets, bucket_unit),
        'heatmap': {
            'controls': [{'control_name': name, 'control_id': ids.get(name),
                          'level': worst[name]} for name in names],
            'cells': [[order[name], position, level]
                      for (name, position), level in cells.items()
                      if name in order],
            'more': max(len(worst) - len(names), 0)},
        'alarms': alarms,
    }


def tiles():
    """Get today's KPI alarms (level 2 and above) as a tile."""
    if not available():
        return None
    now = dt.datetime.now()
    today = dt.datetime.combine(now.date(), dt.time())
    cut = now - today
    days = collections.Counter()
    early = 0
    for row in rows():
        moment = row['startrundate']
        if moment is None or int(row['alarm_level'] or 0) < ALARM:
            continue
        day = moment.date()
        days[day] += 1
        if day == (today - dt.timedelta(days=7)).date() and (
                moment - dt.datetime.combine(day, dt.time()) <= cut):
            early += 1
    return {'today': days[today.date()], 'last_week': early,
            'days': [days[(today - dt.timedelta(days=back)).date()]
                     for back in range(6, -1, -1)]}
