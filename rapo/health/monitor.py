"""Contains the instance health sampler.

Samples the OS and DB metrics in threads of the web server, keeping the last
`history_minutes` of the samples and `history_hours` of their one-minute
aggregates in memory for the Instance details dialog. The aggregates are also
stored (store.py, rapo_health_minute) for `history_days`, with a minute of the
files waiting in the input directories (group `files`): read back at start,
so the history outlives a restart, and read for spans longer than the
memory's.
"""

import collections
import datetime as dt
import math
import queue
import threading
import time

from ..config import config
from .. import options
from ..logger import logger

from . import sources
from . import store


OPTIONS = {name: options.default('HEALTH', name) for name in (
    'enabled', 'os_interval', 'db_interval', 'footprint_interval',
    'history_minutes', 'history_hours', 'history_days')}

# The spans the UI offers, in hours, up to history_hours; 1 shows the samples,
# longer ones the minute aggregates merged into at most MAX_POINTS points.
# LONG_SPANS are read from the stored minutes, offered up to history_days.
SPANS = (1, 3, 6, 12, 24)
LONG_SPANS = (168,)
MAX_POINTS = 480
GROUPS = ('os', 'db', 'files')
# Seconds the stored minutes of a long span are kept for the next snapshot,
# and between purges of the minutes older than history_days.
STORED_SECONDS = 60
PURGE_SECONDS = 3600
# Fields aggregated by their highest value rather than the average, so that a
# short lock or connection leak still shows on a long span.
PEAK_FIELDS = {'locks', 'locks_wait', 'tcp_close_wait', 'processes_rapo',
               'net_errors', 'net_drops'}
# Fields taken from the last point: counters and facts, not measurements.
LAST_FIELDS = {'uptime', 'rapo_uptime', 'db_uptime', 'cpus', 'cpu_count',
               'memory_total_gb', 'pga_limit_gb', 'rapo_gb', 'rapo_segments'}

# Seconds before DB sources that could not be read are probed again, so
# that a grant given later is found without a restart.
PROBE_RETRY = 600

# Rules of the warning levels: the group and field of the value, and the
# number of latest points averaged, so a moment's peak is no alarm. Their
# thresholds are [HEALTH] <rule>_warn and <rule>_crit (a value at or above one
# reaches it, None never), defaults in rapo/options.py.
RULES = {
    'cpu': ('os', 'cpu', 3),
    'memory': ('os', 'memory', 1),
    'disk': ('os', 'disk', 1),
    'close_wait': ('os', 'tcp_close_wait', 1),
    'db_cpu': ('db', 'db_cpu', 1),
    'db_memory': ('db', 'pga_percent', 1),
    'storage': ('db', 'storage', 1),
    'locks': ('db', 'locks', 1),
    'locks_wait': ('db', 'locks_wait', 1),
}
LEVELS = (None, 'warn', 'crit')


def option(name):
    """Get a [HEALTH] option of rapo.ini, read at use so it reloads."""
    section = config.get('HEALTH') or {}
    value = section.get(name)
    if value is None:
        return OPTIONS[name]
    if isinstance(OPTIONS[name], bool):
        return bool(value)
    try:
        return max(int(value), 1)
    except (TypeError, ValueError):
        return OPTIONS[name]


def thresholds():
    """Get {rule: [warn, crit]} with the overrides of rapo.ini."""
    section = config.get('HEALTH') or {}
    output = {}
    for rule in RULES:
        values = []
        for suffix in ('warn', 'crit'):
            default = options.default('HEALTH', f'{rule}_{suffix}')
            value = section.get(f'{rule}_{suffix}', default)
            values.append(value if isinstance(value, (int, float))
                          and not isinstance(value, bool) else default)
        output[rule] = values
    return output


def now():
    return dt.datetime.now().isoformat(timespec='seconds')


def aggregate(points, time):
    """Merge points into one at `time`: numbers averaged (PEAK_FIELDS their
    highest), anything else (LAST_FIELDS, lists, errors) as in the last point.
    """
    output = {}
    for field, value in points[-1].items():
        if (field in LAST_FIELDS or isinstance(value, bool)
                or not isinstance(value, (int, float))):
            output[field] = value
            continue
        values = [point.get(field) for point in points]
        values = [item for item in values if isinstance(item, (int, float))]
        value = (max(values) if field in PEAK_FIELDS
                 else sum(values) / len(values))
        output[field] = round(value, 3)
    output['t'] = time
    return output


def merge(minutes, size):
    """Merge minute aggregates into points of `size` minutes, aligned to
    multiples of it so that the points do not move as minutes are added.
    """
    if size <= 1:
        return list(minutes)
    output = []
    chunk = []
    chunk_key = None
    for point in minutes:
        moment = dt.datetime.fromisoformat(point['t'])
        key = (moment.toordinal() * 1440 + moment.hour * 60
               + moment.minute) // size
        if chunk and key != chunk_key:
            output.append(aggregate(chunk, chunk[len(chunk) // 2]['t']))
            chunk = []
        chunk.append(point)
        chunk_key = key
    if chunk:
        output.append(aggregate(chunk, chunk[len(chunk) // 2]['t']))
    return output


class Sampler:
    """Samples the instance health in the background, one thread per group.

    Listeners are called with `('sample', {group, point, levels, level})` for
    every point and `('level', {level})` when the worst level changes.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.stopping = threading.Event()
        self.wakes = {'os': threading.Event(), 'db': threading.Event()}
        self.threads = []
        self.points = {'os': collections.deque(), 'db': collections.deque()}
        # One-minute aggregates, and the samples of the minute in progress.
        self.minutes = {group: collections.deque() for group in GROUPS}
        self.buckets = {'os': [], 'db': []}
        # The closed minutes waiting to be stored, and the writer storing them.
        self.queue = queue.Queue(maxsize=1000)
        self.writer = None
        self.server = None
        self.store_error = None
        self.files_minute = None
        # {hours: (expires, {group: minutes})} of the long spans.
        self.stored = {}
        self.footprint = None
        self.footprint_time = 0
        # The file systems measured, resolved once in the background
        # (sources.resolve_directories); None until rapo's own are.
        self.mounts = None
        self.resolver = None
        self.probe_errors = None
        self.probe_time = 0
        self.levels = {}
        self.level = None
        self.listeners = []

    def start(self):
        """Start sampling in threads of their own, and the store's writer."""
        if self.threads:
            return
        self.stopping.clear()
        for group, target in (('os', self.sample_os),
                              ('db', self.sample_db)):
            thread = threading.Thread(target=self.run, args=(group, target),
                                      name=f'rapo-health-{group}',
                                      daemon=True)
            thread.start()
            self.threads.append(thread)
        self.writer = threading.Thread(target=self.write,
                                       name='rapo-health-store', daemon=True)
        self.writer.start()
        self.threads.append(self.writer)

    def stop(self):
        """Stop sampling."""
        self.stopping.set()
        for wake in self.wakes.values():
            wake.set()
        for thread in self.threads:
            thread.join(timeout=10)
        self.threads = []

    def reset(self):
        """Probe the DB sources again and apply changed options at once."""
        with self.lock:
            self.probe_errors = None
        for wake in self.wakes.values():
            wake.set()

    def run(self, group, target):
        while not self.stopping.is_set():
            if option('enabled'):
                try:
                    target()
                except Exception:
                    logger.error()
            elif self.points[group] or self.level:
                self.clear(group)
            wake = self.wakes[group]
            wake.wait(option(f'{group}_interval'))
            wake.clear()

    def clear(self, group):
        with self.lock:
            self.points[group].clear()
            self.minutes[group].clear()
            self.buckets[group] = []
            if group == 'os':
                self.minutes['files'].clear()
            self.levels = {}
            changed, self.level = self.level is not None, None
        if changed:
            self.publish('level', {'level': None})

    def sample_os(self):
        if self.resolver is None:
            self.resolver = threading.Thread(target=self.resolve,
                                             name='rapo-health-mounts',
                                             daemon=True)
            self.resolver.start()
        point = {'t': now(), **sources.read_os(self.mounts)}
        self.add('os', point)
        self.add_files(point['t'])

    def add_files(self, moment):
        """Note the files waiting in the input directories, once a minute, as
        the last scan counted them (none when no scan is recent).
        """
        minute = moment[:16]
        if minute == self.files_minute:
            return
        self.files_minute = minute
        try:
            point = files_point(minute + ':30')
        except Exception:
            logger.error()
            point = None
        if point is None:
            return
        size = option('history_hours') * 60
        with self.lock:
            history = self.minutes['files']
            if history.maxlen != size:
                history = self.minutes['files'] = collections.deque(
                    history, maxlen=size)
            history.append(point)
        self.keep('files', point)

    def resolve(self):
        """Find the file systems of rapo and of the datasource directories,
        once: symlinks are not expected to change, and a datasource added
        later counts from the next start. Datasources that cannot be read are
        tried again every footprint_interval.
        """
        try:
            base = sources.base_directories()
            self.mounts = sources.resolve_directories(base)
            while not self.stopping.is_set():
                try:
                    directories = sources.read_directories()
                    break
                except Exception as error:
                    logger.warning('Instance health: datasource directories '
                                   f'not read: {str(error).splitlines()[0]}')
                self.stopping.wait(option('footprint_interval'))
            else:
                return
            self.mounts = sources.resolve_directories(base + directories)
        except Exception:
            logger.error()

    def sample_db(self):
        if (self.probe_errors is None
                or (any(self.probe_errors.values())
                    and time.monotonic() - self.probe_time > PROBE_RETRY)):
            errors = sources.probe()
            missing = [name for name, error in errors.items() if error]
            if missing and missing != [name for name, error
                                       in (self.probe_errors or {}).items()
                                       if error]:
                logger.info('Instance health: no access to '
                            f'{", ".join(sources.DB_SOURCES[name][0] for name in missing)}')
            with self.lock:
                self.probe_errors = errors
                self.probe_time = time.monotonic()
        available = {name for name, error in self.probe_errors.items()
                     if not error}
        point = {'t': now(), **sources.read_db(available)}
        if (self.footprint is None or time.monotonic() - self.footprint_time
                > option('footprint_interval')):
            try:
                self.footprint = {'t': point['t'], **sources.read_footprint()}
            except Exception as error:
                point['errors']['footprint'] = str(error).splitlines()[0]
            self.footprint_time = time.monotonic()
        if self.footprint:
            point['rapo_gb'] = self.footprint['rapo_gb']
            point['rapo_segments'] = self.footprint['rapo_segments']
        self.add('db', point)

    def add(self, group, point):
        size = max(option('history_minutes') * 60
                   // option(f'{group}_interval'), 1) + 1
        minutes = option('history_hours') * 60
        with self.lock:
            points = self.points[group]
            if points.maxlen != size:
                points = self.points[group] = collections.deque(points,
                                                                maxlen=size)
            points.append(point)
            minute = self.roll(group, point, minutes)
            self.levels.update(self.evaluate(group))
            level = max((LEVELS.index(value) for value in self.levels.values()),
                        default=0)
            level = LEVELS[level]
            levels = dict(self.levels)
            changed, self.level = level != self.level, level
        self.publish('sample', {'group': group, 'point': point,
                                'minute': minute, 'levels': levels,
                                'level': level})
        if changed:
            self.publish('level', {'level': level})

    def roll(self, group, point, size):
        """Add the point to its minute; get the previous minute's aggregate
        when the point starts a new one, else None.
        """
        bucket = self.buckets[group]
        minute = None
        if bucket and bucket[0]['t'][:16] != point['t'][:16]:
            minute = aggregate(bucket, bucket[0]['t'][:16] + ':30')
            history = self.minutes[group]
            if history.maxlen != size:
                history = self.minutes[group] = collections.deque(
                    history, maxlen=size)
            history.append(minute)
            bucket = self.buckets[group] = []
            self.keep(group, minute)
        bucket.append(point)
        return minute

    def keep(self, group, minute):
        """Hand a closed minute to the writer; dropped when it lags behind."""
        try:
            self.queue.put_nowait((group, minute))
        except queue.Full:
            pass

    def write(self):
        """Store the closed minutes, read the stored ones back first, and
        purge those older than history_days every hour.
        """
        self.server = store.server_name()
        self.load()
        purged = 0
        while not self.stopping.is_set():
            rows = []
            try:
                rows.append(self.queue.get(timeout=5))
                while len(rows) < 100:
                    rows.append(self.queue.get_nowait())
            except queue.Empty:
                pass
            if rows:
                self.attempt('stored', store.write, self.server, rows)
            if time.monotonic() - purged > PURGE_SECONDS:
                purged = time.monotonic()
                before = (dt.datetime.now()
                          - dt.timedelta(days=option('history_days')))
                self.attempt('purged', store.purge, before)

    def load(self):
        """Put the stored minutes of this server's last history_hours before
        the ones of this run, so that a restart loses nothing.
        """
        since = dt.datetime.now() - dt.timedelta(hours=option('history_hours'))
        for group in GROUPS:
            rows = self.attempt('read', store.read, self.server, group, since)
            if not rows:
                continue
            size = option('history_hours') * 60
            with self.lock:
                current = list(self.minutes[group])
                first = current[0]['t'] if current else None
                older = [row for row in rows if first is None or row['t'] < first]
                self.minutes[group] = collections.deque(older + current,
                                                        maxlen=size)
            logger.debug(f'Instance health: {len(older)} {group} minutes '
                         'read back')

    def attempt(self, what, function, *args):
        """Call a store function; its failure is logged once until it works
        again (the table missing before the upgrade, a database outage).
        """
        try:
            result = function(*args)
        except Exception as error:
            message = str(error).splitlines()[0]
            if self.store_error is None:
                logger.warning(f'Instance health: minutes not {what}, kept '
                               f'in memory only: {message}')
            self.store_error = message
            return None
        if self.store_error is not None:
            logger.info('Instance health: minutes stored again')
            self.store_error = None
        return result

    def evaluate(self, group):
        """Get {rule: level} of the group's rules for its latest points."""
        output = {}
        limits = thresholds()
        points = self.points[group]
        for rule, (rule_group, field, smooth) in RULES.items():
            if rule_group != group:
                continue
            values = [point.get(field) for point in list(points)[-smooth:]]
            values = [value for value in values if value is not None]
            if not values:
                output[rule] = None
                continue
            value = sum(values) / len(values)
            warn, crit = limits[rule]
            if crit is not None and value >= crit:
                output[rule] = 'crit'
            elif warn is not None and value >= warn:
                output[rule] = 'warn'
            else:
                output[rule] = None
        return output

    def publish(self, kind, payload):
        for listener in self.listeners:
            try:
                listener(kind, payload)
            except Exception:
                logger.error()

    def spans(self):
        return ([hours for hours in SPANS if hours <= option('history_hours')]
                + [hours for hours in LONG_SPANS
                   if hours <= option('history_days') * 24])

    def stored_minutes(self, hours):
        """Get the stored minutes of this server's os and db groups for a
        span longer than the memory's, kept for STORED_SECONDS.
        """
        cached = self.stored.get(hours)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        since = dt.datetime.now() - dt.timedelta(hours=hours)
        minutes = {group: self.attempt('read', store.read, self.server or
                                       store.server_name(), group, since)
                   or [] for group in ('os', 'db')}
        self.stored[hours] = (time.monotonic() + STORED_SECONDS, minutes)
        return minutes

    def snapshot(self, history=True, hours=1):
        """Get the state for the UI: the points of the last `hours`, levels
        and DB access. Only the levels without `history`. Spans longer than
        history_hours are read from the stored minutes.
        """
        stored = None
        if history:
            spans = self.spans()
            hours = min(max(int(hours), 1), max(spans, default=1))
            if hours > option('history_hours'):
                stored = self.stored_minutes(hours)
        with self.lock:
            output = {
                'enabled': option('enabled'),
                'server_time': now(),
                'level': self.level,
                'levels': dict(self.levels),
            }
            if not history:
                return output
            probe = self.probe_errors or {}
            intervals = {group: option(f'{group}_interval')
                         for group in ('os', 'db')}
            output.update({
                'labels': sources.labels(),
                'intervals': intervals,
                'history_minutes': option('history_minutes'),
                'hours': hours,
                'spans': spans,
                'thresholds': thresholds(),
                'footprint': self.footprint,
                'access': {name: {'grant': grant, 'error': probe.get(name),
                                  'probed': name in probe}
                           for name, (grant, _) in sources.DB_SOURCES.items()},
            })
            size = math.ceil(hours * 60 / MAX_POINTS)
            output['step'] = {}
            since = []
            for group in ('os', 'db'):
                points = self.points[group]
                minutes = self.minutes[group]
                if points:
                    since.append(points[0]['t'])
                if minutes:
                    since.append(minutes[0]['t'][:16] + ':00')
                if hours == 1:
                    output[group] = list(points)
                    output['step'][group] = intervals[group]
                    continue
                start = (dt.datetime.now() - dt.timedelta(hours=hours)
                         ).isoformat(timespec='seconds')
                selected = [point for point in minutes if point['t'] >= start]
                if stored is not None:
                    # The stored minutes, then those of memory not stored yet.
                    older = stored[group]
                    last = older[-1]['t'] if older else ''
                    selected = older + [point for point in selected
                                        if point['t'] > last]
                    if older:
                        since.append(older[0]['t'][:16] + ':00')
                bucket = self.buckets[group]
                # The minute in progress, which its first aggregate replaces.
                if bucket:
                    selected.append(aggregate(bucket,
                                              bucket[0]['t'][:16] + ':30'))
                output[group] = merge(selected, size)
                output['step'][group] = size * 60
            output['history_since'] = min(since) if since else None
            return output


def files_point(time_text):
    """Get the files waiting in the input directories of the active
    datasources as the last scan counted them, or None when no scan is
    recent (nobody looks and no idle scans).
    """
    from ..pdi import files as pdi_files
    from ..pdi import scanner
    snapshot = scanner.status()
    if not snapshot or 'scanned_epoch' not in snapshot:
        return None
    interval = max(pdi_files.number_option('scan_interval'),
                   pdi_files.number_option('scan_idle_interval'))
    if time.time() - snapshot['scanned_epoch'] > 2 * interval + 60:
        return None
    states = [state for state in snapshot.get('datasources', {}).values()
              if isinstance(state, dict)]
    oldest = [state['oldest'] for state in states if state.get('oldest')]
    return {'t': time_text,
            'waiting': sum(state.get('waiting') or 0 for state in states),
            'datasources_waiting': len([state for state in states
                                        if state.get('waiting')]),
            'stalled': len([state for state in states
                            if state.get('stalled')]),
            'oldest_age': (round(time.time() - min(oldest)) if oldest
                           else None)}


sampler = Sampler()
