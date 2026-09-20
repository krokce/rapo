"""Contains web API elements."""

import datetime as dt
import getpass
import os
import platform
import signal
import subprocess as sp
import sys

import psutil

from .api import app
from ..config import config
from ..database import db
from ..reader import reader


APP = 'rapo.web.api.app:app'


def is_running(record):
    """Check that the recorded server is really running on this host.

    A server that crashed leaves its row marked as running. Trusting that
    PID makes `start` refuse to start and `stop` signal whatever process has
    taken the number since, so the record counts only when it names this
    host and the PID still belongs to a rapo server.
    """
    if not record or record['status'] != 'Y' or not record['pid']:
        return False
    if record['server'] != platform.node():
        return False
    try:
        process = psutil.Process(int(record['pid']))
        return APP in ' '.join(process.cmdline())
    except (psutil.Error, ValueError):
        return False


class Server:
    """Represents application server."""

    def __init__(self, host=None, port=None, dev=False, scheduler=None):
        self.app = app
        self.host = host or config['API'].get('host') or '127.0.0.1'
        self.port = port or config['API'].get('port') or 8080
        self.dev = bool(dev)
        # A reload restarts the scheduler with every change, so development
        # servers run without it unless asked to.
        self.scheduler = scheduler if scheduler is not None \
            else (False if self.dev else None)

        self.table = db.tables.web_api
        self.record = reader.read_web_api_record()
        if is_running(self.record):
            self.server = self.record['server']
            self.username = self.record['username']
            self.pid = int(self.record['pid'])
            self.start_date = self.record['start_date']
            self.stop_date = self.record['stop_date']
            self.status = True if self.record['status'] == 'Y' else False
        else:
            self.server = platform.node()
            self.username = getpass.getuser()
            self.pid = None
            self.start_date = None
            self.stop_date = None
            self.status = None

    def start(self):
        """Start web API server."""
        if self.status is True and self.pid and psutil.pid_exists(self.pid):
            message = f'web API already running at PID {self.pid}'
            raise Exception(message)
        script = [sys.executable, '-m', 'uvicorn', APP]
        args = ['--host', self.host, '--port', str(self.port)]
        env = os.environ.copy()
        if self.scheduler is False:
            env['RAPO_SCHEDULER'] = '0'
        self.start_date = dt.datetime.now()
        self.status = True
        if self.dev is True:
            cmd = [*script, *args, '--reload']
            try:
                proc = sp.Popen(cmd, env=env)
                self.pid = proc.pid
                update = (self.table.update()
                                    .values(server=self.server,
                                            username=self.username,
                                            pid=self.pid,
                                            url=f'{self.host}:{self.port}',
                                            debug='X',
                                            start_date=self.start_date,
                                            stop_date=self.stop_date,
                                            status='Y'))
                db.execute(update)
                proc.wait()
            except KeyboardInterrupt:
                self.stop_date = dt.datetime.now()
                update = (self.table.update()
                                    .values(stop_date=self.stop_date,
                                            status='N'))
                db.execute(update)
                proc.terminate()
        else:
            cmd = [*script, *args]
            proc = sp.Popen(cmd, env=env, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
            self.pid = proc.pid
            update = self.table.update().values(server=self.server,
                                                username=self.username,
                                                pid=self.pid,
                                                url=f'{self.host}:{self.port}',
                                                debug=None,
                                                start_date=self.start_date,
                                                stop_date=self.stop_date,
                                                status='Y')
            db.execute(update)

    def stop(self):
        """Stop web API server."""
        if self.status is not True:
            if self.record and self.record['status'] == 'Y':
                self._record_stop()
                print('Web API was not running, its record was cleared.')
            return
        self.status = False
        if psutil.pid_exists(self.pid):
            os.kill(self.pid, signal.SIGTERM)
        self._record_stop()

    def _record_stop(self):
        """Mark the web API record as stopped."""
        self.stop_date = dt.datetime.now()
        update = self.table.update().values(stop_date=self.stop_date,
                                            status='N')
        db.execute(update)
