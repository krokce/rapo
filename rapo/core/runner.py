"""Contains control run manager of the web server.

All control runs of the server, scheduled or requested from the UI, go
through one run manager. Each run is initiated at once, so it is visible in
the UI, then waits in a FIFO queue for one of `control_parallelism`
execution slots and is performed in its own spawned OS process. Iterations
and cascades of a scheduled run are performed in the same process after the
run itself.

A supervisor thread follows every process and terminates it when its current
run is canceled (status voided in `rapo_log`) or exceeds its timeout.
"""

import collections
import datetime as dt
import multiprocessing as mp
import os
import platform
import threading as th
import time

from ..config import config
from ..database import db
from ..logger import logger, open_run_log

from . import journal
from .control import Control


SUPERVISION_INTERVAL = 2
WATCHDOG_INTERVAL = 5


def get_runner_name():
    """Get stable name of this server used to mark the runs it owns."""
    port = config['API'].get('port') if config.check('API') else None
    return f'{platform.node()}:{port or 8080}'


class Job:
    """Represents one control run owned by the run manager."""

    def __init__(self, control, event_id, trigger_type, chain):
        self.control = control
        self.event_id = event_id
        self.trigger_type = trigger_type
        self.chain = chain
        self.queued = dt.datetime.now()
        self.started = None
        self.process = None
        self.current = None
        self.checked = 0

    @property
    def process_id(self):
        """Get ID of the run currently performed by the job process."""
        if self.current is not None:
            return self.current.value
        return self.control.process_id

    def describe(self):
        """Get job description for the status report."""
        return {
            'event_id': self.event_id,
            'control_name': self.control.name,
            'trigger_type': self.trigger_type,
            'process_id': self.process_id,
            'pid': self.process.pid if self.process else None,
            'queued': self.queued,
            'started': self.started,
        }


class RunManager:
    """Represents control run manager."""

    def __init__(self):
        self.name = get_runner_name()
        self.condition = th.Condition()
        self.pending = collections.deque()
        self.running = []
        self.listeners = []
        self.active = False
        self.threads = []

    @property
    def capacity(self):
        """Get number of execution slots."""
        if config.check('SCHEDULER'):
            return config['SCHEDULER'].get('control_parallelism') or 10
        return 10

    def start(self):
        """Start run manager threads."""
        if self.active:
            return
        self.active = True
        try:
            self.sweep()
        except Exception:
            logger.error()
        for name, target in [('Run-Dispatcher', self._dispatch),
                             ('Run-Supervisor', self._supervise)]:
            thread = th.Thread(name=name, target=target, daemon=True)
            thread.start()
            self.threads.append(thread)
        logger.info(f'Run manager started as {self.name} '
                    f'with {self.capacity} slots')

    def stop(self):
        """Stop run manager killing all its runs at once."""
        if not self.active:
            return
        logger.info('Stopping run manager...')
        with self.condition:
            self.active = False
            pending = list(self.pending)
            running = list(self.running)
            self.pending.clear()
            self.condition.notify_all()
        message = 'Control execution stopped because of the server shutdown.'
        for job in running:
            self._kill(job, message)
        for job in pending:
            self._drop(job, message)
        logger.info('Run manager stopped')

    def submit(self, name, trigger_type, timestamp=None, chain=False,
               **params):
        """Initiate control run and queue it for execution.

        Returns
        -------
        event_id : int
            ID of the scheduler event recorded for this request.
        """
        if not self.active:
            raise RuntimeError('Run manager is not running')
        control = Control(name, timestamp=timestamp, **params)
        scheduled_time = journal.to_datetime(timestamp)
        event_id = journal.record(control.id, trigger_type, journal.FIRED,
                                  scheduled_time=scheduled_time,
                                  runner=self.name)
        if not control._initiate() or not control.process_id:
            journal.update(event_id, event_type=journal.FAILED,
                           message='Control could not be initiated.')
            self._notify()
            return event_id
        journal.update(event_id, process_id=control.process_id)
        job = Job(control, event_id, trigger_type, chain)
        with self.condition:
            self.pending.append(job)
            self.condition.notify_all()
        logger.info(f'{control} Queued as event {event_id} '
                    f'({trigger_type}), {len(self.pending)} in queue')
        self._notify()
        return event_id

    def cancel(self, process_id):
        """Cancel run owned by this manager.

        Returns
        -------
        found : bool
            False when the run is not owned by this manager.
        """
        message = 'Control execution stopped because of the request.'
        with self.condition:
            job = next((job for job in self.pending
                        if job.process_id == process_id), None)
            if job:
                self.pending.remove(job)
            else:
                job = next((job for job in self.running
                            if job.process_id == process_id), None)
                if not job:
                    return False
                self.running.remove(job)
                self.condition.notify_all()
        if job.process is None:
            self._drop(job, message)
        else:
            self._kill(job, message)
        self._notify()
        return True

    def status(self):
        """Get run manager status report."""
        with self.condition:
            pending = [job.describe() for job in self.pending]
            running = [job.describe() for job in self.running]
        return {
            'runner': self.name,
            'active': self.active,
            'capacity': self.capacity,
            'queued': pending,
            'running': running,
        }

    def sweep(self):
        """Mark runs of this server left active after a crash as errors."""
        orphans = journal.read_orphans(self.name)
        for orphan in orphans:
            process_id = int(orphan['process_id'])
            try:
                control = Control(process_id=process_id)
                control._save_text_message('Control execution stopped '
                                           'because the server stopped '
                                           'unexpectedly.')
                control._set_as_error()
            except Exception:
                logger.error()
        if orphans:
            logger.warning(f'{len(orphans)} orphaned runs marked as errors')

    def _dispatch(self):
        while True:
            with self.condition:
                while self.active and (not self.pending or
                                       len(self.running) >= self.capacity):
                    self.condition.wait()
                if not self.active:
                    return
                job = self.pending.popleft()
                self.running.append(job)
            try:
                self._spawn(job)
            except Exception as error:
                logger.error()
                with self.condition:
                    if job in self.running:
                        self.running.remove(job)
                    self.condition.notify_all()
                try:
                    journal.update(job.event_id, event_type=journal.FAILED,
                                   message=str(error))
                    job.control._save_text_message(
                        f'Control process could not be started: {error}')
                    job.control._set_as_error()
                except Exception:
                    logger.error()
            self._notify()

    def _spawn(self, job):
        control = job.control
        result = Control(process_id=control.process_id)
        if result.status != 'I':
            logger.info(f'{control} Dropped from queue as its status is '
                        f'{result.status}')
            with self.condition:
                if job in self.running:
                    self.running.remove(job)
                self.condition.notify_all()
            journal.update(job.event_id, event_type=journal.CANCELED,
                           message='Control run was canceled in queue.')
            if result.status is None:
                result._cancel_as_request()
            return
        context = mp.get_context('spawn')
        job.current = context.Value('q', control.process_id)
        job.process = context.Process(name=control.name, target=operate,
                                      args=(control, job.chain, job.current,
                                            os.getpid(), self.name))
        job.process.start()
        job.started = dt.datetime.now()
        journal.update(job.event_id, event_type=journal.STARTED,
                       start_time=job.started)
        logger.info(f'{control} Running as process on PID '
                    f'{job.process.pid} (event {job.event_id})')

    def _supervise(self):
        while self.active:
            with self.condition:
                running = [job for job in self.running if job.process]
            finished = False
            for job in running:
                try:
                    if not job.process.is_alive():
                        job.process.join()
                        with self.condition:
                            if job in self.running:
                                self.running.remove(job)
                                self.condition.notify_all()
                        logger.info(f'{job.control} Process at PID '
                                    f'{job.process.pid} returns '
                                    f'{job.process.exitcode}')
                        finished = True
                    else:
                        self._check(job)
                except Exception:
                    logger.error()
            if finished:
                self._notify()
            time.sleep(SUPERVISION_INTERVAL)

    def _check(self, job):
        process_id = job.process_id
        control = Control(process_id=process_id)
        if control.status is None:
            reason = 'request'
        elif control.status in ('S', 'P', 'F') and control.timeout:
            reason = 'timeout'
        else:
            return
        logger.info(f'{control} Cancelation with {reason} received')
        with self.condition:
            if job not in self.running:
                return
            self.running.remove(job)
            self.condition.notify_all()
        self._kill(job, f'Control execution stopped because of the {reason}.')
        self._notify()

    def _kill(self, job, message):
        process_id = job.process_id
        if job.process and job.process.is_alive():
            logger.info(f'{job.control} Terminating process at PID '
                        f'{job.process.pid}...')
            job.process.terminate()
            job.process.join(10)
        try:
            control = Control(process_id=process_id)
            if control.status not in ('D', 'E', 'C', 'X'):
                control._save_text_message(message)
                control._cancel()
        except Exception:
            logger.error()

    def _drop(self, job, message):
        try:
            journal.update(job.event_id, event_type=journal.CANCELED,
                           message=message)
            control = Control(process_id=job.control.process_id)
            if control.status not in ('D', 'E', 'C', 'X'):
                control._save_text_message(message)
                control._set_as_canceled()
        except Exception:
            logger.error()

    def _notify(self):
        for listener in self.listeners:
            try:
                listener()
            except Exception:
                logger.error()


def operate(control, chain, current, parent_pid, runner):
    """Perform control run in the spawned process."""
    watchdog = th.Thread(name='Watchdog', target=watch, args=(parent_pid,),
                         daemon=True)
    watchdog.start()

    def observe(run):
        current.value = run.process_id
        open_run_log(run.id, run.process_id)
        if run.trigger:
            journal.record(run.id, run.trigger, journal.STARTED,
                           scheduled_time=journal.to_datetime(run.timestamp),
                           process_id=run.process_id, runner=runner,
                           start_time=dt.datetime.now())

    open_run_log(control.id, control.process_id)
    logger.info(f'{control} Performed by process {os.getpid()} of {runner}')
    control.observer = observe
    control._throttle()
    control._resume()
    if chain:
        control.iterate()
        control.cascade()
    db.engine.dispose()


def watch(parent_pid):
    """Exit the process at once when the server process is gone."""
    while True:
        if os.getppid() != parent_pid:
            os._exit(1)
        time.sleep(WATCHDOG_INTERVAL)


runner = RunManager()
