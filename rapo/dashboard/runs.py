"""Contains the runs of the Dashboard: rapo_log in aggregates.

Runs count on the hour they started, or were added if they never started, as
on Results, on the app server's clock that stamps rapo_log. Runs of deleted
controls are left out, as there. Every read goes through an index of rapo_log
and none reads a whole log text.
"""

import collections
import datetime as dt

import sqlalchemy as sa

from ..database import db
from ..reader import WARNING_PREFIX
from . import spans
from .memo import memo


ACTIVE = ('I', 'W', 'S', 'P', 'F')
# The order of the statuses in the stacks: outcomes first, then the active.
STATUS_ORDER = ('D', 'E', 'C', 'X', None, 'I', 'W', 'S', 'P', 'F')
TOP = 8

# The trigger of a run: its STARTED event, by the index on process_id; null
# for a run the run manager did not start.
TRIGGER = ('(select max(e.trigger_type) from rapo_scheduler_event e '
           'where e.process_id = l.process_id)')


def runs_since(columns):
    """Get the select of the runs since :since with their `started`.

    Three disjoint parts, each on an index of rapo_log: the runs started
    since (start_date), the runs that never started but changed since
    (updated, stamped by every status change) and the runs just initiated
    (status I, whose insert leaves updated empty). A run that never started
    counts when it was added.
    """
    return f"""
        select {columns}, l.start_date started from rapo_log l
         where l.start_date >= :since
        union all
        select {columns}, l.added started from rapo_log l
         where l.start_date is null and l.updated >= :since
           and l.added >= :since
        union all
        select {columns}, l.added started from rapo_log l
         where l.start_date is null and l.updated is null
           and l.status = 'I' and l.added >= :since"""


def controls():
    """Get every control by ID: name, type, engine, group and status."""
    def read():
        config = db.tables.config
        select = sa.select(config.c.control_id, config.c.control_name,
                           config.c.control_type, config.c.control_engine,
                           config.c.control_group, config.c.status)
        return {int(row['control_id']): row
                for row in db.execute(select, as_table=True)}
    return memo.get(('config',), read)


def run_groups(span):
    """Get the runs of a span's window by hour, control, status and trigger.

    Each row has `hour`, `control_id`, `status`, `trigger_type`, `runs`,
    `fetched` and `discrepancies` (both sides summed), `seconds`, `timed` and
    `max_seconds` of the finished runs (D) and `last_process_id`.
    """
    def read():
        start, _ = spans.window(span, dt.datetime.now())
        columns = ('l.process_id, l.control_id, l.status, l.end_date, '
                   'nvl(coalesce(l.fetched_number_a, l.fetched_number), 0) '
                   '+ nvl(l.fetched_number_b, 0) fetched, '
                   'nvl(coalesce(l.error_number_a, l.error_number), 0) '
                   '+ nvl(l.error_number_b, 0) discrepancies, '
                   f'{TRIGGER} trigger_type')
        timed = "r.status = 'D' and r.end_date is not null"
        statement = sa.text(f"""
            select trunc(r.started, 'HH24') hour, r.control_id, r.status,
                   r.trigger_type, count(*) runs, sum(r.fetched) fetched,
                   sum(r.discrepancies) discrepancies,
                   sum(case when {timed}
                            then (r.end_date - r.started) * 86400 end) seconds,
                   sum(case when {timed} then 1 else 0 end) timed,
                   max(case when {timed}
                            then (r.end_date - r.started) * 86400 end)
                       max_seconds,
                   max(r.process_id) last_process_id
              from ({runs_since(columns)}) r
             group by trunc(r.started, 'HH24'), r.control_id, r.status,
                      r.trigger_type
        """).bindparams(since=start)
        return [_numbers(row) for row in db.execute(statement, as_table=True)]
    return memo.get(('run_groups', span), read)


def timeline(span):
    """Get the runs per bucket of a span, stacked by status."""
    now = dt.datetime.now()
    _, buckets = spans.window(span, now)
    bucket_unit = spans.unit(span)
    positions = spans.index(buckets)
    configs = controls()
    counts = {}
    for row in run_groups(span):
        position = positions.get(spans.truncate(row['hour'], bucket_unit))
        if position is None or row['control_id'] not in configs:
            continue
        series = counts.setdefault(row['status'], [0] * len(buckets))
        series[position] += row['runs']
    status = [{'code': code, 'counts': counts[code]}
              for code in sorted(counts, key=_status_rank)]
    total = [sum(values) for values in zip(*counts.values())] if counts \
        else [0] * len(buckets)
    return {'unit': bucket_unit, 'buckets': spans.labels(buckets, bucket_unit),
            'clock': 'server', 'server_time': now.replace(microsecond=0),
            'status': status, 'total': total}


def runs(span):
    """Get the runs of a span by type and trigger, the slowest controls,
    their volume and when they happen.
    """
    now = dt.datetime.now()
    _, buckets = spans.window(span, now)
    bucket_unit = spans.unit(span)
    positions = spans.index(buckets)
    configs = controls()
    by_type = {}
    by_trigger = collections.Counter()
    per_control = {}
    fetched = [0] * len(buckets)
    discrepancies = [0] * len(buckets)
    # Monday first, as the schedules count weekdays (1 = Monday).
    hour_count = [[0] * 24 for _ in range(7)]
    hour_errors = [[0] * 24 for _ in range(7)]
    for row in run_groups(span):
        config = configs.get(row['control_id'])
        position = positions.get(spans.truncate(row['hour'], bucket_unit))
        if config is None or position is None:
            continue
        count, status = row['runs'], row['status']
        failed = count if status == 'E' else 0
        kind = by_type.setdefault(config['control_type'],
                                  {'runs': 0, 'errors': 0})
        kind['runs'] += count
        kind['errors'] += failed
        by_trigger[row['trigger_type'] or 'NONE'] += count
        fetched[position] += row['fetched'] or 0
        discrepancies[position] += row['discrepancies'] or 0
        weekday, hour = row['hour'].weekday(), row['hour'].hour
        hour_count[weekday][hour] += count
        hour_errors[weekday][hour] += failed
        control = per_control.setdefault(row['control_id'], {
            'seconds': 0, 'timed': 0, 'max_seconds': 0})
        control['seconds'] += row['seconds'] or 0
        control['timed'] += row['timed'] or 0
        control['max_seconds'] = max(control['max_seconds'],
                                     row['max_seconds'] or 0)
    return {
        'unit': bucket_unit,
        'buckets': spans.labels(buckets, bucket_unit),
        'by_type': by_type,
        'by_trigger': dict(by_trigger),
        'slowest': _slowest(per_control, configs),
        'volume': {'fetched': fetched, 'discrepancies': discrepancies},
        'hour_weekday': {'count': hour_count, 'errors': hour_errors},
    }


def _control(control_id, configs):
    config = configs[control_id]
    return {'control_id': control_id,
            'control_name': config['control_name'],
            'control_type': config['control_type']}


def _slowest(per_control, configs):
    rows = [{**_control(id, configs), 'runs': control['timed'],
             'avg_minutes': round(control['seconds'] / control['timed'] / 60,
                                  2),
             'max_minutes': round(control['max_seconds'] / 60, 2)}
            for id, control in per_control.items() if control['timed']]
    rows.sort(key=lambda row: -row['avg_minutes'])
    return rows[:TOP]


def tiles():
    """Get today's runs, runs in error, failing controls and runs with a
    warning.

    Each is {today, last_week, days}: last_week the same weekday a week
    before up to the same time of day, days the 7 days to today (whole).
    A failing control is one whose latest run of the day ended in error, as
    on Results.
    """
    def read():
        now = dt.datetime.now()
        today = dt.datetime.combine(now.date(), dt.time())
        cut = (now - today).total_seconds() / 86400
        columns = ('l.process_id, l.control_id, l.status, '
                   'case when dbms_lob.instr(l.text_message, :warning) > 0 '
                   'then 1 else 0 end warned')
        early = 'case when r.started - trunc(r.started) <= :cut then 1 else 0 end'
        statement = sa.text(f"""
            with d as (
              select trunc(r.started) day, r.status, r.warned, {early} early,
                     row_number() over (
                       partition by trunc(r.started), r.control_id
                       order by r.process_id desc) latest,
                     row_number() over (
                       partition by trunc(r.started), r.control_id, {early}
                       order by r.process_id desc) latest_early
                from ({runs_since(columns)}) r
                join rapo_config c on c.control_id = r.control_id)
            select day, count(*) runs, sum(early) runs_early,
                   sum(warned) warnings, sum(warned * early) warnings_early,
                   sum(case when status = 'E' then 1 else 0 end) errors,
                   sum(case when status = 'E' then early else 0 end)
                       errors_early,
                   sum(case when latest = 1 and status = 'E'
                            then 1 else 0 end) failing,
                   sum(case when early = 1 and latest_early = 1
                             and status = 'E' then 1 else 0 end) failing_early
              from d
             group by day
        """).bindparams(since=today - dt.timedelta(days=7), cut=cut,
                        warning=WARNING_PREFIX)
        days = {row['day'].date(): _numbers(row)
                for row in db.execute(statement, as_table=True)}
        return {name: _tile(days, today.date(), field)
                for name, field in (('runs', 'runs'),
                                    ('run_errors', 'errors'),
                                    ('failing_controls', 'failing'),
                                    ('run_warnings', 'warnings'))}
    return memo.get(('run_tiles',), read)


def _tile(days, today, field):
    week = days.get(today - dt.timedelta(days=7)) or {}
    return {'today': (days.get(today) or {}).get(field, 0),
            'last_week': week.get(f'{field}_early', 0),
            'days': [(days.get(today - dt.timedelta(days=back)) or {})
                     .get(field, 0) for back in range(6, -1, -1)]}


def first_process_id(since):
    """Get the first process ID of the runs started since a moment."""
    return db.execute(sa.text(
        'select min(process_id) from rapo_log where start_date >= :since'
    ).bindparams(since=since), as_scalar=True)


def _numbers(row):
    """Get a row with Oracle's Decimals as int or float."""
    result = {}
    for key, value in row.items():
        if hasattr(value, 'as_integer_ratio') and not isinstance(
                value, (int, float)):
            value = int(value) if value == int(value) else float(value)
        result[key] = value
    return result


def _status_rank(code):
    return STATUS_ORDER.index(code) if code in STATUS_ORDER \
        else len(STATUS_ORDER)
