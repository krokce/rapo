"""Contains the instance health sampler.

Samples the OS and DB metrics in threads of the web server, keeping the last
`history_minutes` of them in memory for the Instance details dialog. Nothing
is stored: the history starts anew with the server.
"""

import collections
import datetime as dt
import threading
import time

from ..config import config
from ..logger import logger

from . import sources


OPTIONS = {
    'enabled': True,
    'os_interval': 10,
    'db_interval': 30,
    'footprint_interval': 600,
    'history_minutes': 60,
}

# Seconds before DB sources that could not be read are probed again, so
# that a grant given later is found without a restart.
PROBE_RETRY = 600

# Rules of the warning levels: the group and field of the value, the default
# warn and crit thresholds (a value at or above one reaches it, None never),
# and the number of latest points averaged, so a moment's peak is no alarm.
# [HEALTH] <rule>_warn and <rule>_crit override the thresholds.
RULES = {
    'cpu': ('os', 'cpu', 80, 95, 3),
    'memory': ('os', 'memory', 85, 95, 1),
    'disk': ('os', 'disk', 85, 95, 1),
    'db_cpu': ('db', 'db_cpu', 80, 95, 1),
    'db_memory': ('db', 'pga_percent', 85, 95, 1),
    'storage': ('db', 'storage', 85, 95, 1),
    'locks': ('db', 'locks', 1, None, 1),
    'locks_wait': ('db', 'locks_wait', None, 60, 1),
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
    for rule, (_, _, warn, crit, _) in RULES.items():
        values = []
        for suffix, default in (('warn', warn), ('crit', crit)):
            value = section.get(f'{rule}_{suffix}', default)
            values.append(value if isinstance(value, (int, float))
                          and not isinstance(value, bool) else default)
        output[rule] = values
    return output


def now():
    return dt.datetime.now().isoformat(timespec='seconds')


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
        with self.lock:
            points = self.points[group]
            if points.maxlen != size:
                points = self.points[group] = collections.deque(points,
                                                                maxlen=size)
            points.append(point)
            self.levels.update(self.evaluate(group))
            level = max((LEVELS.index(value) for value in self.levels.values()),
                        default=0)
            level = LEVELS[level]
            levels = dict(self.levels)
            changed, self.level = level != self.level, level
        self.publish('sample', {'group': group, 'point': point,
                                'levels': levels, 'level': level})
        if changed:
            self.publish('level', {'level': level})

    def evaluate(self, group):
        """Get {rule: level} of the group's rules for its latest points."""
        output = {}
        limits = thresholds()
        points = self.points[group]
        for rule, (rule_group, field, _, _, smooth) in RULES.items():
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

    def snapshot(self, history=True):
        """Get the state for the UI: the points, levels and DB access."""
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
            output.update({
                'intervals': {group: option(f'{group}_interval')
                              for group in ('os', 'db')},
                'history_minutes': option('history_minutes'),
                'thresholds': thresholds(),
                'os': list(self.points['os']),
                'db': list(self.points['db']),
                'footprint': self.footprint,
                'access': {name: {'grant': grant, 'error': probe.get(name),
                                  'probed': name in probe}
                           for name, (grant, _) in sources.DB_SOURCES.items()},
            })
            return output


sampler = Sampler()
