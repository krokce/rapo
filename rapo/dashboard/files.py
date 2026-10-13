"""Contains the files of the Dashboard: the PDI Core file log in aggregates.

The file log takes tens of thousands of files a day, too many to sum a month
of it on every look. Closed days are summed once into rapo_file_summary (by
day, hour, datasource, status and duplicate flag) by the scheduler's
maintenance and by Refresh; today, and yesterday until it is summarized, are
read live, one partition each. This module is the only code that knows
rapo_file_summary; the file log's own SQL is pdi.file_summary_select().

Days are those of the database clock, which stamps the file log.
"""

import collections
import datetime as dt
import threading
import time

import sqlalchemy as sa

from .. import options
from ..database import db
from ..logger import logger
from ..pdi import pdi, scanner, DatasourceError
from . import spans
from .memo import memo


TABLE = 'rapo_file_summary'
# The hour of the row marking a day as summarized.
MARKER_HOUR = -1
# Closed days summed again on every maintenance: recycles, reloads and
# deletes change the status of files of the last days.
RECENT_DAYS = 7
TOP = 8
COLUMNS = ('files', 'records_read', 'records_write', 'records_reject',
           'error_count', 'file_bytes', 'runtime_seconds')

# Called with 'summary' once days were summarized, to tell the clients.
listeners = []
_refresh_lock = threading.Lock()
_refreshing = False


def available():
    """Check whether the file log can be read."""
    try:
        return pdi.log_available
    except Exception:
        return False


def keep_days():
    """Get the days of the summary kept, from [DASHBOARD] file_summary_days."""
    default = options.default('DASHBOARD', 'file_summary_days')
    try:
        return max(int(options.get('DASHBOARD', 'file_summary_days')), 31)
    except (TypeError, ValueError):
        return default


def database_now():
    """Get the database clock."""
    return pdi.read_database_time()


def summarize(day):
    """Sum one day of the file log into the summary, replacing it.

    One block, one transaction: the day's rows are deleted and inserted
    anew from its partition, then the marker. Delete and insert, not MERGE,
    because a status that disappeared (SUCCESS became RECYCLED) must go. The
    table lock serializes the maintenance and Refresh; readers are not held.
    """
    start = dt.datetime.combine(day, dt.time())
    columns = ', '.join(COLUMNS)
    block = f"""
        begin
          lock table {TABLE} in exclusive mode;
          delete from {TABLE} where load_day = :day_from;
          insert into {TABLE} (load_day, load_hour, sourceid, sourcename,
                               filestatus, duplicate, {columns}, summarized)
          select :day_from, s.load_hour, s.sourceid, s.sourcename,
                 s.filestatus, s.duplicate, {', '.join(f's.{name}'
                                                      for name in COLUMNS)},
                 sysdate
            from ({pdi.file_summary_select()}) s;
          insert into {TABLE} (load_day, load_hour, sourceid, filestatus,
                               duplicate, files, summarized)
          select :day_from, {MARKER_HOUR}, {MARKER_HOUR}, '-', 0,
                 nvl(sum(files), 0), sysdate
            from {TABLE}
           where load_day = :day_from and load_hour >= 0;
        end;"""
    db.execute(sa.text(block).bindparams(
        day_from=start, day_to=start + dt.timedelta(days=1)))


def summarized_days(day_from, day_to):
    """Get the days in [day_from, day_to) that are summarized."""
    statement = sa.text(
        f'select load_day from {TABLE} where load_day >= :day_from '
        f'and load_day < :day_to and load_hour = {MARKER_HOUR}').bindparams(
            day_from=_start(day_from), day_to=_start(day_to))
    return {row['load_day'].date()
            for row in db.execute(statement, as_table=True)}


def maintain():
    """Sum the closed days of the file log the summary needs, and purge.

    The last RECENT_DAYS are summed again every time; older days of the
    kept window only when they are missing, newest first. Called by the
    scheduler's maintenance.
    """
    if not available():
        return
    started = time.monotonic()
    today = database_now().date()
    days = keep_days()
    recent = [today - dt.timedelta(days=back)
              for back in range(1, RECENT_DAYS + 1)]
    first = today - dt.timedelta(days=days)
    present = summarized_days(first, today)
    missing = [today - dt.timedelta(days=back)
               for back in range(RECENT_DAYS + 1, days + 1)
               if today - dt.timedelta(days=back) not in present]
    for day in recent + missing:
        summarize(day)
    deleted = db.execute(sa.text(
        f'delete from {TABLE} where load_day < :first').bindparams(
            first=_start(first))).rowcount
    logger.info(f'File log summary: {len(recent) + len(missing)} days '
                f'summed, {deleted} rows older than {days} days deleted in '
                f'{time.monotonic() - started:.1f}s')
    _notify()


def refresh(span):
    """Sum the closed days of a span's window again, in the background.

    Raises DatasourceError: 404 without the file log, 409 while a refresh
    of this server is running.
    """
    global _refreshing
    spans.check(span)
    pdi.check()
    if not available():
        raise DatasourceError('The file log is not available.', 404)
    with _refresh_lock:
        if _refreshing:
            raise DatasourceError('The file summary is being refreshed '
                                  'already.', 409)
        _refreshing = True
    now = database_now()
    start, _ = spans.window(span, now)
    today = now.date()
    days = []
    day = today - dt.timedelta(days=1)
    while day >= start.date():
        days.append(day)
        day -= dt.timedelta(days=1)
    thread = threading.Thread(target=_refresh, args=(days,),
                              name='FileSummaryRefresh', daemon=True)
    thread.start()


def refreshing():
    """Check whether a refresh of this server is running."""
    return _refreshing


def _refresh(days):
    global _refreshing
    started = time.monotonic()
    try:
        for day in days:
            summarize(day)
        logger.info(f'File log summary: {len(days)} days summed again in '
                    f'{time.monotonic() - started:.1f}s (Refresh)')
    except Exception:
        logger.error()
    finally:
        with _refresh_lock:
            _refreshing = False
        _notify()


def resummarize(days):
    """Sum the summarized days among `days` again, in the background, after
    rapo changed the status of their files (set-file-status), so the counts
    show the files' current status without waiting for the maintenance.
    """
    if not days or not available():
        return
    today = database_now().date()
    days = sorted(day for day in summarized_days(min(days), today)
                  if day in set(days))
    if days:
        thread = threading.Thread(target=_resummarize, args=(days,),
                                  name='FileSummaryStatus', daemon=True)
        thread.start()


def _resummarize(days):
    try:
        for day in days:
            summarize(day)
        logger.info(f'File log summary: {len(days)} days summed again '
                    f'after a file status change')
    except Exception:
        logger.error()
    finally:
        _notify()


def _notify():
    for listener in listeners:
        try:
            listener('summary')
        except Exception:
            logger.error()


def _live(day):
    """Get one day of the file log summed by hour, read live."""
    return memo.get(('files_live', day),
                    lambda: pdi.read_file_summary_live(day))


def _summary(day_from, day_to, hourly):
    """Get the summed days in [day_from, day_to) by day (or hour),
    datasource, status and duplicate flag.
    """
    def read():
        bucket = ("load_day + load_hour / 24" if hourly else 'load_day')
        sums = ', '.join(f'sum({name}) {name}' for name in COLUMNS)
        statement = sa.text(f"""
            select {bucket} bucket, sourceid, max(sourcename) sourcename,
                   filestatus, duplicate, {sums}
              from {TABLE}
             where load_day >= :day_from and load_day < :day_to
               and load_hour >= 0
             group by {bucket}, sourceid, filestatus, duplicate
        """).bindparams(day_from=_start(day_from), day_to=_start(day_to))
        return [{key: pdi._value(value) for key, value in row.items()}
                for row in db.execute(statement, as_table=True)]
    return memo.get(('files_summary', day_from, day_to, hourly), read)


def _rows(day_from, today, now, hourly):
    """Get the rows of the days [day_from, today] with their `bucket`: the
    summary for the summarized days, the file log for today and an
    unsummarized yesterday.

    Returns
    -------
    rows : list of dict
    state : dict
        `summarized`, `live` and `missing` days.
    """
    present = summarized_days(day_from, today)
    yesterday = today - dt.timedelta(days=1)
    live = [today]
    if yesterday >= day_from and yesterday not in present:
        live.insert(0, yesterday)
    missing = []
    day = day_from
    while day < today:
        if day not in present and day not in live:
            missing.append(day)
        day += dt.timedelta(days=1)
    rows = []
    if present:
        for row in _summary(min(present), max(present)
                            + dt.timedelta(days=1), hourly):
            rows.append(row)
    for day in live:
        start = _start(day)
        for row in _live(day):
            bucket = start + dt.timedelta(hours=row['load_hour'])
            rows.append({**row, 'bucket': bucket if hourly else start})
    return rows, {'summarized': sorted(present), 'live': live,
                  'missing': missing}


def files(span):
    """Get the files of a span: per bucket by status, the records loaded
    and rejected, the throughput, the top datasources and the datasources
    by lane, delivering or silent.
    """
    if not available():
        return {'available': False}
    now = database_now()
    start, buckets = spans.window(span, now)
    bucket_unit = spans.unit(span)
    hourly = bucket_unit == 'hour'
    positions = spans.index(buckets)
    size = len(buckets)
    rows, state = _rows(start.date(), now.date(), now, hourly)
    status = {}
    duplicates = [0] * size
    read = [0] * size
    write = [0] * size
    reject = [0] * size
    loaded = [0] * size
    runtime = [0] * size
    sources = {}
    source_series = {}
    names = {}
    for row in rows:
        position = positions.get(spans.truncate(row['bucket'], bucket_unit))
        if position is None:
            continue
        files_count = row['files'] or 0
        series = status.setdefault(row['filestatus'], [0] * size)
        series[position] += files_count
        if row['duplicate']:
            duplicates[position] += files_count
        read[position] += row['records_read'] or 0
        write[position] += row['records_write'] or 0
        reject[position] += row['records_reject'] or 0
        id = row['sourceid']
        names.setdefault(id, row.get('sourcename'))
        source = sources.setdefault(id, {'files': 0, 'success': 0,
                                         'records': 0, 'rejects': 0,
                                         'runtime': 0})
        source['files'] += files_count
        # The loader's time on the files of every status.
        source['runtime'] += row['runtime_seconds'] or 0
        source['records'] += row['records_write'] or 0
        source['rejects'] += row['records_reject'] or 0
        if row['filestatus'] == 'SUCCESS':
            source['success'] += files_count
        # Per datasource: records loaded, loaded with a runtime, runtime,
        # rejected, read.
        per = source_series.setdefault(id, [[0] * size for _ in range(5)])
        per[0][position] += row['records_write'] or 0
        per[3][position] += row['records_reject'] or 0
        per[4][position] += row['records_read'] or 0
        if row['filestatus'] == 'SUCCESS' and row['runtime_seconds']:
            loaded[position] += row['records_write'] or 0
            runtime[position] += row['runtime_seconds']
            per[1][position] += row['records_write'] or 0
            per[2][position] += row['runtime_seconds']
    # The days neither summarized nor read live are gaps, not zeros.
    missing = set(state['missing'])
    gaps = [position for position, bucket in enumerate(buckets)
            if bucket.date() in missing]
    series_lists = [*status.values(), duplicates, read, write, reject,
                    loaded, runtime]
    for values in series_lists:
        for position in gaps:
            values[position] = None
    lanes = datasources()
    for id, lane in lanes['by_id'].items():
        names[id] = lane['sourcename']
    tops = [{'sourceid': id, 'sourcename': names.get(id), **values}
            for id, values in sources.items()]
    return {
        'available': True,
        'clock': 'database',
        'database_time': now,
        'unit': bucket_unit,
        'buckets': spans.labels(buckets, bucket_unit),
        'status': [{'code': code, 'counts': counts}
                   for code, counts in sorted(
                       status.items(),
                       key=lambda item: -sum(value or 0
                                             for value in item[1]))],
        'duplicates': duplicates,
        'records': {'read': read, 'write': write, 'reject': reject},
        'reject_rate': [_rate(rejected, total) if total is not None
                        else None for rejected, total in zip(reject, read)],
        'top_loaded': sorted(tops, key=lambda row: -row['records'])[:TOP],
        'top_runtime': sorted(
            [row for row in tops if row['runtime']],
            key=lambda row: -row['runtime'])[:TOP],
        'runtime_total': sum(row['runtime'] for row in tops),
        'top_files': sorted(
            [row for row in tops if row['success']],
            key=lambda row: (-row['success'], -row['records']))[:TOP],
        'throughput': {
            'all': [_per_minute(records, seconds) if seconds is not None
                    else None for records, seconds in zip(loaded, runtime)],
            'sources': sorted(
                [{'sourceid': id, 'sourcename': names.get(id),
                  'records': sum(series[0]),
                  'write': [None if position in gaps else value
                            for position, value in enumerate(series[0])],
                  'reject': [None if position in gaps else value
                             for position, value in enumerate(series[3])],
                  'read': [None if position in gaps else value
                           for position, value in enumerate(series[4])],
                  'rates': [None if position in gaps
                            else _per_minute(records, seconds)
                            for position, (records, seconds)
                            in enumerate(zip(series[1], series[2]))]}
                 for id, series in source_series.items()],
                key=lambda row: -row['records'])},
        'datasources': _lanes(lanes, set(sources)),
        'summary': {
            'live_days': [day.isoformat() for day in state['live']],
            'missing_days': [day.isoformat() for day in state['missing']],
            'newest_day': (state['summarized'][-1].isoformat()
                           if state['summarized'] else None),
            'refreshing': refreshing(),
            'maintenance': bool(options.get('SCHEDULER',
                                            'maintenance_interval')),
        },
    }


def datasources():
    """Get the datasources by ID with their lane and waiting files."""
    def read():
        rows = pdi.read_datasource_lanes()
        return {'by_id': {row['id']: row for row in rows}}
    lanes = memo.get(('datasources',), read)
    snapshot = scanner.status() or {}
    return {**lanes, 'scan': snapshot.get('datasources') or {},
            'scanned': bool(snapshot)}


def _lanes(lanes, delivering):
    """Get the datasources by state, each in one: disabled (lane 0), else
    stalled (the last scan), else delivering files in the span or silent;
    with the files waiting in their input directories (the last scan).
    """
    states = collections.Counter(stalled=0, delivering=0, silent=0,
                                 disabled=0)
    totals = collections.Counter()
    for id, row in lanes['by_id'].items():
        totals['datasources'] += 1
        state = lanes['scan'].get(str(id)) or {}
        if not int(row['isactive'] or 0):
            states['disabled'] += 1
        elif state.get('stalled'):
            states['stalled'] += 1
        elif id in delivering:
            states['delivering'] += 1
        else:
            states['silent'] += 1
        totals['waiting'] += state.get('waiting') or 0
    totals['unknown'] = len([id for id in delivering
                             if id not in lanes['by_id']])
    return {'states': dict(states), 'totals': dict(totals),
            'scanned': lanes['scanned']}


def tiles():
    """Get today's files loaded (SUCCESS), records loaded, records rejected
    and files in error.

    Each is {today, last_week, days}: last_week the same weekday a week
    before up to the same time of day (its last hour pro rata, as the
    summary has hours), days the 7 days to today; None where unknown.
    `records_rejected` also has `rate`, today's % of the records read.
    """
    if not available():
        return None

    def read():
        now = database_now()
        today = now.date()
        first = today - dt.timedelta(days=7)
        present = summarized_days(first, today)
        days = {row['bucket'].date(): row
                for row in _totals(first, today, 'load_day')}
        yesterday = today - dt.timedelta(days=1)
        live = [today] + ([yesterday] if yesterday not in present else [])
        for day in live:
            values = collections.Counter()
            for row in _live(day):
                _add(values, row)
            days[day] = values
        known = present | set(live)
        week = collections.Counter()
        if first in present:
            cut = (now - _start(today)) / dt.timedelta(hours=1)
            for row in _totals(first, first + dt.timedelta(days=1),
                               'load_hour'):
                hour = row['bucket']
                share = 1 if hour + 1 <= cut else max(cut - hour, 0)
                for key in ('success', 'read', 'write', 'reject', 'errors'):
                    week[key] += (row[key] or 0) * share
        result = {}
        for name in ('files_success', 'records_loaded', 'records_rejected',
                     'files_error'):
            result[name] = {
                'today': _tile_value(days.get(today), name, True),
                'last_week': _tile_value(week, name, first in present),
                'days': [_tile_value(days.get(day), name, day in known)
                         for day in (today - dt.timedelta(days=back)
                                     for back in range(6, -1, -1))]}
        values = days.get(today) or {}
        result['records_rejected']['rate'] = _rate(
            values.get('reject') or 0, values.get('read') or 0)
        return result
    return memo.get(('file_tiles',), read)


def waiting_tile():
    """Get the files waiting in the input directories as a tile: now (the
    last scan), the same time a week ago and the highest of each of the 7
    days to today, from the instance health's stored `files` minutes (app
    clock); with `stalled`, `datasources_waiting` and `oldest_age` of now.
    """
    def read():
        from ..health import store as health_store
        from ..health.monitor import files_point
        now = dt.datetime.now()
        today = now.date()
        current = files_point(now.isoformat(timespec='seconds')) or {}
        try:
            days = health_store.read_daily_max(
                'files', 'waiting', _start(today - dt.timedelta(days=6)))
            week = health_store.read_value_near(
                'files', 'waiting', now - dt.timedelta(days=7))
        except Exception:
            logger.error()
            days, week = {}, None
        values = [days.get(today - dt.timedelta(days=back))
                  for back in range(6, -1, -1)]
        if current:
            values[-1] = max(values[-1] or 0, current['waiting'])
        return {'today': current.get('waiting'),
                'last_week': pdi._value(week) if week is not None else None,
                'days': [pdi._value(value) if value is not None else None
                         for value in values],
                'stalled': current.get('stalled'),
                'datasources_waiting': current.get('datasources_waiting'),
                'oldest_age': current.get('oldest_age')}
    try:
        if not pdi.available:
            return None
    except Exception:
        return None
    return memo.get(('files_waiting',), read)


def processing_tile():
    """Get the files of the file log waiting to be loaded or loading now,
    of any day: `today` all of them, `loading` (STARTED, PROCESSING),
    `waiting` (WAITING) and `oldest_age`, the seconds since the oldest
    started (database clock).
    """
    if not available():
        return None

    def read():
        rows = pdi.read_files_in_progress()
        now = database_now()
        count = {status: (rows.get(status) or {}).get('files') or 0
                 for status in ('WAITING', 'STARTED', 'PROCESSING')}
        oldest = [row['oldest'] for row in rows.values() if row['oldest']]
        return {'today': sum(count.values()),
                'loading': count['STARTED'] + count['PROCESSING'],
                'waiting': count['WAITING'],
                'oldest_age': (max((now - min(oldest)).total_seconds(), 0)
                               if oldest else None)}
    return memo.get(('files_processing',), read)


def _totals(day_from, day_to, bucket):
    """Get the summary's totals of [day_from, day_to) by day or hour."""
    statement = sa.text(f"""
        select {bucket} bucket,
               sum(case when filestatus = 'SUCCESS' then files else 0 end)
                   success,
               sum(records_read) read,
               sum(records_write) write, sum(records_reject) reject,
               sum(case when filestatus = 'ERROR' then files else 0 end)
                   errors
          from {TABLE}
         where load_day >= :day_from and load_day < :day_to
           and load_hour >= 0
         group by {bucket}
    """).bindparams(day_from=_start(day_from), day_to=_start(day_to))
    return [{key: pdi._value(value) for key, value in row.items()}
            for row in db.execute(statement, as_table=True)]


def _add(values, row):
    if row['filestatus'] == 'SUCCESS':
        values['success'] += row['files'] or 0
    values['read'] += row['records_read'] or 0
    values['write'] += row['records_write'] or 0
    values['reject'] += row['records_reject'] or 0
    if row['filestatus'] == 'ERROR':
        values['errors'] += row['files'] or 0


def _tile_value(values, name, known):
    if not known:
        return None
    values = values or {}
    field = {'files_success': 'success', 'records_loaded': 'write',
             'records_rejected': 'reject', 'files_error': 'errors'}[name]
    return round(values.get(field) or 0)


def _rate(part, whole):
    return round(part * 100 / whole, 3) if whole else None


def _per_minute(records, seconds):
    return round(records * 60 / seconds, 1) if seconds else None


def _start(day):
    return dt.datetime.combine(day, dt.time())
