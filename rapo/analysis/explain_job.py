"""Contains the discrepancy analysis jobs of the web server.

A job explains one side of a run (`explain.analyze`) in a spawned process,
one at a time per server, the rest queued. Its progress goes to the listeners
(the live events) and its report is kept in memory, the latest `CACHED` ones,
until the server stops; a recompute replaces it.
"""

import collections
import datetime as dt
import multiprocessing as mp
import os
import threading as th
import time

from ..config import config
from ..logger import logger

from . import explain


DEFAULTS = {
    'discrepancy_exact_rows': 5000000,
    'discrepancy_timeout_minutes': 20,
    'discrepancy_history_runs': 10,
}
CACHED = 20


def options():
    """Get the [ANALYSIS] options of the jobs, read at use."""
    section = config.get('ANALYSIS') or {}
    result = {}
    for name, default in DEFAULTS.items():
        value = section.get(name)
        try:
            result[name] = int(value) if value not in (None, '') else default
        except (TypeError, ValueError):
            result[name] = default
    return result


def work(conn, process_id, side, result_type, exact_rows, history_runs,
         parent_pid):
    """Run one job in the spawned process, reporting through `conn`."""
    from ..core.runner import watch
    th.Thread(target=watch, args=(parent_pid,), daemon=True).start()

    def progress(step, done, total):
        conn.send(('progress', {'step': step, 'done': done, 'total': total}))
    try:
        report = explain.analyze(process_id, side, result_type,
                                 exact_rows=exact_rows,
                                 history_runs=history_runs,
                                 progress=progress)
        conn.send(('done', explain.to_json(report)))
    except explain.ExplainError as error:
        conn.send(('error', str(error)))
    except Exception as error:
        message = str(error).strip().splitlines()[0] if str(error) else ''
        conn.send(('error', f'{type(error).__name__}: {message}'))
    conn.close()
    os._exit(0)


def _iso(moment):
    return moment.replace(microsecond=0).isoformat() if moment else None


class Job:
    """Represents one analysis of one side of a run."""

    def __init__(self, key):
        self.key = key
        self.state = 'queued'
        self.progress = None
        self.error = None
        self.report = None
        self.queued = dt.datetime.now()
        self.started = None
        self.finished = None

    def describe(self, report=True):
        """Get the job as the API answers it."""
        process_id, side, result_type = self.key
        result = {'process_id': process_id, 'side': side,
                  'result_type': result_type, 'state': self.state,
                  'progress': self.progress, 'error': self.error,
                  'queued': _iso(self.queued), 'started': _iso(self.started),
                  'finished': _iso(self.finished)}
        if report:
            result['report'] = self.report
        return result


class Explainer:
    """Represents the discrepancy analysis jobs of this server."""

    def __init__(self):
        self.jobs = collections.OrderedDict()
        self.queue = collections.deque()
        self.lock = th.Lock()
        self.wake = th.Event()
        self.active = False
        self.thread = None
        self.current = None
        self.listeners = []

    def start(self):
        """Start running the queued jobs."""
        self.active = True
        self.thread = th.Thread(target=self._run, daemon=True,
                                name='discrepancy-analysis')
        self.thread.start()

    def stop(self):
        """Stop the job in progress and forget the rest."""
        self.active = False
        self.wake.set()
        process = self.current
        if process is not None and process.is_alive():
            process.kill()

    def submit(self, process_id, side, result_type=None, recompute=False):
        """Get the job of a side of a run, queueing one when needed."""
        if not self.active:
            raise explain.ExplainError('Discrepancy analysis is not '
                                       'available')
        key = (int(process_id), side, result_type or None)
        with self.lock:
            job = self.jobs.get(key)
            if job and (not recompute or job.state in ('queued', 'running')):
                self.jobs.move_to_end(key)
                return job
            job = Job(key)
            self.jobs[key] = job
            self.jobs.move_to_end(key)
            self.queue.append(job)
            self._trim()
        self.wake.set()
        self.notify(job)
        return job

    def get(self, process_id, side, result_type=None):
        """Get the job of a side of a run, or None."""
        with self.lock:
            return self.jobs.get((int(process_id), side, result_type or None))

    def _trim(self):
        finished = [key for key, job in self.jobs.items()
                    if job.state in ('done', 'error')]
        while len(finished) > CACHED:
            self.jobs.pop(finished.pop(0), None)

    def notify(self, job):
        """Pass a job's state to the listeners (the live events)."""
        payload = job.describe(report=False)
        for listener in self.listeners:
            try:
                listener(payload)
            except Exception:
                pass

    def _run(self):
        while self.active:
            with self.lock:
                job = self.queue.popleft() if self.queue else None
            if job is None:
                self.wake.wait(5)
                self.wake.clear()
                continue
            try:
                self._perform(job)
            except Exception as error:
                job.state, job.error = 'error', str(error)
                logger.error(f'Discrepancy analysis {job.key} failed: {error}')
            job.finished = dt.datetime.now()
            self.notify(job)

    def _perform(self, job):
        settings = options()
        process_id, side, result_type = job.key
        job.state = 'running'
        job.started = dt.datetime.now()
        job.progress = {'step': 'Starting', 'done': 0,
                        'total': explain.STEPS}
        self.notify(job)
        context = mp.get_context('spawn')
        conn, child = context.Pipe(duplex=False)
        process = context.Process(
            name=f'rapo-explain-{process_id}', target=work,
            args=(child, process_id, side, result_type,
                  settings['discrepancy_exact_rows'],
                  settings['discrepancy_history_runs'], os.getpid()),
            daemon=True)
        process.start()
        child.close()
        self.current = process
        logger.info(f'Discrepancy analysis of PID {process_id} side '
                    f'{side.upper()}{" " + result_type if result_type else ""}'
                    f' started (worker PID {process.pid})')
        deadline = time.monotonic() + settings[
            'discrepancy_timeout_minutes'] * 60
        try:
            while True:
                left = deadline - time.monotonic()
                if left <= 0:
                    process.kill()
                    job.state = 'error'
                    job.error = (
                        'The analysis took longer than '
                        f"{settings['discrepancy_timeout_minutes']} minutes "
                        'and was stopped')
                    break
                if not self.active:
                    job.state, job.error = 'error', 'The server stopped'
                    break
                if not conn.poll(min(left, 1)):
                    if not process.is_alive() and not conn.poll(0):
                        job.state = 'error'
                        job.error = 'The analysis worker stopped'
                        break
                    continue
                try:
                    kind, payload = conn.recv()
                except (EOFError, OSError):
                    job.state = 'error'
                    job.error = 'The analysis worker stopped'
                    break
                if kind == 'progress':
                    job.progress = payload
                    self.notify(job)
                elif kind == 'done':
                    job.report, job.state = payload, 'done'
                    break
                elif kind == 'error':
                    job.state, job.error = 'error', payload
                    break
        finally:
            self.current = None
            conn.close()
            process.join(5)
            if process.is_alive():
                process.kill()
                process.join(2)
        seconds = (dt.datetime.now() - job.started).total_seconds()
        logger.info(f'Discrepancy analysis of PID {process_id} side '
                    f'{side.upper()} ended {job.state} in {seconds:.1f}s'
                    + (f': {job.error}' if job.error else ''))


explainer = Explainer()
