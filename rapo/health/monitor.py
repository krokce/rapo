"""Contains the instance health sampler.

Samples the OS and DB metrics in threads of the web server, keeping the last
`history_minutes` of the samples and `history_hours` of their one-minute
aggregates in memory for the Instance details dialog. Nothing is stored: the
history starts anew with the server.
"""

import collections
import datetime as dt
import math
import threading
import time

from ..config import config
from .. import options
from ..logger import logger

from . import sources


OPTIONS = {name: options.default('HEALTH', name) for name in (
    'enabled', 'os_interval', 'db_interval', 'footprint_interval',
    'history_minutes', 'history_hours')}

# The spans the UI offers, in hours, up to history_hours; 1 shows the samples,
# longer ones the minute aggregates merged into at most MAX_POINTS points.
SPANS = (1, 3, 6, 12, 24)
MAX_POINTS = 480
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
        self.minutes = {'os': collections.deque(), 'db': collections.deque()}
        self.buckets = {'os': [], 'db': []}
        self.footprint = None
        self.footprint_time = 0
        self.probe_errors = None
        self.probe_time = 0
        self.levels = {}
        self.level = None
        self.listeners = []

    def start(self):
        """Start sampling in threads of their own."""
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
            self.levels = {}
            changed, self.level = self.level is not None, None
        if changed:
            self.publish('level', {'level': None})

    def sample_os(self):
        point = {'t': now(), **sources.read_os()}
        self.add('os', point)

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
        bucket.append(point)
        return minute

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
        return [hours for hours in SPANS if hours <= option('history_hours')]

    def snapshot(self, history=True, hours=1):
        """Get the state for the UI: the points of the last `hours`, levels
        and DB access. Only the levels without `history`.
        """
        with self.lock:
            output = {
                'enabled': option('enabled'),
                'server_time': now(),
                'level': self.level,
                'levels': dict(self.levels),
            }
            if not history:
                return output
            spans = self.spans()
            hours = min(max(int(hours), 1), max(spans, default=1))
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
                bucket = self.buckets[group]
                # The minute in progress, which its first aggregate replaces.
                if bucket:
                    selected.append(aggregate(bucket,
                                              bucket[0]['t'][:16] + ':30'))
                output[group] = merge(selected, size)
                output['step'][group] = size * 60
            output['history_since'] = min(since) if since else None
            return output


sampler = Sampler()
