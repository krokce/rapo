"""Contains the analysis worker, the process of one analysis session.

The worker holds the only copy of the sample. It keeps the cursor of the
dataset's select open, so that Extend fetches the rows that follow instead
of running the select again; a Bernoulli sample is read whole instead, and
Extend reads a bigger one (`SAMPLINGS`). Messages on the pipe are tuples:
- from the server: `(request_id, command, arguments)`;
- to the server: `('reply', request_id, ok, payload)` and
  `('state', state)` whenever the state changes (throttled while fetching).

Heavy steps (fetching, profiling) run one at a time on the job thread and
report through the state; requests (rows, profile sections, export) are
answered from the current sample by a small thread pool, so the viewer keeps
working while more rows are fetched. A sample is never changed in place: a
step builds a new DataFrame and swaps it in with a new `version`.
"""

import concurrent.futures as cf
import json
import os
import queue
import tempfile
import threading as th
import time

import numpy as np
import pandas as pd

from . import frame as fr
from . import profile


FETCH_BATCH = 5000
# Ends the statement of a shuffled sample.
RANDOM_ORDER = 'order by dbms_random.value'
# How the sample is drawn (SessionManager.create picks one): `all` and
# `first` read the dataset as the database returns it, `sorted` shuffles it
# whole first, `bernoulli` keeps each record with the probability that gives
# the wanted size, so the records stream at once; its Extend reads a bigger
# sample anew.
SAMPLINGS = ('all', 'first', 'sorted', 'bernoulli')
STATE_INTERVAL = 0.5
MB = 1024 * 1024
EXCEL_MAX_ROWS = 1048575
EXCEL_MAX_TEXT = 32767
EXCEL_MAX_DIGITS = 15
SECTIONS = ('overview', 'columns', 'relations', 'breakdown')
GROUPS_LIMIT = 5000
AGGREGATES = ('sum', 'mean', 'min', 'max', 'nunique')
BUCKETS = {'hour': 'h', 'day': 'D', 'month': 'M', 'year': 'Y'}


class Canceled(Exception):
    """The current step was canceled."""


class Worker:
    """Represents the sample of one session and the steps working on it."""

    def __init__(self, conn, sql, options):
        self.conn = conn
        self.sql = sql
        self.options = options
        self.sampling = options.get('sampling') or {'mode': 'first'}
        # The size a Bernoulli sample is drawn for (its rows vary around it).
        self.target = 0
        self.send_lock = th.Lock()
        self.jobs = queue.Queue()
        self.pool = cf.ThreadPoolExecutor(max_workers=3)
        self.cancel_flag = th.Event()
        self.stopping = False

        self.connection = None
        self.cursor = None
        self.columns = []
        self.kinds = {}
        self.frame = None
        self.version = 0
        self.cache = {}
        self.cache_lock = th.Lock()
        self.views = {}
        self.last_state = 0

        self.state = {
            'status': 'starting',
            'step': 'Connecting to the database',
            'progress': None,
            'rows': 0,
            'version': 0,
            'sampling': self.sampling['mode'],
            'target': 0,
            'exhausted': False,
            'extendable': False,
            'cursor_open': False,
            'limited': None,
            'memory_mb': 0,
            'columns': [],
            'sections': [],
            'error': None,
        }

    def run(self):
        """Serve requests until the server says stop or goes away."""
        job_thread = th.Thread(target=self._jobs, daemon=True)
        job_thread.start()
        self.jobs.put(('extend', self.options['initial_rows']))
        while not self.stopping:
            try:
                message = self.conn.recv()
            except (EOFError, OSError):
                break
            request_id, command, arguments = message
            if command == 'stop':
                self._reply(request_id, True, None)
                break
            self.pool.submit(self._handle, request_id, command,
                             arguments or {})
        self.stopping = True
        self.cancel_flag.set()
        os._exit(0)

    def _handle(self, request_id, command, arguments):
        try:
            handler = getattr(self, f'on_{command}')
            payload = handler(**arguments)
            self._reply(request_id, True, payload)
        except (Canceled, fr.FilterError, ValueError) as error:
            self._reply(request_id, False, str(error))
        except Exception as error:
            self._reply(request_id, False,
                        f'{type(error).__name__}: {error}')

    def _reply(self, request_id, ok, payload):
        with self.send_lock:
            self.conn.send(('reply', request_id, ok, payload))

    def _publish(self, force=True, **changes):
        self.state.update(changes)
        now = time.monotonic()
        if not force and now - self.last_state < STATE_INTERVAL:
            return
        self.last_state = now
        self.state['memory_mb'] = _memory_mb()
        with self.send_lock:
            self.conn.send(('state', dict(self.state)))

    # Commands answered at once from the current sample.

    def on_status(self):
        return dict(self.state)

    def on_extend(self, rows=None):
        if not self.state['extendable']:
            raise ValueError('There are no more rows to fetch')
        self.jobs.put(('extend', rows or self.options['extend_rows']))
        return dict(self.state)

    def on_cancel(self):
        self.cancel_flag.set()
        return dict(self.state)

    def on_rows(self, offset=0, limit=200, sort=None, search=None,
                filters=None):
        data, kinds = self._sample()
        positions = self._view(data, kinds, sort, search, filters)
        window = positions[offset:offset + limit]
        subset = data.iloc[window]
        rows = [[fr.to_json(value) for value in row]
                for row in subset.itertuples(index=False, name=None)]
        return {'version': self.state['version'], 'total': len(positions),
                'offset': offset, 'rows': rows}

    def on_profile(self, section):
        """Get a profile section of the sample; start computing it when it
        is not ready. The state lists the section under `sections` once it
        is.
        """
        if section not in SECTIONS:
            raise ValueError(f'Unknown section {section}')
        version = self.state['version']
        with self.cache_lock:
            if (section, version) in self.cache:
                return {'ready': True, 'version': version, 'key': section,
                        'data': self.cache[(section, version)]}
        self.jobs.put(('section', section))
        return {'ready': False, 'version': version, 'key': section,
                'data': None}

    def on_groups(self, by, aggregates=None, filters=None, search=None,
                  sort=None, limit=1000):
        """Group the rows the filters and the search leave.

        `by` is [{column, bucket}], a date-time column cut into `hour`,
        `day`, `month` or `year` when `bucket` is set; `aggregates` is
        [{column, fn}] with fn one of sum, mean, min, max, nunique. The
        groups come by descending count unless `sort` ({column, desc}, where
        column is `count`, a grouping column or `fn(column)`) says otherwise.
        """
        data, kinds = self._sample()
        if not by:
            raise ValueError('Choose a column to group by')
        positions = self._view(data, kinds, None, search, filters)
        subset = data.iloc[positions]
        keys, names, ends = [], [], {}
        for item in by:
            name = item.get('column')
            if name not in data.columns:
                raise ValueError(f'Unknown column {name}')
            series = subset[name]
            bucket = item.get('bucket')
            if bucket and kinds[name] == fr.DATETIME:
                if bucket not in BUCKETS:
                    raise ValueError(f'Unknown bucket {bucket}')
                periods = series.dt.to_period(BUCKETS[bucket])
                series = periods.dt.start_time
                ends[len(names)] = periods
            keys.append(series.rename(f'_key{len(names)}'))
            names.append(name)
        grouped = subset.groupby(keys, dropna=False, sort=False)
        table = grouped.size().rename('count').to_frame()
        labels = []
        for item in aggregates or []:
            name, function = item.get('column'), item.get('fn')
            if name not in data.columns or function not in AGGREGATES:
                raise ValueError(f'Unknown aggregate {function}({name})')
            if function != 'nunique' and kinds[name] != fr.NUMERIC:
                if function in ('sum', 'mean'):
                    raise ValueError(f'{function} needs a numeric column')
            label = f'{function}({name})'
            column = subset[name]
            if kinds[name] == fr.NUMERIC and function != 'nunique':
                column = pd.Series(fr.floats(column), index=subset.index)
            table[label] = column.groupby(keys, dropna=False,
                                          sort=False).agg(function)
            labels.append(label)
        total_groups = len(table)
        order = (sort or {}).get('column') or 'count'
        descending = (sort or {}).get('desc', True)
        table = table.reset_index()
        sort_names = {name: f'_key{index}' for index, name in enumerate(names)}
        sort_column = sort_names.get(order, order)
        if sort_column in table.columns:
            table = table.sort_values(sort_column, ascending=not descending,
                                      na_position='last', kind='stable')
        table = table.iloc[:min(int(limit or 1000), GROUPS_LIMIT)]
        rows = []
        for record in table.itertuples(index=False, name=None):
            row = dict(zip(table.columns, record))
            groups = [fr.to_json(row[f'_key{index}'])
                      for index in range(len(names))]
            bounds = {}
            for index in ends:
                start = row[f'_key{index}']
                if start is not None and start is not pd.NaT \
                        and not pd.isna(start):
                    period = pd.Period(start, freq=BUCKETS[by[index]['bucket']])
                    bounds[index] = fr.to_json((period + 1).start_time)
            rows.append({'keys': groups, 'ends': bounds,
                         'count': int(row['count']),
                         'values': [fr.to_json(row[label])
                                    for label in labels]})
        return {'version': self.state['version'], 'by': names,
                'aggregates': labels, 'rows': rows,
                'total_groups': total_groups, 'total_rows': len(subset)}

    def on_export(self, format='xlsx', sort=None, search=None, filters=None,
                  columns=None):
        data, kinds = self._sample()
        positions = self._view(data, kinds, sort, search, filters)
        names = [name for name in (columns or list(data.columns))
                 if name in data.columns]
        subset = data.iloc[positions][names]
        handle, path = tempfile.mkstemp(prefix='rapo_analysis_',
                                        suffix=f'.{format}')
        os.close(handle)
        if format == 'csv':
            texts = subset.copy()
            for name in names:
                if kinds[name] == fr.DATETIME:
                    texts[name] = fr.text_values(subset[name], kinds[name])
            texts.to_csv(path, index=False, encoding='utf-8-sig')
            return {'path': path, 'rows': len(subset), 'cut': False}
        cut = len(subset) > EXCEL_MAX_ROWS
        _write_excel(path, subset.iloc[:EXCEL_MAX_ROWS], kinds)
        return {'path': path, 'rows': min(len(subset), EXCEL_MAX_ROWS),
                'cut': cut}

    def _sample(self):
        data = self.frame
        if data is None:
            raise ValueError('The sample is not loaded yet')
        return data, self.kinds

    def _view(self, data, kinds, sort, search, filters):
        key = json.dumps([self.state['version'], sort, search, filters],
                         sort_keys=True, default=str)
        positions = self.views.get(key)
        if positions is None:
            if filters or search:
                keep = fr.mask(data, kinds, filters, search).to_numpy()
                positions = np.flatnonzero(keep)
            else:
                positions = np.arange(len(data))
            positions = fr.order(data, positions, sort)
            if len(self.views) > 8:
                self.views.clear()
            self.views[key] = positions
        return positions

    # Steps, one at a time.

    def _jobs(self):
        while not self.stopping:
            name, argument = self.jobs.get()
            self.cancel_flag.clear()
            try:
                if name == 'extend':
                    self._extend(argument)
                    self._compute('columns')
                    self._compute('overview')
                elif name == 'section':
                    self._compute(argument)
                self._publish(status='ready', step=None, progress=None)
            except Canceled:
                self._drain()
                self._publish(status='ready' if self.frame is not None
                              else 'canceled', step=None, progress=None)
            except Exception as error:
                self._drain()
                self._publish(status='ready' if self.frame is not None
                              else 'error', step=None, progress=None,
                              error=f'{type(error).__name__}: {error}')

    def _drain(self):
        while True:
            try:
                self.jobs.get_nowait()
            except queue.Empty:
                return

    def _check(self):
        if self.cancel_flag.is_set() or self.stopping:
            raise Canceled('Canceled')

    def _open(self, target=None):
        import oracledb
        from ..database import db

        oracledb.defaults.fetch_lobs = False
        mode = self.sampling['mode']
        self._publish(status='fetching', step={
            'sorted': 'Shuffling the dataset',
            'bernoulli': 'Sampling the dataset'}.get(mode,
                                                    'Opening the dataset'))
        self.connection = db.engine.raw_connection()
        self.cursor = self.connection.cursor()
        self.cursor.arraysize = FETCH_BATCH
        self.cursor.prefetchrows = FETCH_BATCH
        self.cursor.execute(self._statement(target))
        description = self.cursor.description
        if mode == 'bernoulli':
            # The random value, last; fr.build leaves it out of the rows.
            description = description[:-1]
        names = fr.unique_names(item[0] for item in description)
        self.columns = [
            {'name': name, 'kind': fr.column_kind(item[1]),
             'db_type': getattr(item[1], 'name', str(item[1]))
             .replace('DB_TYPE_', '')}
            for name, item in zip(names, description)]
        self.kinds = {item['name']: item['kind'] for item in self.columns}
        self._publish(cursor_open=True, columns=self.columns)

    def _statement(self, target):
        """Get the select of the sample: `target` records for a Bernoulli
        one, out of the dataset's `total`."""
        mode = self.sampling['mode']
        if mode == 'sorted':
            return f'select * from ({self.sql}) {RANDOM_ORDER}'
        if mode == 'bernoulli':
            # As explain._sampled: a merged dbms_random predicate is
            # evaluated once (all or none of the records), so the value is a
            # column of an unmerged view.
            share = min(1.0, target / max(self.sampling['total'], 1))
            return ('select * from (select /*+ no_merge */ s.*, '
                    f'dbms_random.value rapo_sample from ({self.sql}) s) '
                    f'where rapo_sample < {share:.12f}')
        return self.sql

    def _close_cursor(self):
        for item in (self.cursor, self.connection):
            try:
                if item is not None:
                    item.close()
            except Exception:
                pass
        self.cursor = None
        self.connection = None
        self.state['cursor_open'] = False

    def _extend(self, wanted):
        """Fetch `wanted` more records into the sample: from the open cursor,
        or for a Bernoulli sample a bigger sample read anew, which replaces
        the sample (read whole, so it is not biased to the first records the
        database returns).
        """
        resample = self.sampling['mode'] == 'bernoulli'
        loaded = len(self.frame) if self.frame is not None else 0
        largest = self.options['max_rows']
        if resample:
            target = min((self.target or loaded) + wanted, largest)
            if target <= self.target:
                self._publish(limited='rows', extendable=False)
                return
            self._close_cursor()
            self._open(target)
            wanted, expected, base = largest, target, 0
        else:
            if self.cursor is None:
                if self.state['exhausted'] or self.frame is not None:
                    return
                self._open()
            wanted = min(wanted, largest - loaded)
            if wanted <= 0:
                self._publish(limited='rows', extendable=False)
                return
            expected, base = wanted, loaded
        memory_limit = self.options['max_memory_mb']
        rows = []
        limited = None
        ended = False
        self._publish(status='fetching', step='Fetching rows',
                      progress={'done': 0, 'total': expected}, limited=None)
        try:
            while len(rows) < wanted:
                self._check()
                if memory_limit and _memory_mb() > memory_limit:
                    limited = 'memory'
                    break
                batch = self.cursor.fetchmany(
                    min(FETCH_BATCH, wanted - len(rows)))
                if not batch:
                    ended = True
                    break
                rows.extend(batch)
                progress = {'done': min(len(rows), expected),
                            'total': expected}
                if resample:
                    self._publish(force=False, progress=progress)
                else:
                    self._publish(force=False, rows=base + len(rows),
                                  progress=progress)
        except Canceled:
            # A bigger sample read in part would hold the first records only.
            if resample:
                self._close_cursor()
                raise
            if not rows:
                raise
        except Exception:
            # The cursor is lost (e.g. snapshot too old): the sample is kept,
            # but it can not be extended any more.
            self._close_cursor()
            if (resample and self.frame is not None) \
                    or (not rows and self.frame is None):
                raise
        if ended or resample:
            self._close_cursor()
        self._publish(status='fetching', step='Building the sample',
                      progress=None)
        chunk = fr.build(rows, self.columns)
        if resample or self.frame is None or not len(self.frame):
            data = chunk
        elif len(chunk):
            data = pd.concat([self.frame, chunk], ignore_index=True)
        else:
            data = self.frame
        if base + len(rows) >= largest:
            limited = limited or 'rows'
        if resample:
            self.target = target
            complete = target >= self.sampling['total']
            exhausted = complete and ended
            extendable = not complete and not limited and len(data) < largest
        else:
            exhausted = ended or self.state['exhausted']
            extendable = (self.cursor is not None and not exhausted
                          and not limited)
        self.frame = data
        self.views = {}
        with self.cache_lock:
            self.cache = {}
        self.version += 1
        self._publish(rows=len(data), version=self.version, sections=[],
                      limited=limited, error=None, exhausted=exhausted,
                      extendable=extendable, target=self.target)

    def _compute(self, section):
        data, kinds = self._sample()
        version = self.version
        with self.cache_lock:
            if (section, version) in self.cache:
                return
        labels = {'overview': 'Computing the overview',
                  'columns': 'Profiling the columns',
                  'relations': 'Measuring relations',
                  'breakdown': 'Counting the result types'}
        self._publish(status='profiling', step=labels[section],
                      progress=None)

        def step(done, total):
            self._check()
            self._publish(force=False, progress={'done': done,
                                                 'total': total})

        if section == 'columns':
            result = profile.columns(data, kinds, step)
        elif section == 'overview':
            self._compute('columns')
            with self.cache_lock:
                profiles = self.cache[('columns', version)]
            self._publish(status='profiling', step=labels[section])
            result = profile.overview(data, kinds, profiles)
        elif section == 'relations':
            result = profile.relations(data, kinds, step)
        else:
            result = profile.breakdown(data, kinds, step)
        with self.cache_lock:
            if version != self.version:
                return
            self.cache[(section, version)] = result
            sections = sorted({item[0] for item in self.cache
                               if item[1] == version})
        self._publish(sections=sections)


def _memory_mb():
    import psutil
    return int(psutil.Process().memory_info().rss / MB)


def _write_excel(path, data, kinds):
    """Write the rows to an xlsx file with the formats of the email sheets."""
    import xlsxwriter

    workbook = xlsxwriter.Workbook(path, {'constant_memory': True,
                                          'strings_to_numbers': False,
                                          'strings_to_formulas': False,
                                          'strings_to_urls': False})
    worksheet = workbook.add_worksheet('Data')
    header = workbook.add_format({'bold': True, 'bg_color': '#E0E0E0',
                                  'border': 1})
    date_format = workbook.add_format({'num_format': 'dd.mm.yyyy'})
    moment_format = workbook.add_format(
        {'num_format': 'dd.mm.yyyy hh:mm:ss'})
    names = list(data.columns)
    widths = []
    for index, name in enumerate(names):
        worksheet.write_string(0, index, name.upper(), header)
        widths.append(len(name) + 2)
    formats = {}
    for name in names:
        if kinds[name] == fr.DATETIME:
            series = data[name].dropna()
            midnight = bool((series == series.dt.normalize()).all())
            formats[name] = date_format if midnight else moment_format
    for number, row in enumerate(data.itertuples(index=False, name=None),
                                 start=1):
        for index, value in enumerate(row):
            if value is None or value is pd.NA or value is pd.NaT:
                continue
            name = names[index]
            kind = kinds[name]
            if kind == fr.DATETIME:
                worksheet.write_datetime(number, index,
                                         value.to_pydatetime(),
                                         formats[name])
                widths[index] = max(widths[index], 19)
            elif kind == fr.NUMERIC:
                value = value.item() if isinstance(value, np.generic) \
                    else value
                if isinstance(value, float) and not np.isfinite(value):
                    continue
                if isinstance(value, int) and \
                        len(str(abs(value))) > EXCEL_MAX_DIGITS:
                    worksheet.write_string(number, index, str(value))
                else:
                    worksheet.write_number(number, index, value)
                widths[index] = max(widths[index], min(len(str(value)), 30))
            else:
                text = str(value)[:EXCEL_MAX_TEXT]
                worksheet.write_string(number, index, text)
                widths[index] = max(widths[index], min(len(text), 60))
    for index, width in enumerate(widths):
        worksheet.set_column(index, index, min(width + 1, 62))
    worksheet.freeze_panes(1, 0)
    worksheet.autofilter(0, 0, max(len(data), 1), max(len(names) - 1, 0))
    workbook.close()

