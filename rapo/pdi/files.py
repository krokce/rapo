"""Contains the files waiting in the input directories of the datasources.

The directories are read from the file system of this server, so they must be
local to it or mounted, the way PDI Core sees them. A mask is matched against
the whole file name (Java's matches() in PDI Core, re.fullmatch here), and the
subdirectories of an input directory are walked only when INPUT_SCAN_SUBDIRS
is set.
"""

import datetime as dt
import functools
import grp
import json
import os
import pwd
import re
import stat
import threading
import time

from ..config import config
from ..logger import logger

from .store import pdi, DatasourceError, split_directories


# PDI Core skips a file modified less than this many seconds ago (it may still
# be uploading), and its clean-up deletes only files smaller than this.
YOUNG_SECONDS = 60
PDI_CLEAN_BYTES = 10

OPTIONS = {
    'scan_interval': 60,
    'scan_max_entries': 200000,
    'scan_budget_seconds': 20,
    'list_max_files': 10000,
    'clean_max_bytes': 1024,
    'dir_mode': '2775',
    'stalled_minutes': 60,
    'lock_stale_minutes': 30,
}

OTHER_DIRECTORIES = ('archive_directory', 'error_directory',
                     'duplicate_directory')


def option(name):
    """Get a [DATASOURCES] option of rapo.ini, read at use so it reloads."""
    section = config.get('DATASOURCES') or {}
    value = section.get(name)
    return OPTIONS[name] if value is None else value


def number_option(name):
    """Get a numeric [DATASOURCES] option, its default when not a number."""
    try:
        return max(int(option(name)), 0)
    except (TypeError, ValueError):
        return OPTIONS[name]


def dir_mode():
    """Get the mode of created directories, written in octal (2775)."""
    text = str(option('dir_mode')).strip().lower().removeprefix('0o')
    try:
        return int(text, 8)
    except ValueError:
        return int(OPTIONS['dir_mode'], 8)


def compile_mask(mask):
    """Get a mask as a compiled expression and the error when it is none."""
    if not mask:
        return None, None
    try:
        return re.compile(mask), None
    except (re.error, TypeError) as error:
        return None, str(error)


@functools.lru_cache(maxsize=256)
def user_name(uid):
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)


@functools.lru_cache(maxsize=256)
def group_name(gid):
    try:
        return grp.getgrgid(gid).gr_name
    except KeyError:
        return str(gid)


def walk(root, recursive, cap, deadline=None):
    """Read the files of one directory, and of its subdirectories.

    Returns
    -------
    files : list of tuple
        (name, subdir, os.stat_result), subdir '' for the directory itself.
    state : dict
        `path`, `exists`, `readable`, `capped` (stopped at `cap` files or at
        the deadline) and `error`.
    """
    state = {'path': root, 'exists': True, 'readable': True, 'capped': False,
             'error': None}
    files = []
    stack = [(root, '')]
    while stack:
        path, subdir = stack.pop()
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    if len(files) >= cap or (deadline is not None
                                             and time.monotonic() > deadline):
                        state['capped'] = True
                        return files, state
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if recursive:
                                stack.append((entry.path, os.path.join(
                                    subdir, entry.name)))
                        elif entry.is_file():
                            files.append((entry.name, subdir, entry.stat()))
                    except OSError:
                        continue
        except FileNotFoundError:
            if not subdir:
                state['exists'] = False
                return files, state
        except NotADirectoryError:
            if not subdir:
                state['exists'] = False
                state['error'] = 'Not a directory'
                return files, state
        except PermissionError as error:
            if not subdir:
                state['readable'] = False
                state['error'] = error.strerror
                return files, state
        except OSError as error:
            if not subdir:
                state['readable'] = False
                state['error'] = error.strerror or str(error)
                return files, state
    return files, state


def list_files(row, kind='match', files_mask=None, clean_mask=None,
               subdirs=None):
    """Get the files of a datasource's input directories.

    Parameters
    ----------
    row : dict
        The saved datasource, whose input directories are read.
    kind : str
        `match` the files FILES_MASK picks up, `clean` the small files
        INPUT_CLEAN_FILES_MASK names, `all` every file, with why it is not
        picked up.
    files_mask, clean_mask, subdirs : optional
        The editor's values, to try them on the directories before a save.
    """
    if kind not in ('match', 'clean', 'all'):
        raise DatasourceError('kind must be match, clean or all.')
    files_mask = row['files_mask'] if files_mask is None else files_mask
    clean_mask = (row['input_clean_files_mask'] if clean_mask is None
                  else clean_mask)
    subdirs = bool(row['input_scan_subdirs'] if subdirs is None else subdirs)
    match, match_error = compile_mask(files_mask)
    clean, clean_error = compile_mask(clean_mask)
    clean_max = number_option('clean_max_bytes')
    limit = number_option('list_max_files')
    cap = number_option('scan_max_entries')
    now = time.time()
    result = {'files': [], 'directories': [], 'truncated': False,
              'total': 0, 'matched': 0, 'clean': 0,
              'mask_error': match_error, 'clean_mask_error': clean_error,
              'clean_max_bytes': clean_max, 'pdi_clean_bytes': PDI_CLEAN_BYTES,
              'young_seconds': YOUNG_SECONDS, 'subdirs': subdirs,
              'server_time': dt.datetime.now().replace(microsecond=0)}
    for root in split_directories(row['input_directory']):
        entries, state = walk(root, recursive=subdirs or kind == 'all',
                              cap=cap)
        result['directories'].append(state)
        result['truncated'] = result['truncated'] or state['capped']
        for name, subdir, info in entries:
            scanned = subdirs or not subdir
            matches = bool(scanned and match and match.fullmatch(name))
            is_clean = bool(scanned and clean and clean.fullmatch(name)
                            and info.st_size < clean_max)
            result['total'] += 1
            result['matched'] += matches
            result['clean'] += is_clean
            if kind == 'match' and not matches:
                continue
            if kind == 'clean' and not is_clean:
                continue
            if matches:
                reason = 'Matches FILES_MASK'
            elif not scanned:
                reason = 'In a subdirectory, INPUT_SCAN_SUBDIRS is off'
            elif is_clean:
                reason = 'Clean-up file of INPUT_CLEAN_FILES_MASK'
            elif match is None:
                reason = 'FILES_MASK is not valid'
            else:
                reason = 'Name does not match FILES_MASK'
            result['files'].append({
                'name': name,
                'directory': root,
                'subdir': subdir,
                'path': os.path.join(root, subdir, name),
                'size': info.st_size,
                'modified': dt.datetime.fromtimestamp(
                    int(info.st_mtime)),
                'age': max(int(now - info.st_mtime), 0),
                'owner': user_name(info.st_uid),
                'group': group_name(info.st_gid),
                'mode': stat.filemode(info.st_mode),
                'matches': matches,
                'clean': is_clean,
                'pdi_deletes': is_clean and info.st_size < PDI_CLEAN_BYTES,
                'young': now - info.st_mtime < YOUNG_SECONDS,
                'reason': reason,
            })
    # The oldest first: they have waited longest.
    result['files'].sort(key=lambda file: (file['modified'], file['path']))
    if len(result['files']) > limit:
        result['files'] = result['files'][:limit]
        result['truncated'] = True
    return result


def check_directories(row):
    """Get whether each directory of a datasource exists."""
    states = []
    for root in split_directories(row['input_directory']):
        states.append(directory_state('input_directory', root))
    for name in OTHER_DIRECTORIES:
        if row.get(name):
            states.append(directory_state(name, row[name]))
    return states


def directory_state(field, path):
    exists = os.path.isdir(path)
    return {'field': field, 'path': path, 'exists': exists,
            'writable': exists and os.access(path, os.W_OK | os.X_OK)}


def create_directory(row, path):
    """Create one missing directory of a saved datasource.

    Only a directory the datasource names can be created, with every missing
    parent, each with the mode of [DATASOURCES] dir_mode (umask ignored).
    """
    path = (path or '').strip()
    allowed = split_directories(row['input_directory'])
    allowed += [row[name] for name in OTHER_DIRECTORIES if row.get(name)]
    if path not in allowed:
        raise DatasourceError(f'{path} is no directory of datasource '
                              f'{row["sourcename"]}. Save it first.')
    if not path.startswith('/') or '..' in path.split('/'):
        raise DatasourceError(f'{path} is not an absolute path.')
    if os.path.isdir(path):
        raise DatasourceError(f'{path} already exists.')
    missing = []
    current = path.rstrip('/') or '/'
    while current and not os.path.exists(current):
        missing.append(current)
        current = os.path.dirname(current)
    mode = dir_mode()
    try:
        for directory in reversed(missing):
            os.mkdir(directory)
            os.chmod(directory, mode)
    except OSError as error:
        raise DatasourceError(f'{path} was not created: '
                              f'{error.strerror or error}.') from error
    logger.info(f'Directory {path} of datasource {row["sourcename"]} created '
                f'with mode {oct(mode)[2:]}')
    scanner.poke()
    return list(reversed(missing))


class Scanner:
    """Counts the files waiting for every datasource, in the background.

    Runs in the web server while UI clients are connected, every
    [DATASOURCES] scan_interval seconds. Each input directory is read once
    per scan, however many datasources share it, and a scan stops reading at
    scan_budget_seconds: the directories left out are read first next time,
    and their datasources keep their previous counts meanwhile, marked stale.
    """

    def __init__(self):
        self.thread = None
        self.stopping = threading.Event()
        self.wake = threading.Event()
        self.lock = threading.Lock()
        self.snapshot = None
        self.digest = None
        self.scanned = {}
        self.listeners = []
        self.active = lambda: True

    def start(self):
        """Start scanning in a thread of its own."""
        if self.thread is not None:
            return
        self.stopping.clear()
        self.thread = threading.Thread(target=self.run, name='rapo-ds-scanner',
                                       daemon=True)
        self.thread.start()

    def stop(self):
        """Stop scanning."""
        self.stopping.set()
        self.wake.set()
        if self.thread is not None:
            self.thread.join(timeout=10)
        self.thread = None

    def poke(self):
        """Scan now, e.g. when a client connects or a datasource is saved."""
        self.wake.set()

    def run(self):
        while not self.stopping.is_set():
            if self.active():
                try:
                    self.scan()
                except Exception:
                    logger.error()
            self.wake.wait(max(number_option('scan_interval'), 5))
            self.wake.clear()

    def status(self):
        """Get the last scan, or None before the first one."""
        with self.lock:
            return self.snapshot

    def scan(self):
        """Count the waiting files of every datasource once."""
        if not pdi.available:
            return
        started = time.monotonic()
        rows = pdi.read_datasources()
        previous = (self.snapshot or {}).get('datasources', {})
        roots = {}
        for row in rows:
            for root in split_directories(row['input_directory']):
                roots[root] = roots.get(root, False) or bool(
                    row['input_scan_subdirs'])
        # The directories scanned longest ago first, so that a scan cut short
        # by its budget moves on to the others next time.
        order = sorted(roots, key=lambda root: self.scanned.get(root, 0))
        deadline = started + number_option('scan_budget_seconds')
        cap = number_option('scan_max_entries')
        walked = {}
        for root in order:
            if time.monotonic() > deadline:
                break
            walked[root] = walk(root, roots[root], cap, deadline)
            self.scanned[root] = time.monotonic()
        now = time.time()
        others = {}
        stalled_seconds = number_option('stalled_minutes') * 60
        clean_max = number_option('clean_max_bytes')
        try:
            stats = pdi.read_file_log_stats()
        except Exception:
            logger.error()
            stats = {}
        datasources = {}
        for row in rows:
            id = row['id']
            key = str(id)
            state = self.count(row, walked, now, clean_max)
            if state is None:
                state = dict(previous.get(key) or {}, stale=True)
            for name in OTHER_DIRECTORIES:
                path = row.get(name)
                if path and path not in others:
                    others[path] = os.path.isdir(path)
            state['missing_other'] = [name for name in OTHER_DIRECTORIES
                                      if row.get(name)
                                      and not others[row[name]]]
            oldest = state.get('oldest')
            state['stalled'] = bool(
                row['isactive'] and state.get('waiting')
                and oldest is not None and now - oldest > stalled_seconds)
            state['log'] = stats.get(id)
            datasources[key] = state
        digest = json.dumps(datasources, sort_keys=True, default=str)
        snapshot = {
            'scanned_at': dt.datetime.now().replace(microsecond=0),
            'scanned_epoch': int(now),
            'database_time': pdi.read_database_time(),
            'duration': round(time.monotonic() - started, 2),
            'interval': number_option('scan_interval'),
            'stalled_minutes': number_option('stalled_minutes'),
            'clean_max_bytes': clean_max,
            'datasources': datasources,
        }
        with self.lock:
            self.snapshot = snapshot
            changed, self.digest = digest != self.digest, digest
        if changed:
            for listener in self.listeners:
                listener()

    def count(self, row, walked, now, clean_max):
        """Count the waiting files of one datasource, None when not read."""
        roots = split_directories(row['input_directory'])
        if any(root not in walked for root in roots):
            return None
        match, match_error = compile_mask(row['files_mask'])
        clean, clean_error = compile_mask(row['input_clean_files_mask'])
        subdirs = bool(row['input_scan_subdirs'])
        state = {'waiting': 0, 'bytes': 0, 'young': 0, 'clean': 0,
                 'pdi_clean': 0, 'oldest': None, 'capped': False,
                 'stale': False, 'missing': [], 'unreadable': [],
                 'mask_error': match_error, 'clean_mask_error': clean_error}
        for root in roots:
            entries, directory = walked[root]
            if not directory['exists']:
                state['missing'].append(root)
            elif not directory['readable']:
                state['unreadable'].append(root)
            state['capped'] = state['capped'] or directory['capped']
            for name, subdir, info in entries:
                if subdir and not subdirs:
                    continue
                if match and match.fullmatch(name):
                    state['waiting'] += 1
                    state['bytes'] += info.st_size
                    if now - info.st_mtime < YOUNG_SECONDS:
                        state['young'] += 1
                    if state['oldest'] is None or info.st_mtime < state[
                            'oldest']:
                        state['oldest'] = int(info.st_mtime)
                if (clean and info.st_size < clean_max
                        and clean.fullmatch(name)):
                    state['clean'] += 1
                    if info.st_size < PDI_CLEAN_BYTES:
                        state['pdi_clean'] += 1
        if state['oldest'] is not None:
            state['oldest_at'] = dt.datetime.fromtimestamp(state['oldest'])
        return state


scanner = Scanner()
