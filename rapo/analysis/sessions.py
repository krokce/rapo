"""Contains the analysis session manager of the web server.

A session is one analysis page open on one dataset: a spawned worker process
(`worker.py`) and the pipe to it. Sessions are private to the page that
started them, which closes its own on leave; one not asked anything for
`idle_minutes` is closed by the manager, so a closed tab frees its memory too.
They are local to the server that started them and end with it.
"""

import datetime as dt
import itertools
import multiprocessing as mp
import os
import threading as th
import time
import uuid

from ..config import config
from ..logger import logger

from . import datasets
from .worker import serve


DEFAULTS = {
    'initial_rows': 50000,
    'extend_rows': 50000,
    'max_rows': 1000000,
    'max_sessions': 4,
    'idle_minutes': 15,
    'max_memory_mb': 2048,
}
EXPIRY_INTERVAL = 30
REQUEST_TIMEOUT = 120
EXPORT_TIMEOUT = 900


def options():
    """Get the [ANALYSIS] options, read at use so a reload applies them."""
    section = config.get('ANALYSIS') or {}
    result = {}
    for name, default in DEFAULTS.items():
        value = section.get(name)
        try:
            result[name] = int(value) if value not in (None, '') else default
        except (TypeError, ValueError):
            result[name] = default
    return result


class SessionError(Exception):
    """A session request failed; `status` is the HTTP code to answer."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class Session:
    """Represents one analysis session and its worker process."""

    def __init__(self, manager, meta, sql, settings):
        self.manager = manager
        self.id = uuid.uuid4().hex
        self.meta = meta
        self.sql = sql
        self.settings = settings
        self.created = dt.datetime.now()
        self.used = time.monotonic()
        self.state = {'status': 'starting', 'step': 'Starting the worker',
                      'rows': 0, 'version': 0, 'columns': [], 'sections': []}
        self.pending = {}
        self.counter = itertools.count(1)
        self.lock = th.Lock()
        self.closed = False

        context = mp.get_context('spawn')
        self.conn, child = context.Pipe()
        self.process = context.Process(
            name=f'rapo-analysis-{self.id[:8]}', target=serve,
            args=(child, sql, settings, os.getpid()), daemon=True)
        self.process.start()
        child.close()
        self.reader = th.Thread(target=self._read, daemon=True,
                                name=f'analysis-{self.id[:8]}')
        self.reader.start()

    def describe(self):
        """Get the session as the API answers it."""
        return {'session_id': self.id, 'meta': self.meta,
                'state': self.state, 'options': self.settings}

    def request(self, command, timeout=REQUEST_TIMEOUT, **arguments):
        """Send a command to the worker and wait for its answer."""
        if self.closed:
            raise SessionError('Analysis session is closed', 404)
        self.used = time.monotonic()
        event = th.Event()
        with self.lock:
            request_id = next(self.counter)
            self.pending[request_id] = [event, None, None]
            try:
                self.conn.send((request_id, command, arguments))
            except (OSError, ValueError, BrokenPipeError):
                self.pending.pop(request_id, None)
                raise SessionError('Analysis worker is gone', 410)
        if not event.wait(timeout):
            with self.lock:
                self.pending.pop(request_id, None)
            raise SessionError(f'Analysis worker did not answer {command}',
                               504)
        _, ok, payload = self.pending.pop(request_id)
        self.used = time.monotonic()
        if not ok:
            raise SessionError(payload, 400)
        return payload

    def _read(self):
        while True:
            try:
                message = self.conn.recv()
            except (EOFError, OSError):
                break
            if message[0] == 'state':
                self.state = message[1]
                self.manager.notify(self)
            elif message[0] == 'reply':
                _, request_id, ok, payload = message
                with self.lock:
                    waiting = self.pending.get(request_id)
                    if waiting:
                        waiting[1], waiting[2] = ok, payload
                        waiting[0].set()
        # The worker is gone: fail whoever waits, and tell the page.
        with self.lock:
            for request_id, waiting in list(self.pending.items()):
                waiting[1], waiting[2] = False, 'Analysis worker is gone'
                waiting[0].set()
        if not self.closed:
            self.state = {**self.state, 'status': 'lost', 'step': None,
                          'progress': None, 'cursor_open': False,
                          'error': 'The analysis worker stopped'}
            self.manager.notify(self)
            self.manager.forget(self)

    def close(self):
        """Stop the worker, politely first."""
        if self.closed:
            return
        self.closed = True
        try:
            with self.lock:
                self.conn.send((0, 'stop', None))
        except Exception:
            pass
        self.process.join(2)
        if self.process.is_alive():
            self.process.kill()
            self.process.join(2)
        try:
            self.conn.close()
        except Exception:
            pass


class SessionManager:
    """Represents the analysis sessions of this server."""

    def __init__(self):
        self.sessions = {}
        self.lock = th.Lock()
        self.active = False
        self.thread = None
        self.stop_event = th.Event()
        self.listeners = []

    def start(self):
        """Start closing idle sessions."""
        self.active = True
        self.stop_event.clear()
        self.thread = th.Thread(target=self._expire, daemon=True,
                                name='analysis-sessions')
        self.thread.start()

    def stop(self):
        """Close all sessions."""
        self.active = False
        self.stop_event.set()
        with self.lock:
            sessions = list(self.sessions.values())
            self.sessions.clear()
        for session in sessions:
            session.close()

    def create(self, process_id, dataset, pushdown=None):
        """Resolve the dataset and start a session on it.

        `pushdown` ({filters, search, where}) is applied by the database, so
        the sample is drawn from the matching records only.
        """
        if not self.active:
            raise SessionError('Analysis is not available', 503)
        settings = options()
        with self.lock:
            if len(self.sessions) >= settings['max_sessions']:
                raise SessionError(
                    f"All {settings['max_sessions']} analysis sessions of "
                    'this server are in use. Close an analysis page or '
                    'try again later.', 409)
        try:
            sql, meta = datasets.resolve(process_id, dataset)
            shown = datasets.display(sql, meta)
            pushdown = {key: value for key, value in (pushdown or {}).items()
                        if key in ('filters', 'search', 'where') and value}
            if pushdown:
                sql, shown = datasets.pushdown(sql, shown=shown, **pushdown)
                # A result table is read by its index, so its count is
                # cheap; a datasource's could be a scan of the whole window.
                exact = meta['kind'] == 'result'
                meta['total'] = datasets.count(sql) if exact else None
                meta['total_exact'] = exact
            meta['pushdown'] = pushdown or None
            meta['sql'] = shown
        except datasets.DatasetError as error:
            raise SessionError(str(error), 404)
        except Exception as error:
            raise SessionError(f'Dataset can not be read: {error}', 400)
        session = Session(self, meta, sql, settings)
        with self.lock:
            self.sessions[session.id] = session
        logger.info(f"Analysis session {session.id[:8]} started on "
                    f"{meta['control_name']} PID {process_id} {dataset} "
                    f'(worker PID {session.process.pid})')
        return session

    def get(self, session_id):
        """Get an open session, or fail with 404."""
        with self.lock:
            session = self.sessions.get(session_id)
        if session is None:
            raise SessionError('Analysis session not found or expired', 404)
        return session

    def close(self, session_id):
        """Close a session, if it is still open."""
        with self.lock:
            session = self.sessions.pop(session_id, None)
        if session:
            session.close()
            logger.info(f'Analysis session {session_id[:8]} closed')

    def forget(self, session):
        """Drop a session whose worker is gone."""
        with self.lock:
            if self.sessions.get(session.id) is session:
                self.sessions.pop(session.id)
        logger.warning(f'Analysis session {session.id[:8]} lost its worker')

    def notify(self, session):
        """Pass a state change to the listeners (the live events)."""
        payload = {'session_id': session.id, 'state': session.state}
        for listener in self.listeners:
            try:
                listener(payload)
            except Exception:
                pass

    def _expire(self):
        while not self.stop_event.wait(EXPIRY_INTERVAL):
            idle = options()['idle_minutes'] * 60
            now = time.monotonic()
            with self.lock:
                expired = [session for session in self.sessions.values()
                           if now - session.used > idle]
            for session in expired:
                logger.info(f'Analysis session {session.id[:8]} idle for '
                            f'{idle // 60} min, closing')
                self.close(session.id)
                session.state = {**session.state, 'status': 'expired'}
                self.notify(session)


sessions = SessionManager()
