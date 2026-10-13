"""Contains the KPIs of the Dashboard: the values RACS_KPI_PKG stored.

The history is read once for the last LOOKBACK_DAYS (`kpi.read_run_history_
since`) and every view is cut from it. A period run more than once counts by
its last done run only (`reader.superseded_sql`): the values of superseded
runs are left out. The heatmap puts a run in the bucket of its date_from (the
period it read), the tile in that of STARTRUNDATE (the run's start on the app
server's clock).
"""

import collections
import datetime as dt

import sqlalchemy as sa

from ..database import db
from ..kpi import kpi
from ..reader import superseded_sql
from . import runs as run_data
from . import spans
from .memo import memo


LOOKBACK_DAYS = 31
ALARM = 2


def available():
    """Check whether the KPI tables and their history can be read."""
    return kpi.available and kpi.history_available


def rows():
    """Get the KPI values of the runs of the last LOOKBACK_DAYS that no
    later run of their period superseded, each with its run's `date_from`.
    """
    def read():
        since = (dt.datetime.combine(dt.date.today(), dt.time())
                 - dt.timedelta(days=LOOKBACK_DAYS))
        first = run_data.first_process_id(since)
        history = kpi.read_run_history_since(first, since)
        if not history:
            return []
        periods = {row['process_id']: row['date_from']
                   for row in db.execute(sa.text(f"""
                       select l.process_id, l.date_from
                         from rapo_log l
                        where l.process_id >= :first
                          and {superseded_sql('l')} is null
                   """).bindparams(first=first), as_table=True)}
        result = []
        for row in history:
            process_id = int(row['processid'])
            if process_id not in periods:
                continue
            row = run_data._numbers(row)
            row['date_from'] = periods[process_id] or row['startrundate']
            result.append(row)
        return result
    return memo.get(('kpi_rows',), read)


def types():
    """Get the KPI types by code: their priority rank, unit and decimals."""
    def read():
        return {row['kpi_type']: {'rank': rank,
                                  'unit': row.get('kpi_value_unit'),
                                  'decimals': row.get('kpi_decimal_places')}
                for rank, row in enumerate(kpi.read_kpi_types())}
    return memo.get(('kpi_types',), read)


def kpis(span):
    """Get the KPI alarms of a span: the highest level per control and
    bucket with the run that reached it, and the number of values at level
    ALARM or above.

    A cell is {level, process_id} of its run (the highest level, the latest
    run on a tie) and, when that level is an alarm (1 and above), the KPI of
    the run at that level whose type comes first by priority (`kpi_type`,
    `value`, `unit`, `decimals`) and how many `others` of the run alarmed.
    """
    if not available():
        return {'available': False}
    now = dt.datetime.now()
    start, buckets = spans.window(span, now)
    bucket_unit = spans.unit(span)
    positions = spans.index(buckets)
    catalogue = types()
    last = len(catalogue)
    runs = {}
    cells = {}
    worst = collections.Counter()
    alarms = 0
    for row in rows():
        moment = row['date_from']
        if moment is None or moment < start:
            continue
        position = positions.get(spans.truncate(moment, bucket_unit))
        if position is None:
            continue
        level = int(row['alarm_level'] or 0)
        runs.setdefault(int(row['processid']), []).append(row)
        key = (row['processname'], position)
        best = cells.get(key)
        candidate = (level, int(row['processid']))
        if best is None or candidate > best:
            cells[key] = candidate
        worst[row['processname']] = max(worst[row['processname']], level)
        if level >= ALARM:
            alarms += 1
    names = sorted(worst, key=lambda name: (-worst[name], name))
    order = {name: index for index, name in enumerate(names)}
    ids = {row['control_name']: id
           for id, row in run_data.controls().items()}

    def cell(name, position, level, process_id):
        result = {'row': order[name], 'column': position, 'level': level,
                  'process_id': process_id}
        if level < 1:
            return result
        alarmed = [row for row in runs[process_id]
                   if int(row['alarm_level'] or 0) >= 1]
        top = min((row for row in alarmed
                   if int(row['alarm_level'] or 0) == level),
                  key=lambda row: (catalogue.get(row['kpi_type'], {})
                                   .get('rank', last), row['kpi_type']))
        info = catalogue.get(top['kpi_type'], {})
        return {**result, 'kpi_type': top['kpi_type'],
                'value': top['kpi_value'], 'unit': info.get('unit'),
                'decimals': info.get('decimals'),
                'others': len(alarmed) - 1}

    return {
        'available': True,
        'unit': bucket_unit,
        'buckets': spans.labels(buckets, bucket_unit),
        'heatmap': {
            'controls': [{'control_name': name, 'control_id': ids.get(name),
                          'level': worst[name]} for name in names],
            'cells': [cell(name, position, level, process_id)
                      for (name, position), (level, process_id)
                      in cells.items()]},
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
