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
from ..reader import reader

from . import journal
from .control import Control


SUPERVISION_INTERVAL = 2
WATCHDOG_INTERVAL = 5


def _is_late(since, limit):
    """Check that the given moment is further back than the time limit."""
    if not isinstance(limit, int) or not since:
        return False
    return (dt.datetime.now()-since).total_seconds() > limit


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
        self.canceled = False

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
            for job in pending+running:
                job.canceled = True
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
            # Stops a job whose process is built but not started yet.
            job.canceled = True
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
        """Finish runs of this server left active after a crash."""
        orphans = journal.read_orphans(self.name)
        swept = 0
        for orphan in orphans:
            try:
                if self._finalize(int(orphan['process_id']),
                                  'Control execution stopped because the '
                                  'server stopped unexpectedly.'):
                    swept += 1
            except Exception:
                logger.error()
        if swept:
            logger.warning(f'{swept} orphaned runs finished')

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
        state = reader.read_run_state(control.process_id)
        status = state['status'] if state else None
        if status != 'I':
            logger.info(f'{control} Dropped from queue as its status is '
                        f'{status}')
            with self.condition:
                if job in self.running:
                    self.running.remove(job)
                self.condition.notify_all()
            journal.update(job.event_id, event_type=journal.CANCELED,
                           message='Control run was canceled in queue.')
            if status is None:
                Control(process_id=control.process_id)._cancel_as_request()
            return
        context = mp.get_context('spawn')
        job.current = context.Value('q', control.process_id)
        process = context.Process(name=control.name, target=operate,
                                  args=(control, job.chain, job.current,
                                        os.getpid(), self.name))
        # Started under the lock, so that a cancel arriving right now either
        # stops the job here or finds a process it can terminate.
        with self.condition:
            if job.canceled:
                logger.info(f'{control} Not started as it was canceled')
                return
            job.process = process
            process.start()
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
                        self._settle(job)
                        finished = True
                    else:
                        self._check(job)
                except Exception:
                    logger.error()
            if finished:
                self._notify()
            time.sleep(SUPERVISION_INTERVAL)

    def _check(self, job):
        state = reader.read_run_state(job.process_id)
        if not state:
            return
        status, timeout = state['status'], state['timeout']
        if status is None:
            reason = 'request'
        elif status in ('S', 'P', 'F') and _is_late(state['start_date'],
                                                    timeout):
            reason = 'timeout'
        elif status in ('I', 'W') and _is_late(job.started, timeout):
            # Waiting for the instance limit or the control lock, which the
            # run itself does before it starts and can not time out on.
            reason = 'timeout'
        else:
            return
        logger.info(f'{job.control} Cancelation with {reason} received')
        with self.condition:
            if job not in self.running:
                return
            self.running.remove(job)
            self.condition.notify_all()
        self._kill(job, f'Control execution stopped because of the {reason}.')
        self._notify()

    def _settle(self, job):
        """Finish a run left active by a process that died without it.

        A process killed by the system, or lost to an error raised outside
        the control run flow, leaves its run in an active status forever:
        nothing else ever writes its outcome, and the UI keeps showing it as
        running until the next server start sweeps it.
        """
        exitcode = job.process.exitcode if job.process else None
        try:
            self._finalize(job.process_id,
                           'Control execution stopped because the control '
                           'process finished unexpectedly '
                           f'(exit code {exitcode}).')
        except Exception:
            logger.error()

    def _finalize(self, process_id, message):
        """Finish a run that nobody is performing any more.

        A run whose cancelation was requested becomes canceled, any other
        run still in an active status becomes an error. A run that already
        has an outcome is left as it is.

        Returns
        -------
        finished : bool
            Whether the run needed to be finished.
        """
        control = Control(process_id=process_id)
        if control.status not in (None, 'I', 'W', 'S', 'P', 'F'):
            return False
        # The process may have been killed while holding the control lock.
        control.executor.release_lock()
        if control.status is None:
            control._save_text_message('Control execution stopped because '
                                       'of the request.')
            control._set_as_canceled()
            return True
        logger.warning(f'{control} Run left in status {control.status} '
                       'without anyone performing it')
        control._save_text_message(message)
        control._set_as_error()
        return True

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
    if control._throttle():
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
