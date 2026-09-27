"""Contains the reading of input directories, also as a process of its own.

The web server counts the files waiting in the input directories of the PDI
Core datasources (files.Scanner) in a child process running this file as a
script, so that neither a slow nor a hung network file system can hold up
the web API, nor the Python work of a scan compete with it. The file uses the
standard library only: run by its path it imports nothing of rapo, so the
process stays small and never connects to the database.

The protocol is one JSON line per request on stdin and one per answer on
stdout. The process ends when stdin closes, i.e. when the web server is gone.
"""

import json
import os
import re
import sys
import time


# PDI Core skips a file modified less than this many seconds ago (it may still
# be uploading), and its clean-up deletes only files smaller than this.
YOUNG_SECONDS = 60
PDI_CLEAN_BYTES = 10


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


def path_state(path):
    """Whether a directory exists and rapo may write in it."""
    exists = os.path.isdir(path)
    return {'exists': exists,
            'writable': exists and os.access(path, os.W_OK | os.X_OK)}


def scan(request):
    """Read the input directories of a request and count their files.

    Parameters
    ----------
    request : dict
        `roots`, `[[path, recursive], ...]` in the order to read them;
        `specs`, by path, the masks to count: `[{kind, mask, subdirs}]`, kind
        `match` (count, bytes, young, oldest) or `clean` (small files);
        `others`, more directories whose existence is wanted; `budget`
        (seconds), `cap` (files per directory) and `clean_max` (bytes).

    Returns
    -------
    answer : dict
        `roots`, by path, `{state, counts}` for each directory read, counts
        in the order of its specs; `paths`, `{exists, writable}` by path of
        the directories read and of `others` checked in time.
    """
    started = time.monotonic()
    deadline = started + request['budget']
    now = time.time()
    clean_max = request['clean_max']
    roots = {}
    paths = {}
    for root, recursive in request['roots']:
        if time.monotonic() > deadline:
            break
        entries, state = walk(root, recursive, request['cap'], deadline)
        specs = request['specs'].get(root, [])
        compiled = [re.compile(spec['mask']) for spec in specs]
        counts = []
        for spec in specs:
            if spec['kind'] == 'match':
                counts.append({'waiting': 0, 'bytes': 0, 'young': 0,
                               'oldest': None})
            else:
                counts.append({'clean': 0, 'pdi_clean': 0})
        # Each name is tested once against every distinct mask of the
        # directory, however many datasources share it.
        for name, subdir, info in entries:
            for spec, pattern, count in zip(specs, compiled, counts):
                if subdir and not spec['subdirs']:
                    continue
                if spec['kind'] == 'match':
                    if pattern.fullmatch(name):
                        count['waiting'] += 1
                        count['bytes'] += info.st_size
                        if now - info.st_mtime < YOUNG_SECONDS:
                            count['young'] += 1
                        if (count['oldest'] is None
                                or info.st_mtime < count['oldest']):
                            count['oldest'] = int(info.st_mtime)
                elif info.st_size < clean_max and pattern.fullmatch(name):
                    count['clean'] += 1
                    if info.st_size < PDI_CLEAN_BYTES:
                        count['pdi_clean'] += 1
        roots[root] = {'state': state, 'counts': counts}
        paths[root] = {'exists': state['exists'],
                       'writable': state['exists'] and os.access(
                           root, os.W_OK | os.X_OK)}
    for path in request.get('others', []):
        if time.monotonic() > deadline:
            break
        paths[path] = path_state(path)
    return {'roots': roots, 'paths': paths,
            'duration': round(time.monotonic() - started, 2)}


def serve():
    """Answer requests from stdin until it closes."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            answer = {'ok': True, 'result': scan(json.loads(line))}
        except Exception as error:
            answer = {'ok': False, 'error': f'{type(error).__name__}: {error}'}
        sys.stdout.write(json.dumps(answer) + '\n')
        sys.stdout.flush()


if __name__ == '__main__':
    serve()
