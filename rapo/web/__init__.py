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


class Server:
    """Represents application server."""

    def __init__(self, host=None, port=None, dev=False):
        argv = sys.argv[1:].copy()

        self.app = app
        self.host = host or config['API'].get('host') or '127.0.0.1'
        self.port = port or config['API'].get('port') or 8080
        self.dev = True if dev is True or 'dev' in argv else False
        # A reload restarts the scheduler with every change, so development
        # servers run without it unless asked to.
        self.scheduler = False if self.dev and '--scheduler' not in argv \
            else None

        self.table = db.tables.web_api
        self.record = reader.read_web_api_record()
        if self.record and self.record['status'] == 'Y':
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

        if argv:
            if argv[0] == 'start':
                self.start()
            elif argv[0] == 'stop':
                self.stop()

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
        if self.status is True:
            self.stop_date = dt.datetime.now()
            self.status = False
            if psutil.pid_exists(self.pid):
                os.kill(self.pid, signal.SIGTERM)
            update = self.table.update().values(stop_date=self.stop_date,
                                                status='N')
            db.execute(update)
