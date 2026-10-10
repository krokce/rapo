"""Contains the short-lived memory of the Dashboard's queries.

Every open Dashboard refetches on the live events, so the same aggregates are
asked for several times within seconds. A value is kept for a few seconds per
key and computed by one request at a time (the others wait for it). A live
event bumps the generation of the groups it changes, so a value computed
before the change is never handed out after it, however fresh.
"""

import collections
import threading
import time


SECONDS = 3

# The groups a kind of change makes stale. `runs`, `controls` and `scheduler`
# are the Watcher's table diffs; `files`, `summary`, `config` and `status` the
# kinds of datasources:changed.
STALE = {
    'runs': ('run_groups', 'run_tiles', 'kpi_rows'),
    'controls': ('config', 'run_groups', 'run_tiles', 'kpi_rows',
                 'scheduler'),
    'scheduler': ('scheduler',),
    'files': ('files_live', 'file_tiles', 'files_processing'),
    'summary': ('files_summary', 'file_tiles'),
    'config': ('datasources',),
    'status': ('datasources', 'files_waiting'),
}


class Memo:
    """Values by key (group, ...), each for SECONDS within its generation."""

    def __init__(self):
        self.lock = threading.Lock()
        self.locks = {}
        self.values = {}
        self.generations = collections.Counter()

    def get(self, key, compute, seconds=SECONDS):
        """Get the value of a key, computed anew when stale."""
        value = self._fresh(key)
        if value is not None:
            return value[0]
        with self.lock:
            lock = self.locks.setdefault(key, threading.Lock())
        with lock:
            value = self._fresh(key)
            if value is not None:
                return value[0]
            generation = self.generations[key[0]]
            result = compute()
            self.values[key] = (time.monotonic() + seconds, generation,
                                result)
            return result

    def _fresh(self, key):
        entry = self.values.get(key)
        if entry is None:
            return None
        expires, generation, value = entry
        if expires < time.monotonic() or generation != self.generations[key[0]]:
            return None
        return (value,)

    def invalidate(self, kind):
        """Make the values a kind of change touches stale."""
        with self.lock:
            for group in STALE.get(kind, ()):
                self.generations[group] += 1


memo = Memo()
