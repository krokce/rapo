"""Contains the files waiting in the input directories of the datasources.

The directories are read from the file system of this server, so they must be
local to it or mounted, the way PDI Core sees them. A mask is matched against
the whole file name (Java's matches() in PDI Core, re.fullmatch here), and the
subdirectories of an input directory are walked only when INPUT_SCAN_SUBDIRS
is set.
"""

import concurrent.futures
import datetime as dt
import functools
import grp
import json
import os
import pwd
import re
import select
import stat
import subprocess
import sys
import threading
import time

from ..config import config
from ..logger import logger

from .store import pdi, DatasourceError, split_directories
from .scan_worker import PDI_CLEAN_BYTES, YOUNG_SECONDS, walk

WORKER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'scan_worker.py')
# Seconds a directory check of the editor may take before it says unknown,
# and the threads doing them (a check hung on the network file system keeps
# its thread, not the request).
CHECK_SECONDS = 5
check_pool = concurrent.futures.ThreadPoolExecutor(
    max_workers=8, thread_name_prefix='rapo-ds-check')

OPTIONS = {
    'scan_interval': 60,
    'scan_max_entries': 200000,
    'scan_budget_seconds': 20,
    'list_max_files': 10000,
    'list_budget_seconds': 10,
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
    # A listing asked for from the page stops reading at the budget, cut like
    # a capped one, rather than keep a request waiting on a slow directory.
    deadline = time.monotonic() + max(number_option('list_budget_seconds'), 1)
    now = time.time()
    result = {'files': [], 'directories': [], 'truncated': False,
              'total': 0, 'matched': 0, 'clean': 0,
              'mask_error': match_error, 'clean_mask_error': clean_error,
              'clean_max_bytes': clean_max, 'pdi_clean_bytes': PDI_CLEAN_BYTES,
              'young_seconds': YOUNG_SECONDS, 'subdirs': subdirs,
              'server_time': dt.datetime.now().replace(microsecond=0)}
    for root in split_directories(row['input_directory']):
        entries, state = walk(root, recursive=subdirs or kind == 'all',
                              cap=cap, deadline=deadline)
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


def directories_of(row):
    """Get the directories of a datasource: [(field, path)]."""
    paths = [('input_directory', root)
             for root in split_directories(row['input_directory'])]
    paths += [(name, row[name]) for name in OTHER_DIRECTORIES if row.get(name)]
    return paths


def check_directories(row):
    """Get whether each directory of a datasource exists, now.

    Each check may take CHECK_SECONDS, after which its state is unknown
    (`exists` None), so that a hung network file system delays the answer by
    seconds at most.
    """
    paths = directories_of(row)
    futures = [check_pool.submit(directory_state, field, path)
               for field, path in paths]
    deadline = time.monotonic() + CHECK_SECONDS
    states = []
    for (field, path), future in zip(paths, futures):
        try:
            states.append(future.result(
                timeout=max(deadline - time.monotonic(), 0.01)))
        except concurrent.futures.TimeoutError:
            states.append({'field': field, 'path': path, 'exists': None,
                           'writable': None})
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
    with scanner.lock:
        for created in missing:
            scanner.paths[created] = {'exists': True, 'writable': os.access(
                created, os.W_OK | os.X_OK)}
    scanner.poke()
    return list(reversed(missing))


class Scanner:
    """Counts the files waiting for every active datasource, in the background.

    Runs while UI clients are connected, every [DATASOURCES] scan_interval
    seconds; disabled datasources (ISACTIVE 0) are not read. The directories
    are read by a child process (scan_worker.py, standard library only), so
    that a slow or hung network file system never holds up the web API: the
    thread here only reads the datasources and the file log, sends the child
    the directories and masks, and waits for its counts.

    Each input directory is read once per scan, and each file name tested once
    per distinct mask of the directory. A scan stops reading at
    scan_budget_seconds: the directories left out are read first next time,
    and their datasources keep their previous counts meanwhile, marked stale.
    A child not answering within the budget and 30 seconds is killed and
    started anew; one that died is started anew at the next scan.
    """

    GRACE_SECONDS = 30

    def __init__(self):
        self.thread = None
        self.stopping = threading.Event()
        self.wake = threading.Event()
        self.lock = threading.Lock()
        self.snapshot = None
        self.digest = None
        self.scanned = {}
        # {path: {exists, writable}} of the directories last read or checked.
        self.paths = {}
        self.process = None
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
        """Stop scanning and the child process."""
        self.stopping.set()
        self.wake.set()
        if self.thread is not None:
            self.thread.join(timeout=10)
        self.thread = None
        self.stop_process()

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

    def directory_states(self, row):
        """Get whether the directories of a datasource exist, as last read.

        None when one of them was not read (a disabled datasource, a path just
        saved), for the caller to check them itself.
        """
        with self.lock:
            paths = dict(self.paths)
        states = []
        for field, path in directories_of(row):
            known = paths.get(path)
            if known is None:
                return None
            states.append({'field': field, 'path': path, **known})
        return states

    def start_process(self):
        """Start the child reading the directories, if it is not running."""
        if self.process is not None and self.process.poll() is None:
            return self.process
        if self.process is not None:
            logger.warning(f'Directory scanner process ended with code '
                           f'{self.process.returncode}, starting it anew')
        self.process = subprocess.Popen(
            [sys.executable, '-u', WORKER_PATH], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            bufsize=1, close_fds=True)
        logger.debug(f'Directory scanner process started as PID '
                     f'{self.process.pid}')
        return self.process

    def stop_process(self, kill=False):
        """End the child: close its input, or kill it."""
        process, self.process = self.process, None
        if process is None:
            return
        try:
            if kill:
                process.kill()
            else:
                process.stdin.close()
            process.wait(timeout=3)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    def ask(self, request, timeout):
        """Send the child one request and wait for its answer.

        Raises TimeoutError when none comes in time; the child is then killed
        (a read hung on the file system can not be interrupted otherwise).
        """
        process = self.start_process()
        try:
            process.stdin.write(json.dumps(request) + '\n')
            process.stdin.flush()
            ready, _, _ = select.select([process.stdout], [], [], timeout)
            line = process.stdout.readline() if ready else None
        except (BrokenPipeError, OSError, ValueError) as error:
            self.stop_process(kill=True)
            raise RuntimeError(f'Directory scanner process failed: '
                               f'{error}') from error
        if line is None:
            self.stop_process(kill=True)
            raise TimeoutError(f'Directory scanner process did not answer '
                               f'in {timeout:.0f} s')
        if not line:
            self.stop_process(kill=True)
            raise RuntimeError('Directory scanner process ended')
        answer = json.loads(line)
        if not answer.get('ok'):
            raise RuntimeError(answer.get('error'))
        return answer['result']

    def scan(self):
        """Count the waiting files of every active datasource once."""
        if not pdi.available:
            return
        started = time.monotonic()
        rows = [row for row in pdi.read_datasources() if row['isactive']]
        previous = (self.snapshot or {}).get('datasources', {})
        clean_max = number_option('clean_max_bytes')
        # The directories to read, and the distinct masks of each: one spec
        # per (kind, mask, subdirs), shared by the datasources using it.
        roots, specs, spec_index, plans = {}, {}, {}, {}
        others = set()
        for row in rows:
            plan = {'roots': [], 'errors': {}}
            subdirs = bool(row['input_scan_subdirs'])
            for kind, mask in (('match', row['files_mask']),
                               ('clean', row['input_clean_files_mask'])):
                _, error = compile_mask(mask)
                plan['errors'][kind] = error
            for root in split_directories(row['input_directory']):
                roots[root] = roots.get(root, False) or subdirs
                indexes = {}
                for kind, mask in (('match', row['files_mask']),
                                   ('clean', row['input_clean_files_mask'])):
                    if not mask or plan['errors'][kind]:
                        continue
                    key = (root, kind, mask, subdirs)
                    if key not in spec_index:
                        spec_index[key] = len(specs.setdefault(root, []))
                        specs[root].append({'kind': kind, 'mask': mask,
                                            'subdirs': subdirs})
                    indexes[kind] = spec_index[key]
                plan['roots'].append((root, indexes))
            others.update(row[name] for name in OTHER_DIRECTORIES
                          if row.get(name))
            plans[row['id']] = plan
        # The directories read longest ago first, so that a scan cut short by
        # its budget moves on to the others next time.
        order = sorted(roots, key=lambda root: self.scanned.get(root, 0))
        budget = max(number_option('scan_budget_seconds'), 1)
        request = {'roots': [[root, roots[root]] for root in order],
                   'specs': specs, 'others': sorted(others), 'budget': budget,
                   'cap': number_option('scan_max_entries'),
                   'clean_max': clean_max}
        try:
            answer = self.ask(request, budget + self.GRACE_SECONDS)
        except (TimeoutError, RuntimeError) as error:
            logger.warning(f'{error}; the counts of {len(rows)} datasource(s) '
                           'are kept from the previous scan, marked stale')
            answer = {'roots': {}, 'paths': {}}
        read = answer['roots']
        now = time.time()
        for root in read:
            self.scanned[root] = time.monotonic()
        with self.lock:
            self.paths.update(answer['paths'])
            paths = dict(self.paths)
        stalled_seconds = number_option('stalled_minutes') * 60
        try:
            stats = pdi.read_file_log_stats()
        except Exception:
            logger.error()
            stats = {}
        datasources = {}
        for row in rows:
            id = row['id']
            plan = plans[id]
            if all(root in read for root, _ in plan['roots']):
                state = self.count(plan, read)
            else:
                state = dict(previous.get(str(id)) or {}, stale=True)
            state['missing_other'] = [
                name for name in OTHER_DIRECTORIES if row.get(name)
                and (paths.get(row[name]) or {}).get('exists') is False]
            oldest = state.get('oldest')
            state['stalled'] = bool(
                state.get('waiting') and oldest is not None
                and now - oldest > stalled_seconds)
            state['log'] = stats.get(id)
            datasources[str(id)] = state
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

    def count(self, plan, read):
        """Sum the counts of one datasource over its input directories."""
        state = {'waiting': 0, 'bytes': 0, 'young': 0, 'clean': 0,
                 'pdi_clean': 0, 'oldest': None, 'capped': False,
                 'stale': False, 'missing': [], 'unreadable': [],
                 'mask_error': plan['errors']['match'],
                 'clean_mask_error': plan['errors']['clean']}
        for root, indexes in plan['roots']:
            directory = read[root]['state']
            counts = read[root]['counts']
            if not directory['exists']:
                state['missing'].append(root)
            elif not directory['readable']:
                state['unreadable'].append(root)
            state['capped'] = state['capped'] or directory['capped']
            if 'match' in indexes:
                count = counts[indexes['match']]
                for key in ('waiting', 'bytes', 'young'):
                    state[key] += count[key]
                if count['oldest'] is not None and (
                        state['oldest'] is None
                        or count['oldest'] < state['oldest']):
                    state['oldest'] = count['oldest']
            if 'clean' in indexes:
                count = counts[indexes['clean']]
                state['clean'] += count['clean']
                state['pdi_clean'] += count['pdi_clean']
        if state['oldest'] is not None:
            state['oldest_at'] = dt.datetime.fromtimestamp(state['oldest'])
        return state


scanner = Scanner()
